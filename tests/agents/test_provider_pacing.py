from __future__ import annotations

import asyncio

from google.adk.models import BaseLlm
from google.adk.models._capabilities import LlmCapabilities
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.api_core.exceptions import ResourceExhausted
from google.genai import types
from pydantic import PrivateAttr
import pytest

from recall.agents.full_audit_models import RoleExecutionError
from recall.agents.full_audit_models import RoleExecutionContext
from recall.agents.in_process_runtime import InProcessAdkRoleRunner, RequestBoundLlm
from recall.agents.provider_pacing import (
    DEFAULT_PROVIDER_RPM,
    ProviderRateLimiter,
    provider_rpm_from_environment,
)
from recall.contracts import AgentRole


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.value

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


class ProviderDouble(BaseLlm):
    _calls: int = PrivateAttr(default=0)
    _mode: str = PrivateAttr()

    def __init__(self, mode: str) -> None:
        super().__init__(model="gemini-3.7-flash")
        self._mode = mode

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(self, llm_request, stream=False):
        del llm_request, stream
        self._calls += 1
        if self._mode == "structured_429":
            raise ResourceExhausted("quota")
        if self._mode == "partial_then_success" and self._calls == 1:
            yield _response("partial", partial=True)
            raise ResourceExhausted("quota")
        if self._mode == "response_429" and self._calls == 1:
            yield LlmResponse(error_code="429", error_message="quota")
            return
        if self._mode == "broken":
            raise ValueError("not a quota error")
        yield _response("success")


class ConcurrentWatcherLlm(BaseLlm):
    _entered: int = PrivateAttr(default=0)
    _release: asyncio.Event = PrivateAttr(default_factory=asyncio.Event)

    def __init__(self) -> None:
        super().__init__(model="gemini-3.7-flash")

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(self, llm_request, stream=False):
        del llm_request, stream
        self._entered += 1
        if self._entered == 1:
            await self._release.wait()
        else:
            self._release.set()
        yield _response(_watcher_output())


class RateLimitedThenToolLoopLlm(BaseLlm):
    _calls: int = PrivateAttr(default=0)

    def __init__(self) -> None:
        super().__init__(model="gemini-3.7-flash")

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(self, llm_request, stream=False):
        del llm_request, stream
        self._calls += 1
        if self._calls == 1:
            raise ResourceExhausted("quota")
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_function_call(
                        name="evidence_connector",
                        args={"stage": "prepared"},
                    )
                ],
            )
        )


def _response(text: str, *, partial: bool = False) -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=text)]),
        partial=partial,
    )


def _watcher_output() -> str:
    return (
        '{"effective_at":"2026-08-27T08:00:00Z",'
        '"observation_ids":[],"coverage_status":"PASS",'
        '"source_cursors":{"clinvar":"42"},'
        '"normalized_facts":{"observation_count":1,"scope":"synthetic"},'
        '"conflicts":[],"snapshot_hash":"' + "a" * 64 + '"}'
    )


def _context(index: int) -> RoleExecutionContext:
    return RoleExecutionContext(
        case_id=f"728d6e23-5ee4-4bd4-9319-4304f55628f{index}",
        run_id=f"2c90e154-0c23-5294-ab5c-3f647c15087{index}",
        attempt=1,
        invocation_id=f"34a66eed-6fa4-5b22-a146-f8e8d2e6070{index}",
        input_artifact_ids=(),
        trace_id=f"e190f6ac-b726-42ae-ac2b-e4b80638e91{index}",
    )


async def _no_sleep(_seconds: float) -> None:
    return None


def _guarded(model: BaseLlm, *, backoff_sleeper=_no_sleep) -> RequestBoundLlm:
    return RequestBoundLlm(
        model=model.model,
        delegate=model,
        max_request_bytes=16_384,
        provider_limiter=ProviderRateLimiter(
            60, clock=lambda: 0.0, sleeper=_no_sleep
        ),
        backoff_sleeper=backoff_sleeper,
    )


def _consume(guarded: RequestBoundLlm, *, stream: bool = False) -> list[LlmResponse]:
    async def run() -> list[LlmResponse]:
        return [
            item
            async for item in guarded.generate_content_async(
                LlmRequest(model=guarded.model), stream=stream
            )
        ]

    return asyncio.run(run())


