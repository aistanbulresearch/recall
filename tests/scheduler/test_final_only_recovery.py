from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import pytest

from recall.contracts import content_hash, parse_artifact
from recall.contracts.enums import ScanRunState
from recall.controller.hashes import scan_idempotency_key
from recall.ledger.memory import InMemoryLedger
from recall.ledger.models import COLLECTION_NAMES
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.scheduler.compressed import CompressedCycleScheduler
from recall.scheduler.compressed_batch_receipt import (
    persist_or_reconcile_batch_execution,
)
from recall.scheduler.compressed_cohort import cases_for_cycle
from recall.scheduler.compressed_identity import (
    collection_prefix,
    manifest_artifact_id,
    tick_run_id,
)
from recall.scheduler.compressed_plan import (
    FINAL_ONLY_OWNER_RELEASE_REASON,
    FINAL_ONLY_OWNER_RELEASE_TOKEN,
    authorize_final_only_owner_release,
    load_compressed_plan,
)
from recall.scheduler.entrypoint import execute
from recall.scheduler.compressed_preparation import (
    CompressedPreparationVerifier,
    load_compressed_bundle,
    verify_prepared_cycle,
)
from recall.scheduler.compressed_recovery import (
    FINAL_ONLY_RECOVERY_REASON,
    FinalExecutionRecoverySnapshot,
    authorize_final_only_recovery,
    build_final_execution_recovery_snapshot,
    install_final_only_recovery,
    recovery_collection_prefix,
    recovery_run_id,
    require_recovery_for_started_final_prefix,
    verify_final_only_recovery_ready,
)
from recall.scheduler.model_cost import (
    CostSnapshot,
    DEFAULT_MODEL_COST_POLICY,
    plan_cost_collection_name,
)
from tests.contracts.test_cohort_manifest_v34 import final_only_wire


REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_SHA256 = "db87ed31f01ef31166b4f029cc8f0453a823126495549cd5f497e8e6c7af654b"
PREVIOUS_EXECUTION_ID = "recall-cohort-daily-5tqxh"
PREVIOUS_SOURCE_COMMIT = "787ceb7be92132853c800837b49059c20e902f6b"
PREVIOUS_IMAGE_DIGEST = "sha256:" + "d" * 64
RECOVERY_ATTEMPT_ID = "84d24091-3c09-44d9-a236-a31dbc45e763"
CURRENT_SOURCE_COMMIT = "d7725f3e5cc2750c346928cbb94677e57ef06be3"
CURRENT_IMAGE_DIGEST = "sha256:" + "e" * 64


def _plan_bundle():
    plan = load_compressed_plan(REPO_ROOT)
    bundle = load_compressed_bundle(
        REPO_ROOT, expected_sha256=BUNDLE_SHA256, plan=plan
    )
    return plan, bundle, plan.by_id("c6")


def _write_metrics(cycle, count: int) -> dict[str, object]:
    completed = cycle.window_start + timedelta(seconds=1)
    return {
        "scope": "CASE_WRITE_AND_EXACT_READBACK",
        "measurement_semantics": (
            "LEDGER_METHOD_INVOCATIONS_AND_COMMITTED_CASE_DOCUMENTS"
        ),
        "persistence_surface": "LIVE_FIRESTORE",
        "batch_max_workers": 2,
        "selected_case_count": count,
        "ledger_operation_counts": {
            "watch_case_reads": count,
            "watch_artifact_reads": count,
            "idempotency_run_reads": count,
            "create_run_transaction_calls": count,
            "post_create_or_reuse_artifact_reads": count,
            "exact_run_pointer_reads": count,
            "exact_run_artifact_reads": count,
            "exact_run_event_queries": count,
            "aggregate_count_reads": 2,
        },
        "committed_case_documents": count * 3,
        "started_at": cycle.window_start.isoformat().replace("+00:00", "Z"),
        "completed_at": completed.isoformat().replace("+00:00", "Z"),
        "worker_elapsed_ms": 900,
        "readback_elapsed_ms": 100,
        "total_elapsed_ms": 1_000,
        "effective_write_millis_per_case": 2,
    }


