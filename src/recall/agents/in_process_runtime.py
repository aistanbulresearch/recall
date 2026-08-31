from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from google.api_core.exceptions import ResourceExhausted, TooManyRequests
from google.adk.runners import InMemoryRunner
from google.adk.tools import ToolContext
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import BaseModel, PrivateAttr, ValidationError

from recall.contracts import AgentRole, ContractError

from .config import MODEL_ID
from .factory import OUTPUT_SCHEMAS, build_agent_bundle
from .full_audit_models import (
    MAX_MODEL_TURNS_PER_ROLE,
    RoleExecutionContext,
    RoleExecutionError,
    RoleRunResult,
    TurnTelemetry,
)
from .local_tools import LocalToolCallContext
from .provider_pacing import DEFAULT_PROVIDER_RPM, ProviderRateLimiter
from .schemas import schema_validation_error_code


_TWO_TURN_TOOL_PLAN_ROLES = frozenset(
    {
        AgentRole.EVIDENCE_WATCHER,
        AgentRole.EVIDENCE_ASSESSOR,
        AgentRole.CITATION_AUDITOR,
    }
)


class InProcessAdkRoleRunner:
    """Runs one bounded role invocation inside the scheduler Cloud Run Job."""

    def __init__(
        self,
        *,
        model: str | Any = MODEL_ID,
        max_request_bytes: int = 16_384,
        provider_rpm: int = DEFAULT_PROVIDER_RPM,
        provider_clock: Callable[[], float] = monotonic,
        provider_sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        backoff_sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        max_429_retries: int = 3,
        failure_probe: str | None = None,
    ) -> None:
        if max_request_bytes < 1:
            raise ValueError("model_request_budget_invalid")
        if (
            isinstance(max_429_retries, bool)
            or not isinstance(max_429_retries, int)
            or not 0 <= max_429_retries <= 3
        ):
            raise ValueError("provider_retry_budget_invalid")
        if failure_probe not in {
            None,
            "WATCHER_SCHEMA_INVALID_AFTER_TOOL_ROUND_TRIP",
        }:
            raise ValueError("role_failure_probe_invalid")
        self._model = model
        self._max_request_bytes = max_request_bytes
        self._provider_limiter = ProviderRateLimiter(
            provider_rpm, clock=provider_clock, sleeper=provider_sleeper
        )
        self._backoff_sleeper = backoff_sleeper
        self._max_429_retries = max_429_retries
        self._failure_probe = failure_probe

    @property
    def provider_limiter(self) -> ProviderRateLimiter:
        return self._provider_limiter

    async def execute(
        self,
        role: AgentRole,
        prompt: str,
        tools: Mapping[str, Callable[..., dict[str, object]]],
        context: RoleExecutionContext,
    ) -> RoleRunResult:
        started_at = datetime.now(UTC)
        turn_starts: deque[float] = deque()
        turns: list[TurnTelemetry] = []
        http_429_count = 0
        tool_results: dict[str, Mapping[str, object]] = {}

        def before_model(callback_context: Any, llm_request: Any) -> None:
            del callback_context
            if len(turns) + len(turn_starts) >= MAX_MODEL_TURNS_PER_ROLE:
                raise RoleExecutionError(
                    "model_turn_budget_exceeded",
                    turns=tuple(turns),
                    http_429_count=http_429_count,
                )
            if (
                role in _TWO_TURN_TOOL_PLAN_ROLES
                and len(turns) == 1
                and turns[0].function_call_emitted
                and not turn_starts
            ):
                llm_request.config.tool_config = types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode=types.FunctionCallingConfigMode.NONE
                    )
                )
            turn_starts.append(monotonic())

        def after_model(callback_context: Any, llm_response: Any) -> None:
            nonlocal http_429_count
            del callback_context
            started = turn_starts.popleft() if turn_starts else monotonic()
            usage = getattr(llm_response, "usage_metadata", None)
            content = getattr(llm_response, "content", None)
            parts = getattr(content, "parts", None) if content else ()
            finish_reason = _enum_value(
                getattr(llm_response, "finish_reason", None)
            )
            error_code = str(getattr(llm_response, "error_code", "") or "")
            error_message = str(
                getattr(llm_response, "error_message", "") or ""
            )
            if "429" in error_code or "429" in error_message:
                http_429_count += 1
            function_call_emitted = any(
                getattr(part, "function_call", None) is not None
                for part in parts or ()
            )
            turns.append(
                TurnTelemetry(
                    len(turns) + 1,
                    _usage_count(usage, "prompt_token_count"),
                    _usage_count(usage, "candidates_token_count"),
                    _usage_count(usage, "thoughts_token_count"),
                    _usage_count(usage, "total_token_count"),
                    finish_reason or "UNKNOWN",
                    function_call_emitted,
                    round((monotonic() - started) * 1000),
                )
            )
            if (
                role in _TWO_TURN_TOOL_PLAN_ROLES
                and len(turns) == MAX_MODEL_TURNS_PER_ROLE
                and function_call_emitted
            ):
                raise RoleExecutionError(
                    "agent_final_turn_tool_violation",
                    turns=tuple(turns),
                    http_429_count=http_429_count,
                )

        bundle = build_agent_bundle(
            role,
            tools=_adk_tools(tools, tool_results),
            model=self._model,
        )
        request_bound_model = RequestBoundLlm(
            model=bundle.agent.canonical_model.model,
            delegate=bundle.agent.canonical_model,
            max_request_bytes=self._max_request_bytes,
            provider_limiter=self._provider_limiter,
            backoff_sleeper=self._backoff_sleeper,
            max_429_retries=self._max_429_retries,
            enforce_final_turn_no_tools=role in _TWO_TURN_TOOL_PLAN_ROLES,
        )
        agent = bundle.agent.model_copy(
            update={
                "model": request_bound_model,
                "before_model_callback": before_model,
                "after_model_callback": after_model,
            }
        )
        runner = InMemoryRunner(agent=agent)
        provider_count_absorbed = False

        def absorb_provider_429_count() -> None:
            nonlocal http_429_count, provider_count_absorbed
            if not provider_count_absorbed:
                http_429_count += request_bound_model.http_429_count
                provider_count_absorbed = True

        try:
            events = await runner.run_debug(prompt, quiet=True)
        except asyncio.CancelledError as exc:
            absorb_provider_429_count()
            timeout_substage = request_bound_model.timeout_substage
            if timeout_substage not in {
                "provider_limiter",
                "provider_call",
                "provider_backoff",
                "adk_runtime",
            }:
                timeout_substage = "adk_runtime"
            raise RoleExecutionError(
                f"agent_timeout:{timeout_substage}",
                turns=tuple(turns),
                http_429_count=http_429_count,
            ) from exc
        except RoleExecutionError as exc:
            absorb_provider_429_count()
            raise RoleExecutionError(
                exc.code,
                turns=exc.turns or tuple(turns),
                http_429_count=max(http_429_count, exc.http_429_count),
                tool_records=exc.tool_records,
                tool_call_ids=exc.tool_call_ids,
                tool_response_ids=exc.tool_response_ids,
            ) from exc
        except Exception as exc:  # noqa: BLE001 - retain failed-provider telemetry
            absorb_provider_429_count()
            if _is_rate_limit_error(exc):
                http_429_count = max(1, http_429_count)
            raise RoleExecutionError(
                "agent_provider_call_failed",
                turns=tuple(turns),
                http_429_count=http_429_count,
            ) from exc
        absorb_provider_429_count()
        calls, responses = _tool_event_ids(events)
        if (
            self._failure_probe
            == "WATCHER_SCHEMA_INVALID_AFTER_TOOL_ROUND_TRIP"
            and role is AgentRole.EVIDENCE_WATCHER
        ):
            if not calls or calls != responses:
                raise RoleExecutionError(
                    "smoke_failure_probe_round_trip_missing",
                    turns=tuple(turns),
                    http_429_count=http_429_count,
                    tool_call_ids=calls,
                    tool_response_ids=responses,
                )
            raise RoleExecutionError(
                "agent_schema_invalid",
                turns=tuple(turns),
                http_429_count=http_429_count,
                tool_call_ids=calls,
                tool_response_ids=responses,
            )
        try:
            output = _parse_last_output(events, OUTPUT_SCHEMAS[role])
        except ContractError as exc:
            raise RoleExecutionError(
                exc.code,
                turns=tuple(turns),
                http_429_count=http_429_count,
                tool_call_ids=calls,
                tool_response_ids=responses,
            ) from exc
        return RoleRunResult(
            output=output,
            turns=tuple(turns),
            tool_call_ids=calls,
            tool_response_ids=responses,
            trace_id=context.trace_id,
            invocation_id=context.invocation_id,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            http_429_count=http_429_count,
            tool_results=tool_results,
        )


