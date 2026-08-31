from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import AsyncGenerator

from google.adk.models import BaseLlm
from google.adk.models._capabilities import LlmCapabilities
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import PrivateAttr
import pytest

from recall.agents.full_audit_models import RoleExecutionContext, RoleExecutionError
from recall.agents.in_process_runtime import (
    InProcessAdkRoleRunner,
    RequestBoundLlm,
    _effective_request_bytes,
)
from recall.agents.provider_pacing import ProviderRateLimiter
from recall.agents.schemas import AssessmentAgentOutput, EvidenceSnapshotOutput
from recall.contracts import AgentRole


class ToolThenJsonLlm(BaseLlm):
    _responses: deque[LlmResponse] = PrivateAttr()

    def __init__(self) -> None:
        super().__init__(model="gemini-3.7-flash")
        output = (
            '{"effective_at":"2026-08-27T08:00:00Z",'
            '"observation_ids":[],"coverage_status":"PASS",'
            '"source_cursors":{"synthetic-source":"cursor-001"},'
            '"normalized_facts":{"observation_count":1,"scope":"synthetic"},'
            '"conflicts":[],"snapshot_hash":"' + "a" * 64 + '"}'
        )
        self._responses = deque(
            (
                LlmResponse(
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
                ),
                LlmResponse(
                    content=types.Content(
                        role="model", parts=[types.Part(text=output)]
                    ),
                    partial=False,
                ),
            )
        )

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del llm_request, stream
        yield self._responses.popleft()


class RateLimitedLlm(BaseLlm):
    def __init__(self) -> None:
        super().__init__(model="gemini-3.7-flash")

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del llm_request, stream
        raise RuntimeError("429 ResourceExhausted")
        yield  # pragma: no cover - keeps the async-generator contract


class ToolThenInvalidFinalLlm(BaseLlm):
    _responses: deque[LlmResponse] = PrivateAttr()

    def __init__(self, final_text: str | None) -> None:
        super().__init__(model="gemini-3.7-flash")
        final_parts = [] if final_text is None else [types.Part(text=final_text)]
        self._responses = deque(
            (
                LlmResponse(
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
                ),
                LlmResponse(
                    content=types.Content(role="model", parts=final_parts),
                    partial=False,
                ),
            )
        )

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del llm_request, stream
        yield self._responses.popleft()


class ToolThenThoughtAndValidFinalLlm(BaseLlm):
    _responses: deque[LlmResponse] = PrivateAttr()

    def __init__(self) -> None:
        super().__init__(model="gemini-3.7-flash")
        output = (
            '{"effective_at":"2026-08-27T08:00:00Z",'
            '"observation_ids":[],"coverage_status":"PASS",'
            '"source_cursors":{"synthetic-source":"cursor-001"},'
            '"normalized_facts":{"observation_count":1,'
            '"scope":"synthetic"},"conflicts":[],"snapshot_hash":"'
            + "a" * 64
            + '"}'
        )
        self._responses = deque(
            (
                LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part.from_function_call(
                                name="evidence_connector", args={}
                            )
                        ],
                    ),
                    partial=False,
                ),
                LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(text="internal reasoning", thought=True),
                            types.Part(text=output),
                        ],
                    ),
                    partial=False,
                ),
            )
        )

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del llm_request, stream
        yield self._responses.popleft()


class ThreeTurnLlm(BaseLlm):
    _calls: int = PrivateAttr(default=0)

    def __init__(self) -> None:
        super().__init__(model="gemini-3.7-flash")

    @property
    def calls(self) -> int:
        return self._calls

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del llm_request, stream
        self._calls += 1
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_function_call(
                        name="evidence_connector",
                        args={"stage": "prepared"},
                    )
                ],
            ),
            partial=False,
        )


