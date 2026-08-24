from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
import re
from typing import Any
from uuid import UUID

from recall.agents.authorization import (
    AuthorizationReceiptPersistenceError,
    AuthorizedBackendError,
    ToolAuthorizer,
)
from recall.agents.config import ROLE_TOOL_IDS
from recall.connectors import (
    CitedSource,
    PubMedConnector,
    RefetchAdapter,
    ReplayConnector,
)
from recall.contracts import AgentRole, canonical_json_bytes
from recall.controller.tool_capability import (
    RefetchGrant,
    RunToolCapability,
    ToolCapabilityCodec,
)
from recall.controller.tool_gateway_store import (
    GatewayInvocationStore,
    GatewayResponse,
    InMemoryGatewayInvocationStore,
)
from recall.controller.tool_gateway_identity import (
    IdentityVerifier,
    validate_gateway_identity_config,
    validate_identity_claims,
)
from recall.ledger import LedgerPort


GATEWAY_PROTOCOL_VERSION = "1.0"
MAX_GATEWAY_REQUEST_BYTES = 32 * 1024
MAX_GATEWAY_RESPONSE_BYTES = 64 * 1024
_REQUEST_FIELDS = frozenset(
    {"protocol_version", "request_id", "capability", "arguments"}
)
_ARGUMENT_FIELDS = {
    "evidence_connector": frozenset({"stage"}),
    "ledger_read": frozenset({"artifact_id"}),
    "refetch_metadata": frozenset({"claim_id"}),
}
_TOOL_PATH = re.compile(r"^/v1/tools/([a-z][a-z0-9_]*):invoke$")


@dataclass(frozen=True, slots=True)
class _Dispatch:
    denial_reasons: tuple[str, ...]
    backend: Callable[[], dict[str, object]]


