from __future__ import annotations

import asyncio
import json
from typing import Any

from recall.controller.tool_gateway import GatewayResponse
from recall.controller.tool_gateway_asgi import (
    MAX_GATEWAY_REQUEST_BYTES,
    ToolGatewayAsgiApp,
)


class RecordingGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def handle_http(self, method: str, path: str, headers: dict[str, str], body: dict[str, object]) -> GatewayResponse:
        self.calls.append((method, path, headers, body))
        return GatewayResponse(
            401,
            {
                "protocol_version": "1.0",
                "request_id": None,
                "decision": "DENIED",
                "authorization_receipt": None,
                "result": None,
                "error": "endpoint_auth_missing",
            },
        )


def _invoke(body: bytes) -> tuple[RecordingGateway, list[dict[str, Any]]]:
    gateway = RecordingGateway()
    app = ToolGatewayAsgiApp(gateway)  # type: ignore[arg-type]
    sent: list[dict[str, Any]] = []
    delivered = False

    async def receive() -> dict[str, Any]:
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(
        app(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/tools/ledger_read:invoke",
                "headers": [(b"content-type", b"application/json")],
            },
            receive,
            send,
        )
    )
    return gateway, sent


def test_asgi_adapter_passes_closed_json_to_gateway_and_returns_json() -> None:
    gateway, sent = _invoke(b'{"protocol_version":"1.0"}')
    assert gateway.calls[0][0:2] == (
        "POST",
        "/v1/tools/ledger_read:invoke",
    )
    assert gateway.calls[0][3] == {"protocol_version": "1.0"}
    assert sent[0]["status"] == 401
    assert json.loads(sent[1]["body"])["error"] == "endpoint_auth_missing"


def test_asgi_adapter_rejects_oversized_body_before_gateway() -> None:
    gateway, sent = _invoke(b"{" + b"x" * MAX_GATEWAY_REQUEST_BYTES + b"}")
    assert gateway.calls == []
    assert sent[0]["status"] == 413
    assert json.loads(sent[1]["body"])["error"] == "gateway_request_too_large"