def _cancelled_source_ledger():
    plan, bundle, cycle = _plan_bundle()
    ledger = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )
    from recall.scheduler.compressed_preparation import install_prepared_cycle

    install_prepared_cycle(ledger, bundle, plan, cycle, now=cycle.window_start)
    actual_start = cycle.window_end + timedelta(seconds=1)
    release = authorize_final_only_owner_release(
        plan,
        token=FINAL_ONLY_OWNER_RELEASE_TOKEN,
        reason=FINAL_ONLY_OWNER_RELEASE_REASON,
        actual_start=actual_start,
        max_retries=0,
    )
    scheduler = CompressedCycleScheduler(
        ledger,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        source_commit=PREVIOUS_SOURCE_COMMIT,
        image_digest=PREVIOUS_IMAGE_DIGEST,
        owner_release=release,
    )
    outcomes = tuple(
        scheduler._create_case(item, now=actual_start)
        for item in cases_for_cycle(cycle)
    )
    persist_or_reconcile_batch_execution(
        ledger=ledger,
        plan=plan,
        cycle=cycle,
        outcomes=outcomes,
        write_metrics=_write_metrics(cycle, len(outcomes)),
    )
    states = (
        (ScanRunState.CREATED, 417),
        (ScanRunState.HALTED, 14),
        (ScanRunState.NO_ACTION, 23),
        (ScanRunState.AUDITING, 1),
        (ScanRunState.WATCHING, 1),
    )
    offset = 0
    for state, count in states:
        for outcome in outcomes[offset : offset + count]:
            current = ledger._scan_runs[outcome.run_record.run_id]
            ledger._scan_runs[outcome.run_record.run_id] = replace(
                current,
                state=state,
                lease_epoch=(1 if state in {ScanRunState.AUDITING, ScanRunState.WATCHING} else 0),
                lease_expires_at=(
                    actual_start + timedelta(minutes=15)
                    if state in {ScanRunState.AUDITING, ScanRunState.WATCHING}
                    else None
                ),
            )
        offset += count
    return plan, bundle, cycle, ledger, outcomes, actual_start


@pytest.fixture(scope="module")
def recovery_source():
    return _cancelled_source_ledger()


def _recovery(plan, cycle, snapshot: FinalExecutionRecoverySnapshot):
    return authorize_final_only_recovery(
        plan,
        cycle=cycle,
        recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        owner_recovery_reason=FINAL_ONLY_RECOVERY_REASON,
        previous_execution_id=PREVIOUS_EXECUTION_ID,
        previous_source_commit=PREVIOUS_SOURCE_COMMIT,
        previous_image_digest=PREVIOUS_IMAGE_DIGEST,
        previous_snapshot_sha256=snapshot.snapshot_sha256,
    )


def test_recovery_namespace_and_run_identity_are_attempt_scoped(recovery_source) -> None:
    plan, bundle, cycle, old, outcomes, _started = recovery_source
    snapshot = build_final_execution_recovery_snapshot(
        old,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=PREVIOUS_EXECUTION_ID,
    )
    recovery = _recovery(plan, cycle, snapshot)
    prefix = recovery_collection_prefix(plan, cycle, recovery)
    old_prefix = collection_prefix(plan, cycle)
    first = cases_for_cycle(cycle)[0]
    old_run_id = outcomes[0].run_record.run_id
    new_run_id = recovery_run_id(first, recovery)

    assert prefix.startswith(f"dev_recall_final_p{plan.sha256[:8]}_c6_r")
    assert prefix != old_prefix
    assert len(f"{prefix}tool_gateway_invocations") <= 75
    assert new_run_id != old_run_id
    assert plan_cost_collection_name(plan.sha256) == (
        f"recall_plan6_cost_{plan.sha256[:16]}"
    )


