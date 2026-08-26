from __future__ import annotations

import copy
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from recall.contracts import content_hash, parse_artifact
from recall.ledger.memory import InMemoryLedger
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.scheduler.dayn import (
    DayNScheduler,
    _real_selected_date,
    collection_prefix,
    preview,
)
from recall.scheduler.entrypoint import execute
from recall.scheduler.manifest import (
    manifest_artifact_id,
    mode_receipt_artifact_id,
    require_single_manifest,
)
from recall.scheduler.history import history_receipt_artifact_id
from recall.scheduler.continuation import (
    MissingCohortDay,
    failure_receipt_artifact_id,
    validate_persisted_failure_lineage,
)
from recall.scheduler.preparation import (
    DEFAULT_BUNDLE_PATH,
    LockedPreparationVerifier,
    install_prepared_day,
    load_preparation_bundle,
)


ROOT = Path(__file__).resolve().parents[2]
BUNDLE_SHA = "c460340e75bf186980c8e7a938c5c5e0b4da89599890b2864af7dabdb4ffe841"
SOURCE_COMMIT = "c65ee3d55524caf1d2d9d697c9bff712e35bca82"
IMAGE_DIGEST = "sha256:" + "b" * 64
DAY2_NOW = datetime(2026, 8, 26, 16, 1, tzinfo=timezone.utc)
DAY3_NOW = datetime(2026, 8, 27, 16, 1, tzinfo=timezone.utc)
DAY4_NOW = datetime(2026, 8, 28, 16, 1, tzinfo=timezone.utc)


def _bundle():
    return load_preparation_bundle(ROOT, expected_sha256=BUNDLE_SHA)


def _prepared_ledger(now: datetime = DAY2_NOW):
    bundle = _bundle()
    verifier = LockedPreparationVerifier(bundle)
    ledger = InMemoryLedger(privacy_receipt_verifier=verifier)
    install_prepared_day(ledger, bundle, now=now)
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
    scheduler = DayNScheduler(
        ledger,
        bundle=bundle,
        source_commit=SOURCE_COMMIT,
        image_digest=IMAGE_DIGEST,
    )
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
        image_digest=IMAGE_DIGEST,
        fault_after_run_writes=1,
    )
    with pytest.raises(RuntimeError, match="synthetic_fault_after_run_write"):
        crashing.trigger(now=DAY2_NOW, previous_manifest=None)
    assert ledger.read_back_count("scan_runs") == 1
    assert ledger.get_artifact(manifest_artifact_id(DAY2_NOW.date())) is None
    resumed = DayNScheduler(
        ledger,
        bundle=bundle,
        source_commit=SOURCE_COMMIT,
        image_digest=IMAGE_DIGEST,
    )
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
        ledger,
        bundle=bundle,
        source_commit=SOURCE_COMMIT,
        image_digest=IMAGE_DIGEST,
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
        "execution_status",
        "failure_receipt_id",
    )
    assert [item["selected_for_date"] for item in history] == [
        "2026-08-25",
        "2026-08-26",
    ]
    assert history[0]["executed_at"] == "2026-08-25T15:00:03.280432Z"
    assert history_receipt_artifact_id() in artifact.input_artifact_ids
    assert artifact.payload.managed_history_starts_at_day_index == 2
    assert history[-1]["runs_created"] == 3
    assert history[-1]["runs_predicted"] == 3
    assert history[-1]["executed_at"] == "2026-08-26T16:01:00Z"
    assert history[-1]["execution_status"] == "COMPLETE"
    assert history[-1]["failure_receipt_id"] is None
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
        environment={
            "RECALL_SCHEDULER_MODE": "LEGACY_DAYN",
            "RECALL_COHORT_PREPARATION_SHA256": BUNDLE_SHA,
            "RECALL_SOURCE_COMMIT": SOURCE_COMMIT,
            "RECALL_IMAGE_DIGEST": IMAGE_DIGEST,
        },
        ledger_factory=forbidden_factory,
        repo_root=ROOT,
    )
    assert value["writes"] == 0
    assert value["runs_predicted"] == 3
    assert value["source_commit"] == SOURCE_COMMIT
    assert value["image_digest"] == IMAGE_DIGEST
    assert calls == 0
    ledger, bundle = _prepared_ledger()
    with pytest.raises(RuntimeError, match="frozen_day1_recurring_execution_forbidden"):
        DayNScheduler(
            ledger,
            bundle=bundle,
            source_commit=SOURCE_COMMIT,
            image_digest=IMAGE_DIGEST,
        ).trigger(
            now=datetime(2026, 8, 25, 16, 1, tzinfo=timezone.utc),
            previous_manifest=None,
        )