class RepeatToolUnlessFinalTurnIsLockedLlm(BaseLlm):
    _calls: int = PrivateAttr(default=0)
    _modes: list[types.FunctionCallingConfigMode | None] = PrivateAttr(
        default_factory=list
    )

    def __init__(self) -> None:
        super().__init__(model="gemini-3.7-flash")

    @property
    def calls(self) -> int:
        return self._calls

    @property
    def modes(self) -> tuple[types.FunctionCallingConfigMode | None, ...]:
        return tuple(self._modes)

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del stream
        self._calls += 1
        function_config = (
            None
            if llm_request.config.tool_config is None
            else llm_request.config.tool_config.function_calling_config
        )
        mode = None if function_config is None else function_config.mode
        self._modes.append(mode)
        if mode is types.FunctionCallingConfigMode.NONE:
            output = (
                '{"effective_at":"2026-08-27T08:00:00Z",'
                '"observation_ids":[],"coverage_status":"PASS",'
                '"source_cursors":{"synthetic-source":"cursor-001"},'
                '"normalized_facts":{"observation_count":1,'
                '"scope":"synthetic"},"conflicts":[],"snapshot_hash":"'
                + "a" * 64
                + '"}'
            )
            yield LlmResponse(
                content=types.Content(
                    role="model", parts=[types.Part(text=output)]
                ),
                partial=False,
            )
            return
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_function_call(
                        name="evidence_connector",
                        args={"stage": "prepared"},
                    )
                ],
            ),
            partial=False,
        )


class AssessorRepeatToolUnlessFinalTurnIsLockedLlm(BaseLlm):
    _calls: int = PrivateAttr(default=0)
    _modes: list[types.FunctionCallingConfigMode | None] = PrivateAttr(
        default_factory=list
    )

    def __init__(self, candidate_id: str, snapshot_id: str) -> None:
        super().__init__(model="gemini-3.7-flash")
        self._candidate_id = candidate_id
        self._snapshot_id = snapshot_id

    @property
    def calls(self) -> int:
        return self._calls

    @property
    def modes(self) -> tuple[types.FunctionCallingConfigMode | None, ...]:
        return tuple(self._modes)

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del stream
        self._calls += 1
        function_config = (
            None
            if llm_request.config.tool_config is None
            else llm_request.config.tool_config.function_calling_config
        )
        mode = None if function_config is None else function_config.mode
        self._modes.append(mode)
        if mode is types.FunctionCallingConfigMode.NONE:
            output = {
                "evidence_delta": {
                    "candidate_receipt_id": self._candidate_id,
                    "previous_snapshot_id": None,
                    "current_snapshot_id": self._snapshot_id,
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
            yield LlmResponse(
                content=types.Content(
                    role="model", parts=[types.Part(text=json.dumps(output))]
                ),
                partial=False,
            )
            return
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_function_call(
                        name="ledger_read",
                        args={"artifact_id": self._candidate_id},
                    )
                ],
            ),
            partial=False,
        )


class AuditorParallelToolsUnlessFinalTurnIsLockedLlm(BaseLlm):
    _calls: int = PrivateAttr(default=0)
    _modes: list[types.FunctionCallingConfigMode | None] = PrivateAttr(
        default_factory=list
    )
    _tool_counts: list[int] = PrivateAttr(default_factory=list)
    _tool_dict_counts: list[int] = PrivateAttr(default_factory=list)

    def __init__(self, assessment_id: str, claim_ids: tuple[str, ...]) -> None:
        super().__init__(model="gemini-3.7-flash")
        self._assessment_id = assessment_id
        self._claim_ids = claim_ids

    @property
    def modes(self) -> tuple[types.FunctionCallingConfigMode | None, ...]:
        return tuple(self._modes)

    @property
    def tool_counts(self) -> tuple[int, ...]:
        return tuple(self._tool_counts)

    @property
    def tool_dict_counts(self) -> tuple[int, ...]:
        return tuple(self._tool_dict_counts)

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del stream
        self._calls += 1
        function_config = (
            None
            if llm_request.config.tool_config is None
            else llm_request.config.tool_config.function_calling_config
        )
        mode = None if function_config is None else function_config.mode
        self._modes.append(mode)
        self._tool_counts.append(len(llm_request.config.tools or ()))
        self._tool_dict_counts.append(len(llm_request.tools_dict))
        if mode is types.FunctionCallingConfigMode.NONE:
            output = {
                "assessment_id": self._assessment_id,
                "audit_status": "COMPLETE",
                "claim_results": [
                    {
                        "claim_id": claim_id,
                        "cited_identifier": claim_id,
                        "reason_codes": ["citation_source_binding_missing"],
                        "refetched_source": None,
                    }
                    for claim_id in self._claim_ids
                ],
                "metadata_refetches": [],
                "counter_evidence_coverage": "PASS",
                "audit_completeness": "PASS",
                "rejected_claim_ids": list(self._claim_ids),
            }
            yield LlmResponse(
                content=types.Content(
                    role="model", parts=[types.Part(text=json.dumps(output))]
                ),
                partial=False,
            )
            return
        parts = [
            types.Part.from_function_call(
                name="ledger_read",
                args={"artifact_id": self._assessment_id},
            ),
            *(
                types.Part.from_function_call(
                    name="refetch_metadata", args={"claim_id": claim_id}
                )
                for claim_id in self._claim_ids
            ),
        ]
        yield LlmResponse(
            content=types.Content(role="model", parts=parts),
            partial=False,
        )


