from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ..enums import FactState, PolicyOutcome, PresenceState
from ..errors import ContractError
from ..validation import (
    SEMVER,
    enum_value,
    require_exact_fields,
    tuple_of_strings,
    uuid_value,
)


FACT_STATE_FIELDS = frozenset(
    {
        "privacy_accepted",
        "registry_resolution_valid",
        "route_valid",
        "tool_authorization_complete",
        "source_retrieval_complete",
        "source_schema_valid",
        "data_mode_valid",
        "snapshot_integrity_valid",
        "assessment_valid",
        "citation_audit_complete",
        "all_material_claims_verified",
        "counter_evidence_complete",
    }
)
PRESENCE_STATE_FIELDS = frozenset(
    {
        "candidate_delta_state",
        "unresolved_conflict_state",
        "budget_or_loop_failure_state",
        "existing_open_task_state",
    }
)
POLICY_FACT_FIELDS = FACT_STATE_FIELDS | PRESENCE_STATE_FIELDS


PolicyFact = FactState | PresenceState


def parse_policy_input_facts(value: Any) -> Mapping[str, PolicyFact]:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "input_facts")
    require_exact_fields(value, POLICY_FACT_FIELDS, "input_facts")
    parsed: dict[str, PolicyFact] = {}
    for field in FACT_STATE_FIELDS:
        parsed[field] = enum_value(FactState, value[field], f"input_facts.{field}")
    for field in PRESENCE_STATE_FIELDS:
        parsed[field] = enum_value(
            PresenceState, value[field], f"input_facts.{field}"
        )
    return MappingProxyType(parsed)


@dataclass(frozen=True, slots=True)
class PolicyDecisionPayload:
    policy_version: str
    input_facts: Mapping[str, PolicyFact]
    outcome: PolicyOutcome
    reason_codes: tuple[str, ...]
    missing_prerequisites: tuple[str, ...]
    review_trigger: bool
    existing_task_id: str | None

    def to_wire(self) -> dict[str, object]:
        return {
            "policy_version": self.policy_version,
            "input_facts": {
                field: state.value for field, state in self.input_facts.items()
            },
            "outcome": self.outcome.value,
            "reason_codes": list(self.reason_codes),
            "missing_prerequisites": list(self.missing_prerequisites),
            "review_trigger": self.review_trigger,
            "existing_task_id": self.existing_task_id,
        }


def parse_policy_decision_payload(
    value: Mapping[str, Any],
) -> PolicyDecisionPayload:
    version = value["policy_version"]
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise ContractError("contract_semver_invalid", "policy_version")
    outcome = enum_value(PolicyOutcome, value["outcome"], "outcome")
    review_trigger = value["review_trigger"]
    if not isinstance(review_trigger, bool):
        raise ContractError("contract_type_invalid", "review_trigger")
    if review_trigger is not (outcome is PolicyOutcome.REVIEW_REQUIRED):
        raise ContractError("contract_value_invalid", "review_trigger")
    return PolicyDecisionPayload(
        policy_version=version,
        input_facts=parse_policy_input_facts(value["input_facts"]),
        outcome=outcome,
        reason_codes=tuple_of_strings(value["reason_codes"], "reason_codes"),
        missing_prerequisites=tuple_of_strings(
            value["missing_prerequisites"], "missing_prerequisites"
        ),
        review_trigger=review_trigger,
        existing_task_id=uuid_value(
            value["existing_task_id"], "existing_task_id", nullable=True
        ),
    )