def test_recovery_install_is_exact_456_and_binds_receipt_cost_and_snapshot(
    recovery_source,
) -> None:
    plan, bundle, cycle, old, _outcomes, started = recovery_source
    snapshot = build_final_execution_recovery_snapshot(
        old,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=PREVIOUS_EXECUTION_ID,
    )
    recovery = _recovery(plan, cycle, snapshot)
    target = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )
    result = install_final_only_recovery(
        previous_ledger=old,
        target_ledger=target,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        recovery=recovery,
        source_commit=CURRENT_SOURCE_COMMIT,
        image_digest=CURRENT_IMAGE_DIGEST,
        cost_snapshot=CostSnapshot(1_200, 900),
        now=started + timedelta(hours=1),
    )
    verified = verify_final_only_recovery_ready(
        previous_ledger=old,
        target_ledger=target,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        recovery=recovery,
        source_commit=CURRENT_SOURCE_COMMIT,
        image_digest=CURRENT_IMAGE_DIGEST,
        cost_snapshot=CostSnapshot(1_200, 900),
    )
    receipt = parse_artifact(
        target.get_artifact(result.recovery_receipt_id),
        authorized_producers=PRODUCER_REGISTRY,
    )

    assert result == verified
    assert receipt.schema_name == "FinalExecutionRecoveryReceipt"
    assert receipt.schema_version == "1.0.0"
    assert receipt.payload.previous_snapshot_sha256 == snapshot.snapshot_sha256
    assert receipt.payload.previous_state_counts == snapshot.state_counts
    assert receipt.payload.target_collection_prefix == recovery.collection_prefix
    assert receipt.payload.plan_cost_collection == plan_cost_collection_name(plan.sha256)
    assert receipt.payload.hard_cap_usd_micros == DEFAULT_MODEL_COST_POLICY.hard_cap_usd_micros
    assert receipt.payload.baseline_reserved_usd_micros == 1_200
    assert receipt.payload.baseline_reconciled_usd_micros == 900
    assert target.read_back_count("watch_cases") == 456
    assert target.read_back_count("scan_runs") == 0
    assert target.read_back_count("scan_run_events") == 0
    assert target.read_back_count("review_tasks") == 0
    verify_prepared_cycle(target, bundle, plan, cycle)


def test_previous_snapshot_drift_fails_before_any_target_write(recovery_source) -> None:
    plan, bundle, cycle, old, outcomes, started = recovery_source
    snapshot = build_final_execution_recovery_snapshot(
        old,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=PREVIOUS_EXECUTION_ID,
    )
    recovery = _recovery(plan, cycle, snapshot)
    first_id = outcomes[0].run_record.run_id
    original = old._scan_runs[first_id]
    old._scan_runs[first_id] = replace(original, version=original.version + 1)
    target = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )
    try:
        with pytest.raises(RuntimeError, match="final_recovery_previous_snapshot_drift"):
            install_final_only_recovery(
                previous_ledger=old,
                target_ledger=target,
                plan=plan,
                cycle=cycle,
                bundle=bundle,
                recovery=recovery,
                source_commit=CURRENT_SOURCE_COMMIT,
                image_digest=CURRENT_IMAGE_DIGEST,
                cost_snapshot=CostSnapshot(1_200, 900),
                now=started + timedelta(hours=1),
            )
    finally:
        old._scan_runs[first_id] = original
    assert {name: target.read_back_count(name) for name in COLLECTION_NAMES} == {
        name: 0 for name in COLLECTION_NAMES
    }


