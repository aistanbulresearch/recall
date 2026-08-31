from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
from types import SimpleNamespace
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
import recall.agents.full_audit as full_audit_module
from google.adk.models import BaseLlm
from google.adk.models._capabilities import LlmCapabilities
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import PrivateAttr

from recall.agents.full_audit import (
    FullAuditCoordinator,
    PreparedRunEvidence,
    RoleRunResult,
    TurnTelemetry,
)
from recall.agents.full_audit_models import (
    MAX_MODEL_TURNS_PER_ROLE,
    FullAuditRunOutcome,
    RoleExecutionError,
)
from recall.agents.full_audit_artifacts import (
    build_failed_receipt,
    build_started_receipt,
)
from recall.agents.in_process_runtime import InProcessAdkRoleRunner
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
    projected_cost_micros,
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


async def _no_sleep(_seconds: float) -> None:
    return None


class ToolThenRateLimitedLlm(BaseLlm):
    """Complete one real FunctionTool turn, then fail every final-answer call."""

    _calls: int = PrivateAttr(default=0)

    def __init__(self) -> None:
        super().__init__(model="gemini-3.7-flash")

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del llm_request, stream
        self._calls += 1
        if self._calls == 1:
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part.from_function_call(
                            name="evidence_connector",
                            args={},
                        )
                    ],
                ),
                partial=False,
            )
            return
        raise RuntimeError("429 ResourceExhausted")
        yield  # pragma: no cover - keeps the async-generator contract


class FakeRoleRunner:
    def __init__(self) -> None:
        self.roles: list[AgentRole] = []
        self.assessor_prompt = ""

    async def execute(self, role, prompt, tools, context):
        self.roles.append(role)
        tool_results = {}
        if role is AgentRole.EVIDENCE_WATCHER:
            tool_value = tools["evidence_connector"](
                stage="prepared", tool_context=context.tool_context("watcher-call")
            )
            assert tool_value["records"]
            tool_results["evidence_connector"] = tool_value
            output = EvidenceSnapshotOutput.model_validate(
                {
                    "effective_at": "2026-08-27T08:00:00Z",
                    "observation_ids": [],
                    "coverage_status": "PASS",
                    "source_cursors": tool_value["source_cursors"],
                    "normalized_facts": {"observation_count": 1, "scope": "synthetic"},
                    "conflicts": [],
                    "snapshot_hash": "a" * 64,
                }
            )
        elif role is AgentRole.EVIDENCE_ASSESSOR:
            self.assessor_prompt = prompt
            candidate_id = context.input_artifact_ids[0]
            tool_results[f"ledger:{candidate_id}"] = tools["ledger_read"](
                artifact_id=candidate_id,
                tool_context=context.tool_context("assessor-call"),
            )
            assert (
                tool_results[f"ledger:{candidate_id}"]["schema_name"]
                == "CandidateDeltaReceipt"
            )
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
                        "delta_id": str(
                            uuid5(UUID(context.run_id), "evidence-delta")
                        ),
                        "material_claims": [],
                        "counter_evidence_set": [],
                        "uncertainty_codes": [],
                        "schema_validation_status": "PASS",
                    },
                }
            )
        else:
            assessment_id = context.input_artifact_ids[0]
            tool_results[f"ledger:{assessment_id}"] = tools["ledger_read"](
                artifact_id=assessment_id,
                tool_context=context.tool_context("auditor-call"),
            )
            assert (
                tool_results[f"ledger:{assessment_id}"]["schema_name"]
                == "AssessmentReceipt"
            )
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
            tool_results=tool_results,
        )


class MaterialClaimToolPlanRunner(FakeRoleRunner):
    def __init__(
        self,
        refetch_claim_ids: tuple[str, ...],
        *,
        assessor_ledger_indexes: tuple[int, ...] = (0,),
        auditor_ledger_indexes: tuple[int, ...] = (0,),
    ) -> None:
        super().__init__()
        self.refetch_claim_ids = refetch_claim_ids
        self.assessor_ledger_indexes = assessor_ledger_indexes
        self.auditor_ledger_indexes = auditor_ledger_indexes
        self.auditor_prompt = ""

    async def execute(self, role, prompt, tools, context):
        if role is AgentRole.EVIDENCE_WATCHER:
            return await super().execute(role, prompt, tools, context)
        self.roles.append(role)
        if role is AgentRole.EVIDENCE_ASSESSOR:
            self.assessor_prompt = prompt
            candidate_id, snapshot_id = context.input_artifact_ids
            tool_results = {}
            call_ids = []
            for index, artifact_index in enumerate(
                self.assessor_ledger_indexes, start=1
            ):
                artifact_id = context.input_artifact_ids[artifact_index]
                call_id = f"assessor-call-{index}"
                tool_results[f"ledger:{artifact_id}"] = tools["ledger_read"](
                    artifact_id=artifact_id,
                    tool_context=context.tool_context(call_id),
                )
                call_ids.append(call_id)
            return RoleRunResult(
                output=AssessmentAgentOutput.model_validate(
                    {
                        "evidence_delta": {
                            "candidate_receipt_id": candidate_id,
                            "previous_snapshot_id": None,
                            "current_snapshot_id": snapshot_id,
                            "added_observation_refs": [],
                            "removed_observation_refs": [],
                            "change_items": [{"claim_id": "claim-1"}],
                            "comparison": {
                                "classification_changed": "NOT_EVALUATED",
                                "classification_source_refs": [],
                            },
                            "materiality_proposal": "MATERIAL",
                            "uncertainties": [],
                            "counter_evidence_refs": [],
                        },
                        "assessment_receipt": {
                            "delta_id": str(
                                uuid5(UUID(context.run_id), "evidence-delta")
                            ),
                            "material_claims": ["claim-1"],
                            "counter_evidence_set": [],
                            "uncertainty_codes": [],
                            "schema_validation_status": "PASS",
                        },
                    }
                ),
                turns=(TurnTelemetry(1, 100, 20, 5, 125, "STOP", True, 10),),
                tool_call_ids=tuple(call_ids),
                tool_response_ids=tuple(call_ids),
                trace_id=context.trace_id,
                invocation_id=context.invocation_id,
                started_at=NOW,
                completed_at=NOW + timedelta(seconds=1),
                http_429_count=0,
                tool_results=tool_results,
            )
        self.auditor_prompt = prompt
        assessment_id = context.input_artifact_ids[0]
        tool_results = {}
        ledger_call_ids = []
        for index, artifact_index in enumerate(
            self.auditor_ledger_indexes, start=1
        ):
            artifact_id = context.input_artifact_ids[artifact_index]
            call_id = f"auditor-ledger-{index}"
            tool_results[f"ledger:{artifact_id}"] = tools["ledger_read"](
                artifact_id=artifact_id,
                tool_context=context.tool_context(call_id),
            )
            ledger_call_ids.append(call_id)
        for index, claim_id in enumerate(self.refetch_claim_ids, start=1):
            tool_results[f"refetch:{claim_id}"] = tools["refetch_metadata"](
                claim_id=claim_id,
                tool_context=context.tool_context(f"auditor-refetch-{index}"),
            )
        call_ids = (
            *ledger_call_ids,
            *(f"auditor-refetch-{index}" for index in range(1, len(self.refetch_claim_ids) + 1)),
        )
        return RoleRunResult(
            output=CitationAuditOutput.model_validate(
                {
                    "assessment_id": assessment_id,
                    "audit_status": "COMPLETE",
                    "claim_results": [
                        {
                            "claim_id": "claim-1",
                            "cited_identifier": "claim-1",
                            "reason_codes": ["citation_source_binding_missing"],
                            "refetched_source": None,
                        }
                    ],
                    "metadata_refetches": [],
                    "counter_evidence_coverage": "PASS",
                    "audit_completeness": "PASS",
                    "rejected_claim_ids": ["claim-1"],
                }
            ),
            turns=(TurnTelemetry(1, 100, 20, 5, 125, "STOP", True, 10),),
            tool_call_ids=call_ids,
            tool_response_ids=call_ids,
            trace_id=context.trace_id,
            invocation_id=context.invocation_id,
            started_at=NOW,
            completed_at=NOW + timedelta(seconds=1),
            http_429_count=0,
            tool_results=tool_results,
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
        source_cursors={"synthetic-source": "cursor-001"},
    )
    created = controller.create_run(
        watch_case_id=CASE_ID,
        source_cursors={"synthetic-source": "cursor-001"},
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
        source_cursors={"synthetic-source": "cursor-001"},
        data_mode=DataMode.SYNTHETIC,
        replay_observations=(),
    )


