from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ..enums import AgentExecutionStatus, AgentRole, ExecutionProfile
from ..errors import ContractError
from ..validation import enum_value, non_empty_string, require_exact_fields, tuple_of_strings, uuid_value
from .lifecycle import _non_negative_int, _timestamp


_TURN_FIELDS = frozenset(
    {
        "turn_index",
        "prompt_tokens",
        "candidate_tokens",
        "thoughts_tokens",
        "total_tokens",
        "finish_reason",
        "function_call_emitted",
        "latency_ms",
    }
)

_TOOL_RECORD_FIELDS = frozenset(
    {
        "tool_id",
        "call_id",
        "response_id",
        "adk_invocation_id",
        "request_id",
        "authorization_receipt_id",
    }
)


@dataclass(frozen=True, slots=True)
class AgentExecutionReceiptPayload:
    execution_profile: ExecutionProfile
    agent_role: AgentRole
    attempt: int
    execution_status: AgentExecutionStatus
    runtime_class: str
    model_id: str
    model_revision: str
    endpoint_class: str
    location: str
    trace_id: str
    invocation_id: str
    started_at: str
    completed_at: str | None
    latency_ms: int | None
    turns: tuple[Mapping[str, object], ...]
    http_429_count: int
    tool_call_ids: tuple[str, ...]
    tool_response_ids: tuple[str, ...]
    tool_records: tuple[Mapping[str, str], ...]
    started_receipt_id: str | None
    failure_code: str | None

    def to_wire(self) -> dict[str, object]:
        return {
            "execution_profile": self.execution_profile.value,
            "agent_role": self.agent_role.value,
            "attempt": self.attempt,
            "execution_status": self.execution_status.value,
            "runtime_class": self.runtime_class,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "endpoint_class": self.endpoint_class,
            "location": self.location,
            "trace_id": self.trace_id,
            "invocation_id": self.invocation_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "latency_ms": self.latency_ms,
            "turns": [dict(turn) for turn in self.turns],
            "http_429_count": self.http_429_count,
            "tool_call_ids": list(self.tool_call_ids),
            "tool_response_ids": list(self.tool_response_ids),
            "tool_records": [dict(record) for record in self.tool_records],
            "started_receipt_id": self.started_receipt_id,
            "failure_code": self.failure_code,
        }


def parse_agent_execution_receipt_payload(
    value: Mapping[str, Any],
) -> AgentExecutionReceiptPayload:
    role = enum_value(AgentRole, value["agent_role"], "agent_role")
    status = enum_value(
        AgentExecutionStatus, value["execution_status"], "execution_status"
    )
    attempt = _non_negative_int(value["attempt"], "attempt")
    if attempt < 1:
        raise ContractError("contract_value_invalid", "attempt")
    turns = _parse_turns(value["turns"])
    http_429_count = _non_negative_int(value["http_429_count"], "http_429_count")
    tool_calls = tuple_of_strings(value["tool_call_ids"], "tool_call_ids")
    tool_responses = tuple_of_strings(
        value["tool_response_ids"], "tool_response_ids"
    )
    tool_records = _parse_tool_records(value["tool_records"])
    if len(tool_responses) > len(tool_calls):
        raise ContractError("contract_value_invalid", "tool_response_ids")
    completed_at = value["completed_at"]
    latency_ms = value["latency_ms"]
    started_receipt_id = uuid_value(
        value["started_receipt_id"], "started_receipt_id", nullable=True
    )
    failure_code = value["failure_code"]
    if failure_code is not None:
        failure_code = non_empty_string(failure_code, "failure_code")
    if status is AgentExecutionStatus.STARTED:
        if any(
            item is not None
            for item in (completed_at, latency_ms, started_receipt_id, failure_code)
        ) or turns or http_429_count or tool_calls or tool_responses or tool_records:
            raise ContractError("contract_value_invalid", "execution_status")
    else:
        completed_at = _timestamp(completed_at, "completed_at")
        latency_ms = _non_negative_int(latency_ms, "latency_ms")
        if started_receipt_id is None or (
            status is AgentExecutionStatus.COMPLETED and not turns
        ):
            raise ContractError("contract_value_invalid", "started_receipt_id")
        if status is AgentExecutionStatus.COMPLETED and failure_code is not None:
            raise ContractError("contract_value_invalid", "failure_code")
        if status is AgentExecutionStatus.FAILED and failure_code is None:
            raise ContractError("contract_required_value_missing", "failure_code")
        if started_receipt_id not in value["input_artifact_ids"]:
            raise ContractError("contract_value_invalid", "started_receipt_id")
        if status is AgentExecutionStatus.COMPLETED:
            record_calls = tuple(record["call_id"] for record in tool_records)
            record_responses = tuple(record["response_id"] for record in tool_records)
            if (
                not tool_records
                or len(set(record_calls)) != len(record_calls)
                or set(record_calls) != set(tool_calls)
                or set(record_responses) != set(tool_responses)
            ):
                raise ContractError("contract_value_invalid", "tool_records")
            authorization_ids = {
                record["authorization_receipt_id"] for record in tool_records
            }
            if not authorization_ids.issubset(set(value["input_artifact_ids"])):
                raise ContractError(
                    "contract_value_invalid", "authorization_receipt_id"
                )
            tool_ids = tuple(record["tool_id"] for record in tool_records)
            if role is AgentRole.EVIDENCE_WATCHER and tool_ids != (
                "evidence_connector",
            ):
                raise ContractError("contract_value_invalid", "tool_records")
            if role is AgentRole.EVIDENCE_ASSESSOR and tool_ids != (
                "ledger_read",
            ):
                raise ContractError("contract_value_invalid", "tool_records")
            if role is AgentRole.CITATION_AUDITOR and (
                tool_ids.count("ledger_read") != 1
                or any(
                    tool_id not in {"ledger_read", "refetch_metadata"}
                    for tool_id in tool_ids
                )
            ):
                raise ContractError("contract_value_invalid", "tool_records")
    return AgentExecutionReceiptPayload(
        execution_profile=enum_value(
            ExecutionProfile, value["execution_profile"], "execution_profile"
        ),
        agent_role=role,
        attempt=attempt,
        execution_status=status,
        runtime_class=_closed_string(
            value["runtime_class"], "runtime_class", {"IN_PROCESS_ADK_CLOUD_RUN"}
        ),
        model_id=non_empty_string(value["model_id"], "model_id"),
        model_revision=non_empty_string(value["model_revision"], "model_revision"),
        endpoint_class=_closed_string(
            value["endpoint_class"], "endpoint_class", {"VERTEX_AI_GLOBAL"}
        ),
        location=_closed_string(value["location"], "location", {"global"}),
        trace_id=str(uuid_value(value["trace_id"], "trace_id")),
        invocation_id=str(uuid_value(value["invocation_id"], "invocation_id")),
        started_at=_timestamp(value["started_at"], "started_at"),
        completed_at=completed_at,
        latency_ms=latency_ms,
        turns=turns,
        http_429_count=http_429_count,
        tool_call_ids=tool_calls,
        tool_response_ids=tool_responses,
        tool_records=tool_records,
        started_receipt_id=started_receipt_id,
        failure_code=failure_code,
    )