@pytest.mark.parametrize(
    "mutation",
    ["hard_cap", "previous_prefix", "input_closure"],
)
def test_preseeded_recovery_receipt_drift_fails_before_preparation(
    recovery_source,
    mutation: str,
) -> None:
    plan, bundle, cycle, old, _outcomes, started = recovery_source
    snapshot = build_final_execution_recovery_snapshot(
        old,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=PREVIOUS_EXECUTION_ID,
    )
    recovery = _recovery(plan, cycle, snapshot)
    valid_target = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )
    installed = install_final_only_recovery(
        previous_ledger=old,
        target_ledger=valid_target,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        recovery=recovery,
        source_commit=CURRENT_SOURCE_COMMIT,
        image_digest=CURRENT_IMAGE_DIGEST,
        cost_snapshot=CostSnapshot(1_200, 900),
        now=started + timedelta(hours=1),
    )
    drifted = deepcopy(
        valid_target.get_artifact(installed.recovery_receipt_id)
    )
    assert drifted is not None
    if mutation == "hard_cap":
        drifted["hard_cap_usd_micros"] = (
            DEFAULT_MODEL_COST_POLICY.hard_cap_usd_micros + 1
        )
    elif mutation == "previous_prefix":
        drifted["previous_collection_prefix"] = "dev_recall_wrong_prefix_"
    else:
        drifted["input_artifact_ids"] = []
    drifted["content_hash"] = content_hash(drifted)
    target = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )
    target._artifacts[installed.recovery_receipt_id] = drifted
    before = deepcopy(target._artifacts)

    with pytest.raises(RuntimeError, match="final_recovery_receipt_binding_invalid"):
        install_final_only_recovery(
            previous_ledger=old,
            target_ledger=target,
            plan=plan,
            cycle=cycle,
            bundle=bundle,
            recovery=recovery,
            source_commit=CURRENT_SOURCE_COMMIT,
            image_digest=CURRENT_IMAGE_DIGEST,
            cost_snapshot=CostSnapshot(1_200, 900),
            now=started + timedelta(hours=1),
        )

    assert target._artifacts == before
    assert target.read_back_count("watch_cases") == 0
    assert target.read_back_count("scan_runs") == 0


def test_same_prefix_and_target_execution_rows_are_rejected(recovery_source) -> None:
    plan, bundle, cycle, old, _outcomes, started = recovery_source
    snapshot = build_final_execution_recovery_snapshot(
        old,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=PREVIOUS_EXECUTION_ID,
    )
    recovery = _recovery(plan, cycle, snapshot)
    with pytest.raises(RuntimeError, match="final_recovery_namespace_collision"):
        install_final_only_recovery(
            previous_ledger=old,
            target_ledger=old,
            plan=plan,
            cycle=cycle,
            bundle=bundle,
            recovery=recovery,
            source_commit=CURRENT_SOURCE_COMMIT,
            image_digest=CURRENT_IMAGE_DIGEST,
            cost_snapshot=CostSnapshot(1_200, 900),
            now=started + timedelta(hours=1),
        )

    target = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )
    installed = install_final_only_recovery(
        previous_ledger=old,
        target_ledger=target,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        recovery=recovery,
        source_commit=CURRENT_SOURCE_COMMIT,
        image_digest=CURRENT_IMAGE_DIGEST,
        cost_snapshot=CostSnapshot(1_200, 900),
        now=started + timedelta(hours=1),
    )
    first = cases_for_cycle(cycle)[0]
    old_record = old.get_watch_case(first.case_id)
    assert old_record is not None
    scoped_key = scan_idempotency_key(
        watch_case_id=first.case_id,
        source_cursors=dict(old_record.source_cursors),
        schedule_epoch=cycle.schedule_epoch,
        data_mode="SYNTHETIC",
        identity_scope=recovery.identity_scope,
    )
    assert str(uuid5(NAMESPACE_URL, f"recall:scan-run:{scoped_key}")) == recovery_run_id(
        first, recovery
    )
    target._scan_runs[recovery_run_id(first, recovery)] = old._scan_runs[
        next(iter(old._scan_runs))
    ]
    with pytest.raises(RuntimeError, match="final_recovery_target_execution_started"):
        verify_final_only_recovery_ready(
            previous_ledger=old,
            target_ledger=target,
            plan=plan,
            cycle=cycle,
            bundle=bundle,
            recovery=recovery,
            source_commit=CURRENT_SOURCE_COMMIT,
            image_digest=CURRENT_IMAGE_DIGEST,
            cost_snapshot=CostSnapshot(1_200, 900),
        )
    assert installed.recovery_receipt_id


