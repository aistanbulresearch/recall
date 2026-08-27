from __future__ import annotations

from collections.abc import Sequence

from recall.contracts import Artifact, ContractError
from recall.contracts.enums import (
    AgentExecutionStatus,
    AgentRole,
    ScanRunEventCode,
    ToolDecision,
)
from recall.contracts.tool_causality import tool_request_id


def validate_agent_step_artifacts(
    run_id: str,
    event_code: ScanRunEventCode,
    artifacts: Sequence[Artifact],
) -> None:
    if not artifacts or any(artifact.run_id != run_id for artifact in artifacts):
        raise ContractError("contract_value_invalid", "agent_step.run_id")
    schema_names = [artifact.schema_name for artifact in artifacts]
    if event_code is ScanRunEventCode.FULL_AUDIT_REQUIRED:
        if (
            schema_names.count("EvidenceObservation") < 1
            or schema_names.count("EvidenceSnapshot") != 1
            or schema_names.count("CandidateDeltaReceipt") != 1
            or schema_names.count("AgentExecutionReceipt") != 1
            or len(schema_names) != schema_names.count("EvidenceObservation") + 3
        ):
            raise ContractError("contract_value_invalid", "watcher_artifact_set")
        terminal = next(
            artifact
            for artifact in artifacts
            if artifact.schema_name == "AgentExecutionReceipt"
        )
        if (
            terminal.payload.execution_status is not AgentExecutionStatus.COMPLETED
            or terminal.payload.agent_role is not AgentRole.EVIDENCE_WATCHER
        ):
            raise ContractError("contract_value_invalid", "watcher_execution_receipt")
        return
    if event_code is ScanRunEventCode.ASSESSMENT_COMPLETED:
        _require_exact_agent_set(
            schema_names,
            {"EvidenceDelta", "AssessmentReceipt", "AgentExecutionReceipt"},
            "assessor_artifact_set",
        )
        _require_terminal_role(
            artifacts, AgentRole.EVIDENCE_ASSESSOR, "assessor_execution_receipt"
        )
        return
    if event_code is ScanRunEventCode.AUDIT_COMPLETED:
        _require_exact_agent_set(
            schema_names,
            {"CitationAuditReceipt", "AgentExecutionReceipt"},
            "auditor_artifact_set",
        )
        _require_terminal_role(
            artifacts, AgentRole.CITATION_AUDITOR, "auditor_execution_receipt"
        )
        return
    raise ContractError("contract_transition_invalid", event_code.value)


def validate_started_receipt_binding(
    terminal: Artifact, started: Artifact
) -> None:
    if (
        terminal.schema_name != "AgentExecutionReceipt"
        or started.schema_name != "AgentExecutionReceipt"
        or terminal.run_id != started.run_id
        or terminal.payload.started_receipt_id != started.artifact_id
        or terminal.payload.agent_role is not started.payload.agent_role
        or terminal.payload.attempt != started.payload.attempt
        or started.payload.execution_status is not AgentExecutionStatus.STARTED
        or terminal.payload.execution_status is AgentExecutionStatus.STARTED
    ):
        raise ContractError("ledger_integrity_failed", "started_receipt_binding")


def validate_tool_authorization_bindings(
    terminal: Artifact,
    authorization_receipts: Sequence[Artifact],
) -> None:
    records = terminal.payload.tool_records
    receipt_by_id = {item.artifact_id: item for item in authorization_receipts}
    authorization_ids = tuple(
        record["authorization_receipt_id"] for record in records
    )
    if (
        len(receipt_by_id) != len(authorization_ids)
        or len(set(authorization_ids)) != len(authorization_ids)
        or set(terminal.input_artifact_ids)
        != {terminal.payload.started_receipt_id, *authorization_ids}
    ):
        raise ContractError(
            "ledger_integrity_failed", "tool_authorization_binding"
        )
    for record in records:
        receipt = receipt_by_id.get(record["authorization_receipt_id"])
        expected_request_id = tool_request_id(
            run_id=str(terminal.run_id),
            role=terminal.payload.agent_role,
            attempt=terminal.payload.attempt,
            role_execution_invocation_id=terminal.payload.invocation_id,
            adk_invocation_id=record["adk_invocation_id"],
            function_call_id=record["call_id"],
            tool_id=record["tool_id"],
        )
        if (
            receipt is None
            or receipt.schema_name != "ToolAuthorizationReceipt"
            or receipt.run_id != terminal.run_id
            or receipt.payload.agent_role is not terminal.payload.agent_role
            or receipt.payload.tool_id != record["tool_id"]
            or receipt.payload.decision is not ToolDecision.ALLOWED
            or record["request_id"] != expected_request_id
            or receipt.payload.invocation_id != expected_request_id
            or record["call_id"] != record["response_id"]
        ):
            raise ContractError(
                "ledger_integrity_failed", "tool_authorization_binding"
            )


def _require_exact_agent_set(
    observed: list[str], expected: set[str], field: str
) -> None:
    if len(observed) != len(expected) or set(observed) != expected:
        raise ContractError("contract_value_invalid", field)


def _require_terminal_role(
    artifacts: Sequence[Artifact], role: AgentRole, field: str
) -> None:
    terminal = next(
        artifact
        for artifact in artifacts
        if artifact.schema_name == "AgentExecutionReceipt"
    )
    if (
        terminal.payload.execution_status is not AgentExecutionStatus.COMPLETED
        or terminal.payload.agent_role is not role
    ):
        raise ContractError("contract_value_invalid", field)
