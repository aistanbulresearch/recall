from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from recall.contracts import parse_artifact
from recall.ledger.memory import InMemoryLedger
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.scheduler.dayn import DayNScheduler, collection_prefix, preview
from recall.scheduler.entrypoint import execute
from recall.scheduler.manifest import (
    manifest_artifact_id,
    mode_receipt_artifact_id,
    require_single_manifest,
)
from recall.scheduler.preparation import (
    DEFAULT_BUNDLE_PATH,
    LockedPreparationVerifier,
    install_prepared_day,
    load_preparation_bundle,
)


ROOT = Path(__file__).resolve().parents[2]
BUNDLE_SHA = "c460340e75bf186980c8e7a938c5c5e0b4da89599890b2864af7dabdb4ffe841"
SOURCE_COMMIT = "a" * 40
DAY2_NOW = datetime(2026, 8, 26, 16, 1, tzinfo=timezone.utc)


def _bundle():
    return load_preparation_bundle(ROOT, expected_sha256=BUNDLE_SHA)


def _prepared_ledger():
    bundle = _bundle()
    verifier = LockedPreparationVerifier(bundle)
    ledger = InMemoryLedger(privacy_receipt_verifier=verifier)
    install_prepared_day(ledger, bundle, now=DAY2_NOW)
    return ledger, bundle


def test_preparation_bundle_is_hash_bound_complete_and_exact() -> None:
    path = ROOT / DEFAULT_BUNDLE_PATH
    assert hashlib.sha256(path.read_bytes()).hexdigest() == BUNDLE_SHA
    bundle = _bundle()
    assert len(bundle.cases) == 12
    assert len(bundle.replay_observations) == 5
    assert set(bundle.observations_by_vcv) == {
        "VCV002895953.1",
        "VCV002895953.4",
        "VCV002895953.5",
        "VCV000495460.24",
        "VCV000051100.33",
    }


def test_locked_verifier_rejects_mutated_or_unregistered_receipt() -> None:
    bundle = _bundle()
    verifier = LockedPreparationVerifier(bundle)
    receipt = dict(bundle.cases[0].privacy_receipt)
    assert verifier(receipt)
    mutated = copy.deepcopy(receipt)
    mutated["warnings"] = []
    assert not verifier(mutated)


def test_day2_creates_three_then_reuses_without_new_manifest() -> None:
    ledger, bundle = _prepared_ledger()
    scheduler = DayNScheduler(ledger, bundle=bundle, source_commit=SOURCE_COMMIT)
    first = scheduler.trigger(now=DAY2_NOW, previous_manifest=None)
    second = scheduler.trigger(now=DAY2_NOW, previous_manifest=None)
    assert len(first.newly_created_run_ids) == 3
    assert first.reused_run_ids == ()
    assert len(first.authoritative_run_ids) == 3
    assert second.newly_created_run_ids == ()
    assert len(second.reused_run_ids) == 3
    assert second.authoritative_run_ids == first.authoritative_run_ids
    assert ledger.get_artifact(manifest_artifact_id(DAY2_NOW.date())) is not None
    assert ledger.get_artifact(mode_receipt_artifact_id(DAY2_NOW.date())) is not None
    assert ledger.read_back_count("scan_runs") == 3
    assert ledger.read_back_count("scan_run_events") == 3


def test_crash_resume_reconciles_authoritative_count_and_one_manifest() -> None:
    ledger, bundle = _prepared_ledger()
    crashing = DayNScheduler(
        ledger,
        bundle=bundle,
        source_commit=SOURCE_COMMIT,
        fault_after_run_writes=1,
    )
    with pytest.raises(RuntimeError, match="synthetic_fault_after_run_write"):
        crashing.trigger(now=DAY2_NOW, previous_manifest=None)
    assert ledger.read_back_count("scan_runs") == 1
    assert ledger.get_artifact(manifest_artifact_id(DAY2_NOW.date())) is None
    resumed = DayNScheduler(ledger, bundle=bundle, source_commit=SOURCE_COMMIT)
    result = resumed.trigger(now=DAY2_NOW, previous_manifest=None)
    assert len(result.authoritative_run_ids) == 3
    assert len(result.newly_created_run_ids) == 2
    assert len(result.reused_run_ids) == 1
    third = resumed.trigger(now=DAY2_NOW, previous_manifest=None)
    assert len(third.reused_run_ids) == 3
    manifests = [
        item
        for item in ledger.list_by_run(
            parse_artifact(
                ledger.get_artifact(manifest_artifact_id(DAY2_NOW.date())),
                authorized_producers=PRODUCER_REGISTRY,
            ).run_id
        )
        if item["schema_name"] == "CohortDayManifest"
    ]
    assert len(manifests) == 1


