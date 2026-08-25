from __future__ import annotations

from datetime import timedelta
from dataclasses import replace

from recall.contracts import DataMode
from recall.contracts.enums import ScanRunEventCode, WatchCaseState
from recall.controller import Controller

from .test_run_coordination import CASE_ID
from .policy_inputs import append_policy_artifacts
from .test_terminal_protocol import _policy_ready


PENDING_HASH = "c" * 64
VERIFIED_SNAPSHOT_ID = "eb78d84a-640e-446b-8cf7-d735a97f2f1b"


def _attach_watch_case(_controller: Controller, _now) -> None:
    return None


def test_abstain_preserves_verified_cursor_and_pending_observation() -> None:
    controller, ledger, run_id, now = _policy_ready(
        candidate_event=ScanRunEventCode.CANDIDATE_ABSENT,
        create_watch_case=True,
        source_cursors={"clinvar": "41"},
    )
    _attach_watch_case(controller, now)
    append_policy_artifacts(
        ledger,
        run_id=run_id,
        case_id=CASE_ID,
        now=now + timedelta(seconds=7),
        candidate="ABSENT",
        tool_decision="DENIED",
    )

    controller.evaluate_and_commit(
        run_id,
        verified_delta_hash="1" * 64,
        verified_snapshot_id=VERIFIED_SNAPSHOT_ID,
        verified_source_cursors={"clinvar": "42"},
        pending_observation_hashes=(PENDING_HASH,),
        now=now + timedelta(seconds=8),
    )
    watch_case = ledger.get_watch_case(CASE_ID)

    assert watch_case is not None
    assert dict(watch_case.source_cursors) == {"clinvar": "41"}
    assert watch_case.last_verified_snapshot_id is None
    assert watch_case.pending_observation_hashes == (PENDING_HASH,)
    assert watch_case.state is WatchCaseState.ACTIVE


def test_no_action_advances_exact_verified_cursor_and_clears_pending() -> None:
    controller, ledger, run_id, now = _policy_ready(
        candidate_event=ScanRunEventCode.CANDIDATE_ABSENT,
        create_watch_case=True,
        source_cursors={"clinvar": "41"},
    )
    _attach_watch_case(controller, now)
    append_policy_artifacts(
        ledger,
        run_id=run_id,
        case_id=CASE_ID,
        now=now + timedelta(seconds=7),
        candidate="ABSENT",
    )

    controller.evaluate_and_commit(
        run_id,
        verified_delta_hash="1" * 64,
        verified_snapshot_id=VERIFIED_SNAPSHOT_ID,
        verified_source_cursors={"clinvar": "42"},
        pending_observation_hashes=(PENDING_HASH,),
        now=now + timedelta(seconds=8),
    )
    watch_case = ledger.get_watch_case(CASE_ID)

    assert watch_case is not None
    assert dict(watch_case.source_cursors) == {"clinvar": "42"}
    assert watch_case.last_verified_snapshot_id == VERIFIED_SNAPSHOT_ID
    assert watch_case.pending_observation_hashes == ()
    assert watch_case.state is WatchCaseState.ACTIVE


def test_review_required_links_task_and_advances_only_audited_snapshot() -> None:
    controller, ledger, run_id, now = _policy_ready(
        candidate_event=ScanRunEventCode.CANDIDATE_PRESENT,
        create_watch_case=True,
        source_cursors={"clinvar": "41"},
    )
    _attach_watch_case(controller, now)
    artifacts = append_policy_artifacts(
        ledger,
        run_id=run_id,
        case_id=CASE_ID,
        now=now + timedelta(seconds=7),
        candidate="PRESENT",
    )

    result = controller.evaluate_and_commit(
        run_id,
        verified_delta_hash="2" * 64,
        audit_receipt_id=artifacts["CitationAuditReceipt"],
        claim_ids=("claim-001",),
        verified_snapshot_id=VERIFIED_SNAPSHOT_ID,
        verified_source_cursors={"clinvar": "42"},
        pending_observation_hashes=(PENDING_HASH,),
        now=now + timedelta(seconds=8),
    )
    watch_case = ledger.get_watch_case(CASE_ID)

    assert watch_case is not None
    assert watch_case.state is WatchCaseState.AWAITING_HUMAN
    assert watch_case.open_review_task_id == result.task_id
    assert watch_case.last_verified_snapshot_id == VERIFIED_SNAPSHOT_ID
    assert watch_case.pending_observation_hashes == ()


