from __future__ import annotations

from collections.abc import Mapping

import pytest

from recall.contracts import (
    ArtifactStatus,
    ContractError,
    DataMode,
    FailureTerminal,
    build_artifact,
)
from recall.contracts.enums import FactState, PresenceState
from recall.contracts.failure_registry import (
    FAILURE_REGISTRY,
    MEMORY_AUTHORITY_CONFLICT_PROJECTION,
    FailureCode,
)


PRODUCER_POLICY = {
    "FailureReceipt": frozenset({"controller-failure-recorder"})
}
HALTED_CODES = {
    FailureCode.POLICY_UNAVAILABLE,
    FailureCode.LEDGER_INTEGRITY_FAILED,
    FailureCode.CONTROLLER_FAILED,
}


def _valid_details(code: FailureCode) -> dict[str, object]:
    if code is FailureCode.LOOP_DETECTED:
        return {"hop_count": 2, "repeated_state_hash": "a" * 64}
    if code is FailureCode.SOURCE_UNAVAILABLE:
        return {"source": "captured-replay", "attempts": 3}
    return {}


def _build_failure(
    code: FailureCode,
    *,
    details: Mapping[str, object] | None = None,
    safe_terminal: FailureTerminal | None = None,
    retryable: bool | None = None,
) -> dict[str, object]:
    terminal = safe_terminal or (
        FailureTerminal.HALTED
        if code in HALTED_CODES
        else FailureTerminal.POLICY_BOUND
    )
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
        created_at="2026-08-21T20:45:00Z",
        input_artifact_ids=(),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.REJECTED,
        payload={
            "failure_code": code.value,
            "stage": "POLICY_EVALUATION",
            "retryable": (
                terminal is FailureTerminal.RETRY
                if retryable is None
                else retryable
            ),
            "attempt": 1,
            "budget_state": "WITHIN_LIMIT",
            "details": dict(_valid_details(code) if details is None else details),
            "related_artifact_ids": [],
            "safe_terminal": terminal.value,
            "operator_action": "inspect_receipt",
        },
        authorized_producers=PRODUCER_POLICY,
    )


def test_safe_terminal_is_three_valued_and_halted_is_code_bound() -> None:
    assert {member.value for member in FailureTerminal} == {
        "POLICY_BOUND",
        "RETRY",
        "HALTED",
    }

    with pytest.raises(ContractError, match="contract_value_invalid:safe_terminal"):
        _build_failure(
            FailureCode.SOURCE_UNAVAILABLE,
            safe_terminal=FailureTerminal.HALTED,
        )


@pytest.mark.parametrize(
    ("code", "terminal", "retryable"),
    [
        (FailureCode.SOURCE_UNAVAILABLE, FailureTerminal.RETRY, False),
        (FailureCode.ROUTE_INVALID, FailureTerminal.POLICY_BOUND, True),
        (FailureCode.POLICY_UNAVAILABLE, FailureTerminal.HALTED, True),
    ],
)
def test_retryable_is_exactly_bound_to_retry_terminal(
    code: FailureCode,
    terminal: FailureTerminal,
    retryable: bool,
) -> None:
    with pytest.raises(ContractError, match="contract_value_invalid:retryable"):
        _build_failure(code, safe_terminal=terminal, retryable=retryable)

    _build_failure(
        FailureCode.SOURCE_UNAVAILABLE,
        safe_terminal=FailureTerminal.RETRY,
        retryable=True,
    )

    with pytest.raises(ContractError, match="contract_value_invalid:safe_terminal"):
        _build_failure(
            FailureCode.POLICY_UNAVAILABLE,
            safe_terminal=FailureTerminal.POLICY_BOUND,
        )


@pytest.mark.parametrize("code", list(FailureCode))
def test_each_failure_code_accepts_only_its_closed_details_schema(
    code: FailureCode,
) -> None:
    artifact = _build_failure(code)
    assert artifact["failure_code"] == code.value

    invalid = _valid_details(code)
    invalid["unexpected"] = True
    with pytest.raises(ContractError, match="contract_unknown_field:details"):
        _build_failure(code, details=invalid)


def test_failure_registry_has_exact_28_code_projection_snapshot() -> None:
    expected = {
        "privacy_not_accepted": ("privacy_accepted", "FAIL", ("privacy_not_accepted",)),
        "contract_unknown_field": ("assessment_valid", "FAIL", ("assessment_invalid",)),
        "contract_required_field_missing": ("assessment_valid", "FAIL", ("assessment_invalid",)),
        "artifact_integrity_failed": ("snapshot_integrity_valid", "FAIL", ("snapshot_integrity_invalid",)),
        "producer_not_authorized": ("tool_authorization_complete", "FAIL", ("tool_authorization_incomplete",)),
        "data_mode_conflict": ("data_mode_valid", "FAIL", ("data_mode_invalid",)),
        "registry_unavailable": ("registry_resolution_valid", "NOT_EVALUATED", ("registry_resolution_not_evaluated",)),
        "registry_revision_rejected": ("registry_resolution_valid", "FAIL", ("registry_resolution_invalid",)),
        "route_invalid": ("route_valid", "FAIL", ("route_invalid",)),
        "tool_denied": ("tool_authorization_complete", "FAIL", ("tool_authorization_incomplete",)),
        "source_unavailable": ("source_retrieval_complete", "NOT_EVALUATED", ("source_retrieval_not_evaluated",)),
        "source_schema_drift": ("source_schema_valid", "FAIL", ("source_schema_invalid",)),
        "candidate_delta_unknown": ("candidate_delta_state", "UNKNOWN", ("candidate_delta_not_evaluated",)),
        "agent_schema_invalid": ("assessment_valid", "FAIL", ("assessment_invalid",)),
        "agent_timeout": None,
        "citation_mismatch": ("all_material_claims_verified", "FAIL", ("material_claim_unverified",)),
        "counter_evidence_incomplete": ("counter_evidence_complete", "FAIL", ("counter_evidence_incomplete",)),
        "audit_incomplete": ("citation_audit_complete", "FAIL", ("citation_audit_incomplete",)),
        "memory_rejected": None,
        "duplicate_suppressed": None,
        "lease_expired": None,
        "stale_write_rejected": None,
        "loop_detected": ("budget_or_loop_failure_state", "PRESENT", ("execution_budget_failed",)),
        "budget_exhausted": ("budget_or_loop_failure_state", "PRESENT", ("execution_budget_failed",)),
        "policy_unavailable": None,
        "ledger_integrity_failed": None,
        "controller_failed": None,
        "contract_transition_invalid": None,
    }
    actual = {
        code.value: None
        if projection is None
        else (
            projection.fact_name,
            projection.fact_state.value,
            projection.reason_codes,
        )
        for code, projection in FAILURE_REGISTRY.items()
    }

    assert len(FailureCode) == 28
    assert len(FAILURE_REGISTRY) == 28
    assert actual == expected
    assert MEMORY_AUTHORITY_CONFLICT_PROJECTION.fact_name == "assessment_valid"
    assert MEMORY_AUTHORITY_CONFLICT_PROJECTION.fact_state is FactState.FAIL
    assert PresenceState.PRESENT.value == "PRESENT"
