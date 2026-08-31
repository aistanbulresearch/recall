from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from math import ceil
from statistics import median
from time import monotonic
from uuid import NAMESPACE_URL, uuid5

from recall.agents.full_audit import FullAuditCoordinator, FullAuditRunOutcome
from recall.agents.full_audit_models import PreparedRunEvidence, TurnTelemetry
from recall.connectors.live import LiveSourceRecord
from recall.contracts import (
    ArtifactStatus,
    ContractError,
    DataMode,
    build_artifact,
    canonical_json_bytes,
    parse_artifact,
)
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY
from .compressed_batch import BatchCaseResult
from .cohort import COHORT_ID
from .compressed_plan import CompressedCycle
from .compressed_preparation import CompressedPreparationBundle


FULL_AUDIT_CONCURRENCY = 2


@dataclass(frozen=True, slots=True)
class FullAuditPhaseResult:
    outcomes: tuple[FullAuditRunOutcome, ...]
    summary: dict[str, object]
    elapsed_ms: int
    started_at: str
    completed_at: str


@dataclass(frozen=True, slots=True)
class FullAuditCaseFailure:
    case_id: str
    run_id: str
    error_code: str


class FullAuditPhaseError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        completed_outcomes: tuple[FullAuditRunOutcome, ...],
        failures: tuple[FullAuditCaseFailure, ...],
        checkpoint_artifact_id: str,
    ) -> None:
        super().__init__(message)
        self.completed_outcomes = completed_outcomes
        self.failures = failures
        self.checkpoint_artifact_id = checkpoint_artifact_id


def execute_full_audit_phase(
    batch_outcomes: tuple[BatchCaseResult, ...],
    *,
    coordinator: FullAuditCoordinator,
    bundle: CompressedPreparationBundle,
    cycle: CompressedCycle,
    concurrency: int = FULL_AUDIT_CONCURRENCY,
    refetch_fetcher: Callable[[str], LiveSourceRecord] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    checkpoint_ledger: LedgerPort | None = None,
    plan_sha256: str | None = None,
    expected_manifest_id: str | None = None,
    checkpoint_run_id: str | None = None,
    agent_deadline_at: datetime | None = None,
) -> FullAuditPhaseResult:
    if not 1 <= concurrency <= FULL_AUDIT_CONCURRENCY:
        raise ValueError("full_audit_concurrency_invalid")
    prepared = {
        (item.case_id, item.cycle_id): item for item in bundle.cases
    }

    async def run_all() -> tuple[FullAuditRunOutcome, ...]:
        semaphore = asyncio.Semaphore(concurrency)

        async def execute(item: BatchCaseResult) -> FullAuditRunOutcome:
            key = (item.case.case_id, cycle.cycle_id)
            prepared_case = prepared.get(key)
            if prepared_case is None:
                raise RuntimeError("full_audit_prepared_case_missing")
            replay = ()
            if item.case.vcv is not None:
                replay = (bundle.observations_by_vcv[item.case.vcv],)
            evidence = PreparedRunEvidence(
                case_id=item.case.case_id,
                cloud_bound_payload=prepared_case.cloud_bound_payload,
                source_cursors=dict(item.watch_record.source_cursors),
                data_mode=(
                    item.case.data_mode
                    if not replay
                    else DataMode.CAPTURED_REPLAY
                ),
                replay_observations=replay,
                citation_sources={},
                refetch_fetcher=refetch_fetcher,
            )
            async with semaphore:
                entered_at = max(item.run_record.updated_at, clock())
                arguments = {
                    "evidence": evidence,
                    "now": entered_at,
                }
                if agent_deadline_at is not None:
                    arguments["deadline_at"] = agent_deadline_at
                return await coordinator.execute_run(
                    item.run_record.run_id,
                    **arguments,
                )

        gathered = await asyncio.gather(
            *(execute(item) for item in batch_outcomes),
            return_exceptions=True,
        )
        values = tuple(
            sorted(
                (
                    item
                    for item in gathered
                    if isinstance(item, FullAuditRunOutcome)
                ),
                key=lambda item: item.case_id,
            )
        )
        failures = tuple(
            sorted(
                (
                    FullAuditCaseFailure(
                        batch.case.case_id,
                        batch.run_record.run_id,
                        (
                            result.code
                            if isinstance(result, ContractError)
                            else type(result).__name__
                        ),
                    )
                    for batch, result in zip(
                        batch_outcomes, gathered, strict=True
                    )
                    if isinstance(result, BaseException)
                ),
                key=lambda item: item.case_id,
            )
        )
        if failures:
            if (
                checkpoint_ledger is None
                or plan_sha256 is None
                or expected_manifest_id is None
                or checkpoint_run_id is None
            ):
                raise RuntimeError("full_audit_checkpoint_configuration_missing")
            checkpoint = persist_cohort_checkpoint(
                ledger=checkpoint_ledger,
                plan_sha256=plan_sha256,
                cycle=cycle,
                expected_manifest_id=expected_manifest_id,
                checkpoint_run_id=checkpoint_run_id,
                total_cases=len(batch_outcomes),
                completed=values,
                failures=failures,
                detected_at=clock(),
            )
            first = next(
                item for item in gathered if isinstance(item, BaseException)
            )
            raise FullAuditPhaseError(
                f"full_audit_case_failures:{len(failures)}",
                completed_outcomes=values,
                failures=failures,
                checkpoint_artifact_id=str(checkpoint["artifact_id"]),
            ) from first
        return tuple(sorted(values, key=lambda item: item.case_id))

    phase_started_at = clock().astimezone(UTC)
    started = monotonic()
    outcomes = asyncio.run(run_all())
    phase_completed_at = clock().astimezone(UTC)
    return FullAuditPhaseResult(
        outcomes=outcomes,
        summary=_summary(outcomes, coordinator=coordinator, concurrency=concurrency),
        elapsed_ms=ceil((monotonic() - started) * 1000),
        started_at=phase_started_at.isoformat().replace("+00:00", "Z"),
        completed_at=phase_completed_at.isoformat().replace("+00:00", "Z"),
    )


