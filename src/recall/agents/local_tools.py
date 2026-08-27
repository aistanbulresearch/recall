from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from recall.agents.authorization import ToolAuthorizer
from recall.agents.config import ROLE_TOOL_IDS
from recall.contracts import AgentRole, DataMode, canonical_json_bytes
from recall.contracts.tool_causality import tool_request_id
from recall.connectors import CitedSource, RefetchAdapter
from recall.connectors.live import LiveSourceRecord
from recall.controller.tool_gateway_store import (
    GatewayInvocationStore,
    GatewayResponse,
)
from recall.ledger.port import LedgerPort


@dataclass(frozen=True, slots=True)
class LocalToolCallContext:
    invocation_id: str
    function_call_id: str


@dataclass(frozen=True, slots=True)
class LocalToolInputs:
    case_id: str
    run_id: str
    role: AgentRole
    attempt: int
    role_execution_invocation_id: str
    data_mode: DataMode
    evidence_records: tuple[Mapping[str, object], ...]
    clock: Callable[[], Any]
    citation_sources: Mapping[str, Mapping[str, object]]
    refetch_fetcher: Callable[[str], LiveSourceRecord] | None = None
    tool_record_sink: Callable[[Mapping[str, str]], None] | None = None


def build_local_tools(
    ledger: LedgerPort,
    invocation_store: GatewayInvocationStore,
    inputs: LocalToolInputs,
) -> Mapping[str, Callable[..., dict[str, object]]]:
    observed_adk_invocation_id: str | None = None
    authorizer = ToolAuthorizer(
        ledger,
        role=inputs.role,
        allowed_tool_ids=ROLE_TOOL_IDS[inputs.role],
        case_id=inputs.case_id,
        run_id=inputs.run_id,
        data_mode=inputs.data_mode,
        clock=inputs.clock,
    )

    def invoke(
        tool_id: str,
        arguments: Mapping[str, object],
        tool_context: LocalToolCallContext,
        backend: Callable[[], dict[str, object]],
    ) -> dict[str, object]:
        nonlocal observed_adk_invocation_id
        if tool_context.invocation_id == "" or tool_context.function_call_id == "":
            raise RuntimeError("tool_call_context_missing")
        if observed_adk_invocation_id is None:
            observed_adk_invocation_id = tool_context.invocation_id
        elif observed_adk_invocation_id != tool_context.invocation_id:
            raise RuntimeError("adk_invocation_identity_mismatch")
        request_id = tool_request_id(
            run_id=inputs.run_id,
            role=inputs.role,
            attempt=inputs.attempt,
            role_execution_invocation_id=inputs.role_execution_invocation_id,
            adk_invocation_id=tool_context.invocation_id,
            function_call_id=tool_context.function_call_id,
            tool_id=tool_id,
        )
        request_hash = sha256(
            canonical_json_bytes({"tool_id": tool_id, "arguments": arguments})
        ).hexdigest()
        reservation = invocation_store.reserve(
            request_id, request_hash, now=inputs.clock()
        )
        if reservation.state == "PENDING":
            raise RuntimeError("tool_invocation_pending")
        if reservation.state == "COMPLETE":
            assert reservation.response is not None
            result = reservation.response.body.get("result")
            receipt_id = reservation.response.body.get(
                "authorization_receipt_id"
            )
            if not isinstance(result, dict):
                raise RuntimeError("tool_invocation_result_invalid")
            if not isinstance(receipt_id, str):
                raise RuntimeError("tool_authorization_receipt_missing")
            _record_tool_call(
                inputs, tool_id, tool_context, receipt_id
            )
            return result
        authorized = authorizer.invoke_idempotent(
            request_id,
            tool_id,
            json.dumps(arguments, sort_keys=True, separators=(",", ":")),
            (),
            backend,
        )
        if authorized.value is None:
            raise RuntimeError("tool_authorization_denied")
        response = GatewayResponse(
            200,
            {
                "request_id": request_id,
                "decision": authorized.receipt.payload.decision.value,
                "authorization_receipt_id": authorized.receipt.artifact_id,
                "result": dict(authorized.value),
            },
        )
        invocation_store.complete(request_id, request_hash, response)
        _record_tool_call(
            inputs, tool_id, tool_context, authorized.receipt.artifact_id
        )
        return dict(authorized.value)

    if inputs.role is AgentRole.EVIDENCE_WATCHER:

        def evidence_connector(
            stage: str, tool_context: LocalToolCallContext
        ) -> dict[str, object]:
            """Read the hash-locked prepared evidence for this run."""

            if stage != "prepared":
                raise ValueError("prepared_stage_required")
            return invoke(
                "evidence_connector",
                {"stage": stage},
                tool_context,
                lambda: {"records": [dict(item) for item in inputs.evidence_records]},
            )

        return {"evidence_connector": evidence_connector}

    def ledger_read(
        artifact_id: str, tool_context: LocalToolCallContext
    ) -> dict[str, object]:
        """Read one validated run-scoped ledger artifact."""

        def backend() -> dict[str, object]:
            value = ledger.get_artifact(artifact_id)
            if value is None or value.get("run_id") != inputs.run_id:
                raise ValueError("ledger_artifact_unavailable")
            allowed = {
                AgentRole.EVIDENCE_ASSESSOR: {
                    "CandidateDeltaReceipt",
                    "EvidenceSnapshot",
                },
                AgentRole.CITATION_AUDITOR: {
                    "AssessmentReceipt",
                    "EvidenceDelta",
                },
            }[inputs.role]
            if value.get("schema_name") not in allowed:
                raise ValueError("ledger_artifact_scope_denied")
            return dict(value)

        return invoke(
            "ledger_read",
            {"artifact_id": artifact_id},
            tool_context,
            backend,
        )

    if inputs.role is AgentRole.EVIDENCE_ASSESSOR:
        return {"ledger_read": ledger_read}

    def refetch_metadata(
        claim_id: str, tool_context: LocalToolCallContext
    ) -> dict[str, object]:
        """Refetch public metadata; unavailable sources return no fake record."""

        def backend() -> dict[str, object]:
            raw_cited = inputs.citation_sources.get(claim_id)
            if raw_cited is None or inputs.refetch_fetcher is None:
                return {
                    "claim_id": claim_id,
                    "verdict": "UNAVAILABLE",
                    "reason_codes": ["citation_source_binding_missing"],
                    "refetched_source": None,
                }
            cited = CitedSource(
                identifier=str(raw_cited["identifier"]),
                title=str(raw_cited["title"]),
                locator=str(raw_cited["locator"]),
                content_hash=str(raw_cited["content_hash"]),
                mode=DataMode(str(raw_cited["data_mode"])),
            )
            return RefetchAdapter().refetch(
                cited, inputs.refetch_fetcher
            ).to_claim_verdict(claim_id)

        return invoke(
            "refetch_metadata",
            {"claim_id": claim_id},
            tool_context,
            backend,
        )

    return {"ledger_read": ledger_read, "refetch_metadata": refetch_metadata}


def _record_tool_call(
    inputs: LocalToolInputs,
    tool_id: str,
    context: LocalToolCallContext,
    receipt_id: str,
) -> None:
    if inputs.tool_record_sink is None:
        return
    inputs.tool_record_sink(
        {
            "tool_id": tool_id,
            "call_id": context.function_call_id,
            "response_id": context.function_call_id,
            "adk_invocation_id": context.invocation_id,
            "request_id": request_id_from_call(
                inputs,
                tool_id=tool_id,
                call_id=context.function_call_id,
                adk_invocation_id=context.invocation_id,
            ),
            "authorization_receipt_id": receipt_id,
        }
    )


def request_id_from_call(
    inputs: LocalToolInputs,
    *,
    tool_id: str,
    call_id: str,
    adk_invocation_id: str,
) -> str:
    return tool_request_id(
        run_id=inputs.run_id,
        role=inputs.role,
        attempt=inputs.attempt,
        role_execution_invocation_id=inputs.role_execution_invocation_id,
        adk_invocation_id=adk_invocation_id,
        function_call_id=call_id,
        tool_id=tool_id,
    )