def _material_claim_evidence(
    evidence: PreparedRunEvidence,
) -> PreparedRunEvidence:
    return replace(
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


def _unknown_candidate_evidence(
    evidence: PreparedRunEvidence,
) -> PreparedRunEvidence:
    return replace(
        evidence,
        data_mode=DataMode.CAPTURED_REPLAY,
        replay_observations=(
            {
                "source": "NCBI ClinVar",
                "source_record_id": "projection-unavailable",
                "retrieved_at": "2026-08-16T23:18:25Z",
                "source_version": "rcl-205:1.0.1",
                "source_locator": "bundle://projection-unavailable",
                "source_content_hash": "e" * 64,
                "structured_fields": {
                    "semantic_anchor": "VCV-PROJECTION-UNAVAILABLE",
                    "aggregate_classification": "NOT_EVALUATED",
                },
                "retrieval_status": "PASS",
            },
        ),
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
    assert json.loads(runner.assessor_prompt.split("BINDING_CONTRACT=", 1)[1])[
        "candidate_delta_state"
    ] == "ABSENT"
    artifacts = ledger.list_by_run(run_id)
    assert sum(
        item["schema_name"] == "AgentExecutionReceipt" for item in artifacts
    ) == 6
    assert sum(item["schema_name"] == "CitationAuditReceipt" for item in artifacts) == 1
    assert sum(item["schema_name"] == "PolicyDecision" for item in artifacts) == 1


def test_two_turn_cost_contract_reserves_and_reconciles_every_role_turn() -> None:
    assert MAX_MODEL_TURNS_PER_ROLE == 2
    ledger, run_id, evidence = _full_audit_run()
    inner = InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000)

    class RecordingCostLedger:
        def __init__(self) -> None:
            self.reserved: list[str] = []
            self.reconciled: list[tuple[str, int]] = []

        def reserve(self, reservation_id, worst_case_usd_micros):
            self.reserved.append(reservation_id)
            return inner.reserve(reservation_id, worst_case_usd_micros)

        def reconcile(self, reservation_id, *, actual_usd_micros):
            self.reconciled.append((reservation_id, actual_usd_micros))
            inner.reconcile(
                reservation_id, actual_usd_micros=actual_usd_micros
            )

        def snapshot(self):
            return inner.snapshot()

    cost = RecordingCostLedger()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=FakeRoleRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=cost,
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    outcome = asyncio.run(
        coordinator.execute_run(run_id, evidence=evidence, now=NOW)
    )

    expected_ids = [
        f"{run_id}:{role.value}:1:{turn}"
        for role in (
            AgentRole.EVIDENCE_WATCHER,
            AgentRole.EVIDENCE_ASSESSOR,
            AgentRole.CITATION_AUDITOR,
        )
        for turn in range(1, MAX_MODEL_TURNS_PER_ROLE + 1)
    ]
    one_turn_actual = projected_cost_micros(
        prompt_tokens=100,
        candidate_tokens=20,
        thoughts_tokens=5,
        policy=DEFAULT_MODEL_COST_POLICY,
    )
    assert outcome.terminal_state == "NO_ACTION"
    assert cost.reserved == expected_ids
    assert [item[0] for item in cost.reconciled] == expected_ids
    assert [item[1] for item in cost.reconciled] == [
        value for _role in range(3) for value in (one_turn_actual, 0)
    ]
    assert cost.snapshot().reserved_usd_micros == one_turn_actual * 3
    assert cost.snapshot().reconciled_usd_micros == one_turn_actual * 3


def test_material_claim_auditor_plan_is_prompt_bound_and_cost_bounded() -> None:
    ledger, run_id, evidence = _full_audit_run()
    evidence = _material_claim_evidence(evidence)
    inner = InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000)

    class RecordingCostLedger:
        def __init__(self) -> None:
            self.reserved: list[str] = []
            self.reconciled: list[str] = []

        def reserve(self, reservation_id, worst_case_usd_micros):
            self.reserved.append(reservation_id)
            return inner.reserve(reservation_id, worst_case_usd_micros)

        def reconcile(self, reservation_id, *, actual_usd_micros):
            self.reconciled.append(reservation_id)
            inner.reconcile(
                reservation_id, actual_usd_micros=actual_usd_micros
            )

        def snapshot(self):
            return inner.snapshot()

    runner = MaterialClaimToolPlanRunner(("claim-1",))
    cost = RecordingCostLedger()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=runner,
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=cost,
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    outcome = asyncio.run(
        coordinator.execute_run(run_id, evidence=evidence, now=NOW)
    )
    auditor_receipt = next(
        item
        for item in ledger.list_by_run(run_id)
        if item["schema_name"] == "AgentExecutionReceipt"
        and item["agent_role"] == AgentRole.CITATION_AUDITOR.value
        and item["execution_status"] == "COMPLETED"
    )
    auditor_reservations = [
        item
        for item in cost.reserved
        if f":{AgentRole.CITATION_AUDITOR.value}:" in item
    ]

    assert 'exact material claim IDs ["claim-1"]' in runner.auditor_prompt
    assert "same first model turn" in runner.auditor_prompt
    assert outcome.terminal_state == "ABSTAIN"
    assert [item["tool_id"] for item in auditor_receipt["tool_records"]] == [
        "ledger_read",
        "refetch_metadata",
    ]
    assert len(auditor_reservations) == MAX_MODEL_TURNS_PER_ROLE
    assert all(item in cost.reconciled for item in auditor_reservations)