def persist_cohort_checkpoint(
    *,
    ledger: LedgerPort,
    plan_sha256: str,
    cycle: CompressedCycle,
    expected_manifest_id: str,
    checkpoint_run_id: str,
    total_cases: int,
    completed: tuple[FullAuditRunOutcome, ...],
    failures: tuple[FullAuditCaseFailure, ...],
    detected_at: datetime,
) -> Mapping[str, object]:
    for item in completed:
        _verify_checkpoint_outcome(ledger, item)
    completed_rows = [
        {
            "case_id": item.case_id,
            "run_id": item.run_id,
            "terminal_state": item.terminal_state,
            "audit_status": item.audit_status,
            "citation_audit_receipt_id": item.citation_audit_receipt_id,
            "policy_decision_id": item.policy_decision_id,
            "failure_receipt_ids": list(item.failure_receipt_ids),
            "agent_execution_receipt_ids": list(
                item.agent_execution_receipt_ids
            ),
        }
        for item in completed
    ]
    failed_rows = [
        {
            "case_id": item.case_id,
            "run_id": item.run_id,
            "error_code": item.error_code,
        }
        for item in failures
    ]
    inputs = set()
    for item in completed:
        pointer = ledger.get_scan_run(item.run_id)
        if pointer is None or pointer.scan_run_artifact_id is None:
            raise RuntimeError("full_audit_checkpoint_outcome_unbound")
        inputs.add(str(pointer.scan_run_artifact_id))
        inputs.update(item.failure_receipt_ids)
        inputs.update(item.agent_execution_receipt_ids)
        if item.citation_audit_receipt_id is not None:
            inputs.add(item.citation_audit_receipt_id)
        if item.policy_decision_id is not None:
            inputs.add(item.policy_decision_id)
    for item in failures:
        run = ledger.get_scan_run(item.run_id)
        if run is not None and run.scan_run_artifact_id is not None:
            inputs.add(str(run.scan_run_artifact_id))
    snapshot = {
        "plan_sha256": plan_sha256,
        "cycle_id": cycle.cycle_id,
        "expected_manifest_id": expected_manifest_id,
        "completed_outcomes": completed_rows,
        "failed_cases": failed_rows,
    }
    snapshot_sha = hashlib.sha256(canonical_json_bytes(snapshot)).hexdigest()
    artifact_id = str(
        uuid5(
            NAMESPACE_URL,
            f"{checkpoint_run_id}:cohort-execution-checkpoint:{snapshot_sha}",
        )
    )
    payload = {
        **snapshot,
        "checkpoint_status": "INCOMPLETE",
        "total_cases": total_cases,
        "policy_outcomes_synthesized": False,
    }
    existing = ledger.get_artifact(artifact_id)
    if existing is not None:
        parsed = parse_artifact(existing, authorized_producers=PRODUCER_REGISTRY)
        if (
            parsed.schema_name != "CohortExecutionCheckpoint"
            or parsed.payload.to_wire() != payload
            or parsed.input_artifact_ids != tuple(sorted(inputs))
        ):
            raise RuntimeError("full_audit_checkpoint_reconciliation_failed")
        return existing
    timestamp = detected_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
    wire = build_artifact(
        schema_name="CohortExecutionCheckpoint",
        schema_version="1.0.0",
        artifact_id=artifact_id,
        case_id=COHORT_ID,
        run_id=checkpoint_run_id,
        producer={
            "component": "managed-cohort-scheduler",
            "version": "1.0.0",
            "identity": "cohort-scheduler",
        },
        created_at=timestamp,
        input_artifact_ids=tuple(sorted(inputs)),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.INCOMPLETE,
        payload=payload,
        authorized_producers=PRODUCER_REGISTRY,
    )
    ledger.append_artifact(wire)
    persisted = ledger.get_artifact(str(wire["artifact_id"]))
    if persisted != wire:
        raise RuntimeError("full_audit_checkpoint_readback_failed")
    return wire


