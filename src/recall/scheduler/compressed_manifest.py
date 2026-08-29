from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone

from recall.contracts import ArtifactStatus, DataMode, build_artifact, parse_artifact
from recall.contracts.payloads.scheduler_v34_support import (
    final_only_owner_release_warnings,
)
from recall.contracts.enums import FactState
from recall.ledger.models import ScanRunRecord, WatchCaseRecord
from recall.ledger.producers import PRODUCER_REGISTRY

from .cohort import COHORT_ID
from .compressed_cohort import CompressedCohortCase
from .compressed_identity import (
    evidence_manifest_artifact_id,
    evidence_plan,
    manifest_artifact_id,
    mode_receipt_artifact_id,
    tick_run_id,
)
from .compressed_plan import (
    CompressedCycle,
    CompressedPlan,
    FinalOnlyOwnerRelease,
    TRIGGER_CODE,
)
from .compressed_preparation import CompressedPreparationBundle
from .history import DAY1_EXECUTED_AT
from .full_audit_phase import FullAuditPhaseResult, outcome_to_wire
from .compressed_final_only_manifest import (
    final_only_cumulative,
    final_only_prior_history,
    final_only_supersession_payload,
)
from .compressed_supersession import VerifiedFinalOnlySupersession


DAY1_SCHEDULED_FOR = "2026-08-25T15:00:00Z"