def test_owner_release_without_recovery_rejects_cancelled_prefix_before_write(
    recovery_source,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, bundle, cycle, old, _outcomes, started = recovery_source
    release = authorize_final_only_owner_release(
        plan,
        token=FINAL_ONLY_OWNER_RELEASE_TOKEN,
        reason=FINAL_ONLY_OWNER_RELEASE_REASON,
        actual_start=started + timedelta(hours=1),
        max_retries=0,
    )
    scheduler = CompressedCycleScheduler(
        old,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        source_commit=CURRENT_SOURCE_COMMIT,
        image_digest=CURRENT_IMAGE_DIGEST,
        owner_release=release,
    )
    before_counts = {
        name: old.read_back_count(name) for name in COLLECTION_NAMES
    }
    before_artifacts = dict(old._artifacts)
    before_runs = dict(old._scan_runs)
    monkeypatch.setattr(
        "recall.scheduler.compressed.verify_final_only_supersession",
        lambda *_args, **_kwargs: SimpleNamespace(verified_artifact_ids=()),
    )

    with pytest.raises(RuntimeError, match="final_recovery_required"):
        scheduler.trigger(
            now=release.actual_start,
            previous_manifest=None,
            historical_ledger_factory=lambda _prefix: old,
        )

    assert {
        name: old.read_back_count(name) for name in COLLECTION_NAMES
    } == before_counts
    assert old._artifacts == before_artifacts
    assert old._scan_runs == before_runs


def test_recovery_free_owner_release_still_accepts_fresh_prepared_prefix() -> None:
    plan, bundle, cycle = _plan_bundle()
    fresh = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )
    from recall.scheduler.compressed_preparation import install_prepared_cycle

    install_prepared_cycle(fresh, bundle, plan, cycle, now=cycle.window_start)

    require_recovery_for_started_final_prefix(
        fresh,
        plan=plan,
        cycle=cycle,
    )
    assert fresh.read_back_count("watch_cases") == 456
    assert fresh.read_back_count("scan_runs") == 0


