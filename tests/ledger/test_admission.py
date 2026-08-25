from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from recall.contracts import ContractError, DataMode
from recall.controller import Controller
from recall.ledger import InMemoryLedger

from tests.admission import (
    admit_watch_case,
    cloud_payload,
    in_memory_ledger,
    privacy_receipt,
)
from tests.controller.test_run_coordination import BUDGET, CASE_ID, TRACE_ID


NOW = datetime(2026, 8, 25, 15, 0, tzinfo=UTC)


def test_watch_case_rejects_unverified_receipt_without_case_write() -> None:
    ledger = InMemoryLedger()
    controller = Controller(ledger)
    payload = cloud_payload(CASE_ID)
    receipt = privacy_receipt(CASE_ID, now=NOW, payload=payload)
    ledger.append_artifact(receipt)

    with pytest.raises(ContractError, match="privacy_not_accepted"):
        controller.create_watch_case(
            watch_case_id=CASE_ID,
            tenant_id="synthetic-lab",
            region="us-central1",
            privacy_receipt_id=str(receipt["artifact_id"]),
            cloud_bound_payload=payload,
            data_mode=DataMode.SYNTHETIC,
            source_cursors={"synthetic-source": "cursor-001"},
            pending_observation_hashes=(),
            next_scan_at="2026-08-25T15:00:00Z",
            now=NOW,
        )

    assert ledger.read_back_count("artifacts") == 1
    assert ledger.read_back_count("watch_cases") == 0


def test_watch_case_rejects_payload_hash_mismatch_without_case_write() -> None:
    ledger = in_memory_ledger()
    controller = Controller(ledger)
    payload = cloud_payload(CASE_ID)
    receipt = privacy_receipt(CASE_ID, now=NOW, payload=payload)
    ledger.append_artifact(receipt)
    changed = cloud_payload(CASE_ID)
    changed["variant"] = {**changed["variant"], "gene": "TP53"}

    with pytest.raises(ContractError, match="privacy_not_accepted"):
        controller.create_watch_case(
            watch_case_id=CASE_ID,
            tenant_id="synthetic-lab",
            region="us-central1",
            privacy_receipt_id=str(receipt["artifact_id"]),
            cloud_bound_payload=changed,
            data_mode=DataMode.SYNTHETIC,
            source_cursors={"synthetic-source": "cursor-001"},
            pending_observation_hashes=(),
            next_scan_at="2026-08-25T15:00:00Z",
            now=NOW,
        )

    assert ledger.read_back_count("artifacts") == 1
    assert ledger.read_back_count("watch_cases") == 0


def test_future_case_and_stale_version_make_no_scan_run_write() -> None:
    ledger = in_memory_ledger()
    controller = Controller(ledger)
    admitted, receipt, _payload = admit_watch_case(
        ledger,
        controller,
        case_id=CASE_ID,
        now=NOW,
        next_scan_at="2026-08-26T15:00:00Z",
        source_cursors={"synthetic-source": "cursor-001"},
    )
    before_artifacts = ledger.read_back_count("artifacts")

    with pytest.raises(ContractError, match="contract_transition_invalid"):
        controller.create_run(
            watch_case_id=CASE_ID,
            source_cursors={"synthetic-source": "cursor-001"},
            schedule_epoch="2026-08-26T15:00:00Z",
            data_mode=DataMode.SYNTHETIC,
            privacy_receipt_id=str(receipt["artifact_id"]),
            expected_watch_case_version=admitted.record.version,
            triggered_at=NOW,
            budget_snapshot=BUDGET,
            trace_id=TRACE_ID,
            deadline_at="2026-08-26T15:09:59Z",
            now=NOW,
        )

    with pytest.raises(ContractError, match="stale_write_rejected"):
        controller.create_run(
            watch_case_id=CASE_ID,
            source_cursors={"synthetic-source": "cursor-001"},
            schedule_epoch="2026-08-26T15:00:00Z",
            data_mode=DataMode.SYNTHETIC,
            privacy_receipt_id=str(receipt["artifact_id"]),
            expected_watch_case_version=admitted.record.version + 1,
            triggered_at=NOW + timedelta(days=1),
            budget_snapshot=BUDGET,
            trace_id=TRACE_ID,
            deadline_at="2026-08-26T15:09:59Z",
            now=NOW,
        )

    assert ledger.read_back_count("artifacts") == before_artifacts
    assert ledger.read_back_count("scan_runs") == 0
    assert ledger.read_back_count("scan_run_events") == 0


def test_wrong_mode_and_cursor_drift_make_no_scan_run_write() -> None:
    ledger = in_memory_ledger()
    controller = Controller(ledger)
    admitted, receipt, _payload = admit_watch_case(
        ledger,
        controller,
        case_id=CASE_ID,
        now=NOW,
        next_scan_at="2026-08-25T15:00:00Z",
        source_cursors={"synthetic-source": "cursor-001"},
    )
    before = ledger.read_back_count("artifacts")
    common = {
        "watch_case_id": CASE_ID,
        "schedule_epoch": "2026-08-25T15:00:00Z",
        "privacy_receipt_id": str(receipt["artifact_id"]),
        "expected_watch_case_version": admitted.record.version,
        "triggered_at": NOW,
        "budget_snapshot": BUDGET,
        "trace_id": TRACE_ID,
        "deadline_at": "2026-08-25T15:09:59Z",
        "now": NOW,
    }
    with pytest.raises(ContractError, match="privacy_not_accepted"):
        controller.create_run(
            **common,
            source_cursors={"synthetic-source": "cursor-001"},
            data_mode=DataMode.CAPTURED_REPLAY,
        )
    with pytest.raises(ContractError, match="stale_write_rejected"):
        controller.create_run(
            **common,
            source_cursors={"synthetic-source": "cursor-drift"},
            data_mode=DataMode.SYNTHETIC,
        )

    assert ledger.read_back_count("artifacts") == before
    assert ledger.read_back_count("scan_runs") == 0
    assert ledger.read_back_count("scan_run_events") == 0
