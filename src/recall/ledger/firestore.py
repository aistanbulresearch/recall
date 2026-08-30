from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID, uuid5

import google.auth
from google.cloud import firestore
from google.cloud.firestore_v1.base_client import BaseClient
from google.cloud.firestore_v1.base_query import FieldFilter

from recall.contracts import Artifact, ContractError, parse_artifact
from recall.contracts.enums import ExecutionProfile, ScanRunEventCode, ScanRunState
from recall.contracts.payloads.lifecycle import ScanRunPayload, WatchCasePayload
from recall.controller.lifecycle import require_transition, transition_target

from .admission import (
    PrivacyReceiptVerifier,
    validate_scan_run_admission,
    validate_watch_case_admission,
)
from .agent_step import (
    validate_agent_step_artifacts,
    validate_started_receipt_binding,
    validate_tool_authorization_bindings,
)
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
        privacy_receipt_verifier: PrivacyReceiptVerifier | None = None,
        persistence_surface: str = "FIRESTORE_UNVERIFIED",
        project_sha256: str = "NOT_VERIFIED",
        database: str = "(default)",
    ) -> None:
        if not _PREFIX.fullmatch(collection_prefix):
            raise ValueError("collection_prefix_invalid")
        if collection_prefix and not collection_prefix.endswith("_"):
            raise ValueError("collection_prefix_must_end_with_underscore")
        self._client = client
        self._prefix = collection_prefix
        self._cleanup_allowed = cleanup_allowed
        self._privacy_receipt_verifier = privacy_receipt_verifier
        self._persistence_surface = persistence_surface
        self._project_sha256 = project_sha256
        self._database = database

    @classmethod
    def from_default_credentials(
        cls,
        *,
        collection_prefix: str = "",
        privacy_receipt_verifier: PrivacyReceiptVerifier | None = None,
        expected_project_sha256: str | None = None,
        database: str = "(default)",
        require_live: bool = False,
    ) -> "FirestoreLedger":
        emulator = bool(os.getenv("FIRESTORE_EMULATOR_HOST"))
        if require_live and emulator:
            raise ValueError("live_firestore_emulator_forbidden")
        if not emulator and collection_prefix and not collection_prefix.startswith(
            "dev_recall_"
        ):
            raise ValueError("live_collection_prefix_must_start_with_dev_recall")
        credentials, default_project = google.auth.default()
        project = (
            os.getenv("RECALL_GCP_PROJECT")
            or default_project
            or getattr(credentials, "quota_project_id", None)
        )
        if not project:
            raise ValueError("firestore_project_unresolved")
        project_sha256 = hashlib.sha256(project.encode("utf-8")).hexdigest()
        if (
            expected_project_sha256 is not None
            and project_sha256 != expected_project_sha256
        ):
            raise ValueError("firestore_project_mismatch")
        if database != "(default)":
            raise ValueError("firestore_database_mismatch")
        cleanup_allowed = emulator or collection_prefix.startswith("dev_recall_")
        return cls(
            firestore.Client(
                project=project,
                credentials=credentials,
                database=database,
            ),
            collection_prefix=collection_prefix,
            cleanup_allowed=cleanup_allowed,
            privacy_receipt_verifier=privacy_receipt_verifier,
            persistence_surface=(
                "FIRESTORE_EMULATOR" if emulator else "LIVE_FIRESTORE"
            ),
            project_sha256=project_sha256,
            database=database,
        )

    def _collection(self, name: str) -> Any:
        if name not in COLLECTION_NAMES:
            raise ValueError(f"unknown_collection:{name}")
        return self._client.collection(f"{self._prefix}{name}")

    @property
    def client(self) -> BaseClient:
        return self._client

    @property
    def collection_prefix(self) -> str:
        return self._prefix

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
        self,
        value: Mapping[str, Any],
        *,
        cloud_bound_payload: Mapping[str, Any],
        now: datetime,
    ) -> tuple[WatchCaseRecord, bool]:
        artifact = parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
        if artifact.schema_name != "WatchCase" or not isinstance(
            artifact.payload, WatchCasePayload
        ):
            raise ContractError("contract_schema_invalid", "WatchCase")
        if artifact.case_id is None:
            raise ContractError("contract_required_value_missing", "case_id")
        if len(artifact.input_artifact_ids) != 1:
            raise ContractError("privacy_not_accepted", "watch_case_receipt_link")
        case_reference = self._collection("watch_cases").document(artifact.case_id)
        receipt_reference = self._collection("artifacts").document(
            artifact.input_artifact_ids[0]
        )
        artifact_reference = self._collection("artifacts").document(
            artifact.artifact_id
        )
        transaction = self._client.transaction()

        @firestore.transactional
        def create_once(txn: Any) -> tuple[dict[str, object], bool]:
            case_snapshot = case_reference.get(transaction=txn)
            receipt_snapshot = receipt_reference.get(transaction=txn)
            artifact_snapshot = artifact_reference.get(transaction=txn)
            validate_watch_case_admission(
                watch_case=artifact,
                receipt_wire=(
                    receipt_snapshot.to_dict() if receipt_snapshot.exists else None
                ),
                cloud_payload_wire=cloud_bound_payload,
                verify_receipt=self._privacy_receipt_verifier,
            )
            if case_snapshot.exists:
                existing = WatchCaseRecord.from_wire(case_snapshot.to_dict())
                if not artifact_snapshot.exists:
                    raise ContractError(
                        "artifact_integrity_failed", artifact.case_id
                    )
                existing_artifact = parse_artifact(
                    artifact_snapshot.to_dict(),
                    authorized_producers=PRODUCER_REGISTRY,
                )
                if (
                    existing.artifact_id != artifact.artifact_id
                    or existing_artifact.content_hash != artifact.content_hash
                ):
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
        self,
        value: Mapping[str, Any],
        *,
        expected_watch_case_version: int,
        expected_source_cursors: Mapping[str, str],
        triggered_at: datetime,
        now: datetime,
        identity_scope: str | None = None,
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
        payload = artifact.payload
        assert isinstance(payload, ScanRunPayload)
        case_reference = self._collection("watch_cases").document(
            payload.watch_case_id
        )
        transaction = self._client.transaction()

        @firestore.transactional
        def create_once(txn: Any) -> tuple[dict[str, object], bool]:
            run_snapshot = run_reference.get(transaction=txn)
            case_snapshot = case_reference.get(transaction=txn)
            scan_artifact_snapshot = artifact_reference.get(transaction=txn)
            watch_record = (
                WatchCaseRecord.from_wire(case_snapshot.to_dict())
                if case_snapshot.exists
                else None
            )
            watch_reference = (
                None
                if watch_record is None
                else self._collection("artifacts").document(watch_record.artifact_id)
            )
            watch_snapshot = (
                None
                if watch_reference is None
                else watch_reference.get(transaction=txn)
            )
            watch_wire = (
                None
                if watch_snapshot is None or not watch_snapshot.exists
                else watch_snapshot.to_dict()
            )
            receipt_reference = None
            if watch_wire is not None:
                watch_artifact = parse_artifact(
                    watch_wire, authorized_producers=PRODUCER_REGISTRY
                )
                if len(watch_artifact.input_artifact_ids) == 1:
                    receipt_reference = self._collection("artifacts").document(
                        watch_artifact.input_artifact_ids[0]
                    )
            receipt_snapshot = (
                None
                if receipt_reference is None
                else receipt_reference.get(transaction=txn)
            )
            validate_scan_run_admission(
                scan_run=artifact,
                receipt_wire=(
                    None
                    if receipt_snapshot is None or not receipt_snapshot.exists
                    else receipt_snapshot.to_dict()
                ),
                watch_case_wire=watch_wire,
                watch_case_record=watch_record,
                expected_watch_case_version=expected_watch_case_version,
                expected_source_cursors=expected_source_cursors,
                triggered_at=triggered_at,
                verify_receipt=self._privacy_receipt_verifier,
                identity_scope=identity_scope,
            )
            if run_snapshot.exists:
                existing = ScanRunRecord.from_wire(run_snapshot.to_dict())
                if not scan_artifact_snapshot.exists:
                    raise ContractError("artifact_integrity_failed", artifact.run_id)
                existing_artifact = parse_artifact(
                    scan_artifact_snapshot.to_dict(),
                    authorized_producers=PRODUCER_REGISTRY,
                )
                if (
                    existing.scan_run_artifact_id != artifact.artifact_id
                    or existing_artifact.content_hash != artifact.content_hash
                ):
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

    def backend_metadata(self) -> Mapping[str, str]:
        return {
            "persistence_surface": self._persistence_surface,
            "project_sha256": self._project_sha256,
            "database": self._database,
        }

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
            if closed_event is ScanRunEventCode.FULL_AUDIT_REQUIRED:
                raise ContractError("full_audit_specialized_commit_required")
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

    def commit_agent_step(
        self,
        run_id: str,
        *,
        expected_version: int,
        lease_epoch: int,
        event_code: ScanRunEventCode,
        artifacts: Sequence[Mapping[str, Any]],
        now: datetime,
    ) -> ScanRunRecord:
        parsed_artifacts = tuple(
            parse_artifact(item, authorized_producers=PRODUCER_REGISTRY)
            for item in artifacts
        )
        validate_agent_step_artifacts(run_id, event_code, parsed_artifacts)
        run_reference = self._collection("scan_runs").document(run_id)
        event_id = str(uuid5(UUID(run_id), f"scan-run-event:{expected_version + 1}"))
        event_reference = self._collection("scan_run_events").document(event_id)
        artifact_references = {
            artifact.artifact_id: self._collection("artifacts").document(
                artifact.artifact_id
            )
            for artifact in parsed_artifacts
        }
        terminal_receipt = next(
            artifact
            for artifact in parsed_artifacts
            if artifact.schema_name == "AgentExecutionReceipt"
        )
        started_reference = self._collection("artifacts").document(
            terminal_receipt.payload.started_receipt_id
        )
        authorization_references = {
            record["authorization_receipt_id"]: self._collection(
                "artifacts"
            ).document(record["authorization_receipt_id"])
            for record in terminal_receipt.payload.tool_records
        }
        transaction = self._client.transaction()

        @firestore.transactional
        def apply_agent_step(txn: Any) -> dict[str, object]:
            run_snapshot = run_reference.get(transaction=txn)
            if not run_snapshot.exists:
                raise ContractError("stale_write_rejected", run_id)
            current = ScanRunRecord.from_wire(run_snapshot.to_dict())
            if (
                current.version != expected_version
                or current.lease_epoch != lease_epoch
            ):
                raise ContractError("stale_write_rejected", run_id)
            if current.lease_expires_at is not None and now >= current.lease_expires_at:
                raise ContractError("lease_expired", run_id)
            if current.scan_run_artifact_id is None:
                raise ContractError("ledger_integrity_failed", run_id)
            scan_reference = self._collection("artifacts").document(
                current.scan_run_artifact_id
            )
            scan_snapshot = scan_reference.get(transaction=txn)
            if not scan_snapshot.exists:
                raise ContractError("ledger_integrity_failed", run_id)
            scan_artifact = parse_artifact(
                scan_snapshot.to_dict(), authorized_producers=PRODUCER_REGISTRY
            )
            if (
                scan_artifact.schema_version != "1.1.0"
                or scan_artifact.payload.execution_profile
                is not ExecutionProfile.FULL_AUDIT_V1
            ):
                raise ContractError("full_audit_profile_required", run_id)
            started_snapshot = started_reference.get(transaction=txn)
            if not started_snapshot.exists:
                raise ContractError("ledger_integrity_failed", "started_receipt_id")
            validate_started_receipt_binding(
                terminal_receipt,
                parse_artifact(
                    started_snapshot.to_dict(),
                    authorized_producers=PRODUCER_REGISTRY,
                ),
            )
            authorization_receipts = []
            for receipt_id, reference in authorization_references.items():
                snapshot = reference.get(transaction=txn)
                if not snapshot.exists:
                    raise ContractError(
                        "ledger_integrity_failed", "tool_authorization_binding"
                    )
                authorization_receipts.append(
                    parse_artifact(
                        snapshot.to_dict(), authorized_producers=PRODUCER_REGISTRY
                    )
                )
            validate_tool_authorization_bindings(
                terminal_receipt, authorization_receipts
            )
            existing_snapshots = {
                artifact_id: reference.get(transaction=txn)
                for artifact_id, reference in artifact_references.items()
            }
            for artifact in parsed_artifacts:
                existing = existing_snapshots[artifact.artifact_id]
                if (
                    existing.exists
                    and existing.to_dict()["content_hash"] != artifact.content_hash
                ):
                    raise ContractError(
                        "artifact_integrity_failed", artifact.artifact_id
                    )
            target = transition_target(current.state, event_code)
            version = expected_version + 1
            updated = ScanRunRecord(
                run_id=run_id,
                state=target,
                version=version,
                lease_epoch=lease_epoch,
                lease_expires_at=current.lease_expires_at,
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
                lease_epoch=lease_epoch,
                created_at=now,
            )
            txn.set(run_reference, updated.to_wire())
            txn.create(event_reference, event.to_wire())
            for artifact in parsed_artifacts:
                if not existing_snapshots[artifact.artifact_id].exists:
                    txn.create(
                        artifact_references[artifact.artifact_id],
                        artifact.to_wire(),
                    )
            return updated.to_wire()

        return ScanRunRecord.from_wire(apply_agent_step(transaction))

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
