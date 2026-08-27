from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from time import perf_counter
from typing import TypeVar
from uuid import UUID, uuid5

from recall.contracts import parse_artifact
from recall.contracts.enums import (
    ArtifactStatus,
    DataMode,
    ScanRunEventCode,
    ScanRunState,
)
from recall.ledger.models import (
    ScanRunEventRecord,
    ScanRunRecord,
    WatchCaseRecord,
)
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY

from .compressed_cohort import CompressedCohortCase


BATCH_MAX_WORKERS = 32
_T = TypeVar("_T")
_R = TypeVar("_R")


@dataclass(frozen=True, slots=True)
class BatchCaseResult:
    case: CompressedCohortCase
    watch_record: WatchCaseRecord
    run_record: ScanRunRecord
    created: bool
    artifact_content_hash: str
    privacy_receipt_id: str
    schedule_epoch: str
    idempotency_key: str
    trace_id: str
    deadline_at: str
    budget_snapshot: Mapping[str, object]
    execution_profile: str


@dataclass(frozen=True, slots=True)
class BatchExecutionResult:
    outcomes: tuple[BatchCaseResult, ...]
    started_at: str
    completed_at: str
    worker_elapsed_ms: int
    readback_elapsed_ms: int
    total_elapsed_ms: int
    persistence_surface: str

    def metrics(self) -> dict[str, object]:
        selected = len(self.outcomes)
        created = sum(item.created for item in self.outcomes)
        return {
            "scope": "CASE_WRITE_AND_EXACT_READBACK",
            "measurement_semantics": "LEDGER_METHOD_INVOCATIONS_AND_COMMITTED_CASE_DOCUMENTS",
            "persistence_surface": self.persistence_surface,
            "batch_max_workers": min(BATCH_MAX_WORKERS, selected),
            "selected_case_count": selected,
            "ledger_operation_counts": {
                "watch_case_reads": selected,
                "watch_artifact_reads": selected,
                "idempotency_run_reads": selected,
                "create_run_transaction_calls": created,
                "post_create_or_reuse_artifact_reads": selected,
                "exact_run_pointer_reads": selected,
                "exact_run_artifact_reads": selected,
                "exact_run_event_queries": selected,
                "aggregate_count_reads": 2,
            },
            "committed_case_documents": created * 3,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "worker_elapsed_ms": self.worker_elapsed_ms,
            "readback_elapsed_ms": self.readback_elapsed_ms,
            "total_elapsed_ms": self.total_elapsed_ms,
            "effective_write_millis_per_case": (
                0 if not selected else ceil(self.total_elapsed_ms / selected)
            ),
        }


def execute_verified_batch(
    cases: Sequence[CompressedCohortCase],
    *,
    create_one: Callable[[CompressedCohortCase], BatchCaseResult],
    ledger: LedgerPort,
    started_at: datetime,
) -> BatchExecutionResult:
    started = started_at.astimezone(timezone.utc)
    total_start = perf_counter()
    worker_start = perf_counter()
    results = _joined_parallel(
        cases,
        create_one,
        failure_code="compressed_batch_worker_failed",
    )
    worker_elapsed = ceil((perf_counter() - worker_start) * 1000)
    ordered = tuple(sorted(results, key=lambda item: item.case.case_id))
    readback_start = perf_counter()
    _joined_parallel(
        ordered,
        lambda item: _verify_atomic_triple(ledger, item),
        failure_code="compressed_batch_readback_failed",
    )
    expected_event_count = sum(
        len(ledger.list_scan_run_events(item.run_record.run_id))
        for item in ordered
    )
    if (
        ledger.read_back_count("scan_runs") != len(ordered)
        or ledger.read_back_count("scan_run_events") != expected_event_count
    ):
        raise RuntimeError("compressed_batch_readback_count_mismatch")
    readback_elapsed = ceil((perf_counter() - readback_start) * 1000)
    total_elapsed = ceil((perf_counter() - total_start) * 1000)
    # Preserve the exact additive contract despite timer-read rounding.
    total_elapsed = worker_elapsed + readback_elapsed
    return BatchExecutionResult(
        outcomes=ordered,
        started_at=_timestamp(started),
        completed_at=_timestamp(started + timedelta(milliseconds=total_elapsed)),
        worker_elapsed_ms=worker_elapsed,
        readback_elapsed_ms=readback_elapsed,
        total_elapsed_ms=total_elapsed,
        persistence_surface=str(
            ledger.backend_metadata().get("persistence_surface", "UNKNOWN")
        ),
    )