def _adk_tools(
    local: Mapping[str, Callable[..., dict[str, object]]],
    tool_results: dict[str, Mapping[str, object]],
) -> Mapping[str, Callable[..., dict[str, object]]]:
    wrapped: dict[str, Callable[..., dict[str, object]]] = {}

    if "evidence_connector" in local:

        def evidence_connector(
            tool_context: ToolContext,
        ) -> dict[str, object]:
            """Read the hash-bound prepared evidence for this run."""

            result = local["evidence_connector"](
                stage="prepared", tool_context=_local_context(tool_context)
            )
            tool_results["evidence_connector"] = dict(result)
            return result

        wrapped["evidence_connector"] = evidence_connector

    if "ledger_read" in local:

        def ledger_read(
            artifact_id: str, tool_context: ToolContext
        ) -> dict[str, object]:
            """Read one authorized run-scoped typed ledger artifact."""

            result = local["ledger_read"](
                artifact_id=artifact_id,
                tool_context=_local_context(tool_context),
            )
            tool_results[f"ledger:{artifact_id}"] = dict(result)
            return result

        wrapped["ledger_read"] = ledger_read

    if "refetch_metadata" in local:

        def refetch_metadata(
            claim_id: str, tool_context: ToolContext
        ) -> dict[str, object]:
            """Refetch public citation metadata without inventing unavailable data."""

            result = local["refetch_metadata"](
                claim_id=claim_id,
                tool_context=_local_context(tool_context),
            )
            tool_results[f"refetch:{claim_id}"] = dict(result)
            return result

        wrapped["refetch_metadata"] = refetch_metadata

    if set(wrapped) != set(local):
        raise ValueError("local_tool_wrapper_missing")
    return wrapped