def build_compressed_manifest(
    *,
    plan: CompressedPlan,
    cycle: CompressedCycle,
    source_commit: str,
    image_digest: str,
    selected_cases: Sequence[CompressedCohortCase],
    excluded_case_ids: Sequence[str],
    watch_records: Sequence[WatchCaseRecord],
    run_records: Sequence[ScanRunRecord],
    newly_created_run_ids: Sequence[str],
    reused_run_ids: Sequence[str],
    bundle: CompressedPreparationBundle,
    previous_manifest: Mapping[str, object] | None,
    ramp_gate_receipt: Mapping[str, object] | None,
    headroom_receipt: Mapping[str, object] | None,
    batch_execution_receipt: Mapping[str, object] | None,
    write_measurement_status: str,
    write_metrics: Mapping[str, object] | None,
    agent_phase: FullAuditPhaseResult | None,
    executed_at: datetime,
    trigger_started_at: datetime,
    verified_supersession: VerifiedFinalOnlySupersession | None = None,
    owner_release: FinalOnlyOwnerRelease | None = None,
) -> dict[str, object]:
    authoritative = tuple(sorted(item.run_id for item in run_records))
    final_only = plan.schema_version == "2.8.0"
    if owner_release is not None and (
        not final_only or cycle.cycle_id != "c6"
    ):
        raise RuntimeError("final_only_owner_release_context_invalid")
    if final_only:
        if verified_supersession is None:
            raise RuntimeError("final_only_verified_snapshot_missing")
        history = final_only_prior_history(plan, verified_supersession)
    else:
        history = _prior_history(
            plan=plan,
            cycle=cycle,
            previous_manifest=previous_manifest,
            bundle=bundle,
        )
    schema_version = (
        "3.4.0"
        if final_only
        else "3.3.0"
        if cycle.execution_profile == "FULL_AUDIT_V1"
        else ("3.0.0" if cycle.cycle_index < 3 else "3.1.0")
    )
    if (agent_phase is None) is (cycle.execution_profile == "FULL_AUDIT_V1"):
        raise RuntimeError("compressed_agent_phase_binding_invalid")
    agent_qualified = agent_phase is None or (
        int(agent_phase.summary["halted_runs"]) == 0
        and int(agent_phase.summary["incomplete_runs"]) == 0
        and int(agent_phase.summary["not_evaluated_runs"]) == 0
        and int(agent_phase.summary["complete_runs"])
        == int(agent_phase.summary["total_runs"])
    )
    history.append(
        {
            "sequence_index": len(history) + 1,
            "source_schema_version": f"CohortDayManifest/{schema_version}",
            "cycle_id": cycle.cycle_id,
            "cycle_index": cycle.cycle_index,
            "cohort_due_date": cycle.cohort_due_date.isoformat(),
            "scheduled_for": cycle.schedule_epoch,
            "window_start": cycle.schedule_epoch,
            "window_end": _timestamp(cycle.window_end),
            "trigger_code": TRIGGER_CODE,
            "executed_at": _timestamp(executed_at),
            "runs_created": len(authoritative),
            "runs_predicted": cycle.runs_predicted,
            # This history row records completed cohort admission and durable
            # run creation. Agent qualification is represented natively by the
            # v3.3 envelope status plus run_outcomes/failure receipt bindings.
            "execution_status": "COMPLETE",
            "failure_receipt_id": None,
            "evidence_state": "LIVE_INFRASTRUCTURE_SYNTHETIC_DATA",
            "schedule_mode": plan.schedule_mode,
        }
    )
    observations = bundle.observations_by_vcv
    vcvs = {item.vcv for item in selected_cases if item.vcv is not None}
    anchors = [
        {
            "vcv": vcv,
            "capture_path": str(observations[vcv]["structured_fields"]["capture_path"]),
            "sha256": str(observations[vcv]["source_content_hash"]),
            "artifact_id": str(observations[vcv]["artifact_id"]),
        }
        for vcv in sorted(vcvs)
    ]
    cases = [
        {
            "case_id": item.case_id,
            "data_mode": item.declared_composition.value,
            "vcv": item.vcv,
        }
        for item in sorted(selected_cases, key=lambda item: item.case_id)
    ]
    inputs = {
        str(bundle.history_receipt["artifact_id"]),
        *(item.artifact_id for item in watch_records),
        *(str(item.scan_run_artifact_id) for item in run_records),
        *(str(item["artifact_id"]) for item in anchors),
    }
    if cycle.cycle_id == "c1":
        inputs.add(str(bundle.legacy_failure_receipt["artifact_id"]))
    inputs.update(
        str(item["failure_receipt_id"])
        for item in history
        if item["failure_receipt_id"] is not None
    )
    previous_id = None
    if previous_manifest is not None:
        previous_id = str(previous_manifest["artifact_id"])
        inputs.add(previous_id)
    if ramp_gate_receipt is not None:
        inputs.add(str(ramp_gate_receipt["artifact_id"]))
    if headroom_receipt is not None:
        inputs.add(str(headroom_receipt["artifact_id"]))
    if batch_execution_receipt is not None:
        inputs.add(str(batch_execution_receipt["artifact_id"]))
    if verified_supersession is not None:
        inputs.update(verified_supersession.verified_artifact_ids)
    if agent_phase is not None:
        for outcome in agent_phase.outcomes:
            inputs.update(outcome.agent_execution_receipt_ids)
            inputs.update(outcome.failure_receipt_ids)
            if outcome.citation_audit_receipt_id is not None:
                inputs.add(outcome.citation_audit_receipt_id)
            if outcome.policy_decision_id is not None:
                inputs.add(outcome.policy_decision_id)
    predicted_match = len(authoritative) == cycle.runs_predicted
    parity_match = (
        len(newly_created_run_ids) == cycle.runs_predicted
        and len(reused_run_ids) == 0
    )
    epoch_parity_match = len(authoritative) == cycle.runs_predicted
    deadline_policy = _deadline_policy(
        cycle=cycle,
        trigger_started_at=trigger_started_at,
        write_completed_at=(
            trigger_started_at
            if write_metrics is None
            else datetime.fromisoformat(
                str(write_metrics["completed_at"]).replace("Z", "+00:00")
            )
        ),
        agent_completed_at=executed_at,
        owner_release=owner_release,
    )
    deadline_qualified = (
        deadline_policy["trigger_started_at"] <= deadline_policy["trigger_window_end"]
        and deadline_policy["write_completed_at"] <= deadline_policy["write_deadline"]
        and deadline_policy["agent_completed_at"] <= deadline_policy["agent_deadline"]
        and deadline_policy["agent_completed_at"]
        <= deadline_policy["authoritative_end_to_end_deadline"]
    )
    qualified = (predicted_match if cycle.cycle_index < 3 else (
        epoch_parity_match
        and write_measurement_status == "MEASURED"
        and write_metrics is not None
        and write_metrics["persistence_surface"] == "LIVE_FIRESTORE"
        and int(write_metrics["effective_write_millis_per_case"]) <= 2000
        and deadline_qualified
    )) and agent_qualified
    if final_only:
        history[-1]["execution_status"] = (
            "COMPLETE" if qualified else "INCOMPLETE"
        )
    payload = {
        "day_index": cycle.cycle_index + 1,
        "selected_for_date": cycle.cohort_due_date.isoformat(),
        "scheduled_for": cycle.schedule_epoch,
        "source_commit": source_commit,
        "image_digest": image_digest,
        "trigger_code": TRIGGER_CODE,
        "previous_manifest_id": previous_id,
        "managed_history_starts_at_day_index": 2,
        "cycle_id": cycle.cycle_id,
        "cycle_index": cycle.cycle_index,
        "plan_version": plan.version,
        "plan_sha256": plan.sha256,
        "cohort_due_date": cycle.cohort_due_date.isoformat(),
        "window_start": cycle.schedule_epoch,
        "window_end": _timestamp(cycle.window_end),
        "schedule_mode": plan.schedule_mode,
        "headroom_receipt_id": (
            None
            if headroom_receipt is None
            else str(headroom_receipt["artifact_id"])
        ),
        "delta": {
            "selected_case_ids": sorted(item.case_id for item in selected_cases),
            "excluded_case_ids": sorted(excluded_case_ids),
            "newly_created_run_ids": sorted(newly_created_run_ids),
            "reused_run_ids": sorted(reused_run_ids),
            "authoritative_run_ids": list(authoritative),
            "runs_predicted": cycle.runs_predicted,
            "prediction_match": predicted_match,
        },
        "cumulative": (
            final_only_cumulative(
                history,
                historical_attempt_count=len(
                    plan.supersession.historical_evidence
                )
                - 2,
            )
            if final_only and plan.supersession is not None
            else _cumulative(history)
        ),
        "cases": cases,
        "vcv_anchors": anchors,
        "execution_history": history,
    }
    if cycle.cycle_index >= 3:
        if write_metrics is None or batch_execution_receipt is None:
            raise RuntimeError("compressed_write_evidence_missing")
        if not final_only and ramp_gate_receipt is None:
            raise RuntimeError("compressed_ramp_gate_receipt_missing")
        payload.update(
            {
                "epoch_label": cycle.epoch_label,
                "evaluation_role": cycle.evaluation_role,
                "ramp_gate_receipt_id": (
                    None
                    if ramp_gate_receipt is None
                    else str(ramp_gate_receipt["artifact_id"])
                ),
                "cycle_attempt_id": tick_run_id(plan, cycle),
                "batch_execution_receipt_id": str(
                    batch_execution_receipt["artifact_id"]
                ),
                "write_measurement_status": write_measurement_status,
                "deadline_policy": deadline_policy,
                "write_metrics": dict(write_metrics),
                "parity": {
                    "expected_newly_created_runs": cycle.runs_predicted,
                    "actual_newly_created_runs": len(newly_created_run_ids),
                    "expected_reused_runs": 0,
                    "actual_reused_runs": len(reused_run_ids),
                    "new_epoch_required": True,
                    "same_write_path_as_ramp": True,
                    "parity_match": parity_match,
                    "epoch_parity_match": epoch_parity_match,
                    "fresh_write_parity_match": parity_match,
                },
            }
        )
    if final_only:
        assert verified_supersession is not None
        payload["final_only_supersession"] = final_only_supersession_payload(
            plan, verified_supersession
        )
    if (
        not final_only
        and (cycle.cycle_id == "c6") is not (headroom_receipt is not None)
    ):
        raise RuntimeError("compressed_headroom_manifest_binding_invalid")
    if agent_phase is not None:
        payload.update(
            {
                "agent_execution_summary": dict(agent_phase.summary),
                "run_outcomes": [
                    outcome_to_wire(item, epoch_label=cycle.epoch_label)
                    for item in agent_phase.outcomes
                ],
            }
        )
    return build_artifact(
        schema_name="CohortDayManifest",
        schema_version=schema_version,
        artifact_id=manifest_artifact_id(plan, cycle),
        case_id=COHORT_ID,
        run_id=tick_run_id(plan, cycle),
        producer={"component": "managed-cohort-scheduler", "version": schema_version, "identity": "cohort-scheduler"},
        created_at=_timestamp(executed_at),
        input_artifact_ids=tuple(sorted(inputs)),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID if qualified else ArtifactStatus.INCOMPLETE,
        payload=payload,
        authorized_producers=PRODUCER_REGISTRY,
        warnings=(
            final_only_owner_release_warnings()
            if owner_release is not None
            else ()
        ),
    )


