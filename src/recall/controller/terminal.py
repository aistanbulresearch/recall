from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from uuid import UUID, uuid5

from recall.contracts import ArtifactStatus, ContractError, DataMode, build_artifact
from recall.contracts.enums import (
    PolicyOutcome,
    ScanRunEventCode,
    ScanRunState,
    WatchCaseState,
)
from recall.contracts.payloads.policy import PolicyDecisionPayload
from recall.controller.facts import build_policy_input_facts
from recall.controller.failure_artifacts import build_technical_halt_failure
from recall.controller.hashes import review_deduplication_key
from recall.ledger.models import ReviewTaskRecord, ScanRunRecord, WatchCaseRecord
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.policy import POLICY_VERSION

from .results import TerminalCommitResult


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class ControllerTerminalMixin:
    _ledger: LedgerPort
    _policy_evaluator: Callable[[Mapping[str, object], str], object]
    _facts_builder: Callable[[LedgerPort, str], Mapping[str, object]] | None
    _policy_call_count: int

    def evaluate_and_commit(
        self,
        run_id: str,
        *,
        verified_delta_hash: str,
        now: datetime,
        audit_receipt_id: str | None = None,
        claim_ids: Sequence[str] = (),
        verified_snapshot_id: str | None = None,
        verified_source_cursors: Mapping[str, str] | None = None,
        pending_observation_hashes: Sequence[str] = (),
    ) -> TerminalCommitResult:
        current = self._ledger.get_scan_run(run_id)
        if current is None:
            raise ContractError("stale_write_rejected", run_id)
        if current.state in {
            ScanRunState.NO_ACTION,
            ScanRunState.ABSTAIN,
            ScanRunState.REVIEW_REQUIRED,
            ScanRunState.HALTED,
        }:
            tasks = self._ledger.list_review_tasks(run_id)
            return TerminalCommitResult(
                current,
                current.terminal_policy_decision_id,
                None if not tasks else tasks[0].task_id,
                True,
            )
        if current.state is not ScanRunState.POLICY_EVALUATION:
            raise ContractError("contract_transition_invalid", current.state.value)
        scan_artifact = self._scan_run_artifact(current)
        # HALTED classification table:
        # facts ContractError -> ledger_integrity_failed
        # facts non-contract exception or policy input ContractError -> controller_failed
        # invalid/failed/timed-out PolicyDecision production -> policy_unavailable
        try:
            builder = self._facts_builder or build_policy_input_facts
            input_facts = builder(self._ledger, run_id)
        except ContractError:
            return self._commit_technical_halt(
                current=current,
                scan_artifact=scan_artifact,
                failure_code="ledger_integrity_failed",
                pending_observation_hashes=pending_observation_hashes,
                now=now,
            )
        except Exception:
            return self._commit_technical_halt(
                current=current,
                scan_artifact=scan_artifact,
                failure_code="controller_failed",
                pending_observation_hashes=pending_observation_hashes,
                now=now,
            )
        try:
            self._policy_call_count += 1
            decision = self._policy_evaluator(input_facts, POLICY_VERSION)
        except ContractError:
            return self._commit_technical_halt(
                current=current,
                scan_artifact=scan_artifact,
                failure_code="controller_failed",
                pending_observation_hashes=pending_observation_hashes,
                now=now,
            )
        except Exception:
            return self._commit_technical_halt(
                current=current,
                scan_artifact=scan_artifact,
                failure_code="policy_unavailable",
                pending_observation_hashes=pending_observation_hashes,
                now=now,
            )
        if not isinstance(decision, PolicyDecisionPayload):
            return self._commit_technical_halt(
                current=current,
                scan_artifact=scan_artifact,
                failure_code="policy_unavailable",
                pending_observation_hashes=pending_observation_hashes,
                now=now,
            )
        try:
            decision_wire = self._build_policy_decision(
                run_id=run_id,
                case_id=str(scan_artifact["case_id"]),
                scan_artifact_id=str(current.scan_run_artifact_id),
                data_mode=DataMode(scan_artifact["data_mode"]),
                decision=decision,
                now=now,
            )
        except Exception:
            return self._commit_technical_halt(
                current=current,
                scan_artifact=scan_artifact,
                failure_code="policy_unavailable",
                pending_observation_hashes=pending_observation_hashes,
                now=now,
            )

        target = ScanRunState(decision.outcome.value)
        event_code = {
            PolicyOutcome.NO_ACTION: ScanRunEventCode.POLICY_NO_ACTION,
            PolicyOutcome.ABSTAIN: ScanRunEventCode.POLICY_ABSTAIN,
            PolicyOutcome.REVIEW_REQUIRED: ScanRunEventCode.POLICY_REVIEW_REQUIRED,
        }[decision.outcome]
        task_wire: dict[str, object] | None = None
        if target is ScanRunState.REVIEW_REQUIRED:
            if audit_receipt_id is None or not claim_ids:
                raise ContractError(
                    "contract_required_value_missing", "review_task_inputs"
                )
            task_wire = self._build_review_task(
                run_id=run_id,
                case_id=str(scan_artifact["case_id"]),
                decision_id=str(decision_wire["artifact_id"]),
                verified_delta_hash=verified_delta_hash,
                audit_receipt_id=audit_receipt_id,
                claim_ids=claim_ids,
                data_mode=DataMode(scan_artifact["data_mode"]),
                now=now,
            )
        task_id = None if task_wire is None else str(task_wire["artifact_id"])
        try:
            watch_case_update = self._build_watch_case_update(
                case_id=str(scan_artifact["case_id"]),
                target=target,
                reason_codes=decision.reason_codes,
                task_id=task_id,
                verified_snapshot_id=verified_snapshot_id,
                verified_source_cursors=verified_source_cursors,
                pending_observation_hashes=pending_observation_hashes,
                now=now,
            )
        except ContractError:
            return self._commit_technical_halt(
                current=current,
                scan_artifact=scan_artifact,
                failure_code="ledger_integrity_failed",
                pending_observation_hashes=pending_observation_hashes,
                now=now,
            )
        except Exception:
            return self._commit_technical_halt(
                current=current,
                scan_artifact=scan_artifact,
                failure_code="controller_failed",
                pending_observation_hashes=pending_observation_hashes,
                now=now,
            )
        record, task = self._ledger.commit_terminal(
            run_id,
            expected_version=current.version,
            lease_epoch=current.lease_epoch,
            target_state=target.value,
            event_code=event_code,
            policy_decision=decision_wire,
            failure_receipt=None,
            review_task=task_wire,
            watch_case_update=watch_case_update,
            now=now,
        )
        return TerminalCommitResult(
            record,
            str(decision_wire["artifact_id"]),
            None if task is None else task.task_id,
            False,
        )

    def deliver_task_outbox(self, task_id: str) -> ReviewTaskRecord:
        return self._ledger.mark_task_delivered(task_id)

    def _scan_run_artifact(self, current: ScanRunRecord) -> dict[str, object]:
        if current.scan_run_artifact_id is None:
            raise ContractError("ledger_integrity_failed", "scan_run_artifact_id")
        artifact = self._ledger.get_artifact(current.scan_run_artifact_id)
        if artifact is None or artifact.get("schema_name") != "ScanRun":
            raise ContractError("ledger_integrity_failed", "ScanRun")
        return artifact

    def _build_policy_decision(
        self,
        *,
        run_id: str,
        case_id: str,
        scan_artifact_id: str,
        data_mode: DataMode,
        decision: PolicyDecisionPayload,
        now: datetime,
    ) -> dict[str, object]:
        decision_id = str(uuid5(UUID(run_id), "policy-decision"))
        return build_artifact(
            schema_name="PolicyDecision",
            schema_version="2.0.0",
            artifact_id=decision_id,
            case_id=case_id,
            run_id=run_id,
            producer={
                "component": "deterministic-policy-gate",
                "version": POLICY_VERSION,
                "identity": "policy-gate",
            },
            created_at=_timestamp(now),
            input_artifact_ids=(scan_artifact_id,),
            data_mode=data_mode,
            status=ArtifactStatus.VALID,
            payload=decision.to_wire(),
            authorized_producers=PRODUCER_REGISTRY,
        )

    def _build_review_task(
        self,
        *,
        run_id: str,
        case_id: str,
        decision_id: str,
        verified_delta_hash: str,
        audit_receipt_id: str,
        claim_ids: Sequence[str],
        data_mode: DataMode,
        now: datetime,
    ) -> dict[str, object]:
        deduplication_key = review_deduplication_key(
            case_id=case_id,
            policy_decision_id=decision_id,
            verified_delta_hash=verified_delta_hash,
        )
        task_id = str(uuid5(UUID(run_id), f"review-task:{deduplication_key}"))
        return build_artifact(
            schema_name="ReviewTask",
            schema_version="1.0.0",
            artifact_id=task_id,
            case_id=case_id,
            run_id=run_id,
            producer={
                "component": "controller-outbox",
                "version": "0.1.0",
                "identity": "controller",
            },
            created_at=_timestamp(now),
            input_artifact_ids=tuple(sorted((audit_receipt_id, decision_id))),
            data_mode=data_mode,
            status=ArtifactStatus.VALID,
            payload={
                "watch_case_id": case_id,
                "trigger_decision_id": decision_id,
                "state": "OPEN",
                "priority_band": "STANDARD",
                "claim_ids": sorted(set(claim_ids)),
                "audit_receipt_id": audit_receipt_id,
                "simulation": True,
                "deduplication_key": deduplication_key,
            },
            authorized_producers=PRODUCER_REGISTRY,
        )

    def _commit_technical_halt(
        self,
        *,
        current: ScanRunRecord,
        scan_artifact: Mapping[str, object],
        failure_code: str,
        pending_observation_hashes: Sequence[str],
        now: datetime,
    ) -> TerminalCommitResult:
        failure = build_technical_halt_failure(
            current=current,
            scan_artifact=scan_artifact,
            failure_code=failure_code,
            now=now,
        )
        try:
            watch_case_update = self._build_watch_case_update(
                case_id=str(scan_artifact["case_id"]),
                target=ScanRunState.HALTED,
                reason_codes=(failure_code,),
                task_id=None,
                verified_snapshot_id=None,
                verified_source_cursors=None,
                pending_observation_hashes=pending_observation_hashes,
                now=now,
            )
        except ContractError as exc:
            if exc.code != "ledger_integrity_failed":
                raise
            # A missing WatchCase is itself the ledger-integrity cause. The run
            # still records HALTED and its FailureReceipt atomically; no semantic
            # terminal or cursor update is fabricated.
            watch_case_update = None
        record, _task = self._ledger.commit_terminal(
            current.run_id,
            expected_version=current.version,
            lease_epoch=current.lease_epoch,
            target_state=ScanRunState.HALTED.value,
            event_code=ScanRunEventCode.TECHNICAL_HALTED,
            policy_decision=None,
            failure_receipt=failure,
            review_task=None,
            watch_case_update=watch_case_update,
            now=now,
        )
        return TerminalCommitResult(record, None, None, False)

    def _build_watch_case_update(
        self,
        *,
        case_id: str,
        target: ScanRunState,
        reason_codes: Sequence[str],
        task_id: str | None,
        verified_snapshot_id: str | None,
        verified_source_cursors: Mapping[str, str] | None,
        pending_observation_hashes: Sequence[str],
        now: datetime,
    ) -> WatchCaseRecord | None:
        current = self._ledger.get_watch_case(case_id)
        if current is None:
            raise ContractError("ledger_integrity_failed", "WatchCase")
        pending = tuple(
            sorted(
                set(current.pending_observation_hashes)
                | set(pending_observation_hashes)
            )
        )
        if target in {ScanRunState.NO_ACTION, ScanRunState.REVIEW_REQUIRED}:
            if verified_snapshot_id is None or verified_source_cursors is None:
                raise ContractError(
                    "contract_required_value_missing", "verified_cursor_inputs"
                )
            cursors = tuple(sorted(verified_source_cursors.items()))
            snapshot_id = verified_snapshot_id
            pending = ()
            attention = ()
        else:
            cursors = current.source_cursors
            snapshot_id = current.last_verified_snapshot_id
            attention = tuple(sorted(set(reason_codes)))
        if target is ScanRunState.REVIEW_REQUIRED:
            state = WatchCaseState.AWAITING_HUMAN
            open_task_id = task_id
            next_scan_at = None
        elif target is ScanRunState.HALTED:
            state = WatchCaseState.ATTENTION_REQUIRED
            open_task_id = None
            next_scan_at = None
        else:
            state = WatchCaseState.ACTIVE
            open_task_id = None
            next_scan_at = current.next_scan_at
        return WatchCaseRecord(
            watch_case_id=current.watch_case_id,
            artifact_id=current.artifact_id,
            state=state,
            version=current.version + 1,
            source_cursors=cursors,
            last_verified_snapshot_id=snapshot_id,
            pending_observation_hashes=pending,
            open_review_task_id=open_task_id,
            attention_reason_codes=attention,
            next_scan_at=next_scan_at,
            updated_at=now,
        )
