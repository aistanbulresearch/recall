from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
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
    portfolio_case_vcv_bindings,
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


def _wire_for_schema(schema_version: str) -> dict[str, object]:
    value = copy.deepcopy(_wire())
    value["schema_version"] = schema_version
    if schema_version != "2.6.0":
        value["cycles"][2]["epoch_label"] = "PLAN6_R1_20"
        value["cycles"][3]["activation"] = "PROVISIONAL_R1_GATED"
        value["cycles"][3]["epoch_label"] = "PLAN6_R2_80_PROVISIONAL"
    else:
        value["cycles"][3]["activation"] = "ACTIVE"
        value["cycles"][3]["epoch_label"] = "PLAN6_R2_80_ACTIVE"
    if schema_version == "2.3.0":
        for cycle in value["cycles"]:
            cycle.pop("write_timeout_seconds")
            cycle.pop("agent_timeout_seconds")
    return value


def test_schema_260_accepts_exact_plan9_r1_retry() -> None:
    value = _wire_for_schema("2.6.0")
    value["cycles"][2]["epoch_label"] = "PLAN6_RAMP_FIRST_PASS_RETRY"
    value["cycles"][3]["activation"] = "ACTIVE"

    plan = parse_compressed_plan(value, sha256="0" * 64)

    assert plan.by_id("c3").epoch_label == "PLAN6_RAMP_FIRST_PASS_RETRY"
    assert plan.by_id("c3").predecessor == load_compressed_plan(ROOT).by_id(
        "c3"
    ).predecessor
    assert [plan.by_id(item).predecessor.binding for item in ("c4", "c5", "c6")] == [
        "CURRENT_PLAN",
        "CURRENT_PLAN",
        "CURRENT_PLAN",
    ]
    assert [item.activation for item in plan.cycles] == [
        "IMMUTABLE_EXECUTED",
        "IMMUTABLE_EXECUTED",
        "ACTIVE",
        "ACTIVE",
        "PROVISIONAL_R1_GATED",
        "PROVISIONAL_R1_GATED",
    ]
    assert plan.by_id("c4").epoch_label == "PLAN6_R2_80_ACTIVE"


@pytest.mark.parametrize("schema_version", ["2.4.0", "2.5.0"])
def test_legacy_schema_rejects_plan9_retry_epoch(schema_version: str) -> None:
    value = _wire_for_schema(schema_version)
    value["cycles"][2]["epoch_label"] = "PLAN6_RAMP_FIRST_PASS_RETRY"

    with pytest.raises(RuntimeError, match="compressed_retry_schema_invalid"):
        parse_compressed_plan(value, sha256="0" * 64)


def test_schema_260_rejects_unlabelled_retry() -> None:
    value = _wire_for_schema("2.6.0")
    value["cycles"][2]["epoch_label"] = "PLAN6_R1_20"
    value["cycles"][3]["activation"] = "ACTIVE"

    with pytest.raises(RuntimeError, match="compressed_retry_epoch_invalid"):
        parse_compressed_plan(value, sha256="0" * 64)


def test_schema_260_rejects_provisional_label_on_active_c4() -> None:
    value = _wire_for_schema("2.6.0")
    value["cycles"][3]["epoch_label"] = "PLAN6_R2_80_PROVISIONAL"

    with pytest.raises(RuntimeError, match="compressed_active_epoch_invalid"):
        parse_compressed_plan(value, sha256="0" * 64)


def test_schema_260_preserves_current_plan_successor_chain() -> None:
    value = _wire_for_schema("2.6.0")
    value["cycles"][2]["epoch_label"] = "PLAN6_RAMP_FIRST_PASS_RETRY"
    value["cycles"][3]["activation"] = "ACTIVE"
    value["cycles"][3]["predecessor"] = copy.deepcopy(
        value["cycles"][2]["predecessor"]
    )
    value["cycles"][3]["predecessor"]["cycle_id"] = "c3"

    with pytest.raises(RuntimeError, match="compressed_current_predecessor_invalid"):
        parse_compressed_plan(value, sha256="0" * 64)


