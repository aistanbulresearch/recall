from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy

import pytest

from recall.contracts import (
    ArtifactStatus,
    ContractError,
    DataMode,
    ToolDecision,
    build_artifact,
    parse_artifact,
)
from recall.contracts.canonical import content_hash


PRODUCER_POLICY = {
    "ToolAuthorizationReceipt": frozenset({"controller-authorizer"}),
    "DataModeReceipt": frozenset({"controller-mode-gate"}),
    "FailureReceipt": frozenset({"controller-failure-recorder"}),
}


def valid_tool_receipt() -> dict[str, object]:
    return build_artifact(
        schema_name="ToolAuthorizationReceipt",
        schema_version="1.0.0",
        artifact_id="1d769ca8-b6bd-4920-b772-315bb57344bf",
        case_id="ceb8cc5d-d637-4e43-a35b-101e4d79f8ac",
        run_id="679e98e2-7cb3-45d5-870b-4bbd9a9c1295",
        producer={
            "component": "tool-authorizer",
            "version": "0.1.0",
            "identity": "controller-authorizer",
        },
        created_at="2026-08-21T19:30:00Z",
        input_artifact_ids=(),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.REJECTED,
        payload={
            "agent_role": "EVIDENCE_ASSESSOR",
            "tool_id": "review-task-writer",
            "requested_action": "create_review_task",
            "decision": ToolDecision.DENIED.value,
            "policy_version": "1.0.1",
            "reason_codes": ["tool_not_allowlisted"],
            "invocation_id": "9f74dc50-6e27-4aab-878e-fb7f9d8fca76",
        },
        authorized_producers=PRODUCER_POLICY,
    )


def valid_mode_receipt() -> dict[str, object]:
    return build_artifact(
        schema_name="DataModeReceipt",
        schema_version="2.0.0",
        artifact_id="9ef71d1a-7fa8-4dfd-be1e-ad7a2098271d",
        case_id="ceb8cc5d-d637-4e43-a35b-101e4d79f8ac",
        run_id=None,
        producer={
            "component": "mode-gate",
            "version": "0.1.0",
            "identity": "controller-mode-gate",
        },
        created_at="2026-08-21T19:30:00Z",
        input_artifact_ids=("1d769ca8-b6bd-4920-b772-315bb57344bf",),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID,
        payload={
            "subject_artifact_ids": ["1d769ca8-b6bd-4920-b772-315bb57344bf"],
            "mode_set": ["CAPTURED_REPLAY", "SYNTHETIC"],
            "declared_composition": "SYNTHETIC_WITH_CAPTURED_REPLAY",
            "propagation_status": "PASS",
            "reason_codes": [],
        },
        authorized_producers=PRODUCER_POLICY,
    )


def valid_failure_receipt() -> dict[str, object]:
    return build_artifact(
        schema_name="FailureReceipt",
        schema_version="1.0.0",
        artifact_id="9a9ad89b-f933-4728-adb2-a2bf874bb41e",
        case_id="ceb8cc5d-d637-4e43-a35b-101e4d79f8ac",
        run_id="679e98e2-7cb3-45d5-870b-4bbd9a9c1295",
        producer={
            "component": "failure-recorder",
            "version": "0.1.0",
            "identity": "controller-failure-recorder",
        },
        created_at="2026-08-21T19:30:00Z",
        input_artifact_ids=(),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.REJECTED,
        payload={
            "failure_code": "route_invalid",
            "stage": "ROUTING",
            "retryable": False,
            "attempt": 1,
            "budget_state": "WITHIN_LIMIT",
            "details": {},
            "related_artifact_ids": [],
            "safe_terminal": "POLICY_BOUND",
            "operator_action": "inspect_route",
        },
        authorized_producers=PRODUCER_POLICY,
    )


def test_tool_receipt_round_trips_and_verifies_hash() -> None:
    wire = valid_tool_receipt()
    artifact = parse_artifact(wire, authorized_producers=PRODUCER_POLICY)

    assert artifact.schema_name == "ToolAuthorizationReceipt"
    assert artifact.payload.decision is ToolDecision.DENIED
    assert artifact.to_wire() == wire


def test_tool_receipt_requires_authorized_producer_when_policy_is_supplied() -> None:
    wire = valid_tool_receipt()

    assert parse_artifact(
        wire, authorized_producers=PRODUCER_POLICY
    ).producer.identity == (
        "controller-authorizer"
    )

    with pytest.raises(ContractError, match="producer_not_authorized"):
        parse_artifact(
            wire,
            authorized_producers={
                "ToolAuthorizationReceipt": frozenset({"different-authorizer"})
            },
        )


def test_parse_artifact_cannot_be_called_without_producer_policy() -> None:
    wire = valid_tool_receipt()

    with pytest.raises(TypeError, match="authorized_producers"):
        parse_artifact(wire)  # type: ignore[call-arg]



@pytest.mark.parametrize(
    "factory", [valid_tool_receipt, valid_mode_receipt, valid_failure_receipt]
)
def test_empty_producer_registry_rejects_every_registered_artifact(
    factory: Callable[[], dict[str, object]],
) -> None:
    wire = factory()

    with pytest.raises(ContractError, match="producer_not_authorized"):
        parse_artifact(wire, authorized_producers={})


@pytest.mark.parametrize(
    ("mutator", "expected_code"),
    [
        (lambda value: value.__setitem__("surprise", True), "contract_unknown_field"),
        (
            lambda value: value["producer"].__setitem__("email", "forbidden"),
            "contract_unknown_field",
        ),
        (
            lambda value: value.__setitem__("payload_unknown", 1),
            "contract_unknown_field",
        ),
        (lambda value: value.pop("run_id"), "contract_required_field_missing"),
        (lambda value: value.__setitem__("content_hash", "0" * 64), "artifact_integrity_failed"),
    ],
)
def test_contract_rejects_unknown_missing_or_tampered_data(
    mutator: object, expected_code: str
) -> None:
    wire = deepcopy(valid_tool_receipt())
    mutator(wire)  # type: ignore[operator]

    with pytest.raises(ContractError, match=expected_code):
        parse_artifact(wire, authorized_producers=PRODUCER_POLICY)


def test_data_mode_accepts_only_registered_composition() -> None:
    wire = valid_mode_receipt()

    artifact = parse_artifact(wire, authorized_producers=PRODUCER_POLICY)
    assert artifact.run_id is None
    assert artifact.payload.mode_set == (
        DataMode.CAPTURED_REPLAY,
        DataMode.SYNTHETIC,
    )

    invalid = deepcopy(wire)
    invalid["mode_set"] = ["MOCK", "SYNTHETIC"]
    invalid["content_hash"] = "0" * 64
    with pytest.raises(ContractError, match="data_mode_conflict"):
        parse_artifact(
            invalid,
            authorized_producers=PRODUCER_POLICY,
            verify_hash=False,
        )


@pytest.mark.parametrize("factory", [valid_tool_receipt, valid_failure_receipt])
def test_run_scoped_receipts_reject_null_run_id(
    factory: Callable[[], dict[str, object]],
) -> None:
    wire = factory()
    wire["run_id"] = None
    wire["content_hash"] = content_hash(wire)

    with pytest.raises(ContractError, match="contract_required_value_missing:run_id"):
        parse_artifact(wire, authorized_producers=PRODUCER_POLICY)