class FinalTurnFunctionCallDespiteNoneLlm(BaseLlm):
    """Return a forbidden second function call even after the final lock."""

    _calls: int = PrivateAttr(default=0)
    _modes: list[types.FunctionCallingConfigMode | None] = PrivateAttr(
        default_factory=list
    )
    _tool_counts: list[int] = PrivateAttr(default_factory=list)

    def __init__(self, assessment_id: str) -> None:
        super().__init__(model="gemini-3.7-flash")
        self._assessment_id = assessment_id

    @property
    def modes(self) -> tuple[types.FunctionCallingConfigMode | None, ...]:
        return tuple(self._modes)

    @property
    def tool_counts(self) -> tuple[int, ...]:
        return tuple(self._tool_counts)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del stream
        self._calls += 1
        function_config = (
            None
            if llm_request.config.tool_config is None
            else llm_request.config.tool_config.function_calling_config
        )
        self._modes.append(None if function_config is None else function_config.mode)
        self._tool_counts.append(len(llm_request.config.tools or ()))
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_function_call(
                        name="ledger_read",
                        args={"artifact_id": self._assessment_id},
                    )
                ],
            ),
            partial=False,
        )


class ProviderCallStallLlm(BaseLlm):
    """Stall before a response, optionally after one real tool round-trip."""

    _calls: int = PrivateAttr(default=0)
    _first_turn_tool: bool = PrivateAttr()
    _stalled: asyncio.Event = PrivateAttr(default_factory=asyncio.Event)

    def __init__(self, *, first_turn_tool: bool) -> None:
        super().__init__(model="gemini-3.7-flash")
        self._first_turn_tool = first_turn_tool

    @property
    def stalled(self) -> asyncio.Event:
        return self._stalled

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del llm_request, stream
        self._calls += 1
        if self._first_turn_tool and self._calls == 1:
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
        self._stalled.set()
        await asyncio.Event().wait()
        yield  # pragma: no cover - preserves async-generator shape


class OversizedSecondTurnLlm(BaseLlm):
    _calls: int = PrivateAttr(default=0)

    def __init__(self) -> None:
        super().__init__(model="gemini-3.7-flash")

    @property
    def calls(self) -> int:
        return self._calls

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del llm_request, stream
        self._calls += 1
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_function_call(
                        name="evidence_connector",
                        args={"stage": "prepared"},
                    )
                ],
            ),
            partial=False,
        )


async def _no_sleep(_seconds: float) -> None:
    return None


def _runner(model: BaseLlm, **kwargs) -> InProcessAdkRoleRunner:
    return InProcessAdkRoleRunner(
        model=model,
        provider_clock=lambda: 0.0,
        provider_sleeper=_no_sleep,
        backoff_sleeper=_no_sleep,
        **kwargs,
    )


