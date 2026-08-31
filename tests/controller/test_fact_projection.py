from __future__ import annotations

from datetime import timedelta

from recall.contracts.enums import ScanRunEventCode
from recall.controller.facts import build_policy_input_facts

from .policy_inputs import append_policy_artifacts
from .test_terminal_protocol import _policy_ready


def test_facts_are_derived_from_validated_ledger_artifacts() -> None:
    _controller, ledger, run_id, now = _policy_ready(
        candidate_event=ScanRunEventCode.CANDIDATE_PRESENT
    )
    append_policy_artifacts(
        ledger,
        run_id=run_id,
        case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        now=now + timedelta(seconds=7),
        candidate="PRESENT",
        tool_decision="DENIED",
        citation_pass=False,
    )

    facts = build_policy_input_facts(ledger, run_id)

    assert facts["privacy_accepted"] == "PASS"
    assert facts["registry_resolution_valid"] == "PASS"
    assert facts["route_valid"] == "PASS"
    assert facts["tool_authorization_complete"] == "FAIL"
    assert facts["candidate_delta_state"] == "PRESENT"
    assert facts["assessment_valid"] == "PASS"
    assert facts["citation_audit_complete"] == "PASS"
    assert facts["all_material_claims_verified"] == "FAIL"
    assert facts["counter_evidence_complete"] == "PASS"
    assert facts["unresolved_conflict_state"] == "ABSENT"
    assert facts["budget_or_loop_failure_state"] == "ABSENT"
    assert facts["existing_open_task_state"] == "ABSENT"
