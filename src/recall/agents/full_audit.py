from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import UUID, uuid5

from recall.contracts import (
    AgentRole,
    ArtifactStatus,
    ContractError,
    DataMode,
    build_artifact,
    parse_artifact,
)
from recall.contracts.enums import (
    DataComposition,
    ScanRunEventCode,
    ScanRunState,
    WatchCaseState,
)
from recall.controller import Controller
from recall.controller.tool_gateway_store import GatewayInvocationStore
from recall.ledger.port import LedgerPort
from recall.ledger.models import ScanRunRecord
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.scheduler.model_cost import (
    CostSnapshot,
    ModelCostLedger,
    ModelCostPolicy,
    projected_cost_micros,
    validate_request_budget,
    worst_case_turn_cost_micros,
)

from .full_audit_artifacts import (
    ASSESSOR_OUTPUT_BINDING_FIELDS,
    build_assessor_artifacts,
    build_auditor_artifacts,
    build_completed_receipt,
    build_failed_receipt,
    build_registry_receipt,
    build_started_receipt,
    build_watcher_artifacts,
    prepared_tool_records,
)
from .full_audit_models import (
    FullAuditRunOutcome,
    MAX_MODEL_TURNS_PER_ROLE,
    PreparedRunEvidence,
    RoleExecutionContext,
    RoleExecutionError,
    RoleRunResult,
    RoleRunner,
    TurnTelemetry,
)
from .local_tools import LocalToolInputs, build_local_tools
from .schemas import (
    EvidenceSnapshotOutput,
    safe_contract_code,
    safe_schema_failure_detail,
)


__all__ = [
    "FullAuditCoordinator",
    "FullAuditRunOutcome",
    "PreparedRunEvidence",
    "RoleExecutionContext",
    "RoleRunResult",
    "TurnTelemetry",
]


