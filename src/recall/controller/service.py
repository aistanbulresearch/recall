from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from recall.contracts import (
    ArtifactStatus,
    ContractError,
    DataMode,
    ExecutionProfile,
    build_artifact,
)
from recall.contracts.enums import (
    ScanRunEventCode,
    ScanRunState,
    WatchCaseState,
)
from recall.controller.hashes import scan_idempotency_key
from recall.controller.lifecycle import transition_target
from recall.ledger.models import ScanRunRecord
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.policy import POLICY_VERSION, evaluate

from .guard import ControllerGuardMixin
from .results import CreateRunResult, CreateWatchCaseResult
from .terminal import ControllerTerminalMixin

def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


PolicyEvaluator = Callable[[Mapping[str, object], str], object]
FactsBuilder = Callable[[LedgerPort, str], Mapping[str, object]]


class Controller(ControllerGuardMixin, ControllerTerminalMixin):
    def __init__(
        self,
        ledger: LedgerPort,
        *,
        policy_evaluator: PolicyEvaluator = evaluate,
        facts_builder: FactsBuilder | None = None,
    ) -> None:
        self._ledger = ledger
        self._policy_evaluator = policy_evaluator
        self._facts_builder = facts_builder
        self._policy_call_count = 0

    @property
    def policy_call_count(self) -> int:
        return self._policy_call_count

    def create_run(
        self,
        *,
        watch_case_id: str,
        source_cursors: Mapping[str, str],
        schedule_epoch: str,
        data_mode: DataMode,
        privacy_receipt_id: str,
        expected_watch_case_version: int,
        triggered_at: datetime,
        budget_snapshot: Mapping[str, object],
        trace_id: str,
        deadline_at: str,
        now: datetime,
        execution_profile: ExecutionProfile | None = None,
    ) -> CreateRunResult:
        key = scan_idempotency_key(
            watch_case_id=watch_case_id,
            source_cursors=source_cursors,
            schedule_epoch=schedule_epoch,
            data_mode=data_mode.value,
        )
        run_id = str(uuid5(NAMESPACE_URL, f"recall:scan-run:{key}"))
        watch_case = self._ledger.get_watch_case(watch_case_id)
        if watch_case is None:
            raise ContractError("stale_write_rejected", watch_case_id)
        artifact_id = str(uuid5(UUID(run_id), "scan-run-artifact"))
        payload = {
            "watch_case_id": watch_case_id,
            "state": ScanRunState.CREATED.value,
            "scheduled_for": schedule_epoch,
            "attempt": 0,
            "lease_epoch": 0,
            "deadline_at": deadline_at,
            "budget_snapshot": dict(budget_snapshot),
            "idempotency_key": key,
            "trace_id": trace_id,
            "terminal_policy_decision_id": None,
            "failure_receipt_ids": [],
        }
        if execution_profile is not None:
            payload["execution_profile"] = execution_profile.value
        wire = build_artifact(
            schema_name="ScanRun",
            schema_version="1.1.0" if execution_profile is not None else "1.0.0",
            artifact_id=artifact_id,
            case_id=watch_case_id,
            run_id=run_id,
            producer={
                "component": "workflow-controller",
                "version": "0.1.0",
                "identity": "controller",
            },
            created_at=_timestamp(triggered_at),
            input_artifact_ids=tuple(
                sorted((privacy_receipt_id, watch_case.artifact_id))
            ),
            data_mode=data_mode,
            status=ArtifactStatus.VALID,
            payload=payload,
            authorized_producers=PRODUCER_REGISTRY,
        )
        record, created = self._ledger.create_scan_run(
            wire,
            expected_watch_case_version=expected_watch_case_version,
            expected_source_cursors=source_cursors,
            triggered_at=triggered_at,
            now=now,
        )
        return CreateRunResult(record, created)

    def create_watch_case(
        self,
        *,
        watch_case_id: str,
        tenant_id: str,
        region: str,
        privacy_receipt_id: str,
        cloud_bound_payload: Mapping[str, object],
        data_mode: DataMode,
        source_cursors: Mapping[str, str],
        pending_observation_hashes: Sequence[str],
        next_scan_at: str,
        now: datetime,
    ) -> CreateWatchCaseResult:
        artifact_id = str(uuid5(UUID(watch_case_id), "watch-case-artifact"))
        wire = build_artifact(
            schema_name="WatchCase",
            schema_version="2.0.0",
            artifact_id=artifact_id,
            case_id=watch_case_id,
            run_id=None,
            producer={
                "component": "workflow-controller",
                "version": "0.1.0",
                "identity": "controller",
            },
            created_at=_timestamp(now),
            input_artifact_ids=(privacy_receipt_id,),
            data_mode=data_mode,
            status=ArtifactStatus.VALID,
            payload={
                "tenant_id": tenant_id,
                "region": region,
                "state": WatchCaseState.ACTIVE.value,
                "monitoring_started_at": _timestamp(now),
                "monitoring_policy": {"policy_version": POLICY_VERSION},
                "next_scan_at": next_scan_at,
                "source_cursors": dict(sorted(source_cursors.items())),
                "last_verified_snapshot_id": None,
                "last_verified_scan": {"run_id": None, "completed_at": None},
                "pending_observation_hashes": sorted(
                    set(pending_observation_hashes)
                ),
                "attention_marker": None,
                "open_review_task_id": None,
                "retention_policy": {"class": "contest-synthetic"},
            },
            authorized_producers=PRODUCER_REGISTRY,
        )
        record, created = self._ledger.create_watch_case(
            wire, cloud_bound_payload=cloud_bound_payload, now=now
        )
        return CreateWatchCaseResult(record, created)

    def transition(
        self,
        run_id: str,
        *,
        expected_version: int,
        lease_epoch: int,
        event_code: ScanRunEventCode,
        now: datetime,
    ) -> ScanRunRecord:
        current = self._ledger.get_scan_run(run_id)
        if current is None:
            raise ContractError("stale_write_rejected", run_id)
        if current.version != expected_version or current.lease_epoch != lease_epoch:
            raise ContractError("stale_write_rejected", run_id)
        target = transition_target(current.state, event_code)
        return self._ledger.transition_with_cas(
            run_id,
            expected_version=expected_version,
            lease_epoch=lease_epoch,
            to_state=target.value,
            event_code=event_code,
            now=now,
        )

    def acquire_lease(
        self,
        run_id: str,
        *,
        expected_version: int,
        new_epoch: int,
        expires_at: datetime,
        now: datetime,
    ) -> ScanRunRecord:
        return self._ledger.acquire_lease(
            run_id,
            expected_version=expected_version,
            new_epoch=new_epoch,
            expires_at=expires_at,
            now=now,
        )
