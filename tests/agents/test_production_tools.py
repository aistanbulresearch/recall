from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from google.adk.tools.function_tool import FunctionTool

from recall.agents import tools
from recall.agents.tools import ToolGatewayClient


@dataclass
class FakeToolContext:
    state: dict[str, object]
    invocation_id: str = "managed-invocation-1"
    function_call_id: str = "function-call-1"


class RecordingTransport:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        body: dict[str, object],
        timeout_seconds: float,
    ) -> tuple[int, dict[str, object]]:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "body": body,
                "timeout_seconds": timeout_seconds,
            }
        )
        return 200, {
            "protocol_version": "1.0",
            "request_id": body["request_id"],
            "decision": "ALLOWED",
            "authorization_receipt": {"artifact_id": "receipt-1"},
            "result": self.result,
            "error": None,
        }


def _client(transport: RecordingTransport) -> ToolGatewayClient:
    return ToolGatewayClient(
        endpoint_url="https://controller.internal",
        audience="https://controller.internal",
        token_provider=lambda _audience: "signed-oidc-token",
        transport=transport,
        timeout_seconds=12,
    )


def _context() -> FakeToolContext:
    return FakeToolContext(state={"recall.tool_capability": "signed-capability"})


def test_gateway_client_sends_opaque_capability_and_returns_non_echo_result() -> None:
    transport = RecordingTransport({"protocol_id": "RCL-205"})
    result = _client(transport).invoke(
        "evidence_connector", {"stage": "stage-1"}, _context()
    )
    assert result == {"protocol_id": "RCL-205"}
    assert result != {"stage": "stage-1"}
    call = transport.calls[0]
    assert call["url"] == "https://controller.internal/v1/tools/evidence_connector:invoke"
    assert call["headers"] == {
        "Authorization": "Bearer signed-oidc-token",
        "Content-Type": "application/json",
    }
    assert call["body"]["capability"] == "signed-capability"
    assert call["body"]["arguments"] == {"stage": "stage-1"}


def test_module_level_callables_use_real_gateway_client_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = RecordingTransport({"artifact": {"schema_name": "EvidenceDelta"}})
    monkeypatch.setattr(tools, "_client_from_environment", lambda: _client(transport))
    result = tools.ledger_read("11111111-1111-4111-8111-111111111111", _context())
    assert result == {"artifact": {"schema_name": "EvidenceDelta"}}
    assert transport.calls[0]["body"]["arguments"] == {
        "artifact_id": "11111111-1111-4111-8111-111111111111"
    }


def test_refetch_callable_accepts_claim_id_only(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = RecordingTransport(
        {"claim_id": "claim-001", "verdict": "UNAVAILABLE", "refetched_source": None}
    )
    monkeypatch.setattr(tools, "_client_from_environment", lambda: _client(transport))
    result = tools.refetch_metadata("claim-001", _context())
    assert result["refetched_source"] is None
    assert transport.calls[0]["body"]["arguments"] == {"claim_id": "claim-001"}


def test_adk_schema_exposes_arguments_but_not_tool_context() -> None:
    declaration = FunctionTool(tools.evidence_connector)._get_declaration()
    schema = declaration.parameters_json_schema
    assert schema is not None
    assert schema["properties"] == {"stage": {"title": "Stage", "type": "string"}}
    assert "tool_context" not in schema["properties"]


@pytest.mark.parametrize(
    "context",
    [
        FakeToolContext(state={}),
        FakeToolContext(state={"recall.tool_capability": ""}),
    ],
)
def test_missing_managed_capability_fails_before_http(context: FakeToolContext) -> None:
    transport = RecordingTransport({})
    with pytest.raises(RuntimeError, match="tool_capability_missing"):
        _client(transport).invoke("ledger_read", {"artifact_id": "x"}, context)
    assert transport.calls == []
