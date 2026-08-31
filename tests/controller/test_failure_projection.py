from __future__ import annotations

import pytest

from recall.contracts.enums import FactState, PresenceState
from recall.contracts.failure_registry import FailureCode
from recall.controller.projection import project_failure


@pytest.mark.parametrize(
    ("schema_name", "fact_name"),
    [
        ("PrivacyReceipt", "privacy_accepted"),
        ("ToolAuthorizationReceipt", "tool_authorization_complete"),
        ("EvidenceSnapshot", "snapshot_integrity_valid"),
    ],
)
def test_same_contract_failure_projects_by_artifact_schema(
    schema_name: str, fact_name: str
) -> None:
    projection = project_failure(FailureCode.CONTRACT_UNKNOWN_FIELD, schema_name)

    assert projection is not None
    assert projection.fact_name == fact_name
    assert projection.fact_state is FactState.FAIL


def test_candidate_delta_contract_failure_projects_unknown_presence() -> None:
    projection = project_failure(
        FailureCode.CONTRACT_REQUIRED_FIELD_MISSING, "CandidateDeltaReceipt"
    )
    assert projection is not None
    assert projection.fact_name == "candidate_delta_state"
    assert projection.fact_state is PresenceState.UNKNOWN


def test_invalid_policy_decision_is_not_projected_as_semantic_fact() -> None:
    assert (
        project_failure(FailureCode.CONTRACT_UNKNOWN_FIELD, "PolicyDecision")
        is None
    )
