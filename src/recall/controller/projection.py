from __future__ import annotations

from recall.contracts.enums import FactState, PresenceState
from recall.contracts.failure_registry import (
    FAILURE_REGISTRY,
    FailureCode,
    FailureProjection,
)


_SCHEMA_PROJECTIONS = {
    "PrivacyReceipt": FailureProjection(
        "privacy_accepted", FactState.FAIL, ("privacy_not_accepted",)
    ),
    "RegistryResolutionReceipt": FailureProjection(
        "registry_resolution_valid",
        FactState.FAIL,
        ("registry_resolution_invalid",),
    ),
    "ToolAuthorizationReceipt": FailureProjection(
        "tool_authorization_complete",
        FactState.FAIL,
        ("tool_authorization_incomplete",),
    ),
    "EvidenceSnapshot": FailureProjection(
        "snapshot_integrity_valid",
        FactState.FAIL,
        ("snapshot_integrity_invalid",),
    ),
    "EvidenceObservation": FailureProjection(
        "snapshot_integrity_valid",
        FactState.FAIL,
        ("snapshot_integrity_invalid",),
    ),
    "DataModeReceipt": FailureProjection(
        "data_mode_valid", FactState.FAIL, ("data_mode_invalid",)
    ),
    "CandidateDeltaReceipt": FailureProjection(
        "candidate_delta_state",
        PresenceState.UNKNOWN,
        ("candidate_delta_not_evaluated",),
    ),
    "EvidenceDelta": FailureProjection(
        "assessment_valid", FactState.FAIL, ("assessment_invalid",)
    ),
    "AssessmentReceipt": FailureProjection(
        "assessment_valid", FactState.FAIL, ("assessment_invalid",)
    ),
    "CitationAuditReceipt": FailureProjection(
        "citation_audit_complete",
        FactState.FAIL,
        ("citation_audit_incomplete",),
    ),
}

_CONTRACT_FAILURES = frozenset(
    {
        FailureCode.CONTRACT_UNKNOWN_FIELD,
        FailureCode.CONTRACT_REQUIRED_FIELD_MISSING,
        FailureCode.ARTIFACT_INTEGRITY_FAILED,
        FailureCode.PRODUCER_NOT_AUTHORIZED,
    }
)


def project_failure(
    code: FailureCode, artifact_schema: str
) -> FailureProjection | None:
    if artifact_schema == "PolicyDecision":
        return None
    if code in _CONTRACT_FAILURES and artifact_schema in _SCHEMA_PROJECTIONS:
        return _SCHEMA_PROJECTIONS[artifact_schema]
    return FAILURE_REGISTRY[code]
