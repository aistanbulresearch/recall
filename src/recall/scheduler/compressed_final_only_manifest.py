from __future__ import annotations

from collections.abc import Mapping, Sequence

from recall.contracts import parse_artifact
from recall.ledger.producers import PRODUCER_REGISTRY

from .compressed_plan import CompressedCycle, CompressedPlan
from .compressed_supersession import VerifiedFinalOnlySupersession


def final_only_prior_history(
    plan: CompressedPlan,
    verified: VerifiedFinalOnlySupersession,
) -> list[dict[str, object]]:
    _require_snapshot(plan, verified)
    parsed = tuple(
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
        for wire in verified.manifest_wires
    )
    c1, c2, *c3_attempts = parsed
    if len(c1.payload.execution_history) < 3 or not c3_attempts:
        raise RuntimeError("final_only_history_rows_missing")
    legacy = [dict(row) for row in c1.payload.execution_history[:2]]
    c1_row = dict(c1.payload.execution_history[-1])
    c2_row = dict(c2.payload.execution_history[-1])
    c3_rows = [dict(item.payload.execution_history[-1]) for item in c3_attempts]
    latest_c3 = dict(c3_rows[-1])
    latest_c3.update(
        {
            "sequence_index": 5,
            "source_schema_version": "HistoricalAttempts/1.0.0",
            "runs_created": sum(int(row["runs_created"]) for row in c3_rows),
            "runs_predicted": sum(int(row["runs_predicted"]) for row in c3_rows),
            "execution_status": "HISTORICAL_ATTEMPTS_PRESERVED",
            "failure_receipt_id": None,
            "evidence_state": "HASH_BOUND_HISTORICAL_ATTEMPTS",
        }
    )
    rows = [*legacy, c1_row, c2_row, latest_c3]
    for sequence, cycle_id in ((6, "c4"), (7, "c5")):
        cycle = plan.by_id(cycle_id)
        rows.append(_retired_row(cycle, sequence=sequence, plan=plan))
    for sequence, row in enumerate(rows, start=1):
        row["sequence_index"] = sequence
    return rows


def final_only_supersession_payload(
    plan: CompressedPlan,
    verified: VerifiedFinalOnlySupersession,
) -> dict[str, object]:
    _require_snapshot(plan, verified)
    assert plan.supersession is not None
    return {
        "mode": plan.supersession.mode,
        "superseded_plan_sha256": plan.supersession.superseded_plan_sha256,
        "owner_decision": plan.supersession.owner_decision,
        "reason_code": plan.supersession.reason_code,
        "historical_evidence": [
            {
                "cycle_id": item.cycle_id,
                "evidence_role": item.evidence_role,
                "execution_status": item.execution_status,
                "plan_sha256": item.plan_sha256,
                "collection_prefix": item.collection_prefix,
                "manifest_artifact_id": item.manifest_artifact_id,
                "manifest_content_hash": item.manifest_content_hash,
                "mode_receipt_artifact_id": item.mode_receipt_artifact_id,
                "mode_receipt_content_hash": item.mode_receipt_content_hash,
            }
            for item in plan.supersession.historical_evidence
        ],
        "retired_cycles": [
            {
                "cycle_id": item.cycle_id,
                "state": item.state,
                "execution_status": item.execution_status,
                "runs_created": item.runs_created,
            }
            for item in plan.supersession.retired_cycles
        ],
        "verified_artifact_ids": list(verified.verified_artifact_ids),
    }


def verify_final_only_history_rows(
    plan: CompressedPlan,
    verified: VerifiedFinalOnlySupersession,
    rows: Sequence[Mapping[str, object]],
) -> None:
    """Bind every re-declared historical row to the verified source artifacts."""
    expected = final_only_prior_history(plan, verified)
    observed = [dict(row) for row in rows[:-1]]
    if observed != expected:
        raise RuntimeError("final_only_history_row_binding_invalid")


def final_only_cumulative(
    history: Sequence[Mapping[str, object]],
    *,
    historical_attempt_count: int,
) -> dict[str, int]:
    compressed = list(history[2:])
    active = [
        row for row in compressed if row["execution_status"] != "RETIRED_TIMEBOX"
    ]
    return {
        "compressed_cycles_completed": sum(
            row["execution_status"] == "COMPLETE" for row in compressed
        ),
        "successful_compressed_cycles": sum(
            row["execution_status"] == "COMPLETE"
            and row["runs_created"] == row["runs_predicted"]
            for row in compressed
        ),
        "runs_predicted": sum(int(row["runs_predicted"]) for row in active),
        "runs_created": sum(int(row["runs_created"]) for row in active),
        "distinct_execution_dates": len(
            {
                str(row["executed_at"])[:10]
                for row in active
                if row["executed_at"] is not None
            }
        ),
        "logical_days_covered": len(active),
        "historical_incomplete_attempts": historical_attempt_count,
    }


def _retired_row(
    cycle: CompressedCycle,
    *,
    sequence: int,
    plan: CompressedPlan,
) -> dict[str, object]:
    return {
        "sequence_index": sequence,
        "source_schema_version": "OwnerSupersession/1.0.0",
        "cycle_id": cycle.cycle_id,
        "cycle_index": cycle.cycle_index,
        "cohort_due_date": cycle.cohort_due_date.isoformat(),
        "scheduled_for": cycle.schedule_epoch,
        "window_start": cycle.schedule_epoch,
        "window_end": cycle.window_end.isoformat().replace("+00:00", "Z"),
        "trigger_code": "COHORT_COMPRESSED_MACHINE_TRIGGERED",
        "executed_at": None,
        "runs_created": 0,
        "runs_predicted": 0,
        "execution_status": "RETIRED_TIMEBOX",
        "failure_receipt_id": None,
        "evidence_state": "OWNER_DECISION",
        "schedule_mode": plan.schedule_mode,
    }


def _require_snapshot(
    plan: CompressedPlan,
    verified: VerifiedFinalOnlySupersession,
) -> None:
    supersession = plan.supersession
    expected_ids = tuple(
        artifact_id
        for item in (() if supersession is None else supersession.historical_evidence)
        for artifact_id in (
            item.manifest_artifact_id,
            item.mode_receipt_artifact_id,
        )
        if artifact_id is not None
    )
    if (
        plan.schema_version != "2.8.0"
        or supersession is None
        or verified.plan_sha256 != plan.sha256
        or verified.verified_artifact_ids != expected_ids
        or len(verified.manifest_wires) != len(supersession.historical_evidence)
    ):
        raise RuntimeError("final_only_verified_snapshot_invalid")