def test_daily_prefix_is_date_bound() -> None:
    assert collection_prefix(DAY2_NOW.date()) == "dev_recall_m2_cohort_20260826_"


def test_execution_at_window_end_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="cohort_execution_outside_daily_window"):
        _real_selected_date(
            datetime(2026, 8, 26, 16, 10, tzinfo=timezone.utc)
        )


def test_missing_day_emits_typed_receipt_and_incomplete_manifest() -> None:
    ledger, bundle = _prepared_ledger(DAY3_NOW)
    result = DayNScheduler(
        ledger,
        bundle=bundle,
        source_commit=SOURCE_COMMIT,
        image_digest=IMAGE_DIGEST,
    ).trigger(
        now=DAY3_NOW,
        previous_manifest=None,
        missing_days=(MissingCohortDay(date(2026, 8, 26)),),
    )
    receipt_id = failure_receipt_artifact_id(date(2026, 8, 26))
    receipt = ledger.get_artifact(receipt_id)
    assert receipt is not None
    parsed_receipt = parse_artifact(receipt, authorized_producers=PRODUCER_REGISTRY)
    assert parsed_receipt.schema_name == "CohortDayFailureReceipt"
    assert parsed_receipt.payload.detected_at == "2026-08-27T16:01:00Z"
    manifest = parse_artifact(
        ledger.get_artifact(result.manifest_artifact_id),
        authorized_producers=PRODUCER_REGISTRY,
    )
    assert manifest.schema_version == "2.1.0"
    assert manifest.status.value == "INCOMPLETE"
    assert [row["execution_status"] for row in manifest.payload.execution_history] == [
        "COMPLETE",
        "INCOMPLETE",
        "COMPLETE",
    ]
    assert manifest.payload.execution_history[1]["executed_at"] is None
    assert manifest.payload.execution_history[1]["failure_receipt_id"] == receipt_id
    assert receipt_id in manifest.input_artifact_ids


def test_failure_receipt_retry_reuses_first_detection_bytes() -> None:
    ledger, bundle = _prepared_ledger(DAY3_NOW)
    scheduler = DayNScheduler(
        ledger,
        bundle=bundle,
        source_commit=SOURCE_COMMIT,
        image_digest=IMAGE_DIGEST,
    )
    missing = (MissingCohortDay(date(2026, 8, 26)),)
    scheduler.trigger(now=DAY3_NOW, previous_manifest=None, missing_days=missing)
    receipt_id = failure_receipt_artifact_id(date(2026, 8, 26))
    first = ledger.get_artifact(receipt_id)
    scheduler.trigger(
        now=datetime(2026, 8, 27, 16, 2, tzinfo=timezone.utc),
        previous_manifest=None,
        missing_days=missing,
    )
    assert ledger.get_artifact(receipt_id) == first


def test_retry_with_changed_gap_context_refuses_before_new_writes() -> None:
    ledger, bundle = _prepared_ledger(DAY3_NOW)
    scheduler = DayNScheduler(
        ledger,
        bundle=bundle,
        source_commit=SOURCE_COMMIT,
        image_digest=IMAGE_DIGEST,
    )
    scheduler.trigger(
        now=DAY3_NOW,
        previous_manifest=None,
        missing_days=(MissingCohortDay(date(2026, 8, 26)),),
    )
    before_artifacts = ledger.read_back_count("artifacts")
    before_runs = ledger.read_back_count("scan_runs")
    with pytest.raises(RuntimeError, match="cohort_manifest_context_mismatch"):
        scheduler.trigger(
            now=datetime(2026, 8, 27, 16, 2, tzinfo=timezone.utc),
            previous_manifest=None,
            missing_days=(),
        )
    assert ledger.read_back_count("artifacts") == before_artifacts
    assert ledger.read_back_count("scan_runs") == before_runs


