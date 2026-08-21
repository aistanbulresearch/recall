from __future__ import annotations

from recall.controller.hashes import (
    repeated_state_hash,
    review_deduplication_key,
    scan_idempotency_key,
)


def test_scan_idempotency_key_is_order_independent_for_source_cursors() -> None:
    first = scan_idempotency_key(
        watch_case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        source_cursors={"clinvar": "42", "pubmed": "17"},
        schedule_epoch="2026-08-22T00:00:00Z",
        data_mode="SYNTHETIC",
    )
    second = scan_idempotency_key(
        watch_case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        source_cursors={"pubmed": "17", "clinvar": "42"},
        schedule_epoch="2026-08-22T00:00:00Z",
        data_mode="SYNTHETIC",
    )

    assert first == second
    assert len(first) == 64


def test_review_deduplication_key_uses_frozen_three_inputs() -> None:
    key = review_deduplication_key(
        case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        policy_decision_id="c70f31c8-dc41-46d8-b9fe-5ea52340788a",
        verified_delta_hash="1" * 64,
    )

    assert key == review_deduplication_key(
        case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        policy_decision_id="c70f31c8-dc41-46d8-b9fe-5ea52340788a",
        verified_delta_hash="1" * 64,
    )
    assert len(key) == 64


def test_repeated_state_hash_excludes_attempt_lease_and_timestamp_fields() -> None:
    stable = {
        "source_cursors": {"clinvar": "42"},
        "last_verified_snapshot_id": "eb78d84a-640e-446b-8cf7-d735a97f2f1b",
        "pending_observation_hashes": ["2" * 64],
        "latest_artifact_hashes": ["3" * 64],
        "attempt": 1,
        "lease_epoch": 4,
        "lease_expires_at": "2026-08-22T00:01:00Z",
        "updated_at": "2026-08-22T00:00:00Z",
    }
    retry = {
        **stable,
        "attempt": 2,
        "lease_epoch": 5,
        "lease_expires_at": "2026-08-22T00:02:00Z",
        "updated_at": "2026-08-22T00:01:00Z",
    }

    assert repeated_state_hash(stable) == repeated_state_hash(retry)
