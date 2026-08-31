from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID, uuid5

from recall.contracts import ArtifactStatus, DataMode, build_artifact, parse_artifact
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY

from .cohort import RUN_PREDICTIONS
from .manifest import day_index, manifest_artifact_id, tick_run_id


FAILURE_CODE = "previous_cohort_manifest_missing"
CONTINUATION_POLICY = "RECORD_INCOMPLETE_AND_CONTINUE"


@dataclass(frozen=True, slots=True)
class MissingCohortDay:
    selected_for_date: date


def failure_receipt_artifact_id(selected_for_date: date) -> str:
    return str(
        uuid5(
            UUID(tick_run_id(selected_for_date)),
            "cohort-day-failure-receipt",
        )
    )


def persist_failure_receipts(
    ledger: LedgerPort,
    *,
    missing_days: Sequence[MissingCohortDay],
    current_date: date,
    detected_at: datetime,
    source_commit: str,
    image_digest: str,
) -> tuple[dict[str, object], ...]:
    persisted = []
    for missing in sorted(missing_days, key=lambda item: item.selected_for_date):
        receipt_id = failure_receipt_artifact_id(missing.selected_for_date)
        wire = ledger.get_artifact(receipt_id)
        if wire is None:
            wire = build_artifact(
                schema_name="CohortDayFailureReceipt",
                schema_version="1.0.0",
                artifact_id=receipt_id,
                case_id=None,
                run_id=tick_run_id(current_date),
                producer={
                    "component": "managed-cohort-scheduler",
                    "version": "1.0.0",
                    "identity": "cohort-scheduler",
                },
                created_at=_timestamp(detected_at),
                input_artifact_ids=(),
                data_mode=DataMode.SYNTHETIC,
                status=ArtifactStatus.INCOMPLETE,
                payload={
                    "day_index": day_index(missing.selected_for_date),
                    "selected_for_date": missing.selected_for_date.isoformat(),
                    "detected_at": _timestamp(detected_at),
                    "failure_code": FAILURE_CODE,
                    "expected_manifest_id": manifest_artifact_id(
                        missing.selected_for_date
                    ),
                    "runs_predicted": RUN_PREDICTIONS[missing.selected_for_date],
                    "runs_created": 0,
                    "source_commit": source_commit,
                    "image_digest": image_digest,
                    "continuation_policy": CONTINUATION_POLICY,
                },
                authorized_producers=PRODUCER_REGISTRY,
            )
            ledger.append_artifact(wire)
            wire = ledger.get_artifact(receipt_id)
            if wire is None:
                raise RuntimeError("cohort_failure_receipt_missing")
        _validate_receipt(
            wire,
            missing=missing,
            source_commit=source_commit,
            image_digest=image_digest,
        )
        persisted.append(wire)
    return tuple(persisted)


def adapt_manifest_history(
    manifest: Mapping[str, object],
) -> tuple[dict[str, object], ...]:
    parsed = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
    if parsed.schema_name != "CohortDayManifest":
        raise RuntimeError("previous_cohort_manifest_invalid")
    if parsed.schema_version == "2.0.0":
        return tuple(
            {
                **dict(item),
                "execution_status": "COMPLETE",
                "failure_receipt_id": None,
            }
            for item in parsed.payload.execution_history
        )
    if parsed.schema_version != "2.1.0":
        raise RuntimeError("previous_cohort_manifest_invalid")
    return tuple(dict(item) for item in parsed.payload.execution_history)


def validate_persisted_failure_lineage(
    ledger: LedgerPort,
    manifest: Mapping[str, object],
    *,
    previous_manifest: Mapping[str, object] | None,
) -> None:
    parsed = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
    referenced = {
        str(item["failure_receipt_id"])
        for item in parsed.payload.execution_history
        if item["failure_receipt_id"] is not None
    }
    inherited = (
        set()
        if previous_manifest is None
        else failure_receipt_ids(previous_manifest)
    )
    if not inherited.issubset(referenced):
        raise RuntimeError("cohort_failure_receipt_lineage_invalid")
    current = referenced - inherited
    resolved = set()
    for artifact_id in current:
        wire = ledger.get_artifact(artifact_id)
        if wire is None:
            raise RuntimeError("cohort_failure_receipt_lineage_invalid")
        candidate = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
        if candidate.schema_name != "CohortDayFailureReceipt":
            raise RuntimeError("cohort_failure_receipt_lineage_invalid")
        resolved.add(candidate.artifact_id)
    if current != resolved:
        raise RuntimeError("cohort_failure_receipt_lineage_invalid")
    run_receipts = {
        str(item["artifact_id"])
        for item in ledger.list_by_run(str(parsed.run_id))
        if item["schema_name"] == "CohortDayFailureReceipt"
    }
    if run_receipts != current:
        raise RuntimeError("cohort_failure_receipt_unreferenced")


