from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from recall.scheduler.compressed_plan import (
    EXPECTED_PLAN_SHA256,
    PLAN_PATH,
    load_compressed_plan,
    parse_compressed_plan,
    resolve_declared_cycle,
)
from recall.scheduler.compressed_cohort import all_compressed_cases, cases_for_cycle
from recall.scheduler.compressed_identity import (
    manifest_artifact_id,
    mode_receipt_artifact_id,
    tick_run_id,
    trace_id,
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
        ("c3", 4),
        ("c4", 1),
        ("c5", 1),
        ("c6", 450),
    ]
    assert all(
        current.window_start.timestamp() - prior.window_end.timestamp() >= 1200
        for prior, current in zip(plan.cycles, plan.cycles[1:])
    )
    cases = all_compressed_cases(plan.cycles)
    assert len(cases) == 462
    assert sum(item.cycle_id == "historical-day1" for item in cases) == 1
    assert len(cases_for_cycle(plan.by_id("c6"))) == 450
    assert all(
        item.next_scan_at == plan.by_id(item.cycle_id).schedule_epoch
        for item in cases
        if item.cycle_id != "historical-day1"
    )


def test_resolver_requires_exactly_one_declared_window() -> None:
    plan = load_compressed_plan(ROOT)
    assert resolve_declared_cycle(
        datetime(2026, 8, 26, 20, 35, tzinfo=timezone.utc), plan
    ).cycle_id == "c1"
    with pytest.raises(RuntimeError, match="window_match_invalid:0"):
        resolve_declared_cycle(
            datetime(2026, 8, 26, 20, 45, tzinfo=timezone.utc), plan
        )


def test_plan_rejects_overlap_and_short_gap() -> None:
    value = copy.deepcopy(_wire())
    value["cycles"][1]["window_start"] = "2026-08-26T20:35:00Z"
    with pytest.raises(RuntimeError, match="gap_invalid"):
        parse_compressed_plan(value, sha256="0" * 64)


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
        datetime(2026, 8, 26, 20, 35, tzinfo=timezone.utc),
    )
    with pytest.raises(RuntimeError, match="window_match_invalid:2"):
        resolve_declared_cycle(
            datetime(2026, 8, 26, 20, 36, tzinfo=timezone.utc), overlapping
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