class FullAuditCoordinator:
    def __init__(
        self,
        ledger: LedgerPort,
        *,
        role_runner: RoleRunner,
        invocation_store: GatewayInvocationStore,
        cost_ledger: ModelCostLedger,
        cost_policy: ModelCostPolicy,
        role_timeout_seconds: int = 120,
        lease_duration_seconds: int = 900,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if role_timeout_seconds < 1 or lease_duration_seconds < 1:
            raise ValueError("full_audit_timeout_invalid")
        self._ledger = ledger
        self._runner = role_runner
        self._invocations = invocation_store
        self._cost = cost_ledger
        self._cost_policy = cost_policy
        self._role_timeout = role_timeout_seconds
        self._lease_duration = lease_duration_seconds
        self._clock = clock
        self._controller = Controller(ledger)

    async def execute_run(
        self,
        run_id: str,
        *,
        evidence: PreparedRunEvidence,
        now: datetime,
        deadline_at: datetime | None = None,
    ) -> FullAuditRunOutcome:
        started_clock = monotonic()
        all_turns: list[TurnTelemetry] = []
        http_429_count = 0
        active_role: AgentRole | None = None
        active_started: Mapping[str, object] | None = None
        active_attempt = 0
        current: ScanRunRecord | None = None
        try:
            current = self._prepare_run(run_id, evidence=evidence, now=now)
            scan = self._scan_artifact(current)
            scan_deadline_at = datetime.fromisoformat(
                str(scan["deadline_at"]).replace("Z", "+00:00")
            )
            deadline_at = (
                scan_deadline_at
                if deadline_at is None
                else min(scan_deadline_at, deadline_at)
            )
            if now >= deadline_at:
                raise RuntimeError("agent_execution_deadline_exceeded")
            if current.state in {
                ScanRunState.NO_ACTION,
                ScanRunState.ABSTAIN,
                ScanRunState.REVIEW_REQUIRED,
                ScanRunState.HALTED,
            }:
                return self._outcome(
                    run_id,
                    evidence.case_id,
                    elapsed_ms=0,
                    turns=(),
                    http_429_count=0,
                )
            trace_id = str(scan["trace_id"])
            if current.state is ScanRunState.WATCHING:
                active_role = AgentRole.EVIDENCE_WATCHER
                active_attempt, active_started, result = await self._execute_role(
                    active_role,
                    run_id=run_id,
                    evidence=evidence,
                    input_artifact_ids=(),
                    trace_id=trace_id,
                    now=now,
                    deadline_at=deadline_at,
                )
                all_turns.extend(result.turns)
                http_429_count += result.http_429_count
                completed = build_completed_receipt(
                    case_id=evidence.case_id,
                    run_id=run_id,
                    role=active_role,
                    attempt=active_attempt,
                    started_receipt_id=str(active_started["artifact_id"]),
                    data_mode=evidence.data_mode,
                    result=result,
                )
                try:
                    artifacts = build_watcher_artifacts(
                        run_id=run_id,
                        evidence=evidence,
                        result=result,
                        completed_receipt=completed,
                    )
                except ContractError as exc:
                    raise self._role_contract_failure(result, exc.code) from exc
                current = self._ledger.commit_agent_step(
                    run_id,
                    expected_version=current.version,
                    lease_epoch=current.lease_epoch,
                    event_code=ScanRunEventCode.FULL_AUDIT_REQUIRED,
                    artifacts=artifacts,
                    now=result.completed_at,
                )
                active_started = None

            candidate = self._one(run_id, "CandidateDeltaReceipt")
            snapshot = self._one(run_id, "EvidenceSnapshot")
            if current.state is ScanRunState.ASSESSING:
                active_role = AgentRole.EVIDENCE_ASSESSOR
                input_ids = (
                    str(candidate["artifact_id"]),
                    str(snapshot["artifact_id"]),
                )
                active_attempt, active_started, result = await self._execute_role(
                    active_role,
                    run_id=run_id,
                    evidence=evidence,
                    input_artifact_ids=input_ids,
                    trace_id=trace_id,
                    now=current.updated_at,
                    deadline_at=deadline_at,
                    required_ledger_artifact_id=input_ids[0],
                    assessor_candidate=candidate,
                    assessor_snapshot=snapshot,
                )
                all_turns.extend(result.turns)
                http_429_count += result.http_429_count
                completed = build_completed_receipt(
                    case_id=evidence.case_id,
                    run_id=run_id,
                    role=active_role,
                    attempt=active_attempt,
                    started_receipt_id=str(active_started["artifact_id"]),
                    data_mode=evidence.data_mode,
                    result=result,
                )
                try:
                    artifacts = build_assessor_artifacts(
                        run_id=run_id,
                        evidence=evidence,
                        candidate=candidate,
                        snapshot=snapshot,
                        result=result,
                        completed_receipt=completed,
                    )
                except ContractError as exc:
                    raise self._role_contract_failure(
                        result,
                        exc.code,
                        contract_detail=exc.detail,
                    ) from exc
                current = self._ledger.commit_agent_step(
                    run_id,
                    expected_version=current.version,
                    lease_epoch=current.lease_epoch,
                    event_code=ScanRunEventCode.ASSESSMENT_COMPLETED,
                    artifacts=artifacts,
                    now=result.completed_at,
                )
                active_started = None

            assessment = self._one(run_id, "AssessmentReceipt")
            delta = self._one(run_id, "EvidenceDelta")
            material_claim_ids = self._material_claim_ids(assessment)
            if current.state is ScanRunState.AUDITING:
                active_role = AgentRole.CITATION_AUDITOR
                input_ids = (
                    str(assessment["artifact_id"]),
                    str(delta["artifact_id"]),
                )
                active_attempt, active_started, result = await self._execute_role(
                    active_role,
                    run_id=run_id,
                    evidence=evidence,
                    input_artifact_ids=input_ids,
                    trace_id=trace_id,
                    now=current.updated_at,
                    deadline_at=deadline_at,
                    required_ledger_artifact_id=input_ids[0],
                    required_refetch_claim_ids=material_claim_ids,
                )
                all_turns.extend(result.turns)
                http_429_count += result.http_429_count
                completed = build_completed_receipt(
                    case_id=evidence.case_id,
                    run_id=run_id,
                    role=active_role,
                    attempt=active_attempt,
                    started_receipt_id=str(active_started["artifact_id"]),
                    data_mode=evidence.data_mode,
                    result=result,
                )
                try:
                    artifacts = build_auditor_artifacts(
                        run_id=run_id,
                        evidence=evidence,
                        assessment=assessment,
                        result=result,
                        completed_receipt=completed,
                    )
                except ContractError as exc:
                    raise self._role_contract_failure(result, exc.code) from exc
                current = self._ledger.commit_agent_step(
                    run_id,
                    expected_version=current.version,
                    lease_epoch=current.lease_epoch,
                    event_code=ScanRunEventCode.AUDIT_COMPLETED,
                    artifacts=artifacts,
                    now=result.completed_at,
                )
                active_started = None

            self._append_data_mode_receipt(run_id, evidence=evidence, now=current.updated_at)
            audit = self._one(run_id, "CitationAuditReceipt")
            terminal = self._controller.evaluate_and_commit(
                run_id,
                verified_delta_hash=str(candidate["content_hash"]),
                now=current.updated_at,
                audit_receipt_id=str(audit["artifact_id"]),
                claim_ids=material_claim_ids,
                verified_snapshot_id=str(snapshot["artifact_id"]),
                verified_source_cursors=evidence.source_cursors,
            )
            return self._outcome(
                run_id,
                evidence.case_id,
                elapsed_ms=round((monotonic() - started_clock) * 1000),
                turns=tuple(all_turns),
                http_429_count=http_429_count,
            )
        except Exception as exc:  # noqa: BLE001 - one case must not kill cohort
            if isinstance(exc, ContractError) and exc.code in {
                "stale_write_rejected",
                "lease_active",
            }:
                # A duplicate invocation lost a CAS race. It must never convert
                # the winning invocation's authoritative state into HALTED.
                raise
            if isinstance(exc, RoleExecutionError):
                all_turns.extend(exc.turns)
                http_429_count += exc.http_429_count
            failure_now = now if self._clock is None else self._clock()
            if failure_now.tzinfo is None:
                raise ValueError("full_audit_clock_timezone_required") from exc
            return self._halt(
                run_id,
                evidence=evidence,
                error=exc,
                active_role=active_role,
                active_attempt=active_attempt,
                active_started=active_started,
                now=failure_now.astimezone(UTC),
                elapsed_ms=round((monotonic() - started_clock) * 1000),
                turns=tuple(all_turns),
                http_429_count=http_429_count,
                ownership=current,
            )

    def cost_snapshot(self) -> CostSnapshot:
        return self._cost.snapshot()

    @property
    def cost_policy(self) -> ModelCostPolicy:
        return self._cost_policy

    def _prepare_run(
        self, run_id: str, *, evidence: PreparedRunEvidence, now: datetime
    ):
        current = self._required_run(run_id)
        if current.state is ScanRunState.CREATED:
            current = self._controller.transition(
                run_id,
                expected_version=current.version,
                lease_epoch=current.lease_epoch,
                event_code=ScanRunEventCode.OUTBOX_PUBLISHED,
                now=now,
            )
        active_states = {
            ScanRunState.ROUTING,
            ScanRunState.WATCHING,
            ScanRunState.ASSESSING,
            ScanRunState.AUDITING,
            ScanRunState.POLICY_EVALUATION,
        }
        lease_expired = (
            current.lease_expires_at is not None
            and now >= current.lease_expires_at
        )
        if current.state is ScanRunState.QUEUED or (
            current.state in active_states and lease_expired
        ):
            current = self._controller.acquire_lease(
                run_id,
                expected_version=current.version,
                new_epoch=current.lease_epoch + 1,
                expires_at=now + timedelta(seconds=self._lease_duration),
                now=now,
            )
        elif current.state in active_states:
            # An active lease belongs to another invocation. Only an expired
            # lease may be resumed, and acquire_lease records the new epoch.
            raise ContractError("lease_active", run_id)
        if current.state is ScanRunState.ROUTING:
            registry_receipts = [
                item
                for item in self._ledger.list_by_run(run_id)
                if item["schema_name"] == "RegistryResolutionReceipt"
            ]
            if len(registry_receipts) > 1:
                raise ContractError(
                    "ledger_integrity_failed", "RegistryResolutionReceipt"
                )
            if not registry_receipts:
                self._ledger.append_artifact(build_registry_receipt(
                    case_id=evidence.case_id,
                    run_id=run_id,
                    data_mode=evidence.data_mode,
                    now=now,
                ))
            current = self._controller.transition(
                run_id,
                expected_version=current.version,
                lease_epoch=current.lease_epoch,
                event_code=ScanRunEventCode.ROUTE_VALIDATED,
                now=now,
            )
        return current

    async def _execute_role(
        self,
        role: AgentRole,
        *,
        run_id: str,
        evidence: PreparedRunEvidence,
        input_artifact_ids: tuple[str, ...],
        trace_id: str,
        now: datetime,
        deadline_at: datetime,
        required_ledger_artifact_id: str | None = None,
        required_refetch_claim_ids: tuple[str, ...] = (),
        assessor_candidate: Mapping[str, object] | None = None,
        assessor_snapshot: Mapping[str, object] | None = None,
    ) -> tuple[int, Mapping[str, object], RoleRunResult]:
        abandoned = self._open_started_receipt(run_id, role)
        if abandoned is not None:
            abandoned_started_at = datetime.fromisoformat(
                str(abandoned["started_at"]).replace("Z", "+00:00")
            )
            self._ledger.append_artifact(
                build_failed_receipt(
                    case_id=evidence.case_id,
                    run_id=run_id,
                    role=role,
                    attempt=int(abandoned["attempt"]),
                    started_receipt_id=str(abandoned["artifact_id"]),
                    trace_id=str(abandoned["trace_id"]),
                    invocation_id=str(abandoned["invocation_id"]),
                    data_mode=evidence.data_mode,
                    started_at=abandoned_started_at,
                    failed_at=now,
                    failure_code="controller_failed",
                )
            )
        attempt = self._next_attempt(run_id, role)
        if attempt > 2:
            raise RuntimeError("agent_retry_budget_exhausted")
        invocation_id = str(uuid5(UUID(run_id), f"{role.value}:{attempt}"))
        context = RoleExecutionContext(
            evidence.case_id,
            run_id,
            attempt,
            invocation_id,
            input_artifact_ids,
            trace_id,
        )
        started = build_started_receipt(
            case_id=evidence.case_id, run_id=run_id, role=role,
            attempt=attempt, trace_id=trace_id, invocation_id=invocation_id,
            data_mode=evidence.data_mode, now=now,
        )
        self._ledger.append_artifact(started)
        prompt = self._prompt(
            role,
            input_artifact_ids,
            run_id=run_id,
            required_refetch_claim_ids=required_refetch_claim_ids,
            assessor_candidate=assessor_candidate,
            assessor_snapshot=assessor_snapshot,
        )
        validate_request_budget(prompt.encode("utf-8"), self._cost_policy)
        tool_records: list[Mapping[str, str]] = []
        tools = build_local_tools(
            self._ledger,
            self._invocations,
            LocalToolInputs(
                case_id=evidence.case_id,
                run_id=run_id,
                role=role,
                attempt=attempt,
                role_execution_invocation_id=invocation_id,
                data_mode=evidence.data_mode,
                evidence_records=prepared_tool_records(
                    evidence, observed_at=now
                ),
                source_cursors=evidence.source_cursors,
                clock=lambda: now,
                citation_sources=evidence.citation_sources,
                refetch_fetcher=evidence.refetch_fetcher,
                tool_record_sink=tool_records.append,
            ),
        )
        reservations: list[str] = []
        reconciled_reservations: set[str] = set()
        reconciliation_failed = False
        captured_turns: tuple[TurnTelemetry, ...] = ()
        worst = worst_case_turn_cost_micros(self._cost_policy)

        def reconcile_unsettled_reservations(
            turns: tuple[TurnTelemetry, ...],
        ) -> None:
            nonlocal reconciliation_failed
            for index, reservation_id in enumerate(reservations):
                if reservation_id in reconciled_reservations:
                    continue
                actual = 0
                if index < len(turns):
                    turn = turns[index]
                    actual = projected_cost_micros(
                        prompt_tokens=turn.prompt_tokens,
                        candidate_tokens=turn.candidate_tokens,
                        thoughts_tokens=turn.thoughts_tokens,
                        policy=self._cost_policy,
                    )
                try:
                    self._cost.reconcile(
                        reservation_id,
                        actual_usd_micros=actual,
                    )
                except BaseException:  # cost-ledger failure is not safely retryable
                    reconciliation_failed = True
                    raise
                reconciled_reservations.add(reservation_id)

        def failed_role_error(exc: RoleExecutionError) -> RoleExecutionError:
            record_calls = tuple(str(item["call_id"]) for item in tool_records)
            record_responses = tuple(
                str(item["response_id"]) for item in tool_records
            )
            exception_has_ids = bool(
                exc.tool_call_ids or exc.tool_response_ids
            )
            records_have_ids = bool(record_calls or record_responses)
            evidence_disagrees = (
                exception_has_ids
                and records_have_ids
                and (
                    exc.tool_call_ids != record_calls
                    or exc.tool_response_ids != record_responses
                )
            )
            return RoleExecutionError(
                "agent_tool_evidence_mismatch" if evidence_disagrees else exc.code,
                turns=exc.turns,
                http_429_count=exc.http_429_count,
                tool_records=tuple(tool_records),
                tool_call_ids=(
                    record_calls if records_have_ids else exc.tool_call_ids
                ),
                tool_response_ids=(
                    record_responses
                    if records_have_ids
                    else exc.tool_response_ids
                ),
            )

        try:
            for turn_index in range(1, MAX_MODEL_TURNS_PER_ROLE + 1):
                reservation_id = f"{run_id}:{role.value}:{attempt}:{turn_index}"
                reservation = self._cost.reserve(reservation_id, worst)
                if reservation.state != "RESERVED":
                    raise RuntimeError("model_cost_cap_exceeded")
                reservations.append(reservation_id)
            remaining_seconds = (deadline_at - now).total_seconds()
            if remaining_seconds <= 0:
                raise RoleExecutionError("agent_execution_deadline_exceeded")
            try:
                result = await asyncio.wait_for(
                    self._runner.execute(role, prompt, tools, context),
                    timeout=min(self._role_timeout, remaining_seconds),
                )
            except RoleExecutionError as exc:
                captured_turns = exc.turns
                raise failed_role_error(exc) from exc
            except TimeoutError as exc:
                raise RoleExecutionError(
                    "agent_timeout",
                    tool_records=tuple(tool_records),
                ) from exc
            result = replace(result, tool_records=tuple(tool_records))
            captured_turns = result.turns
            reconcile_unsettled_reservations(result.turns)
            if len(result.turns) > MAX_MODEL_TURNS_PER_ROLE:
                raise RoleExecutionError(
                    "model_turn_budget_exceeded",
                    turns=result.turns,
                    http_429_count=result.http_429_count,
                    tool_records=result.tool_records,
                    tool_call_ids=result.tool_call_ids,
                    tool_response_ids=result.tool_response_ids,
                )
            if (
                not result.tool_call_ids
                or len(set(result.tool_call_ids)) != len(result.tool_call_ids)
                or set(result.tool_call_ids) != set(result.tool_response_ids)
            ):
                raise RoleExecutionError(
                    "agent_tool_round_trip_incomplete",
                    turns=result.turns,
                    http_429_count=result.http_429_count,
                    tool_records=result.tool_records,
                    tool_call_ids=result.tool_call_ids,
                    tool_response_ids=result.tool_response_ids,
                )
            if role is AgentRole.EVIDENCE_WATCHER:
                self._verify_watcher_source_cursors(
                    result,
                    expected_source_cursors=evidence.source_cursors,
                )
            if required_ledger_artifact_id is not None:
                self._verify_ledger_read_target(
                    result,
                    required_artifact_id=required_ledger_artifact_id,
                )
            if role is AgentRole.CITATION_AUDITOR:
                self._verify_auditor_tool_plan(
                    result,
                    required_ledger_artifact_id=required_ledger_artifact_id,
                    required_refetch_claim_ids=required_refetch_claim_ids,
                )
            return attempt, started, result
        except BaseException as exc:
            if (
                not reconciliation_failed
                and len(reconciled_reservations) < len(reservations)
            ):
                try:
                    reconcile_unsettled_reservations(captured_turns)
                except BaseException as reconciliation_error:
                    exc.add_note(
                        "model cost reconciliation also failed; reservation "
                        "state is not safely retryable"
                    )
                    raise exc from reconciliation_error
            raise

    def _halt(
        self,
        run_id: str,
        *,
        evidence: PreparedRunEvidence,
        error: Exception,
        active_role: AgentRole | None,
        active_attempt: int,
        active_started: Mapping[str, object] | None,
        now: datetime,
        elapsed_ms: int,
        turns: tuple[TurnTelemetry, ...],
        http_429_count: int,
        ownership: ScanRunRecord | None,
    ) -> FullAuditRunOutcome:
        if ownership is None:
            raise error
        current = ownership
        observed = self._required_run(run_id)
        if (
            observed.version != current.version
            or observed.lease_epoch != current.lease_epoch
        ):
            raise ContractError("stale_write_rejected", run_id) from error
        now = max(now, current.updated_at)
        if active_role is not None and active_started is None:
            active_started = self._open_started_receipt(run_id, active_role)
            if active_started is not None:
                active_attempt = int(active_started["attempt"])
        agent_failure_code = self._agent_failure_code(error)
        # The frozen FailureReceipt contract permits HALTED only for controller,
        # ledger, or policy failures. Role-specific detail remains on the failed
        # AgentExecutionReceipt; the authoritative technical terminal is a
        # controller failure because the required FULL_AUDIT_V1 step did not finish.
        terminal_failure_code = self._terminal_failure_code(error)
        scan = self._scan_artifact(current)
        failed_agent_receipt = None
        if active_role is not None and active_started is not None:
            started_at = datetime.fromisoformat(
                str(active_started["started_at"]).replace("Z", "+00:00")
            )
            active_turns = error.turns if isinstance(error, RoleExecutionError) else ()
            active_429_count = (
                error.http_429_count if isinstance(error, RoleExecutionError) else 0
            )
            active_tool_records = (
                error.tool_records if isinstance(error, RoleExecutionError) else ()
            )
            active_tool_call_ids = (
                error.tool_call_ids if isinstance(error, RoleExecutionError) else ()
            )
            active_tool_response_ids = (
                error.tool_response_ids
                if isinstance(error, RoleExecutionError)
                else ()
            )
            failed_agent_receipt = build_failed_receipt(
                case_id=evidence.case_id, run_id=run_id, role=active_role,
                attempt=active_attempt, started_receipt_id=str(active_started["artifact_id"]),
                trace_id=str(scan["trace_id"]),
                invocation_id=str(active_started["invocation_id"]),
                data_mode=evidence.data_mode, started_at=started_at, failed_at=now,
                failure_code=agent_failure_code,
                turns=active_turns,
                http_429_count=active_429_count,
                tool_records=active_tool_records,
                tool_call_ids=active_tool_call_ids,
                tool_response_ids=active_tool_response_ids,
                schema_failure_detail=self._schema_failure_detail(error),
            )
        failure = build_artifact(
            schema_name="FailureReceipt", schema_version="1.0.0",
            artifact_id=str(uuid5(UUID(run_id), f"failure:{terminal_failure_code}")),
            case_id=evidence.case_id, run_id=run_id,
            producer={"component": "full-audit-controller", "version": "1.0.0", "identity": "controller-failure-recorder"},
            created_at=now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            input_artifact_ids=(str(current.scan_run_artifact_id),),
            data_mode=evidence.data_mode, status=ArtifactStatus.REJECTED,
            payload={
                "failure_code": terminal_failure_code,
                "stage": "UNKNOWN" if active_role is None else active_role.value,
                "retryable": False, "attempt": max(1, active_attempt),
                "budget_state": "WITHIN_LIMIT", "details": {},
                "related_artifact_ids": [str(current.scan_run_artifact_id)],
                "safe_terminal": "HALTED", "operator_action": "inspect_agent_execution_receipts",
            }, authorized_producers=PRODUCER_REGISTRY,
        )
        case = self._ledger.get_watch_case(evidence.case_id)
        case_update = None if case is None else replace(
            case,
            state=WatchCaseState.ATTENTION_REQUIRED,
            version=case.version + 1,
            attention_reason_codes=(terminal_failure_code,),
            next_scan_at=None,
            updated_at=now,
        )
        if current.state not in {
            ScanRunState.NO_ACTION, ScanRunState.ABSTAIN,
            ScanRunState.REVIEW_REQUIRED, ScanRunState.HALTED,
        }:
            self._ledger.commit_terminal(
                run_id, expected_version=current.version,
                lease_epoch=current.lease_epoch, target_state="HALTED",
                event_code=ScanRunEventCode.TECHNICAL_HALTED,
                policy_decision=None, failure_receipt=failure, review_task=None,
                terminal_artifacts=(
                    () if failed_agent_receipt is None else (failed_agent_receipt,)
                ),
                watch_case_update=case_update, now=now,
            )
        return self._outcome(
            run_id, evidence.case_id, elapsed_ms=elapsed_ms,
            turns=turns, http_429_count=http_429_count,
        )

    def _append_data_mode_receipt(
        self, run_id: str, *, evidence: PreparedRunEvidence, now: datetime
    ) -> None:
        artifacts = tuple(
            item
            for item in self._ledger.list_by_run(run_id)
            if item["schema_name"] != "DataModeReceipt"
        )
        subjects = sorted(str(item["artifact_id"]) for item in artifacts)
        modes = sorted({str(item["data_mode"]) for item in artifacts})
        composition = {
            ("SYNTHETIC",): DataComposition.SYNTHETIC_ONLY.value,
            ("CAPTURED_REPLAY", "SYNTHETIC"): DataComposition.SYNTHETIC_WITH_CAPTURED_REPLAY.value,
        }.get(tuple(modes))
        if composition is None:
            raise ContractError("data_mode_conflict")
        receipt_id = str(uuid5(UUID(run_id), "data-mode"))
        existing = self._ledger.get_artifact(receipt_id)
        created_at = (
            now.astimezone(UTC).isoformat().replace("+00:00", "Z")
            if existing is None
            else str(existing["created_at"])
        )
        wire = build_artifact(
            schema_name="DataModeReceipt", schema_version="2.0.0",
            artifact_id=receipt_id,
            case_id=evidence.case_id, run_id=run_id,
            producer={"component": "controller-mode-gate", "version": "2.0.0", "identity": "controller-mode-gate"},
            created_at=created_at,
            input_artifact_ids=tuple(subjects), data_mode=evidence.data_mode,
            status=ArtifactStatus.VALID,
            payload={
                "subject_artifact_ids": subjects, "mode_set": modes,
                "declared_composition": composition,
                "propagation_status": "PASS", "reason_codes": [],
            }, authorized_producers=PRODUCER_REGISTRY,
        )
        if existing is not None and existing != wire:
            raise ContractError("data_mode_receipt_reconciliation_failed")
        self._ledger.append_artifact(wire)

    def _outcome(
        self, run_id: str, case_id: str, *, elapsed_ms: int,
        turns: tuple[TurnTelemetry, ...], http_429_count: int,
    ) -> FullAuditRunOutcome:
        current = self._required_run(run_id)
        artifacts = tuple(self._ledger.list_by_run(run_id))
        audit = next((item for item in artifacts if item["schema_name"] == "CitationAuditReceipt"), None)
        policy = next((item for item in artifacts if item["schema_name"] == "PolicyDecision"), None)
        failures = tuple(sorted(item["failure_code"] for item in artifacts if item["schema_name"] == "FailureReceipt"))
        failure_ids = tuple(sorted(str(item["artifact_id"]) for item in artifacts if item["schema_name"] == "FailureReceipt"))
        execution_ids = tuple(sorted(str(item["artifact_id"]) for item in artifacts if item["schema_name"] == "AgentExecutionReceipt"))
        terminal_receipts = tuple(
            item
            for item in artifacts
            if item["schema_name"] == "AgentExecutionReceipt"
            and item["execution_status"] != "STARTED"
        )
        persisted_turns = tuple(
            TurnTelemetry(
                int(turn["turn_index"]),
                int(turn["prompt_tokens"]),
                int(turn["candidate_tokens"]),
                int(turn["thoughts_tokens"]),
                int(turn["total_tokens"]),
                str(turn["finish_reason"]),
                bool(turn["function_call_emitted"]),
                int(turn["latency_ms"]),
            )
            for receipt in sorted(
                terminal_receipts,
                key=lambda item: (str(item["started_at"]), str(item["artifact_id"])),
            )
            for turn in receipt["turns"]
        )
        persisted_429_count = sum(
            int(item["http_429_count"]) for item in terminal_receipts
        )
        persisted_elapsed_ms = elapsed_ms
        if terminal_receipts:
            starts = [
                datetime.fromisoformat(str(item["started_at"]).replace("Z", "+00:00"))
                for item in terminal_receipts
            ]
            completions = [
                datetime.fromisoformat(str(item["completed_at"]).replace("Z", "+00:00"))
                for item in terminal_receipts
            ]
            persisted_elapsed_ms = round(
                (max(completions) - min(starts)).total_seconds() * 1000
            )
        return FullAuditRunOutcome(
            case_id, run_id, current.state.value,
            "NOT_EVALUATED" if audit is None else str(audit["audit_status"]),
            None if audit is None else str(audit["artifact_id"]),
            None if policy is None else str(policy["artifact_id"]),
            None if policy is None else str(policy["outcome"]),
            () if policy is None else tuple(policy["reason_codes"]),
            failures,
            failure_ids,
            execution_ids,
            persisted_elapsed_ms,
            persisted_turns,
            persisted_429_count,
        )

    @staticmethod
    def _agent_failure_code(error: Exception) -> str:
        if isinstance(error, TimeoutError) or (
            isinstance(error, RoleExecutionError) and error.code == "agent_timeout"
        ):
            return "agent_timeout"
        if isinstance(error, RoleExecutionError) and (
            error.code == "agent_schema_invalid"
            or error.code.startswith("agent_schema_invalid:")
            or error.code == "agent_response_missing"
            or error.code.startswith("agent_response_missing:")
        ):
            return "agent_schema_invalid"
        if isinstance(error, RoleExecutionError):
            return "controller_failed"
        if isinstance(error, ContractError):
            if error.code in {
                "artifact_integrity_failed",
                "ledger_integrity_failed",
                "stale_write_rejected",
                "lease_expired",
                "contract_transition_invalid",
            }:
                return "ledger_integrity_failed"
            return "agent_schema_invalid"
        message = str(error)
        if "model_cost_cap_exceeded" in message:
            return "budget_exhausted"
        if "source_unavailable" in message:
            return "source_unavailable"
        return "controller_failed"

    @staticmethod
    def _terminal_failure_code(error: Exception) -> str:
        if isinstance(error, ContractError) and error.code in {
            "artifact_integrity_failed",
            "ledger_integrity_failed",
            "stale_write_rejected",
            "lease_expired",
            "contract_transition_invalid",
        }:
            return "ledger_integrity_failed"
        return "controller_failed"

    def _one(self, run_id: str, schema: str) -> Mapping[str, object]:
        matches = [item for item in self._ledger.list_by_run(run_id) if item["schema_name"] == schema]
        if len(matches) != 1:
            raise ContractError("ledger_integrity_failed", schema)
        return matches[0]

    def _open_started_receipt(
        self, run_id: str, role: AgentRole
    ) -> Mapping[str, object] | None:
        receipts = [
            item
            for item in self._ledger.list_by_run(run_id)
            if item["schema_name"] == "AgentExecutionReceipt"
            and item["agent_role"] == role.value
        ]
        completed_start_ids = {
            str(item["started_receipt_id"])
            for item in receipts
            if item["execution_status"] != "STARTED"
        }
        open_receipts = [
            item
            for item in receipts
            if item["execution_status"] == "STARTED"
            and str(item["artifact_id"]) not in completed_start_ids
        ]
        if not open_receipts:
            return None
        return max(open_receipts, key=lambda item: int(item["attempt"]))

    def _required_run(self, run_id: str):
        current = self._ledger.get_scan_run(run_id)
        if current is None:
            raise ContractError("stale_write_rejected", run_id)
        return current

    def _scan_artifact(self, current) -> Mapping[str, object]:
        value = self._ledger.get_artifact(str(current.scan_run_artifact_id))
        if value is None:
            raise ContractError("ledger_integrity_failed", "ScanRun")
        parsed = parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
        if parsed.schema_version != "1.1.0":
            raise ContractError("full_audit_profile_required")
        return value

    def _next_attempt(self, run_id: str, role: AgentRole) -> int:
        attempts = [
            int(item["attempt"])
            for item in self._ledger.list_by_run(run_id)
            if item["schema_name"] == "AgentExecutionReceipt"
            and item["agent_role"] == role.value
        ]
        return max(attempts, default=0) + 1

    @staticmethod
    def _prompt(
        role: AgentRole,
        input_ids: tuple[str, ...],
        *,
        run_id: str,
        required_refetch_claim_ids: tuple[str, ...] = (),
        assessor_candidate: Mapping[str, object] | None = None,
        assessor_snapshot: Mapping[str, object] | None = None,
    ) -> str:
        if role is AgentRole.EVIDENCE_WATCHER:
            return "Call evidence_connector once, then return the strict EvidenceSnapshot output."
        if role is AgentRole.EVIDENCE_ASSESSOR:
            if assessor_candidate is None or assessor_snapshot is None:
                raise ContractError("ledger_integrity_failed", "assessor_binding")
            candidate_id = str(assessor_candidate.get("artifact_id", ""))
            snapshot_id = str(assessor_snapshot.get("artifact_id", ""))
            state = str(assessor_candidate.get("candidate_delta_state", ""))
            if (
                input_ids != (candidate_id, snapshot_id)
                or assessor_candidate.get("current_snapshot_id") != snapshot_id
                or state not in {"ABSENT", "PRESENT", "UNKNOWN"}
            ):
                raise ContractError("ledger_integrity_failed", "assessor_binding")
            delta_id = str(uuid5(UUID(run_id), "evidence-delta"))
            exact_fields = {
                "assessment_receipt.delta_id": delta_id,
                "evidence_delta.candidate_receipt_id": candidate_id,
                "evidence_delta.comparison": {
                    "classification_changed": "NOT_EVALUATED",
                    "classification_source_refs": [],
                },
                "evidence_delta.counter_evidence_refs": [],
                "evidence_delta.current_snapshot_id": snapshot_id,
                "evidence_delta.previous_snapshot_id": assessor_candidate.get(
                    "previous_snapshot_id"
                ),
                "evidence_delta.removed_observation_refs": [],
            }
            exact_branch_fields: dict[str, object]
            constraints: dict[str, object]
            if state == "PRESENT":
                exact_branch_fields = {}
                constraints = {
                    "evidence_delta.materiality_proposal": {
                        "not_const": "NO_CANDIDATE",
                        "type": "string",
                    }
                }
                branch_instruction = (
                    "For PRESENT, materiality_proposal must be a schema-valid "
                    "string other than NO_CANDIDATE. Constraint objects are "
                    "predicates only; never copy them into the output."
                )
            else:
                exact_branch_fields = {
                    "assessment_receipt.counter_evidence_set": [],
                    "assessment_receipt.material_claims": [],
                    "evidence_delta.added_observation_refs": [],
                    "evidence_delta.change_items": [],
                    "evidence_delta.materiality_proposal": "NO_CANDIDATE",
                }
                constraints = {}
                branch_instruction = (
                    f"For {state}, emit the strict no-candidate JSON: copy every "
                    "exact_branch_fields value literally, keep all listed arrays "
                    "empty, and set materiality_proposal to NO_CANDIDATE. Do not "
                    "propose materiality or claims."
                )
            binding_contract = json.dumps(
                {
                    "candidate_delta_state": state,
                    "constraints": constraints,
                    "exact_branch_fields": exact_branch_fields,
                    "exact_fields": exact_fields,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            return (
                "Call ledger_read for CandidateDeltaReceipt "
                f"{candidate_id} exactly once. Then return strict assessment JSON. "
                "Copy every exact_fields value literally; do not replace, omit, "
                "or contradict controller-owned values. "
                f"{branch_instruction} "
                f"BINDING_CONTRACT={binding_contract}"
            )
        claim_ids = json.dumps(
            list(required_refetch_claim_ids), separators=(",", ":")
        )
        return (
            f"Call ledger_read for AssessmentReceipt {input_ids[0]} and call "
            "refetch_metadata exactly once for each of the exact material claim "
            f"IDs {claim_ids} in the same first model turn; then return strict "
            "citation audit JSON. Empty material claims still require COMPLETE "
            "no-claim audit semantics."
        )

    @staticmethod
    def _material_claim_ids(
        assessment: Mapping[str, object],
    ) -> tuple[str, ...]:
        raw_claim_ids = assessment.get("material_claims", [])
        if not isinstance(raw_claim_ids, list):
            raise ContractError(
                "ledger_integrity_failed", "AssessmentReceipt.material_claims"
            )
        claim_ids = tuple(sorted(str(item) for item in raw_claim_ids))
        if len(set(claim_ids)) != len(claim_ids):
            raise ContractError(
                "ledger_integrity_failed", "AssessmentReceipt.material_claims"
            )
        return claim_ids

    @staticmethod
    def _verify_auditor_tool_plan(
        result: RoleRunResult,
        *,
        required_ledger_artifact_id: str | None,
        required_refetch_claim_ids: tuple[str, ...],
    ) -> None:
        if required_ledger_artifact_id is None:
            raise ContractError("ledger_integrity_failed", "auditor-ledger-plan")
        tool_ids = tuple(str(item["tool_id"]) for item in result.tool_records)
        expected_tool_ids = (
            "ledger_read",
            *("refetch_metadata" for _ in required_refetch_claim_ids),
        )
        expected_result_ids = {f"ledger:{required_ledger_artifact_id}"} | {
            f"refetch:{claim_id}" for claim_id in required_refetch_claim_ids
        }
        if (
            tool_ids.count("ledger_read") != 1
            or tuple(sorted(tool_ids)) != tuple(sorted(expected_tool_ids))
            or set(result.tool_results) != expected_result_ids
        ):
            raise RoleExecutionError(
                "agent_tool_round_trip_incomplete",
                turns=result.turns,
                http_429_count=result.http_429_count,
                tool_records=result.tool_records,
                tool_call_ids=result.tool_call_ids,
                tool_response_ids=result.tool_response_ids,
            )

    @staticmethod
    def _verify_ledger_read_target(
        result: RoleRunResult,
        *,
        required_artifact_id: str,
    ) -> None:
        tool_ids = tuple(str(item["tool_id"]) for item in result.tool_records)
        ledger_result_ids = {
            key for key in result.tool_results if key.startswith("ledger:")
        }
        expected_result_id = f"ledger:{required_artifact_id}"
        unexpected_result_ids = {
            key
            for key in result.tool_results
            if not key.startswith(("ledger:", "refetch:"))
        }
        if (
            tool_ids.count("ledger_read") != 1
            or ledger_result_ids != {expected_result_id}
            or unexpected_result_ids
        ):
            raise RoleExecutionError(
                "agent_tool_round_trip_incomplete",
                turns=result.turns,
                http_429_count=result.http_429_count,
                tool_records=result.tool_records,
                tool_call_ids=result.tool_call_ids,
                tool_response_ids=result.tool_response_ids,
            )

    @staticmethod
    def _verify_watcher_source_cursors(
        result: RoleRunResult,
        *,
        expected_source_cursors: Mapping[str, str],
    ) -> None:
        output = result.output
        tool_result = result.tool_results.get("evidence_connector")
        output_cursors = (
            output.source_cursors.model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
            if isinstance(output, EvidenceSnapshotOutput)
            else None
        )
        tool_cursors = (
            tool_result.get("source_cursors")
            if isinstance(tool_result, Mapping)
            else None
        )
        expected = dict(sorted(expected_source_cursors.items()))
        if (
            set(result.tool_results) != {"evidence_connector"}
            or output_cursors != expected
            or tool_cursors != expected
        ):
            raise RoleExecutionError(
                "agent_schema_invalid:artifact_contract:watcher_source_cursor_mismatch",
                turns=result.turns,
                http_429_count=result.http_429_count,
                tool_records=result.tool_records,
                tool_call_ids=result.tool_call_ids,
                tool_response_ids=result.tool_response_ids,
            )

    @staticmethod
    def _role_contract_failure(
        result: RoleRunResult,
        contract_code: str,
        *,
        contract_detail: str | None = None,
    ) -> RoleExecutionError:
        safe_code = safe_contract_code(contract_code)
        mismatch_suffix = ""
        if (
            safe_code == "assessor_output_binding_invalid"
            and contract_detail is not None
        ):
            fields = tuple(contract_detail.split(","))
            if (
                fields
                and fields == tuple(sorted(set(fields)))
                and all(field in ASSESSOR_OUTPUT_BINDING_FIELDS for field in fields)
            ):
                mismatch_suffix = ":" + ",".join(fields)
        return RoleExecutionError(
            "agent_schema_invalid:artifact_contract:"
            + safe_code
            + mismatch_suffix,
            turns=result.turns,
            http_429_count=result.http_429_count,
            tool_records=result.tool_records,
            tool_call_ids=result.tool_call_ids,
            tool_response_ids=result.tool_response_ids,
        )

    @staticmethod
    def _schema_failure_detail(error: Exception) -> str | None:
        if not isinstance(error, RoleExecutionError):
            return None
        mismatch_prefix = (
            "agent_schema_invalid:artifact_contract:"
            "assessor_output_binding_invalid:"
        )
        if error.code.startswith(mismatch_prefix):
            fields = tuple(error.code.removeprefix(mismatch_prefix).split(","))
            if (
                fields
                and fields == tuple(sorted(set(fields)))
                and all(field in ASSESSOR_OUTPUT_BINDING_FIELDS for field in fields)
            ):
                return (
                    "artifact_contract:assessor_output_binding_invalid:"
                    + ",".join(fields)
                )
            return "artifact_contract:assessor_output_binding_invalid"
        return safe_schema_failure_detail(error.code)