def build_compressed_mode_receipt(
    manifest: Mapping[str, object], plan: CompressedPlan, cycle: CompressedCycle
) -> dict[str, object]:
    parsed = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
    subjects = tuple(sorted({parsed.artifact_id, *parsed.input_artifact_ids}))
    # All locked compressed cycles are descendants of a replay-bearing cohort
    # history. Current-cycle anchors may be empty, but provenance is transitive.
    has_replay = parsed.payload.cycle_index >= 1
    return build_artifact(
        schema_name="DataModeReceipt",
        schema_version="2.0.0",
        artifact_id=mode_receipt_artifact_id(plan, cycle),
        case_id=COHORT_ID,
        run_id=tick_run_id(plan, cycle),
        producer={"component": "cohort-mode-gate", "version": "1.0.0", "identity": "controller-mode-gate"},
        created_at=parsed.created_at,
        input_artifact_ids=subjects,
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID,
        payload={
            "subject_artifact_ids": list(subjects),
            "mode_set": ["CAPTURED_REPLAY", "SYNTHETIC"] if has_replay else ["SYNTHETIC"],
            "declared_composition": "SYNTHETIC_WITH_CAPTURED_REPLAY" if has_replay else "SYNTHETIC_ONLY",
            "propagation_status": FactState.PASS.value,
            "reason_codes": [],
        },
        authorized_producers=PRODUCER_REGISTRY,
    )


