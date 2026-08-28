from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import pytest

from recall.agents.full_audit import (
    FullAuditCoordinator,
    PreparedRunEvidence,
    RoleRunResult,
    TurnTelemetry,
)
from recall.agents.full_audit_models import FullAuditRunOutcome, RoleExecutionError
from recall.agents.full_audit_artifacts import build_started_receipt
from recall.agents.schemas import (
    AssessmentAgentOutput,
    CitationAuditOutput,
    EvidenceSnapshotOutput,
)
from recall.contracts import (
    AgentRole,
    ContractError,
    DataMode,
    ExecutionProfile,
    content_hash,
    parse_artifact,
)
from recall.contracts.enums import ScanRunEventCode
from recall.controller import Controller
from recall.controller.tool_gateway_store import InMemoryGatewayInvocationStore
from recall.ledger import InMemoryLedger
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.scheduler.model_cost import (
    DEFAULT_MODEL_COST_POLICY,
    InMemoryModelCostLedger,
)
from recall.scheduler.full_audit_phase import (
    FullAuditCaseFailure,
    FullAuditPhaseError,
    execute_full_audit_phase,
    persist_cohort_checkpoint,
)
from tests.admission import admit_watch_case, in_memory_ledger


CASE_ID = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
NOW = datetime(2026, 8, 27, 8, 0, tzinfo=UTC)


class FakeRoleRunner:
    def __init__(self) -> None:
        self.roles: list[AgentRole] = []

    async def execute(self, role, prompt, tools, context):
        self.roles.append(role)
        if role is AgentRole.EVIDENCE_WATCHER:
            tool_value = tools["evidence_connector"](
                stage="prepared", tool_context=context.tool_context("watcher-call")
            )
            assert tool_value["records"]
            output = EvidenceSnapshotOutput.model_validate(
                {
                    "effective_at": "2026-08-27T08:00:00Z",
                    "observation_ids": [],
                    "coverage_status": "PASS",
                    "source_cursors": {"clinvar": "42"},
                    "normalized_facts": {"observation_count": 1, "scope": "synthetic"},
                    "conflicts": [],
                    "snapshot_hash": "a" * 64,
                }
            )
        elif role is AgentRole.EVIDENCE_ASSESSOR:
            candidate_id = context.input_artifact_ids[0]
            assert tools["ledger_read"](
                artifact_id=candidate_id,
                tool_context=context.tool_context("assessor-call"),
            )["schema_name"] == "CandidateDeltaReceipt"
            output = AssessmentAgentOutput.model_validate(
                {
                    "evidence_delta": {
                        "candidate_receipt_id": candidate_id,
                        "previous_snapshot_id": None,
                        "current_snapshot_id": context.input_artifact_ids[1],
                        "added_observation_refs": [],
                        "removed_observation_refs": [],
                        "change_items": [],
                        "comparison": {
                            "classification_changed": "NOT_EVALUATED",
                            "classification_source_refs": [],
                        },
                        "materiality_proposal": "NO_CANDIDATE",
                        "uncertainties": [],
                        "counter_evidence_refs": [],
                    },
                    "assessment_receipt": {
                        "delta_id": "00000000-0000-4000-8000-000000000001",
                        "material_claims": [],
                        "counter_evidence_set": [],
                        "uncertainty_codes": [],
                        "schema_validation_status": "PASS",
                    },
                }
            )
        else:
            assessment_id = context.input_artifact_ids[0]
            assert tools["ledger_read"](
                artifact_id=assessment_id,
                tool_context=context.tool_context("auditor-call"),
            )["schema_name"] == "AssessmentReceipt"
            output = CitationAuditOutput.model_validate(
                {
                    "assessment_id": assessment_id,
                    "audit_status": "COMPLETE",
                    "claim_results": [],
                    "metadata_refetches": [],
                    "counter_evidence_coverage": "PASS",
                    "audit_completeness": "PASS",
                    "rejected_claim_ids": [],
                }
            )
        call_ids = {
            AgentRole.EVIDENCE_WATCHER: ("watcher-call",),
            AgentRole.EVIDENCE_ASSESSOR: ("assessor-call",),
            AgentRole.CITATION_AUDITOR: ("auditor-call",),
        }[role]
        return RoleRunResult(
            output=output,
            turns=(TurnTelemetry(1, 100, 20, 5, 125, "STOP", True, 1000),),
            tool_call_ids=call_ids,
            tool_response_ids=call_ids,
            trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
            invocation_id=context.invocation_id,
            started_at=NOW,
            completed_at=NOW + timedelta(seconds=1),
            http_429_count=0,
        )


class BarrierRoleRunner(FakeRoleRunner):
    def __init__(self) -> None:
        super().__init__()
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def execute(self, role, prompt, tools, context):
        if role is AgentRole.EVIDENCE_WATCHER:
            self.entered.set()
            await self.release.wait()
        return await super().execute(role, prompt, tools, context)


