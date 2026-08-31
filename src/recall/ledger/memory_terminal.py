from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import UUID, uuid5

from recall.contracts import ContractError, parse_artifact
from recall.contracts.enums import ScanRunEventCode, ScanRunState
from recall.contracts.payloads.lifecycle import ReviewTaskPayload
from recall.contracts.payloads.policy import PolicyDecisionPayload
from recall.controller.lifecycle import require_transition

from .models import ReviewTaskRecord, ScanRunEventRecord, ScanRunRecord, WatchCaseRecord
from .producers import PRODUCER_REGISTRY


class InMemoryTerminalMixin:
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
        policy = self._parse_optional(policy_decision)
        failure = self._parse_optional(failure_receipt)
        task = self._parse_optional(review_task)
        extras = tuple(self._parse_optional(item) for item in terminal_artifacts)
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
                artifact is None
                or artifact.schema_name != "AgentExecutionReceipt"
                or artifact.run_id != run_id
                or artifact.payload.execution_status.value != "FAILED"
            ):
                raise ContractError(
                    "contract_terminal_authority_invalid", "terminal_artifacts"
                )

        with self._lock:
            current = self._scan_runs.get(run_id)
            if (
                current is None
                or current.version != expected_version
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
            self._validate_watch_case_update(watch_case_update)
            for artifact in (policy, failure, task, *extras):
                if artifact is None:
                    continue
                existing = self._artifacts.get(artifact.artifact_id)
                if (
                    existing is not None
                    and existing["content_hash"] != artifact.content_hash
                ):
                    raise ContractError(
                        "artifact_integrity_failed", artifact.artifact_id
                    )
            artifacts_and_wires = tuple(
                (artifact, wire)
                for artifact, wire in (
                    (policy, policy_decision),
                    (failure, failure_receipt),
                    (task, review_task),
                    *zip(extras, terminal_artifacts, strict=True),
                )
                if artifact is not None and wire is not None
            )
            # All validation is complete. Store the terminal artifacts directly
            # under the same lock as the pointer/event mutation so a failed
            # AgentExecutionReceipt can never be separated from HALTED.
            for artifact, wire in artifacts_and_wires:
                if artifact.artifact_id not in self._artifacts:
                    self._artifacts[artifact.artifact_id] = deepcopy(dict(wire))
            task_record = self._store_review_task(task, run_id, now)
            version = current.version + 1
            updated = replace(
                current,
                state=target,
                version=version,
                updated_at=now,
                terminal_policy_decision_id=(
                    None if policy is None else policy.artifact_id
                ),
                failure_receipt_ids=(
                    current.failure_receipt_ids
                    if failure is None
                    else (*current.failure_receipt_ids, failure.artifact_id)
                ),
            )
            event = ScanRunEventRecord(
                event_id=str(uuid5(UUID(run_id), f"scan-run-event:{version}")),
                run_id=run_id,
                sequence=version,
                from_state=current.state,
                to_state=target,
                event_code=closed_event,
                agent_id=None,
                lease_epoch=lease_epoch,
                created_at=now,
            )
            self._scan_runs[run_id] = updated
            self._scan_run_events[event.event_id] = event
            if watch_case_update is not None:
                self._watch_cases[watch_case_update.watch_case_id] = watch_case_update
            return updated, task_record

    def list_review_tasks(self, run_id: str) -> tuple[ReviewTaskRecord, ...]:
        return tuple(
            sorted(
                (task for task in self._review_tasks.values() if task.run_id == run_id),
                key=lambda task: task.task_id,
            )
        )

    def mark_task_delivered(self, task_id: str) -> ReviewTaskRecord:
        with self._lock:
            current = self._review_tasks.get(task_id)
            if current is None:
                raise ContractError("contract_required_value_missing", "review_task")
            if current.delivery_state == "DELIVERED":
                return current
            delivered = replace(current, delivery_state="DELIVERED")
            self._review_tasks[task_id] = delivered
            return delivered

    def get_watch_case(self, watch_case_id: str) -> WatchCaseRecord | None:
        return self._watch_cases.get(watch_case_id)

    def list_watch_cases(self) -> tuple[WatchCaseRecord, ...]:
        return tuple(
            sorted(self._watch_cases.values(), key=lambda item: item.watch_case_id)
        )

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
        with self._lock:
            current = self._scan_runs.get(run_id)
            if (
                current is None
                or current.version != expected_version
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
                observed = replace(
                    current,
                    version=version,
                    last_repeated_state_hash=state_hash,
                    repeated_state_count=1,
                    updated_at=now,
                )
                event = ScanRunEventRecord(
                    event_id=str(uuid5(UUID(run_id), f"scan-run-event:{version}")),
                    run_id=run_id,
                    sequence=version,
                    from_state=current.state,
                    to_state=target,
                    event_code=event_code,
                    agent_id=None,
                    lease_epoch=lease_epoch,
                    created_at=now,
                )
                self._scan_runs[run_id] = observed
                self._scan_run_events[event.event_id] = event
                return observed, False

            target = ScanRunState.POLICY_EVALUATION
            event_code = ScanRunEventCode.LOOP_DETECTED
            require_transition(current.state, event_code, target)
            self.append_artifact(failure_receipt)
            version = current.version + 1
            updated = replace(
                current,
                state=target,
                version=version,
                updated_at=now,
                failure_receipt_ids=(*current.failure_receipt_ids, failure.artifact_id),
                repeated_state_count=current.repeated_state_count + 1,
            )
            event = ScanRunEventRecord(
                event_id=str(uuid5(UUID(run_id), f"scan-run-event:{version}")),
                run_id=run_id,
                sequence=version,
                from_state=current.state,
                to_state=target,
                event_code=event_code,
                agent_id=None,
                lease_epoch=lease_epoch,
                created_at=now,
            )
            self._scan_runs[run_id] = updated
            self._scan_run_events[event.event_id] = event
            return updated, True

    @staticmethod
    def _parse_optional(value: Mapping[str, Any] | None):
        return (
            None
            if value is None
            else parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
        )

    def _validate_watch_case_update(
        self, update: WatchCaseRecord | None
    ) -> None:
        if update is None:
            return
        current = self._watch_cases.get(update.watch_case_id)
        if (
            current is None
            or current.version + 1 != update.version
            or current.artifact_id != update.artifact_id
        ):
            raise ContractError("stale_write_rejected", update.watch_case_id)

    def _store_review_task(self, task, run_id: str, now: datetime):
        if task is None:
            return None
        payload = task.payload
        assert isinstance(payload, ReviewTaskPayload)
        record = ReviewTaskRecord(
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
        self._review_tasks[record.task_id] = record
        return record