def test_failure_receipt_append_failure_precedes_scan_run_writes() -> None:
    class DroppingLedger(InMemoryLedger):
        def append_artifact(self, value):
            if value["schema_name"] == "CohortDayFailureReceipt":
                return parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
            return super().append_artifact(value)

    bundle = _bundle()
    ledger = DroppingLedger(
        privacy_receipt_verifier=LockedPreparationVerifier(bundle)
    )
    install_prepared_day(ledger, bundle, now=DAY3_NOW)
    with pytest.raises(RuntimeError, match="cohort_failure_receipt_missing"):
        DayNScheduler(
            ledger,
            bundle=bundle,
            source_commit=SOURCE_COMMIT,
            image_digest=IMAGE_DIGEST,
        ).trigger(
            now=DAY3_NOW,
            previous_manifest=None,
            missing_days=(MissingCohortDay(date(2026, 8, 26)),),
        )
    assert ledger.read_back_count("scan_runs") == 0
    assert ledger.read_back_count("scan_run_events") == 0
    assert ledger.get_artifact(manifest_artifact_id(DAY3_NOW.date())) is None


def test_day3_reads_committed_v20_day2_and_emits_v21() -> None:
    previous = json.loads(
        (
            ROOT
            / "artifacts/evidence/cohort-manifest-example/day2-manifest.v2.0.legacy.json"
        ).read_text(encoding="utf-8")
    )
    ledger, bundle = _prepared_ledger(DAY3_NOW)
    result = DayNScheduler(
        ledger,
        bundle=bundle,
        source_commit=SOURCE_COMMIT,
        image_digest=IMAGE_DIGEST,
    ).trigger(now=DAY3_NOW, previous_manifest=previous)
    manifest = parse_artifact(
        ledger.get_artifact(result.manifest_artifact_id),
        authorized_producers=PRODUCER_REGISTRY,
    )
    assert manifest.schema_version == "2.1.0"
    assert manifest.payload.previous_manifest_id == previous["artifact_id"]
    assert [row["execution_status"] for row in manifest.payload.execution_history] == [
        "COMPLETE",
        "COMPLETE",
        "COMPLETE",
    ]
    assert result.failure_receipt_ids == ()


def test_multiple_missing_days_emit_ordered_receipts_and_history() -> None:
    now = datetime(2026, 8, 28, 16, 1, tzinfo=timezone.utc)
    ledger, bundle = _prepared_ledger(now)
    result = DayNScheduler(
        ledger,
        bundle=bundle,
        source_commit=SOURCE_COMMIT,
        image_digest=IMAGE_DIGEST,
    ).trigger(
        now=now,
        previous_manifest=None,
        missing_days=(
            MissingCohortDay(date(2026, 8, 27)),
            MissingCohortDay(date(2026, 8, 26)),
        ),
    )
    expected_ids = tuple(
        sorted(
            failure_receipt_artifact_id(value)
            for value in (date(2026, 8, 26), date(2026, 8, 27))
        )
    )
    assert result.failure_receipt_ids == expected_ids
    manifest = parse_artifact(
        ledger.get_artifact(result.manifest_artifact_id),
        authorized_producers=PRODUCER_REGISTRY,
    )
    assert [row["day_index"] for row in manifest.payload.execution_history] == [
        1,
        2,
        3,
        4,
    ]
    assert [row["execution_status"] for row in manifest.payload.execution_history] == [
        "COMPLETE",
        "INCOMPLETE",
        "INCOMPLETE",
        "COMPLETE",
    ]
    assert manifest.payload.cumulative["daily_cycles"] == 2
    assert manifest.payload.cumulative["distinct_execution_dates"] == 2


def test_day4_inherits_day3_incomplete_lineage_transitively() -> None:
    day3_ledger, bundle = _prepared_ledger(DAY3_NOW)
    day3 = DayNScheduler(
        day3_ledger,
        bundle=bundle,
        source_commit=SOURCE_COMMIT,
        image_digest=IMAGE_DIGEST,
    ).trigger(
        now=DAY3_NOW,
        previous_manifest=None,
        missing_days=(MissingCohortDay(date(2026, 8, 26)),),
    )
    day3_manifest = day3_ledger.get_artifact(day3.manifest_artifact_id)
    assert day3_manifest is not None
    day4_now = datetime(2026, 8, 28, 16, 1, tzinfo=timezone.utc)
    day4_ledger, _ = _prepared_ledger(day4_now)
    day4 = DayNScheduler(
        day4_ledger,
        bundle=bundle,
        source_commit=SOURCE_COMMIT,
        image_digest=IMAGE_DIGEST,
    ).trigger(now=day4_now, previous_manifest=day3_manifest)
    manifest = parse_artifact(
        day4_ledger.get_artifact(day4.manifest_artifact_id),
        authorized_producers=PRODUCER_REGISTRY,
    )
    inherited_id = failure_receipt_artifact_id(date(2026, 8, 26))
    assert inherited_id in manifest.input_artifact_ids
    assert inherited_id in day4.failure_receipt_ids