def test_in_process_runner_executes_real_adk_function_tool_and_returns_telemetry() -> None:
    observed: list[tuple[str, str, str]] = []

    def evidence_connector(stage, tool_context):
        observed.append(
            (stage, tool_context.invocation_id, tool_context.function_call_id)
        )
        return {
            "records": [{"source": "synthetic"}],
            "source_cursors": {"synthetic-source": "cursor-001"},
        }

    context = RoleExecutionContext(
        case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
        attempt=1,
        invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
        input_artifact_ids=(),
        trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
    )
    runner = _runner(ToolThenJsonLlm())
    result = asyncio.run(
        runner.execute(
            AgentRole.EVIDENCE_WATCHER,
            "Call the evidence connector once and return strict JSON.",
            {"evidence_connector": evidence_connector},
            context,
        )
    )

    assert len(observed) == 1
    assert observed[0][0] == "prepared"
    assert observed[0][1]
    assert observed[0][2]
    assert result.output.coverage_status == "PASS"
    assert result.trace_id == context.trace_id
    assert len(result.turns) == 2
    assert runner.provider_limiter.dispatch_count == 2
    assert result.turns[0].function_call_emitted is True
    assert result.tool_call_ids == result.tool_response_ids
    assert result.tool_results["evidence_connector"]["source_cursors"] == {
        "synthetic-source": "cursor-001"
    }


def test_smoke_probe_fails_after_real_watcher_tool_round_trip_without_retry() -> None:
    observed: list[str] = []
    runner = _runner(
        ToolThenJsonLlm(),
        max_429_retries=0,
        failure_probe="WATCHER_SCHEMA_INVALID_AFTER_TOOL_ROUND_TRIP",
    )

    with pytest.raises(RoleExecutionError) as captured:
        asyncio.run(
            runner.execute(
                AgentRole.EVIDENCE_WATCHER,
                "Call the evidence connector once and return strict JSON.",
                {
                    "evidence_connector": lambda stage, **_: (
                        observed.append(stage) or {"records": []}
                    )
                },
                RoleExecutionContext(
                    case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
                    run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
                    attempt=1,
                    invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
                    input_artifact_ids=(),
                    trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
                ),
            )
        )

    error = captured.value
    assert error.code == "agent_schema_invalid"
    assert observed == ["prepared"]
    assert len(error.turns) == 2
    assert error.tool_call_ids == error.tool_response_ids
    assert len(error.tool_call_ids) == 1
    assert runner.provider_limiter.dispatch_count == 2


def test_smoke_runner_rejects_provider_retry_budget_above_contract() -> None:
    with pytest.raises(ValueError, match="provider_retry_budget_invalid"):
        _runner(ToolThenJsonLlm(), max_429_retries=4)


def test_watcher_tool_exposes_no_model_controlled_stage_and_keeps_local_guard() -> None:
    observed: list[str] = []

    def evidence_connector(stage, tool_context):
        del tool_context
        observed.append(stage)
        return {"records": []}

    result = asyncio.run(
        _runner(ToolThenJsonLlm()).execute(
            AgentRole.EVIDENCE_WATCHER,
            "Call the evidence connector once and return strict JSON.",
            {"evidence_connector": evidence_connector},
            RoleExecutionContext(
                case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
                run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
                attempt=1,
                invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
                input_artifact_ids=(),
                trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
            ),
        )
    )

    assert observed == ["prepared"]
    assert len(result.tool_call_ids) == 1
    assert result.tool_call_ids == result.tool_response_ids


@pytest.mark.parametrize(
    ("final_text", "error_code"),
    [
        ("not-json", "agent_schema_invalid:json_invalid"),
        (None, "agent_response_missing:response_missing"),
        (
            "{}",
            "agent_schema_invalid:pydantic_invalid:effective_at:missing",
        ),
    ],
)
def test_schema_failure_after_real_tool_round_trip_preserves_runtime_evidence(
    final_text: str | None,
    error_code: str,
) -> None:
    calls: list[str] = []

    with pytest.raises(RoleExecutionError) as captured:
        asyncio.run(
            _runner(ToolThenInvalidFinalLlm(final_text)).execute(
                AgentRole.EVIDENCE_WATCHER,
                "Call the evidence connector once and return strict JSON.",
                {
                    "evidence_connector": lambda stage, **_: (
                        calls.append(stage) or {"records": []}
                    )
                },
                RoleExecutionContext(
                    case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
                    run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
                    attempt=1,
                    invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
                    input_artifact_ids=(),
                    trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
                ),
            )
        )

    error = captured.value
    assert error.code == error_code
    assert calls == ["prepared"]
    assert len(error.turns) == 2
    assert error.turns[0].function_call_emitted is True
    assert error.turns[1].function_call_emitted is False
    assert len(error.tool_call_ids) == 1
    assert error.tool_call_ids == error.tool_response_ids


