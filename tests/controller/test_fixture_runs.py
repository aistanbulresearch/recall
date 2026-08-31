from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from recall.demo import parse_fixture_spec, run_fixture
from recall.ledger import InMemoryLedger
from recall.demo.admission import verify_synthetic_privacy_receipt


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.parametrize(
    ("filename", "terminal", "reasons", "tasks", "policy_decisions"),
    [
        ("no_change.json", "NO_ACTION", ["no_candidate_delta"], 0, 1),
        ("audited_change.json", "REVIEW_REQUIRED", ["audited_candidate_delta"], 1, 1),
        (
            "fault_run.json",
            "ABSTAIN",
            ["material_claim_unverified", "tool_authorization_incomplete"],
            0,
            1,
        ),
        ("policy_unavailable.json", "HALTED", ["policy_unavailable"], 0, 0),
    ],
)
def test_fixture_runs_are_driven_by_validated_artifacts(
    filename: str,
    terminal: str,
    reasons: list[str],
    tasks: int,
    policy_decisions: int,
) -> None:
    raw = json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))
    assert raw.get("expected_outcome") is None
    spec = parse_fixture_spec(raw)
    report = run_fixture(
        InMemoryLedger(
            privacy_receipt_verifier=verify_synthetic_privacy_receipt
        ),
        spec,
        execution_id=f"test-{filename}",
        now=datetime(2026, 8, 22, tzinfo=UTC),
    )

    assert report["terminal_state"] == terminal
    assert report["ordered_reason_codes"] == reasons
    assert report["firestore_read_back"]["review_tasks"] == tasks
    assert report["policy_decision_count"] == policy_decisions
    assert report["policy_call_count"] == 1
    assert report["duplicate_create_reused"] is True
    assert report["duplicate_terminal_reused"] is True
    assert report["firestore_read_back"]["watch_cases"] == 1
    assert report["pointer_last_event"]["consistent"] is True
    if tasks:
        assert report["review_task_delivery_states"] == ["DELIVERED"]
        assert report["watch_case_read_back"]["state"] == "AWAITING_HUMAN"
        assert report["watch_case_read_back"]["open_review_task_id"] == report[
            "review_task_ids"
        ][0]
        assert report["watch_case_read_back"]["last_verified_snapshot_id"] is not None
        assert report["watch_case_read_back"]["source_cursors"] != {
            "synthetic-source": "cursor-000"
        }
    elif terminal == "NO_ACTION":
        assert report["watch_case_read_back"]["state"] == "ACTIVE"
        assert report["watch_case_read_back"]["last_verified_snapshot_id"] is not None
        assert report["watch_case_read_back"]["source_cursors"] != {
            "synthetic-source": "cursor-000"
        }
    else:
        assert report["watch_case_read_back"]["last_verified_snapshot_id"] is None
        assert report["watch_case_read_back"]["source_cursors"] == dict(
            spec.source_cursors
        )