def _full_audit_run() -> tuple[InMemoryLedger, str, PreparedRunEvidence]:
    ledger = in_memory_ledger()
    controller = Controller(ledger)
    admitted, receipt, cloud_payload = admit_watch_case(
        ledger,
        controller,
        case_id=CASE_ID,
        now=NOW,
        next_scan_at="2026-08-27T08:00:00Z",
        source_cursors={"clinvar": "42"},
    )
    created = controller.create_run(
        watch_case_id=CASE_ID,
        source_cursors={"clinvar": "42"},
        schedule_epoch="2026-08-27T08:00:00Z",
        data_mode=DataMode.SYNTHETIC,
        privacy_receipt_id=str(receipt["artifact_id"]),
        expected_watch_case_version=admitted.record.version,
        triggered_at=NOW,
        budget_snapshot={
            "delegation_depth": 0,
            "specialist_invocations": 0,
            "model_calls_per_role": 2,
            "schema_repairs": 1,
            "agent_retries": 1,
            "connector_retries": 0,
            "repeated_state_limit": 2,
            "wall_time_seconds": 900,
            "step_deadlines": {"watcher": 120, "assessor": 120, "auditor": 120},
            "token_ceilings": {"watcher": 2048, "assessor": 2048, "auditor": 2048},
        },
        trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
        deadline_at="2026-08-27T08:15:00Z",
        now=NOW,
        execution_profile=ExecutionProfile.FULL_AUDIT_V1,
    ).record
    return ledger, created.run_id, PreparedRunEvidence(
        case_id=CASE_ID,
        cloud_bound_payload=cloud_payload,
        source_cursors={"clinvar": "42"},
        data_mode=DataMode.SYNTHETIC,
        replay_observations=(),
    )


def test_full_audit_executes_all_roles_and_commits_deterministic_policy() -> None:
    ledger, run_id, evidence = _full_audit_run()
    runner = FakeRoleRunner()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=runner,
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    outcome = asyncio.run(coordinator.execute_run(run_id, evidence=evidence, now=NOW))

    assert runner.roles == [
        AgentRole.EVIDENCE_WATCHER,
        AgentRole.EVIDENCE_ASSESSOR,
        AgentRole.CITATION_AUDITOR,
    ]
    assert outcome.terminal_state == "NO_ACTION"
    assert outcome.audit_status == "COMPLETE"
    assert outcome.policy_outcome == "NO_ACTION"
    assert outcome.technical_failure_codes == ()
    artifacts = ledger.list_by_run(run_id)
    assert sum(
        item["schema_name"] == "AgentExecutionReceipt" for item in artifacts
    ) == 6
    assert sum(item["schema_name"] == "CitationAuditReceipt" for item in artifacts) == 1
    assert sum(item["schema_name"] == "PolicyDecision" for item in artifacts) == 1


def test_hash_bound_exact_allele_projection_creates_present_candidate() -> None:
    ledger, run_id, evidence = _full_audit_run()
    evidence = replace(
        evidence,
        data_mode=DataMode.CAPTURED_REPLAY,
        replay_observations=(
            {
                "source": "NCBI ClinVar",
                "source_record_id": "clinvar_positive_v5",
                "retrieved_at": "2026-08-16T23:18:25Z",
                "source_version": "rcl-205:1.0.1",
                "source_locator": "https://www.ncbi.nlm.nih.gov/clinvar/variation/VCV002895953.5/",
                "source_content_hash": "d" * 64,
                "structured_fields": {
                    "semantic_anchor": "VCV002895953.5",
                    "gene": "BRCA2",
                    "transcript_hgvs": "NM_000059.4:c.7522G>C",
                    "aggregate_classification": "CONFLICTING",
                },
                "retrieval_status": "PASS",
            },
        ),
    )
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=FakeRoleRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    outcome = asyncio.run(
        coordinator.execute_run(run_id, evidence=evidence, now=NOW)
    )
    candidate = next(
        item
        for item in ledger.list_by_run(run_id)
        if item["schema_name"] == "CandidateDeltaReceipt"
    )

    assert candidate["candidate_delta_state"] == "PRESENT"
    assert candidate["exact_allele_match"] is True
    assert candidate["new_observation_hashes"] == ["d" * 64]
    assert outcome.policy_outcome == "ABSTAIN"


