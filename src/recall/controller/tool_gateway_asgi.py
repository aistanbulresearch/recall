from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any

from recall.controller.tool_gateway import (
    MAX_GATEWAY_REQUEST_BYTES,
    GatewayResponse,
    ToolGateway,
)


class ToolGatewayAsgiApp:
    """Dependency-free ASGI adapter for the internal Cloud Run service."""

    def __init__(self, gateway: ToolGateway) -> None:
        self._gateway = gateway

    async def __call__(
        self,
        scope: Mapping[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        if scope.get("type") != "http":
            await self._send(send, _error(404, "gateway_scope_invalid"))
            return
        headers = {
            key.decode("latin-1").title(): value.decode("latin-1")
            for key, value in scope.get("headers", ())
        }
        content_type = headers.get("Content-Type", "")
        if not content_type.startswith("application/json"):
            await self._send(send, _error(415, "gateway_content_type_invalid"))
            return
        raw = bytearray()
        while True:
            message = await receive()
            if message.get("type") != "http.request":
                await self._send(send, _error(400, "gateway_request_invalid"))
                return
            raw.extend(message.get("body", b""))
            if len(raw) > MAX_GATEWAY_REQUEST_BYTES:
                await self._send(send, _error(413, "gateway_request_too_large"))
                return
            if not message.get("more_body", False):
                break
        try:
            body = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            await self._send(send, _error(400, "gateway_json_invalid"))
            return
        if not isinstance(body, Mapping):
            await self._send(send, _error(400, "gateway_json_invalid"))
            return
        response = self._gateway.handle_http(
            str(scope.get("method", "")),
            str(scope.get("path", "")),
            headers,
            body,
        )
        await self._send(send, response)

    @staticmethod
    async def _send(send: Any, response: GatewayResponse) -> None:
        body = json.dumps(
            response.body, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": response.status_code,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body})


def _error(status: int, code: str) -> GatewayResponse:
    return GatewayResponse(
        status,
        {
            "protocol_version": "1.0",
            "request_id": None,
            "decision": "DENIED",
            "authorization_receipt": None,
            "result": None,
            "error": code,
        },
    )
