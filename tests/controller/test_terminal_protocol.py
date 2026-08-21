from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

import pytest

from recall.contracts import ContractError, DataMode
from recall.controller import Controller, ScanRunEventCode, ScanRunState
from recall.ledger import InMemoryLedger

from .test_run_coordination import BUDGET, CASE_ID, TRACE_ID
from .policy_inputs import append_policy_artifacts


def _facts(candidate: str) -> dict[str, str]:
    downstream = "PASS" if candidate == "PRESENT" else "NOT_EVALUATED"
    return {
        "privacy_accepted": "PASS",
        "registry_resolution_valid": "PASS",
        "route_valid": "PASS",
        "tool_authorization_complete": "PASS",
        "source_retrieval_complete": "PASS",
        "source_schema_valid": "PASS",
        "data_mode_valid": "PASS",
        "snapshot_integrity_valid": "PASS",
        "candidate_delta_state": candidate,
        "assessment_valid": downstream,
        "citation_audit_complete": downstream,
        "all_material_claims_verified": downstream,
        "counter_evidence_complete": downstream,
        "unresolved_conflict_state": "ABSENT",
        "budget_or_loop_failure_state": "ABSENT",
        "existing_open_task_state": "ABSENT" if candidate == "PRESENT" else "UNKNOWN",
    }


def _policy_ready(
    *, candidate_event: ScanRunEventCode, create_watch_case: bool = False
) -> tuple[Controller, InMemoryLedger, str, datetime]:
    ledger = InMemoryLedger()
    controller = Controller(ledger)
    now = datetime(2026, 8, 22, tzinfo=UTC)
    if create_watch_case:
        controller.create_watch_case(
            watch_case_id=CASE_ID,
            tenant_id="synthetic-contest-lab",
            region="us-central1",
            source_cursors={"clinvar": "42"},
            pending_observation_hashes=("4" * 64,),
            next_scan_at="2026-08-22T00:00:00Z",
            now=now,
        )
    created = controller.create_run(
        watch_case_id=CASE_ID,
        source_cursors={"clinvar": "42"},
        schedule_epoch="2026-08-22T00:00:00Z",
        data_mode=DataMode.SYNTHETIC,
        budget_snapshot=BUDGET,
        trace_id=TRACE_ID,
        deadline_at="2026-08-22T00:09:59Z",
        now=now,
    ).record
    queued = controller.transition(
        created.run_id,
        expected_version=1,
        lease_epoch=0,
        event_code=ScanRunEventCode.OUTBOX_PUBLISHED,
        now=now + timedelta(seconds=1),
    )
    routing = controller.acquire_lease(
        queued.run_id,
        expected_version=2,
        new_epoch=1,
        expires_at=now + timedelta(minutes=5),
        now=now + timedelta(seconds=2),
    )
    watching = controller.transition(
        routing.run_id,
        expected_version=3,
        lease_epoch=1,
        event_code=ScanRunEventCode.ROUTE_VALIDATED,
        now=now + timedelta(seconds=3),
    )
    policy_ready = controller.transition(
        watching.run_id,
        expected_version=4,
        lease_epoch=1,
        event_code=candidate_event,
        now=now + timedelta(seconds=4),
    )
    if candidate_event is ScanRunEventCode.CANDIDATE_PRESENT:
        assessing = policy_ready
        auditing = controller.transition(
            assessing.run_id,
            expected_version=5,
            lease_epoch=1,
            event_code=ScanRunEventCode.ASSESSMENT_COMPLETED,
            now=now + timedelta(seconds=5),
        )
        policy_ready = controller.transition(
            auditing.run_id,
            expected_version=6,
            lease_epoch=1,
            event_code=ScanRunEventCode.AUDIT_COMPLETED,
            now=now + timedelta(seconds=6),
        )
    assert policy_ready.state is ScanRunState.POLICY_EVALUATION
    return controller, ledger, policy_ready.run_id, now


def test_no_action_is_committed_once_and_duplicate_delivery_skips_policy() -> None:
    controller, ledger, run_id, now = _policy_ready(
        candidate_event=ScanRunEventCode.CANDIDATE_ABSENT,
        create_watch_case=True,
    )
    append_policy_artifacts(
        ledger,
        run_id=run_id,
        case_id=CASE_ID,
        now=now + timedelta(seconds=7),
        candidate="ABSENT",
    )

    first = controller.evaluate_and_commit(
        run_id,
        verified_delta_hash="1" * 64,
        verified_snapshot_id="00000000-0000-0000-0000-000000000001",
        verified_source_cursors={"clinvar": "43"},
        now=now + timedelta(seconds=7),
    )
    event_count = ledger.read_back_count("scan_run_events", run_id=run_id)
    second = controller.evaluate_and_commit(
        run_id,
        verified_delta_hash="1" * 64,
        verified_snapshot_id="00000000-0000-0000-0000-000000000001",
        verified_source_cursors={"clinvar": "43"},
        now=now + timedelta(seconds=8),
    )

    assert first.record.state is ScanRunState.NO_ACTION
    assert second.record == first.record
    assert second.reused is True
    assert controller.policy_call_count == 1
    assert ledger.read_back_count("scan_run_events", run_id=run_id) == event_count
    assert len(ledger.list_review_tasks(run_id)) == 0
    assert [item["schema_name"] for item in ledger.list_by_run(run_id)].count(
        "PolicyDecision"
    ) == 1


