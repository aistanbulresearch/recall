from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID, uuid5

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from recall.contracts import ContractError, parse_artifact
from recall.contracts.enums import ScanRunEventCode, ScanRunState
from recall.contracts.payloads.lifecycle import ReviewTaskPayload
from recall.contracts.payloads.policy import PolicyDecisionPayload
from recall.controller.lifecycle import require_transition

from .models import ReviewTaskRecord, ScanRunEventRecord, ScanRunRecord, WatchCaseRecord
from .producers import PRODUCER_REGISTRY


class FirestoreTerminalMixin:
    def commit_terminal(
        self,
        run_id: str,
        *,
        expected_version: int,
        lease_epoch: int,
        target_state: str,
        event_code: ScanRunEventCode,
        policy_decision: Mapping[str, Any] | None,
        failure_receipt: Mapping[str, Any] | None,
        review_task: Mapping[str, Any] | None,
        watch_case_update: WatchCaseRecord | None,
        now: datetime,
        terminal_artifacts: Sequence[Mapping[str, Any]] = (),
    ) -> tuple[ScanRunRecord, ReviewTaskRecord | None]:
        policy = (
            None
            if policy_decision is None
            else parse_artifact(
                policy_decision, authorized_producers=PRODUCER_REGISTRY
            )
        )
        failure = (
            None
            if failure_receipt is None
            else parse_artifact(
                failure_receipt, authorized_producers=PRODUCER_REGISTRY
            )
        )
        task = (
            None
            if review_task is None
            else parse_artifact(review_task, authorized_producers=PRODUCER_REGISTRY)
        )
        extras = tuple(
            parse_artifact(item, authorized_producers=PRODUCER_REGISTRY)
            for item in terminal_artifacts
        )
        target = ScanRunState(target_state)
        closed_event = ScanRunEventCode(event_code)
        if target is ScanRunState.HALTED:
            if policy is not None or failure is None or task is not None:
                raise ContractError("contract_terminal_authority_invalid", target.value)
        else:
            if policy is None or failure is not None:
                raise ContractError("contract_terminal_authority_invalid", target.value)
            if not isinstance(policy.payload, PolicyDecisionPayload):
                raise ContractError("contract_schema_invalid", "PolicyDecision")
            if policy.payload.outcome.value != target.value:
                raise ContractError("contract_value_invalid", "PolicyDecision.outcome")
            if (target is ScanRunState.REVIEW_REQUIRED) is not (task is not None):
                raise ContractError("contract_value_invalid", "ReviewTask.presence")
        if task is not None and not isinstance(task.payload, ReviewTaskPayload):
            raise ContractError("contract_schema_invalid", "ReviewTask")
        for artifact in extras:
            if (
                artifact.schema_name != "AgentExecutionReceipt"
                or artifact.run_id != run_id
                or artifact.payload.execution_status.value != "FAILED"
            ):
                raise ContractError(
                    "contract_terminal_authority_invalid", "terminal_artifacts"
                )

        run_reference = self._collection("scan_runs").document(run_id)
        event_id = str(uuid5(UUID(run_id), f"scan-run-event:{expected_version + 1}"))
        event_reference = self._collection("scan_run_events").document(event_id)
        transaction = self._client.transaction()

        @firestore.transactional
        def commit(txn: Any) -> tuple[dict[str, object], dict[str, object] | None]:
            snapshot = run_reference.get(transaction=txn)
            if not snapshot.exists:
                raise ContractError("stale_write_rejected", run_id)
            current = ScanRunRecord.from_wire(snapshot.to_dict())
            if (
                current.version != expected_version
                or current.lease_epoch != lease_epoch
            ):
                raise ContractError("stale_write_rejected", run_id)
            if (
                target is not ScanRunState.HALTED
                and current.state is not ScanRunState.POLICY_EVALUATION
            ):
                raise ContractError("contract_transition_invalid", current.state.value)
            require_transition(current.state, closed_event, target)
            if current.lease_expires_at is not None and now >= current.lease_expires_at:
                raise ContractError("lease_expired", run_id)
            case_reference = None
            if watch_case_update is not None:
                case_reference = self._collection("watch_cases").document(
                    watch_case_update.watch_case_id
                )
                case_snapshot = case_reference.get(transaction=txn)
                if not case_snapshot.exists:
                    raise ContractError(
                        "stale_write_rejected", watch_case_update.watch_case_id
                    )
                current_case = WatchCaseRecord.from_wire(case_snapshot.to_dict())
                if (
                    current_case.version + 1 != watch_case_update.version
                    or current_case.artifact_id != watch_case_update.artifact_id
                ):
                    raise ContractError(
                        "stale_write_rejected", watch_case_update.watch_case_id
                    )
            task_record: ReviewTaskRecord | None = None
            for artifact, wire in (
                (policy, policy_decision),
                (failure, failure_receipt),
                (task, review_task),
                *zip(extras, terminal_artifacts, strict=True),
            ):
                if artifact is not None and wire is not None:
                    reference = self._collection("artifacts").document(
                        artifact.artifact_id
                    )
                    txn.create(reference, dict(wire))
            if task is not None:
                payload = task.payload
                assert isinstance(payload, ReviewTaskPayload)
                task_record = ReviewTaskRecord(
                    task_id=task.artifact_id,
                    run_id=run_id,
                    watch_case_id=payload.watch_case_id,
                    policy_decision_id=payload.trigger_decision_id,
                    deduplication_key=payload.deduplication_key,
                    artifact_id=task.artifact_id,
                    state=payload.state.value,
                    delivery_state="PENDING",
                    created_at=now,
                )
                txn.create(
                    self._collection("review_tasks").document(task_record.task_id),
                    task_record.to_wire(),
                )
            version = current.version + 1
            updated = ScanRunRecord(
                run_id=run_id,
                state=target,
                version=version,
                lease_epoch=lease_epoch,
                lease_expires_at=current.lease_expires_at,
                updated_at=now,
                scan_run_artifact_id=current.scan_run_artifact_id,
                terminal_policy_decision_id=(
                    None if policy is None else policy.artifact_id
                ),
                failure_receipt_ids=(
                    current.failure_receipt_ids
                    if failure is None
                    else (*current.failure_receipt_ids, failure.artifact_id)
                ),
                last_repeated_state_hash=current.last_repeated_state_hash,
                repeated_state_count=current.repeated_state_count,
            )
            event = ScanRunEventRecord(
                event_id=event_id,
                run_id=run_id,
                sequence=version,
                from_state=current.state,
                to_state=target,
                event_code=closed_event,
                agent_id=None,
                lease_epoch=lease_epoch,
                created_at=now,
            )
            txn.set(run_reference, updated.to_wire())
            if case_reference is not None and watch_case_update is not None:
                txn.set(case_reference, watch_case_update.to_wire())
            txn.create(event_reference, event.to_wire())
            return (
                updated.to_wire(),
                None if task_record is None else task_record.to_wire(),
            )

        run_wire, task_wire = commit(transaction)
        return (
            ScanRunRecord.from_wire(run_wire),
            None if task_wire is None else ReviewTaskRecord.from_wire(task_wire),
        )

    def list_review_tasks(self, run_id: str) -> tuple[ReviewTaskRecord, ...]:
        query = self._collection("review_tasks").where(
            filter=FieldFilter("run_id", "==", run_id)
        )
        return tuple(
            sorted(
                (ReviewTaskRecord.from_wire(snapshot.to_dict()) for snapshot in query.stream()),
                key=lambda task: task.task_id,
            )
        )

    def mark_task_delivered(self, task_id: str) -> ReviewTaskRecord:
        reference = self._collection("review_tasks").document(task_id)
        transaction = self._client.transaction()

        @firestore.transactional
        def deliver(txn: Any) -> dict[str, object]:
            snapshot = reference.get(transaction=txn)
            if not snapshot.exists:
                raise ContractError("contract_required_value_missing", "review_task")
            current = ReviewTaskRecord.from_wire(snapshot.to_dict())
            if current.delivery_state == "DELIVERED":
                return current.to_wire()
            wire = current.to_wire()
            wire["delivery_state"] = "DELIVERED"
            txn.set(reference, wire)
            return wire

        return ReviewTaskRecord.from_wire(deliver(transaction))

    def get_watch_case(self, watch_case_id: str) -> WatchCaseRecord | None:
        snapshot = self._collection("watch_cases").document(watch_case_id).get()
        return (
            WatchCaseRecord.from_wire(snapshot.to_dict())
            if snapshot.exists
            else None
        )

    def list_watch_cases(self) -> tuple[WatchCaseRecord, ...]:
        values = []
        for snapshot in self._collection("watch_cases").stream():
            record = WatchCaseRecord.from_wire(snapshot.to_dict())
            if str(snapshot.id) != record.watch_case_id:
                raise ContractError(
                    "ledger_integrity_failed", "watch_case_document_id"
                )
            values.append(record)
        return tuple(sorted(values, key=lambda item: item.watch_case_id))

    def observe_state_hash(
        self,
        run_id: str,
        *,
        expected_version: int,
        lease_epoch: int,
        state_hash: str,
        failure_receipt: Mapping[str, Any],
        now: datetime,
    ) -> tuple[ScanRunRecord, bool]:
        failure = parse_artifact(
            failure_receipt, authorized_producers=PRODUCER_REGISTRY
        )
        if failure.schema_name != "FailureReceipt":
            raise ContractError("contract_schema_invalid", "FailureReceipt")
        run_reference = self._collection("scan_runs").document(run_id)
        failure_reference = self._collection("artifacts").document(
            failure.artifact_id
        )
        event_id = str(uuid5(UUID(run_id), f"scan-run-event:{expected_version + 1}"))
        event_reference = self._collection("scan_run_events").document(event_id)
        transaction = self._client.transaction()

        @firestore.transactional
        def observe(txn: Any) -> tuple[dict[str, object], bool]:
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
            if current.last_repeated_state_hash != state_hash:
                target = current.state
                event_code = ScanRunEventCode.STATE_HASH_OBSERVED
                require_transition(current.state, event_code, target)
                version = current.version + 1
                observed = ScanRunRecord(
                    run_id=run_id,
                    state=target,
                    version=version,
                    lease_epoch=lease_epoch,
                    lease_expires_at=current.lease_expires_at,
                    updated_at=now,
                    scan_run_artifact_id=current.scan_run_artifact_id,
                    terminal_policy_decision_id=current.terminal_policy_decision_id,
                    failure_receipt_ids=current.failure_receipt_ids,
                    last_repeated_state_hash=state_hash,
                    repeated_state_count=1,
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
                txn.set(run_reference, observed.to_wire())
                txn.create(event_reference, event.to_wire())
                return observed.to_wire(), False

            target = ScanRunState.POLICY_EVALUATION
            event_code = ScanRunEventCode.LOOP_DETECTED
            require_transition(current.state, event_code, target)
            version = current.version + 1
            updated = ScanRunRecord(
                run_id=run_id,
                state=target,
                version=version,
                lease_epoch=lease_epoch,
                lease_expires_at=current.lease_expires_at,
                updated_at=now,
                scan_run_artifact_id=current.scan_run_artifact_id,
                terminal_policy_decision_id=current.terminal_policy_decision_id,
                failure_receipt_ids=(
                    *current.failure_receipt_ids,
                    failure.artifact_id,
                ),
                last_repeated_state_hash=state_hash,
                repeated_state_count=current.repeated_state_count + 1,
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
            txn.create(failure_reference, dict(failure_receipt))
            txn.set(run_reference, updated.to_wire())
            txn.create(event_reference, event.to_wire())
            return updated.to_wire(), True

        wire, looped = observe(transaction)
        return ScanRunRecord.from_wire(wire), looped