class ToolGateway:
    def __init__(
        self,
        *,
        ledger: LedgerPort,
        replay_connector: ReplayConnector,
        pubmed_connector: PubMedConnector,
        refetch_adapter: RefetchAdapter,
        capability_codec: ToolCapabilityCodec,
        identity_verifier: IdentityVerifier,
        expected_audience: str,
        role_principals: Mapping[AgentRole, str],
        invocation_store: GatewayInvocationStore,
        clock: Callable[[], datetime],
    ) -> None:
        validate_gateway_identity_config(expected_audience, role_principals)
        self._ledger = ledger
        self._replay = replay_connector
        self._pubmed = pubmed_connector
        self._refetch = refetch_adapter
        self._codec = capability_codec
        self._identity = identity_verifier
        self._audience = expected_audience
        self._principals = dict(role_principals)
        self._store = invocation_store
        self._clock = clock

    def handle_http(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        body: Mapping[str, object],
    ) -> GatewayResponse:
        if method != "POST":
            return self._error(405, None, "gateway_method_not_allowed")
        match = _TOOL_PATH.fullmatch(path)
        if match is None:
            return self._error(404, None, "gateway_route_not_found")
        authorization = headers.get("Authorization", "")
        bearer = (
            authorization.removeprefix("Bearer ")
            if authorization.startswith("Bearer ")
            else ""
        )
        return self.handle(match.group(1), bearer, body)

    def handle(
        self,
        tool_id: str,
        bearer_token: str,
        body: Mapping[str, object],
    ) -> GatewayResponse:
        request = self._parse_request(body)
        if isinstance(request, GatewayResponse):
            return request
        request_id, capability_token, arguments = request
        if not bearer_token:
            return self._error(401, request_id, "endpoint_auth_missing")
        try:
            claims = self._identity.verify(bearer_token, self._audience)
        except Exception:  # noqa: BLE001 - external verifier fails closed
            return self._error(401, request_id, "endpoint_token_invalid")
        identity_error = validate_identity_claims(
            claims,
            expected_audience=self._audience,
            now=self._clock().astimezone(UTC),
        )
        if identity_error is not None:
            return self._error(401, request_id, identity_error)
        try:
            capability = self._codec.verify(capability_token)
        except ValueError as exc:
            return self._error(403, request_id, str(exc).split(":", 1)[0])
        if claims.get("email") != self._principals.get(capability.role):
            return self._error(
                401, request_id, "endpoint_principal_role_mismatch"
            )
        parsed_arguments = self._validate_arguments(tool_id, arguments)
        if isinstance(parsed_arguments, GatewayResponse):
            return GatewayResponse(
                parsed_arguments.status_code,
                {**parsed_arguments.body, "request_id": request_id},
            )
        dispatch = self._prepare_dispatch(tool_id, parsed_arguments, capability)
        request_hash = sha256(
            canonical_json_bytes(
                {
                    "tool_id": tool_id,
                    "capability": capability_token,
                    "arguments": parsed_arguments,
                }
            )
        ).hexdigest()
        try:
            reservation = self._store.reserve(
                request_id, request_hash, now=self._clock().astimezone(UTC)
            )
        except ValueError as exc:
            return self._error(409, request_id, str(exc))
        if reservation.state == "COMPLETE":
            assert reservation.response is not None
            return reservation.response
        if reservation.state == "PENDING":
            return self._error(409, request_id, "gateway_request_in_progress")
        authorizer = ToolAuthorizer(
            self._ledger,
            role=capability.role,
            allowed_tool_ids=ROLE_TOOL_IDS[capability.role],
            case_id=capability.case_id,
            run_id=capability.run_id,
            data_mode=capability.data_mode,
            clock=lambda: reservation.created_at,
        )
        requested_action = json.dumps(
            parsed_arguments, sort_keys=True, separators=(",", ":")
        )
        try:
            result = authorizer.invoke_idempotent(
                request_id,
                tool_id,
                requested_action,
                dispatch.denial_reasons,
                dispatch.backend,
            )
            response = GatewayResponse(
                200 if result.value is not None else 403,
                {
                    "protocol_version": GATEWAY_PROTOCOL_VERSION,
                    "request_id": request_id,
                    "decision": result.receipt.payload.decision.value,
                    "authorization_receipt": result.receipt.to_wire(),
                    "result": result.value,
                    "error": (
                        None
                        if result.value is not None
                        else "tool_authorization_denied"
                    ),
                },
            )
        except AuthorizationReceiptPersistenceError:
            response = self._error(
                503, request_id, "authorization_receipt_persistence_failed"
            )
        except AuthorizedBackendError as exc:
            detail = (
                str(exc.cause)
                if isinstance(exc.cause, RuntimeError)
                else type(exc.cause).__name__
            )
            response = GatewayResponse(
                502,
                {
                    "protocol_version": GATEWAY_PROTOCOL_VERSION,
                    "request_id": request_id,
                    "decision": "ALLOWED",
                    "authorization_receipt": exc.receipt.to_wire(),
                    "result": None,
                    "error": f"gateway_backend_failed:{detail}"[:200],
                },
            )
        except Exception:  # noqa: BLE001 - no receipt means no backend authority
            response = self._error(500, request_id, "tool_authorization_failed")
        if len(canonical_json_bytes(response.body)) > MAX_GATEWAY_RESPONSE_BYTES:
            response = GatewayResponse(
                502,
                {
                    "protocol_version": GATEWAY_PROTOCOL_VERSION,
                    "request_id": request_id,
                    "decision": response.body["decision"],
                    "authorization_receipt": response.body[
                        "authorization_receipt"
                    ],
                    "result": None,
                    "error": "gateway_response_too_large",
                },
            )
        self._store.complete(request_id, request_hash, response)
        return response

    def _parse_request(
        self, body: Mapping[str, object]
    ) -> tuple[str, str, Mapping[str, object]] | GatewayResponse:
        if not isinstance(body, Mapping) or set(body) != _REQUEST_FIELDS:
            return self._error(400, None, "gateway_request_fields_invalid")
        if len(canonical_json_bytes(body)) > MAX_GATEWAY_REQUEST_BYTES:
            return self._error(413, None, "gateway_request_too_large")
        request_id = body["request_id"]
        capability = body["capability"]
        arguments = body["arguments"]
        try:
            UUID(str(request_id))
        except ValueError:
            return self._error(400, None, "gateway_request_id_invalid")
        if (
            not isinstance(capability, str)
            or not capability
            or len(capability) > 24 * 1024
        ):
            return self._error(400, str(request_id), "tool_capability_missing")
        if body["protocol_version"] != GATEWAY_PROTOCOL_VERSION:
            return self._error(
                400, str(request_id), "gateway_protocol_version_invalid"
            )
        if not isinstance(arguments, Mapping):
            return self._error(
                400, str(request_id), "gateway_request_arguments_invalid"
            )
        return str(request_id), capability, arguments

    def _validate_arguments(
        self, tool_id: str, arguments: Mapping[str, object]
    ) -> dict[str, object] | GatewayResponse:
        expected = _ARGUMENT_FIELDS.get(tool_id)
        if expected is None:
            return dict(arguments)
        if set(arguments) != expected or any(
            not isinstance(arguments[field], str) or not arguments[field]
            or len(arguments[field]) > 4096
            for field in expected
        ):
            return self._error(400, None, "gateway_request_fields_invalid")
        return dict(arguments)

    def _prepare_dispatch(
        self,
        tool_id: str,
        arguments: Mapping[str, object],
        capability: RunToolCapability,
    ) -> _Dispatch:
        reasons: list[str] = []
        if tool_id not in capability.allowed_tool_ids:
            return _Dispatch(("tool_not_allowlisted",), lambda: {})
        if tool_id == "evidence_connector":
            stage = str(arguments["stage"])
            if stage not in capability.allowed_replay_stages:
                reasons.append("replay_stage_not_granted")
            return _Dispatch(tuple(sorted(set(reasons))), lambda: self._replay.tool_result(stage))
        if tool_id == "ledger_read":
            artifact_id = str(arguments["artifact_id"])
            if artifact_id not in capability.allowed_artifact_ids:
                reasons.append("artifact_not_granted")
            return _Dispatch(
                tuple(sorted(set(reasons))),
                lambda: {
                    "artifact": self._read_authorized_artifact(
                        artifact_id, capability
                    )
                },
            )
        if tool_id == "refetch_metadata":
            claim_id = str(arguments["claim_id"])
            grant = next(
                (
                    item
                    for item in capability.refetch_grants
                    if item.claim_id == claim_id
                ),
                None,
            )
            if grant is None:
                reasons.append("refetch_claim_not_granted")
                return _Dispatch(tuple(sorted(set(reasons))), lambda: {})
            return _Dispatch(
                tuple(sorted(set(reasons))),
                lambda: self._refetch_grant(grant, capability),
            )
        return _Dispatch(tuple(sorted(set(reasons))), lambda: {})

    def _read_authorized_artifact(
        self, artifact_id: str, capability: RunToolCapability
    ) -> dict[str, object]:
        reasons: list[str] = []
        if artifact_id not in capability.allowed_artifact_ids:
            reasons.append("artifact_not_granted")
        artifact = self._ledger.get_artifact(artifact_id)
        if artifact is None:
            reasons.append("artifact_missing")
        else:
            if artifact["case_id"] != capability.case_id:
                reasons.append("artifact_case_mismatch")
            if artifact["run_id"] != capability.run_id:
                reasons.append("artifact_run_mismatch")
            if (
                artifact["schema_name"]
                not in capability.allowed_artifact_schema_names
            ):
                reasons.append("artifact_schema_not_granted")
            if artifact["data_mode"] != capability.data_mode.value:
                reasons.append("artifact_data_mode_mismatch")
        if reasons:
            raise RuntimeError(
                f"gateway_artifact_scope_invalid:{','.join(sorted(set(reasons)))}"
            )
        assert artifact is not None
        return deepcopy(artifact)

    def _refetch_grant(
        self, grant: RefetchGrant, capability: RunToolCapability
    ) -> dict[str, object]:
        artifact = self._read_authorized_artifact(
            grant.source_artifact_id, capability
        )
        if artifact["content_hash"] != grant.source_artifact_content_hash:
            raise RuntimeError("source_artifact_hash_mismatch")
        cited = CitedSource(
            identifier=grant.identifier,
            title=grant.title,
            locator=grant.locator,
            content_hash=grant.content_hash,
            mode=grant.data_mode,
        )
        return self._refetch.refetch(cited, self._pubmed.fetch).to_claim_verdict(
            grant.claim_id
        )

    @staticmethod
    def _error(
        status_code: int, request_id: str | None, code: str
    ) -> GatewayResponse:
        return GatewayResponse(
            status_code,
            {
                "protocol_version": GATEWAY_PROTOCOL_VERSION,
                "request_id": request_id,
                "decision": "DENIED",
                "authorization_receipt": None,
                "result": None,
                "error": code,
            },
        )