def test_one_case_failure_halts_only_that_run_without_policy_decision() -> None:
    ledger, run_id, evidence = _full_audit_run()

    class BrokenRunner(FakeRoleRunner):
        async def execute(self, role, prompt, tools, context):
            if role is AgentRole.EVIDENCE_ASSESSOR:
                raise TimeoutError("synthetic timeout")
            return await super().execute(role, prompt, tools, context)

    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=BrokenRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    outcome = asyncio.run(coordinator.execute_run(run_id, evidence=evidence, now=NOW))

    assert outcome.terminal_state == "HALTED"
    assert outcome.audit_status == "NOT_EVALUATED"
    assert outcome.policy_outcome is None
    assert outcome.technical_failure_codes == ("controller_failed",)
    failed_agent_receipts = [
        item
        for item in ledger.list_by_run(run_id)
        if item["schema_name"] == "AgentExecutionReceipt"
        and item["execution_status"] == "FAILED"
    ]
    assert [item["failure_code"] for item in failed_agent_receipts] == ["agent_timeout"]
    assert not any(
        item["schema_name"] == "PolicyDecision" for item in ledger.list_by_run(run_id)
    )


def test_failed_agent_receipt_uses_authoritative_failure_time() -> None:
    ledger, run_id, evidence = _full_audit_run()

    class BrokenRunner(FakeRoleRunner):
        async def execute(self, role, prompt, tools, context):
            del role, prompt, tools, context
            raise TimeoutError("synthetic delayed timeout")

    failure_at = NOW + timedelta(seconds=5)
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=BrokenRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
        clock=lambda: failure_at,
    )

    outcome = asyncio.run(
        coordinator.execute_run(run_id, evidence=evidence, now=NOW)
    )
    failed = next(
        item
        for item in ledger.list_by_run(run_id)
        if item["schema_name"] == "AgentExecutionReceipt"
        and item["execution_status"] == "FAILED"
    )

    assert outcome.terminal_state == "HALTED"
    assert failed["completed_at"] == "2026-08-27T08:00:05Z"
    assert failed["latency_ms"] == 5000


def test_expired_lease_without_takeover_cannot_be_halted_by_old_owner() -> None:
    ledger, run_id, evidence = _full_audit_run()

    class BrokenRunner(FakeRoleRunner):
        async def execute(self, role, prompt, tools, context):
            del role, prompt, tools, context
            raise TimeoutError("failure after lease expiry")

    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=BrokenRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
        lease_duration_seconds=1,
        clock=lambda: NOW + timedelta(seconds=1),
    )

    with pytest.raises(ContractError, match="lease_expired"):
        asyncio.run(coordinator.execute_run(run_id, evidence=evidence, now=NOW))

    current = ledger.get_scan_run(run_id)
    assert current is not None and current.state.value == "WATCHING"
    assert not any(
        item["schema_name"] == "FailureReceipt"
        or (
            item["schema_name"] == "AgentExecutionReceipt"
            and item["execution_status"] == "FAILED"
        )
        for item in ledger.list_by_run(run_id)
    )


def test_crash_after_terminal_commit_keeps_failed_agent_receipt_atomic() -> None:
    ledger, run_id, evidence = _full_audit_run()

    class BrokenRunner(FakeRoleRunner):
        async def execute(self, role, prompt, tools, context):
            if role is AgentRole.EVIDENCE_ASSESSOR:
                raise TimeoutError("synthetic timeout")
            return await super().execute(role, prompt, tools, context)

    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=BrokenRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )
    commit_terminal = ledger.commit_terminal

    def commit_then_crash(*args, **kwargs):
        commit_terminal(*args, **kwargs)
        raise KeyboardInterrupt("crash after terminal transaction")

    ledger.commit_terminal = commit_then_crash  # type: ignore[method-assign]
    with pytest.raises(KeyboardInterrupt, match="terminal transaction"):
        asyncio.run(coordinator.execute_run(run_id, evidence=evidence, now=NOW))

    current = ledger.get_scan_run(run_id)
    assert current is not None and current.state.value == "HALTED"
    artifacts = ledger.list_by_run(run_id)
    assert any(item["schema_name"] == "FailureReceipt" for item in artifacts)
    assert any(
        item["schema_name"] == "AgentExecutionReceipt"
        and item["execution_status"] == "FAILED"
        for item in artifacts
    )


def test_authoritative_end_to_end_deadline_halts_before_model_invocation() -> None:
    ledger, run_id, evidence = _full_audit_run()
    runner = FakeRoleRunner()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=runner,
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    outcome = asyncio.run(
        coordinator.execute_run(
            run_id,
            evidence=evidence,
            now=datetime(2026, 8, 27, 8, 15, tzinfo=UTC),
        )
    )

    assert runner.roles == []
    assert outcome.terminal_state == "HALTED"
    assert outcome.audit_status == "NOT_EVALUATED"
    assert outcome.policy_outcome is None
    assert not any(
        item["schema_name"] == "PolicyDecision"
        for item in ledger.list_by_run(run_id)
    )