@pytest.mark.parametrize(
    "refetch_claim_ids",
    [(), ("claim-1", "unexpected-claim")],
    ids=("missing", "extra"),
)
def test_auditor_missing_or_extra_refetch_halts_without_policy(
    refetch_claim_ids: tuple[str, ...],
) -> None:
    ledger, run_id, evidence = _full_audit_run()
    evidence = _material_claim_evidence(evidence)
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=MaterialClaimToolPlanRunner(refetch_claim_ids),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(
            hard_cap_usd_micros=75_000_000
        ),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    outcome = asyncio.run(
        coordinator.execute_run(run_id, evidence=evidence, now=NOW)
    )
    artifacts = ledger.list_by_run(run_id)
    failed = next(
        item
        for item in artifacts
        if item["schema_name"] == "AgentExecutionReceipt"
        and item["agent_role"] == AgentRole.CITATION_AUDITOR.value
        and item["execution_status"] == "FAILED"
    )

    assert outcome.terminal_state == "HALTED"
    assert outcome.policy_decision_id is None
    assert failed["failure_code"] == "controller_failed"
    assert failed["turns"]
    assert not any(item["schema_name"] == "PolicyDecision" for item in artifacts)


@pytest.mark.parametrize(
    ("role", "ledger_indexes"),
    [
        (AgentRole.EVIDENCE_ASSESSOR, (1,)),
        (AgentRole.EVIDENCE_ASSESSOR, (0, 0)),
        (AgentRole.EVIDENCE_ASSESSOR, ()),
        (AgentRole.EVIDENCE_ASSESSOR, (0, 1)),
        (AgentRole.CITATION_AUDITOR, (1,)),
        (AgentRole.CITATION_AUDITOR, (0, 0)),
        (AgentRole.CITATION_AUDITOR, ()),
        (AgentRole.CITATION_AUDITOR, (0, 1)),
    ],
    ids=(
        "assessor-wrong-target",
        "assessor-duplicate",
        "assessor-omitted",
        "assessor-mixed",
        "auditor-wrong-target",
        "auditor-duplicate",
        "auditor-omitted",
        "auditor-mixed",
    ),
)
def test_role_ledger_read_must_match_exact_controller_supplied_artifact(
    role: AgentRole,
    ledger_indexes: tuple[int, ...],
) -> None:
    ledger, run_id, evidence = _full_audit_run()
    evidence = _material_claim_evidence(evidence)
    runner = MaterialClaimToolPlanRunner(
        ("claim-1",),
        assessor_ledger_indexes=(
            ledger_indexes
            if role is AgentRole.EVIDENCE_ASSESSOR
            else (0,)
        ),
        auditor_ledger_indexes=(
            ledger_indexes
            if role is AgentRole.CITATION_AUDITOR
            else (0,)
        ),
    )
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=runner,
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(
            hard_cap_usd_micros=75_000_000
        ),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    outcome = asyncio.run(
        coordinator.execute_run(run_id, evidence=evidence, now=NOW)
    )
    failed = next(
        item
        for item in ledger.list_by_run(run_id)
        if item["schema_name"] == "AgentExecutionReceipt"
        and item["agent_role"] == role.value
        and item["execution_status"] == "FAILED"
    )

    assert outcome.terminal_state == "HALTED"
    assert outcome.policy_decision_id is None
    assert failed["failure_code"] == "controller_failed"
    assert failed["turns"]
    assert not any(
        item["schema_name"] == "PolicyDecision"
        for item in ledger.list_by_run(run_id)
    )


@pytest.mark.parametrize(
    ("runtime_code", "warning_detail"),
    [
        ("agent_response_missing:response_missing", "response_missing"),
        ("agent_schema_invalid:json_invalid", "json_invalid"),
        (
            "agent_schema_invalid:pydantic_invalid:effective_at:missing",
            "pydantic_invalid:effective_at:missing",
        ),
    ],
)
def test_schema_failure_persists_tool_evidence_and_reconciles_reserved_turns_once(
    runtime_code: str,
    warning_detail: str,
) -> None:
    ledger, run_id, evidence = _full_audit_run()
    inner = InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000)

    class RecordingCostLedger:
        def __init__(self) -> None:
            self.reconciled: list[tuple[str, int]] = []

        def reserve(self, reservation_id, worst_case_usd_micros):
            return inner.reserve(reservation_id, worst_case_usd_micros)

        def reconcile(self, reservation_id, *, actual_usd_micros):
            self.reconciled.append((reservation_id, actual_usd_micros))
            inner.reconcile(
                reservation_id, actual_usd_micros=actual_usd_micros
            )

        def snapshot(self):
            return inner.snapshot()

    turn = TurnTelemetry(1, 100, 20, 5, 125, "STOP", True, 10)

    class MissingFinalSchemaRunner:
        async def execute(self, role, prompt, tools, context):
            del prompt
            assert role is AgentRole.EVIDENCE_WATCHER
            tools["evidence_connector"](
                stage="prepared",
                tool_context=context.tool_context("watcher-call"),
            )
            raise RoleExecutionError(
                runtime_code,
                turns=(turn,),
                tool_call_ids=("watcher-call",),
                tool_response_ids=("watcher-call",),
            )

    cost = RecordingCostLedger()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=MissingFinalSchemaRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=cost,
        cost_policy=DEFAULT_MODEL_COST_POLICY,
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
    actual = projected_cost_micros(
        prompt_tokens=100,
        candidate_tokens=20,
        thoughts_tokens=5,
        policy=DEFAULT_MODEL_COST_POLICY,
    )

    assert outcome.terminal_state == "HALTED"
    assert failed["failure_code"] == "agent_schema_invalid"
    assert failed["warnings"] == [
        {
            "code": "agent_schema_failure",
            "message_key": warning_detail,
            "related_artifact_ids": [],
        }
    ]
    assert failed["turns"] == [turn.to_wire()]
    assert failed["tool_call_ids"] == ["watcher-call"]
    assert failed["tool_response_ids"] == ["watcher-call"]
    assert [item["tool_id"] for item in failed["tool_records"]] == [
        "evidence_connector"
    ]
    assert cost.reconciled == [
        (f"{run_id}:{AgentRole.EVIDENCE_WATCHER.value}:1:1", actual),
        (f"{run_id}:{AgentRole.EVIDENCE_WATCHER.value}:1:2", 0),
    ]
    assert not any(
        item["schema_name"] == "PolicyDecision"
        for item in ledger.list_by_run(run_id)
    )