def test_review_required_creates_exactly_one_task_and_idempotent_outbox() -> None:
    controller, ledger, run_id, now = _policy_ready(
        candidate_event=ScanRunEventCode.CANDIDATE_PRESENT,
        create_watch_case=True,
    )
    artifacts = append_policy_artifacts(
        ledger,
        run_id=run_id,
        case_id=CASE_ID,
        now=now + timedelta(seconds=7),
        candidate="PRESENT",
    )

    first = controller.evaluate_and_commit(
        run_id,
        verified_delta_hash="2" * 64,
        audit_receipt_id=artifacts["CitationAuditReceipt"],
        claim_ids=("claim-001",),
        verified_snapshot_id="00000000-0000-0000-0000-000000000002",
        verified_source_cursors={"clinvar": "44"},
        now=now + timedelta(seconds=8),
    )
    second = controller.evaluate_and_commit(
        run_id,
        verified_delta_hash="2" * 64,
        audit_receipt_id=artifacts["CitationAuditReceipt"],
        claim_ids=("claim-001",),
        verified_snapshot_id="00000000-0000-0000-0000-000000000002",
        verified_source_cursors={"clinvar": "44"},
        now=now + timedelta(seconds=9),
    )
    task = ledger.list_review_tasks(run_id)[0]

    assert first.record.state is ScanRunState.REVIEW_REQUIRED
    assert second.task_id == first.task_id == task.task_id
    assert second.reused is True
    assert controller.policy_call_count == 1
    assert len(ledger.list_review_tasks(run_id)) == 1
    assert task.delivery_state == "PENDING"

    delivered = controller.deliver_task_outbox(task.task_id)
    delivered_again = controller.deliver_task_outbox(task.task_id)

    assert delivered.delivery_state == "DELIVERED"
    assert delivered_again == delivered
    assert controller.policy_call_count == 1
    assert len(ledger.list_review_tasks(run_id)) == 1


def test_invalid_policy_output_halts_with_failure_and_no_policy_or_task() -> None:
    def corrupt_policy(_facts: object, _version: str) -> object:
        return {"outcome": "FORGED"}

    controller, ledger, run_id, now = _policy_ready(
        candidate_event=ScanRunEventCode.CANDIDATE_ABSENT,
        create_watch_case=True,
    )
    append_policy_artifacts(
        ledger,
        run_id=run_id,
        case_id=CASE_ID,
        now=now + timedelta(seconds=7),
        candidate="ABSENT",
    )
    controller = Controller(ledger, policy_evaluator=corrupt_policy)

    result = controller.evaluate_and_commit(
        run_id,
        verified_delta_hash="3" * 64,
        now=now + timedelta(seconds=7),
    )
    schemas = [item["schema_name"] for item in ledger.list_by_run(run_id)]

    assert result.record.state is ScanRunState.HALTED
    assert [item["failure_code"] for item in ledger.list_by_run(run_id) if item["schema_name"] == "FailureReceipt"] == ["policy_unavailable"]
    assert controller.policy_call_count == 1
    assert schemas.count("FailureReceipt") == 1
    assert schemas.count("PolicyDecision") == 0
    assert len(ledger.list_review_tasks(run_id)) == 0


def test_ledger_integrity_failure_halts_before_policy_call() -> None:
    controller, ledger, run_id, now = _policy_ready(
        candidate_event=ScanRunEventCode.CANDIDATE_ABSENT,
        create_watch_case=True,
    )
    identifiers = append_policy_artifacts(
        ledger,
        run_id=run_id,
        case_id=CASE_ID,
        now=now + timedelta(seconds=7),
        candidate="ABSENT",
    )
    ledger._artifacts[identifiers["CandidateDeltaReceipt"]]["content_hash"] = "0" * 64

    result = controller.evaluate_and_commit(
        run_id,
        verified_delta_hash="4" * 64,
        now=now + timedelta(seconds=8),
    )
    artifacts = ledger.list_by_run(run_id)
    failures = [item for item in artifacts if item["schema_name"] == "FailureReceipt"]

    assert result.record.state is ScanRunState.HALTED
    assert controller.policy_call_count == 0
    assert [item["failure_code"] for item in failures] == [
        "ledger_integrity_failed"
    ]
    assert not any(item["schema_name"] == "PolicyDecision" for item in artifacts)
    assert len(ledger.list_review_tasks(run_id)) == 0


