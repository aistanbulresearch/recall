from __future__ import annotations

from datetime import UTC, datetime, timedelta

from recall.contracts import DataMode
from recall.controller import Controller, ScanRunEventCode, ScanRunState
from recall.ledger import InMemoryLedger

from .test_run_coordination import BUDGET, CASE_ID, TRACE_ID


def test_second_semantically_identical_state_blocks_downstream_step() -> None:
    ledger = InMemoryLedger()
    controller = Controller(ledger)
    now = datetime(2026, 8, 22, tzinfo=UTC)
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
        expected_version=created.version,
        lease_epoch=created.lease_epoch,
        event_code=ScanRunEventCode.OUTBOX_PUBLISHED,
        now=now + timedelta(seconds=1),
    )
    routing = controller.acquire_lease(
        queued.run_id,
        expected_version=queued.version,
        new_epoch=1,
        expires_at=now + timedelta(minutes=5),
        now=now + timedelta(seconds=2),
    )
    calls = 0

    def downstream_step() -> str:
        nonlocal calls
        calls += 1
        return "called"

    stable_state = {
        "source_cursors": {"clinvar": "42"},
        "last_verified_snapshot_id": None,
        "pending_observation_hashes": ["2" * 64],
        "latest_artifact_hashes": ["3" * 64],
        "attempt": 1,
        "lease_epoch": 1,
        "lease_expires_at": "2026-08-22T00:05:00Z",
        "updated_at": "2026-08-22T00:00:02Z",
    }
    first = controller.run_guarded_step(
        routing.run_id,
        state_context=stable_state,
        now=now + timedelta(seconds=3),
        step=downstream_step,
    )
    retry_state = {
        **stable_state,
        "attempt": 2,
        "lease_epoch": 99,
        "lease_expires_at": "2026-08-22T00:06:00Z",
        "updated_at": "2026-08-22T00:00:04Z",
    }
    second = controller.run_guarded_step(
        routing.run_id,
        state_context=retry_state,
        now=now + timedelta(seconds=4),
        step=downstream_step,
    )

    current = ledger.get_scan_run(routing.run_id)
    events = ledger.list_scan_run_events(routing.run_id)
    artifacts = ledger.list_by_run(routing.run_id)
    failures = [item for item in artifacts if item["schema_name"] == "FailureReceipt"]

    assert first.loop_detected is False
    assert first.step_result == "called"
    assert second.loop_detected is True
    assert second.step_result is None
    assert calls == 1
    assert current is not None
    assert current.state is ScanRunState.POLICY_EVALUATION
    assert current.version == events[-1].sequence
    assert current.state is events[-1].to_state
    assert events[-1].event_code is ScanRunEventCode.LOOP_DETECTED
    assert len(failures) == 1
    assert failures[0]["failure_code"] == "loop_detected"
    assert failures[0]["safe_terminal"] == "POLICY_BOUND"
    assert failures[0]["details"]["hop_count"] == 2
