from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

import pytest

from recall.contracts import ContractError, content_hash, parse_artifact
from recall.contracts.payloads.scheduler_v34_support import (
    FINAL_ONLY_OWNER_RELEASE_REASON,
    FINAL_ONLY_OWNER_RELEASE_TOKEN,
)
from recall.ledger.producers import PRODUCER_REGISTRY
from tests.support.compressed_v33_manifest import build_valid_c3_manifest


def _id(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"final-only:{label}"))


def _history_binding(
    cycle_id: str,
    label: str,
    *,
    role: str,
    status: str,
    mode: bool,
) -> dict[str, object]:
    return {
        "cycle_id": cycle_id,
        "evidence_role": role,
        "execution_status": status,
        "plan_sha256": "a" * 64,
        "collection_prefix": f"history_{label}_",
        "manifest_artifact_id": _id(f"{label}:manifest"),
        "manifest_content_hash": "b" * 64,
        "mode_receipt_artifact_id": _id(f"{label}:mode") if mode else None,
        "mode_receipt_content_hash": "c" * 64 if mode else None,
    }


def _coherently_change_agent_budget(value: dict[str, object]) -> None:
    deadline = value["deadline_policy"]
    assert isinstance(deadline, dict)
    write_completed = datetime.fromisoformat(
        str(deadline["write_completed_at"]).replace("Z", "+00:00")
    )
    end_to_end = datetime.fromisoformat(
        str(deadline["authoritative_end_to_end_deadline"]).replace(
            "Z", "+00:00"
        )
    )
    deadline["agent_timeout_seconds"] = 26_999
    deadline["agent_deadline"] = min(
        write_completed + timedelta(seconds=26_999), end_to_end
    ).isoformat().replace("+00:00", "Z")


def _misstate_parity_count(value: dict[str, object], field: str) -> None:
    parity = value["parity"]
    assert isinstance(parity, dict)
    parity[field] = int(parity[field]) + 1


def _as_owner_release(value: dict[str, object]) -> None:
    static_end = datetime.fromisoformat(
        str(value["window_end"]).replace("Z", "+00:00")
    )
    actual_start = static_end + timedelta(seconds=1)
    write_completed = actual_start + timedelta(seconds=1)
    agent_completed = actual_start + timedelta(seconds=2)
    value["created_at"] = agent_completed.isoformat().replace("+00:00", "Z")
    value["warnings"] = [
        {
            "code": FINAL_ONLY_OWNER_RELEASE_TOKEN,
            "message_key": FINAL_ONLY_OWNER_RELEASE_REASON,
            "related_artifact_ids": [],
        },
        {
            "code": "CLOUD_RUN_MAX_RETRIES_0",
            "message_key": "OWNER_RELEASE_EXTERNAL_ACTIVATION_FACT",
            "related_artifact_ids": [],
        },
    ]
    value["deadline_policy"] = {
        "trigger_started_at": actual_start.isoformat().replace("+00:00", "Z"),
        "trigger_window_end": actual_start.isoformat().replace("+00:00", "Z"),
        "write_timeout_seconds": 1_800,
        "write_deadline": (actual_start + timedelta(seconds=1_800))
        .isoformat()
        .replace("+00:00", "Z"),
        "write_completed_at": write_completed.isoformat().replace(
            "+00:00", "Z"
        ),
        "agent_timeout_seconds": 27_000,
        "agent_deadline": (write_completed + timedelta(seconds=27_000))
        .isoformat()
        .replace("+00:00", "Z"),
        "agent_completed_at": agent_completed.isoformat().replace(
            "+00:00", "Z"
        ),
        "execution_timeout_seconds": 28_800,
        "authoritative_end_to_end_deadline": (
            actual_start + timedelta(seconds=28_800)
        )
        .isoformat()
        .replace("+00:00", "Z"),
    }
    value["execution_history"][-1]["executed_at"] = value["created_at"]
    compressed = value["execution_history"][2:]
    value["cumulative"]["distinct_execution_dates"] = len(
        {
            str(row["executed_at"])[:10]
            for row in compressed
            if row["executed_at"] is not None
        }
    )