def test_dangling_inherited_receipt_produces_zero_current_writes() -> None:
    day3_ledger, bundle = _prepared_ledger(DAY3_NOW)
    day3 = DayNScheduler(
        day3_ledger,
        bundle=bundle,
        source_commit=SOURCE_COMMIT,
        image_digest=IMAGE_DIGEST,
    ).trigger(
        now=DAY3_NOW,
        previous_manifest=None,
        missing_days=(MissingCohortDay(DAY2_NOW.date()),),
    )
    receipt_id = failure_receipt_artifact_id(DAY2_NOW.date())
    day3_ledger._artifacts.pop(receipt_id)  # type: ignore[attr-defined]
    current, _ = _prepared_ledger(DAY4_NOW)
    before = _scheduler_counts(current)

    def factory(*, collection_prefix, **_kwargs):
        if collection_prefix.endswith("20260828_"):
            return current
        if collection_prefix.endswith("20260827_"):
            return day3_ledger
        raise AssertionError(collection_prefix)

    with pytest.raises(
        RuntimeError, match="cohort_failure_receipt_lineage_invalid"
    ):
        execute(
            [],
            environment=_entrypoint_environment(),
            now_factory=lambda: DAY4_NOW,
            ledger_factory=factory,
            repo_root=ROOT,
        )
    assert day3_ledger.get_artifact(day3.manifest_artifact_id) is not None
    assert _scheduler_counts(current) == before


def test_wrong_predecessor_id_produces_zero_current_writes() -> None:
    day2_ledger, bundle = _prepared_ledger(DAY2_NOW)
    day2 = DayNScheduler(
        day2_ledger,
        bundle=bundle,
        source_commit=SOURCE_COMMIT,
        image_digest=IMAGE_DIGEST,
    ).trigger(now=DAY2_NOW, previous_manifest=None)
    day2_manifest = day2_ledger.get_artifact(day2.manifest_artifact_id)
    assert day2_manifest is not None
    day3_ledger, _ = _prepared_ledger(DAY3_NOW)
    day3 = DayNScheduler(
        day3_ledger,
        bundle=bundle,
        source_commit=SOURCE_COMMIT,
        image_digest=IMAGE_DIGEST,
    ).trigger(now=DAY3_NOW, previous_manifest=day2_manifest)
    day3_manifest = copy.deepcopy(
        day3_ledger.get_artifact(day3.manifest_artifact_id)
    )
    assert day3_manifest is not None
    wrong_id = "00000000-0000-4000-8000-000000000001"
    day3_manifest["previous_manifest_id"] = wrong_id
    inputs = set(day3_manifest["input_artifact_ids"])
    inputs.remove(day2.manifest_artifact_id)
    inputs.add(wrong_id)
    day3_manifest["input_artifact_ids"] = sorted(inputs)
    day3_manifest["content_hash"] = content_hash(day3_manifest)
    day3_ledger._artifacts[day3.manifest_artifact_id] = day3_manifest  # type: ignore[attr-defined]
    current, _ = _prepared_ledger(DAY4_NOW)
    before = _scheduler_counts(current)

    def factory(*, collection_prefix, **_kwargs):
        if collection_prefix.endswith("20260828_"):
            return current
        if collection_prefix.endswith("20260827_"):
            return day3_ledger
        if collection_prefix.endswith("20260826_"):
            return day2_ledger
        raise AssertionError(collection_prefix)

    with pytest.raises(RuntimeError, match="cohort_manifest_predecessor_invalid"):
        execute(
            [],
            environment=_entrypoint_environment(),
            now_factory=lambda: DAY4_NOW,
            ledger_factory=factory,
            repo_root=ROOT,
        )
    assert _scheduler_counts(current) == before


def test_missing_current_failure_receipt_breaks_lineage_validation() -> None:
    ledger, bundle = _prepared_ledger(DAY3_NOW)
    result = DayNScheduler(
        ledger,
        bundle=bundle,
        source_commit=SOURCE_COMMIT,
        image_digest=IMAGE_DIGEST,
    ).trigger(
        now=DAY3_NOW,
        previous_manifest=None,
        missing_days=(MissingCohortDay(date(2026, 8, 26)),),
    )
    manifest = ledger.get_artifact(result.manifest_artifact_id)
    assert manifest is not None
    receipt_id = failure_receipt_artifact_id(date(2026, 8, 26))
    ledger._artifacts.pop(receipt_id)  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError, match="cohort_failure_receipt_lineage_invalid"):
        validate_persisted_failure_lineage(
            ledger,
            manifest,
            previous_manifest=None,
        )


