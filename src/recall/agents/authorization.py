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


class AuthorizationReceiptPersistenceError(RuntimeError):
    """The authorization decision could not be durably recorded."""


class AuthorizedBackendError(RuntimeError):
    """An allowed backend failed after its receipt was durably recorded."""

    def __init__(self, receipt: Artifact, cause: Exception) -> None:
        super().__init__("authorized_backend_failed")
        self.receipt = receipt
        self.cause = cause


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
        invocation_id = str(
            uuid5(UUID(self._run_id), f"tool-invocation:{self._request_count}")
        )
        return self._invoke(
            invocation_id,
            tool_id,
            requested_action,
            (),
            backend,
            *args,
            **kwargs,
        )

    def invoke_idempotent(
        self,
        invocation_id: str,
        tool_id: str,
        requested_action: str,
        denial_reason_codes: tuple[str, ...],
        backend: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> AuthorizedResult[T]:
        UUID(invocation_id)
        self._request_count += 1
        return self._invoke(
            invocation_id,
            tool_id,
            requested_action,
            denial_reason_codes,
            backend,
            *args,
            **kwargs,
        )

    def _invoke(
        self,
        invocation_id: str,
        tool_id: str,
        requested_action: str,
        denial_reason_codes: tuple[str, ...],
        backend: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> AuthorizedResult[T]:
        allowed = tool_id in self._allowed_tool_ids and not denial_reason_codes
        decision = ToolDecision.ALLOWED if allowed else ToolDecision.DENIED
        reason_codes = (
            []
            if allowed
            else list(denial_reason_codes or ("tool_not_allowlisted",))
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
        try:
            receipt = self._ledger.append_artifact(receipt_wire)
        except Exception as exc:  # noqa: BLE001 - persistence must fail closed
            raise AuthorizationReceiptPersistenceError(
                "authorization_receipt_persistence_failed"
            ) from exc
        if not allowed:
            self.counters = AuthorizationCounters(
                allowed=self.counters.allowed,
                denied=self.counters.denied + 1,
                backend_invocations=self.counters.backend_invocations,
            )
            return AuthorizedResult(receipt, None)
        self.counters = AuthorizationCounters(
            allowed=self.counters.allowed + 1,
            denied=self.counters.denied,
            backend_invocations=self.counters.backend_invocations + 1,
        )
        try:
            value = backend(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - preserve the persisted receipt
            raise AuthorizedBackendError(receipt, exc) from exc
        return AuthorizedResult(receipt, value)