def _prior_history(
    *,
    plan: CompressedPlan,
    cycle: CompressedCycle,
    previous_manifest: Mapping[str, object] | None,
    bundle: CompressedPreparationBundle,
) -> list[dict[str, object]]:
    if cycle.cycle_index == 1:
        if previous_manifest is not None:
            raise RuntimeError("compressed_c1_previous_manifest_forbidden")
        history = parse_artifact(bundle.history_receipt, authorized_producers=PRODUCER_REGISTRY)
        failure = parse_artifact(bundle.legacy_failure_receipt, authorized_producers=PRODUCER_REGISTRY)
        return [
            {
                "sequence_index": 1,
                "source_schema_version": "CohortHistoryReceipt/1.0.0",
                "cycle_id": None,
                "cycle_index": None,
                "cohort_due_date": history.payload.selected_for_date,
                "scheduled_for": DAY1_SCHEDULED_FOR,
                "window_start": None,
                "window_end": None,
                "trigger_code": history.payload.trigger_code,
                "executed_at": DAY1_EXECUTED_AT,
                "runs_created": history.payload.runs_created,
                "runs_predicted": history.payload.runs_predicted,
                "execution_status": "COMPLETE",
                "failure_receipt_id": None,
                "evidence_state": history.payload.evidence_classification,
                "schedule_mode": None,
            },
            {
                "sequence_index": 2,
                "source_schema_version": "CompressedCycleFailureReceipt/1.0.0",
                "cycle_id": None,
                "cycle_index": None,
                "cohort_due_date": failure.payload.cohort_due_date,
                "scheduled_for": failure.payload.scheduled_for,
                "window_start": None,
                "window_end": None,
                "trigger_code": "COHORT_DAY_MANAGED",
                "executed_at": None,
                "runs_created": 0,
                "runs_predicted": failure.payload.runs_predicted,
                "execution_status": "INCOMPLETE",
                "failure_receipt_id": failure.artifact_id,
                "evidence_state": failure.payload.evidence_state,
                "schedule_mode": None,
            },
        ]
    if previous_manifest is None:
        raise RuntimeError("compressed_previous_manifest_missing")
    parsed = parse_artifact(previous_manifest, authorized_producers=PRODUCER_REGISTRY)
    prior_cycle = plan.cycles[cycle.cycle_index - 2]
    prior_plan = evidence_plan(plan, prior_cycle)
    if (
        parsed.schema_version not in {"3.0.0", "3.1.0", "3.2.0", "3.3.0"}
        or parsed.payload.cycle_id != prior_cycle.cycle_id
        or parsed.payload.plan_sha256 != prior_plan.sha256
        or parsed.artifact_id != evidence_manifest_artifact_id(plan, prior_cycle)
    ):
        raise RuntimeError("compressed_previous_manifest_invalid")
    return [dict(item) for item in parsed.payload.execution_history]


