from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from recall.contracts import parse_artifact
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.scheduler.compressed_plan import (
    EXPECTED_PLAN_SHA256,
    PLAN_PATH,
    load_compressed_plan,
    parse_compressed_plan,
    resolve_declared_cycle,
    PLAN3_SHA256,
)
from recall.scheduler.compressed_cohort import (
    all_compressed_cases,
    cases_for_cycle,
    portfolio_cases,
)
from recall.scheduler.compressed_identity import (
    collection_prefix,
    manifest_artifact_id,
    mode_receipt_artifact_id,
    tick_run_id,
    trace_id,
    evidence_collection_prefix,
    evidence_manifest_artifact_id,
)
from recall.scheduler.manifest import manifest_artifact_id as legacy_manifest_id


ROOT = Path(__file__).resolve().parents[2]


def _wire() -> dict[str, object]:
    return json.loads((ROOT / PLAN_PATH).read_text(encoding="utf-8"))


def test_locked_plan_has_exact_table_and_verification_gaps() -> None:
    plan = load_compressed_plan(ROOT)
    assert plan.sha256 == EXPECTED_PLAN_SHA256
    assert [(item.cycle_id, item.runs_predicted) for item in plan.cycles] == [
        ("c1", 3),
        ("c2", 2),
        ("c3", 20),
        ("c4", 80),
        ("c5", 200),
        ("c6", 456),
    ]
    assert [item.window_start.isoformat() for item in plan.cycles] == [
        "2026-08-26T20:40:00+00:00",
        "2026-08-26T22:30:00+00:00",
        "2026-08-27T12:00:00+00:00",
        "2026-08-28T09:00:00+00:00",
        "2026-08-29T09:00:00+00:00",
        "2026-08-30T09:00:00+00:00",
    ]
    assert all(
        current.window_start.timestamp() - prior.window_start.timestamp() >= 1200
        for prior, current in zip(plan.cycles, plan.cycles[1:])
    )
    c2 = plan.by_id("c2")
    assert c2.predecessor is not None
    assert c2.predecessor.plan_sha256 == PLAN3_SHA256
    assert evidence_collection_prefix(plan, plan.by_id("c1")) == (
        "dev_recall_m2_compressed_p5f18998f11c1_c1_20260826_"
    )
    assert evidence_manifest_artifact_id(plan, plan.by_id("c1")) == (
        "bd51bd00-fcf4-5d91-a45d-4d203e02127c"
    )
    assert all(item.write_path == "FIRESTORE_BATCH_V1" for item in plan.cycles[2:])
    assert [item.execution_profile for item in plan.cycles] == [
        "CREATE_ONLY_V1", "CREATE_ONLY_V1", "FULL_AUDIT_V1",
        "FULL_AUDIT_V1", "FULL_AUDIT_V1", "FULL_AUDIT_V1",
    ]
    assert [item.activation for item in plan.cycles] == [
        "IMMUTABLE_EXECUTED", "IMMUTABLE_EXECUTED", "ACTIVE",
        "PROVISIONAL_R1_GATED", "PROVISIONAL_R1_GATED",
        "PROVISIONAL_R1_GATED",
    ]
    cases = all_compressed_cases(plan.cycles)
    assert len(cases) == 762
    assert len({(item.case_id, item.cycle_id) for item in cases}) == 762
    assert len(portfolio_cases(plan.cycles)) == 462
    assert sum(item.cycle_id == "historical-day1" for item in cases) == 1
    assert [len(cases_for_cycle(plan.by_id(item))) for item in ("c3", "c4", "c5", "c6")] == [20, 80, 200, 456]
    assert set(item.case_id for item in cases_for_cycle(plan.by_id("c3"))).isdisjoint(
        item.case_id for item in cases_for_cycle(plan.by_id("c4"))
    )
    assert all(
        item.next_scan_at == plan.by_id(item.cycle_id).schedule_epoch
        for item in cases
        if item.cycle_id != "historical-day1"
    )