def previous_complete_managed_date(
    manifest: Mapping[str, object],
) -> date | None:
    parsed = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
    if parsed.schema_name != "CohortDayManifest":
        raise RuntimeError("previous_cohort_manifest_invalid")
    prior_complete = [
        date.fromisoformat(str(item["selected_for_date"]))
        for item in adapt_manifest_history(manifest)
        if item["execution_status"] == "COMPLETE"
        and int(item["day_index"]) >= 2
        and int(item["day_index"]) < parsed.payload.day_index
    ]
    return None if not prior_complete else prior_complete[-1]


def validate_persisted_manifest_link(
    ledger: LedgerPort,
    manifest: Mapping[str, object],
    *,
    manifest_date: date,
    previous_manifest: Mapping[str, object] | None,
) -> date | None:
    parsed = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
    if (
        parsed.schema_name != "CohortDayManifest"
        or parsed.payload.day_index != day_index(manifest_date)
        or parsed.payload.selected_for_date != manifest_date.isoformat()
    ):
        raise RuntimeError("previous_cohort_manifest_invalid")
    previous_date = previous_complete_managed_date(manifest)
    expected_id = (
        None if previous_date is None else manifest_artifact_id(previous_date)
    )
    if parsed.payload.previous_manifest_id != expected_id:
        raise RuntimeError("cohort_manifest_predecessor_invalid")
    if expected_id is None:
        if previous_manifest is not None:
            raise RuntimeError("cohort_manifest_predecessor_invalid")
    else:
        if previous_manifest is None:
            raise RuntimeError("cohort_manifest_predecessor_invalid")
        predecessor = parse_artifact(
            previous_manifest, authorized_producers=PRODUCER_REGISTRY
        )
        if (
            predecessor.schema_name != "CohortDayManifest"
            or predecessor.artifact_id != expected_id
            or predecessor.payload.day_index != day_index(previous_date)
            or predecessor.payload.selected_for_date != previous_date.isoformat()
        ):
            raise RuntimeError("cohort_manifest_predecessor_invalid")
    validate_persisted_failure_lineage(
        ledger,
        manifest,
        previous_manifest=previous_manifest,
    )
    return previous_date


def failure_receipt_ids(manifest: Mapping[str, object]) -> set[str]:
    parsed = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
    if parsed.schema_name != "CohortDayManifest":
        raise RuntimeError("previous_cohort_manifest_invalid")
    return {
        str(item["failure_receipt_id"])
        for item in adapt_manifest_history(manifest)
        if item["failure_receipt_id"] is not None
    }


def reconcile_existing_manifest_context(
    manifest: Mapping[str, object],
    *,
    selected_for_date: date,
    previous_manifest: Mapping[str, object] | None,
    missing_days: Sequence[MissingCohortDay],
    source_commit: str,
    image_digest: str,
) -> tuple[str, ...]:
    parsed = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
    previous_id = (
        None if previous_manifest is None else str(previous_manifest["artifact_id"])
    )
    if (
        parsed.schema_name != "CohortDayManifest"
        or parsed.schema_version != "2.1.0"
        or parsed.payload.selected_for_date != selected_for_date.isoformat()
        or parsed.payload.previous_manifest_id != previous_id
        or parsed.payload.source_commit != source_commit
        or parsed.payload.image_digest != image_digest
    ):
        raise RuntimeError("cohort_manifest_context_mismatch")
    inherited = (
        set()
        if previous_manifest is None
        else failure_receipt_ids(previous_manifest)
    )
    persisted = failure_receipt_ids(manifest)
    expected_current = {
        failure_receipt_artifact_id(item.selected_for_date)
        for item in missing_days
    }
    if persisted - inherited != expected_current:
        raise RuntimeError("cohort_manifest_context_mismatch")
    return tuple(sorted(persisted))


def _validate_receipt(
    wire: Mapping[str, object],
    *,
    missing: MissingCohortDay,
    source_commit: str,
    image_digest: str,
) -> None:
    parsed = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
    payload = parsed.payload
    expected = {
        "schema_name": "CohortDayFailureReceipt",
        "artifact_id": failure_receipt_artifact_id(missing.selected_for_date),
        "day_index": day_index(missing.selected_for_date),
        "selected_for_date": missing.selected_for_date.isoformat(),
        "failure_code": FAILURE_CODE,
        "expected_manifest_id": manifest_artifact_id(missing.selected_for_date),
        "runs_predicted": RUN_PREDICTIONS[missing.selected_for_date],
        "runs_created": 0,
        "source_commit": source_commit,
        "image_digest": image_digest,
        "continuation_policy": CONTINUATION_POLICY,
    }
    actual = {
        "schema_name": parsed.schema_name,
        "artifact_id": parsed.artifact_id,
        "day_index": payload.day_index,
        "selected_for_date": payload.selected_for_date,
        "failure_code": payload.failure_code,
        "expected_manifest_id": payload.expected_manifest_id,
        "runs_predicted": payload.runs_predicted,
        "runs_created": payload.runs_created,
        "source_commit": payload.source_commit,
        "image_digest": payload.image_digest,
        "continuation_policy": payload.continuation_policy,
    }
    if actual != expected:
        raise RuntimeError("cohort_failure_receipt_mismatch")


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