@pytest.mark.parametrize(
    "active_tail",
    [
        ["ACTIVE", "PROVISIONAL_R1_GATED", "PROVISIONAL_R1_GATED", "PROVISIONAL_R1_GATED"],
        ["ACTIVE", "ACTIVE", "ACTIVE", "PROVISIONAL_R1_GATED"],
        ["ACTIVE", "ACTIVE", "PROVISIONAL_R1_GATED", "ACTIVE"],
    ],
)
def test_schema_260_rejects_non_plan9_activation_tuple(
    active_tail: list[str],
) -> None:
    value = _wire_for_schema("2.6.0")
    value["cycles"][2]["epoch_label"] = "PLAN6_RAMP_FIRST_PASS_RETRY"
    for cycle, activation in zip(value["cycles"][2:], active_tail, strict=True):
        cycle["activation"] = activation

    with pytest.raises(RuntimeError, match="compressed_cycle_activation_invalid"):
        parse_compressed_plan(value, sha256="0" * 64)


@pytest.mark.parametrize("active_count", [1, 2, 3, 4])
def test_schema_250_accepts_ordered_active_prefix(active_count: int) -> None:
    value = _wire_for_schema("2.5.0")
    for index, cycle in enumerate(value["cycles"][2:]):
        cycle["activation"] = (
            "ACTIVE" if index < active_count else "PROVISIONAL_R1_GATED"
        )

    plan = parse_compressed_plan(value, sha256="0" * 64)

    assert [item.activation for item in plan.cycles[2:]] == [
        "ACTIVE" if index < active_count else "PROVISIONAL_R1_GATED"
        for index in range(4)
    ]


@pytest.mark.parametrize(
    "activations",
    [
        ["PROVISIONAL_R1_GATED"] * 4,
        ["PROVISIONAL_R1_GATED", "ACTIVE", "ACTIVE", "ACTIVE"],
        ["ACTIVE", "PROVISIONAL_R1_GATED", "ACTIVE", "PROVISIONAL_R1_GATED"],
        ["ACTIVE", "UNKNOWN", "PROVISIONAL_R1_GATED", "PROVISIONAL_R1_GATED"],
    ],
)
def test_schema_250_rejects_invalid_activation_order(
    activations: list[str],
) -> None:
    value = _wire_for_schema("2.5.0")
    for cycle, activation in zip(value["cycles"][2:], activations, strict=True):
        cycle["activation"] = activation

    with pytest.raises(RuntimeError, match="compressed_cycle_activation_invalid"):
        parse_compressed_plan(value, sha256="0" * 64)


def test_schema_250_requires_immutable_executed_prefix() -> None:
    value = _wire_for_schema("2.5.0")
    value["cycles"][1]["activation"] = "ACTIVE"

    with pytest.raises(RuntimeError, match="compressed_cycle_activation_invalid"):
        parse_compressed_plan(value, sha256="0" * 64)


@pytest.mark.parametrize("schema_version", ["2.3.0", "2.4.0"])
def test_legacy_activation_contract_is_unchanged(schema_version: str) -> None:
    value = _wire_for_schema(schema_version)
    parse_compressed_plan(value, sha256="0" * 64)
    for cycle in value["cycles"][2:]:
        cycle["activation"] = "ACTIVE"

    with pytest.raises(RuntimeError, match="compressed_cycle_activation_invalid"):
        parse_compressed_plan(value, sha256="0" * 64)


def test_schema_250_preserves_phase_timeout_validation() -> None:
    value = _wire_for_schema("2.5.0")
    value["cycles"][2]["agent_timeout_seconds"] = 0

    with pytest.raises(RuntimeError, match="compressed_phase_timeout_invalid"):
        parse_compressed_plan(value, sha256="0" * 64)


def test_schema_250_requires_phase_timeout_fields() -> None:
    value = _wire_for_schema("2.5.0")
    value["cycles"][2].pop("write_timeout_seconds")

    with pytest.raises(RuntimeError, match="compressed_cycle_shape_invalid"):
        parse_compressed_plan(value, sha256="0" * 64)


