from __future__ import annotations

from copy import deepcopy

import pytest

from recall.contracts import ArtifactStatus, ContractError, DataMode, build_artifact
from recall.ledger.producers import PRODUCER_REGISTRY


CASE_ID = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
RUN_ID = "b1d74cb8-25ac-4a84-ab9d-5a71a366c2da"
ARTIFACT_ID = "f7617fa1-2f75-47f3-b88d-ec72e88e3051"
STARTED_ID = "09de3050-40e1-41cc-9bd7-663469e94da1"
AUTHORIZATION_ID = "6af1fa45-7ef0-4bfa-a1cf-67020ea4cfbd"
CREATED_AT = "2026-08-27T08:00:00Z"


def _build(
    schema_name: str,
    schema_version: str,
    payload: dict[str, object],
    *,
    artifact_id: str = ARTIFACT_ID,
    run_id: str | None = RUN_ID,
    identity: str,
    input_artifact_ids: tuple[str, ...] = (),
) -> dict[str, object]:
    return build_artifact(
        schema_name=schema_name,
        schema_version=schema_version,
        artifact_id=artifact_id,
        case_id=CASE_ID,
        run_id=run_id,
        producer={
            "component": identity,
            "version": "0.1.0",
            "identity": identity,
        },
        created_at=CREATED_AT,
        input_artifact_ids=input_artifact_ids,
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID,
        payload=payload,
        authorized_producers=PRODUCER_REGISTRY,
    )


def _scan_run_payload(*, full_audit: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "watch_case_id": CASE_ID,
        "state": "CREATED",
        "scheduled_for": CREATED_AT,
        "attempt": 0,
        "lease_epoch": 0,
        "deadline_at": "2026-08-27T08:30:00Z",
        "budget_snapshot": {
            "delegation_depth": 0,
            "specialist_invocations": 0,
            "model_calls_per_role": 1,
            "schema_repairs": 0,
            "agent_retries": 1,
            "connector_retries": 0,
            "repeated_state_limit": 2,
            "wall_time_seconds": 600,
            "step_deadlines": {"watcher": 120},
            "token_ceilings": {"watcher": 2048},
        },
        "idempotency_key": "a" * 64,
        "trace_id": "e190f6ac-b726-42ae-ac2b-e4b80638e91c",
        "terminal_policy_decision_id": None,
        "failure_receipt_ids": [],
    }
    if full_audit:
        payload["execution_profile"] = "FULL_AUDIT_V1"
    return payload


def _privacy_payload(*, include_locus: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "decision": "ACCEPTED",
        "detector_versions": {
            "deterministic": "1.0.0",
            "gemma": "gemma4:e4b-it-qat",
        },
        "identifier_classes_checked": ["PERSON_NAME"],
        "detectors": {
            "deterministic": {"version": "1.0.0", "approved_spans": []},
            "gemma": {
                "version": "gemma4:e4b-it-qat",
                "invoked": True,
                "schema_valid": True,
                "approved_residual_spans": [],
            },
        },
        "outbound": {
            "scan_status": "CLEAR",
            "allowed_field_paths": ["$.variant.gene"],
            "raw_text_field_count": 0,
        },
        "payload_hash": "b" * 64,
        "signature_ref": {
            "key_id": "lab-key",
            "algorithm": "HMAC-SHA256",
            "signature": "c" * 64,
        },
    }
    if include_locus:
        payload.update(
            {
                "execution_locus": "LAB_LOCAL",
                "transport_class": "LOCAL_PROCESS",
                "endpoint_class": "OLLAMA_LOCAL",
                "model_id": "gemma4:e4b-it-qat",
                "model_revision": "sha256:" + "d" * 64,
            }
        )
    return payload


def _agent_receipt_payload(status: str) -> dict[str, object]:
    terminal = status != "STARTED"
    completed = status == "COMPLETED"
    return {
        "execution_profile": "FULL_AUDIT_V1",
        "agent_role": "EVIDENCE_WATCHER",
        "attempt": 1,
        "execution_status": status,
        "runtime_class": "IN_PROCESS_ADK_CLOUD_RUN",
        "model_id": "gemini-3.7-flash",
        "model_revision": "gemini-3.7-flash",
        "endpoint_class": "VERTEX_AI_GLOBAL",
        "location": "global",
        "trace_id": "e190f6ac-b726-42ae-ac2b-e4b80638e91c",
        "invocation_id": "c9a19973-602f-46b2-953e-62c4cb33f595",
        "started_at": CREATED_AT,
        "completed_at": "2026-08-27T08:00:02Z" if terminal else None,
        "latency_ms": 2000 if terminal else None,
        "turns": (
            [
                {
                    "turn_index": 1,
                    "prompt_tokens": 100,
                    "candidate_tokens": 20,
                    "thoughts_tokens": 5,
                    "total_tokens": 125,
                    "finish_reason": "STOP",
                    "function_call_emitted": True,
                    "latency_ms": 1900,
                }
            ]
            if terminal
            else []
        ),
        "http_429_count": 0,
        "tool_call_ids": (["tool-call-1"] if completed else []),
        "tool_response_ids": (["tool-call-1"] if completed else []),
        "tool_records": (
            [
                {
                    "tool_id": "evidence_connector",
                    "call_id": "tool-call-1",
                    "response_id": "tool-call-1",
                    "adk_invocation_id": "adk-invocation-1",
                    "request_id": "ea9c34f8-4c8a-4b5e-ae71-663a5d68ace9",
                    "authorization_receipt_id": AUTHORIZATION_ID,
                }
            ]
            if completed
            else []
        ),
        "started_receipt_id": STARTED_ID if terminal else None,
        "failure_code": "agent_output_invalid" if status == "FAILED" else None,
    }


