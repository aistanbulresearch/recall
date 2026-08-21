from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from uuid import UUID, uuid5

from recall.contracts import ArtifactStatus, ContractError, DataMode, build_artifact
from recall.controller.hashes import repeated_state_hash
from recall.ledger.models import ScanRunRecord
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY

from .results import GuardedStepResult


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class ControllerGuardMixin:
    _ledger: LedgerPort

    def run_guarded_step(
        self,
        run_id: str,
        *,
        state_context: Mapping[str, object],
        now: datetime,
        step: Callable[[], object],
    ) -> GuardedStepResult:
        current = self._ledger.get_scan_run(run_id)
        if current is None:
            raise ContractError("stale_write_rejected", run_id)
        state_hash = repeated_state_hash(state_context)
        failure = self._build_loop_failure(
            current=current,
            state_hash=state_hash,
            now=now,
        )
        record, looped = self._ledger.observe_state_hash(
            run_id,
            expected_version=current.version,
            lease_epoch=current.lease_epoch,
            state_hash=state_hash,
            failure_receipt=failure,
            now=now,
        )
        if looped:
            return GuardedStepResult(record, True, None)
        return GuardedStepResult(record, False, step())

    def _build_loop_failure(
        self,
        *,
        current: ScanRunRecord,
        state_hash: str,
        now: datetime,
    ) -> dict[str, object]:
        scan_artifact = self._guard_scan_run_artifact(current)
        failure_id = str(uuid5(UUID(current.run_id), f"loop-detected:{state_hash}"))
        return build_artifact(
            schema_name="FailureReceipt",
            schema_version="1.0.0",
            artifact_id=failure_id,
            case_id=str(scan_artifact["case_id"]),
            run_id=current.run_id,
            producer={
                "component": "workflow-controller",
                "version": "0.1.0",
                "identity": "controller-failure-recorder",
            },
            created_at=_timestamp(now),
            input_artifact_ids=(str(current.scan_run_artifact_id),),
            data_mode=DataMode(scan_artifact["data_mode"]),
            status=ArtifactStatus.REJECTED,
            payload={
                "failure_code": "loop_detected",
                "stage": current.state.value,
                "retryable": False,
                "attempt": 2,
                "budget_state": "WITHIN_LIMIT",
                "details": {
                    "hop_count": 2,
                    "repeated_state_hash": state_hash,
                },
                "related_artifact_ids": [str(current.scan_run_artifact_id)],
                "safe_terminal": "POLICY_BOUND",
                "operator_action": "evaluate_loop_failure_under_policy",
            },
            authorized_producers=PRODUCER_REGISTRY,
        )

    def _guard_scan_run_artifact(
        self, current: ScanRunRecord
    ) -> dict[str, object]:
        if current.scan_run_artifact_id is None:
            raise ContractError("ledger_integrity_failed", "scan_run_artifact_id")
        artifact = self._ledger.get_artifact(current.scan_run_artifact_id)
        if artifact is None or artifact.get("schema_name") != "ScanRun":
            raise ContractError("ledger_integrity_failed", "ScanRun")
        return artifact
