from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel

from recall.contracts import AgentRole, DataMode
from recall.connectors.live import LiveSourceRecord

from .local_tools import LocalToolCallContext


MAX_MODEL_TURNS_PER_ROLE = 2


@dataclass(frozen=True, slots=True)
class TurnTelemetry:
    turn_index: int
    prompt_tokens: int
    candidate_tokens: int
    thoughts_tokens: int
    total_tokens: int
    finish_reason: str
    function_call_emitted: bool
    latency_ms: int

    def to_wire(self) -> dict[str, object]:
        return {
            "turn_index": self.turn_index,
            "prompt_tokens": self.prompt_tokens,
            "candidate_tokens": self.candidate_tokens,
            "thoughts_tokens": self.thoughts_tokens,
            "total_tokens": self.total_tokens,
            "finish_reason": self.finish_reason,
            "function_call_emitted": self.function_call_emitted,
            "latency_ms": self.latency_ms,
        }


@dataclass(frozen=True, slots=True)
class RoleRunResult:
    output: BaseModel
    turns: tuple[TurnTelemetry, ...]
    tool_call_ids: tuple[str, ...]
    tool_response_ids: tuple[str, ...]
    trace_id: str
    invocation_id: str
    started_at: datetime
    completed_at: datetime
    http_429_count: int
    tool_results: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    tool_records: tuple[Mapping[str, str], ...] = ()


class RoleExecutionError(RuntimeError):
    """Preserve provider telemetry when an ADK role invocation fails."""

    def __init__(
        self,
        code: str,
        *,
        turns: tuple[TurnTelemetry, ...] = (),
        http_429_count: int = 0,
        tool_records: tuple[Mapping[str, str], ...] = (),
        tool_call_ids: tuple[str, ...] = (),
        tool_response_ids: tuple[str, ...] = (),
    ) -> None:
        super().__init__(code)
        self.code = code
        self.turns = turns
        self.http_429_count = http_429_count
        self.tool_records = tool_records
        self.tool_call_ids = tool_call_ids
        self.tool_response_ids = tool_response_ids


@dataclass(frozen=True, slots=True)
class PreparedRunEvidence:
    case_id: str
    cloud_bound_payload: Mapping[str, object]
    source_cursors: Mapping[str, str]
    data_mode: DataMode
    replay_observations: tuple[Mapping[str, object], ...]
    citation_sources: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    refetch_fetcher: Callable[[str], LiveSourceRecord] | None = None


@dataclass(frozen=True, slots=True)
class RoleExecutionContext:
    case_id: str
    run_id: str
    attempt: int
    invocation_id: str
    input_artifact_ids: tuple[str, ...]
    trace_id: str

    def tool_context(self, function_call_id: str) -> LocalToolCallContext:
        return LocalToolCallContext(self.invocation_id, function_call_id)


class RoleRunner(Protocol):
    async def execute(
        self,
        role: AgentRole,
        prompt: str,
        tools: Mapping[str, Callable[..., dict[str, object]]],
        context: RoleExecutionContext,
    ) -> RoleRunResult: ...


@dataclass(frozen=True, slots=True)
class FullAuditRunOutcome:
    case_id: str
    run_id: str
    terminal_state: str
    audit_status: str
    citation_audit_receipt_id: str | None
    policy_decision_id: str | None
    policy_outcome: str | None
    policy_reason_codes: tuple[str, ...]
    technical_failure_codes: tuple[str, ...]
    failure_receipt_ids: tuple[str, ...]
    agent_execution_receipt_ids: tuple[str, ...]
    elapsed_ms: int
    turns: tuple[TurnTelemetry, ...]
    http_429_count: int
