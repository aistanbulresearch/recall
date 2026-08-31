from __future__ import annotations

from uuid import UUID, uuid5

from .enums import AgentRole


def tool_request_id(
    *,
    run_id: str,
    role: AgentRole,
    attempt: int,
    role_execution_invocation_id: str,
    adk_invocation_id: str,
    function_call_id: str,
    tool_id: str,
) -> str:
    """Return the persisted authorization identity for one ADK tool call."""

    UUID(role_execution_invocation_id)
    if not adk_invocation_id:
        raise ValueError("tool_call_identity_invalid")
    if attempt < 1 or not function_call_id or not tool_id:
        raise ValueError("tool_call_identity_invalid")
    return str(
        uuid5(
            UUID(run_id),
            "|".join(
                (
                    role.value,
                    str(attempt),
                    role_execution_invocation_id,
                    adk_invocation_id,
                    function_call_id,
                    tool_id,
                )
            ),
        )
    )
