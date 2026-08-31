from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from recall.scheduler.model_cost import (
    DEFAULT_MODEL_COST_POLICY,
    InMemoryModelCostLedger,
    projected_cost_micros,
    validate_request_budget,
)


def test_locked_policy_matches_owner_cap_and_vertex_flash_prices() -> None:
    policy = DEFAULT_MODEL_COST_POLICY

    assert policy.model_id == "gemini-3.7-flash"
    assert policy.location == "global"
    assert policy.input_usd_micros_per_million_tokens == 750_000
    assert policy.output_usd_micros_per_million_tokens == 3_750_000
    assert policy.hard_cap_usd_micros == 75_000_000
    assert len(policy.sha256) == 64


def test_request_budget_is_fail_closed_before_model_invocation() -> None:
    validate_request_budget(b"x" * 16_384, DEFAULT_MODEL_COST_POLICY)

    with pytest.raises(RuntimeError, match="model_request_budget_exceeded"):
        validate_request_budget(b"x" * 16_385, DEFAULT_MODEL_COST_POLICY)


def test_cost_projection_counts_thoughts_as_output() -> None:
    assert projected_cost_micros(
        prompt_tokens=1_000,
        candidate_tokens=100,
        thoughts_tokens=50,
        policy=DEFAULT_MODEL_COST_POLICY,
    ) == 1_313


def test_four_concurrent_workers_cannot_oversubscribe_hard_cap() -> None:
    ledger = InMemoryModelCostLedger(hard_cap_usd_micros=30_000)

    def reserve(index: int) -> str:
        return ledger.reserve(f"turn-{index}", 10_000).state

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(reserve, range(4)))

    assert results.count("RESERVED") == 3
    assert results.count("DENIED") == 1
    snapshot = ledger.snapshot()
    assert snapshot.reserved_usd_micros == 30_000
    assert snapshot.reconciled_usd_micros == 0


def test_reservation_replay_and_reconciliation_are_idempotent() -> None:
    ledger = InMemoryModelCostLedger(hard_cap_usd_micros=30_000)
    first = ledger.reserve("turn-1", 20_000)
    replay = ledger.reserve("turn-1", 20_000)
    ledger.reconcile("turn-1", actual_usd_micros=7_000)
    ledger.reconcile("turn-1", actual_usd_micros=7_000)

    assert first.state == replay.state == "RESERVED"
    assert ledger.snapshot().reserved_usd_micros == 7_000
    assert ledger.snapshot().reconciled_usd_micros == 7_000

    with pytest.raises(ValueError, match="model_cost_reservation_integrity_failed"):
        ledger.reserve("turn-1", 19_999)
    with pytest.raises(ValueError, match="model_cost_reconciliation_integrity_failed"):
        ledger.reconcile("turn-1", actual_usd_micros=7_001)