def test_provider_visible_watcher_schema_round_trips_exact_synthetic_source() -> None:
    schema = EvidenceSnapshotOutput.model_json_schema(by_alias=True)
    source_schema = schema["$defs"]["SourceCursorsOutput"]

    assert "synthetic-source" in source_schema["properties"]
    parsed = EvidenceSnapshotOutput.model_validate(
        {
            "effective_at": "2026-08-31T00:00:00Z",
            "observation_ids": [],
            "coverage_status": "PASS",
            "source_cursors": {"synthetic-source": "cursor-001"},
            "normalized_facts": {
                "observation_count": 1,
                "scope": "synthetic",
            },
            "conflicts": [],
            "snapshot_hash": "a" * 64,
        }
    )
    assert parsed.to_contract_payload()["source_cursors"] == {
        "synthetic-source": "cursor-001"
    }


def test_schema_failure_detail_never_persists_model_supplied_field_or_value() -> None:
    payload = {
        "effective_at": "2026-08-31T00:00:00Z",
        "observation_ids": [],
        "coverage_status": "PASS",
        "source_cursors": {"synthetic-source": "cursor-001"},
        "normalized_facts": {
            "observation_count": 1,
            "scope": "synthetic",
        },
        "conflicts": [],
        "snapshot_hash": "a" * 64,
        "model-supplied-secret-name": "model-supplied-secret-value",
    }

    with pytest.raises(RoleExecutionError) as captured:
        asyncio.run(
            _runner(ToolThenInvalidFinalLlm(json.dumps(payload))).execute(
                AgentRole.EVIDENCE_WATCHER,
                "Call once and return strict JSON.",
                {"evidence_connector": lambda **_: {"records": []}},
                RoleExecutionContext(
                    case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
                    run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
                    attempt=1,
                    invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
                    input_artifact_ids=(),
                    trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
                ),
            )
        )

    assert captured.value.code == (
        "agent_schema_invalid:pydantic_invalid:field:extra_forbidden"
    )
    assert "secret" not in captured.value.code


@pytest.mark.parametrize(
    "payload",
    [
        {
            "evidence_delta": {
                "candidate_receipt_id": "not-a-uuid",
                "previous_snapshot_id": None,
                "current_snapshot_id": "00000000-0000-4000-8000-000000000011",
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
                "delta_id": "00000000-0000-4000-8000-000000000012",
                "material_claims": [],
                "counter_evidence_set": [],
                "uncertainty_codes": [],
                "schema_validation_status": "PASS",
            },
        },
        {
            "evidence_delta": {
                "candidate_receipt_id": "00000000-0000-4000-8000-000000000010",
                "previous_snapshot_id": None,
                "current_snapshot_id": "00000000-0000-4000-8000-000000000011",
                "added_observation_refs": [],
                "removed_observation_refs": [],
                "change_items": [],
                "comparison": {
                    "classification_changed": "NOT_EVALUATED",
                    "classification_source_refs": [],
                },
                "materiality_proposal": "",
                "uncertainties": [],
                "counter_evidence_refs": [],
            },
            "assessment_receipt": {
                "delta_id": "00000000-0000-4000-8000-000000000012",
                "material_claims": [],
                "counter_evidence_set": [],
                "uncertainty_codes": [],
                "schema_validation_status": "PASS",
            },
        },
    ],
)
def test_provider_visible_assessor_schema_rejects_downstream_invalid_boundaries(
    payload,
) -> None:
    with pytest.raises(ValueError):
        AssessmentAgentOutput.model_validate(payload)


def test_schema_parser_excludes_explicit_thought_parts_without_normalizing_output() -> None:
    result = asyncio.run(
        _runner(ToolThenThoughtAndValidFinalLlm()).execute(
            AgentRole.EVIDENCE_WATCHER,
            "Call the evidence connector once and return strict JSON.",
            {"evidence_connector": lambda **_: {"records": []}},
            RoleExecutionContext(
                case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
                run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
                attempt=1,
                invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
                input_artifact_ids=(),
                trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
            ),
        )
    )

    assert len(result.turns) == 2
    assert result.output.coverage_status == "PASS"