def test_scan_run_11_requires_full_audit_profile_and_keeps_10_legacy() -> None:
    current = _build(
        "ScanRun",
        "1.1.0",
        _scan_run_payload(full_audit=True),
        identity="controller",
    )
    legacy = _build(
        "ScanRun",
        "1.0.0",
        _scan_run_payload(full_audit=False),
        identity="controller",
    )

    assert current["execution_profile"] == "FULL_AUDIT_V1"
    assert "execution_profile" not in legacy

    missing = _scan_run_payload(full_audit=False)
    with pytest.raises(ContractError, match="contract_required_field_missing"):
        _build("ScanRun", "1.1.0", missing, identity="controller")


def test_privacy_receipt_11_records_model_execution_locus_and_keeps_10_legacy() -> None:
    current = _build(
        "PrivacyReceipt",
        "1.1.0",
        _privacy_payload(include_locus=True),
        run_id=None,
        identity="privacy-gate",
    )
    legacy = _build(
        "PrivacyReceipt",
        "1.0.0",
        _privacy_payload(include_locus=False),
        run_id=None,
        identity="privacy-gate",
    )

    assert current["execution_locus"] == "LAB_LOCAL"
    assert current["model_revision"].startswith("sha256:")
    assert "execution_locus" not in legacy

    invalid = _privacy_payload(include_locus=True)
    invalid["execution_locus"] = "UNDECLARED_CLOUD"
    with pytest.raises(ContractError, match="contract_enum_invalid"):
        _build(
            "PrivacyReceipt",
            "1.1.0",
            invalid,
            run_id=None,
            identity="privacy-gate",
        )


@pytest.mark.parametrize("status", ["STARTED", "COMPLETED", "FAILED"])
def test_agent_execution_receipt_10_round_trips_strict_status_shapes(
    status: str,
) -> None:
    wire = _build(
        "AgentExecutionReceipt",
        "1.0.0",
        _agent_receipt_payload(status),
        identity="controller-agent-executor",
        input_artifact_ids=(
            (STARTED_ID, AUTHORIZATION_ID)
            if status == "COMPLETED"
            else ((STARTED_ID,) if status == "FAILED" else ())
        ),
    )

    assert wire["execution_status"] == status
    assert wire["runtime_class"] == "IN_PROCESS_ADK_CLOUD_RUN"
    assert wire["model_id"] == "gemini-3.7-flash"


def test_agent_execution_terminal_receipt_requires_started_receipt_dependency() -> None:
    with pytest.raises(ContractError, match="contract_value_invalid"):
        _build(
            "AgentExecutionReceipt",
            "1.0.0",
            _agent_receipt_payload("COMPLETED"),
            identity="controller-agent-executor",
            input_artifact_ids=(),
        )


def test_agent_execution_receipt_rejects_token_accounting_contradiction() -> None:
    payload = deepcopy(_agent_receipt_payload("COMPLETED"))
    payload["turns"][0]["total_tokens"] = 124
    with pytest.raises(ContractError, match="contract_value_invalid"):
        _build(
            "AgentExecutionReceipt",
            "1.0.0",
            payload,
            identity="controller-agent-executor",
            input_artifact_ids=(STARTED_ID, AUTHORIZATION_ID),
        )


def test_agent_execution_receipt_rejects_tool_ids_without_causal_records() -> None:
    payload = deepcopy(_agent_receipt_payload("COMPLETED"))
    payload["tool_records"][0]["response_id"] = "different-response"
    with pytest.raises(ContractError, match="contract_value_invalid"):
        _build(
            "AgentExecutionReceipt",
            "1.0.0",
            payload,
            identity="controller-agent-executor",
            input_artifact_ids=(STARTED_ID, AUTHORIZATION_ID),
        )