def test_post_assessor_contract_failure_preserves_completed_role_evidence(
    monkeypatch,
) -> None:
    ledger, run_id, evidence = _full_audit_run()

    def reject_assessor_artifacts(**_):
        raise ContractError("contract_required_field_missing")

    monkeypatch.setattr(
        full_audit_module,
        "build_assessor_artifacts",
        reject_assessor_artifacts,
    )
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=FakeRoleRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(
            hard_cap_usd_micros=75_000_000
        ),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    outcome = asyncio.run(
        coordinator.execute_run(run_id, evidence=evidence, now=NOW)
    )
    failed = next(
        item
        for item in ledger.list_by_run(run_id)
        if item["schema_name"] == "AgentExecutionReceipt"
        and item["agent_role"] == AgentRole.EVIDENCE_ASSESSOR.value
        and item["execution_status"] == "FAILED"
    )

    assert outcome.terminal_state == "HALTED"
    assert failed["failure_code"] == "agent_schema_invalid"
    assert failed["warnings"] == [
        {
            "code": "agent_schema_failure",
            "message_key": "artifact_contract:contract_required_field_missing",
            "related_artifact_ids": [],
        }
    ]
    assert failed["turns"]
    assert failed["tool_call_ids"] == ["assessor-call"]
    assert failed["tool_response_ids"] == ["assessor-call"]
    assert [item["tool_id"] for item in failed["tool_records"]] == [
        "ledger_read"
    ]
    assert outcome.policy_decision_id is None


def test_watcher_cursor_mismatch_halts_without_policy_decision() -> None:
    ledger, run_id, evidence = _full_audit_run()

    class CursorMismatchRunner(FakeRoleRunner):
        async def execute(self, role, prompt, tools, context):
            result = await super().execute(role, prompt, tools, context)
            if role is not AgentRole.EVIDENCE_WATCHER:
                return result
            return replace(
                result,
                output=EvidenceSnapshotOutput.model_validate(
                    {
                        **result.output.model_dump(mode="json", by_alias=True),
                        "source_cursors": {"clinvar": "42"},
                    }
                ),
            )

    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=CursorMismatchRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(
            hard_cap_usd_micros=75_000_000
        ),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    outcome = asyncio.run(
        coordinator.execute_run(run_id, evidence=evidence, now=NOW)
    )

    assert outcome.terminal_state == "HALTED"
    assert outcome.policy_decision_id is None
    failed = next(
        item
        for item in ledger.list_by_run(run_id)
        if item["schema_name"] == "AgentExecutionReceipt"
        and item["execution_status"] == "FAILED"
    )
    assert failed["warnings"] == [
        {
            "code": "agent_schema_failure",
            "message_key": "artifact_contract:watcher_source_cursor_mismatch",
            "related_artifact_ids": [],
        }
    ]


@pytest.mark.parametrize("candidate_state", ["ABSENT", "UNKNOWN", "PRESENT"])
def test_assessor_prompt_contains_exact_controller_binding_skeleton(
    candidate_state: str,
) -> None:
    run_id = "2c90e154-0c23-5294-ab5c-3f647c150875"
    candidate_id = "00000000-0000-4000-8000-000000000010"
    previous_snapshot_id = "00000000-0000-4000-8000-000000000009"
    snapshot_id = "00000000-0000-4000-8000-000000000011"
    prompt = FullAuditCoordinator._prompt(
        AgentRole.EVIDENCE_ASSESSOR,
        (candidate_id, snapshot_id),
        run_id=run_id,
        assessor_candidate={
            "artifact_id": candidate_id,
            "previous_snapshot_id": previous_snapshot_id,
            "current_snapshot_id": snapshot_id,
            "candidate_delta_state": candidate_state,
        },
        assessor_snapshot={"artifact_id": snapshot_id},
    )

    binding = json.loads(prompt.split("BINDING_CONTRACT=", 1)[1])
    assert binding["candidate_delta_state"] == candidate_state
    assert binding["exact_fields"] == {
        "assessment_receipt.delta_id": str(uuid5(UUID(run_id), "evidence-delta")),
        "evidence_delta.candidate_receipt_id": candidate_id,
        "evidence_delta.comparison": {
            "classification_changed": "NOT_EVALUATED",
            "classification_source_refs": [],
        },
        "evidence_delta.counter_evidence_refs": [],
        "evidence_delta.current_snapshot_id": snapshot_id,
        "evidence_delta.previous_snapshot_id": previous_snapshot_id,
        "evidence_delta.removed_observation_refs": [],
    }
    universal_paths = {
        "assessment_receipt.delta_id",
        "evidence_delta.candidate_receipt_id",
        "evidence_delta.comparison",
        "evidence_delta.counter_evidence_refs",
        "evidence_delta.current_snapshot_id",
        "evidence_delta.previous_snapshot_id",
        "evidence_delta.removed_observation_refs",
    }
    if candidate_state == "PRESENT":
        assert binding["exact_branch_fields"] == {}
        assert binding["constraints"] == {
            "evidence_delta.materiality_proposal": {
                "not_const": "NO_CANDIDATE",
                "type": "string",
            }
        }
        assert "Constraint objects are predicates only" in prompt
        assert "never copy them into the output" in prompt
        expected_paths = universal_paths | {
            "evidence_delta.materiality_proposal"
        }
    else:
        assert binding["exact_branch_fields"] == {
            "assessment_receipt.counter_evidence_set": [],
            "assessment_receipt.material_claims": [],
            "evidence_delta.added_observation_refs": [],
            "evidence_delta.change_items": [],
            "evidence_delta.materiality_proposal": "NO_CANDIDATE",
        }
        assert binding["constraints"] == {}
        assert "emit the strict no-candidate JSON" in prompt
        assert "Do not propose materiality or claims" in prompt
        expected_paths = universal_paths | {
            "assessment_receipt.counter_evidence_set",
            "assessment_receipt.material_claims",
            "evidence_delta.added_observation_refs",
            "evidence_delta.change_items",
            "evidence_delta.materiality_proposal",
        }
    prompt_paths = (
        set(binding["exact_fields"])
        | set(binding["exact_branch_fields"])
        | set(binding["constraints"])
    )
    assert prompt_paths == expected_paths