def test_non_contract_fact_failure_maps_to_controller_failed_before_policy() -> None:
    def broken_facts(_ledger: object, _run_id: str) -> dict[str, object]:
        raise RuntimeError("unexpected_controller_projection_failure")

    _controller, ledger, run_id, now = _policy_ready(
        candidate_event=ScanRunEventCode.CANDIDATE_ABSENT,
        create_watch_case=True,
    )
    append_policy_artifacts(
        ledger,
        run_id=run_id,
        case_id=CASE_ID,
        now=now + timedelta(seconds=7),
        candidate="ABSENT",
    )
    controller = Controller(ledger, facts_builder=broken_facts)

    result = controller.evaluate_and_commit(
        run_id,
        verified_delta_hash="5" * 64,
        now=now + timedelta(seconds=8),
    )
    artifacts = ledger.list_by_run(run_id)

    assert result.record.state is ScanRunState.HALTED
    assert controller.policy_call_count == 0
    assert [item["failure_code"] for item in artifacts if item["schema_name"] == "FailureReceipt"] == ["controller_failed"]
    assert not any(item["schema_name"] == "PolicyDecision" for item in artifacts)
    assert len(ledger.list_review_tasks(run_id)) == 0


def test_policy_input_contract_failure_maps_to_controller_failed() -> None:
    def unsupported_policy(_facts: object, _version: str) -> object:
        raise ContractError(
            "contract_policy_version_unsupported", "policy-input-version"
        )

    _controller, ledger, run_id, now = _policy_ready(
        candidate_event=ScanRunEventCode.CANDIDATE_ABSENT,
        create_watch_case=True,
    )
    append_policy_artifacts(
        ledger,
        run_id=run_id,
        case_id=CASE_ID,
        now=now + timedelta(seconds=7),
        candidate="ABSENT",
    )
    controller = Controller(ledger, policy_evaluator=unsupported_policy)

    result = controller.evaluate_and_commit(
        run_id,
        verified_delta_hash="6" * 64,
        now=now + timedelta(seconds=8),
    )
    artifacts = ledger.list_by_run(run_id)

    assert result.record.state is ScanRunState.HALTED
    assert controller.policy_call_count == 1
    assert [item["failure_code"] for item in artifacts if item["schema_name"] == "FailureReceipt"] == ["controller_failed"]
    assert not any(item["schema_name"] == "PolicyDecision" for item in artifacts)
    assert len(ledger.list_review_tasks(run_id)) == 0


def test_missing_watch_case_is_a_ledger_integrity_halt_not_semantic_terminal() -> None:
    controller, ledger, run_id, now = _policy_ready(
        candidate_event=ScanRunEventCode.CANDIDATE_ABSENT,
        create_watch_case=False,
    )
    append_policy_artifacts(
        ledger,
        run_id=run_id,
        case_id=CASE_ID,
        now=now + timedelta(seconds=7),
        candidate="ABSENT",
    )

    result = controller.evaluate_and_commit(
        run_id,
        verified_delta_hash="7" * 64,
        verified_snapshot_id="00000000-0000-0000-0000-000000000007",
        verified_source_cursors={"clinvar": "43"},
        now=now + timedelta(seconds=8),
    )
    artifacts = ledger.list_by_run(run_id)

    assert result.record.state is ScanRunState.HALTED
    assert [item["failure_code"] for item in artifacts if item["schema_name"] == "FailureReceipt"] == ["ledger_integrity_failed"]
    assert not any(item["schema_name"] == "PolicyDecision" for item in artifacts)
    assert len(ledger.list_review_tasks(run_id)) == 0


def test_terminal_artifact_conflict_rejects_without_partial_authoritative_write() -> None:
    controller, ledger, run_id, now = _policy_ready(
        candidate_event=ScanRunEventCode.CANDIDATE_PRESENT,
        create_watch_case=True,
    )
    inputs = append_policy_artifacts(
        ledger,
        run_id=run_id,
        case_id=CASE_ID,
        now=now + timedelta(seconds=7),
        candidate="PRESENT",
    )
    delta_hash = "8" * 64
    decision_id = str(uuid5(UUID(run_id), "policy-decision"))
    ledger._artifacts[decision_id] = {
        "content_hash": "0" * 64,
        "run_id": None,
    }
    pointer_before = ledger.get_scan_run(run_id)
    events_before = ledger.read_back_count("scan_run_events", run_id=run_id)
    artifacts_before = len(ledger._artifacts)

    with pytest.raises(ContractError, match="artifact_integrity_failed"):
        controller.evaluate_and_commit(
            run_id,
            verified_delta_hash=delta_hash,
            audit_receipt_id=inputs["CitationAuditReceipt"],
            claim_ids=("claim-001",),
            verified_snapshot_id=inputs["EvidenceSnapshot"],
            verified_source_cursors={"clinvar": "44"},
            now=now + timedelta(seconds=8),
        )

    assert ledger.get_scan_run(run_id) == pointer_before
    assert ledger.read_back_count("scan_run_events", run_id=run_id) == events_before
    assert len(ledger._artifacts) == artifacts_before
    assert not any(
        item.get("schema_name") == "PolicyDecision"
        for item in ledger.list_by_run(run_id)
    )
