from __future__ import annotations

import asyncio
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
from recall.contracts import AgentRole


class ToolThenJsonLlm(BaseLlm):
    _responses: deque[LlmResponse] = PrivateAttr()

    def __init__(self) -> None:
        super().__init__(model="gemini-3.7-flash")
        output = (
            '{"effective_at":"2026-08-27T08:00:00Z",'
            '"observation_ids":[],"coverage_status":"PASS",'
            '"source_cursors":{"clinvar":"42"},'
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
                '"source_cursors":{"clinvar":"42"},'
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
        return {"records": [{"source": "synthetic"}]}

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
        ("not-json", "agent_schema_invalid"),
        (None, "agent_response_missing"),
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

    with pytest.raises(RoleExecutionError, match="model_turn_budget_exceeded"):
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

    assert captured.code == "agent_timeout"
    assert captured.http_429_count == 1