def test_role_timeout_is_capped_by_remaining_end_to_end_budget() -> None:
    ledger, run_id, evidence = _full_audit_run()

    class SlowRunner(FakeRoleRunner):
        async def execute(self, role, prompt, tools, context):
            await asyncio.sleep(2)
            return await super().execute(role, prompt, tools, context)

    runner = SlowRunner()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=runner,
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
        role_timeout_seconds=300,
    )

    outcome = asyncio.run(
        coordinator.execute_run(
            run_id,
            evidence=evidence,
            now=datetime(2026, 8, 27, 8, 14, 59, tzinfo=UTC),
        )
    )

    assert runner.roles == []
    assert outcome.terminal_state == "HALTED"
    assert outcome.policy_outcome is None
    failed = [
        item
        for item in ledger.list_by_run(run_id)
        if item["schema_name"] == "AgentExecutionReceipt"
        and item["execution_status"] == "FAILED"
    ]
    assert [item["failure_code"] for item in failed] == ["agent_timeout"]


def test_open_started_attempt_is_closed_and_role_resumes_once() -> None:
    ledger, run_id, evidence = _full_audit_run()
    runner = FakeRoleRunner()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=runner,
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
        lease_duration_seconds=1,
    )
    current = coordinator._prepare_run(run_id, evidence=evidence, now=NOW)
    assert current.state.value == "WATCHING"
    scan = ledger.get_artifact(str(current.scan_run_artifact_id))
    assert scan is not None
    abandoned = build_started_receipt(
        case_id=CASE_ID,
        run_id=run_id,
        role=AgentRole.EVIDENCE_WATCHER,
        attempt=1,
        trace_id=str(scan["trace_id"]),
        invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
        data_mode=DataMode.SYNTHETIC,
        now=NOW,
    )
    ledger.append_artifact(abandoned)

    outcome = asyncio.run(
        coordinator.execute_run(
            run_id, evidence=evidence, now=NOW + timedelta(seconds=1)
        )
    )

    receipts = [
        item
        for item in ledger.list_by_run(run_id)
        if item["schema_name"] == "AgentExecutionReceipt"
    ]
    watcher = [
        item for item in receipts if item["agent_role"] == "EVIDENCE_WATCHER"
    ]
    assert outcome.terminal_state == "NO_ACTION"
    assert len(receipts) == 8
    observed = sorted(
        (item["attempt"], item["execution_status"]) for item in watcher
    )
    assert observed == [
        (1, "FAILED"),
        (1, "STARTED"),
        (2, "COMPLETED"),
        (2, "STARTED"),
    ]


def test_provider_rate_limit_halts_one_case_and_preserves_429_telemetry() -> None:
    ledger, run_id, evidence = _full_audit_run()

    class RateLimitedRunner(FakeRoleRunner):
        async def execute(self, role, prompt, tools, context):
            del role, prompt, tools, context
            raise RoleExecutionError(
                "agent_provider_call_failed",
                turns=(
                    TurnTelemetry(
                        1, 100, 0, 0, 100, "ERROR", False, 250
                    ),
                ),
                http_429_count=1,
            )

    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=RateLimitedRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    outcome = asyncio.run(
        coordinator.execute_run(run_id, evidence=evidence, now=NOW)
    )

    assert outcome.terminal_state == "HALTED"
    assert outcome.http_429_count == 1
    assert len(outcome.turns) == 1
    assert outcome.policy_decision_id is None

    replayed = asyncio.run(
        coordinator.execute_run(run_id, evidence=evidence, now=NOW)
    )
    assert replayed.turns == outcome.turns
    assert replayed.http_429_count == 1
    assert replayed.elapsed_ms == outcome.elapsed_ms


def test_cas_loser_never_converts_the_winning_step_to_halted() -> None:
    ledger, run_id, evidence = _full_audit_run()
    original = ledger.commit_agent_step

    def commit_then_report_stale(*args, **kwargs):
        original(*args, **kwargs)
        raise ContractError("stale_write_rejected", run_id)

    ledger.commit_agent_step = commit_then_report_stale  # type: ignore[method-assign]
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=FakeRoleRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    with pytest.raises(ContractError, match="stale_write_rejected"):
        asyncio.run(coordinator.execute_run(run_id, evidence=evidence, now=NOW))

    assert ledger.get_scan_run(run_id).state.value == "ASSESSING"
    assert not any(
        item["schema_name"] == "FailureReceipt"
        for item in ledger.list_by_run(run_id)
    )


