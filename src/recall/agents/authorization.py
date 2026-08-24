from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid5

from recall.contracts import (
    AgentRole,
    Artifact,
    ArtifactStatus,
    DataMode,
    ToolDecision,
    build_artifact,
)
from recall.ledger import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY

from .config import POLICY_VERSION, ROLE_TOOL_IDS


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class AuthorizationCounters:
    allowed: int = 0
    denied: int = 0
    backend_invocations: int = 0


@dataclass(frozen=True, slots=True)
class AuthorizedResult(Generic[T]):
    receipt: Artifact
    value: T | None


class ToolAuthorizer:
    def __init__(
        self,
        ledger: LedgerPort,
        *,
        role: AgentRole,
        allowed_tool_ids: frozenset[str],
        case_id: str,
        run_id: str,
        data_mode: DataMode,
        clock: Callable[[], datetime],
    ) -> None:
        if allowed_tool_ids != ROLE_TOOL_IDS[role]:
            raise ValueError(f"agent_tool_set_invalid:{role.value}")
        self._ledger = ledger
        self._role = role
        self._allowed_tool_ids = allowed_tool_ids
        self._case_id = case_id
        self._run_id = run_id
        self._data_mode = data_mode
        self._clock = clock
        self._request_count = 0
        self.counters = AuthorizationCounters()

    def invoke(
        self,
        tool_id: str,
        requested_action: str,
        backend: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> AuthorizedResult[T]:
        self._request_count += 1
        allowed = tool_id in self._allowed_tool_ids
        decision = ToolDecision.ALLOWED if allowed else ToolDecision.DENIED
        reason_codes = [] if allowed else ["tool_not_allowlisted"]
        invocation_id = str(
            uuid5(UUID(self._run_id), f"tool-invocation:{self._request_count}")
        )
        now = self._clock()
        receipt_wire = build_artifact(
            schema_name="ToolAuthorizationReceipt",
            schema_version="1.0.0",
            artifact_id=str(uuid5(UUID(invocation_id), "authorization-receipt")),
            case_id=self._case_id,
            run_id=self._run_id,
            producer={
                "component": "controller-authorizer",
                "version": POLICY_VERSION,
                "identity": "controller-authorizer",
            },
            created_at=now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            input_artifact_ids=(),
            data_mode=self._data_mode,
            status=ArtifactStatus.VALID,
            payload={
                "agent_role": self._role.value,
                "tool_id": tool_id,
                "requested_action": requested_action,
                "decision": decision.value,
                "policy_version": POLICY_VERSION,
                "reason_codes": reason_codes,
                "invocation_id": invocation_id,
            },
            authorized_producers=PRODUCER_REGISTRY,
        )
        receipt = self._ledger.append_artifact(receipt_wire)
        if not allowed:
            self.counters = AuthorizationCounters(
                allowed=self.counters.allowed,
                denied=self.counters.denied + 1,
                backend_invocations=self.counters.backend_invocations,
            )
            return AuthorizedResult(receipt, None)
        value = backend(*args, **kwargs)
        self.counters = AuthorizationCounters(
            allowed=self.counters.allowed + 1,
            denied=self.counters.denied,
            backend_invocations=self.counters.backend_invocations + 1,
        )
        return AuthorizedResult(receipt, value)
