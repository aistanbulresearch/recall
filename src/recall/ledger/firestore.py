from __future__ import annotations

import os
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID, uuid5

from google.cloud import firestore
from google.cloud.firestore_v1.base_client import BaseClient
from google.cloud.firestore_v1.base_query import FieldFilter

from recall.contracts import Artifact, ContractError, parse_artifact
from recall.contracts.enums import ScanRunEventCode, ScanRunState
from recall.contracts.payloads.lifecycle import ScanRunPayload, WatchCasePayload
from recall.controller.lifecycle import require_transition

from .firestore_terminal import FirestoreTerminalMixin
from .models import (
    COLLECTION_NAMES,
    ReviewTaskRecord,
    ScanRunEventRecord,
    ScanRunRecord,
    WatchCaseRecord,
)
from .producers import PRODUCER_REGISTRY


_PREFIX = re.compile(r"^[a-z0-9_]*$")


class FirestoreLedger(FirestoreTerminalMixin):
    collection_names = COLLECTION_NAMES

    def __init__(
        self,
        client: BaseClient,
        *,
        collection_prefix: str = "",
        cleanup_allowed: bool = False,
    ) -> None:
        if not _PREFIX.fullmatch(collection_prefix):
            raise ValueError("collection_prefix_invalid")
        if collection_prefix and not collection_prefix.endswith("_"):
            raise ValueError("collection_prefix_must_end_with_underscore")
        self._client = client
        self._prefix = collection_prefix
        self._cleanup_allowed = cleanup_allowed

    @classmethod
    def from_default_credentials(
        cls, *, collection_prefix: str = ""
    ) -> "FirestoreLedger":
        emulator = bool(os.getenv("FIRESTORE_EMULATOR_HOST"))
        if not emulator and collection_prefix and not collection_prefix.startswith(
            "dev_recall_"
        ):
            raise ValueError("live_collection_prefix_must_start_with_dev_recall")
        cleanup_allowed = emulator or collection_prefix.startswith("dev_recall_")
        return cls(
            firestore.Client(database="(default)"),
            collection_prefix=collection_prefix,
            cleanup_allowed=cleanup_allowed,
        )

    def _collection(self, name: str) -> Any:
        if name not in COLLECTION_NAMES:
            raise ValueError(f"unknown_collection:{name}")
        return self._client.collection(f"{self._prefix}{name}")

    def append_artifact(self, value: Mapping[str, Any]) -> Artifact:
        artifact = parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
        reference = self._collection("artifacts").document(artifact.artifact_id)
        transaction = self._client.transaction()

        @firestore.transactional
        def append_once(txn: Any) -> None:
            snapshot = reference.get(transaction=txn)
            if snapshot.exists:
                existing = snapshot.to_dict()
                if existing["content_hash"] != artifact.content_hash:
                    raise ContractError(
                        "artifact_integrity_failed", artifact.artifact_id
                    )
                return
            txn.create(reference, artifact.to_wire())

        append_once(transaction)
        return artifact

    def create_watch_case(
        self, value: Mapping[str, Any], *, now: datetime
    ) -> tuple[WatchCaseRecord, bool]:
        artifact = parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
        if artifact.schema_name != "WatchCase" or not isinstance(
            artifact.payload, WatchCasePayload
        ):
            raise ContractError("contract_schema_invalid", "WatchCase")
        if artifact.case_id is None:
            raise ContractError("contract_required_value_missing", "case_id")
        case_reference = self._collection("watch_cases").document(artifact.case_id)
        artifact_reference = self._collection("artifacts").document(
            artifact.artifact_id
        )
        transaction = self._client.transaction()

        @firestore.transactional
        def create_once(txn: Any) -> tuple[dict[str, object], bool]:
            snapshot = case_reference.get(transaction=txn)
            if snapshot.exists:
                existing = WatchCaseRecord.from_wire(snapshot.to_dict())
                if existing.artifact_id != artifact.artifact_id:
                    raise ContractError("artifact_integrity_failed", artifact.case_id)
                return existing.to_wire(), False
            payload = artifact.payload
            assert isinstance(payload, WatchCasePayload)
            record = WatchCaseRecord(
                watch_case_id=artifact.case_id,
                artifact_id=artifact.artifact_id,
                state=payload.state,
                version=1,
                source_cursors=tuple(payload.source_cursors.items()),
                last_verified_snapshot_id=payload.last_verified_snapshot_id,
                pending_observation_hashes=payload.pending_observation_hashes,
                open_review_task_id=payload.open_review_task_id,
                attention_reason_codes=(),
                next_scan_at=payload.next_scan_at,
                updated_at=now,
            )
            txn.create(artifact_reference, artifact.to_wire())
            txn.create(case_reference, record.to_wire())
            return record.to_wire(), True

        wire, created = create_once(transaction)
        return WatchCaseRecord.from_wire(wire), created

    def create_scan_run(
        self, value: Mapping[str, Any], *, now: datetime
    ) -> tuple[ScanRunRecord, bool]:
        artifact = parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
        if artifact.schema_name != "ScanRun" or not isinstance(
            artifact.payload, ScanRunPayload
        ):
            raise ContractError("contract_schema_invalid", "ScanRun")
        if artifact.run_id is None:
            raise ContractError("contract_required_value_missing", "run_id")
        require_transition(
            None, ScanRunEventCode.RUN_CREATED, ScanRunState.CREATED
        )
        run_reference = self._collection("scan_runs").document(artifact.run_id)
        artifact_reference = self._collection("artifacts").document(
            artifact.artifact_id
        )
        event_id = str(uuid5(UUID(artifact.run_id), "scan-run-event:1"))
        event_reference = self._collection("scan_run_events").document(event_id)
        transaction = self._client.transaction()

        @firestore.transactional
        def create_once(txn: Any) -> tuple[dict[str, object], bool]:
            snapshot = run_reference.get(transaction=txn)
            if snapshot.exists:
                existing = ScanRunRecord.from_wire(snapshot.to_dict())
                if existing.scan_run_artifact_id != artifact.artifact_id:
                    raise ContractError("artifact_integrity_failed", artifact.run_id)
                return existing.to_wire(), False
            record = ScanRunRecord(
                run_id=artifact.run_id,
                state=ScanRunState.CREATED,
                version=1,
                lease_epoch=0,
                lease_expires_at=None,
                updated_at=now,
                scan_run_artifact_id=artifact.artifact_id,
                terminal_policy_decision_id=None,
                failure_receipt_ids=(),
                last_repeated_state_hash=None,
                repeated_state_count=0,
            )
            event = ScanRunEventRecord(
                event_id=event_id,
                run_id=artifact.run_id,
                sequence=1,
                from_state=None,
                to_state=ScanRunState.CREATED,
                event_code=ScanRunEventCode.RUN_CREATED,
                agent_id=None,
                lease_epoch=0,
                created_at=now,
            )
            txn.create(artifact_reference, artifact.to_wire())
            txn.create(run_reference, record.to_wire())
            txn.create(event_reference, event.to_wire())
            return record.to_wire(), True

        wire, created = create_once(transaction)
        return ScanRunRecord.from_wire(wire), created

    def get_artifact(self, artifact_id: str) -> dict[str, object] | None:
        snapshot = self._collection("artifacts").document(artifact_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def list_by_run(self, run_id: str) -> tuple[dict[str, object], ...]:
        query = self._collection("artifacts").where(
            filter=FieldFilter("run_id", "==", run_id)
        )
        values = [snapshot.to_dict() for snapshot in query.stream()]
        return tuple(sorted(values, key=lambda item: str(item["artifact_id"])))

    def transition_with_cas(
        self,
        run_id: str,
        *,
        expected_version: int,
        lease_epoch: int,
        to_state: str,
        event_code: ScanRunEventCode,
        now: datetime,
        next_lease_expires_at: datetime | None = None,
    ) -> ScanRunRecord:
        run_reference = self._collection("scan_runs").document(run_id)
        event_id = str(uuid5(UUID(run_id), f"scan-run-event:{expected_version + 1}"))
        event_reference = self._collection("scan_run_events").document(event_id)
        transaction = self._client.transaction()

        @firestore.transactional
        def apply_transition(txn: Any) -> dict[str, object]:
            snapshot = run_reference.get(transaction=txn)
            if not snapshot.exists:
                raise ContractError("stale_write_rejected", run_id)
            current = ScanRunRecord.from_wire(snapshot.to_dict())
            if (
                current.version != expected_version
                or current.lease_epoch != lease_epoch
            ):
                raise ContractError("stale_write_rejected", run_id)
            if current.state in {
                ScanRunState.NO_ACTION,
                ScanRunState.ABSTAIN,
                ScanRunState.REVIEW_REQUIRED,
                ScanRunState.HALTED,
            }:
                raise ContractError("contract_transition_invalid", current.state.value)
            if current.lease_expires_at is not None and now >= current.lease_expires_at:
                raise ContractError("lease_expired", run_id)
            prior_state = current.state
            expiry = next_lease_expires_at or current.lease_expires_at
            try:
                target_state = ScanRunState(to_state)
                closed_event = ScanRunEventCode(event_code)
            except ValueError as exc:
                raise ContractError(
                    "contract_enum_invalid", "scan_run_transition"
                ) from exc
            require_transition(prior_state, closed_event, target_state)
            version = expected_version + 1
            updated = ScanRunRecord(
                run_id=run_id,
                state=target_state,
                version=version,
                lease_epoch=lease_epoch,
                lease_expires_at=expiry,
                updated_at=now,
                scan_run_artifact_id=current.scan_run_artifact_id,
                terminal_policy_decision_id=current.terminal_policy_decision_id,
                failure_receipt_ids=current.failure_receipt_ids,
                last_repeated_state_hash=current.last_repeated_state_hash,
                repeated_state_count=current.repeated_state_count,
            )
            event = ScanRunEventRecord(
                event_id=event_id,
                run_id=run_id,
                sequence=version,
                from_state=prior_state,
                to_state=target_state,
                event_code=closed_event,
                agent_id=None,
                lease_epoch=lease_epoch,
                created_at=now,
            )
            txn.set(run_reference, updated.to_wire())
            txn.create(event_reference, event.to_wire())
            return updated.to_wire()

        return ScanRunRecord.from_wire(apply_transition(transaction))

    def acquire_lease(
        self,
        run_id: str,
        *,
        expected_version: int,
        new_epoch: int,
        expires_at: datetime,
        now: datetime,
    ) -> ScanRunRecord:
        run_reference = self._collection("scan_runs").document(run_id)
        event_id = str(uuid5(UUID(run_id), f"scan-run-event:{expected_version + 1}"))
        event_reference = self._collection("scan_run_events").document(event_id)
        transaction = self._client.transaction()

        @firestore.transactional
        def acquire(txn: Any) -> dict[str, object]:
            snapshot = run_reference.get(transaction=txn)
            if not snapshot.exists:
                raise ContractError("stale_write_rejected", run_id)
            current = ScanRunRecord.from_wire(snapshot.to_dict())
            if current.version != expected_version or new_epoch <= current.lease_epoch:
                raise ContractError("stale_write_rejected", run_id)
            if expires_at <= now:
                raise ContractError("lease_expired", run_id)
            if current.lease_expires_at is not None and now < current.lease_expires_at:
                raise ContractError("lease_active", run_id)
            if current.state is ScanRunState.QUEUED:
                target = ScanRunState.ROUTING
                event_code = ScanRunEventCode.LEASE_ACQUIRED
            elif current.state in {
                ScanRunState.ROUTING,
                ScanRunState.WATCHING,
                ScanRunState.ASSESSING,
                ScanRunState.AUDITING,
                ScanRunState.POLICY_EVALUATION,
            }:
                target = current.state
                event_code = ScanRunEventCode.LEASE_TAKEN_OVER
            else:
                raise ContractError("contract_transition_invalid", current.state.value)
            require_transition(current.state, event_code, target)
            version = current.version + 1
            updated = ScanRunRecord(
                run_id=run_id,
                state=target,
                version=version,
                lease_epoch=new_epoch,
                lease_expires_at=expires_at,
                updated_at=now,
                scan_run_artifact_id=current.scan_run_artifact_id,
                terminal_policy_decision_id=current.terminal_policy_decision_id,
                failure_receipt_ids=current.failure_receipt_ids,
                last_repeated_state_hash=current.last_repeated_state_hash,
                repeated_state_count=current.repeated_state_count,
            )
            event = ScanRunEventRecord(
                event_id=event_id,
                run_id=run_id,
                sequence=version,
                from_state=current.state,
                to_state=target,
                event_code=event_code,
                agent_id=None,
                lease_epoch=new_epoch,
                created_at=now,
            )
            txn.set(run_reference, updated.to_wire())
            txn.create(event_reference, event.to_wire())
            return updated.to_wire()

        return ScanRunRecord.from_wire(acquire(transaction))

    def get_scan_run(self, run_id: str) -> ScanRunRecord | None:
        snapshot = self._collection("scan_runs").document(run_id).get()
        return ScanRunRecord.from_wire(snapshot.to_dict()) if snapshot.exists else None

    def list_scan_run_events(
        self, run_id: str
    ) -> tuple[ScanRunEventRecord, ...]:
        query = self._collection("scan_run_events").where(
            filter=FieldFilter("run_id", "==", run_id)
        )
        return tuple(
            sorted(
                (
                    ScanRunEventRecord.from_wire(snapshot.to_dict())
                    for snapshot in query.stream()
                ),
                key=lambda event: event.sequence,
            )
        )

    def read_back_count(self, collection: str, *, run_id: str | None = None) -> int:
        query: Any = self._collection(collection)
        if run_id is not None:
            query = query.where(filter=FieldFilter("run_id", "==", run_id))
        return sum(1 for _ in query.stream())

    def cleanup_collections(self) -> None:
        if not self._cleanup_allowed:
            raise ContractError("cleanup_not_authorized")
        for collection in COLLECTION_NAMES:
            snapshots = list(self._collection(collection).stream())
            for offset in range(0, len(snapshots), 100):
                batch = self._client.batch()
                for snapshot in snapshots[offset : offset + 100]:
                    batch.delete(snapshot.reference)
                batch.commit()
