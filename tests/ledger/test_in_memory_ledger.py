from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest

from recall.contracts import ContractError, DataMode
from recall.controller import Controller, ScanRunEventCode
from recall.ledger import InMemoryLedger, ScanRunRecord

from .helpers import ARTIFACT_ID, RUN_ID, conflicting_receipt, tool_receipt
from tests.admission import admit_watch_case, in_memory_ledger


CASE_ID = "728d6e23-5ee4-4bd4-9319-4304f55628f3"


def _leased_ledger(
    now: datetime, *, lease_seconds: int = 300
) -> tuple[InMemoryLedger, Controller, ScanRunRecord]:
    ledger = in_memory_ledger()
    controller = Controller(ledger)
    admitted, receipt, _payload = admit_watch_case(
        ledger,
        controller,
        case_id=CASE_ID,
        now=now,
        next_scan_at="2026-08-22T00:00:00Z",
        source_cursors={"clinvar": "42"},
    )
    created = controller.create_run(
        watch_case_id=CASE_ID,
        source_cursors={"clinvar": "42"},
        schedule_epoch="2026-08-22T00:00:00Z",
        data_mode=DataMode.SYNTHETIC,
        privacy_receipt_id=str(receipt["artifact_id"]),
        expected_watch_case_version=admitted.record.version,
        triggered_at=datetime(2026, 8, 22, tzinfo=UTC),
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
        deadline_at="2026-08-22T00:09:59Z",
        now=now,
    ).record
    queued = controller.transition(
        created.run_id,
        expected_version=1,
        lease_epoch=0,
        event_code=ScanRunEventCode.OUTBOX_PUBLISHED,
        now=now,
    )
    routing = controller.acquire_lease(
        queued.run_id,
        expected_version=2,
        new_epoch=1,
        expires_at=now + timedelta(seconds=lease_seconds),
        now=now,
    )
    return ledger, controller, routing


def test_append_is_idempotent_but_rejects_same_id_with_different_hash() -> None:
    ledger = in_memory_ledger()
    wire = tool_receipt()

    first = ledger.append_artifact(wire)
    second = ledger.append_artifact(wire)

    assert first.to_wire() == second.to_wire()
    assert ledger.get_artifact(ARTIFACT_ID) == wire
    assert [item["artifact_id"] for item in ledger.list_by_run(RUN_ID)] == [
        ARTIFACT_ID
    ]

    with pytest.raises(ContractError, match="artifact_integrity_failed"):
        ledger.append_artifact(conflicting_receipt())
    assert ledger.get_artifact(ARTIFACT_ID) == wire


def test_transition_cas_writes_one_event_and_stale_version_changes_nothing() -> None:
    now = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
    ledger, controller, routing = _leased_ledger(now)
    running = controller.transition(
        routing.run_id,
        expected_version=3,
        lease_epoch=1,
        event_code=ScanRunEventCode.ROUTE_VALIDATED,
        now=now + timedelta(seconds=1),
    )

    assert running.version == 4
    assert running.state == "WATCHING"
    assert ledger.read_back_count("scan_run_events", run_id=running.run_id) == 4

    with pytest.raises(ContractError, match="stale_write_rejected"):
        controller.transition(
            running.run_id,
            expected_version=3,
            lease_epoch=1,
            event_code=ScanRunEventCode.CANDIDATE_UNKNOWN,
            now=now + timedelta(seconds=2),
        )
    assert ledger.get_scan_run(running.run_id) == running
    assert ledger.read_back_count("scan_run_events", run_id=running.run_id) == 4


def test_ledger_rejects_mismatched_transition_without_any_write() -> None:
    now = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
    ledger, _controller, routing = _leased_ledger(now)
    pointer_before = ledger.get_scan_run(routing.run_id)
    events_before = ledger.read_back_count(
        "scan_run_events", run_id=routing.run_id
    )
    artifacts_before = ledger.read_back_count("artifacts", run_id=routing.run_id)

    with pytest.raises(ContractError, match="contract_transition_invalid"):
        ledger.transition_with_cas(
            routing.run_id,
            expected_version=routing.version,
            lease_epoch=routing.lease_epoch,
            to_state="ASSESSING",
            event_code=ScanRunEventCode.ROUTE_VALIDATED,
            now=now + timedelta(seconds=1),
        )

    assert ledger.get_scan_run(routing.run_id) == pointer_before
    assert (
        ledger.read_back_count("scan_run_events", run_id=routing.run_id)
        == events_before
    )
    assert ledger.read_back_count("artifacts", run_id=routing.run_id) == artifacts_before

def test_expired_lease_rejects_transition_without_state_or_event_change() -> None:
    now = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
    ledger, controller, routing = _leased_ledger(now, lease_seconds=1)

    with pytest.raises(ContractError, match="lease_expired"):
        controller.transition(
            routing.run_id,
            expected_version=3,
            lease_epoch=1,
            event_code=ScanRunEventCode.ROUTE_VALIDATED,
            now=now + timedelta(seconds=2),
        )

    assert ledger.get_scan_run(routing.run_id) == routing
    assert ledger.read_back_count("scan_run_events", run_id=routing.run_id) == 3


def test_concurrent_compare_and_set_allows_exactly_one_writer() -> None:
    now = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
    ledger, controller, routing = _leased_ledger(now)
    barrier = Barrier(2)

    def compete(event_code: ScanRunEventCode) -> str:
        barrier.wait()
        try:
            controller.transition(
                routing.run_id,
                expected_version=3,
                lease_epoch=1,
                event_code=event_code,
                now=now + timedelta(seconds=1),
            )
            return "committed"
        except ContractError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                compete,
                [
                    ScanRunEventCode.ROUTE_VALIDATED,
                    ScanRunEventCode.PREREQUISITE_FAILED,
                ],
            )
        )

    assert sorted(results) == ["committed", "stale_write_rejected"]
    assert ledger.read_back_count("scan_run_events", run_id=routing.run_id) == 4