def _scheduler_counts(ledger: InMemoryLedger) -> tuple[int, int, int]:
    return (
        ledger.read_back_count("scan_runs"),
        ledger.read_back_count("scan_run_events"),
        ledger.read_back_count("artifacts"),
    )


def _entrypoint_environment() -> dict[str, str]:
    return {
        "RECALL_SCHEDULER_MODE": "LEGACY_DAYN",
        "RECALL_COHORT_PREPARATION_SHA256": BUNDLE_SHA,
        "RECALL_SOURCE_COMMIT": SOURCE_COMMIT,
        "RECALL_IMAGE_DIGEST": IMAGE_DIGEST,
        "RECALL_EXPECTED_PROJECT_SHA256": "c" * 64,
    }


@pytest.mark.parametrize("mode", ["partial", "backend_error"])
def test_prior_day_failure_produces_zero_current_scheduler_writes(mode) -> None:
    current, _bundle_value = _prepared_ledger(DAY3_NOW)
    before_runs = current.read_back_count("scan_runs")
    before_events = current.read_back_count("scan_run_events")
    before_artifacts = current.read_back_count("artifacts")

    class PriorLedger:
        def get_artifact(self, _artifact_id):
            if mode == "backend_error":
                raise OSError("prior-ledger-read-failed")
            return None

        def read_back_count(self, collection):
            return 1 if collection == "scan_runs" else 0

    prior = PriorLedger()

    def factory(*, collection_prefix, **_kwargs):
        if collection_prefix.endswith("20260827_"):
            return current
        if collection_prefix.endswith("20260826_"):
            return prior
        raise AssertionError(collection_prefix)

    reason = (
        "prior-ledger-read-failed"
        if mode == "backend_error"
        else "previous_cohort_day_partial_state"
    )
    with pytest.raises((OSError, RuntimeError), match=reason):
        execute(
            [],
            environment={
                "RECALL_SCHEDULER_MODE": "LEGACY_DAYN",
                "RECALL_COHORT_PREPARATION_SHA256": BUNDLE_SHA,
                "RECALL_SOURCE_COMMIT": SOURCE_COMMIT,
                "RECALL_IMAGE_DIGEST": IMAGE_DIGEST,
                "RECALL_EXPECTED_PROJECT_SHA256": "c" * 64,
            },
            now_factory=lambda: DAY3_NOW,
            ledger_factory=factory,
            repo_root=ROOT,
        )
    assert current.read_back_count("scan_runs") == before_runs
    assert current.read_back_count("scan_run_events") == before_events
    assert current.read_back_count("artifacts") == before_artifacts


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
        DayNScheduler(
            ledger,
            bundle=bundle,
            source_commit=SOURCE_COMMIT,
            image_digest=IMAGE_DIGEST,
        ).trigger(
            now=DAY2_NOW, previous_manifest=None
        )


@pytest.mark.parametrize(
    ("source_commit", "image_digest", "reason"),
    [
        ("g" * 40, IMAGE_DIGEST, "cohort_source_commit_invalid"),
        ("a" * 40, IMAGE_DIGEST, "source_commit_mismatch"),
        (SOURCE_COMMIT, "sha256:not-hex", "cohort_image_digest_invalid"),
    ],
)
def test_entrypoint_refuses_provenance_mismatch_before_ledger_creation(
    source_commit, image_digest, reason
) -> None:
    calls = 0

    def forbidden_factory(**_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("ledger factory must not run before provenance gate")

    with pytest.raises(RuntimeError, match=reason):
        execute(
            [],
            environment={
                "RECALL_SCHEDULER_MODE": "LEGACY_DAYN",
                "RECALL_COHORT_PREPARATION_SHA256": BUNDLE_SHA,
                "RECALL_SOURCE_COMMIT": source_commit,
                "RECALL_IMAGE_DIGEST": image_digest,
                "RECALL_EXPECTED_PROJECT_SHA256": "c" * 64,
            },
            now_factory=lambda: DAY2_NOW,
            ledger_factory=forbidden_factory,
            repo_root=ROOT,
        )
    assert calls == 0
