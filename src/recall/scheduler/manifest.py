from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid5

from recall.contracts import ArtifactStatus, DataMode, build_artifact, parse_artifact
from recall.contracts.enums import FactState
from recall.ledger.models import ScanRunRecord, WatchCaseRecord
from recall.ledger.producers import PRODUCER_REGISTRY

from .cohort import MANAGED_COHORT, RUN_PREDICTIONS, ManagedCohortCase
from .preparation import CohortPreparationBundle


COHORT_ID = str(uuid5(NAMESPACE_URL, "recall:m2:staged-cohort:v1"))
TRIGGER_CODE = "COHORT_DAY_MANAGED"
MANAGED_HISTORY_STARTS_AT = 2
DAY1_HISTORY = {
    "day_index": 1,
    "executed_at": "2026-08-25T15:01:07.720049Z",
    "selected_for_date": "2026-08-25",
    "runs_created": 1,
    "runs_predicted": 1,
}


def day_index(selected_for_date: date) -> int:
    index = (selected_for_date - date(2026, 8, 24)).days
    if index < 2:
        raise RuntimeError("managed_cohort_day_before_day2")
    return index


def logical_tick_at(selected_for_date: date) -> datetime:
    return datetime(
        selected_for_date.year,
        selected_for_date.month,
        selected_for_date.day,
        16,
        tzinfo=timezone.utc,
    )


def tick_run_id(selected_for_date: date) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            f"recall:cohort-tick:{COHORT_ID}:{selected_for_date.isoformat()}",
        )
    )


def manifest_artifact_id(selected_for_date: date) -> str:
    return str(uuid5(UUID(tick_run_id(selected_for_date)), "cohort-day-manifest"))


def mode_receipt_artifact_id(selected_for_date: date) -> str:
    return str(uuid5(UUID(tick_run_id(selected_for_date)), "cohort-data-mode-receipt"))