def _joined_parallel(
    values: Sequence[_T],
    operation: Callable[[_T], _R],
    *,
    failure_code: str,
) -> list[_R]:
    if not values:
        return []
    completed: list[_R] = []
    failure: Exception | None = None
    workers = min(BATCH_MAX_WORKERS, len(values))
    with ThreadPoolExecutor(
        max_workers=workers,
        thread_name_prefix="recall-compressed-batch",
    ) as executor:
        futures: tuple[Future[_R], ...] = tuple(
            executor.submit(operation, value) for value in values
        )
        for future in as_completed(futures):
            try:
                result = future.result()
                if failure is None:
                    completed.append(result)
            except Exception as exc:  # join all workers before propagation
                if failure is None:
                    failure = exc
                    for pending in futures:
                        pending.cancel()
    if failure is not None:
        raise RuntimeError(failure_code) from failure
    return completed


def _verify_atomic_triple(
    ledger: LedgerPort, result: BatchCaseResult
) -> str:
    expected = result.run_record
    persisted = ledger.get_scan_run(expected.run_id)
    if persisted != expected:
        raise RuntimeError("compressed_batch_run_pointer_mismatch")
    wire = ledger.get_artifact(str(expected.scan_run_artifact_id))
    if wire is None:
        raise RuntimeError("compressed_batch_run_artifact_missing")
    artifact = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
    payload = artifact.payload
    events = ledger.list_scan_run_events(expected.run_id)
    if not result.created:
        if (
            artifact.schema_name != "ScanRun"
            or artifact.schema_version
            != (
                "1.1.0"
                if result.execution_profile == "FULL_AUDIT_V1"
                else "1.0.0"
            )
            or artifact.run_id != expected.run_id
            or artifact.case_id != result.case.case_id
            or artifact.content_hash != result.artifact_content_hash
            or payload.idempotency_key != result.idempotency_key
            or payload.scheduled_for != result.schedule_epoch
            or not events
            or events[0].from_state is not None
            or events[0].to_state is not ScanRunState.CREATED
            or events[0].event_code is not ScanRunEventCode.RUN_CREATED
            or events[-1].to_state is not expected.state
            or events[-1].sequence != expected.version
            or len(events) != expected.version
        ):
            raise RuntimeError("compressed_batch_reused_run_mismatch")
        return expected.run_id
    if (
        artifact.schema_name != "ScanRun"
        or artifact.schema_version
        != ("1.1.0" if result.execution_profile == "FULL_AUDIT_V1" else "1.0.0")
        or artifact.run_id != expected.run_id
        or artifact.artifact_id != expected.scan_run_artifact_id
        or artifact.case_id != result.case.case_id
        or artifact.created_at
        != expected.updated_at.isoformat().replace("+00:00", "Z")
        or artifact.content_hash != result.artifact_content_hash
        or artifact.producer.component != "workflow-controller"
        or artifact.producer.version != "0.1.0"
        or artifact.producer.identity != "controller"
        or artifact.input_artifact_ids
        != tuple(sorted((result.privacy_receipt_id, result.watch_record.artifact_id)))
        or artifact.data_mode is not DataMode.SYNTHETIC
        or artifact.status is not ArtifactStatus.VALID
        or artifact.warnings
        or artifact.extensions
        or payload.watch_case_id != result.case.case_id
        or payload.state is not ScanRunState.CREATED
        or payload.scheduled_for != result.schedule_epoch
        or payload.attempt != 0
        or payload.lease_epoch != 0
        or payload.deadline_at != result.deadline_at
        or dict(payload.budget_snapshot) != dict(result.budget_snapshot)
        or payload.idempotency_key != result.idempotency_key
        or payload.trace_id != result.trace_id
        or payload.terminal_policy_decision_id is not None
        or payload.failure_receipt_ids
        or (
            result.execution_profile == "FULL_AUDIT_V1"
            and payload.execution_profile.value != "FULL_AUDIT_V1"
        )
    ):
        raise RuntimeError("compressed_batch_run_artifact_mismatch")
    if len(events) != 1:
        raise RuntimeError("compressed_batch_event_count_mismatch")
    expected_event = ScanRunEventRecord(
        event_id=str(uuid5(UUID(expected.run_id), "scan-run-event:1")),
        run_id=expected.run_id,
        sequence=1,
        from_state=None,
        to_state=ScanRunState.CREATED,
        event_code=ScanRunEventCode.RUN_CREATED,
        agent_id=None,
        lease_epoch=0,
        created_at=expected.updated_at,
    )
    if events[0] != expected_event:
        raise RuntimeError("compressed_batch_event_mismatch")
    return expected.run_id


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