def test_cohort_phase_enforces_concurrency_two_and_preserves_case_binding() -> None:
    class MeasuringCoordinator:
        cost_policy = DEFAULT_MODEL_COST_POLICY

        def __init__(self) -> None:
            self.active = 0
            self.max_active = 0

        async def execute_run(self, run_id, *, evidence, now):
            del now
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.01)
            self.active -= 1
            ids = tuple(
                str(uuid5(NAMESPACE_URL, f"{run_id}:receipt:{index}"))
                for index in range(6)
            )
            return FullAuditRunOutcome(
                evidence.case_id,
                run_id,
                "NO_ACTION",
                "COMPLETE",
                str(uuid5(NAMESPACE_URL, f"{run_id}:audit")),
                str(uuid5(NAMESPACE_URL, f"{run_id}:policy")),
                "NO_ACTION",
                ("no_candidate_delta",),
                (),
                (),
                ids,
                10,
                (TurnTelemetry(1, 10, 2, 1, 13, "STOP", True, 5),),
                0,
            )

        def cost_snapshot(self):
            return SimpleNamespace(
                reserved_usd_micros=100, reconciled_usd_micros=80
            )

    cases = []
    prepared = []
    for index in range(7):
        case_id = str(uuid5(NAMESPACE_URL, f"case:{index}"))
        run_id = str(uuid5(NAMESPACE_URL, f"run:{index}"))
        cases.append(
            SimpleNamespace(
                    case=SimpleNamespace(
                        case_id=case_id,
                        vcv=None,
                        data_mode=DataMode.SYNTHETIC,
                    ),
                run_record=SimpleNamespace(run_id=run_id, updated_at=NOW),
                watch_record=SimpleNamespace(source_cursors={"clinvar": str(index)}),
            )
        )
        prepared.append(
            SimpleNamespace(
                case_id=case_id,
                cycle_id="c3",
                cloud_bound_payload={"case_token": case_id},
            )
        )
    coordinator = MeasuringCoordinator()
    phase = execute_full_audit_phase(
        tuple(cases),
        coordinator=coordinator,  # type: ignore[arg-type]
        bundle=SimpleNamespace(cases=tuple(prepared), observations_by_vcv={}),
        cycle=SimpleNamespace(cycle_id="c3"),
    )

    assert coordinator.max_active == 2
    assert len(phase.outcomes) == 7
    assert phase.summary["complete_runs"] == 7
    assert phase.summary["concurrency"] == 2


def test_cohort_phase_derives_replay_mode_from_production_shaped_case() -> None:
    class CapturingCoordinator:
        cost_policy = DEFAULT_MODEL_COST_POLICY

        def __init__(self) -> None:
            self.modes = []

        async def execute_run(self, run_id, *, evidence, now):
            del now
            self.modes.append(evidence.data_mode)
            ids = tuple(
                str(uuid5(NAMESPACE_URL, f"{run_id}:receipt:{index}"))
                for index in range(6)
            )
            return FullAuditRunOutcome(
                evidence.case_id, run_id, "NO_ACTION", "COMPLETE",
                str(uuid5(NAMESPACE_URL, f"{run_id}:audit")),
                str(uuid5(NAMESPACE_URL, f"{run_id}:policy")),
                "NO_ACTION", ("no_candidate_delta",), (), (), ids, 10, (), 0,
            )

        def cost_snapshot(self):
            return SimpleNamespace(
                reserved_usd_micros=0, reconciled_usd_micros=0
            )

    case_id = str(uuid5(NAMESPACE_URL, "replay-case"))
    run_id = str(uuid5(NAMESPACE_URL, "replay-run"))
    coordinator = CapturingCoordinator()
    execute_full_audit_phase(
        (
            SimpleNamespace(
                case=SimpleNamespace(
                    case_id=case_id,
                    vcv="VCV0001",
                    data_mode=DataMode.SYNTHETIC,
                ),
                run_record=SimpleNamespace(run_id=run_id, updated_at=NOW),
                watch_record=SimpleNamespace(source_cursors={"clinvar": "42"}),
            ),
        ),
        coordinator=coordinator,  # type: ignore[arg-type]
        bundle=SimpleNamespace(
            cases=(
                SimpleNamespace(
                    case_id=case_id,
                    cycle_id="c3",
                    cloud_bound_payload={"case_token": case_id},
                ),
            ),
            observations_by_vcv={"VCV0001": {"source": "captured"}},
        ),
        cycle=SimpleNamespace(cycle_id="c3"),
    )

    assert coordinator.modes == [DataMode.CAPTURED_REPLAY]


def test_active_lease_refuses_duplicate_dispatch_without_halting_winner() -> None:
    ledger, run_id, evidence = _full_audit_run()
    runner = BarrierRoleRunner()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=runner,
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    async def exercise():
        winner = asyncio.create_task(
            coordinator.execute_run(run_id, evidence=evidence, now=NOW)
        )
        await runner.entered.wait()
        duplicate = asyncio.create_task(
            coordinator.execute_run(
                run_id, evidence=evidence, now=NOW + timedelta(seconds=1)
            )
        )
        await asyncio.sleep(0)
        runner.release.set()
        return await asyncio.gather(winner, duplicate, return_exceptions=True)

    results = asyncio.run(exercise())
    assert sum(isinstance(item, FullAuditRunOutcome) for item in results) == 1
    rejected = next(item for item in results if isinstance(item, ContractError))
    assert rejected.code == "lease_active"
    assert runner.roles == [
        AgentRole.EVIDENCE_WATCHER,
        AgentRole.EVIDENCE_ASSESSOR,
        AgentRole.CITATION_AUDITOR,
    ]
    assert ledger.get_scan_run(run_id).state.value != "HALTED"
    receipts = [
        item
        for item in ledger.list_by_run(run_id)
        if item["schema_name"] == "AgentExecutionReceipt"
    ]
    assert all(item["execution_status"] != "FAILED" for item in receipts)


