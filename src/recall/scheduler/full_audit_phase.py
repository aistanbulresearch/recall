from __future__ import annotations

import asyncio
from dataclasses import dataclass
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from math import ceil
from statistics import median
from time import monotonic

from recall.agents.full_audit import FullAuditCoordinator, FullAuditRunOutcome
from recall.agents.full_audit_models import PreparedRunEvidence, TurnTelemetry
from recall.connectors.live import LiveSourceRecord
from recall.contracts import DataMode
from .compressed_batch import BatchCaseResult
from .compressed_plan import CompressedCycle
from .compressed_preparation import CompressedPreparationBundle


FULL_AUDIT_CONCURRENCY = 4


@dataclass(frozen=True, slots=True)
class FullAuditPhaseResult:
    outcomes: tuple[FullAuditRunOutcome, ...]
    summary: dict[str, object]
    elapsed_ms: int


def execute_full_audit_phase(
    batch_outcomes: tuple[BatchCaseResult, ...],
    *,
    coordinator: FullAuditCoordinator,
    bundle: CompressedPreparationBundle,
    cycle: CompressedCycle,
    concurrency: int = FULL_AUDIT_CONCURRENCY,
    refetch_fetcher: Callable[[str], LiveSourceRecord] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
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
                return await coordinator.execute_run(
                    item.run_record.run_id,
                    evidence=evidence,
                    now=entered_at,
                )

        gathered = await asyncio.gather(
            *(execute(item) for item in batch_outcomes),
            return_exceptions=True,
        )
        failures = tuple(item for item in gathered if isinstance(item, BaseException))
        if failures:
            # All independent cases were allowed to finish before the cohort
            # fails loudly. Integrity/CAS failures are never converted into a
            # fabricated per-case terminal state.
            raise RuntimeError(
                f"full_audit_case_failures:{len(failures)}"
            ) from failures[0]
        values = tuple(item for item in gathered if isinstance(item, FullAuditRunOutcome))
        return tuple(sorted(values, key=lambda item: item.case_id))

    started = monotonic()
    outcomes = asyncio.run(run_all())
    return FullAuditPhaseResult(
        outcomes=outcomes,
        summary=_summary(outcomes, coordinator=coordinator, concurrency=concurrency),
        elapsed_ms=ceil((monotonic() - started) * 1000),
    )


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