def test_schema_250_preserves_execution_profile_validation() -> None:
    value = _wire_for_schema("2.5.0")
    value["cycles"][2]["execution_profile"] = "CREATE_ONLY_V1"

    with pytest.raises(RuntimeError, match="compressed_execution_profile_invalid"):
        parse_compressed_plan(value, sha256="0" * 64)


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
    assert [item.window_start.isoformat() for item in plan.cycles[:2]] == [
        "2026-08-26T20:40:00+00:00",
        "2026-08-26T22:30:00+00:00",
    ]
    assert [
        (
            item.cycle_id,
            item.window_start.isoformat(),
            item.window_end.isoformat(),
        )
        for item in plan.cycles[2:]
    ] == [
        ("c3", "2026-08-29T10:00:00+00:00", "2026-08-29T10:29:59+00:00"),
        ("c4", "2026-08-29T10:55:00+00:00", "2026-08-29T12:54:59+00:00"),
        ("c5", "2026-08-29T13:19:00+00:00", "2026-08-29T17:18:59+00:00"),
        ("c6", "2026-08-29T17:47:00+00:00", "2026-08-30T01:46:59+00:00"),
    ]
    assert [item.window_end - item.window_start for item in plan.cycles[2:]] == [
        timedelta(minutes=29, seconds=59),
        timedelta(hours=1, minutes=59, seconds=59),
        timedelta(hours=3, minutes=59, seconds=59),
        timedelta(hours=7, minutes=59, seconds=59),
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
        "ACTIVE", "PROVISIONAL_R1_GATED",
        "PROVISIONAL_R1_GATED",
    ]
    assert plan.by_id("c3").epoch_label == "PLAN6_RAMP_FIRST_PASS_RETRY"
    assert plan.by_id("c4").epoch_label == "PLAN6_R2_80_ACTIVE"
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


def test_external_note_universe_is_exactly_462_with_six_historical_additions() -> None:
    plan = load_compressed_plan(ROOT)
    bindings = portfolio_case_vcv_bindings(plan.cycles)
    final_pool = {item.case_id for item in cases_for_cycle(plan.by_id("c6"))}
    historical = set(bindings) - final_pool

    assert len(bindings) == 462
    assert historical == {
        "b54d172c-d4c7-53d9-b6ea-a8ae154a84d3",
        "b8390531-4c50-5f26-83da-0a1dadf07acf",
        "6c0e023a-69de-57f3-8f0b-f1107ac7d1e4",
        "420c82a9-c37d-5d40-826a-bda26184ae34",
        "c4e45bde-971b-52ee-9ba3-f182432146fa",
        "f453187b-b739-598d-a266-604dba66b6e5",
    }
    assert {case_id: bindings[case_id] for case_id in historical} == {
        "b54d172c-d4c7-53d9-b6ea-a8ae154a84d3": None,
        "b8390531-4c50-5f26-83da-0a1dadf07acf": None,
        "6c0e023a-69de-57f3-8f0b-f1107ac7d1e4": None,
        "420c82a9-c37d-5d40-826a-bda26184ae34": None,
        "c4e45bde-971b-52ee-9ba3-f182432146fa": "VCV002895953.1",
        "f453187b-b739-598d-a266-604dba66b6e5": "VCV002895953.4",
    }
    assert sum(vcv is not None for vcv in bindings.values()) == 5


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

    c4_inside_window = plan.by_id("c4").window_start + timedelta(minutes=30)
    assert resolve_declared_cycle(c4_inside_window, plan).cycle_id == "c4"
    for cycle_id in ("c5", "c6"):
        with pytest.raises(RuntimeError, match="compressed_cycle_not_active"):
            cycle = plan.by_id(cycle_id)
            resolve_declared_cycle(cycle.window_start + timedelta(minutes=1), plan)


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


def test_plan9_retry_uses_fresh_c3_namespace_without_changing_case_set() -> None:
    plan = load_compressed_plan(ROOT)
    c3 = plan.by_id("c3")
    failed_plan = replace(
        plan,
        sha256=(
            "fe3a1d5650daf27fd72b31030d5f7e26cf75b7ffd6cb1f7220c5c86f4c869b61"
        ),
    )

    assert collection_prefix(plan, c3) != collection_prefix(failed_plan, c3)
    assert tick_run_id(plan, c3) != tick_run_id(failed_plan, c3)
    assert manifest_artifact_id(plan, c3) != manifest_artifact_id(failed_plan, c3)
    assert [item.case_id for item in cases_for_cycle(c3)] == [
        item.case_id for item in cases_for_cycle(failed_plan.by_id("c3"))
    ]