def require_single_manifest(
    artifacts: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    manifests = [
        item for item in artifacts if item.get("schema_name") == "CohortDayManifest"
    ]
    if len(manifests) != 1:
        raise RuntimeError(f"cohort_manifest_cardinality_invalid:{len(manifests)}")
    return manifests[0]


def build_manifest(
    *,
    selected_for_date: date,
    source_commit: str,
    selected_cases: Sequence[ManagedCohortCase],
    excluded_case_ids: Sequence[str],
    watch_records: Sequence[WatchCaseRecord],
    run_records: Sequence[ScanRunRecord],
    newly_created_run_ids: Sequence[str],
    reused_run_ids: Sequence[str],
    bundle: CohortPreparationBundle,
    previous_manifest: Mapping[str, object] | None,
    executed_at: datetime,
) -> dict[str, object]:
    predicted = RUN_PREDICTIONS[selected_for_date]
    authoritative_ids = tuple(sorted(record.run_id for record in run_records))
    index = day_index(selected_for_date)
    history = _prior_history(previous_manifest, index=index)
    history.append(
        {
            "day_index": index,
            "executed_at": _timestamp(executed_at.astimezone(timezone.utc)),
            "selected_for_date": selected_for_date.isoformat(),
            "runs_created": len(authoritative_ids),
            "runs_predicted": predicted,
        }
    )
    selected_vcvs = {item.vcv for item in selected_cases if item.vcv is not None}
    observations = bundle.observations_by_vcv
    anchor_rows = [
        {
            "vcv": vcv,
            "capture_path": str(observations[vcv]["structured_fields"]["capture_path"]),
            "sha256": str(observations[vcv]["source_content_hash"]),
            "artifact_id": str(observations[vcv]["artifact_id"]),
        }
        for vcv in sorted(selected_vcvs)
    ]
    case_rows = [
        {
            "case_id": item.case_id,
            "data_mode": item.declared_composition.value,
            "vcv": item.vcv,
        }
        for item in sorted(selected_cases, key=lambda item: item.case_id)
    ]
    input_ids = {
        *(record.artifact_id for record in watch_records),
        *(str(record.scan_run_artifact_id) for record in run_records),
        *(str(row["artifact_id"]) for row in anchor_rows),
    }
    previous_id = None
    if previous_manifest is not None:
        previous_id = str(previous_manifest["artifact_id"])
        input_ids.add(previous_id)
    matched = len(authoritative_ids) == predicted
    return build_artifact(
        schema_name="CohortDayManifest",
        schema_version="1.0.0",
        artifact_id=manifest_artifact_id(selected_for_date),
        case_id=COHORT_ID,
        run_id=tick_run_id(selected_for_date),
        producer={
            "component": "managed-cohort-scheduler",
            "version": "1.0.0",
            "identity": "cohort-scheduler",
        },
        created_at=_timestamp(executed_at.astimezone(timezone.utc)),
        input_artifact_ids=tuple(sorted(input_ids)),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID if matched else ArtifactStatus.INCOMPLETE,
        payload={
            "day_index": index,
            "selected_for_date": selected_for_date.isoformat(),
            "scheduled_for": _timestamp(logical_tick_at(selected_for_date)),
            "source_commit": source_commit,
            "trigger_code": TRIGGER_CODE,
            "previous_manifest_id": previous_id,
            "managed_history_starts_at_day_index": MANAGED_HISTORY_STARTS_AT,
            "delta": {
                "selected_case_ids": sorted(item.case_id for item in selected_cases),
                "excluded_case_ids": sorted(excluded_case_ids),
                "newly_created_run_ids": sorted(newly_created_run_ids),
                "reused_run_ids": sorted(reused_run_ids),
                "authoritative_run_ids": list(authoritative_ids),
                "runs_predicted": predicted,
                "prediction_match": matched,
            },
            "cumulative": _cumulative(history),
            "cases": case_rows,
            "vcv_anchors": anchor_rows,
            "execution_history": history,
        },
        authorized_producers=PRODUCER_REGISTRY,
    )


def build_mode_receipt(
    manifest: Mapping[str, object],
    *,
    selected_for_date: date,
) -> dict[str, object]:
    parsed = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
    subjects = tuple(sorted({parsed.artifact_id, *parsed.input_artifact_ids}))
    has_replay = bool(parsed.payload.vcv_anchors) or parsed.payload.previous_manifest_id is not None
    modes = ["CAPTURED_REPLAY", "SYNTHETIC"] if has_replay else ["SYNTHETIC"]
    composition = (
        "SYNTHETIC_WITH_CAPTURED_REPLAY" if has_replay else "SYNTHETIC_ONLY"
    )
    return build_artifact(
        schema_name="DataModeReceipt",
        schema_version="2.0.0",
        artifact_id=mode_receipt_artifact_id(selected_for_date),
        case_id=COHORT_ID,
        run_id=tick_run_id(selected_for_date),
        producer={
            "component": "cohort-mode-gate",
            "version": "1.0.0",
            "identity": "controller-mode-gate",
        },
        created_at=parsed.created_at,
        input_artifact_ids=subjects,
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID,
        payload={
            "subject_artifact_ids": list(subjects),
            "mode_set": modes,
            "declared_composition": composition,
            "propagation_status": FactState.PASS.value,
            "reason_codes": [],
        },
        authorized_producers=PRODUCER_REGISTRY,
    )


def _prior_history(
    previous_manifest: Mapping[str, object] | None, *, index: int
) -> list[dict[str, object]]:
    if index == 2:
        if previous_manifest is not None:
            raise RuntimeError("day2_previous_manifest_forbidden")
        return [dict(DAY1_HISTORY)]
    if previous_manifest is None:
        raise RuntimeError("previous_cohort_manifest_required")
    parsed = parse_artifact(previous_manifest, authorized_producers=PRODUCER_REGISTRY)
    if parsed.schema_name != "CohortDayManifest":
        raise RuntimeError("previous_cohort_manifest_invalid")
    if parsed.payload.day_index != index - 1:
        raise RuntimeError("previous_cohort_manifest_not_adjacent")
    return [dict(item) for item in parsed.payload.execution_history]


def _cumulative(history: Sequence[Mapping[str, object]]) -> dict[str, int]:
    return {
        "daily_cycles": len(history),
        "successful_daily_cycles": sum(
            int(item["runs_created"] == item["runs_predicted"]) for item in history
        ),
        "runs_predicted": sum(int(item["runs_predicted"]) for item in history),
        "runs_created": sum(int(item["runs_created"]) for item in history),
        "distinct_execution_dates": len(
            {str(item["selected_for_date"]) for item in history}
        ),
    }


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
