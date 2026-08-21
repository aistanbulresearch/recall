from __future__ import annotations

from copy import deepcopy

import pytest

from recall.contracts import ContractError
from recall.policy import evaluate


BASE_FACTS = {
    "privacy_accepted": "PASS",
    "registry_resolution_valid": "PASS",
    "route_valid": "PASS",
    "tool_authorization_complete": "PASS",
    "source_retrieval_complete": "PASS",
    "source_schema_valid": "PASS",
    "data_mode_valid": "PASS",
    "snapshot_integrity_valid": "PASS",
}


def facts(
    *,
    candidate: str,
    assessment: str = "NOT_EVALUATED",
    audit: str = "NOT_EVALUATED",
    claims: str = "NOT_EVALUATED",
    counter: str = "NOT_EVALUATED",
    conflict: str = "ABSENT",
    budget: str = "ABSENT",
    open_task: str = "UNKNOWN",
) -> dict[str, str]:
    return {
        **BASE_FACTS,
        "candidate_delta_state": candidate,
        "assessment_valid": assessment,
        "citation_audit_complete": audit,
        "all_material_claims_verified": claims,
        "counter_evidence_complete": counter,
        "unresolved_conflict_state": conflict,
        "budget_or_loop_failure_state": budget,
        "existing_open_task_state": open_task,
    }


ROWS = (
    (facts(candidate="ABSENT"), "NO_ACTION", ("no_candidate_delta",)),
    (
        facts(
            candidate="PRESENT",
            assessment="PASS",
            audit="PASS",
            claims="PASS",
            counter="PASS",
            open_task="ABSENT",
        ),
        "REVIEW_REQUIRED",
        ("audited_candidate_delta",),
    ),
    (
        facts(
            candidate="PRESENT",
            assessment="PASS",
            audit="PASS",
            claims="PASS",
            counter="PASS",
            open_task="PRESENT",
        ),
        "NO_ACTION",
        ("duplicate_suppressed",),
    ),
    (
        {
            **facts(candidate="UNKNOWN", conflict="UNKNOWN"),
            "privacy_accepted": "FAIL",
            "route_valid": "NOT_EVALUATED",
        },
        "ABSTAIN",
        (
            "candidate_delta_not_evaluated",
            "privacy_not_accepted",
            "route_not_evaluated",
            "unresolved_conflict_not_evaluated",
        ),
    ),
    (
        facts(
            candidate="PRESENT",
            assessment="FAIL",
            open_task="UNKNOWN",
        ),
        "ABSTAIN",
        (
            "assessment_invalid",
            "citation_audit_not_evaluated",
            "counter_evidence_not_evaluated",
            "material_claims_not_evaluated",
        ),
    ),
    (
        facts(
            candidate="PRESENT",
            assessment="PASS",
            audit="FAIL",
            claims="FAIL",
            counter="PASS",
        ),
        "ABSTAIN",
        ("citation_audit_incomplete", "material_claim_unverified"),
    ),
    (
        facts(
            candidate="PRESENT",
            assessment="PASS",
            audit="PASS",
            claims="FAIL",
            counter="PASS",
        ),
        "ABSTAIN",
        ("material_claim_unverified",),
    ),
    (
        facts(
            candidate="PRESENT",
            assessment="PASS",
            audit="PASS",
            claims="PASS",
            counter="FAIL",
        ),
        "ABSTAIN",
        ("counter_evidence_incomplete",),
    ),
    (
        facts(
            candidate="PRESENT",
            assessment="PASS",
            audit="PASS",
            claims="PASS",
            counter="PASS",
            conflict="PRESENT",
        ),
        "ABSTAIN",
        ("unresolved_evidence_conflict",),
    ),
    (
        facts(candidate="UNKNOWN", budget="PRESENT"),
        "ABSTAIN",
        ("candidate_delta_not_evaluated", "execution_budget_failed"),
    ),
    (
        facts(
            candidate="PRESENT",
            assessment="PASS",
            audit="PASS",
            claims="PASS",
            counter="PASS",
            open_task="UNKNOWN",
        ),
        "ABSTAIN",
        ("existing_open_task_not_evaluated",),
    ),
)


@pytest.mark.parametrize(("input_facts", "outcome", "reasons"), ROWS)
def test_normative_truth_table(
    input_facts: dict[str, str], outcome: str, reasons: tuple[str, ...]
) -> None:
    result = evaluate(input_facts, "1.0.1")

    assert result.outcome.value == outcome
    assert result.reason_codes == reasons
    assert result.reason_codes == tuple(sorted(result.reason_codes))


@pytest.mark.parametrize(("input_facts", "_outcome", "_reasons"), ROWS)
def test_policy_output_is_byte_equivalent_for_same_input(
    input_facts: dict[str, str], _outcome: str, _reasons: tuple[str, ...]
) -> None:
    assert evaluate(input_facts, "1.0.1").to_wire() == evaluate(
        deepcopy(input_facts), "1.0.1"
    ).to_wire()


def test_policy_rejects_unknown_missing_and_invalid_fact_values() -> None:
    valid = facts(candidate="ABSENT")
    unknown = {**valid, "memory_valid": "PASS"}
    missing = dict(valid)
    missing.pop("privacy_accepted")
    invalid = {**valid, "privacy_accepted": "TRUE"}

    for value in (unknown, missing, invalid):
        with pytest.raises(ContractError):
            evaluate(value, "1.0.1")


def test_no_candidate_ignores_non_applicable_downstream_not_evaluated() -> None:
    result = evaluate(facts(candidate="ABSENT"), "1.0.1")

    assert result.outcome.value == "NO_ACTION"
    assert result.missing_prerequisites == ()