def test_provider_rpm_defaults_to_safe_r1_value_and_accepts_canonical_decimal() -> None:
    assert provider_rpm_from_environment({}) == DEFAULT_PROVIDER_RPM == 6
    assert provider_rpm_from_environment({"RECALL_PROVIDER_RPM": "7"}) == 7
    assert provider_rpm_from_environment({"RECALL_PROVIDER_RPM": "60"}) == 60


@pytest.mark.parametrize(
    "value", ["", " 6", "6 ", "+6", "-1", "6.0", "06", "0", "61", "rpm6"]
)
def test_provider_rpm_rejects_noncanonical_or_out_of_range_values(value: str) -> None:
    with pytest.raises(RuntimeError, match="provider_rpm_invalid"):
        provider_rpm_from_environment({"RECALL_PROVIDER_RPM": value})


def test_one_limiter_serializes_every_reserved_dispatch_at_declared_rpm() -> None:
    clock = FakeClock()
    limiter = ProviderRateLimiter(6, clock=clock, sleeper=clock.sleep)

    async def reserve_three() -> None:
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()

    asyncio.run(reserve_three())

    assert clock.sleeps == [10.0, 10.0]
    assert limiter.dispatch_count == 3


def test_structured_rate_limit_retries_four_dispatches_with_backoff() -> None:
    sleeps: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    guarded = _guarded(
        ProviderDouble("structured_429"), backoff_sleeper=record_sleep
    )

    with pytest.raises(ResourceExhausted):
        _consume(guarded)

    assert guarded.http_429_count == 4
    assert guarded.provider_limiter.dispatch_count == 4
    assert sleeps == [1.0, 2.0, 4.0]


@pytest.mark.parametrize("mode", ["partial_then_success", "response_429"])
def test_429_then_success_buffers_attempt_and_exposes_only_success(mode: str) -> None:
    guarded = _guarded(ProviderDouble(mode))

    responses = _consume(guarded)

    assert [item.content.parts[0].text for item in responses] == ["success"]
    assert guarded.http_429_count == 1
    assert guarded.provider_limiter.dispatch_count == 2


def test_non_rate_limit_error_is_not_retried_and_streaming_fails_closed() -> None:
    guarded = _guarded(ProviderDouble("broken"))

    with pytest.raises(ValueError, match="not a quota error"):
        _consume(guarded)
    assert guarded.http_429_count == 0
    assert guarded.provider_limiter.dispatch_count == 1

    with pytest.raises(
        RoleExecutionError, match="provider_streaming_retry_unsupported"
    ):
        _consume(guarded, stream=True)
    assert guarded.provider_limiter.dispatch_count == 1


def test_concurrent_role_invocations_share_one_runner_limiter() -> None:
    clock = FakeClock()
    runner = InProcessAdkRoleRunner(
        model=ConcurrentWatcherLlm(),
        provider_rpm=6,
        provider_clock=clock,
        provider_sleeper=clock.sleep,
        backoff_sleeper=_no_sleep,
    )

    async def run_both():
        return await asyncio.gather(
            *(
                runner.execute(
                    AgentRole.EVIDENCE_WATCHER,
                    "Return the strict snapshot JSON.",
                    {"evidence_connector": lambda **_: {"records": []}},
                    _context(index),
                )
                for index in (1, 2)
            )
        )

    results = asyncio.run(run_both())

    assert [result.output.coverage_status for result in results] == ["PASS", "PASS"]
    assert runner.provider_limiter.dispatch_count == 2
    assert clock.sleeps == [10.0]


def test_later_role_error_retains_hidden_recovered_429_count() -> None:
    runner = InProcessAdkRoleRunner(
        model=RateLimitedThenToolLoopLlm(),
        provider_rpm=60,
        provider_clock=lambda: 0.0,
        provider_sleeper=_no_sleep,
        backoff_sleeper=_no_sleep,
    )

    with pytest.raises(RoleExecutionError) as captured:
        asyncio.run(
            runner.execute(
                AgentRole.EVIDENCE_WATCHER,
                "Keep calling the evidence connector.",
                {"evidence_connector": lambda **_: {"records": []}},
                _context(3),
            )
        )

    assert captured.value.code == "model_turn_budget_exceeded"
    assert captured.value.http_429_count == 1