def test_in_process_runner_preserves_rate_limit_telemetry_on_provider_error() -> None:
    context = RoleExecutionContext(
        case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
        attempt=1,
        invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
        input_artifact_ids=(),
        trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
    )

    try:
        asyncio.run(
            _runner(RateLimitedLlm()).execute(
                AgentRole.EVIDENCE_WATCHER,
                "Call the evidence connector once.",
                {"evidence_connector": lambda **_: {"records": []}},
                context,
            )
        )
    except RoleExecutionError as exc:
        assert exc.code == "agent_provider_call_failed"
        assert exc.http_429_count == 4
    else:  # pragma: no cover - fail explicitly if ADK swallows the provider error
        raise AssertionError("rate limit error was not propagated")


def test_in_process_runner_refuses_third_provider_dispatch() -> None:
    context = RoleExecutionContext(
        case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
        attempt=1,
        invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
        input_artifact_ids=(),
        trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
    )
    model = ThreeTurnLlm()

    with pytest.raises(
        RoleExecutionError, match="agent_final_turn_tool_violation"
    ):
        asyncio.run(
            _runner(model).execute(
                AgentRole.EVIDENCE_WATCHER,
                "Call twice.",
                {"evidence_connector": lambda **_: {"records": []}},
                context,
            )
        )

    assert model.calls == 2


def test_watcher_final_turn_disables_repeat_tool_call_within_two_turn_budget() -> None:
    context = RoleExecutionContext(
        case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
        attempt=1,
        invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
        input_artifact_ids=(),
        trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
    )
    model = RepeatToolUnlessFinalTurnIsLockedLlm()
    calls: list[str] = []

    runner = _runner(model)
    result = asyncio.run(
        runner.execute(
            AgentRole.EVIDENCE_WATCHER,
            "Call the evidence connector once.",
            {
                "evidence_connector": lambda **_: (
                    calls.append("evidence_connector") or {"records": []}
                )
            },
            context,
        )
    )

    assert model.calls == 2
    assert model.modes == (None, types.FunctionCallingConfigMode.NONE)
    assert runner.provider_limiter.dispatch_count == 2
    assert calls == ["evidence_connector"]
    assert len(result.turns) == 2
    assert result.output.coverage_status == "PASS"


def test_assessor_final_turn_disables_repeat_tool_call_within_two_turn_budget() -> None:
    candidate_id = "00000000-0000-4000-8000-000000000010"
    snapshot_id = "00000000-0000-4000-8000-000000000011"
    context = RoleExecutionContext(
        case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
        attempt=1,
        invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
        input_artifact_ids=(candidate_id, snapshot_id),
        trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
    )
    model = AssessorRepeatToolUnlessFinalTurnIsLockedLlm(
        candidate_id, snapshot_id
    )
    calls: list[str] = []

    result = asyncio.run(
        _runner(model).execute(
            AgentRole.EVIDENCE_ASSESSOR,
            f"Call ledger_read for CandidateDeltaReceipt {candidate_id}.",
            {
                "ledger_read": lambda artifact_id, **_: (
                    calls.append(artifact_id)
                    or {"schema_name": "CandidateDeltaReceipt"}
                )
            },
            context,
        )
    )

    assert model.calls == 2
    assert model.modes == (None, types.FunctionCallingConfigMode.NONE)
    assert calls == [candidate_id]
    assert len(result.turns) == 2
    assert result.turns[0].function_call_emitted is True
    assert result.turns[1].function_call_emitted is False
    assert result.tool_call_ids == result.tool_response_ids
    assert len(result.tool_call_ids) == 1
    assert set(result.tool_results) == {f"ledger:{candidate_id}"}
    assert result.output.assessment_receipt.schema_validation_status == "PASS"


