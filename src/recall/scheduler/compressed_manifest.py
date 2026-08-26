from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from recall.contracts import ArtifactStatus, DataMode, build_artifact, parse_artifact
from recall.contracts.enums import FactState
from recall.ledger.models import ScanRunRecord, WatchCaseRecord
from recall.ledger.producers import PRODUCER_REGISTRY

from .cohort import COHORT_ID
from .compressed_cohort import CompressedCohortCase
from .compressed_identity import (
    manifest_artifact_id,
    mode_receipt_artifact_id,
    tick_run_id,
)
from .compressed_plan import CompressedCycle, CompressedPlan, TRIGGER_CODE
from .compressed_preparation import CompressedPreparationBundle
from .history import DAY1_EXECUTED_AT


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
    headroom_receipt: Mapping[str, object] | None,
    executed_at: datetime,
) -> dict[str, object]:
    authoritative = tuple(sorted(item.run_id for item in run_records))
    history = _prior_history(
        plan=plan,
        cycle=cycle,
        previous_manifest=previous_manifest,
        bundle=bundle,
    )
    history.append(
        {
            "sequence_index": len(history) + 1,
            "source_schema_version": "CohortDayManifest/3.0.0",
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
    if headroom_receipt is not None:
        inputs.add(str(headroom_receipt["artifact_id"]))
    matched = len(authoritative) == cycle.runs_predicted
    return build_artifact(
        schema_name="CohortDayManifest",
        schema_version="3.0.0",
        artifact_id=manifest_artifact_id(plan, cycle),
        case_id=COHORT_ID,
        run_id=tick_run_id(plan, cycle),
        producer={"component": "managed-cohort-scheduler", "version": "3.0.0", "identity": "cohort-scheduler"},
        created_at=_timestamp(executed_at),
        input_artifact_ids=tuple(sorted(inputs)),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID if matched else ArtifactStatus.INCOMPLETE,
        payload={
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
                "prediction_match": matched,
            },
            "cumulative": _cumulative(history),
            "cases": cases,
            "vcv_anchors": anchors,
            "execution_history": history,
        },
        authorized_producers=PRODUCER_REGISTRY,
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
    if (
        parsed.schema_version != "3.0.0"
        or parsed.payload.cycle_id != prior_cycle.cycle_id
        or parsed.artifact_id != manifest_artifact_id(plan, prior_cycle)
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