def test_manifest_history_shape_and_manual_day1_boundary() -> None:
    ledger, bundle = _prepared_ledger()
    result = DayNScheduler(
        ledger, bundle=bundle, source_commit=SOURCE_COMMIT
    ).trigger(now=DAY2_NOW, previous_manifest=None)
    manifest = ledger.get_artifact(result.manifest_artifact_id)
    assert manifest is not None
    artifact = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
    history = artifact.payload.execution_history
    assert tuple(history[0]) == (
        "day_index",
        "executed_at",
        "selected_for_date",
        "runs_created",
        "runs_predicted",
    )
    assert [item["selected_for_date"] for item in history] == [
        "2026-08-25",
        "2026-08-26",
    ]
    assert artifact.payload.managed_history_starts_at_day_index == 2
    assert history[-1]["runs_created"] == 3
    assert history[-1]["runs_predicted"] == 3
    assert history[-1]["executed_at"] == "2026-08-26T16:01:00Z"
    assert artifact.created_at == "2026-08-26T16:01:00Z"
    assert artifact.payload.scheduled_for == "2026-08-26T16:00:00Z"


def test_preview_constructs_no_ledger_and_day1_recurring_is_rejected() -> None:
    calls = 0

    def forbidden_factory(**_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("ledger factory must not run during preview")

    value = execute(
        ["--preview-date", "2026-08-26"],
        environment={"RECALL_COHORT_PREPARATION_SHA256": BUNDLE_SHA},
        ledger_factory=forbidden_factory,
        repo_root=ROOT,
    )
    assert value["writes"] == 0
    assert value["runs_predicted"] == 3
    assert calls == 0
    ledger, bundle = _prepared_ledger()
    with pytest.raises(RuntimeError, match="frozen_day1_recurring_execution_forbidden"):
        DayNScheduler(ledger, bundle=bundle, source_commit=SOURCE_COMMIT).trigger(
            now=datetime(2026, 8, 25, 16, 1, tzinfo=timezone.utc),
            previous_manifest=None,
        )


def test_daily_prefix_is_date_bound() -> None:
    assert collection_prefix(DAY2_NOW.date()) == "dev_recall_m2_cohort_20260826_"


def test_bundle_requires_exactly_one_cohort_manifest() -> None:
    manifest = {"schema_name": "CohortDayManifest", "artifact_id": "one"}
    assert require_single_manifest([manifest]) is manifest
    with pytest.raises(RuntimeError, match="cardinality_invalid:0"):
        require_single_manifest([])
    with pytest.raises(RuntimeError, match="cardinality_invalid:2"):
        require_single_manifest([manifest, dict(manifest)])


def test_missing_data_mode_receipt_fails_closed() -> None:
    class DroppingLedger(InMemoryLedger):
        def append_artifact(self, value):
            if value["schema_name"] == "DataModeReceipt":
                return parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
            return super().append_artifact(value)

    bundle = _bundle()
    ledger = DroppingLedger(privacy_receipt_verifier=LockedPreparationVerifier(bundle))
    install_prepared_day(ledger, bundle, now=DAY2_NOW)
    with pytest.raises(RuntimeError, match="cohort_data_mode_receipt_missing"):
        DayNScheduler(ledger, bundle=bundle, source_commit=SOURCE_COMMIT).trigger(
            now=DAY2_NOW, previous_manifest=None
        )