def test_routing_receipt_is_reused_byte_for_byte_after_expired_takeover() -> None:
    ledger, run_id, evidence = _full_audit_run()
    controller = Controller(ledger)
    queued = controller.transition(
        run_id,
        expected_version=1,
        lease_epoch=0,
        event_code=ScanRunEventCode.OUTBOX_PUBLISHED,
        now=NOW,
    )
    routing = controller.acquire_lease(
        run_id,
        expected_version=queued.version,
        new_epoch=1,
        expires_at=NOW + timedelta(seconds=1),
        now=NOW,
    )
    from recall.agents.full_audit_artifacts import build_registry_receipt

    receipt = build_registry_receipt(
        case_id=evidence.case_id,
        run_id=run_id,
        data_mode=evidence.data_mode,
        now=NOW,
    )
    ledger.append_artifact(receipt)
    before = ledger.get_artifact(str(receipt["artifact_id"]))
    runner = FakeRoleRunner()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=runner,
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )
    outcome = asyncio.run(
        coordinator.execute_run(
            run_id, evidence=evidence, now=NOW + timedelta(seconds=1)
        )
    )

    assert routing.state.value == "ROUTING"
    assert outcome.terminal_state != "HALTED"
    assert ledger.get_artifact(str(receipt["artifact_id"])) == before
    takeover_events = [
        event
        for event in ledger.list_scan_run_events(run_id)
        if event.event_code is ScanRunEventCode.LEASE_TAKEN_OVER
    ]
    assert len(takeover_events) == 1


def test_hard_crash_after_data_mode_append_resumes_byte_identically() -> None:
    ledger, run_id, evidence = _full_audit_run()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=FakeRoleRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
        lease_duration_seconds=60,
    )
    evaluate = coordinator._controller.evaluate_and_commit
    crashed = False

    def crash_once(*args, **kwargs):
        nonlocal crashed
        if not crashed:
            crashed = True
            raise KeyboardInterrupt("hard crash after data-mode append")
        return evaluate(*args, **kwargs)

    coordinator._controller.evaluate_and_commit = crash_once  # type: ignore[method-assign]
    with pytest.raises(KeyboardInterrupt, match="hard crash"):
        asyncio.run(coordinator.execute_run(run_id, evidence=evidence, now=NOW))
    before = next(
        item
        for item in ledger.list_by_run(run_id)
        if item["schema_name"] == "DataModeReceipt"
    )

    outcome = asyncio.run(
        coordinator.execute_run(
            run_id, evidence=evidence, now=NOW + timedelta(seconds=60)
        )
    )
    receipts = [
        item
        for item in ledger.list_by_run(run_id)
        if item["schema_name"] == "DataModeReceipt"
    ]

    assert outcome.terminal_state == "NO_ACTION"
    assert receipts == [before]


def test_expired_old_worker_cannot_halt_new_lease_owner() -> None:
    ledger, run_id, evidence = _full_audit_run()
    controller = Controller(ledger)

    class LeaseStealingRunner(FakeRoleRunner):
        async def execute(self, role, prompt, tools, context):
            current = ledger.get_scan_run(run_id)
            assert current is not None
            controller.acquire_lease(
                run_id,
                expected_version=current.version,
                new_epoch=current.lease_epoch + 1,
                expires_at=NOW + timedelta(seconds=2),
                now=NOW + timedelta(seconds=1),
            )
            raise TimeoutError("old worker failed after ownership changed")

    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=LeaseStealingRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
        lease_duration_seconds=1,
        clock=lambda: NOW + timedelta(seconds=2),
    )

    with pytest.raises(ContractError, match="stale_write_rejected"):
        asyncio.run(coordinator.execute_run(run_id, evidence=evidence, now=NOW))

    current = ledger.get_scan_run(run_id)
    assert current is not None
    assert current.state.value == "WATCHING"
    assert current.lease_epoch == 2
    assert not any(
        item["schema_name"] == "FailureReceipt"
        for item in ledger.list_by_run(run_id)
    )
    assert not any(
        item["schema_name"] == "AgentExecutionReceipt"
        and item["execution_status"] == "FAILED"
        for item in ledger.list_by_run(run_id)
    )


