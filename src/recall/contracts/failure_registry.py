from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from .enums import FactState, PresenceState


class FailureCode(StrEnum):
    PRIVACY_NOT_ACCEPTED = "privacy_not_accepted"
    CONTRACT_UNKNOWN_FIELD = "contract_unknown_field"
    CONTRACT_REQUIRED_FIELD_MISSING = "contract_required_field_missing"
    ARTIFACT_INTEGRITY_FAILED = "artifact_integrity_failed"
    PRODUCER_NOT_AUTHORIZED = "producer_not_authorized"
    DATA_MODE_CONFLICT = "data_mode_conflict"
    REGISTRY_UNAVAILABLE = "registry_unavailable"
    REGISTRY_REVISION_REJECTED = "registry_revision_rejected"
    ROUTE_INVALID = "route_invalid"
    TOOL_DENIED = "tool_denied"
    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_SCHEMA_DRIFT = "source_schema_drift"
    CANDIDATE_DELTA_UNKNOWN = "candidate_delta_unknown"
    AGENT_SCHEMA_INVALID = "agent_schema_invalid"
    CITATION_MISMATCH = "citation_mismatch"
    COUNTER_EVIDENCE_INCOMPLETE = "counter_evidence_incomplete"
    AUDIT_INCOMPLETE = "audit_incomplete"
    MEMORY_REJECTED = "memory_rejected"
    DUPLICATE_SUPPRESSED = "duplicate_suppressed"
    LEASE_EXPIRED = "lease_expired"
    STALE_WRITE_REJECTED = "stale_write_rejected"
    LOOP_DETECTED = "loop_detected"
    BUDGET_EXHAUSTED = "budget_exhausted"
    POLICY_UNAVAILABLE = "policy_unavailable"
    LEDGER_INTEGRITY_FAILED = "ledger_integrity_failed"
    CONTROLLER_FAILED = "controller_failed"
    CONTRACT_TRANSITION_INVALID = "contract_transition_invalid"


@dataclass(frozen=True, slots=True)
class FailureProjection:
    fact_name: str
    fact_state: FactState | PresenceState
    reason_codes: tuple[str, ...]


ASSESSMENT_INVALID = FailureProjection(
    "assessment_valid", FactState.FAIL, ("assessment_invalid",)
)

# ADR-0008 keeps memory state out of policy inputs. A detected authority
# conflict invalidates the assessment; it is not a 27th stable failure code.
MEMORY_AUTHORITY_CONFLICT_PROJECTION = ASSESSMENT_INVALID


FAILURE_REGISTRY = MappingProxyType(
    {
        FailureCode.PRIVACY_NOT_ACCEPTED: FailureProjection(
            "privacy_accepted", FactState.FAIL, ("privacy_not_accepted",)
        ),
        FailureCode.CONTRACT_UNKNOWN_FIELD: ASSESSMENT_INVALID,
        FailureCode.CONTRACT_REQUIRED_FIELD_MISSING: ASSESSMENT_INVALID,
        FailureCode.ARTIFACT_INTEGRITY_FAILED: FailureProjection(
            "snapshot_integrity_valid",
            FactState.FAIL,
            ("snapshot_integrity_invalid",),
        ),
        FailureCode.PRODUCER_NOT_AUTHORIZED: FailureProjection(
            "tool_authorization_complete",
            FactState.FAIL,
            ("tool_authorization_incomplete",),
        ),
        FailureCode.DATA_MODE_CONFLICT: FailureProjection(
            "data_mode_valid", FactState.FAIL, ("data_mode_invalid",)
        ),
        FailureCode.REGISTRY_UNAVAILABLE: FailureProjection(
            "registry_resolution_valid",
            FactState.NOT_EVALUATED,
            ("registry_resolution_not_evaluated",),
        ),
        FailureCode.REGISTRY_REVISION_REJECTED: FailureProjection(
            "registry_resolution_valid",
            FactState.FAIL,
            ("registry_resolution_invalid",),
        ),
        FailureCode.ROUTE_INVALID: FailureProjection(
            "route_valid", FactState.FAIL, ("route_invalid",)
        ),
        FailureCode.TOOL_DENIED: FailureProjection(
            "tool_authorization_complete",
            FactState.FAIL,
            ("tool_authorization_incomplete",),
        ),
        FailureCode.SOURCE_UNAVAILABLE: FailureProjection(
            "source_retrieval_complete",
            FactState.NOT_EVALUATED,
            ("source_retrieval_not_evaluated",),
        ),
        FailureCode.SOURCE_SCHEMA_DRIFT: FailureProjection(
            "source_schema_valid", FactState.FAIL, ("source_schema_invalid",)
        ),
        FailureCode.CANDIDATE_DELTA_UNKNOWN: FailureProjection(
            "candidate_delta_state",
            PresenceState.UNKNOWN,
            ("candidate_delta_not_evaluated",),
        ),
        FailureCode.AGENT_SCHEMA_INVALID: ASSESSMENT_INVALID,
        FailureCode.CITATION_MISMATCH: FailureProjection(
            "all_material_claims_verified",
            FactState.FAIL,
            ("material_claim_unverified",),
        ),
        FailureCode.AUDIT_INCOMPLETE: FailureProjection(
            "citation_audit_complete",
            FactState.FAIL,
            ("citation_audit_incomplete",),
        ),
        FailureCode.COUNTER_EVIDENCE_INCOMPLETE: FailureProjection(
            "counter_evidence_complete",
            FactState.FAIL,
            ("counter_evidence_incomplete",),
        ),
        FailureCode.MEMORY_REJECTED: None,
        FailureCode.DUPLICATE_SUPPRESSED: None,
        FailureCode.LEASE_EXPIRED: None,
        FailureCode.STALE_WRITE_REJECTED: None,
        FailureCode.LOOP_DETECTED: FailureProjection(
            "budget_or_loop_failure_state",
            PresenceState.PRESENT,
            ("execution_budget_failed",),
        ),
        FailureCode.BUDGET_EXHAUSTED: FailureProjection(
            "budget_or_loop_failure_state",
            PresenceState.PRESENT,
            ("execution_budget_failed",),
        ),
        FailureCode.POLICY_UNAVAILABLE: None,
        FailureCode.LEDGER_INTEGRITY_FAILED: None,
        FailureCode.CONTROLLER_FAILED: None,
        FailureCode.CONTRACT_TRANSITION_INVALID: None,
    }
)
