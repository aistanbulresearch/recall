from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from threading import RLock
from typing import Any
from uuid import UUID, uuid5

from recall.contracts import Artifact, ContractError, parse_artifact
from recall.contracts.enums import ScanRunEventCode, ScanRunState
from recall.contracts.payloads.lifecycle import ScanRunPayload, WatchCasePayload
from recall.controller.lifecycle import require_transition

from .admission import (
    PrivacyReceiptVerifier,
    validate_scan_run_admission,
    validate_watch_case_admission,
)
from .memory_terminal import InMemoryTerminalMixin
from .models import (
    COLLECTION_NAMES,
    ReviewTaskRecord,
    ScanRunEventRecord,
    ScanRunRecord,
    WatchCaseRecord,
)
from .producers import PRODUCER_REGISTRY


class InMemoryLedger(InMemoryTerminalMixin):
    collection_names = COLLECTION_NAMES

    def __init__(
        self, *, privacy_receipt_verifier: PrivacyReceiptVerifier | None = None
    ) -> None:
        self._artifacts: dict[str, dict[str, object]] = {}
        self._scan_runs: dict[str, ScanRunRecord] = {}
        self._scan_run_events: dict[str, ScanRunEventRecord] = {}
        self._watch_cases: dict[str, WatchCaseRecord] = {}
        self._review_tasks: dict[str, ReviewTaskRecord] = {}
        self._privacy_receipt_verifier = privacy_receipt_verifier
        self._lock = RLock()

    def append_artifact(self, value: Mapping[str, Any]) -> Artifact:
        artifact = parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
        with self._lock:
            existing = self._artifacts.get(artifact.artifact_id)
            if existing is not None:
                if existing["content_hash"] != artifact.content_hash:
                    raise ContractError(
                        "artifact_integrity_failed", artifact.artifact_id
                    )
                return parse_artifact(
                    existing, authorized_producers=PRODUCER_REGISTRY
                )
            self._artifacts[artifact.artifact_id] = deepcopy(artifact.to_wire())
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
        with self._lock:
            receipt_wire = (
                self._artifacts.get(artifact.input_artifact_ids[0])
                if len(artifact.input_artifact_ids) == 1
                else None
            )
            validate_watch_case_admission(
                watch_case=artifact,
                receipt_wire=receipt_wire,
                cloud_payload_wire=cloud_bound_payload,
                verify_receipt=self._privacy_receipt_verifier,
            )
            existing = self._watch_cases.get(artifact.case_id)
            if existing is not None:
                existing_wire = self._artifacts.get(existing.artifact_id)
                if existing_wire is None:
                    raise ContractError(
                        "artifact_integrity_failed", artifact.case_id
                    )
                existing_artifact = parse_artifact(
                    existing_wire, authorized_producers=PRODUCER_REGISTRY
                )
                if (
                    existing.artifact_id != artifact.artifact_id
                    or existing_artifact.content_hash != artifact.content_hash
                ):
                    raise ContractError("artifact_integrity_failed", artifact.case_id)
                return existing, False
            self.append_artifact(value)
            payload = artifact.payload
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
            self._watch_cases[record.watch_case_id] = record
            return record, True

    def create_scan_run(
        self,
        value: Mapping[str, Any],
        *,
        expected_watch_case_version: int,
        expected_source_cursors: Mapping[str, str],
        triggered_at: datetime,
        now: datetime,
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
        with self._lock:
            payload = artifact.payload
            assert isinstance(payload, ScanRunPayload)
            watch_record = self._watch_cases.get(payload.watch_case_id)
            watch_wire = (
                None
                if watch_record is None
                else self._artifacts.get(watch_record.artifact_id)
            )
            receipt_wire = None
            if watch_wire is not None:
                watch_artifact = parse_artifact(
                    watch_wire, authorized_producers=PRODUCER_REGISTRY
                )
                if len(watch_artifact.input_artifact_ids) == 1:
                    receipt_wire = self._artifacts.get(
                        watch_artifact.input_artifact_ids[0]
                    )
            validate_scan_run_admission(
                scan_run=artifact,
                receipt_wire=receipt_wire,
                watch_case_wire=watch_wire,
                watch_case_record=watch_record,
                expected_watch_case_version=expected_watch_case_version,
                expected_source_cursors=expected_source_cursors,
                triggered_at=triggered_at,
                verify_receipt=self._privacy_receipt_verifier,
            )
            existing = self._scan_runs.get(artifact.run_id)
            if existing is not None:
                existing_wire = self._artifacts.get(
                    str(existing.scan_run_artifact_id)
                )
                if existing_wire is None:
                    raise ContractError("artifact_integrity_failed", artifact.run_id)
                existing_artifact = parse_artifact(
                    existing_wire, authorized_producers=PRODUCER_REGISTRY
                )
                if (
                    existing.scan_run_artifact_id != artifact.artifact_id
                    or existing_artifact.content_hash != artifact.content_hash
                ):
                    raise ContractError("artifact_integrity_failed", artifact.run_id)
                return existing, False
            self.append_artifact(value)
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
                event_id=str(uuid5(UUID(artifact.run_id), "scan-run-event:1")),
                run_id=artifact.run_id,
                sequence=1,
                from_state=None,
                to_state=ScanRunState.CREATED,
                event_code=ScanRunEventCode.RUN_CREATED,
                agent_id=None,
                lease_epoch=0,
                created_at=now,
            )
            self._scan_runs[record.run_id] = record
            self._scan_run_events[event.event_id] = event
            return record, True

    def backend_metadata(self) -> Mapping[str, str]:
        return {
            "persistence_surface": "IN_MEMORY_TEST",
            "project_sha256": "NOT_APPLICABLE",
            "database": "NOT_APPLICABLE",
        }

    def get_artifact(self, artifact_id: str) -> dict[str, object] | None:
        value = self._artifacts.get(artifact_id)
        return None if value is None else deepcopy(value)

    def list_by_run(self, run_id: str) -> tuple[dict[str, object], ...]:
        values = [
            deepcopy(value)
            for value in self._artifacts.values()
            if value["run_id"] == run_id
        ]
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
        with self._lock:
            return self._transition_locked(
                run_id,
                expected_version=expected_version,
                lease_epoch=lease_epoch,
                to_state=to_state,
                event_code=event_code,
                now=now,
                next_lease_expires_at=next_lease_expires_at,
            )

    def _transition_locked(
        self,
        run_id: str,
        *,
        expected_version: int,
        lease_epoch: int,
        to_state: str,
        event_code: ScanRunEventCode,
        now: datetime,
        next_lease_expires_at: datetime | None,
    ) -> ScanRunRecord:
        current = self._scan_runs.get(run_id)
        if current is None:
            raise ContractError("stale_write_rejected", run_id)
        if current.version != expected_version or current.lease_epoch != lease_epoch:
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
            raise ContractError("contract_enum_invalid", "scan_run_transition") from exc
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
            event_id=str(uuid5(UUID(run_id), f"scan-run-event:{version}")),
            run_id=run_id,
            sequence=version,
            from_state=prior_state,
            to_state=target_state,
            event_code=closed_event,
            agent_id=None,
            lease_epoch=lease_epoch,
            created_at=now,
        )
        self._scan_runs[run_id] = updated
        self._scan_run_events[event.event_id] = event
        return updated

    def acquire_lease(
        self,
        run_id: str,
        *,
        expected_version: int,
        new_epoch: int,
        expires_at: datetime,
        now: datetime,
    ) -> ScanRunRecord:
        with self._lock:
            current = self._scan_runs.get(run_id)
            if current is None or current.version != expected_version:
                raise ContractError("stale_write_rejected", run_id)
            if new_epoch <= current.lease_epoch:
                raise ContractError("stale_write_rejected", "lease_epoch")
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
                event_id=str(uuid5(UUID(run_id), f"scan-run-event:{version}")),
                run_id=run_id,
                sequence=version,
                from_state=current.state,
                to_state=target,
                event_code=event_code,
                agent_id=None,
                lease_epoch=new_epoch,
                created_at=now,
            )
            self._scan_runs[run_id] = updated
            self._scan_run_events[event.event_id] = event
            return updated

    def get_scan_run(self, run_id: str) -> ScanRunRecord | None:
        return self._scan_runs.get(run_id)

    def list_scan_run_events(
        self, run_id: str
    ) -> tuple[ScanRunEventRecord, ...]:
        return tuple(
            sorted(
                (
                    event
                    for event in self._scan_run_events.values()
                    if event.run_id == run_id
                ),
                key=lambda event: event.sequence,
            )
        )

    def read_back_count(self, collection: str, *, run_id: str | None = None) -> int:
        if collection not in COLLECTION_NAMES:
            raise ValueError(f"unknown_collection:{collection}")
        values: list[Mapping[str, object]]
        if collection == "artifacts":
            values = list(self._artifacts.values())
        elif collection == "scan_runs":
            values = [value.to_wire() for value in self._scan_runs.values()]
        elif collection == "scan_run_events":
            values = [value.to_wire() for value in self._scan_run_events.values()]
        elif collection == "watch_cases":
            values = [value.to_wire() for value in self._watch_cases.values()]
        else:
            values = [value.to_wire() for value in self._review_tasks.values()]
        if run_id is not None:
            values = [value for value in values if value.get("run_id") == run_id]
        return len(values)