def test_queued_case_uses_semaphore_entry_clock_for_fresh_lease() -> None:
    class ClockCoordinator:
        cost_policy = DEFAULT_MODEL_COST_POLICY

        def __init__(self) -> None:
            self.observed: list[datetime] = []

        async def execute_run(self, run_id, *, evidence, now):
            self.observed.append(now)
            return FullAuditRunOutcome(
                evidence.case_id, run_id, "NO_ACTION", "COMPLETE",
                str(uuid5(NAMESPACE_URL, f"{run_id}:audit")),
                str(uuid5(NAMESPACE_URL, f"{run_id}:policy")),
                "NO_ACTION", (), (), (), (), 0, (), 0,
            )

        def cost_snapshot(self):
            return SimpleNamespace(
                reserved_usd_micros=0, reconciled_usd_micros=0
            )

    case_id = str(uuid5(NAMESPACE_URL, "lease-clock-case"))
    run_id = str(uuid5(NAMESPACE_URL, "lease-clock-run"))
    entered_at = NOW + timedelta(minutes=20)
    coordinator = ClockCoordinator()
    execute_full_audit_phase(
        (
            SimpleNamespace(
                case=SimpleNamespace(
                    case_id=case_id, vcv=None, data_mode=DataMode.SYNTHETIC
                ),
                run_record=SimpleNamespace(run_id=run_id, updated_at=NOW),
                watch_record=SimpleNamespace(source_cursors={"synthetic": "1"}),
            ),
        ),
        coordinator=coordinator,  # type: ignore[arg-type]
        bundle=SimpleNamespace(
            cases=(
                SimpleNamespace(
                    case_id=case_id,
                    cycle_id="c3",
                    cloud_bound_payload={"case_token": case_id},
                ),
            ),
            observations_by_vcv={},
        ),
        cycle=SimpleNamespace(cycle_id="c3"),
        clock=lambda: entered_at,
    )

    assert coordinator.observed == [entered_at]


def test_queued_case_at_agent_deadline_invokes_no_model_role() -> None:
    ledger, run_id, evidence = _full_audit_run()
    runner = FakeRoleRunner()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=runner,
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )
    phase = execute_full_audit_phase(
        (
            SimpleNamespace(
                case=SimpleNamespace(
                    case_id=evidence.case_id,
                    vcv=None,
                    data_mode=DataMode.SYNTHETIC,
                ),
                run_record=SimpleNamespace(run_id=run_id, updated_at=NOW),
                watch_record=SimpleNamespace(
                    source_cursors=evidence.source_cursors
                ),
            ),
        ),
        coordinator=coordinator,
        bundle=SimpleNamespace(
            cases=(
                SimpleNamespace(
                    case_id=evidence.case_id,
                    cycle_id="c3",
                    cloud_bound_payload=evidence.cloud_bound_payload,
                ),
            ),
            observations_by_vcv={},
        ),
        cycle=SimpleNamespace(cycle_id="c3"),
        clock=lambda: NOW,
        agent_deadline_at=NOW,
    )

    assert runner.roles == []
    assert phase.outcomes[0].terminal_state == "HALTED"
    assert phase.outcomes[0].audit_status == "NOT_EVALUATED"


def test_cohort_waits_for_unrelated_cases_before_reporting_integrity_failure() -> None:
    class PartiallyBrokenCoordinator:
        cost_policy = DEFAULT_MODEL_COST_POLICY

        def __init__(self) -> None:
            self.observed: list[str] = []

        async def execute_run(self, run_id, *, evidence, now):
            del now
            self.observed.append(evidence.case_id)
            await asyncio.sleep(0.01)
            if evidence.case_id.endswith("1"):
                raise ContractError("stale_write_rejected", run_id)
            return FullAuditRunOutcome(
                evidence.case_id, run_id, "NO_ACTION", "COMPLETE",
                str(uuid5(NAMESPACE_URL, f"{run_id}:audit")),
                str(uuid5(NAMESPACE_URL, f"{run_id}:policy")),
                "NO_ACTION", (), (), (), (), 0, (), 0,
            )

        def cost_snapshot(self):
            return SimpleNamespace(
                reserved_usd_micros=0, reconciled_usd_micros=0
            )

    coordinator = PartiallyBrokenCoordinator()
    cases = []
    prepared = []
    for suffix in ("0", "1", "2"):
        case_id = f"00000000-0000-4000-8000-00000000000{suffix}"
        run_id = str(uuid5(NAMESPACE_URL, f"isolation:{suffix}"))
        cases.append(
            SimpleNamespace(
                case=SimpleNamespace(
                    case_id=case_id, vcv=None, data_mode=DataMode.SYNTHETIC
                ),
                run_record=SimpleNamespace(run_id=run_id, updated_at=NOW),
                watch_record=SimpleNamespace(source_cursors={"synthetic": suffix}),
            )
        )
        prepared.append(
            SimpleNamespace(
                case_id=case_id,
                cycle_id="c3",
                cloud_bound_payload={"case_token": case_id},
            )
        )

    checkpoint_ledger = InMemoryLedger()
    with pytest.raises(
        RuntimeError, match="full_audit_checkpoint_outcome_unbound"
    ):
        execute_full_audit_phase(
            tuple(cases),
            coordinator=coordinator,  # type: ignore[arg-type]
            bundle=SimpleNamespace(
                cases=tuple(prepared), observations_by_vcv={}
            ),
            cycle=SimpleNamespace(cycle_id="c3"),
            checkpoint_ledger=checkpoint_ledger,
            plan_sha256="a" * 64,
            expected_manifest_id="00000000-0000-4000-8000-000000000101",
            checkpoint_run_id="00000000-0000-4000-8000-000000000102",
            clock=lambda: NOW,
        )

    assert set(coordinator.observed) == {
        "00000000-0000-4000-8000-000000000000",
        "00000000-0000-4000-8000-000000000001",
        "00000000-0000-4000-8000-000000000002",
    }
    assert not any(
        item["schema_name"] == "CohortExecutionCheckpoint"
        for item in checkpoint_ledger._artifacts.values()
    )


