from __future__ import annotations

import json
from pathlib import Path

import pytest

from recall.contracts import (
    AgentRole,
    ContractError,
    FactState,
    PolicyOutcome,
    TerminalState,
    authorize_tool_request,
    parse_fault_fixture,
)
from recall.contracts.failure_registry import FAILURE_REGISTRY, FailureCode
from recall.contracts.ui_registry import GOLDEN_PATH_UI_FIELDS


FIXTURE = Path(__file__).parents[1] / "fixtures" / "fault_run.json"


def test_f09_fixture_denies_assessor_task_creation_without_selecting_outcome() -> None:
    fixture = parse_fault_fixture(json.loads(FIXTURE.read_text(encoding="utf-8")))
    receipt = authorize_tool_request(fixture.tool_request, allowed_actions=frozenset())

    assert fixture.institutional_mode.value == "SYNTHETIC"
    assert fixture.evidence_mode.value == "CAPTURED_REPLAY"
    assert fixture.citation_mismatch is True
    assert fixture.citation_probe.cited_identifier == "PMID:12345678"
    assert fixture.citation_probe.cited_title != fixture.citation_probe.refetched_title
    assert fixture.expected_outcome is None
    assert fixture.tool_request.agent_role is AgentRole.EVIDENCE_ASSESSOR
    assert receipt.decision.value == "DENIED"
    assert receipt.reason_codes == ("tool_not_allowlisted",)


def test_f09_fixture_rejects_mock_institutional_input() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["institutional_mode"] = "MOCK"

    with pytest.raises(ContractError, match="fault_fixture_institutional_mode"):
        parse_fault_fixture(raw)


def test_f09_fixture_rejects_a_declared_mismatch_without_mismatched_records() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["citation_probe"]["refetched_title"] = raw["citation_probe"]["cited_title"]

    with pytest.raises(
        ContractError, match="fault_fixture_citation_mismatch_required"
    ):
        parse_fault_fixture(raw)


def test_f11_keeps_halted_outside_policy_outcomes() -> None:
    assert TerminalState.HALTED.value == "HALTED"
    assert "HALTED" not in {outcome.value for outcome in PolicyOutcome}
    assert "UI-FAILURE-CODE" in GOLDEN_PATH_UI_FIELDS
    assert "UI-HALTED" not in GOLDEN_PATH_UI_FIELDS
    assert "UI-GLOBAL-RUN-STATE" in GOLDEN_PATH_UI_FIELDS
    assert len(GOLDEN_PATH_UI_FIELDS) == 12


def test_f14_failure_registry_is_single_closed_mapping() -> None:
    mapping = FAILURE_REGISTRY[FailureCode.TOOL_DENIED]

    assert mapping.fact_name == "tool_authorization_complete"
    assert mapping.fact_state is FactState.FAIL
    assert mapping.reason_codes == ("tool_authorization_incomplete",)
    assert len(FAILURE_REGISTRY) == len(FailureCode)