def _parse_turns(value: Any) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list):
        raise ContractError("contract_type_invalid", "turns")
    parsed: list[Mapping[str, object]] = []
    for index, raw in enumerate(value, start=1):
        if not isinstance(raw, Mapping):
            raise ContractError("contract_type_invalid", "turns")
        require_exact_fields(raw, _TURN_FIELDS, f"turns[{index - 1}]")
        turn_index = _non_negative_int(raw["turn_index"], "turn_index")
        if turn_index != index:
            raise ContractError("contract_value_invalid", "turn_index")
        counts = {
            field: _non_negative_int(raw[field], field)
            for field in (
                "prompt_tokens",
                "candidate_tokens",
                "thoughts_tokens",
                "total_tokens",
                "latency_ms",
            )
        }
        if counts["total_tokens"] != (
            counts["prompt_tokens"]
            + counts["candidate_tokens"]
            + counts["thoughts_tokens"]
        ):
            raise ContractError("contract_value_invalid", "total_tokens")
        if not isinstance(raw["function_call_emitted"], bool):
            raise ContractError("contract_type_invalid", "function_call_emitted")
        parsed.append(
            MappingProxyType(
                {
                    "turn_index": turn_index,
                    **counts,
                    "finish_reason": non_empty_string(
                        raw["finish_reason"], "finish_reason"
                    ),
                    "function_call_emitted": raw["function_call_emitted"],
                }
            )
        )
    return tuple(parsed)


def _parse_tool_records(value: Any) -> tuple[Mapping[str, str], ...]:
    if not isinstance(value, list):
        raise ContractError("contract_type_invalid", "tool_records")
    parsed: list[Mapping[str, str]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise ContractError("contract_type_invalid", "tool_records")
        require_exact_fields(raw, _TOOL_RECORD_FIELDS, f"tool_records[{index}]")
        parsed.append(
            MappingProxyType(
                {
                    "tool_id": non_empty_string(raw["tool_id"], "tool_id"),
                    "call_id": non_empty_string(raw["call_id"], "call_id"),
                    "response_id": non_empty_string(
                        raw["response_id"], "response_id"
                    ),
                    "adk_invocation_id": non_empty_string(
                        raw["adk_invocation_id"], "adk_invocation_id"
                    ),
                    "request_id": str(
                        uuid_value(raw["request_id"], "request_id")
                    ),
                    "authorization_receipt_id": str(
                        uuid_value(
                            raw["authorization_receipt_id"],
                            "authorization_receipt_id",
                        )
                    ),
                }
            )
        )
    return tuple(parsed)


def _closed_string(value: Any, field: str, allowed: set[str]) -> str:
    parsed = non_empty_string(value, field)
    if parsed not in allowed:
        raise ContractError("contract_enum_invalid", field)
    return parsed
