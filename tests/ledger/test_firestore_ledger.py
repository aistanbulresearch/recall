from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from recall.contracts import ContractError, DataMode
from recall.controller import Controller, ScanRunEventCode
from recall.ledger import FirestoreLedger

from .helpers import ARTIFACT_ID, RUN_ID, conflicting_receipt, tool_receipt


@pytest.fixture
def firestore_ledger() -> FirestoreLedger:
    mode = os.getenv("RECALL_FIRESTORE_TEST_MODE")
    emulator_host = os.getenv("FIRESTORE_EMULATOR_HOST")
    if mode == "emulator":
        if not emulator_host:
            pytest.fail("firestore_emulator_unavailable:FIRESTORE_EMULATOR_HOST_missing")
        prefix = ""
    elif mode == "live":
        prefix = f"dev_recall_3e_{uuid4().hex}_"
    else:
        pytest.fail(
            "firestore_test_mode_required:set_RECALL_FIRESTORE_TEST_MODE_to_emulator_or_live"
        )

    ledger = FirestoreLedger.from_default_credentials(collection_prefix=prefix)
    try:
        yield ledger
    finally:
        before_cleanup = {
            collection: ledger.read_back_count(collection)
            for collection in ledger.collection_names
        }
        print(
            "firestore_evidence="
            f"mode={mode.upper()},data=SYNTHETIC,before_cleanup={before_cleanup}"
        )
        ledger.cleanup_collections()
        after_cleanup = {
            collection: ledger.read_back_count(collection)
            for collection in ledger.collection_names
        }
        print(
            "firestore_evidence="
            f"mode={mode.upper()},data=SYNTHETIC,after_cleanup={after_cleanup}"
        )
        assert all(count == 0 for count in after_cleanup.values())


def test_firestore_append_conflict_and_read_back(
    firestore_ledger: FirestoreLedger,
) -> None:
    wire = tool_receipt()
    firestore_ledger.append_artifact(wire)
    firestore_ledger.append_artifact(wire)

    assert firestore_ledger.get_artifact(ARTIFACT_ID) == wire
    assert firestore_ledger.read_back_count("artifacts", run_id=RUN_ID) == 1
    with pytest.raises(ContractError, match="artifact_integrity_failed"):
        firestore_ledger.append_artifact(conflicting_receipt())
    assert firestore_ledger.read_back_count("artifacts", run_id=RUN_ID) == 1


def test_firestore_cas_lease_events_and_failed_write_stability(
    firestore_ledger: FirestoreLedger,
) -> None:
    now = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
    controller = Controller(firestore_ledger)
    created = controller.create_run(
        watch_case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        source_cursors={"clinvar": "42"},
        schedule_epoch="2026-08-22T00:00:00Z",
        data_mode=DataMode.SYNTHETIC,
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
        now=now + timedelta(seconds=1),
    )
    routing = controller.acquire_lease(
        queued.run_id,
        expected_version=2,
        new_epoch=1,
        expires_at=now + timedelta(seconds=5),
        now=now + timedelta(seconds=2),
    )
    watching = controller.transition(
        routing.run_id,
        expected_version=3,
        lease_epoch=1,
        event_code=ScanRunEventCode.ROUTE_VALIDATED,
        now=now + timedelta(seconds=3),
    )

    with pytest.raises(ContractError, match="stale_write_rejected"):
        controller.transition(
            watching.run_id,
            expected_version=3,
            lease_epoch=1,
            event_code=ScanRunEventCode.CANDIDATE_UNKNOWN,
            now=now + timedelta(seconds=2),
        )
    with pytest.raises(ContractError, match="lease_expired"):
        controller.transition(
            watching.run_id,
            expected_version=4,
            lease_epoch=1,
            event_code=ScanRunEventCode.CANDIDATE_UNKNOWN,
            now=now + timedelta(seconds=6),
        )

    assert firestore_ledger.get_scan_run(watching.run_id) == watching
    assert (
        firestore_ledger.read_back_count(
            "scan_run_events", run_id=watching.run_id
        )
        == 4
    )


def test_firestore_rejects_mismatched_transition_atomically(
    firestore_ledger: FirestoreLedger,
) -> None:
    now = datetime(2026, 8, 21, 19, 0, tzinfo=UTC)
    controller = Controller(firestore_ledger)
    created = controller.create_run(
        watch_case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        source_cursors={"clinvar": "43"},
        schedule_epoch="2026-08-22T00:01:00Z",
        data_mode=DataMode.SYNTHETIC,
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
        trace_id="0a651403-8226-4072-9240-344542b0c5fc",
        deadline_at="2026-08-22T00:10:59Z",
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
    pointer_before = firestore_ledger.get_scan_run(routing.run_id)
    events_before = firestore_ledger.read_back_count(
        "scan_run_events", run_id=routing.run_id
    )
    artifacts_before = firestore_ledger.read_back_count(
        "artifacts", run_id=routing.run_id
    )

    with pytest.raises(ContractError, match="contract_transition_invalid"):
        firestore_ledger.transition_with_cas(
            routing.run_id,
            expected_version=routing.version,
            lease_epoch=routing.lease_epoch,
            to_state="ASSESSING",
            event_code=ScanRunEventCode.ROUTE_VALIDATED,
            now=now + timedelta(seconds=3),
        )

    assert firestore_ledger.get_scan_run(routing.run_id) == pointer_before
    assert (
        firestore_ledger.read_back_count(
            "scan_run_events", run_id=routing.run_id
        )
        == events_before
    )
    assert (
        firestore_ledger.read_back_count("artifacts", run_id=routing.run_id)
        == artifacts_before
    )
    events = firestore_ledger.list_scan_run_events(routing.run_id)
    pointer_after = firestore_ledger.get_scan_run(routing.run_id)
    assert pointer_after is not None
    assert pointer_after.state is events[-1].to_state
    assert pointer_after.version == events[-1].sequence
