from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import os
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid5

from google.adk.tools import ToolContext

from recall.contracts import AgentRole
from recall.controller.tool_capability import CAPABILITY_STATE_KEY


GATEWAY_PROTOCOL_VERSION = "1.0"
_RESPONSE_FIELDS = frozenset(
    {
        "protocol_version",
        "request_id",
        "decision",
        "authorization_receipt",
        "result",
        "error",
    }
)


class GatewayTransport(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        body: dict[str, object],
        timeout_seconds: float,
    ) -> tuple[int, dict[str, object]]: ...


class UrlLibGatewayTransport:
    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        body: dict[str, object],
        timeout_seconds: float,
    ) -> tuple[int, dict[str, object]]:
        request = Request(
            url,
            data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                status = response.status
                raw = response.read()
        except HTTPError as exc:
            status = exc.code
            raw = exc.read()
        except (OSError, TimeoutError, URLError) as exc:
            raise RuntimeError("tool_gateway_unavailable") from exc
        try:
            parsed = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("tool_gateway_response_invalid") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("tool_gateway_response_invalid")
        return status, parsed


def _google_identity_token(audience: str) -> str:
    from google.auth.transport.requests import Request
    from google.oauth2.id_token import fetch_id_token

    return fetch_id_token(Request(), audience)


class ToolGatewayClient:
    def __init__(
        self,
        *,
        endpoint_url: str,
        audience: str,
        token_provider: Callable[[str], str],
        transport: GatewayTransport,
        timeout_seconds: float = 20.0,
    ) -> None:
        if not endpoint_url.startswith("https://"):
            raise ValueError("tool_gateway_https_required")
        if not audience:
            raise ValueError("tool_gateway_audience_required")
        if timeout_seconds <= 0:
            raise ValueError("tool_gateway_timeout_invalid")
        self._endpoint = endpoint_url.rstrip("/")
        self._audience = audience
        self._token_provider = token_provider
        self._transport = transport
        self._timeout = timeout_seconds

    def invoke(
        self,
        tool_id: str,
        arguments: Mapping[str, object],
        tool_context: ToolContext,
    ) -> dict[str, object]:
        state = getattr(tool_context, "state", None)
        capability = (
            state.get(CAPABILITY_STATE_KEY) if isinstance(state, Mapping) else None
        )
        if not isinstance(capability, str) or not capability:
            raise RuntimeError("tool_capability_missing")
        invocation_id = getattr(tool_context, "invocation_id", None)
        function_call_id = getattr(tool_context, "function_call_id", None)
        if not isinstance(invocation_id, str) or not invocation_id:
            raise RuntimeError("tool_context_invocation_id_missing")
        if not isinstance(function_call_id, str) or not function_call_id:
            raise RuntimeError("tool_context_function_call_id_missing")
        request_id = str(
            uuid5(
                NAMESPACE_URL,
                f"recall:{invocation_id}:{function_call_id}:{tool_id}",
            )
        )
        body: dict[str, object] = {
            "protocol_version": GATEWAY_PROTOCOL_VERSION,
            "request_id": request_id,
            "capability": capability,
            "arguments": dict(arguments),
        }
        token = self._token_provider(self._audience)
        status, response = self._transport.post(
            f"{self._endpoint}/v1/tools/{tool_id}:invoke",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            body=body,
            timeout_seconds=self._timeout,
        )
        if (
            set(response) != _RESPONSE_FIELDS
            or response.get("protocol_version") != GATEWAY_PROTOCOL_VERSION
        ):
            raise RuntimeError("tool_gateway_response_invalid")
        if response.get("request_id") != request_id:
            raise RuntimeError("tool_gateway_request_mismatch")
        if status != 200 or response.get("decision") != "ALLOWED":
            error = response.get("error")
            code = error if isinstance(error, str) else "tool_gateway_denied"
            raise RuntimeError(code)
        result = response.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("tool_gateway_result_invalid")
        return result


def _client_from_environment() -> ToolGatewayClient:
    endpoint = os.environ.get("RECALL_TOOL_GATEWAY_URL", "")
    audience = os.environ.get("RECALL_TOOL_GATEWAY_AUDIENCE", endpoint)
    timeout_text = os.environ.get("RECALL_TOOL_GATEWAY_TIMEOUT_SECONDS", "20")
    try:
        timeout = float(timeout_text)
    except ValueError as exc:
        raise RuntimeError("tool_gateway_timeout_invalid") from exc
    return ToolGatewayClient(
        endpoint_url=endpoint,
        audience=audience,
        token_provider=_google_identity_token,
        transport=UrlLibGatewayTransport(),
        timeout_seconds=timeout,
    )


def evidence_connector(stage: str, tool_context: ToolContext) -> dict[str, object]:
    """Read the authorized frozen evidence replay stage through Controller."""

    return _client_from_environment().invoke(
        "evidence_connector", {"stage": stage}, tool_context
    )


def ledger_read(artifact_id: str, tool_context: ToolContext) -> dict[str, object]:
    """Read one Controller-granted authoritative artifact by UUID."""

    return _client_from_environment().invoke(
        "ledger_read", {"artifact_id": artifact_id}, tool_context
    )


def refetch_metadata(claim_id: str, tool_context: ToolContext) -> dict[str, object]:
    """Refetch one Controller-granted claim from its authoritative citation."""

    return _client_from_environment().invoke(
        "refetch_metadata", {"claim_id": claim_id}, tool_context
    )


def production_tools_for(
    role: AgentRole,
) -> Mapping[str, Callable[..., dict[str, object]]]:
    if role is AgentRole.EVIDENCE_WATCHER:
        return {"evidence_connector": evidence_connector}
    if role is AgentRole.EVIDENCE_ASSESSOR:
        return {"ledger_read": ledger_read}
    if role is AgentRole.CITATION_AUDITOR:
        return {
            "ledger_read": ledger_read,
            "refetch_metadata": refetch_metadata,
        }
    raise ValueError(f"production_tools_unavailable:{role.value}")