def test_policy_unavailable_halts_without_advancing_cursor() -> None:
    def corrupt_policy(_facts: object, _version: str) -> object:
        return {"outcome": "FORGED"}

    controller, ledger, run_id, now = _policy_ready(
        candidate_event=ScanRunEventCode.CANDIDATE_ABSENT,
        create_watch_case=True,
        source_cursors={"clinvar": "41"},
    )
    _attach_watch_case(controller, now)
    append_policy_artifacts(
        ledger,
        run_id=run_id,
        case_id=CASE_ID,
        now=now + timedelta(seconds=7),
        candidate="ABSENT",
    )
    controller = Controller(ledger, policy_evaluator=corrupt_policy)

    controller.evaluate_and_commit(
        run_id,
        verified_delta_hash="3" * 64,
        verified_snapshot_id=VERIFIED_SNAPSHOT_ID,
        verified_source_cursors={"clinvar": "42"},
        pending_observation_hashes=(PENDING_HASH,),
        now=now + timedelta(seconds=8),
    )
    watch_case = ledger.get_watch_case(CASE_ID)

    assert watch_case is not None
    assert watch_case.state is WatchCaseState.ATTENTION_REQUIRED
    assert dict(watch_case.source_cursors) == {"clinvar": "41"}
    assert watch_case.last_verified_snapshot_id is None
    assert watch_case.pending_observation_hashes == (PENDING_HASH,)


def test_abstained_observation_hash_is_reseen_in_next_run() -> None:
    controller, ledger, run_id, now = _policy_ready(
        candidate_event=ScanRunEventCode.CANDIDATE_ABSENT,
        create_watch_case=True,
        source_cursors={"clinvar": "41"},
    )
    _attach_watch_case(controller, now)
    append_policy_artifacts(
        ledger,
        run_id=run_id,
        case_id=CASE_ID,
        now=now + timedelta(seconds=7),
        candidate="ABSENT",
        tool_decision="DENIED",
    )
    controller.evaluate_and_commit(
        run_id,
        verified_delta_hash="1" * 64,
        pending_observation_hashes=(PENDING_HASH,),
        now=now + timedelta(seconds=8),
    )
    watch_case = ledger.get_watch_case(CASE_ID)
    assert watch_case is not None
    watch_artifact = ledger.get_artifact(watch_case.artifact_id)
    assert watch_artifact is not None
    privacy_receipt_id = str(watch_artifact["input_artifact_ids"][0])
    ledger._watch_cases[CASE_ID] = replace(
        watch_case,
        next_scan_at="2026-08-22T01:00:00Z",
    )
    watch_case = ledger.get_watch_case(CASE_ID)
    assert watch_case is not None
    next_run = controller.create_run(
        watch_case_id=CASE_ID,
        source_cursors={"clinvar": "41"},
        schedule_epoch="2026-08-22T01:00:00Z",
        data_mode=DataMode.SYNTHETIC,
        privacy_receipt_id=privacy_receipt_id,
        expected_watch_case_version=watch_case.version,
        triggered_at=now + timedelta(hours=1),
        budget_snapshot={
            "delegation_depth": 1,
            "specialist_invocations": 3,
            "model_calls_per_role": 1,
            "schema_repairs": 1,
            "agent_retries": 1,
            "connector_retries": 3,
            "repeated_state_limit": 1,
            "wall_time_seconds": 599,
            "step_deadlines": {},
            "token_ceilings": {},
        },
        trace_id="0a651403-8226-4072-9240-344542b0c5fb",
        deadline_at="2026-08-22T01:09:59Z",
        now=now + timedelta(hours=1),
    ).record
    artifacts = append_policy_artifacts(
        ledger,
        run_id=next_run.run_id,
        case_id=CASE_ID,
        now=now + timedelta(hours=1, seconds=1),
        candidate="PRESENT",
    )
    candidate = ledger.get_artifact(artifacts["CandidateDeltaReceipt"])

    assert candidate is not None
    assert candidate["new_observation_hashes"] == [PENDING_HASH]