def test_auditor_executes_declared_parallel_tool_plan_then_schema_only() -> None:
    assessment_id = "00000000-0000-4000-8000-000000000020"
    claim_ids = ("claim-1", "claim-2")
    context = RoleExecutionContext(
        case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
        attempt=1,
        invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
        input_artifact_ids=(assessment_id,),
        trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
    )
    model = AuditorParallelToolsUnlessFinalTurnIsLockedLlm(
        assessment_id, claim_ids
    )
    ledger_calls: list[str] = []
    refetch_calls: list[str] = []

    result = asyncio.run(
        _runner(model).execute(
            AgentRole.CITATION_AUDITOR,
            "Read the assessment and refetch exact claims claim-1, claim-2.",
            {
                "ledger_read": lambda artifact_id, **_: (
                    ledger_calls.append(artifact_id)
                    or {"schema_name": "AssessmentReceipt"}
                ),
                "refetch_metadata": lambda claim_id, **_: (
                    refetch_calls.append(claim_id)
                    or {
                        "claim_id": claim_id,
                        "verdict": "UNAVAILABLE",
                        "reason_codes": ["citation_source_binding_missing"],
                        "refetched_source": None,
                    }
                ),
            },
            context,
        )
    )

    assert model.modes == (None, types.FunctionCallingConfigMode.NONE)
    assert model.tool_counts[0] > 0
    assert model.tool_counts[1] == 0
    assert model.tool_dict_counts[0] > 0
    assert model.tool_dict_counts[1] == 0
    assert ledger_calls == [assessment_id]
    assert sorted(refetch_calls) == list(claim_ids)
    assert len(result.turns) == 2
    assert result.turns[0].function_call_emitted is True
    assert result.turns[1].function_call_emitted is False
    assert result.tool_call_ids == result.tool_response_ids
    assert len(result.tool_call_ids) == 3
    assert set(result.tool_results) == {
        f"ledger:{assessment_id}",
        "refetch:claim-1",
        "refetch:claim-2",
    }
    assert result.output.audit_status == "COMPLETE"


def test_auditor_forbidden_final_function_call_fails_before_repeat_tool() -> None:
    assessment_id = "00000000-0000-4000-8000-000000000020"
    context = RoleExecutionContext(
        case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
        attempt=1,
        invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
        input_artifact_ids=(assessment_id,),
        trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
    )
    model = FinalTurnFunctionCallDespiteNoneLlm(assessment_id)
    ledger_calls: list[str] = []

    with pytest.raises(
        RoleExecutionError, match="agent_final_turn_tool_violation"
    ) as captured:
        asyncio.run(
            _runner(model).execute(
                AgentRole.CITATION_AUDITOR,
                f"Read AssessmentReceipt {assessment_id}, then return JSON.",
                {
                    "ledger_read": lambda artifact_id, **_: (
                        ledger_calls.append(artifact_id)
                        or {"schema_name": "AssessmentReceipt"}
                    ),
                    "refetch_metadata": lambda **_: {},
                },
                context,
            )
        )

    assert model.modes == (None, types.FunctionCallingConfigMode.NONE)
    assert model.tool_counts[0] > 0
    assert model.tool_counts[1] == 0
    assert ledger_calls == [assessment_id]
    assert len(captured.value.turns) == 2
    assert all(item.function_call_emitted for item in captured.value.turns)


def test_in_process_runner_refuses_oversized_second_request_before_dispatch() -> None:
    context = RoleExecutionContext(
        case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
        attempt=1,
        invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
        input_artifact_ids=(),
        trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
    )
    model = OversizedSecondTurnLlm()

    with pytest.raises(RoleExecutionError, match="model_request_budget_exceeded"):
        asyncio.run(
            _runner(model, max_request_bytes=16_384).execute(
                AgentRole.EVIDENCE_WATCHER,
                "Call the evidence connector once.",
                {
                    "evidence_connector": lambda **_: {
                        "records": [{"oversized": "x" * 50_000}]
                    }
                },
                context,
            )
        )

    assert model.calls == 1


def test_provider_bound_guard_sees_adk_label_added_after_callback() -> None:
    request = LlmRequest(model="gemini-3.7-flash")
    callback_visible_bytes = len(_effective_request_bytes(request))
    request.config.labels = {"google-adk-agent-name": "evidence_watcher"}
    assert len(_effective_request_bytes(request)) > callback_visible_bytes
    model = OversizedSecondTurnLlm()
    guarded = RequestBoundLlm(
        model=model.model,
        delegate=model,
        max_request_bytes=callback_visible_bytes,
        provider_limiter=ProviderRateLimiter(
            60, clock=lambda: 0.0, sleeper=_no_sleep
        ),
        backoff_sleeper=_no_sleep,
    )

    async def consume() -> None:
        async for _ in guarded.generate_content_async(request):
            pass

    with pytest.raises(RoleExecutionError, match="model_request_budget_exceeded"):
        asyncio.run(consume())

    assert model.calls == 0