def test_checkpoint_binds_genuine_terminal_artifacts_and_reuses_exact_bytes() -> None:
    ledger, run_id, evidence = _full_audit_run()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=FakeRoleRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )
    outcome = asyncio.run(
        coordinator.execute_run(run_id, evidence=evidence, now=NOW)
    )
    failure = FullAuditCaseFailure(
        "00000000-0000-4000-8000-000000000099",
        "00000000-0000-4000-8000-000000000098",
        "stale_write_rejected",
    )
    checkpoint = persist_cohort_checkpoint(
        ledger=ledger,
        plan_sha256="a" * 64,
        cycle=SimpleNamespace(cycle_id="c3"),
        expected_manifest_id="00000000-0000-4000-8000-000000000101",
        checkpoint_run_id="00000000-0000-4000-8000-000000000102",
        total_cases=2,
        completed=(outcome,),
        failures=(failure,),
        detected_at=NOW,
    )
    parsed = parse_artifact(
        checkpoint, authorized_producers=PRODUCER_REGISTRY
    )
    assert parsed.payload.policy_outcomes_synthesized is False
    assert len(parsed.payload.completed_outcomes) == 1
    assert len(parsed.payload.failed_cases) == 1
    pointer = ledger.get_scan_run(run_id)
    assert pointer is not None
    assert str(pointer.scan_run_artifact_id) in checkpoint["input_artifact_ids"]

    replay = persist_cohort_checkpoint(
        ledger=ledger,
        plan_sha256="a" * 64,
        cycle=SimpleNamespace(cycle_id="c3"),
        expected_manifest_id="00000000-0000-4000-8000-000000000101",
        checkpoint_run_id="00000000-0000-4000-8000-000000000102",
        total_cases=2,
        completed=(outcome,),
        failures=(failure,),
        detected_at=NOW + timedelta(days=1),
    )
    assert replay == checkpoint

    invalid = deepcopy(checkpoint)
    invalid["completed_outcomes"][0]["terminal_state"] = "RUNNING"
    invalid["content_hash"] = content_hash(invalid)
    with pytest.raises(ContractError, match="contract_enum_invalid"):
        parse_artifact(invalid, authorized_producers=PRODUCER_REGISTRY)

    missing_scan_input = deepcopy(checkpoint)
    missing_scan_input["input_artifact_ids"] = [
        item
        for item in missing_scan_input["input_artifact_ids"]
        if item != str(pointer.scan_run_artifact_id)
    ]
    missing_scan_input["content_hash"] = content_hash(missing_scan_input)
    ledger._artifacts[str(checkpoint["artifact_id"])] = missing_scan_input
    with pytest.raises(
        RuntimeError, match="full_audit_checkpoint_reconciliation_failed"
    ):
        persist_cohort_checkpoint(
            ledger=ledger,
            plan_sha256="a" * 64,
            cycle=SimpleNamespace(cycle_id="c3"),
            expected_manifest_id="00000000-0000-4000-8000-000000000101",
            checkpoint_run_id="00000000-0000-4000-8000-000000000102",
            total_cases=2,
            completed=(outcome,),
            failures=(failure,),
            detected_at=NOW + timedelta(days=2),
        )
    ledger._artifacts[str(checkpoint["artifact_id"])] = checkpoint

    ledger._artifacts.pop(outcome.policy_decision_id)
    with pytest.raises(
        RuntimeError, match="full_audit_checkpoint_outcome_unbound"
    ):
        persist_cohort_checkpoint(
            ledger=ledger,
            plan_sha256="a" * 64,
            cycle=SimpleNamespace(cycle_id="c3"),
            expected_manifest_id="00000000-0000-4000-8000-000000000101",
            checkpoint_run_id="00000000-0000-4000-8000-000000000102",
            total_cases=2,
            completed=(outcome,),
            failures=(failure,),
            detected_at=NOW + timedelta(days=2),
        )