def _verify_checkpoint_outcome(
    ledger: LedgerPort, outcome: FullAuditRunOutcome
) -> None:
    pointer = ledger.get_scan_run(outcome.run_id)
    artifacts = tuple(
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
        for wire in ledger.list_by_run(outcome.run_id)
    )
    by_id = {item.artifact_id: item for item in artifacts}
    scan = (
        None
        if pointer is None or pointer.scan_run_artifact_id is None
        else by_id.get(str(pointer.scan_run_artifact_id))
    )
    if (
        pointer is None
        or pointer.state.value != outcome.terminal_state
        or scan is None
        or scan.schema_name != "ScanRun"
        or scan.case_id != outcome.case_id
        or scan.run_id != outcome.run_id
        or pointer.terminal_policy_decision_id != outcome.policy_decision_id
        or tuple(sorted(pointer.failure_receipt_ids))
        != tuple(sorted(outcome.failure_receipt_ids))
    ):
        raise RuntimeError("full_audit_checkpoint_outcome_unbound")

    referenced_ids = set(outcome.failure_receipt_ids)
    referenced_ids.update(outcome.agent_execution_receipt_ids)
    if outcome.citation_audit_receipt_id is not None:
        referenced_ids.add(outcome.citation_audit_receipt_id)
    if outcome.policy_decision_id is not None:
        referenced_ids.add(outcome.policy_decision_id)
    if any(
        artifact_id not in by_id
        or by_id[artifact_id].case_id != outcome.case_id
        or by_id[artifact_id].run_id != outcome.run_id
        for artifact_id in referenced_ids
    ):
        raise RuntimeError("full_audit_checkpoint_outcome_unbound")

    failures = tuple(by_id[item] for item in outcome.failure_receipt_ids)
    if (
        any(item.schema_name != "FailureReceipt" for item in failures)
        or tuple(sorted(item.payload.failure_code for item in failures))
        != tuple(sorted(outcome.technical_failure_codes))
    ):
        raise RuntimeError("full_audit_checkpoint_outcome_unbound")
    if outcome.terminal_state == "HALTED":
        if outcome.policy_decision_id is not None or not failures:
            raise RuntimeError("full_audit_checkpoint_outcome_unbound")
    else:
        policy = by_id.get(str(outcome.policy_decision_id))
        if (
            policy is None
            or policy.schema_name != "PolicyDecision"
            or policy.payload.outcome.value != outcome.terminal_state
            or policy.payload.outcome.value != outcome.policy_outcome
            or tuple(policy.payload.reason_codes) != outcome.policy_reason_codes
        ):
            raise RuntimeError("full_audit_checkpoint_outcome_unbound")

    if outcome.audit_status == "NOT_EVALUATED":
        if outcome.citation_audit_receipt_id is not None:
            raise RuntimeError("full_audit_checkpoint_outcome_unbound")
    else:
        audit = by_id.get(str(outcome.citation_audit_receipt_id))
        if (
            audit is None
            or audit.schema_name != "CitationAuditReceipt"
            or audit.payload.audit_status.value != outcome.audit_status
        ):
            raise RuntimeError("full_audit_checkpoint_outcome_unbound")

    execution = tuple(by_id[item] for item in outcome.agent_execution_receipt_ids)
    if any(item.schema_name != "AgentExecutionReceipt" for item in execution):
        raise RuntimeError("full_audit_checkpoint_outcome_unbound")
    starts = {
        item.artifact_id: item
        for item in execution
        if item.payload.execution_status.value == "STARTED"
    }
    terminals = tuple(
        item
        for item in execution
        if item.payload.execution_status.value != "STARTED"
    )
    if any(
        item.payload.started_receipt_id not in starts
        or starts[item.payload.started_receipt_id].payload.agent_role
        is not item.payload.agent_role
        or starts[item.payload.started_receipt_id].payload.attempt
        != item.payload.attempt
        for item in terminals
    ):
        raise RuntimeError("full_audit_checkpoint_outcome_unbound")
    if starts and set(starts) != {
        item.payload.started_receipt_id for item in terminals
    }:
        raise RuntimeError("full_audit_checkpoint_outcome_unbound")
    if outcome.audit_status != "NOT_EVALUATED" and not terminals:
        raise RuntimeError("full_audit_checkpoint_outcome_unbound")