def test_executed_manifest_exports_match_external_plan_bindings() -> None:
    plan = load_compressed_plan(ROOT)
    for cycle_id, successor_id in (("c1", "c2"), ("c2", "c3")):
        binding = plan.by_id(successor_id).predecessor
        assert binding is not None
        wire = json.loads(
            (
                ROOT
                / "artifacts/evidence/cohort-compression/executed-manifests"
                / f"{cycle_id}-manifest.json"
            ).read_text(encoding="utf-8")
        )
        parsed = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
        assert parsed.schema_name == "CohortDayManifest"
        assert parsed.artifact_id == binding.manifest_artifact_id
        assert parsed.content_hash == binding.manifest_content_hash


def test_resolver_requires_exactly_one_declared_window() -> None:
    plan = load_compressed_plan(ROOT)
    assert resolve_declared_cycle(
        datetime(2026, 8, 26, 20, 45, tzinfo=timezone.utc), plan
    ).cycle_id == "c1"
    with pytest.raises(RuntimeError, match="window_match_invalid:0"):
        resolve_declared_cycle(
            datetime(2026, 8, 26, 20, 55, tzinfo=timezone.utc), plan
        )

    with pytest.raises(RuntimeError, match="compressed_cycle_not_active"):
        resolve_declared_cycle(
            datetime(2026, 8, 28, 9, 30, tzinfo=timezone.utc), plan
        )


def test_plan_rejects_overlap_and_short_gap() -> None:
    value = copy.deepcopy(_wire())
    value["cycles"][3]["window_start"] = "2026-08-27T09:10:00Z"
    with pytest.raises(RuntimeError, match="start_interval_invalid"):
        parse_compressed_plan(value, sha256="0" * 64)


def test_plan_rejects_external_predecessor_drift_and_missing_batch_gate() -> None:
    predecessor = copy.deepcopy(_wire())
    predecessor["cycles"][1]["predecessor"]["manifest_artifact_id"] = (
        "00000000-0000-4000-8000-000000000001"
    )
    with pytest.raises(RuntimeError, match="external_predecessor_invalid"):
        parse_compressed_plan(predecessor, sha256="0" * 64)
    batch = copy.deepcopy(_wire())
    batch["cycles"][5]["write_path"] = "SERIAL_VERIFIED"
    with pytest.raises(RuntimeError, match="batch_gate_missing"):
        parse_compressed_plan(batch, sha256="0" * 64)


def test_plan_hash_rejects_prediction_table_drift(tmp_path: Path) -> None:
    value = copy.deepcopy(_wire())
    value["cycles"][0]["runs_predicted"] = 4
    target = tmp_path / PLAN_PATH
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(RuntimeError, match="compressed_plan_hash_mismatch"):
        load_compressed_plan(tmp_path)


def test_resolver_rejects_ambiguous_windows_even_if_parser_is_bypassed() -> None:
    plan = load_compressed_plan(ROOT)
    overlapping = copy.deepcopy(plan)
    object.__setattr__(
        overlapping.cycles[1],
        "window_start",
        datetime(2026, 8, 26, 20, 45, tzinfo=timezone.utc),
    )
    with pytest.raises(RuntimeError, match="window_match_invalid:2"):
        resolve_declared_cycle(
            datetime(2026, 8, 26, 20, 46, tzinfo=timezone.utc), overlapping
        )


def test_cycle_identities_are_unique_and_do_not_collide_with_legacy() -> None:
    plan = load_compressed_plan(ROOT)
    ticks = [tick_run_id(plan, item) for item in plan.cycles]
    manifests = [manifest_artifact_id(plan, item) for item in plan.cycles]
    receipts = [mode_receipt_artifact_id(plan, item) for item in plan.cycles]
    traces = [
        trace_id(plan, cycle, cases_for_cycle(cycle)[0].case_id)
        for cycle in plan.cycles
    ]
    assert len(set(ticks + manifests + receipts + traces)) == 24
    assert not set(manifests) & {
        legacy_manifest_id(item.cohort_due_date) for item in plan.cycles
    }
    prefixes = [collection_prefix(plan, item) for item in plan.cycles]
    assert len(set(prefixes)) == 6
    assert all(f"_p{plan.sha256[:12]}_" in item for item in prefixes)
    assert collection_prefix(replace(plan, sha256="f" * 64), plan.cycles[0]) != prefixes[0]