def test_runner_cancellation_after_429_preserves_count_as_agent_timeout() -> None:
    context = RoleExecutionContext(
        case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
        attempt=1,
        invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
        input_artifact_ids=(),
        trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
    )
    async def cancel_during_backoff() -> RoleExecutionError:
        backoff_entered = asyncio.Event()

        async def blocking_backoff(_seconds: float) -> None:
            backoff_entered.set()
            await asyncio.Event().wait()

        runner = InProcessAdkRoleRunner(
            model=RateLimitedLlm(),
            provider_rpm=60,
            provider_sleeper=_no_sleep,
            backoff_sleeper=blocking_backoff,
        )
        task = asyncio.create_task(
            runner.execute(
                AgentRole.EVIDENCE_WATCHER,
                "Call once.",
                {"evidence_connector": lambda **_: {"records": []}},
                context,
            )
        )
        await asyncio.wait_for(backoff_entered.wait(), timeout=1)
        task.cancel()
        try:
            await task
        except RoleExecutionError as exc:
            return exc
        raise AssertionError("cancelled runner did not preserve a typed failure")

    captured = asyncio.run(cancel_during_backoff())

    assert captured.code == "agent_timeout:provider_backoff"
    assert captured.http_429_count == 1


def test_runner_cancellation_while_waiting_for_provider_slot_is_typed() -> None:
    context = RoleExecutionContext(
        case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
        attempt=1,
        invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
        input_artifact_ids=(),
        trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
    )

    async def exercise() -> RoleExecutionError:
        limiter_entered = asyncio.Event()

        async def blocking_limiter(_seconds: float) -> None:
            limiter_entered.set()
            await asyncio.Event().wait()

        runner = InProcessAdkRoleRunner(
            model=ToolThenJsonLlm(),
            provider_rpm=1,
            provider_clock=lambda: 0.0,
            provider_sleeper=blocking_limiter,
        )
        await runner.provider_limiter.acquire()
        task = asyncio.create_task(
            runner.execute(
                AgentRole.EVIDENCE_WATCHER,
                "Call once.",
                {"evidence_connector": lambda **_: {"records": []}},
                context,
            )
        )
        await asyncio.wait_for(limiter_entered.wait(), timeout=1)
        task.cancel()
        try:
            await task
        except RoleExecutionError as exc:
            return exc
        raise AssertionError("cancelled provider wait did not stay typed")

    captured = asyncio.run(exercise())

    assert captured.code == "agent_timeout:provider_limiter"
    assert captured.turns == ()


@pytest.mark.parametrize("first_turn_tool", [False, True])
def test_runner_cancellation_inside_provider_call_preserves_prior_turn(
    first_turn_tool: bool,
) -> None:
    context = RoleExecutionContext(
        case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        run_id="2c90e154-0c23-5294-ab5c-3f647c150875",
        attempt=1,
        invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
        input_artifact_ids=(),
        trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
    )
    model = ProviderCallStallLlm(first_turn_tool=first_turn_tool)
    tool_calls: list[str] = []

    async def exercise() -> RoleExecutionError:
        task = asyncio.create_task(
            _runner(model).execute(
                AgentRole.EVIDENCE_WATCHER,
                "Call the connector once, then return JSON.",
                {
                    "evidence_connector": lambda **_: (
                        tool_calls.append("evidence_connector")
                        or {"records": []}
                    )
                },
                context,
            )
        )
        await asyncio.wait_for(model.stalled.wait(), timeout=1)
        task.cancel()
        try:
            await task
        except RoleExecutionError as exc:
            return exc
        raise AssertionError("cancelled provider call did not stay typed")

    captured = asyncio.run(exercise())

    assert captured.code == "agent_timeout:provider_call"
    assert len(captured.turns) == int(first_turn_tool)
    assert tuple(item.function_call_emitted for item in captured.turns) == (
        (True,) if first_turn_tool else ()
    )
    assert tool_calls == (["evidence_connector"] if first_turn_tool else [])
