from __future__ import annotations

from collections import deque
from collections.abc import AsyncGenerator, Callable, Mapping
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from google.adk.runners import InMemoryRunner
from google.adk.tools import ToolContext
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from pydantic import BaseModel

from recall.contracts import AgentRole, ContractError

from .config import MODEL_ID
from .factory import OUTPUT_SCHEMAS, build_agent_bundle
from .full_audit_models import (
    RoleExecutionContext,
    RoleExecutionError,
    RoleRunResult,
    TurnTelemetry,
)
from .local_tools import LocalToolCallContext


class InProcessAdkRoleRunner:
    """Runs one bounded role invocation inside the scheduler Cloud Run Job."""

    def __init__(
        self, *, model: str | Any = MODEL_ID, max_request_bytes: int = 16_384
    ) -> None:
        if max_request_bytes < 1:
            raise ValueError("model_request_budget_invalid")
        self._model = model
        self._max_request_bytes = max_request_bytes

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
            if len(turns) + len(turn_starts) >= 2:
                raise RoleExecutionError(
                    "model_turn_budget_exceeded",
                    turns=tuple(turns),
                    http_429_count=http_429_count,
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
            turns.append(
                TurnTelemetry(
                    len(turns) + 1,
                    _usage_count(usage, "prompt_token_count"),
                    _usage_count(usage, "candidates_token_count"),
                    _usage_count(usage, "thoughts_token_count"),
                    _usage_count(usage, "total_token_count"),
                    finish_reason or "UNKNOWN",
                    any(
                        getattr(part, "function_call", None) is not None
                        for part in parts or ()
                    ),
                    round((monotonic() - started) * 1000),
                )
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
        )
        agent = bundle.agent.model_copy(
            update={
                "model": request_bound_model,
                "before_model_callback": before_model,
                "after_model_callback": after_model,
            }
        )
        runner = InMemoryRunner(agent=agent)
        try:
            events = await runner.run_debug(prompt, quiet=True)
        except RoleExecutionError as exc:
            if exc.code == "model_request_budget_exceeded" and not exc.turns:
                raise RoleExecutionError(
                    exc.code,
                    turns=tuple(turns),
                    http_429_count=http_429_count,
                ) from exc
            raise
        except Exception as exc:  # noqa: BLE001 - retain failed-provider telemetry
            message = f"{type(exc).__name__}:{exc}"
            if "429" in message or "ResourceExhausted" in message:
                http_429_count = max(1, http_429_count)
            raise RoleExecutionError(
                "agent_provider_call_failed",
                turns=tuple(turns),
                http_429_count=http_429_count,
            ) from exc
        output = _parse_last_output(events, OUTPUT_SCHEMAS[role])
        calls, responses = _tool_event_ids(events)
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
            stage: str, tool_context: ToolContext
        ) -> dict[str, object]:
            """Read the hash-bound prepared evidence for this run."""

            return local["evidence_connector"](
                stage=stage, tool_context=_local_context(tool_context)
            )

        wrapped["evidence_connector"] = evidence_connector

    if "ledger_read" in local:

        def ledger_read(
            artifact_id: str, tool_context: ToolContext
        ) -> dict[str, object]:
            """Read one authorized run-scoped typed ledger artifact."""

            return local["ledger_read"](
                artifact_id=artifact_id,
                tool_context=_local_context(tool_context),
            )

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
            str(part.text) for part in parts if getattr(part, "text", None)
        )
        if text:
            try:
                return output_schema.model_validate_json(text)
            except ValueError as exc:
                raise ContractError("agent_schema_invalid") from exc
    raise ContractError("agent_response_missing")


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

    @property
    def capabilities(self):
        return self.delegate.capabilities

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        if len(_effective_request_bytes(llm_request)) > self.max_request_bytes:
            raise RoleExecutionError("model_request_budget_exceeded")
        async for response in self.delegate.generate_content_async(
            llm_request, stream
        ):
            yield response