def outcome_to_wire(
    outcome: FullAuditRunOutcome, *, epoch_label: str
) -> dict[str, object]:
    return {
        "case_id": outcome.case_id,
        "run_id": outcome.run_id,
        "epoch_label": epoch_label,
        "terminal_state": outcome.terminal_state,
        "audit_status": outcome.audit_status,
        "citation_audit_receipt_id": outcome.citation_audit_receipt_id,
        "policy_decision_id": outcome.policy_decision_id,
        "policy_outcome": outcome.policy_outcome,
        "policy_reason_codes": list(outcome.policy_reason_codes),
        "technical_failure_codes": list(outcome.technical_failure_codes),
        "failure_receipt_ids": list(outcome.failure_receipt_ids),
        "agent_execution_receipt_ids": list(
            outcome.agent_execution_receipt_ids
        ),
        "elapsed_ms": outcome.elapsed_ms,
    }


def _summary(
    outcomes: tuple[FullAuditRunOutcome, ...],
    *,
    coordinator: FullAuditCoordinator,
    concurrency: int,
) -> dict[str, object]:
    turns: tuple[TurnTelemetry, ...] = tuple(
        turn for outcome in outcomes for turn in outcome.turns
    )
    latencies = sorted(outcome.elapsed_ms for outcome in outcomes)
    cost = coordinator.cost_snapshot()
    return {
        "execution_profile": "FULL_AUDIT_V1",
        "runtime_class": "IN_PROCESS_ADK_CLOUD_RUN",
        "concurrency": concurrency,
        "model_id": coordinator.cost_policy.model_id,
        "endpoint_class": "VERTEX_AI_GLOBAL",
        "total_runs": len(outcomes),
        "complete_runs": sum(item.audit_status == "COMPLETE" for item in outcomes),
        "incomplete_runs": sum(item.audit_status == "INCOMPLETE" for item in outcomes),
        "not_evaluated_runs": sum(
            item.audit_status == "NOT_EVALUATED" for item in outcomes
        ),
        "halted_runs": sum(item.terminal_state == "HALTED" for item in outcomes),
        "total_agent_invocations": sum(
            len(item.agent_execution_receipt_ids) // 2 for item in outcomes
        ),
        "total_prompt_tokens": sum(item.prompt_tokens for item in turns),
        "total_candidate_tokens": sum(item.candidate_tokens for item in turns),
        "total_thoughts_tokens": sum(item.thoughts_tokens for item in turns),
        "total_tokens": sum(
            item.prompt_tokens + item.candidate_tokens + item.thoughts_tokens
            for item in turns
        ),
        "p50_latency_ms": 0 if not latencies else round(median(latencies)),
        "p95_latency_ms": _percentile95(latencies),
        "http_429_count": sum(item.http_429_count for item in outcomes),
        "projected_cost_usd_micros": cost.reconciled_usd_micros,
        "reserved_cost_usd_micros": cost.reserved_usd_micros,
        "pricing_policy_sha256": coordinator.cost_policy.sha256,
        "actual_billed_cost_state": "NOT_VERIFIED",
    }


def _percentile95(values: list[int]) -> int:
    if not values:
        return 0
    return values[max(0, ceil(len(values) * 0.95) - 1)]