def test_unknown_candidate_executes_with_exact_no_candidate_binding() -> None:
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
            evidence=_unknown_candidate_evidence(evidence),
            now=NOW,
        )
    )
    candidate = next(
        item
        for item in ledger.list_by_run(run_id)
        if item["schema_name"] == "CandidateDeltaReceipt"
    )
    binding = json.loads(runner.assessor_prompt.split("BINDING_CONTRACT=", 1)[1])

    assert candidate["candidate_delta_state"] == "UNKNOWN"
    assert binding["candidate_delta_state"] == "UNKNOWN"
    assert binding["exact_branch_fields"][
        "evidence_delta.materiality_proposal"
    ] == "NO_CANDIDATE"
    assert runner.roles == [
        AgentRole.EVIDENCE_WATCHER,
        AgentRole.EVIDENCE_ASSESSOR,
        AgentRole.CITATION_AUDITOR,
    ]
    assert outcome.terminal_state != "HALTED"
    assert outcome.audit_status == "COMPLETE"
    assert outcome.policy_decision_id is not None
    assert any(
        item["schema_name"] == "AssessmentReceipt"
        for item in ledger.list_by_run(run_id)
    )


@pytest.mark.parametrize("candidate_present", [False, True])
def test_assessor_contradictory_controller_owned_claims_halt_fail_closed(
    candidate_present: bool,
) -> None:
    ledger, run_id, evidence = _full_audit_run()
    base_runner = (
        MaterialClaimToolPlanRunner(("claim-1",))
        if candidate_present
        else FakeRoleRunner()
    )
    if candidate_present:
        evidence = _material_claim_evidence(evidence)

    class ContradictoryAssessorRunner:
        async def execute(self, role, prompt, tools, context):
            result = await base_runner.execute(role, prompt, tools, context)
            if role is not AgentRole.EVIDENCE_ASSESSOR:
                return result
            wire = result.output.model_dump(mode="json")
            if candidate_present:
                wire["evidence_delta"]["materiality_proposal"] = "NO_CANDIDATE"
            else:
                wire["assessment_receipt"]["material_claims"] = [
                    "fabricated-no-candidate-claim"
                ]
            return replace(
                result,
                output=AssessmentAgentOutput.model_validate(wire),
            )

    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=ContradictoryAssessorRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(
            hard_cap_usd_micros=75_000_000
        ),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    outcome = asyncio.run(
        coordinator.execute_run(run_id, evidence=evidence, now=NOW)
    )

    assert outcome.terminal_state == "HALTED"
    assert outcome.policy_decision_id is None
    failed = next(
        item
        for item in ledger.list_by_run(run_id)
        if item["schema_name"] == "AgentExecutionReceipt"
        and item["agent_role"] == AgentRole.EVIDENCE_ASSESSOR.value
        and item["execution_status"] == "FAILED"
    )
    mismatch_field = (
        "evidence_delta.materiality_proposal"
        if candidate_present
        else "assessment_receipt.material_claims"
    )
    assert failed["warnings"] == [
        {
            "code": "agent_schema_failure",
            "message_key": (
                "artifact_contract:assessor_output_binding_invalid:"
                + mismatch_field
            ),
            "related_artifact_ids": [],
        }
    ]


def test_assessor_binding_mismatch_bitset_is_sorted_and_value_free() -> None:
    ledger, run_id, evidence = _full_audit_run()

    class MultipleMismatchRunner(FakeRoleRunner):
        async def execute(self, role, prompt, tools, context):
            result = await super().execute(role, prompt, tools, context)
            if role is not AgentRole.EVIDENCE_ASSESSOR:
                return result
            wire = result.output.model_dump(mode="json")
            wire["evidence_delta"]["current_snapshot_id"] = (
                "00000000-0000-4000-8000-000000000099"
            )
            wire["assessment_receipt"]["material_claims"] = [
                "model-supplied-value-must-not-persist"
            ]
            return replace(
                result,
                output=AssessmentAgentOutput.model_validate(wire),
                turns=(
                    result.turns[0],
                    TurnTelemetry(2, 110, 25, 7, 142, "STOP", False, 900),
                ),
            )

    inner_cost = InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000)

    class RecordingCostLedger:
        def __init__(self) -> None:
            self.reconciled: list[tuple[str, int]] = []

        def reserve(self, reservation_id, worst_case_usd_micros):
            return inner_cost.reserve(reservation_id, worst_case_usd_micros)

        def reconcile(self, reservation_id, *, actual_usd_micros):
            self.reconciled.append((reservation_id, actual_usd_micros))
            return inner_cost.reconcile(
                reservation_id,
                actual_usd_micros=actual_usd_micros,
            )

        def snapshot(self):
            return inner_cost.snapshot()

    cost = RecordingCostLedger()

    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=MultipleMismatchRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=cost,
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    outcome = asyncio.run(
        coordinator.execute_run(run_id, evidence=evidence, now=NOW)
    )
    failed = next(
        item
        for item in ledger.list_by_run(run_id)
        if item["schema_name"] == "AgentExecutionReceipt"
        and item["agent_role"] == AgentRole.EVIDENCE_ASSESSOR.value
        and item["execution_status"] == "FAILED"
    )

    assert outcome.terminal_state == "HALTED"
    assert outcome.policy_decision_id is None
    assert failed["warnings"] == [
        {
            "code": "agent_schema_failure",
            "message_key": (
                "artifact_contract:assessor_output_binding_invalid:"
                "assessment_receipt.material_claims,"
                "evidence_delta.current_snapshot_id"
            ),
            "related_artifact_ids": [],
        }
    ]
    assert "model-supplied-value" not in json.dumps(failed["warnings"])
    assert len(failed["turns"]) == 2
    assert failed["tool_call_ids"] == ["assessor-call"]
    assert failed["tool_response_ids"] == ["assessor-call"]
    assert [item["tool_id"] for item in failed["tool_records"]] == [
        "ledger_read"
    ]
    assessor_cost = [
        item
        for item in cost.reconciled
        if f":{AgentRole.EVIDENCE_ASSESSOR.value}:" in item[0]
    ]
    assert len(assessor_cost) == 2
    assert len({reservation_id for reservation_id, _ in assessor_cost}) == 2
    assert all(actual > 0 for _, actual in assessor_cost)


