from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from recall.contracts.enums import FactState, PolicyOutcome, PresenceState
from recall.contracts.errors import ContractError
from recall.contracts.payloads.policy import (
    PolicyDecisionPayload,
    PolicyFact,
    parse_policy_input_facts,
)


POLICY_VERSION = "1.0.1"

BASE_REASON_CODES = {
    "privacy_accepted": {
        FactState.FAIL: "privacy_not_accepted",
        FactState.NOT_EVALUATED: "privacy_not_evaluated",
    },
    "registry_resolution_valid": {
        FactState.FAIL: "registry_resolution_invalid",
        FactState.NOT_EVALUATED: "registry_resolution_not_evaluated",
    },
    "route_valid": {
        FactState.FAIL: "route_invalid",
        FactState.NOT_EVALUATED: "route_not_evaluated",
    },
    "tool_authorization_complete": {
        FactState.FAIL: "tool_authorization_incomplete",
        FactState.NOT_EVALUATED: "tool_authorization_not_evaluated",
    },
    "source_retrieval_complete": {
        FactState.FAIL: "source_retrieval_incomplete",
        FactState.NOT_EVALUATED: "source_retrieval_not_evaluated",
    },
    "source_schema_valid": {
        FactState.FAIL: "source_schema_invalid",
        FactState.NOT_EVALUATED: "source_schema_not_evaluated",
    },
    "data_mode_valid": {
        FactState.FAIL: "data_mode_invalid",
        FactState.NOT_EVALUATED: "data_mode_not_evaluated",
    },
    "snapshot_integrity_valid": {
        FactState.FAIL: "snapshot_integrity_invalid",
        FactState.NOT_EVALUATED: "snapshot_integrity_not_evaluated",
    },
}

PRESENT_REASON_CODES = {
    "assessment_valid": {
        FactState.FAIL: "assessment_invalid",
        FactState.NOT_EVALUATED: "assessment_not_evaluated",
    },
    "citation_audit_complete": {
        FactState.FAIL: "citation_audit_incomplete",
        FactState.NOT_EVALUATED: "citation_audit_not_evaluated",
    },
    "all_material_claims_verified": {
        FactState.FAIL: "material_claim_unverified",
        FactState.NOT_EVALUATED: "material_claims_not_evaluated",
    },
    "counter_evidence_complete": {
        FactState.FAIL: "counter_evidence_incomplete",
        FactState.NOT_EVALUATED: "counter_evidence_not_evaluated",
    },
}


def _append_fact_reason(
    facts: Mapping[str, PolicyFact],
    field: str,
    projection: Mapping[FactState, str],
    reasons: list[str],
    missing: set[str],
) -> None:
    state = facts[field]
    if isinstance(state, FactState) and state in projection:
        reasons.append(projection[state])
        missing.add(field)


def evaluate(
    input_facts: Mapping[str, Any],
    policy_version: str,
    *,
    existing_task_id: str | None = None,
) -> PolicyDecisionPayload:
    if policy_version != POLICY_VERSION:
        raise ContractError("contract_policy_version_unsupported", policy_version)
    facts = parse_policy_input_facts(input_facts)
    reasons: list[str] = []
    missing: set[str] = set()

    for field, projection in BASE_REASON_CODES.items():
        _append_fact_reason(facts, field, projection, reasons, missing)

    candidate = facts["candidate_delta_state"]
    if candidate is PresenceState.UNKNOWN:
        reasons.append("candidate_delta_not_evaluated")
        missing.add("candidate_delta_state")

    conflict = facts["unresolved_conflict_state"]
    if conflict is PresenceState.PRESENT:
        reasons.append("unresolved_evidence_conflict")
        missing.add("unresolved_conflict_state")
    elif conflict is PresenceState.UNKNOWN:
        reasons.append("unresolved_conflict_not_evaluated")
        missing.add("unresolved_conflict_state")

    budget = facts["budget_or_loop_failure_state"]
    if budget is PresenceState.PRESENT:
        reasons.append("execution_budget_failed")
        missing.add("budget_or_loop_failure_state")
    elif budget is PresenceState.UNKNOWN:
        reasons.append("execution_budget_not_evaluated")
        missing.add("budget_or_loop_failure_state")

    if candidate is PresenceState.PRESENT:
        for field, projection in PRESENT_REASON_CODES.items():
            _append_fact_reason(facts, field, projection, reasons, missing)

    if candidate is PresenceState.PRESENT and not reasons:
        existing = facts["existing_open_task_state"]
        if existing is PresenceState.UNKNOWN:
            reasons.append("existing_open_task_not_evaluated")
            missing.add("existing_open_task_state")

    ordered_reasons = tuple(sorted(set(reasons)))
    if ordered_reasons:
        outcome = PolicyOutcome.ABSTAIN
    elif candidate is PresenceState.ABSENT:
        outcome = PolicyOutcome.NO_ACTION
        ordered_reasons = ("no_candidate_delta",)
    elif facts["existing_open_task_state"] is PresenceState.PRESENT:
        outcome = PolicyOutcome.NO_ACTION
        ordered_reasons = ("duplicate_suppressed",)
    else:
        outcome = PolicyOutcome.REVIEW_REQUIRED
        ordered_reasons = ("audited_candidate_delta",)

    return PolicyDecisionPayload(
        policy_version=policy_version,
        input_facts=facts,
        outcome=outcome,
        reason_codes=ordered_reasons,
        missing_prerequisites=tuple(sorted(missing)),
        review_trigger=outcome is PolicyOutcome.REVIEW_REQUIRED,
        existing_task_id=existing_task_id,
    )
