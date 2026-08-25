from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from recall.contracts import ContractError, DataMode
from recall.controller import Controller, ScanRunEventCode, ScanRunState
from recall.ledger import InMemoryLedger

from tests.admission import admit_watch_case, in_memory_ledger


CASE_ID = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
TRACE_ID = "0a651403-8226-4072-9240-344542b0c5fb"
BUDGET = {
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
}


def create(controller: Controller, ledger: InMemoryLedger, now: datetime):
    admitted_record = ledger.get_watch_case(CASE_ID)
    if admitted_record is None:
        admitted, receipt, _payload = admit_watch_case(
            ledger,
            controller,
            case_id=CASE_ID,
            now=now,
            next_scan_at="2026-08-22T00:00:00Z",
            source_cursors={"clinvar": "42", "pubmed": "17"},
        )
        admitted_record = admitted.record
        receipt_id = str(receipt["artifact_id"])
    else:
        watch_artifact = ledger.get_artifact(admitted_record.artifact_id)
        assert watch_artifact is not None
        receipt_id = str(watch_artifact["input_artifact_ids"][0])
    return controller.create_run(
        watch_case_id=CASE_ID,
        source_cursors={"clinvar": "42", "pubmed": "17"},
        schedule_epoch="2026-08-22T00:00:00Z",
        data_mode=DataMode.SYNTHETIC,
        privacy_receipt_id=receipt_id,
        expected_watch_case_version=admitted_record.version,
        triggered_at=datetime(2026, 8, 22, tzinfo=UTC),
        budget_snapshot=BUDGET,
        trace_id=TRACE_ID,
        deadline_at="2026-08-22T00:09:59Z",
        now=now,
    )


def test_create_run_is_idempotent_and_writes_one_artifact_and_event() -> None:
    ledger = in_memory_ledger()
    controller = Controller(ledger)
    now = datetime(2026, 8, 22, tzinfo=UTC)

    first = create(controller, ledger, now)
    second = create(controller, ledger, now + timedelta(seconds=1))

    assert first.record.run_id == second.record.run_id
    assert first.created is True
    assert second.created is False
    assert ledger.read_back_count("artifacts", run_id=first.record.run_id) == 1
    assert ledger.read_back_count("scan_runs", run_id=first.record.run_id) == 1
    assert ledger.read_back_count("scan_run_events", run_id=first.record.run_id) == 1
    assert first.record.scan_run_artifact_id is not None
    assert second.record.version == 1


def test_pointer_state_and_version_match_last_event() -> None:
    ledger = in_memory_ledger()
    controller = Controller(ledger)
    now = datetime(2026, 8, 22, tzinfo=UTC)
    created = create(controller, ledger, now).record

    queued = controller.transition(
        created.run_id,
        expected_version=1,
        lease_epoch=0,
        event_code=ScanRunEventCode.OUTBOX_PUBLISHED,
        now=now + timedelta(seconds=1),
    )
    events = ledger.list_scan_run_events(created.run_id)

    assert queued.state is ScanRunState.QUEUED
    assert queued.state is events[-1].to_state
    assert queued.version == events[-1].sequence


def test_expired_lease_can_be_taken_over_with_new_epoch() -> None:
    ledger = in_memory_ledger()
    controller = Controller(ledger)
    now = datetime(2026, 8, 22, tzinfo=UTC)
    created = create(controller, ledger, now).record
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
        expires_at=now + timedelta(seconds=5),
        now=now + timedelta(seconds=2),
    )

    with pytest.raises(ContractError, match="lease_active"):
        controller.acquire_lease(
            routing.run_id,
            expected_version=3,
            new_epoch=2,
            expires_at=now + timedelta(seconds=10),
            now=now + timedelta(seconds=4),
        )

    taken_over = controller.acquire_lease(
        routing.run_id,
        expected_version=3,
        new_epoch=2,
        expires_at=now + timedelta(seconds=12),
        now=now + timedelta(seconds=6),
    )
    events = ledger.list_scan_run_events(routing.run_id)

    assert taken_over.state is ScanRunState.ROUTING
    assert taken_over.lease_epoch == 2
    assert taken_over.version == 4
    assert events[-1].event_code is ScanRunEventCode.LEASE_TAKEN_OVER
    assert taken_over.state is events[-1].to_state
    assert taken_over.version == events[-1].sequence


def test_stale_takeover_changes_no_pointer_or_event() -> None:
    ledger = in_memory_ledger()
    controller = Controller(ledger)
    now = datetime(2026, 8, 22, tzinfo=UTC)
    created = create(controller, ledger, now).record
    queued = controller.transition(
        created.run_id,
        expected_version=1,
        lease_epoch=0,
        event_code=ScanRunEventCode.OUTBOX_PUBLISHED,
        now=now + timedelta(seconds=1),
    )
    before_events = ledger.list_scan_run_events(created.run_id)

    with pytest.raises(ContractError, match="stale_write_rejected"):
        controller.acquire_lease(
            queued.run_id,
            expected_version=1,
            new_epoch=1,
            expires_at=now + timedelta(seconds=10),
            now=now + timedelta(seconds=2),
        )

    assert ledger.get_scan_run(created.run_id) == queued
    assert ledger.list_scan_run_events(created.run_id) == before_events