def test_deadline_exhausted_after_reservation_reconciles_both_turns_to_zero() -> None:
    ledger, run_id, evidence = _full_audit_run()
    inner = InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000)

    class RecordingCostLedger:
        def __init__(self) -> None:
            self.reconciled: list[tuple[str, int]] = []

        def reserve(self, reservation_id, worst_case_usd_micros):
            return inner.reserve(reservation_id, worst_case_usd_micros)

        def reconcile(self, reservation_id, *, actual_usd_micros):
            self.reconciled.append((reservation_id, actual_usd_micros))
            inner.reconcile(reservation_id, actual_usd_micros=actual_usd_micros)

        def snapshot(self):
            return inner.snapshot()

    cost = RecordingCostLedger()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=FakeRoleRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=cost,
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    with pytest.raises(
        RoleExecutionError, match="agent_execution_deadline_exceeded"
    ):
        asyncio.run(
            coordinator._execute_role(
                AgentRole.EVIDENCE_WATCHER,
                run_id=run_id,
                evidence=evidence,
                input_artifact_ids=(),
                trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
                now=NOW,
                deadline_at=NOW,
            )
        )

    assert cost.reconciled == [
        (f"{run_id}:{AgentRole.EVIDENCE_WATCHER.value}:1:1", 0),
        (f"{run_id}:{AgentRole.EVIDENCE_WATCHER.value}:1:2", 0),
    ]


def test_second_reserve_exception_zero_reconciles_first_reservation_once() -> None:
    ledger, run_id, evidence = _full_audit_run()
    inner = InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000)

    class SecondReserveFails:
        def __init__(self) -> None:
            self.reserve_count = 0
            self.reconciled: list[tuple[str, int]] = []

        def reserve(self, reservation_id, worst_case_usd_micros):
            self.reserve_count += 1
            if self.reserve_count == 2:
                raise RuntimeError("second_reserve_failed")
            return inner.reserve(reservation_id, worst_case_usd_micros)

        def reconcile(self, reservation_id, *, actual_usd_micros):
            self.reconciled.append((reservation_id, actual_usd_micros))
            inner.reconcile(reservation_id, actual_usd_micros=actual_usd_micros)

        def snapshot(self):
            return inner.snapshot()

    cost = SecondReserveFails()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=FakeRoleRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=cost,
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    with pytest.raises(RuntimeError, match="second_reserve_failed"):
        asyncio.run(
            coordinator._execute_role(
                AgentRole.EVIDENCE_WATCHER,
                run_id=run_id,
                evidence=evidence,
                input_artifact_ids=(),
                trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
                now=NOW,
                deadline_at=NOW + timedelta(minutes=1),
            )
        )

    assert cost.reconciled == [
        (f"{run_id}:{AgentRole.EVIDENCE_WATCHER.value}:1:1", 0)
    ]


def test_unexpected_runner_failure_zero_reconciles_all_reservations_once() -> None:
    ledger, run_id, evidence = _full_audit_run()
    inner = InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000)

    class RecordingCostLedger:
        def __init__(self) -> None:
            self.reconciled: list[tuple[str, int]] = []

        def reserve(self, reservation_id, worst_case_usd_micros):
            return inner.reserve(reservation_id, worst_case_usd_micros)

        def reconcile(self, reservation_id, *, actual_usd_micros):
            self.reconciled.append((reservation_id, actual_usd_micros))
            inner.reconcile(reservation_id, actual_usd_micros=actual_usd_micros)

        def snapshot(self):
            return inner.snapshot()

    class UnexpectedFailureRunner:
        async def execute(self, role, prompt, tools, context):
            del role, prompt, tools, context
            raise ValueError("unexpected_runner_failure")

    cost = RecordingCostLedger()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=UnexpectedFailureRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=cost,
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    with pytest.raises(ValueError, match="unexpected_runner_failure"):
        asyncio.run(
            coordinator._execute_role(
                AgentRole.EVIDENCE_WATCHER,
                run_id=run_id,
                evidence=evidence,
                input_artifact_ids=(),
                trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
                now=NOW,
                deadline_at=NOW + timedelta(minutes=1),
            )
        )

    assert cost.reconciled == [
        (f"{run_id}:{AgentRole.EVIDENCE_WATCHER.value}:1:1", 0),
        (f"{run_id}:{AgentRole.EVIDENCE_WATCHER.value}:1:2", 0),
    ]


def test_failure_tool_ids_disagree_with_authoritative_records_fails_closed() -> None:
    ledger, run_id, evidence = _full_audit_run()

    class DisagreeingRunner:
        async def execute(self, role, prompt, tools, context):
            del role, prompt
            tools["evidence_connector"](
                stage="prepared",
                tool_context=context.tool_context("authoritative-call"),
            )
            raise RoleExecutionError(
                "agent_provider_call_failed",
                tool_call_ids=("reported-call",),
                tool_response_ids=("reported-call",),
            )

    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=DisagreeingRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(
            hard_cap_usd_micros=75_000_000
        ),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    with pytest.raises(RoleExecutionError) as captured:
        asyncio.run(
            coordinator._execute_role(
                AgentRole.EVIDENCE_WATCHER,
                run_id=run_id,
                evidence=evidence,
                input_artifact_ids=(),
                trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
                now=NOW,
                deadline_at=NOW + timedelta(minutes=1),
            )
        )

    assert captured.value.code == "agent_tool_evidence_mismatch"
    assert captured.value.tool_call_ids == ("authoritative-call",)
    assert captured.value.tool_response_ids == ("authoritative-call",)
    assert captured.value.tool_records[0]["authorization_receipt_id"]


def test_real_adk_tool_then_second_provider_429_preserves_authoritative_evidence() -> None:
    ledger, run_id, evidence = _full_audit_run()
    inner = InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000)

    class RecordingCostLedger:
        def __init__(self) -> None:
            self.reconciled: list[tuple[str, int]] = []

        def reserve(self, reservation_id, worst_case_usd_micros):
            return inner.reserve(reservation_id, worst_case_usd_micros)

        def reconcile(self, reservation_id, *, actual_usd_micros):
            self.reconciled.append((reservation_id, actual_usd_micros))
            inner.reconcile(reservation_id, actual_usd_micros=actual_usd_micros)

        def snapshot(self):
            return inner.snapshot()

    runner = InProcessAdkRoleRunner(
        model=ToolThenRateLimitedLlm(),
        provider_rpm=60,
        provider_clock=lambda: 0.0,
        provider_sleeper=_no_sleep,
        backoff_sleeper=_no_sleep,
    )
    cost = RecordingCostLedger()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=runner,
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=cost,
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    outcome = asyncio.run(
        coordinator.execute_run(run_id, evidence=evidence, now=NOW)
    )
    artifacts = ledger.list_by_run(run_id)
    failed = next(
        item
        for item in artifacts
        if item["schema_name"] == "AgentExecutionReceipt"
        and item["execution_status"] == "FAILED"
    )

    assert outcome.terminal_state == "HALTED"
    assert outcome.policy_decision_id is None
    assert failed["failure_code"] == "controller_failed"
    assert len(failed["turns"]) == 1
    assert failed["http_429_count"] >= 1
    assert len(failed["tool_records"]) == 1
    record = failed["tool_records"][0]
    assert record["tool_id"] == "evidence_connector"
    assert failed["tool_call_ids"] == [record["call_id"]]
    assert failed["tool_response_ids"] == [record["response_id"]]
    assert record["authorization_receipt_id"] in failed["input_artifact_ids"]
    assert len(cost.reconciled) == 2
    assert len({reservation_id for reservation_id, _ in cost.reconciled}) == 2
    assert not any(item["schema_name"] == "PolicyDecision" for item in artifacts)


