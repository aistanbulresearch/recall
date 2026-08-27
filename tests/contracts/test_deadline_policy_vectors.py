from __future__ import annotations

import json
from pathlib import Path

import pytest

from recall.contracts.errors import ContractError
from recall.contracts.payloads.scheduler_v33 import _parse_deadline
from recall.scheduler.compressed_plan import load_compressed_plan
from recall.testing.deadline_policy_vectors import (
    VECTOR_PATH,
    render_deadline_policy_vectors,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_committed_deadline_vectors_are_generated_by_core() -> None:
    assert (REPO_ROOT / VECTOR_PATH).read_bytes() == render_deadline_policy_vectors(
        REPO_ROOT
    )


def test_core_parser_matches_every_deadline_golden_vector() -> None:
    fixture = json.loads((REPO_ROOT / VECTOR_PATH).read_text(encoding="utf-8"))
    plan = load_compressed_plan(REPO_ROOT)
    observed: dict[str, str] = {}
    for vector in fixture["vectors"]:
        value = {
            **vector["manifest_context"],
            "deadline_policy": vector["deadline_policy"],
        }
        try:
            _parse_deadline(value)
            cycle = plan.by_id(vector["manifest_context"]["cycle_id"])
            locked = (
                cycle.window_start.isoformat().replace("+00:00", "Z"),
                cycle.window_end.isoformat().replace("+00:00", "Z"),
                cycle.schedule_epoch,
            )
            presented = tuple(
                vector["manifest_context"][field]
                for field in ("window_start", "window_end", "scheduled_for")
            )
            if presented != locked:
                raise ContractError("contract_value_invalid", "deadline_policy.plan_context")
        except ContractError:
            observed[vector["vector_id"]] = "REJECT"
        else:
            observed[vector["vector_id"]] = "ACCEPT"

    expected = {
        vector["vector_id"]: vector["expected"] for vector in fixture["vectors"]
    }
    assert observed == expected


def test_valid_vector_retains_sub_microsecond_cross_runtime_boundary() -> None:
    fixture = json.loads((REPO_ROOT / VECTOR_PATH).read_text(encoding="utf-8"))
    valid = next(
        item
        for item in fixture["vectors"]
        if item["vector_id"] == "valid_c3_fractional_microseconds"
    )
    fraction = valid["deadline_policy"]["trigger_started_at"].split(".")[1][:-1]
    assert len(fraction) == 7


@pytest.mark.parametrize(
    "vector_id",
    [
        "legacy_20_00_plus_3600_to_23_00",
        "coherent_phase_repartition",
        "unknown_plan_hash",
    ],
)
def test_required_no_ship_regressions_stay_rejected(vector_id: str) -> None:
    fixture = json.loads((REPO_ROOT / VECTOR_PATH).read_text(encoding="utf-8"))
    vector = next(item for item in fixture["vectors"] if item["vector_id"] == vector_id)
    assert vector["expected"] == "REJECT"