def _cumulative(history: Sequence[Mapping[str, object]]) -> dict[str, int]:
    compressed = [item for item in history if item["schedule_mode"] == "COMPRESSED_MACHINE_TRIGGERED"]
    return {
        "compressed_cycles_completed": len(compressed),
        "successful_compressed_cycles": sum(item["runs_created"] == item["runs_predicted"] for item in compressed),
        "runs_predicted": sum(int(item["runs_predicted"]) for item in compressed),
        "runs_created": sum(int(item["runs_created"]) for item in compressed),
        "distinct_execution_dates": len({str(item["executed_at"])[:10] for item in compressed}),
        "logical_days_covered": len({str(item["cohort_due_date"]) for item in compressed}),
        "historical_incomplete_attempts": sum(item["execution_status"] == "INCOMPLETE" for item in history),
    }


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _deadline_policy(
    *,
    cycle: CompressedCycle,
    trigger_started_at: datetime,
    write_completed_at: datetime,
    agent_completed_at: datetime,
    owner_release: FinalOnlyOwnerRelease | None = None,
) -> dict[str, str]:
    if owner_release is not None and (
        owner_release.cycle_id != cycle.cycle_id
        or owner_release.actual_start != trigger_started_at
    ):
        raise RuntimeError("final_only_owner_release_context_invalid")
    end_to_end = (
        owner_release.execution_deadline
        if owner_release is not None
        else cycle.end_to_end_deadline
    )
    write_deadline = min(
        trigger_started_at + timedelta(seconds=cycle.write_timeout_seconds),
        end_to_end,
    )
    agent_deadline = min(
        write_completed_at + timedelta(seconds=cycle.agent_timeout_seconds),
        end_to_end,
    )
    return {
        "trigger_started_at": _timestamp(trigger_started_at),
        "trigger_window_end": _timestamp(
            trigger_started_at if owner_release is not None else cycle.window_end
        ),
        "write_timeout_seconds": cycle.write_timeout_seconds,
        "write_deadline": _timestamp(write_deadline),
        "write_completed_at": _timestamp(write_completed_at),
        "agent_timeout_seconds": cycle.agent_timeout_seconds,
        "agent_deadline": _timestamp(agent_deadline),
        "agent_completed_at": _timestamp(agent_completed_at),
        "execution_timeout_seconds": cycle.execution_timeout_seconds,
        "authoritative_end_to_end_deadline": _timestamp(end_to_end),
    }