def test_local_tool_construction_failure_occurs_before_any_cost_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, run_id, evidence = _full_audit_run()

    class NoReservationCostLedger:
        def reserve(self, reservation_id, worst_case_usd_micros):
            raise AssertionError("cost reservation must follow tool construction")

        def reconcile(self, reservation_id, *, actual_usd_micros):
            raise AssertionError("nothing was reserved")

        def snapshot(self):
            return SimpleNamespace(reserved_usd_micros=0, reconciled_usd_micros=0)

    monkeypatch.setattr(
        full_audit_module,
        "build_local_tools",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("local_tool_construction_failed")
        ),
    )
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=FakeRoleRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=NoReservationCostLedger(),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )

    with pytest.raises(RuntimeError, match="local_tool_construction_failed"):
        asyncio.run(
            coordinator._execute_role(
                AgentRole.EVIDENCE_WATCHER,
                run_id=run_id,
                evidence=evidence,
                input_artifact_ids=(),
                trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
                now=NOW,
                deadline_at=NOW + timedelta(minutes=1),
            )
        )


@pytest.mark.parametrize("invalid_mode", ["ROUND_TRIP", "THREE_TURNS"])
def test_post_result_invariant_failure_preserves_evidence_without_double_cost(
    invalid_mode: str,
) -> None:
    ledger, run_id, evidence = _full_audit_run()
    inner = InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000)

    class RecordingCostLedger:
        def __init__(self) -> None:
            self.reconciled: list[tuple[str, int]] = []

        def reserve(self, reservation_id, worst_case_usd_micros):
            return inner.reserve(reservation_id, worst_case_usd_micros)

        def reconcile(self, reservation_id, *, actual_usd_micros):
            self.reconciled.append((reservation_id, actual_usd_micros))
            inner.reconcile(reservation_id, actual_usd_micros=actual_usd_micros)

        def snapshot(self):
            return inner.snapshot()

    base_turns = (
        TurnTelemetry(1, 100, 20, 5, 125, "STOP", True, 10),
        TurnTelemetry(2, 110, 25, 5, 140, "STOP", False, 10),
    )

    class InvalidResultRunner:
        async def execute(self, role, prompt, tools, context):
            del prompt
            tools["evidence_connector"](
                stage="prepared",
                tool_context=context.tool_context("watcher-call"),
            )
            turns = base_turns
            responses: tuple[str, ...] = ()
            if invalid_mode == "THREE_TURNS":
                turns += (
                    TurnTelemetry(3, 1, 1, 0, 2, "STOP", False, 1),
                )
                responses = ("watcher-call",)
            return RoleRunResult(
                EvidenceSnapshotOutput.model_validate(
                    {
                        "effective_at": "2026-08-27T08:00:00Z",
                        "observation_ids": [],
                        "coverage_status": "PASS",
                        "source_cursors": {"clinvar": "42"},
                        "normalized_facts": {
                            "observation_count": 1,
                            "scope": "synthetic",
                        },
                        "conflicts": [],
                        "snapshot_hash": "a" * 64,
                    }
                ),
                turns,
                ("watcher-call",),
                responses,
                context.trace_id,
                context.invocation_id,
                NOW,
                NOW + timedelta(seconds=1),
                0,
            )

    cost = RecordingCostLedger()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=InvalidResultRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=cost,
        cost_policy=DEFAULT_MODEL_COST_POLICY,
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
    assert failed["turns"] == [turn.to_wire() for turn in (
        base_turns
        if invalid_mode == "ROUND_TRIP"
        else base_turns + (TurnTelemetry(3, 1, 1, 0, 2, "STOP", False, 1),)
    )]
    assert failed["tool_call_ids"] == ["watcher-call"]
    assert failed["tool_response_ids"] == (
        [] if invalid_mode == "ROUND_TRIP" else ["watcher-call"]
    )
    assert len(cost.reconciled) == 2
    assert len({item[0] for item in cost.reconciled}) == 2
    assert not any(
        item["schema_name"] == "PolicyDecision"
        for item in ledger.list_by_run(run_id)
    )


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
    runner = MaterialClaimToolPlanRunner(("claim-1",))
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=runner,
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
    binding = json.loads(runner.assessor_prompt.split("BINDING_CONTRACT=", 1)[1])
    assert binding["candidate_delta_state"] == "PRESENT"
    assert binding["constraints"]["evidence_delta.materiality_proposal"] == {
        "not_const": "NO_CANDIDATE",
        "type": "string",
    }
    assert runner.roles == [
        AgentRole.EVIDENCE_WATCHER,
        AgentRole.EVIDENCE_ASSESSOR,
        AgentRole.CITATION_AUDITOR,
    ]
    assert outcome.audit_status == "COMPLETE"
    assert outcome.policy_decision_id is not None
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


@pytest.mark.parametrize(
    ("runtime_code", "warning_detail"),
    [
        ("agent_timeout:provider_limiter", "timeout_substage:provider_limiter"),
        ("agent_timeout:provider_call", "timeout_substage:provider_call"),
        ("agent_timeout:provider_backoff", "timeout_substage:provider_backoff"),
        ("agent_timeout:adk_runtime", "timeout_substage:adk_runtime"),
        ("agent_timeout:lease_guard", "timeout_substage:lease_guard"),
        ("agent_timeout:raw secret value", "timeout_substage:unclassified"),
    ],
)
def test_runtime_timeout_detail_is_closed_and_failure_class_stays_stable(
    runtime_code: str, warning_detail: str
) -> None:
    ledger, run_id, evidence = _full_audit_run()

    class BrokenRunner(FakeRoleRunner):
        async def execute(self, role, prompt, tools, context):
            del role, prompt, tools, context
            raise RoleExecutionError(runtime_code)

    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=BrokenRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
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
    assert outcome.policy_decision_id is None
    assert failed["failure_code"] == "agent_timeout"
    assert failed["warnings"] == [
        {
            "code": "agent_runtime_failure",
            "message_key": warning_detail,
            "related_artifact_ids": [],
        }
    ]
    warning_wire = json.dumps(failed["warnings"])
    assert "raw secret value" not in warning_wire
    assert evidence.case_id not in warning_wire
    assert run_id not in warning_wire