def test_incomplete_final_manifest_cannot_bypass_recovery_isolation(
    recovery_source,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, bundle, cycle, old, _outcomes, started = recovery_source
    release = authorize_final_only_owner_release(
        plan,
        token=FINAL_ONLY_OWNER_RELEASE_TOKEN,
        reason=FINAL_ONLY_OWNER_RELEASE_REASON,
        actual_start=started + timedelta(hours=1),
        max_retries=0,
    )
    incomplete = deepcopy(final_only_wire.__wrapped__())
    incomplete.update(
        {
            "artifact_id": manifest_artifact_id(plan, cycle),
            "run_id": tick_run_id(plan, cycle),
            "plan_sha256": plan.sha256,
        }
    )
    incomplete["execution_history"][-1]["execution_status"] = "INCOMPLETE"
    incomplete["cumulative"]["compressed_cycles_completed"] = 2
    incomplete["cumulative"]["successful_compressed_cycles"] = 2
    incomplete["content_hash"] = content_hash(incomplete)
    assert parse_artifact(
        incomplete, authorized_producers=PRODUCER_REGISTRY
    ).status.value == "INCOMPLETE"
    old._artifacts[manifest_artifact_id(plan, cycle)] = incomplete
    before_counts = {
        name: old.read_back_count(name) for name in COLLECTION_NAMES
    }
    before_artifacts = deepcopy(old._artifacts)
    before_runs = dict(old._scan_runs)
    scheduler = CompressedCycleScheduler(
        old,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        source_commit=CURRENT_SOURCE_COMMIT,
        image_digest=CURRENT_IMAGE_DIGEST,
        owner_release=release,
    )
    monkeypatch.setattr(
        "recall.scheduler.compressed.verify_final_only_supersession",
        lambda *_args, **_kwargs: SimpleNamespace(verified_artifact_ids=()),
    )
    try:
        with pytest.raises(RuntimeError, match="final_recovery_required"):
            scheduler.trigger(
                now=release.actual_start,
                previous_manifest=None,
                historical_ledger_factory=lambda _prefix: old,
            )
        assert {
            name: old.read_back_count(name) for name in COLLECTION_NAMES
        } == before_counts
        assert old._artifacts == before_artifacts
        assert old._scan_runs == before_runs
    finally:
        old._artifacts.pop(manifest_artifact_id(plan, cycle), None)


def test_wrong_artifact_at_final_manifest_id_fails_closed(recovery_source) -> None:
    plan, _bundle, cycle, old, _outcomes, _started = recovery_source
    manifest_id = manifest_artifact_id(plan, cycle)
    wrong = deepcopy(
        next(
            wire
            for wire in old._artifacts.values()
            if wire["schema_name"] == "BatchExecutionReceipt"
        )
    )
    wrong["artifact_id"] = manifest_id
    wrong["content_hash"] = content_hash(wrong)
    old._artifacts[manifest_id] = wrong
    before = deepcopy(old._artifacts)
    try:
        with pytest.raises(RuntimeError, match="final_recovery_required"):
            require_recovery_for_started_final_prefix(
                old,
                plan=plan,
                cycle=cycle,
            )
        assert old._artifacts == before
    finally:
        old._artifacts.pop(manifest_id, None)


def test_recovery_scheduler_creates_fresh_attempt_scoped_run_without_touching_old(
    recovery_source,
) -> None:
    plan, bundle, cycle, old, outcomes, started = recovery_source
    snapshot = build_final_execution_recovery_snapshot(
        old,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=PREVIOUS_EXECUTION_ID,
    )
    recovery = _recovery(plan, cycle, snapshot)
    target = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )
    install_final_only_recovery(
        previous_ledger=old,
        target_ledger=target,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        recovery=recovery,
        source_commit=CURRENT_SOURCE_COMMIT,
        image_digest=CURRENT_IMAGE_DIGEST,
        cost_snapshot=CostSnapshot(1_200, 900),
        now=started + timedelta(hours=1),
    )
    release = authorize_final_only_owner_release(
        plan,
        token=FINAL_ONLY_OWNER_RELEASE_TOKEN,
        reason=FINAL_ONLY_OWNER_RELEASE_REASON,
        actual_start=started + timedelta(hours=1),
        max_retries=0,
        recovery=recovery,
    )
    scheduler = CompressedCycleScheduler(
        target,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        source_commit=CURRENT_SOURCE_COMMIT,
        image_digest=CURRENT_IMAGE_DIGEST,
        owner_release=release,
    )
    first = cases_for_cycle(cycle)[0]
    old_before = old.get_scan_run(outcomes[0].run_record.run_id)
    created = scheduler._create_case(first, now=release.actual_start)

    assert created.created is True
    assert created.run_record.run_id == recovery_run_id(first, recovery)
    assert created.run_record.run_id != outcomes[0].run_record.run_id
    assert old.get_scan_run(outcomes[0].run_record.run_id) == old_before
    assert target.read_back_count("scan_runs") == 1
    assert target.read_back_count("scan_run_events") == 1


@pytest.mark.parametrize(
    ("attempt_id", "reason", "error"),
    [
        ("not-a-uuid", FINAL_ONLY_RECOVERY_REASON, "attempt_id_invalid"),
        (RECOVERY_ATTEMPT_ID, "wrong", "reason_invalid"),
    ],
)
def test_recovery_authority_fails_closed(attempt_id: str, reason: str, error: str) -> None:
    plan, bundle, cycle = _plan_bundle()
    with pytest.raises(RuntimeError, match=f"final_recovery_{error}"):
        authorize_final_only_recovery(
            plan,
            cycle=cycle,
            recovery_attempt_id=attempt_id,
            owner_recovery_reason=reason,
            previous_execution_id=PREVIOUS_EXECUTION_ID,
            previous_source_commit=PREVIOUS_SOURCE_COMMIT,
            previous_image_digest=PREVIOUS_IMAGE_DIGEST,
            previous_snapshot_sha256="a" * 64,
        )