@pytest.fixture(scope="module")
def final_only_wire() -> dict[str, object]:
    _plan, parsed, _legacy = build_valid_c3_manifest()
    wire = parsed.to_wire()
    wire["schema_version"] = "3.4.0"
    wire["cycle_id"] = "c6"
    wire["cycle_index"] = 6
    wire["day_index"] = 7
    wire["plan_sha256"] = "e" * 64
    wire["epoch_label"] = "PLAN6_FINAL_456_REASSESSMENT_ACTIVE"
    wire["evaluation_role"] = "PORTFOLIO_REASSESSMENT"
    wire["previous_manifest_id"] = None
    wire["ramp_gate_receipt_id"] = None
    wire["headroom_receipt_id"] = None
    start = datetime.fromisoformat("2026-08-29T16:00:00+00:00")
    end = datetime.fromisoformat("2026-08-29T23:43:59+00:00")
    write_completed = start + timedelta(seconds=1)
    agent_completed = start + timedelta(seconds=2)
    wire.update(
        {
            "window_start": "2026-08-29T16:00:00Z",
            "window_end": "2026-08-29T23:43:59Z",
            "scheduled_for": "2026-08-29T16:00:00Z",
            "created_at": agent_completed.isoformat().replace("+00:00", "Z"),
            "deadline_policy": {
                "trigger_started_at": "2026-08-29T16:00:00Z",
                "trigger_window_end": "2026-08-29T23:43:59Z",
                "write_timeout_seconds": 1_800,
                "write_deadline": (
                    start + timedelta(seconds=1_800)
                ).isoformat().replace("+00:00", "Z"),
                "write_completed_at": write_completed.isoformat().replace(
                    "+00:00", "Z"
                ),
                "agent_timeout_seconds": 27_000,
                "agent_deadline": (
                    write_completed + timedelta(seconds=27_000)
                ).isoformat().replace("+00:00", "Z"),
                "agent_completed_at": agent_completed.isoformat().replace(
                    "+00:00", "Z"
                ),
                "execution_timeout_seconds": 28_800,
                "authoritative_end_to_end_deadline": (
                    start + timedelta(seconds=28_800)
                ).isoformat().replace("+00:00", "Z"),
            },
        }
    )
    for outcome in wire["run_outcomes"]:
        outcome["epoch_label"] = wire["epoch_label"]

    bindings = [
        _history_binding(
            "c1", "c1", role="IMMUTABLE_EXECUTED", status="COMPLETE", mode=True
        ),
        _history_binding(
            "c2", "c2", role="IMMUTABLE_EXECUTED", status="COMPLETE", mode=True
        ),
        _history_binding(
            "c3", "c3-a", role="HISTORICAL_ATTEMPT", status="INCOMPLETE", mode=False
        ),
        _history_binding(
            "c3", "c3-b", role="HISTORICAL_ATTEMPT", status="INCOMPLETE", mode=False
        ),
    ]
    verified_ids = [
        artifact_id
        for binding in bindings
        for artifact_id in (
            binding["manifest_artifact_id"],
            binding["mode_receipt_artifact_id"],
        )
        if artifact_id is not None
    ]
    wire["final_only_supersession"] = {
        "mode": "FINAL_ONLY_TIMEBOX",
        "superseded_plan_sha256": (
            "c3e454c1b593c98a558c3f03c67b7de6f5d0e2d1e3c98efdfb91d4c5530a9791"
        ),
        "owner_decision": "RETIRE_RAMP_DUE_TIMEBOX_AND_AUTHORIZE_FINAL_456",
        "reason_code": "RAMP_TIMEBOX_EXHAUSTED",
        "historical_evidence": bindings,
        "retired_cycles": [
            {
                "cycle_id": "c4",
                "state": "RETIRED_TIMEBOX",
                "execution_status": "NOT_EXECUTED",
                "runs_created": 0,
            },
            {
                "cycle_id": "c5",
                "state": "RETIRED_TIMEBOX",
                "execution_status": "NOT_EXECUTED",
                "runs_created": 0,
            },
        ],
        "verified_artifact_ids": verified_ids,
    }
    wire["input_artifact_ids"] = sorted(
        set(wire["input_artifact_ids"]) | set(verified_ids)
    )

    legacy1, legacy2, c1, c2, c3 = deepcopy(wire["execution_history"])
    c3.update(
        {
            "sequence_index": 5,
            "execution_status": "HISTORICAL_ATTEMPTS_PRESERVED",
            "source_schema_version": "CohortDayManifest/3.3.0",
        }
    )
    retired = []
    for sequence, cycle_id in ((6, "c4"), (7, "c5")):
        row = deepcopy(c3)
        row.update(
            {
                "sequence_index": sequence,
                "cycle_id": cycle_id,
                "cycle_index": int(cycle_id[1:]),
                "runs_created": 0,
                "runs_predicted": 0,
                "execution_status": "RETIRED_TIMEBOX",
                "executed_at": None,
                "source_schema_version": "OwnerSupersession/1.0.0",
                "evidence_state": "OWNER_DECISION",
            }
        )
        retired.append(row)
    current = deepcopy(c3)
    current.update(
        {
            "sequence_index": 8,
            "cycle_id": "c6",
            "cycle_index": 6,
            "runs_created": len(wire["delta"]["authoritative_run_ids"]),
            "runs_predicted": wire["delta"]["runs_predicted"],
            "execution_status": "COMPLETE",
            "source_schema_version": "CohortDayManifest/3.4.0",
            "executed_at": wire["created_at"],
            "scheduled_for": wire["scheduled_for"],
            "window_start": wire["window_start"],
            "window_end": wire["window_end"],
        }
    )
    wire["execution_history"] = [
        legacy1,
        legacy2,
        c1,
        c2,
        c3,
        *retired,
        current,
    ]
    compressed = wire["execution_history"][2:]
    wire["cumulative"] = {
        "compressed_cycles_completed": 3,
        "successful_compressed_cycles": 3,
        "runs_predicted": sum(
            int(row["runs_predicted"])
            for row in compressed
            if row["execution_status"] != "RETIRED_TIMEBOX"
        ),
        "runs_created": sum(
            int(row["runs_created"])
            for row in compressed
            if row["execution_status"] != "RETIRED_TIMEBOX"
        ),
        "distinct_execution_dates": len(
            {
                str(row["executed_at"])[:10]
                for row in compressed
                if row["executed_at"] is not None
            }
        ),
        "logical_days_covered": 4,
        "historical_incomplete_attempts": 2,
    }
    wire["content_hash"] = content_hash(wire)
    return wire