def _local_context(tool_context: ToolContext) -> LocalToolCallContext:
    function_call_id = tool_context.function_call_id
    if not function_call_id:
        raise RuntimeError("adk_function_call_id_missing")
    return LocalToolCallContext(tool_context.invocation_id, function_call_id)


def _parse_last_output(
    events: list[object], output_schema: type[BaseModel]
) -> BaseModel:
    for event in reversed(events):
        content = getattr(event, "content", None)
        parts = getattr(content, "parts", None) if content else None
        if not parts:
            continue
        text = "".join(
            str(part.text)
            for part in parts
            if getattr(part, "text", None)
            and not bool(getattr(part, "thought", False))
        )
        if text:
            try:
                return output_schema.model_validate_json(text)
            except ValidationError as exc:
                raise ContractError(schema_validation_error_code(exc)) from exc
    raise ContractError("agent_response_missing:response_missing")


def _tool_event_ids(events: list[object]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    calls: list[str] = []
    responses: list[str] = []
    for event in events:
        content = getattr(event, "content", None)
        parts = getattr(content, "parts", None) if content else None
        for part in parts or ():
            call = getattr(part, "function_call", None)
            response = getattr(part, "function_response", None)
            if call is not None and getattr(call, "id", None):
                calls.append(str(call.id))
            if response is not None and getattr(response, "id", None):
                responses.append(str(response.id))
    return tuple(calls), tuple(responses)


def _usage_count(usage: Any, field: str) -> int:
    return int(getattr(usage, field, 0) or 0)


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _effective_request_bytes(llm_request: Any) -> bytes:
    try:
        value = llm_request.model_dump_json(
            exclude_none=True,
            exclude={"tools_dict"},
            fallback=_request_json_fallback,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise RoleExecutionError("model_request_serialization_failed") from exc
    return value.encode("utf-8")


def _request_json_fallback(value: Any) -> object:
    if isinstance(value, type) and issubclass(value, BaseModel):
        return value.model_json_schema()
    raise TypeError(f"model_request_value_unserializable:{type(value).__name__}")


class RequestBoundLlm(BaseLlm):
    """Final provider-bound request guard, after ADK mutates the request."""

    delegate: BaseLlm
    max_request_bytes: int
    provider_limiter: ProviderRateLimiter
    backoff_sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep
    max_429_retries: int = 3
    enforce_final_turn_no_tools: bool = False
    _http_429_count: int = PrivateAttr(default=0)
    _logical_request_count: int = PrivateAttr(default=0)
    _timeout_substage: str = PrivateAttr(default="adk_runtime")

    @property
    def http_429_count(self) -> int:
        return self._http_429_count

    @property
    def timeout_substage(self) -> str:
        return self._timeout_substage

    @property
    def capabilities(self):
        return self.delegate.capabilities

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self._logical_request_count += 1
        if self.enforce_final_turn_no_tools and self._logical_request_count == 2:
            llm_request.config.tool_config = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=types.FunctionCallingConfigMode.NONE
                )
            )
            llm_request.config.tools = []
            llm_request.tools_dict.clear()
        if len(_effective_request_bytes(llm_request)) > self.max_request_bytes:
            raise RoleExecutionError("model_request_budget_exceeded")
        if stream:
            raise RoleExecutionError("provider_streaming_retry_unsupported")
        for attempt in range(self.max_429_retries + 1):
            self._timeout_substage = "provider_limiter"
            await self.provider_limiter.acquire()
            responses: list[LlmResponse] = []
            try:
                self._timeout_substage = "provider_call"
                async for response in self.delegate.generate_content_async(
                    llm_request, False
                ):
                    responses.append(response)
            except Exception as exc:  # noqa: BLE001 - classify provider failure
                if not _is_rate_limit_error(exc):
                    raise
                self._http_429_count += 1
                if attempt >= self.max_429_retries:
                    raise
                self._timeout_substage = "provider_backoff"
                await self.backoff_sleeper(float(2**attempt))
                continue
            if any(_is_rate_limit_response(response) for response in responses):
                self._http_429_count += 1
                if attempt >= self.max_429_retries:
                    raise RoleExecutionError(
                        "agent_provider_call_failed",
                        http_429_count=self._http_429_count,
                    )
                self._timeout_substage = "provider_backoff"
                await self.backoff_sleeper(float(2**attempt))
                continue
            self._timeout_substage = "adk_runtime"
            for response in responses:
                yield response
            return


def _is_rate_limit_response(response: LlmResponse) -> bool:
    error_code = str(getattr(response, "error_code", "") or "").upper()
    error_message = str(getattr(response, "error_message", "") or "").upper()
    return error_code in {"429", "RESOURCE_EXHAUSTED"} or (
        "429" in error_message or "RESOURCE_EXHAUSTED" in error_message
    )


def _is_rate_limit_error(error: BaseException) -> bool:
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (ResourceExhausted, TooManyRequests)):
            return True
        response = getattr(current, "response", None)
        if getattr(response, "status_code", None) == 429:
            return True
        code = getattr(current, "code", None)
        code = code() if callable(code) else code
        code_name = str(getattr(code, "name", code) or "").upper()
        if code == 429 or code_name in {"429", "RESOURCE_EXHAUSTED"}:
            return True
        message = f"{type(current).__name__}:{current}".upper()
        if "429" in message or "RESOURCEEXHAUSTED" in message:
            return True
        current = current.__cause__ or current.__context__
    return False
