from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Lock
from time import monotonic
from types import SimpleNamespace

import pytest

from recall.scheduler.compressed_batch import (
    BATCH_MAX_WORKERS,
    BatchExecutionResult,
    WritePhaseDeadlineExceeded,
    _joined_parallel,
)
from recall.scheduler.compressed_cohort import cases_for_cycle
from recall.scheduler.compressed_plan import load_compressed_plan
from recall.scheduler.compressed_preparation import (
    DEFAULT_COMPRESSED_BUNDLE_PATH,
    load_compressed_bundle,
)
from recall.scheduler.entrypoint import execute


ROOT = Path(__file__).resolve().parents[2]
IMAGE_DIGEST = "sha256:" + "a" * 64


def _loaded():
    plan = load_compressed_plan(ROOT)
    sha = hashlib.sha256((ROOT / DEFAULT_COMPRESSED_BUNDLE_PATH).read_bytes()).hexdigest()
    bundle = load_compressed_bundle(ROOT, expected_sha256=sha, plan=plan)
    return plan, bundle, sha


def test_parallel_failure_joins_all_started_workers_before_raising() -> None:
    release = Event()
    lock = Lock()
    active = 0
    completed = 0

    def operation(value: int) -> int:
        nonlocal active, completed
        with lock:
            active += 1
        try:
            if value == 0:
                release.set()
                raise RuntimeError("injected")
            release.wait(timeout=1)
            return value
        finally:
            with lock:
                active -= 1
                completed += 1

    with pytest.raises(RuntimeError, match="batch_failed"):
        _joined_parallel(tuple(range(64)), operation, failure_code="batch_failed")
    assert active == 0
    assert completed >= 1


def test_parallel_deadline_returns_without_waiting_for_hung_backend() -> None:
    release = Event()

    def operation(_value: int) -> int:
        release.wait(timeout=2)
        return 1

    started = monotonic()
    try:
        with pytest.raises(
            WritePhaseDeadlineExceeded,
            match="compressed_write_phase_deadline_exceeded",
        ):
            _joined_parallel(
                (1,),
                operation,
                failure_code="must_not_wrap",
                deadline_at=datetime.now(UTC) + timedelta(milliseconds=50),
                clock=lambda: datetime.now(UTC),
            )
        assert monotonic() - started < 1
    finally:
        release.set()


def test_worker_deadline_exception_is_not_wrapped_as_generic_batch_failure() -> None:
    def operation(_value: int) -> int:
        raise WritePhaseDeadlineExceeded(
            "compressed_write_phase_deadline_exceeded"
        )

    with pytest.raises(
        WritePhaseDeadlineExceeded,
        match="compressed_write_phase_deadline_exceeded",
    ):
        _joined_parallel((1,), operation, failure_code="must_not_wrap")


def test_batch_metrics_are_additive_and_count_committed_case_documents() -> None:
    outcomes = tuple(
        SimpleNamespace(created=index < 18) for index in range(20)
    )
    result = BatchExecutionResult(
        outcomes=outcomes,  # type: ignore[arg-type]
        started_at="2026-08-27T09:00:00Z",
        completed_at="2026-08-27T09:00:01Z",
        worker_elapsed_ms=700,
        readback_elapsed_ms=300,
        total_elapsed_ms=1000,
        persistence_surface="LIVE_FIRESTORE",
    )
    metrics = result.metrics()
    assert metrics["batch_max_workers"] == 20
    assert metrics["committed_case_documents"] == 54
    assert metrics["effective_write_millis_per_case"] == 50
    counts = metrics["ledger_operation_counts"]
    assert counts["create_run_transaction_calls"] == 18
    assert counts["exact_run_event_queries"] == 20
    assert counts["aggregate_count_reads"] == 2


def test_preview_declares_ramp_and_final_without_constructing_ledger() -> None:
    plan, bundle, bundle_sha = _loaded()

    def forbidden(**_kwargs):
        raise AssertionError("preview_must_not_construct_ledger")

    result = execute(
        ["--preview-date", "2026-08-31"],
        environment={
            "RECALL_SCHEDULER_MODE": "COMPRESSED_V3",
            "RECALL_COMPRESSED_PREPARATION_SHA256": bundle_sha,
            "RECALL_SOURCE_COMMIT": bundle.source_commit,
            "RECALL_IMAGE_DIGEST": IMAGE_DIGEST,
        },
        ledger_factory=forbidden,
        repo_root=ROOT,
    )
    assert result["writes"] == 0
    assert result["cycle_id"] == "c6"
    assert result["runs_predicted"] == 456
    assert result["write_path"] == "FIRESTORE_BATCH_V1"
    assert result["batch_max_workers"] == BATCH_MAX_WORKERS
    assert result["epoch_label"] == "PLAN6_FINAL_456_REASSESSMENT_PROVISIONAL"
    assert result["activation"] == "PROVISIONAL_R1_GATED"
    assert result["execution_profile"] == "FULL_AUDIT_V1"
    assert result["evaluation_role"] == "PORTFOLIO_REASSESSMENT"
    assert "actual_reused_runs" in result["parity_indicator_fields"]
    assert "epoch_parity_match" in result["parity_indicator_fields"]
    assert "fresh_write_parity_match" in result["parity_indicator_fields"]
    assert result["write_timeout_seconds"] == plan.by_id("c6").write_timeout_seconds
    assert result["agent_timeout_seconds"] == plan.by_id("c6").agent_timeout_seconds
    assert result["authoritative_end_to_end_deadline"] == (
        plan.by_id("c6").end_to_end_deadline.isoformat().replace("+00:00", "Z")
    )
    assert len(result["selected_case_ids"]) == 456
    assert len(result["excluded_case_ids"]) == 6
    assert result["plan_sha256"] == plan.sha256


def test_ramp_subsets_and_final_use_identical_write_path() -> None:
    plan, _bundle, _sha = _loaded()
    ramp_sets = [
        {item.case_id for item in cases_for_cycle(plan.by_id(cycle_id))}
        for cycle_id in ("c3", "c4", "c5")
    ]
    assert [len(item) for item in ramp_sets] == [20, 80, 200]
    assert ramp_sets[0].isdisjoint(ramp_sets[1])
    assert ramp_sets[0].isdisjoint(ramp_sets[2])
    assert ramp_sets[1].isdisjoint(ramp_sets[2])
    final = {item.case_id for item in cases_for_cycle(plan.by_id("c6"))}
    assert len(final) == 456
    assert set.union(*ramp_sets).issubset(final)
    assert {item.write_path for item in plan.cycles[2:]} == {"FIRESTORE_BATCH_V1"}