def test_entrypoint_routes_explicit_recovery_to_strict_new_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, _bundle, cycle = _plan_bundle()
    prefixes: list[str] = []
    observed: dict[str, object] = {}

    def ledger_factory(*, collection_prefix: str, privacy_receipt_verifier, **_kwargs):
        prefixes.append(collection_prefix)
        return InMemoryLedger(privacy_receipt_verifier=privacy_receipt_verifier)

    def fake_trigger(self, **kwargs):
        observed["recovery"] = self._owner_release.recovery
        observed["previous"] = kwargs["recovery_previous_ledger"]
        return SimpleNamespace(
            cycle_id="c6",
            cohort_due_date=cycle.cohort_due_date.isoformat(),
            newly_created_run_ids=(),
            reused_run_ids=(),
            authoritative_run_ids=(),
            manifest_artifact_id="manifest",
            data_mode_receipt_id=None,
        )

    monkeypatch.setattr(CompressedCycleScheduler, "trigger", fake_trigger)
    result = execute(
        [
            "--owner-release-token",
            FINAL_ONLY_OWNER_RELEASE_TOKEN,
            "--owner-release-reason",
            FINAL_ONLY_OWNER_RELEASE_REASON,
            "--recovery-attempt-id",
            RECOVERY_ATTEMPT_ID,
            "--owner-recovery-reason",
            FINAL_ONLY_RECOVERY_REASON,
            "--recovery-previous-execution-id",
            PREVIOUS_EXECUTION_ID,
            "--recovery-previous-source-commit",
            PREVIOUS_SOURCE_COMMIT,
            "--recovery-previous-image-digest",
            PREVIOUS_IMAGE_DIGEST,
            "--recovery-previous-snapshot-sha256",
            "a" * 64,
        ],
        environment={
            "RECALL_SCHEDULER_MODE": "COMPRESSED_V3",
            "RECALL_PROVIDER_RPM": "8",
            "RECALL_COMPRESSED_PREPARATION_SHA256": BUNDLE_SHA256,
            "RECALL_SOURCE_COMMIT": CURRENT_SOURCE_COMMIT,
            "RECALL_IMAGE_DIGEST": CURRENT_IMAGE_DIGEST,
            "RECALL_EXPECTED_PROJECT_SHA256": "b" * 64,
            "RECALL_FINAL_OWNER_RELEASE_MAX_RETRIES": "0",
            "RECALL_NCBI_TOOL": "recall-test",
            "RECALL_NCBI_EMAIL": "test@example.invalid",
        },
        now_factory=lambda: cycle.window_end + timedelta(hours=2),
        ledger_factory=ledger_factory,
        full_audit_factory=lambda _ledger: object(),
        repo_root=REPO_ROOT,
    )
    recovery = observed["recovery"]
    assert recovery is not None
    assert prefixes == [
        recovery.collection_prefix,
        recovery.previous_collection_prefix,
    ]
    assert result["collection_prefix"] == recovery.collection_prefix
    assert result["owner_release"]["recovery_attempt_id"] == RECOVERY_ATTEMPT_ID
    assert observed["previous"] is not None


@pytest.mark.parametrize(
    "argv",
    [
        ["--recovery-attempt-id", RECOVERY_ATTEMPT_ID],
        [
            "--owner-release-token",
            FINAL_ONLY_OWNER_RELEASE_TOKEN,
            "--owner-release-reason",
            FINAL_ONLY_OWNER_RELEASE_REASON,
            "--recovery-attempt-id",
            RECOVERY_ATTEMPT_ID,
        ],
    ],
)
def test_entrypoint_rejects_partial_recovery_contract_before_ledger(
    argv: list[str],
) -> None:
    calls = 0

    def forbidden_ledger(**_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("ledger_must_not_be_constructed")

    with pytest.raises(RuntimeError, match="final_recovery_cli_invalid"):
        execute(
            argv,
            environment={
                "RECALL_SCHEDULER_MODE": "COMPRESSED_V3",
                "RECALL_PROVIDER_RPM": "8",
            },
            ledger_factory=forbidden_ledger,
        )
    assert calls == 0