def test_final_turn_tool_violation_is_typed_and_safely_described() -> None:
    ledger, run_id, evidence = _full_audit_run()

    class BrokenRunner(FakeRoleRunner):
        async def execute(self, role, prompt, tools, context):
            del role, prompt, tools, context
            raise RoleExecutionError(
                "agent_final_turn_tool_violation",
                turns=(
                    TurnTelemetry(1, 10, 2, 0, 12, "STOP", True, 10),
                    TurnTelemetry(2, 12, 2, 0, 14, "STOP", True, 11),
                ),
            )

    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=BrokenRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
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
    assert outcome.policy_decision_id is None
    assert outcome.technical_failure_codes == ("controller_failed",)
    assert failed["failure_code"] == "agent_final_turn_tool_violation"
    assert failed["warnings"] == [
        {
            "code": "agent_runtime_failure",
            "message_key": (
                "effective_final_request:mode_none:tools_zero:"
                "function_call_returned"
            ),
            "related_artifact_ids": [],
        }
    ]
    assert len(failed["turns"]) == 2


def test_failed_receipt_rejects_unrecognized_runtime_warning_detail() -> None:
    receipt = build_failed_receipt(
        case_id=CASE_ID,
        run_id="3dc2e659-73a7-4f4d-bd23-0e0826a173ec",
        role=AgentRole.EVIDENCE_WATCHER,
        attempt=1,
        started_receipt_id="71e0e8d4-652f-43ac-b911-4281831c847e",
        trace_id="fa3fcd17-4d9b-4304-9aa4-c03e334091f0",
        invocation_id="3c179906-b72b-4c90-8920-90ad2e856fd0",
        data_mode=DataMode.SYNTHETIC,
        started_at=NOW,
        failed_at=NOW + timedelta(seconds=1),
        failure_code="agent_timeout",
        schema_failure_detail="timeout_substage:secret-provider-payload",
    )

    assert receipt["warnings"] == [
        {
            "code": "agent_runtime_failure",
            "message_key": "runtime_failure:unclassified",
            "related_artifact_ids": [],
        }
    ]
    assert "secret-provider-payload" not in json.dumps(receipt)


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
    clock_values = iter((NOW, NOW, NOW + timedelta(seconds=31)))

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
        role_timeout_seconds=1,
        lease_duration_seconds=31,
        clock=lambda: next(clock_values),
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


def test_role_timeout_uses_fresh_clock_for_shared_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, run_id, evidence = _full_audit_run()
    observed_timeouts: list[float] = []

    async def capture_wait_for(awaitable, *, timeout):
        observed_timeouts.append(timeout)
        return await awaitable

    monkeypatch.setattr(full_audit_module.asyncio, "wait_for", capture_wait_for)
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=FakeRoleRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
        role_timeout_seconds=300,
        lease_duration_seconds=900,
        clock=lambda: NOW + timedelta(seconds=650),
    )

    asyncio.run(
        coordinator._execute_role(
            AgentRole.EVIDENCE_WATCHER,
            run_id=run_id,
            evidence=evidence,
            input_artifact_ids=(),
            trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
            now=NOW,
            deadline_at=NOW + timedelta(seconds=800),
        )
    )

    assert observed_timeouts == [150]


def test_three_role_timeouts_leave_lease_commit_safety_margin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, run_id, evidence = _full_audit_run()
    observed_timeouts: list[float] = []
    clock_values = iter(
        (
            NOW,
            NOW,
            NOW + timedelta(seconds=300),
            NOW + timedelta(seconds=300),
            NOW + timedelta(seconds=600),
            NOW + timedelta(seconds=600),
        )
    )

    async def capture_wait_for(awaitable, *, timeout):
        observed_timeouts.append(timeout)
        return await awaitable

    monkeypatch.setattr(full_audit_module.asyncio, "wait_for", capture_wait_for)
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=FakeRoleRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
        role_timeout_seconds=300,
        lease_duration_seconds=900,
        clock=lambda: next(clock_values),
    )

    outcome = asyncio.run(
        coordinator.execute_run(
            run_id,
            evidence=evidence,
            now=NOW,
            deadline_at=NOW + timedelta(seconds=27_000),
        )
    )

    assert outcome.terminal_state == "NO_ACTION"
    assert observed_timeouts == [300, 300, 270]


@pytest.mark.parametrize("role_timeout", [900, 901])
def test_role_timeout_must_remain_strictly_below_lease(
    role_timeout: int,
) -> None:
    ledger, _, _ = _full_audit_run()

    with pytest.raises(ValueError, match="full_audit_timeout_invalid"):
        FullAuditCoordinator(
            ledger,
            role_runner=FakeRoleRunner(),
            invocation_store=InMemoryGatewayInvocationStore(),
            cost_ledger=InMemoryModelCostLedger(
                hard_cap_usd_micros=75_000_000
            ),
            cost_policy=DEFAULT_MODEL_COST_POLICY,
            role_timeout_seconds=role_timeout,
            lease_duration_seconds=900,
        )


def test_open_started_attempt_is_closed_and_role_resumes_once() -> None:
    ledger, run_id, evidence = _full_audit_run()
    runner = FakeRoleRunner()
    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=runner,
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
        role_timeout_seconds=1,
        lease_duration_seconds=31,
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
            run_id, evidence=evidence, now=NOW + timedelta(seconds=31)
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
        role_timeout_seconds=59,
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
    clock_values = iter((NOW, NOW, NOW + timedelta(seconds=62)))

    class LeaseStealingRunner(FakeRoleRunner):
        async def execute(self, role, prompt, tools, context):
            current = ledger.get_scan_run(run_id)
            assert current is not None
            controller.acquire_lease(
                run_id,
                expected_version=current.version,
                new_epoch=current.lease_epoch + 1,
                expires_at=NOW + timedelta(seconds=62),
                now=NOW + timedelta(seconds=31),
            )
            raise TimeoutError("old worker failed after ownership changed")

    coordinator = FullAuditCoordinator(
        ledger,
        role_runner=LeaseStealingRunner(),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
        role_timeout_seconds=1,
        lease_duration_seconds=31,
        clock=lambda: next(clock_values),
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
