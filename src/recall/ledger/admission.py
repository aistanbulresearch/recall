from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from recall.contracts import Artifact, ContractError, parse_artifact
from recall.contracts.cloud_payload import CloudBoundPayload, parse_cloud_bound_payload
from recall.contracts.enums import ArtifactStatus, DataMode, WatchCaseState
from recall.contracts.payloads.lifecycle import ScanRunPayload, WatchCasePayload
from recall.contracts.payloads.receipts import PrivacyReceiptPayload
from recall.controller.hashes import scan_idempotency_key
from recall.privacy.signing import content_hash as privacy_payload_hash

from .models import WatchCaseRecord
from .producers import PRODUCER_REGISTRY


PrivacyReceiptVerifier = Callable[[Mapping[str, Any]], bool]


@dataclass(frozen=True, slots=True)
class AdmittedWatchCase:
    receipt: Artifact
    cloud_payload: CloudBoundPayload


def validate_watch_case_admission(
    *,
    watch_case: Artifact,
    receipt_wire: Mapping[str, Any] | None,
    cloud_payload_wire: Mapping[str, Any],
    verify_receipt: PrivacyReceiptVerifier | None,
) -> AdmittedWatchCase:
    if watch_case.schema_name != "WatchCase" or not isinstance(
        watch_case.payload, WatchCasePayload
    ):
        raise ContractError("contract_schema_invalid", "WatchCase")
    if watch_case.case_id is None:
        raise ContractError("contract_required_value_missing", "case_id")
    if len(watch_case.input_artifact_ids) != 1:
        raise ContractError("privacy_not_accepted", "watch_case_receipt_link")
    if receipt_wire is None:
        raise ContractError("privacy_not_accepted", "privacy_receipt_missing")
    receipt = _accepted_receipt(
        receipt_wire,
        expected_id=watch_case.input_artifact_ids[0],
        expected_case_id=watch_case.case_id,
        expected_mode=watch_case.data_mode,
        verify_receipt=verify_receipt,
    )
    cloud_payload = parse_cloud_bound_payload(cloud_payload_wire)
    payload = receipt.payload
    assert isinstance(payload, PrivacyReceiptPayload)
    if privacy_payload_hash(cloud_payload.to_wire()) != payload.payload_hash:
        raise ContractError("privacy_not_accepted", "payload_hash_mismatch")
    if (
        cloud_payload.case_token != watch_case.case_id
        or cloud_payload.tenant_id != watch_case.payload.tenant_id
        or cloud_payload.region != watch_case.payload.region
        or cloud_payload.data_mode is not watch_case.data_mode
    ):
        raise ContractError("privacy_not_accepted", "cloud_payload_mismatch")
    return AdmittedWatchCase(receipt=receipt, cloud_payload=cloud_payload)


def validate_scan_run_admission(
    *,
    scan_run: Artifact,
    receipt_wire: Mapping[str, Any] | None,
    watch_case_wire: Mapping[str, Any] | None,
    watch_case_record: WatchCaseRecord | None,
    expected_watch_case_version: int,
    expected_source_cursors: Mapping[str, str],
    triggered_at: datetime,
    verify_receipt: PrivacyReceiptVerifier | None,
    identity_scope: str | None = None,
) -> tuple[Artifact, Artifact]:
    if scan_run.schema_name != "ScanRun" or not isinstance(
        scan_run.payload, ScanRunPayload
    ):
        raise ContractError("contract_schema_invalid", "ScanRun")
    payload = scan_run.payload
    if scan_run.case_id is None or scan_run.case_id != payload.watch_case_id:
        raise ContractError("contract_required_value_missing", "watch_case_id")
    if watch_case_record is None or watch_case_wire is None:
        raise ContractError("stale_write_rejected", payload.watch_case_id)
    watch_case = parse_artifact(
        watch_case_wire, authorized_producers=PRODUCER_REGISTRY
    )
    if watch_case.schema_name != "WatchCase" or not isinstance(
        watch_case.payload, WatchCasePayload
    ):
        raise ContractError("contract_schema_invalid", "WatchCase")
    if (
        watch_case.artifact_id != watch_case_record.artifact_id
        or watch_case.case_id != payload.watch_case_id
    ):
        raise ContractError("artifact_integrity_failed", payload.watch_case_id)
    if len(watch_case.input_artifact_ids) != 1:
        raise ContractError("privacy_not_accepted", "watch_case_receipt_link")
    receipt_id = watch_case.input_artifact_ids[0]
    expected_inputs = tuple(sorted((receipt_id, watch_case.artifact_id)))
    if scan_run.input_artifact_ids != expected_inputs:
        raise ContractError("privacy_not_accepted", "scan_run_dependency_link")
    receipt = _accepted_receipt(
        receipt_wire,
        expected_id=receipt_id,
        expected_case_id=payload.watch_case_id,
        expected_mode=watch_case.data_mode,
        verify_receipt=verify_receipt,
    )
    if scan_run.data_mode is not watch_case.data_mode:
        raise ContractError("privacy_not_accepted", "scan_run_data_mode_mismatch")
    if watch_case_record.state is not WatchCaseState.ACTIVE:
        raise ContractError(
            "contract_transition_invalid", watch_case_record.state.value
        )
    if watch_case_record.version != expected_watch_case_version:
        raise ContractError("stale_write_rejected", payload.watch_case_id)
    if dict(watch_case_record.source_cursors) != dict(expected_source_cursors):
        raise ContractError("stale_write_rejected", "source_cursors")
    expected_key = scan_idempotency_key(
        watch_case_id=payload.watch_case_id,
        source_cursors=expected_source_cursors,
        schedule_epoch=payload.scheduled_for,
        data_mode=scan_run.data_mode.value,
        identity_scope=identity_scope,
    )
    if payload.idempotency_key != expected_key:
        raise ContractError("artifact_integrity_failed", "idempotency_key")
    if watch_case_record.next_scan_at is None:
        raise ContractError("contract_transition_invalid", "next_scan_at")
    due_at = _timestamp(watch_case_record.next_scan_at, "next_scan_at")
    scheduled_for = _timestamp(payload.scheduled_for, "scheduled_for")
    if scheduled_for != due_at or due_at > triggered_at:
        raise ContractError("contract_transition_invalid", "watch_case_not_due")
    return receipt, watch_case


def _accepted_receipt(
    value: Mapping[str, Any] | None,
    *,
    expected_id: str,
    expected_case_id: str,
    expected_mode: DataMode,
    verify_receipt: PrivacyReceiptVerifier | None,
) -> Artifact:
    if value is None:
        raise ContractError("privacy_not_accepted", "privacy_receipt_missing")
    receipt = parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
    if receipt.schema_name != "PrivacyReceipt" or not isinstance(
        receipt.payload, PrivacyReceiptPayload
    ):
        raise ContractError("privacy_not_accepted", "privacy_receipt_schema")
    if (
        receipt.artifact_id != expected_id
        or receipt.case_id != expected_case_id
        or receipt.data_mode is not expected_mode
        or receipt.status is not ArtifactStatus.VALID
        or receipt.payload.decision.value != "ACCEPTED"
    ):
        raise ContractError("privacy_not_accepted", "privacy_receipt_mismatch")
    if verify_receipt is None or not verify_receipt(value):
        raise ContractError("privacy_not_accepted", "privacy_signature_invalid")
    return receipt


def _timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("contract_timestamp_invalid", field) from exc
    if parsed.tzinfo is None:
        raise ContractError("contract_timestamp_invalid", field)
    return parsed