def test_manifest_340_accepts_hash_bound_final_only_supersession(
    final_only_wire: dict[str, object],
) -> None:
    parsed = parse_artifact(
        final_only_wire, authorized_producers=PRODUCER_REGISTRY
    )

    assert parsed.schema_version == "3.4.0"
    assert parsed.payload.previous_manifest_id is None
    assert parsed.payload.ramp_gate_receipt_id is None
    assert parsed.payload.headroom_receipt_id is None
    assert parsed.payload.final_only_supersession["mode"] == "FINAL_ONLY_TIMEBOX"
    assert parsed.payload.execution_history[-3]["execution_status"] == "RETIRED_TIMEBOX"


def test_manifest_340_accepts_exact_owner_release_after_static_window(
    final_only_wire: dict[str, object],
) -> None:
    value = deepcopy(final_only_wire)
    _as_owner_release(value)
    value["content_hash"] = content_hash(value)

    parsed = parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)

    assert parsed.payload.window_end == final_only_wire["window_end"]
    assert parsed.payload.deadline_policy["trigger_started_at"] > value["window_end"]


@pytest.mark.parametrize("warning_mutation", ["missing", "wrong_reason"])
def test_manifest_340_rejects_late_deadlines_without_exact_owner_release(
    final_only_wire: dict[str, object], warning_mutation: str
) -> None:
    value = deepcopy(final_only_wire)
    _as_owner_release(value)
    if warning_mutation == "missing":
        value["warnings"] = []
    else:
        value["warnings"][0]["message_key"] = "UNAUTHORIZED_REASON"
    value["content_hash"] = content_hash(value)

    with pytest.raises(ContractError):
        parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value.__setitem__("headroom_receipt_id", _id("fake-headroom")),
        lambda value: value.__setitem__("ramp_gate_receipt_id", _id("fake-ramp")),
        lambda value: value["final_only_supersession"]["verified_artifact_ids"].pop(),
        lambda value: value["execution_history"][-3].__setitem__(
            "execution_status", "COMPLETE"
        ),
        _coherently_change_agent_budget,
        lambda value: _misstate_parity_count(
            value, "expected_newly_created_runs"
        ),
        lambda value: _misstate_parity_count(
            value, "actual_newly_created_runs"
        ),
        lambda value: _misstate_parity_count(value, "expected_reused_runs"),
        lambda value: _misstate_parity_count(value, "actual_reused_runs"),
    ],
)
def test_manifest_340_rejects_gate_fiction_or_unbound_history(
    final_only_wire: dict[str, object],
    mutator,
) -> None:
    value = deepcopy(final_only_wire)
    mutator(value)
    value["content_hash"] = content_hash(value)

    with pytest.raises(ContractError):
        parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
