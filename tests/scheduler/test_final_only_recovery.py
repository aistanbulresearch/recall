from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest

from recall.contracts import (
    ArtifactStatus,
    ContractError,
    DataMode,
    build_artifact,
    content_hash,
    parse_artifact,
)
from recall.contracts.enums import ScanRunState, WatchCaseState
from recall.controller.hashes import scan_idempotency_key
from recall.ledger.memory import InMemoryLedger
from recall.ledger.models import COLLECTION_NAMES, ReviewTaskRecord
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
SECOND_RECOVERY_ATTEMPT_ID = "3f08d9a0-f8f9-4e1b-a4f1-b9d0a28a0f55"
SECOND_PREVIOUS_EXECUTION_ID = "recall-cohort-daily-recovery-cancelled"
CURRENT_SOURCE_COMMIT = "d7725f3e5cc2750c346928cbb94677e57ef06be3"
CURRENT_IMAGE_DIGEST = "sha256:" + "e" * 64
BASELINE_CANCELLED_SNAPSHOT_SHA256 = (
    "5e9b1f7795da8ce7ec357d34c6f02d151bbc95945abfea2793d00c59258d5abe"
)
LEGACY_CANCELLED_STATES = (
    (ScanRunState.CREATED, 417),
    (ScanRunState.HALTED, 14),
    (ScanRunState.NO_ACTION, 23),
    (ScanRunState.AUDITING, 1),
    (ScanRunState.WATCHING, 1),
)
LIVE_CHAINED_CANCELLED_STATES = (
    (ScanRunState.CREATED, 260),
    (ScanRunState.HALTED, 66),
    (ScanRunState.NO_ACTION, 128),
    (ScanRunState.WATCHING, 1),
    (ScanRunState.ASSESSING, 1),
)
ALL_STATE_CANCELLED_STATES = (
    (ScanRunState.CREATED, 446),
    (ScanRunState.QUEUED, 1),
    (ScanRunState.ROUTING, 1),
    (ScanRunState.WATCHING, 1),
    (ScanRunState.ASSESSING, 1),
    (ScanRunState.AUDITING, 1),
    (ScanRunState.POLICY_EVALUATION, 1),
    (ScanRunState.NO_ACTION, 1),
    (ScanRunState.ABSTAIN, 1),
    (ScanRunState.REVIEW_REQUIRED, 1),
    (ScanRunState.HALTED, 1),
)


class _BulkReadCountingLedger(InMemoryLedger):
    def __init__(self) -> None:
        super().__init__()
        self.read_calls = {
            "list_watch_cases": 0,
            "list_scan_runs": 0,
            "list_review_tasks_all": 0,
            "get_artifacts": 0,
            "get_watch_case": 0,
            "get_scan_run": 0,
            "get_artifact": 0,
        }

    def list_watch_cases(self):
        self.read_calls["list_watch_cases"] += 1
        return tuple(self._watch_cases.values())

    def list_scan_runs(self):
        self.read_calls["list_scan_runs"] += 1
        return tuple(self._scan_runs.values())

    def list_review_tasks_all(self):
        self.read_calls["list_review_tasks_all"] += 1
        return tuple(self._review_tasks.values())

    def get_artifacts(self, artifact_ids):
        self.read_calls["get_artifacts"] += 1
        return {
            artifact_id: deepcopy(self._artifacts[artifact_id])
            for artifact_id in dict.fromkeys(artifact_ids)
            if artifact_id in self._artifacts
        }

    def get_watch_case(self, watch_case_id):
        self.read_calls["get_watch_case"] += 1
        return super().get_watch_case(watch_case_id)

    def get_scan_run(self, run_id):
        self.read_calls["get_scan_run"] += 1
        return super().get_scan_run(run_id)

    def get_artifact(self, artifact_id):
        self.read_calls["get_artifact"] += 1
        return super().get_artifact(artifact_id)


def _clone_ledger(source: InMemoryLedger) -> InMemoryLedger:
    cloned = InMemoryLedger(
        privacy_receipt_verifier=source._privacy_receipt_verifier
    )
    cloned._artifacts = deepcopy(source._artifacts)
    cloned._watch_cases = deepcopy(source._watch_cases)
    cloned._scan_runs = deepcopy(source._scan_runs)
    cloned._scan_run_events = deepcopy(source._scan_run_events)
    cloned._review_tasks = deepcopy(source._review_tasks)
    return cloned


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


def _policy_facts(state: ScanRunState) -> dict[str, str]:
    candidate = "ABSENT" if state is ScanRunState.NO_ACTION else "PRESENT"
    pass_state = "NOT_EVALUATED" if candidate == "ABSENT" else "PASS"
    return {
        "privacy_accepted": "PASS",
        "registry_resolution_valid": "PASS",
        "route_valid": "PASS",
        "tool_authorization_complete": "PASS",
        "source_retrieval_complete": "PASS",
        "source_schema_valid": "PASS",
        "data_mode_valid": "PASS",
        "snapshot_integrity_valid": "PASS",
        "assessment_valid": pass_state,
        "citation_audit_complete": pass_state,
        "all_material_claims_verified": pass_state,
        "counter_evidence_complete": pass_state,
        "candidate_delta_state": candidate,
        "unresolved_conflict_state": "ABSENT",
        "budget_or_loop_failure_state": "ABSENT",
        "existing_open_task_state": "ABSENT",
    }


def _append_terminal_closure(
    ledger: InMemoryLedger,
    *,
    run,
    watch,
    initial_source_cursors: dict[str, str],
    evidence_data_mode: DataMode,
    now,
) -> None:
    created_at = now.isoformat().replace("+00:00", "Z")
    if run.state is ScanRunState.HALTED:
        failure_id = run.failure_receipt_ids[0]
        ledger.append_artifact(
            build_artifact(
                schema_name="FailureReceipt",
                schema_version="1.0.0",
                artifact_id=failure_id,
                case_id=watch.watch_case_id,
                run_id=run.run_id,
                producer={
                    "component": "full-audit-controller",
                    "version": "1.0.0",
                    "identity": "controller-failure-recorder",
                },
                created_at=created_at,
                input_artifact_ids=(run.scan_run_artifact_id,),
                data_mode=evidence_data_mode,
                status=ArtifactStatus.REJECTED,
                payload={
                    "failure_code": "controller_failed",
                    "stage": "UNKNOWN",
                    "retryable": False,
                    "attempt": 1,
                    "budget_state": "WITHIN_LIMIT",
                    "details": {},
                    "related_artifact_ids": [run.scan_run_artifact_id],
                    "safe_terminal": "HALTED",
                    "operator_action": "inspect_agent_execution_receipts",
                },
                authorized_producers=PRODUCER_REGISTRY,
            )
        )
        return
    if run.state not in {
        ScanRunState.NO_ACTION,
        ScanRunState.ABSTAIN,
        ScanRunState.REVIEW_REQUIRED,
    }:
        return
    policy_id = str(run.terminal_policy_decision_id)
    ledger.append_artifact(
        build_artifact(
            schema_name="PolicyDecision",
            schema_version="2.0.0",
            artifact_id=policy_id,
            case_id=watch.watch_case_id,
            run_id=run.run_id,
            producer={
                "component": "deterministic-policy-gate",
                "version": "1.0.1",
                "identity": "policy-gate",
            },
            created_at=created_at,
            input_artifact_ids=(run.scan_run_artifact_id,),
            data_mode=DataMode.SYNTHETIC,
            status=ArtifactStatus.VALID,
            payload={
                "policy_version": "1.0.1",
                "input_facts": _policy_facts(run.state),
                "outcome": run.state.value,
                "reason_codes": [f"test_{run.state.value.lower()}"],
                "missing_prerequisites": [],
                "review_trigger": run.state is ScanRunState.REVIEW_REQUIRED,
                "existing_task_id": None,
            },
            authorized_producers=PRODUCER_REGISTRY,
        )
    )
    if run.state in {ScanRunState.NO_ACTION, ScanRunState.REVIEW_REQUIRED}:
        ledger.append_artifact(
            build_artifact(
                schema_name="EvidenceSnapshot",
                schema_version="1.0.0",
                artifact_id=str(watch.last_verified_snapshot_id),
                case_id=watch.watch_case_id,
                run_id=run.run_id,
                producer={
                    "component": "evidence-watcher",
                    "version": "0.1.0",
                    "identity": "evidence-watcher",
                },
                created_at=created_at,
                input_artifact_ids=(),
                data_mode=evidence_data_mode,
                status=ArtifactStatus.VALID,
                payload={
                    "effective_at": created_at,
                    "observation_ids": [],
                    "coverage_status": "PASS",
                    "source_cursors": initial_source_cursors,
                    "normalized_facts": {"observation_count": 1},
                    "conflicts": [],
                    "snapshot_hash": "b" * 64,
                },
                authorized_producers=PRODUCER_REGISTRY,
            )
        )
    if run.state is ScanRunState.REVIEW_REQUIRED:
        task_id = str(watch.open_review_task_id)
        audit_id = str(uuid5(UUID(run.run_id), "citation-audit"))
        claim_id = str(uuid5(UUID(run.run_id), "claim"))
        task = build_artifact(
            schema_name="ReviewTask",
            schema_version="1.0.0",
            artifact_id=task_id,
            case_id=watch.watch_case_id,
            run_id=run.run_id,
            producer={
                "component": "controller-outbox",
                "version": "0.1.0",
                "identity": "controller",
            },
            created_at=created_at,
            input_artifact_ids=tuple(sorted((audit_id, policy_id))),
            data_mode=DataMode.SYNTHETIC,
            status=ArtifactStatus.VALID,
            payload={
                "watch_case_id": watch.watch_case_id,
                "trigger_decision_id": policy_id,
                "state": "OPEN",
                "priority_band": "STANDARD",
                "claim_ids": [claim_id],
                "audit_receipt_id": audit_id,
                "simulation": True,
                "deduplication_key": "d" * 64,
            },
            authorized_producers=PRODUCER_REGISTRY,
        )
        ledger.append_artifact(task)
        ledger._review_tasks[task_id] = ReviewTaskRecord(
            task_id=task_id,
            run_id=run.run_id,
            watch_case_id=watch.watch_case_id,
            policy_decision_id=policy_id,
            deduplication_key="d" * 64,
            artifact_id=task_id,
            state="OPEN",
            delivery_state="PENDING",
            created_at=now,
        )


def _mark_cancelled_execution(
    ledger,
    outcomes,
    *,
    plan,
    cycle,
    actual_start,
    state_counts=LEGACY_CANCELLED_STATES,
    lifecycle_faithful: bool = False,
) -> None:
    persist_or_reconcile_batch_execution(
        ledger=ledger,
        plan=plan,
        cycle=cycle,
        outcomes=outcomes,
        write_metrics=_write_metrics(cycle, len(outcomes)),
    )
    version_by_state = {
        ScanRunState.CREATED: 1,
        ScanRunState.QUEUED: 2,
        ScanRunState.ROUTING: 3,
        ScanRunState.WATCHING: 4,
        ScanRunState.ASSESSING: 5,
        ScanRunState.AUDITING: 6,
        ScanRunState.POLICY_EVALUATION: 7,
        ScanRunState.NO_ACTION: 8,
        ScanRunState.ABSTAIN: 8,
        ScanRunState.REVIEW_REQUIRED: 8,
        ScanRunState.HALTED: 5,
    }
    leased_states = {
        ScanRunState.ROUTING,
        ScanRunState.WATCHING,
        ScanRunState.ASSESSING,
        ScanRunState.AUDITING,
        ScanRunState.POLICY_EVALUATION,
        ScanRunState.NO_ACTION,
        ScanRunState.ABSTAIN,
        ScanRunState.REVIEW_REQUIRED,
        ScanRunState.HALTED,
    }
    offset = 0
    for state, count in state_counts:
        for outcome in outcomes[offset : offset + count]:
            current = ledger._scan_runs[outcome.run_record.run_id]
            ledger._scan_runs[outcome.run_record.run_id] = replace(
                current,
                state=state,
                version=(version_by_state[state] if lifecycle_faithful else current.version),
                terminal_policy_decision_id=(
                    str(uuid5(NAMESPACE_URL, f"policy:{current.run_id}"))
                    if state
                    in {
                        ScanRunState.NO_ACTION,
                        ScanRunState.ABSTAIN,
                        ScanRunState.REVIEW_REQUIRED,
                    }
                    else None
                ),
                failure_receipt_ids=(
                    (str(uuid5(NAMESPACE_URL, f"failure:{current.run_id}")),)
                    if state is ScanRunState.HALTED
                    else ()
                ),
                lease_epoch=(
                    1
                    if lifecycle_faithful and state in leased_states
                    else (
                        1
                        if state in {ScanRunState.AUDITING, ScanRunState.WATCHING}
                        else 0
                    )
                ),
                lease_expires_at=(
                    actual_start + timedelta(minutes=15)
                    if (
                        state in leased_states
                        if lifecycle_faithful
                        else state in {ScanRunState.AUDITING, ScanRunState.WATCHING}
                    )
                    else None
                ),
            )
            watch = ledger._watch_cases[outcome.case.case_id]
            if state is ScanRunState.HALTED:
                ledger._watch_cases[outcome.case.case_id] = replace(
                    watch,
                    state=WatchCaseState.ATTENTION_REQUIRED,
                    version=watch.version + 1,
                    attention_reason_codes=("controller_failed",),
                    next_scan_at=None,
                    updated_at=actual_start + timedelta(seconds=1),
                )
            elif state is ScanRunState.NO_ACTION:
                ledger._watch_cases[outcome.case.case_id] = replace(
                    watch,
                    state=WatchCaseState.ACTIVE,
                    version=watch.version + 1,
                    source_cursors=(
                        watch.source_cursors
                        if lifecycle_faithful
                        else (
                            (
                                "synthetic-source",
                                f"{dict(watch.source_cursors)['synthetic-source']}:verified",
                            ),
                        )
                    ),
                    last_verified_snapshot_id=str(
                        uuid5(NAMESPACE_URL, f"snapshot:{outcome.case.case_id}")
                    ),
                    pending_observation_hashes=(),
                    attention_reason_codes=(),
                    updated_at=actual_start + timedelta(seconds=1),
                )
            elif state is ScanRunState.ABSTAIN:
                ledger._watch_cases[outcome.case.case_id] = replace(
                    watch,
                    state=WatchCaseState.ACTIVE,
                    version=watch.version + 1,
                    pending_observation_hashes=(),
                    open_review_task_id=None,
                    attention_reason_codes=("policy_abstain",),
                    updated_at=actual_start + timedelta(seconds=1),
                )
            elif state is ScanRunState.REVIEW_REQUIRED:
                ledger._watch_cases[outcome.case.case_id] = replace(
                    watch,
                    state=WatchCaseState.AWAITING_HUMAN,
                    version=watch.version + 1,
                    last_verified_snapshot_id=str(
                        uuid5(NAMESPACE_URL, f"snapshot:{outcome.case.case_id}")
                    ),
                    pending_observation_hashes=(),
                    open_review_task_id=str(
                        uuid5(NAMESPACE_URL, f"task:{outcome.case.case_id}")
                    ),
                    attention_reason_codes=(),
                    next_scan_at=None,
                    updated_at=actual_start + timedelta(seconds=1),
                )
            if lifecycle_faithful:
                _append_terminal_closure(
                    ledger,
                    run=ledger._scan_runs[outcome.run_record.run_id],
                    watch=ledger._watch_cases[outcome.case.case_id],
                    initial_source_cursors=dict(watch.source_cursors),
                    evidence_data_mode=(
                        DataMode.CAPTURED_REPLAY
                        if outcome.case.vcv is not None
                        else DataMode.SYNTHETIC
                    ),
                    now=actual_start + timedelta(seconds=1),
                )
        offset += count
    assert offset == len(outcomes)


def _place_replay_outcomes_in_terminal_states(outcomes):
    replay = sorted(
        (item for item in outcomes if item.case.vcv is not None),
        key=lambda item: item.case.case_id,
    )
    assert len(replay) == 3
    positions: dict[ScanRunState, int] = {}
    offset = 0
    for state, count in ALL_STATE_CANCELLED_STATES:
        if state in {
            ScanRunState.NO_ACTION,
            ScanRunState.REVIEW_REQUIRED,
            ScanRunState.HALTED,
        }:
            assert count == 1
            positions[state] = offset
        offset += count
    arranged = [None] * len(outcomes)
    for state, outcome in zip(
        (
            ScanRunState.NO_ACTION,
            ScanRunState.REVIEW_REQUIRED,
            ScanRunState.HALTED,
        ),
        replay,
        strict=True,
    ):
        arranged[positions[state]] = outcome
    remaining = iter(item for item in outcomes if item not in replay)
    for index, item in enumerate(arranged):
        if item is None:
            arranged[index] = next(remaining)
    return tuple(arranged)


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
    _mark_cancelled_execution(
        ledger,
        outcomes,
        plan=plan,
        cycle=cycle,
        actual_start=actual_start,
    )
    return plan, bundle, cycle, ledger, outcomes, actual_start


@pytest.fixture(scope="module")
def recovery_source():
    return _cancelled_source_ledger()


def _cancelled_first_recovery_ledger(
    *,
    state_counts=LEGACY_CANCELLED_STATES,
    lifecycle_faithful: bool = False,
    replay_terminal_closure: bool = False,
):
    plan, bundle, cycle, base, _base_outcomes, started = _cancelled_source_ledger()
    base_snapshot = build_final_execution_recovery_snapshot(
        base,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=PREVIOUS_EXECUTION_ID,
    )
    first_recovery = _recovery(plan, cycle, base_snapshot)
    first = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )
    install_final_only_recovery(
        previous_ledger=base,
        target_ledger=first,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        recovery=first_recovery,
        source_commit=CURRENT_SOURCE_COMMIT,
        image_digest=CURRENT_IMAGE_DIGEST,
        cost_snapshot=CostSnapshot(1_200, 900),
        now=started + timedelta(minutes=30),
    )
    recovery_start = started + timedelta(hours=1)
    release = authorize_final_only_owner_release(
        plan,
        token=FINAL_ONLY_OWNER_RELEASE_TOKEN,
        reason=FINAL_ONLY_OWNER_RELEASE_REASON,
        actual_start=recovery_start,
        max_retries=0,
        recovery=first_recovery,
    )
    scheduler = CompressedCycleScheduler(
        first,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        source_commit=CURRENT_SOURCE_COMMIT,
        image_digest=CURRENT_IMAGE_DIGEST,
        owner_release=release,
    )
    outcomes = tuple(
        scheduler._create_case(item, now=recovery_start)
        for item in cases_for_cycle(cycle)
    )
    if replay_terminal_closure:
        outcomes = _place_replay_outcomes_in_terminal_states(outcomes)
    _mark_cancelled_execution(
        first,
        outcomes,
        plan=plan,
        cycle=cycle,
        actual_start=recovery_start,
        state_counts=state_counts,
        lifecycle_faithful=lifecycle_faithful,
    )
    return plan, bundle, cycle, first, first_recovery, recovery_start


@pytest.fixture(scope="module")
def chained_recovery_source():
    return _cancelled_first_recovery_ledger(lifecycle_faithful=True)


@pytest.fixture(scope="module")
def live_chained_recovery_source():
    return _cancelled_first_recovery_ledger(
        state_counts=LIVE_CHAINED_CANCELLED_STATES,
        lifecycle_faithful=True,
    )


@pytest.fixture(scope="module")
def all_state_chained_recovery_source():
    return _cancelled_first_recovery_ledger(
        state_counts=ALL_STATE_CANCELLED_STATES,
        lifecycle_faithful=True,
    )


@pytest.fixture(scope="module")
def replay_terminal_chained_recovery_source():
    return _cancelled_first_recovery_ledger(
        state_counts=ALL_STATE_CANCELLED_STATES,
        lifecycle_faithful=True,
        replay_terminal_closure=True,
    )


def test_recovery_snapshot_uses_bounded_bulk_reads_and_preserves_bytes(
    recovery_source,
) -> None:
    plan, bundle, cycle, old, _outcomes, _started = recovery_source
    counting = _BulkReadCountingLedger()
    counting._artifacts = deepcopy(old._artifacts)
    counting._watch_cases = deepcopy(old._watch_cases)
    counting._scan_runs = deepcopy(old._scan_runs)
    counting._scan_run_events = deepcopy(old._scan_run_events)
    counting._review_tasks = deepcopy(old._review_tasks)

    snapshot = build_final_execution_recovery_snapshot(
        counting,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=PREVIOUS_EXECUTION_ID,
    )

    assert snapshot.snapshot_sha256 == BASELINE_CANCELLED_SNAPSHOT_SHA256
    assert counting.read_calls == {
        "list_watch_cases": 1,
        "list_scan_runs": 1,
        "list_review_tasks_all": 0,
        "get_artifacts": 1,
        "get_watch_case": 0,
        "get_scan_run": 0,
        "get_artifact": 0,
    }


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


def _prior_recovery_receipt_hash(ledger: InMemoryLedger) -> str:
    receipt_id = str(
        uuid5(UUID(RECOVERY_ATTEMPT_ID), "final-execution-recovery-receipt")
    )
    return str(ledger._artifacts[receipt_id]["content_hash"])


def _second_recovery(
    plan,
    cycle,
    snapshot: FinalExecutionRecoverySnapshot,
    *,
    previous_recovery_receipt_hash: str,
):
    return authorize_final_only_recovery(
        plan,
        cycle=cycle,
        recovery_attempt_id=SECOND_RECOVERY_ATTEMPT_ID,
        owner_recovery_reason=FINAL_ONLY_RECOVERY_REASON,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
        previous_snapshot_sha256=snapshot.snapshot_sha256,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=previous_recovery_receipt_hash,
    )


def test_second_generation_snapshot_binds_verified_prior_scope_and_receipt(
    chained_recovery_source,
) -> None:
    plan, bundle, cycle, previous, first_recovery, _started = (
        chained_recovery_source
    )
    snapshot = build_final_execution_recovery_snapshot(
        previous,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(previous),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )
    recovery = _second_recovery(
        plan,
        cycle,
        snapshot,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(previous),
    )
    prior_receipt_id = str(
        uuid5(UUID(RECOVERY_ATTEMPT_ID), "final-execution-recovery-receipt")
    )
    target = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )
    installed = install_final_only_recovery(
        previous_ledger=previous,
        target_ledger=target,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        recovery=recovery,
        source_commit="6" * 40,
        image_digest="sha256:" + "7" * 64,
        cost_snapshot=CostSnapshot(1_500, 1_100),
        now=_started + timedelta(hours=1),
    )
    receipt = parse_artifact(
        target.get_artifact(installed.recovery_receipt_id),
        authorized_producers=PRODUCER_REGISTRY,
    )

    assert len(snapshot.scan_run_artifact_ids) == 456
    assert snapshot.previous_recovery_receipt_id == prior_receipt_id
    assert snapshot.previous_identity_scope == first_recovery.identity_scope
    assert recovery.previous_collection_prefix == first_recovery.collection_prefix
    assert recovery.previous_recovery_attempt_id == RECOVERY_ATTEMPT_ID
    assert recovery.collection_prefix != first_recovery.collection_prefix
    assert prior_receipt_id in receipt.input_artifact_ids
    assert target.read_back_count("watch_cases") == 456
    assert target.read_back_count("scan_runs") == 0

    wrong_shape = deepcopy(target.get_artifact(installed.recovery_receipt_id))
    wrong_shape["previous_state_counts"] = {
        state.value: dict(LEGACY_CANCELLED_STATES).get(state, 0)
        for state in (
            ScanRunState.AUDITING,
            ScanRunState.CREATED,
            ScanRunState.HALTED,
            ScanRunState.NO_ACTION,
            ScanRunState.WATCHING,
        )
    }
    wrong_shape["content_hash"] = content_hash(wrong_shape)
    with pytest.raises(ContractError, match="previous_state_counts"):
        parse_artifact(wrong_shape, authorized_producers=PRODUCER_REGISTRY)


def test_second_generation_snapshot_accepts_exact_live_cancelled_distribution(
    live_chained_recovery_source,
) -> None:
    plan, bundle, cycle, previous, _first_recovery, _started = (
        live_chained_recovery_source
    )

    snapshot = build_final_execution_recovery_snapshot(
        previous,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(previous),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )

    assert snapshot.state_counts == {
        state.value: dict(LIVE_CHAINED_CANCELLED_STATES).get(state, 0)
        for state in ScanRunState
    }
    assert sum(snapshot.state_counts.values()) == 456


def test_live_cancelled_distribution_round_trips_recovery_receipt(
    live_chained_recovery_source,
) -> None:
    plan, bundle, cycle, previous, _first_recovery, started = (
        live_chained_recovery_source
    )
    prior_receipt_hash = _prior_recovery_receipt_hash(previous)
    snapshot = build_final_execution_recovery_snapshot(
        previous,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=prior_receipt_hash,
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )
    recovery = _second_recovery(
        plan,
        cycle,
        snapshot,
        previous_recovery_receipt_hash=prior_receipt_hash,
    )
    target = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )

    installed = install_final_only_recovery(
        previous_ledger=previous,
        target_ledger=target,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        recovery=recovery,
        source_commit="6" * 40,
        image_digest="sha256:" + "7" * 64,
        cost_snapshot=CostSnapshot(1_500, 1_100),
        now=started + timedelta(hours=1),
    )
    receipt = parse_artifact(
        target.get_artifact(installed.recovery_receipt_id),
        authorized_producers=PRODUCER_REGISTRY,
    )

    assert dict(receipt.payload.previous_state_counts) == dict(
        snapshot.state_counts
    )
    assert set(receipt.payload.previous_state_counts) == {
        state.value for state in ScanRunState
    }
    assert target.read_back_count("watch_cases") == 456
    assert target.read_back_count("scan_runs") == 0


def test_second_generation_snapshot_accepts_all_reachable_cancelled_states(
    all_state_chained_recovery_source,
) -> None:
    plan, bundle, cycle, previous, _first_recovery, _started = (
        all_state_chained_recovery_source
    )

    snapshot = build_final_execution_recovery_snapshot(
        previous,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(previous),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )

    assert set(snapshot.state_counts) == {state.value for state in ScanRunState}
    assert snapshot.state_counts[ScanRunState.CREATED.value] == 446
    assert all(
        snapshot.state_counts[state.value] == 1
        for state in ScanRunState
        if state is not ScanRunState.CREATED
    )


def test_second_generation_accepts_replay_terminal_evidence_modes(
    replay_terminal_chained_recovery_source,
) -> None:
    plan, bundle, cycle, previous, _first_recovery, _started = (
        replay_terminal_chained_recovery_source
    )

    snapshot = build_final_execution_recovery_snapshot(
        previous,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(previous),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )
    vcv_by_case = {
        item.case_id: item.vcv for item in cases_for_cycle(cycle)
    }
    observed: set[ScanRunState] = set()
    for run in previous._scan_runs.values():
        case_id = str(previous._artifacts[run.scan_run_artifact_id]["case_id"])
        if vcv_by_case[case_id] is None:
            continue
        artifact_id = (
            run.failure_receipt_ids[0]
            if run.state is ScanRunState.HALTED
            else str(previous._watch_cases[case_id].last_verified_snapshot_id)
        )
        artifact = parse_artifact(
            previous._artifacts[artifact_id],
            authorized_producers=PRODUCER_REGISTRY,
        )
        assert artifact.data_mode is DataMode.CAPTURED_REPLAY
        observed.add(run.state)

    assert observed == {
        ScanRunState.NO_ACTION,
        ScanRunState.REVIEW_REQUIRED,
        ScanRunState.HALTED,
    }
    assert sum(snapshot.state_counts.values()) == 456


@pytest.mark.parametrize(
    "state",
    [
        ScanRunState.NO_ACTION,
        ScanRunState.REVIEW_REQUIRED,
        ScanRunState.HALTED,
    ],
)
def test_second_generation_rejects_wrong_replay_terminal_evidence_mode(
    replay_terminal_chained_recovery_source,
    state: ScanRunState,
) -> None:
    plan, bundle, cycle, source, _first_recovery, started = (
        replay_terminal_chained_recovery_source
    )
    previous = _clone_ledger(source)
    snapshot = build_final_execution_recovery_snapshot(
        source,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )
    run = next(item for item in previous._scan_runs.values() if item.state is state)
    case_id = str(previous._artifacts[run.scan_run_artifact_id]["case_id"])
    assert next(
        item.vcv for item in cases_for_cycle(cycle) if item.case_id == case_id
    ) is not None
    artifact_id = (
        run.failure_receipt_ids[0]
        if state is ScanRunState.HALTED
        else str(previous._watch_cases[case_id].last_verified_snapshot_id)
    )
    wire = deepcopy(previous._artifacts[artifact_id])
    wire["data_mode"] = DataMode.SYNTHETIC.value
    wire["content_hash"] = content_hash(wire)
    previous._artifacts[artifact_id] = wire
    recovery = _second_recovery(
        plan,
        cycle,
        snapshot,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
    )

    _reject_recovery(
        old=previous,
        plan=plan,
        bundle=bundle,
        cycle=cycle,
        recovery=recovery,
        started=started,
        reason="final_recovery_previous_terminal_binding_invalid",
    )


def _rewrite_replay_halt_as_workflow_controller_failure(
    ledger: InMemoryLedger,
    *,
    data_mode: DataMode,
) -> None:
    run = next(
        item for item in ledger._scan_runs.values() if item.state is ScanRunState.HALTED
    )
    ledger._scan_runs[run.run_id] = replace(run, version=8)
    failure_id = run.failure_receipt_ids[0]
    wire = deepcopy(ledger._artifacts[failure_id])
    wire["producer"] = {
        "component": "workflow-controller",
        "version": "0.1.0",
        "identity": "controller-failure-recorder",
    }
    wire["data_mode"] = data_mode.value
    wire["stage"] = "POLICY_EVALUATION"
    wire["content_hash"] = content_hash(wire)
    ledger._artifacts[failure_id] = wire


def _rewrite_replay_halt_as_full_audit_failure(
    ledger: InMemoryLedger,
    *,
    stage: str,
    version: int,
) -> None:
    run = next(
        item for item in ledger._scan_runs.values() if item.state is ScanRunState.HALTED
    )
    ledger._scan_runs[run.run_id] = replace(run, version=version)
    failure_id = run.failure_receipt_ids[0]
    wire = deepcopy(ledger._artifacts[failure_id])
    wire["stage"] = stage
    wire["content_hash"] = content_hash(wire)
    ledger._artifacts[failure_id] = wire


def test_second_generation_accepts_replay_policy_stage_halt_as_synthetic(
    replay_terminal_chained_recovery_source,
) -> None:
    plan, bundle, cycle, source, _first_recovery, _started = (
        replay_terminal_chained_recovery_source
    )
    previous = _clone_ledger(source)
    _rewrite_replay_halt_as_workflow_controller_failure(
        previous,
        data_mode=DataMode.SYNTHETIC,
    )

    snapshot = build_final_execution_recovery_snapshot(
        previous,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(previous),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )

    assert snapshot.state_counts[ScanRunState.HALTED.value] == 1


def test_second_generation_rejects_replay_policy_halt_with_replay_mode(
    replay_terminal_chained_recovery_source,
) -> None:
    plan, bundle, cycle, source, _first_recovery, started = (
        replay_terminal_chained_recovery_source
    )
    previous = _clone_ledger(source)
    snapshot = build_final_execution_recovery_snapshot(
        source,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )
    _rewrite_replay_halt_as_workflow_controller_failure(
        previous,
        data_mode=DataMode.CAPTURED_REPLAY,
    )
    recovery = _second_recovery(
        plan,
        cycle,
        snapshot,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
    )

    _reject_recovery(
        old=previous,
        plan=plan,
        bundle=bundle,
        cycle=cycle,
        recovery=recovery,
        started=started,
        reason="final_recovery_previous_terminal_binding_invalid",
    )


@pytest.mark.parametrize("version", [5, 6, 7])
def test_second_generation_rejects_workflow_policy_halt_before_version_8(
    replay_terminal_chained_recovery_source,
    version: int,
) -> None:
    plan, bundle, cycle, source, _first_recovery, started = (
        replay_terminal_chained_recovery_source
    )
    previous = _clone_ledger(source)
    snapshot = build_final_execution_recovery_snapshot(
        source,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )
    _rewrite_replay_halt_as_workflow_controller_failure(
        previous,
        data_mode=DataMode.SYNTHETIC,
    )
    run = next(
        item for item in previous._scan_runs.values() if item.state is ScanRunState.HALTED
    )
    previous._scan_runs[run.run_id] = replace(run, version=version)
    recovery = _second_recovery(
        plan,
        cycle,
        snapshot,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
    )

    _reject_recovery(
        old=previous,
        plan=plan,
        bundle=bundle,
        cycle=cycle,
        recovery=recovery,
        started=started,
        reason="final_recovery_previous_terminal_binding_invalid",
    )


@pytest.mark.parametrize(
    ("stage", "version"),
    [
        ("EVIDENCE_WATCHER", 6),
        ("EVIDENCE_ASSESSOR", 7),
        ("CITATION_AUDITOR", 8),
    ],
)
def test_second_generation_accepts_full_audit_halt_stage_version_closure(
    replay_terminal_chained_recovery_source,
    stage: str,
    version: int,
) -> None:
    plan, bundle, cycle, source, _first_recovery, _started = (
        replay_terminal_chained_recovery_source
    )
    previous = _clone_ledger(source)
    _rewrite_replay_halt_as_full_audit_failure(
        previous,
        stage=stage,
        version=version,
    )

    snapshot = build_final_execution_recovery_snapshot(
        previous,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(previous),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )

    assert snapshot.state_counts[ScanRunState.HALTED.value] == 1


@pytest.mark.parametrize(
    ("stage", "version"),
    [
        ("UNKNOWN", 6),
        ("UNKNOWN", 7),
        ("UNKNOWN", 8),
        ("EVIDENCE_WATCHER", 7),
        ("EVIDENCE_ASSESSOR", 5),
        ("CITATION_AUDITOR", 6),
    ],
)
def test_second_generation_rejects_full_audit_halt_stage_version_drift(
    replay_terminal_chained_recovery_source,
    stage: str,
    version: int,
) -> None:
    plan, bundle, cycle, source, _first_recovery, started = (
        replay_terminal_chained_recovery_source
    )
    previous = _clone_ledger(source)
    snapshot = build_final_execution_recovery_snapshot(
        source,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )
    _rewrite_replay_halt_as_full_audit_failure(
        previous,
        stage=stage,
        version=version,
    )
    recovery = _second_recovery(
        plan,
        cycle,
        snapshot,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
    )

    _reject_recovery(
        old=previous,
        plan=plan,
        bundle=bundle,
        cycle=cycle,
        recovery=recovery,
        started=started,
        reason="final_recovery_previous_terminal_binding_invalid",
    )


def test_second_generation_uses_one_bounded_review_task_enumeration(
    all_state_chained_recovery_source,
) -> None:
    plan, bundle, cycle, source, _first_recovery, _started = (
        all_state_chained_recovery_source
    )
    counting = _BulkReadCountingLedger()
    counting._privacy_receipt_verifier = source._privacy_receipt_verifier
    counting._artifacts = deepcopy(source._artifacts)
    counting._watch_cases = deepcopy(source._watch_cases)
    counting._scan_runs = deepcopy(source._scan_runs)
    counting._scan_run_events = deepcopy(source._scan_run_events)
    counting._review_tasks = deepcopy(source._review_tasks)

    build_final_execution_recovery_snapshot(
        counting,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )

    assert counting.read_calls == {
        "list_watch_cases": 1,
        "list_scan_runs": 1,
        "list_review_tasks_all": 1,
        "get_artifacts": 1,
        "get_watch_case": 0,
        "get_scan_run": 0,
        "get_artifact": 1,
    }


def test_second_generation_assessing_illegal_pointer_is_zero_write(
    live_chained_recovery_source,
) -> None:
    plan, bundle, cycle, source, _first_recovery, started = (
        live_chained_recovery_source
    )
    previous = _clone_ledger(source)
    snapshot = build_final_execution_recovery_snapshot(
        source,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )
    assessing = next(
        run for run in previous._scan_runs.values()
        if run.state is ScanRunState.ASSESSING
    )
    case_id = str(previous._artifacts[assessing.scan_run_artifact_id]["case_id"])
    previous._watch_cases[case_id] = replace(
        previous._watch_cases[case_id],
        next_scan_at=None,
    )
    recovery = _second_recovery(
        plan,
        cycle,
        snapshot,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
    )

    _reject_recovery(
        old=previous,
        plan=plan,
        bundle=bundle,
        cycle=cycle,
        recovery=recovery,
        started=started,
        reason="final_recovery_previous_watch_pointer_invalid",
    )


def test_second_generation_state_distribution_drift_is_zero_write(
    live_chained_recovery_source,
) -> None:
    plan, bundle, cycle, source, _first_recovery, started = (
        live_chained_recovery_source
    )
    previous = _clone_ledger(source)
    snapshot = build_final_execution_recovery_snapshot(
        source,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )
    created = next(
        run for run in previous._scan_runs.values()
        if run.state is ScanRunState.CREATED
    )
    previous._scan_runs[created.run_id] = replace(
        created,
        state=ScanRunState.QUEUED,
        version=2,
    )
    recovery = _second_recovery(
        plan,
        cycle,
        snapshot,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
    )

    _reject_recovery(
        old=previous,
        plan=plan,
        bundle=bundle,
        cycle=cycle,
        recovery=recovery,
        started=started,
        reason="final_recovery_previous_snapshot_drift",
    )


@pytest.mark.parametrize("state", tuple(ScanRunState))
def test_second_generation_rejects_illegal_pointer_for_every_lifecycle_state(
    all_state_chained_recovery_source,
    state: ScanRunState,
) -> None:
    plan, bundle, cycle, source, _first_recovery, started = (
        all_state_chained_recovery_source
    )
    previous = _clone_ledger(source)
    snapshot = build_final_execution_recovery_snapshot(
        source,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )
    run = next(item for item in previous._scan_runs.values() if item.state is state)
    case_id = str(previous._artifacts[run.scan_run_artifact_id]["case_id"])
    watch = previous._watch_cases[case_id]
    if state is ScanRunState.CREATED:
        previous._scan_runs[run.run_id] = replace(run, version=0)
    elif state is ScanRunState.QUEUED:
        previous._scan_runs[run.run_id] = replace(
            run,
            lease_epoch=1,
            lease_expires_at=started + timedelta(minutes=15),
        )
    elif state is ScanRunState.ROUTING:
        previous._scan_runs[run.run_id] = replace(
            run,
            lease_epoch=0,
            lease_expires_at=None,
        )
    elif state is ScanRunState.WATCHING:
        previous._watch_cases[case_id] = replace(
            watch,
            last_verified_snapshot_id=str(
                uuid5(NAMESPACE_URL, f"invalid:{case_id}")
            ),
        )
    elif state is ScanRunState.ASSESSING:
        previous._watch_cases[case_id] = replace(watch, next_scan_at=None)
    elif state is ScanRunState.AUDITING:
        previous._scan_runs[run.run_id] = replace(
            run,
            terminal_policy_decision_id=str(
                uuid5(NAMESPACE_URL, f"invalid-policy:{run.run_id}")
            ),
        )
    elif state is ScanRunState.POLICY_EVALUATION:
        previous._scan_runs[run.run_id] = replace(
            run,
            failure_receipt_ids=(
                str(uuid5(NAMESPACE_URL, f"invalid-failure:{run.run_id}")),
            ),
        )
    elif state is ScanRunState.NO_ACTION:
        previous._watch_cases[case_id] = replace(
            watch,
            source_cursors=(("synthetic-source", "wrong-cursor"),),
        )
    elif state is ScanRunState.ABSTAIN:
        previous._watch_cases[case_id] = replace(
            watch,
            attention_reason_codes=(),
        )
    elif state is ScanRunState.REVIEW_REQUIRED:
        previous._watch_cases[case_id] = replace(
            watch,
            open_review_task_id=None,
        )
    else:
        previous._scan_runs[run.run_id] = replace(run, failure_receipt_ids=())
    recovery = _second_recovery(
        plan,
        cycle,
        snapshot,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
    )

    _reject_recovery(
        old=previous,
        plan=plan,
        bundle=bundle,
        cycle=cycle,
        recovery=recovery,
        started=started,
        reason=(
            "final_recovery_previous_terminal_binding_invalid"
            if state is ScanRunState.REVIEW_REQUIRED
            else "final_recovery_previous_watch_pointer_invalid"
        ),
    )


def test_second_generation_rejects_dangling_terminal_artifact_pointers(
    all_state_chained_recovery_source,
) -> None:
    plan, bundle, cycle, source, _first_recovery, _started = (
        all_state_chained_recovery_source
    )
    previous = _clone_ledger(source)
    terminal = next(
        run
        for run in previous._scan_runs.values()
        if run.state is ScanRunState.NO_ACTION
    )
    previous._artifacts.pop(str(terminal.terminal_policy_decision_id))

    with pytest.raises(
        RuntimeError, match="final_recovery_previous_terminal_binding_invalid"
    ):
        build_final_execution_recovery_snapshot(
            previous,
            plan=plan,
            cycle=cycle,
            bundle=bundle,
            previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
            previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
            previous_recovery_receipt_hash=_prior_recovery_receipt_hash(previous),
            previous_source_commit=CURRENT_SOURCE_COMMIT,
            previous_image_digest=CURRENT_IMAGE_DIGEST,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "policy_substitution",
        "failure_code_drift",
        "snapshot_cursor_drift",
        "review_task_missing",
        "review_task_extra",
        "review_task_duplicate",
        "review_task_cross_run",
        "review_task_state_drift",
    ],
)
def test_second_generation_terminal_closure_drift_is_zero_write(
    all_state_chained_recovery_source,
    mutation: str,
) -> None:
    plan, bundle, cycle, source, _first_recovery, started = (
        all_state_chained_recovery_source
    )
    previous = _clone_ledger(source)
    snapshot = build_final_execution_recovery_snapshot(
        source,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )
    runs = {run.state: run for run in previous._scan_runs.values()}
    review_run = runs[ScanRunState.REVIEW_REQUIRED]
    review_case = next(
        case
        for case in previous._watch_cases.values()
        if case.open_review_task_id is not None
    )
    task_id = str(review_case.open_review_task_id)
    if mutation == "policy_substitution":
        no_action = runs[ScanRunState.NO_ACTION]
        previous._scan_runs[no_action.run_id] = replace(
            no_action,
            terminal_policy_decision_id=review_run.terminal_policy_decision_id,
        )
    elif mutation == "failure_code_drift":
        halted = runs[ScanRunState.HALTED]
        failure_id = halted.failure_receipt_ids[0]
        wire = deepcopy(previous._artifacts[failure_id])
        wire["failure_code"] = "ledger_integrity_failed"
        wire["content_hash"] = content_hash(wire)
        previous._artifacts[failure_id] = wire
    elif mutation == "snapshot_cursor_drift":
        snapshot_id = str(review_case.last_verified_snapshot_id)
        wire = deepcopy(previous._artifacts[snapshot_id])
        wire["source_cursors"] = {"synthetic-source": "drifted"}
        wire["content_hash"] = content_hash(wire)
        previous._artifacts[snapshot_id] = wire
    elif mutation == "review_task_missing":
        previous._review_tasks.pop(task_id)
    elif mutation == "review_task_extra":
        extra_id = str(uuid5(NAMESPACE_URL, "extra-review-task"))
        previous._review_tasks[extra_id] = replace(
            previous._review_tasks[task_id],
            task_id=extra_id,
            artifact_id=extra_id,
        )
    elif mutation == "review_task_duplicate":
        task = previous._review_tasks[task_id]
        previous.list_review_tasks_all = lambda: (task, task)
    elif mutation == "review_task_cross_run":
        previous._review_tasks[task_id] = replace(
            previous._review_tasks[task_id], run_id=str(uuid5(NAMESPACE_URL, "wrong-run"))
        )
    else:
        previous._review_tasks[task_id] = replace(
            previous._review_tasks[task_id], state="CLOSED"
        )
    recovery = _second_recovery(
        plan,
        cycle,
        snapshot,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
    )

    _reject_recovery(
        old=previous,
        plan=plan,
        bundle=bundle,
        cycle=cycle,
        recovery=recovery,
        started=started,
        reason="final_recovery_previous_terminal_binding_invalid",
    )


def test_second_generation_terminal_artifact_bytes_are_snapshot_bound(
    all_state_chained_recovery_source,
) -> None:
    plan, bundle, cycle, source, _first_recovery, started = (
        all_state_chained_recovery_source
    )
    previous = _clone_ledger(source)
    snapshot = build_final_execution_recovery_snapshot(
        source,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )
    no_action = next(
        run
        for run in previous._scan_runs.values()
        if run.state is ScanRunState.NO_ACTION
    )
    policy_id = str(no_action.terminal_policy_decision_id)
    wire = deepcopy(previous._artifacts[policy_id])
    wire["reason_codes"] = ["same_outcome_different_reason"]
    wire["content_hash"] = content_hash(wire)
    previous._artifacts[policy_id] = wire
    recovery = _second_recovery(
        plan,
        cycle,
        snapshot,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
    )

    _reject_recovery(
        old=previous,
        plan=plan,
        bundle=bundle,
        cycle=cycle,
        recovery=recovery,
        started=started,
        reason="final_recovery_previous_snapshot_drift",
    )


@pytest.mark.parametrize(
    ("state", "mutation"),
    [
        (ScanRunState.CREATED, "repeated_state"),
        (ScanRunState.WATCHING, "lease_takeover"),
        (ScanRunState.POLICY_EVALUATION, "prelease_shortcut"),
        (ScanRunState.NO_ACTION, "terminal_shortcut"),
        (ScanRunState.HALTED, "post_terminal_version"),
        (ScanRunState.HALTED, "preownership_halt"),
        (ScanRunState.HALTED, "routing_halt"),
        (ScanRunState.WATCHING, "expired_lease_boundary"),
    ],
)
def test_second_generation_rejects_non_full_audit_run_pointer_shortcuts(
    all_state_chained_recovery_source,
    state: ScanRunState,
    mutation: str,
) -> None:
    plan, bundle, cycle, source, _first_recovery, started = (
        all_state_chained_recovery_source
    )
    previous = _clone_ledger(source)
    snapshot = build_final_execution_recovery_snapshot(
        source,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )
    run = next(item for item in previous._scan_runs.values() if item.state is state)
    if mutation == "repeated_state":
        changed = replace(
            run,
            version=2,
            last_repeated_state_hash="a" * 64,
            repeated_state_count=1,
        )
    elif mutation == "lease_takeover":
        changed = replace(run, version=5, lease_epoch=2)
    elif mutation == "prelease_shortcut":
        changed = replace(
            run,
            version=3,
            lease_epoch=0,
            lease_expires_at=None,
        )
    elif mutation == "terminal_shortcut":
        changed = replace(
            run,
            version=4,
            lease_epoch=0,
            lease_expires_at=None,
        )
    elif mutation == "preownership_halt":
        changed = replace(
            run,
            version=2,
            lease_epoch=0,
            lease_expires_at=None,
        )
    elif mutation == "routing_halt":
        changed = replace(run, version=4)
    elif mutation == "expired_lease_boundary":
        changed = replace(run, lease_expires_at=run.updated_at)
    else:
        changed = replace(run, version=9)
    previous._scan_runs[run.run_id] = changed
    recovery = _second_recovery(
        plan,
        cycle,
        snapshot,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(source),
    )

    _reject_recovery(
        old=previous,
        plan=plan,
        bundle=bundle,
        cycle=cycle,
        recovery=recovery,
        started=started,
        reason="final_recovery_previous_watch_pointer_invalid",
    )


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("receipt_id", "final_recovery_previous_receipt_missing"),
        ("identity_scope", "final_recovery_previous_receipt_binding_invalid"),
        ("previous_prefix", "final_recovery_previous_receipt_binding_invalid"),
        ("target_prefix", "final_recovery_previous_receipt_binding_invalid"),
        ("target_source", "final_recovery_previous_receipt_binding_invalid"),
        ("target_image", "final_recovery_previous_receipt_binding_invalid"),
        ("target_plan", "final_recovery_previous_receipt_binding_invalid"),
        ("target_bundle", "final_recovery_previous_receipt_binding_invalid"),
        ("cost", "final_recovery_previous_receipt_binding_invalid"),
        ("previous_execution", "final_recovery_previous_receipt_binding_invalid"),
        ("previous_source", "final_recovery_previous_receipt_binding_invalid"),
        ("previous_image", "final_recovery_previous_receipt_binding_invalid"),
        ("previous_snapshot", "final_recovery_previous_receipt_binding_invalid"),
        ("batch_hash", "final_recovery_previous_receipt_binding_invalid"),
        ("cost_lower", "final_recovery_previous_receipt_binding_invalid"),
    ],
)
def test_second_generation_receipt_chain_drift_is_zero_write(
    chained_recovery_source,
    mutation: str,
    error: str,
) -> None:
    plan, bundle, cycle, source, _first_recovery, started = chained_recovery_source
    previous = _clone_ledger(source)
    expected_receipt_hash = _prior_recovery_receipt_hash(source)
    receipt_id = str(
        uuid5(UUID(RECOVERY_ATTEMPT_ID), "final-execution-recovery-receipt")
    )
    wire = deepcopy(previous._artifacts[receipt_id])
    if mutation == "receipt_id":
        previous._artifacts.pop(receipt_id)
    else:
        payload = wire
        if mutation == "identity_scope":
            payload["identity_scope"] = "final-only-recovery:" + "f" * 64
        elif mutation == "previous_prefix":
            payload["previous_collection_prefix"] = "dev_recall_wrong_base_"
        elif mutation == "target_prefix":
            payload["target_collection_prefix"] = "dev_recall_final_wrong_"
        elif mutation == "target_source":
            payload["target_source_commit"] = "1" * 40
        elif mutation == "target_image":
            payload["target_image_digest"] = "sha256:" + "2" * 64
        elif mutation == "target_plan":
            payload["previous_plan_sha256"] = "3" * 64
            payload["target_plan_sha256"] = "3" * 64
            payload["plan_cost_collection"] = "recall_plan6_cost_" + "3" * 16
        elif mutation == "target_bundle":
            payload["previous_bundle_sha256"] = "4" * 64
            payload["target_bundle_sha256"] = "4" * 64
        elif mutation == "cost":
            payload["hard_cap_usd_micros"] += 1
        elif mutation == "previous_execution":
            payload["previous_execution_id"] = "recall-cohort-daily-drifted"
        elif mutation == "previous_source":
            payload["previous_source_commit"] = "5" * 40
        elif mutation == "previous_image":
            payload["previous_image_digest"] = "sha256:" + "6" * 64
        elif mutation == "previous_snapshot":
            payload["previous_snapshot_sha256"] = "7" * 64
        elif mutation == "batch_hash":
            payload["previous_batch_receipt_hash"] = "8" * 64
        else:
            payload["baseline_reserved_usd_micros"] = 0
            payload["baseline_reconciled_usd_micros"] = 0
        wire["content_hash"] = content_hash(wire)
        previous._artifacts[receipt_id] = wire
    target = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )

    with pytest.raises(RuntimeError, match=error):
        snapshot = build_final_execution_recovery_snapshot(
            previous,
            plan=plan,
            cycle=cycle,
            bundle=bundle,
            previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
            previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
            previous_recovery_receipt_hash=expected_receipt_hash,
            previous_source_commit=CURRENT_SOURCE_COMMIT,
            previous_image_digest=CURRENT_IMAGE_DIGEST,
        )
        install_final_only_recovery(
            previous_ledger=previous,
            target_ledger=target,
            plan=plan,
            cycle=cycle,
            bundle=bundle,
            recovery=_second_recovery(
                plan,
                cycle,
                snapshot,
                previous_recovery_receipt_hash=expected_receipt_hash,
            ),
            source_commit="6" * 40,
            image_digest="sha256:" + "7" * 64,
            cost_snapshot=CostSnapshot(1_200, 900),
            now=started + timedelta(hours=1),
        )
    _assert_target_empty(target)


def test_second_generation_snapshot_drift_is_zero_write(
    chained_recovery_source,
) -> None:
    plan, bundle, cycle, previous, _first_recovery, started = (
        chained_recovery_source
    )
    snapshot = build_final_execution_recovery_snapshot(
        previous,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(previous),
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )
    recovery = authorize_final_only_recovery(
        plan,
        cycle=cycle,
        recovery_attempt_id=SECOND_RECOVERY_ATTEMPT_ID,
        owner_recovery_reason=FINAL_ONLY_RECOVERY_REASON,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
        previous_snapshot_sha256="5" * 64,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=_prior_recovery_receipt_hash(previous),
    )
    target = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )

    with pytest.raises(RuntimeError, match="final_recovery_previous_snapshot_drift"):
        install_final_only_recovery(
            previous_ledger=previous,
            target_ledger=target,
            plan=plan,
            cycle=cycle,
            bundle=bundle,
            recovery=recovery,
            source_commit="6" * 40,
            image_digest="sha256:" + "7" * 64,
            cost_snapshot=CostSnapshot(1_200, 900),
            now=started + timedelta(hours=1),
        )
    assert snapshot.snapshot_sha256 != recovery.previous_snapshot_sha256
    _assert_target_empty(target)


def test_second_generation_cost_continuity_drift_is_zero_write(
    chained_recovery_source,
) -> None:
    plan, bundle, cycle, source, _first_recovery, started = chained_recovery_source
    previous = _clone_ledger(source)
    expected_receipt_hash = _prior_recovery_receipt_hash(previous)
    snapshot = build_final_execution_recovery_snapshot(
        previous,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
        previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        previous_recovery_receipt_hash=expected_receipt_hash,
        previous_source_commit=CURRENT_SOURCE_COMMIT,
        previous_image_digest=CURRENT_IMAGE_DIGEST,
    )
    target = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )

    with pytest.raises(RuntimeError, match="final_recovery_cost_continuity_invalid"):
        install_final_only_recovery(
            previous_ledger=previous,
            target_ledger=target,
            plan=plan,
            cycle=cycle,
            bundle=bundle,
            recovery=_second_recovery(
                plan,
                cycle,
                snapshot,
                previous_recovery_receipt_hash=expected_receipt_hash,
            ),
            source_commit="6" * 40,
            image_digest="sha256:" + "7" * 64,
            cost_snapshot=CostSnapshot(1_199, 899),
            now=started + timedelta(hours=1),
        )
    _assert_target_empty(target)


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

    wrong_shape = deepcopy(target.get_artifact(result.recovery_receipt_id))
    wrong_shape["previous_state_counts"] = {
        state.value: dict(LEGACY_CANCELLED_STATES).get(state, 0)
        for state in ScanRunState
    }
    wrong_shape["content_hash"] = content_hash(wrong_shape)
    with pytest.raises(ContractError, match="previous_state_counts"):
        parse_artifact(wrong_shape, authorized_producers=PRODUCER_REGISTRY)


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


def _assert_target_empty(target: InMemoryLedger) -> None:
    assert {name: target.read_back_count(name) for name in COLLECTION_NAMES} == {
        name: 0 for name in COLLECTION_NAMES
    }


def _reject_recovery(
    *,
    old: InMemoryLedger,
    plan,
    bundle,
    cycle,
    recovery,
    started,
    reason: str,
) -> None:
    target = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )
    with pytest.raises(RuntimeError, match=reason):
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
    _assert_target_empty(target)


def test_cancelled_fixture_is_lifecycle_faithful_and_snapshotable(
    recovery_source,
) -> None:
    plan, bundle, cycle, old, outcomes, _started = recovery_source
    observed: dict[ScanRunState, int] = {}
    for outcome in outcomes:
        run = old.get_scan_run(outcome.run_record.run_id)
        watch = old.get_watch_case(outcome.case.case_id)
        assert run is not None and watch is not None
        observed[run.state] = observed.get(run.state, 0) + 1
        if run.state is ScanRunState.HALTED:
            assert watch.state is WatchCaseState.ATTENTION_REQUIRED
            assert watch.next_scan_at is None
            assert run.failure_receipt_ids
        elif run.state is ScanRunState.NO_ACTION:
            assert watch.state is WatchCaseState.ACTIVE
            assert watch.last_verified_snapshot_id is not None
            assert dict(watch.source_cursors) != {
                "synthetic-source": outcome.case.cursor
            }
            assert run.terminal_policy_decision_id is not None
        else:
            assert watch.state is WatchCaseState.ACTIVE
            assert watch.version == 1
    assert observed == {
        ScanRunState.CREATED: 417,
        ScanRunState.HALTED: 14,
        ScanRunState.NO_ACTION: 23,
        ScanRunState.AUDITING: 1,
        ScanRunState.WATCHING: 1,
    }
    build_final_execution_recovery_snapshot(
        old,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=PREVIOUS_EXECUTION_ID,
    )


@pytest.mark.parametrize("mutation", ["missing", "extra", "substituted"])
def test_previous_watch_identity_set_drift_is_zero_write(
    recovery_source, mutation: str
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
    first_id = outcomes[0].case.case_id
    first = old._watch_cases[first_id]
    extra_id = "f99e3d5e-cba3-5f57-bbf3-51e879177f72"
    try:
        if mutation == "missing":
            del old._watch_cases[first_id]
        elif mutation == "extra":
            old._watch_cases[extra_id] = replace(first, watch_case_id=extra_id)
        else:
            second = old._watch_cases[outcomes[1].case.case_id]
            old._watch_cases[first_id] = replace(
                first, artifact_id=second.artifact_id
            )
        _reject_recovery(
            old=old,
            plan=plan,
            bundle=bundle,
            cycle=cycle,
            recovery=recovery,
            started=started,
            reason="final_recovery_previous_watch_set_invalid",
        )
    finally:
        old._watch_cases[first_id] = first
        old._watch_cases.pop(extra_id, None)


@pytest.mark.parametrize(
    "mutation",
    ["tenant", "monitoring_policy", "data_mode", "privacy_receipt"],
)
def test_previous_preparation_material_drift_is_zero_write(
    recovery_source, mutation: str
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
    case_id = outcomes[0].case.case_id
    prepared = next(item for item in bundle.cases if item.case_id == case_id)
    watch_id = str(prepared.watch_case["artifact_id"])
    privacy_id = str(prepared.privacy_receipt["artifact_id"])
    artifact_id = privacy_id if mutation == "privacy_receipt" else watch_id
    original = deepcopy(old._artifacts[artifact_id])
    drifted = deepcopy(original)
    if mutation == "tenant":
        drifted["tenant_id"] = "tenant-substituted"
    elif mutation == "monitoring_policy":
        drifted["monitoring_policy"] = {"policy": "substituted"}
    elif mutation == "data_mode":
        drifted["data_mode"] = "CAPTURED_REPLAY"
    else:
        drifted["warnings"] = ["substituted"]
    drifted["content_hash"] = content_hash(drifted)
    old._artifacts[artifact_id] = drifted
    try:
        _reject_recovery(
            old=old,
            plan=plan,
            bundle=bundle,
            cycle=cycle,
            recovery=recovery,
            started=started,
            reason=(
                "final_recovery_previous_privacy_material_invalid"
                if mutation == "privacy_receipt"
                else "final_recovery_previous_watch_material_invalid"
            ),
        )
    finally:
        old._artifacts[artifact_id] = original


@pytest.mark.parametrize(
    "mutation", ["scheduled_for", "idempotency", "input_closure", "profile"]
)
def test_previous_scan_run_immutable_closure_drift_is_zero_write(
    recovery_source, mutation: str
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
    run = old._scan_runs[outcomes[0].run_record.run_id]
    artifact_id = str(run.scan_run_artifact_id)
    original = deepcopy(old._artifacts[artifact_id])
    drifted = deepcopy(original)
    if mutation == "scheduled_for":
        drifted["scheduled_for"] = "2026-08-30T00:00:00Z"
    elif mutation == "idempotency":
        drifted["idempotency_key"] = "f" * 64
    elif mutation == "input_closure":
        drifted["input_artifact_ids"] = drifted["input_artifact_ids"][:1]
    else:
        drifted["schema_version"] = "1.0.0"
        del drifted["execution_profile"]
    drifted["content_hash"] = content_hash(drifted)
    old._artifacts[artifact_id] = drifted
    try:
        _reject_recovery(
            old=old,
            plan=plan,
            bundle=bundle,
            cycle=cycle,
            recovery=recovery,
            started=started,
            reason="final_recovery_previous_run_binding_invalid",
        )
    finally:
        old._artifacts[artifact_id] = original


def test_extra_previous_scan_run_is_zero_write(recovery_source) -> None:
    plan, bundle, cycle, old, outcomes, started = recovery_source
    snapshot = build_final_execution_recovery_snapshot(
        old,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=PREVIOUS_EXECUTION_ID,
    )
    recovery = _recovery(plan, cycle, snapshot)
    original = old._scan_runs[outcomes[0].run_record.run_id]
    extra_id = str(uuid5(NAMESPACE_URL, "unexpected-previous-scan-run"))
    old._scan_runs[extra_id] = replace(original, run_id=extra_id)
    try:
        _reject_recovery(
            old=old,
            plan=plan,
            bundle=bundle,
            cycle=cycle,
            recovery=recovery,
            started=started,
            reason="final_recovery_previous_run_set_invalid",
        )
    finally:
        del old._scan_runs[extra_id]


def test_embedded_previous_scan_run_id_mismatch_is_zero_write(
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
    run_id = outcomes[0].run_record.run_id
    original = old._scan_runs[run_id]
    old._scan_runs[run_id] = replace(
        original, run_id=str(uuid5(NAMESPACE_URL, "substituted-run-id"))
    )
    try:
        _reject_recovery(
            old=old,
            plan=plan,
            bundle=bundle,
            cycle=cycle,
            recovery=recovery,
            started=started,
            reason="final_recovery_previous_run_set_invalid",
        )
    finally:
        old._scan_runs[run_id] = original


@pytest.mark.parametrize(
    "mutation",
    ["last_repeated_state_hash", "repeated_state_count"],
)
def test_previous_scan_run_loop_pointer_drift_changes_snapshot_and_writes_nothing(
    recovery_source, mutation: str
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
    run_id = outcomes[0].run_record.run_id
    original = old._scan_runs[run_id]
    change = (
        {"last_repeated_state_hash": "f" * 64}
        if mutation == "last_repeated_state_hash"
        else {"repeated_state_count": original.repeated_state_count + 1}
    )
    old._scan_runs[run_id] = replace(original, **change)
    try:
        _reject_recovery(
            old=old,
            plan=plan,
            bundle=bundle,
            cycle=cycle,
            recovery=recovery,
            started=started,
            reason="final_recovery_previous_snapshot_drift",
        )
    finally:
        old._scan_runs[run_id] = original


@pytest.mark.parametrize(
    "mutation",
    ["version", "source_cursor", "snapshot_id", "updated_at"],
)
def test_legal_current_watch_pointer_drift_changes_snapshot_and_writes_nothing(
    recovery_source, mutation: str
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
    outcome = next(
        item
        for item in outcomes
        if old._scan_runs[item.run_record.run_id].state is ScanRunState.NO_ACTION
    )
    case_id = outcome.case.case_id
    original = old._watch_cases[case_id]
    changes = {
        "version": {"version": original.version + 1},
        "source_cursor": {
            "source_cursors": (("synthetic-source", "verified-drift"),)
        },
        "snapshot_id": {
            "last_verified_snapshot_id": str(
                uuid5(NAMESPACE_URL, f"drift:{case_id}")
            )
        },
        "updated_at": {"updated_at": original.updated_at + timedelta(seconds=1)},
    }
    old._watch_cases[case_id] = replace(original, **changes[mutation])
    try:
        _reject_recovery(
            old=old,
            plan=plan,
            bundle=bundle,
            cycle=cycle,
            recovery=recovery,
            started=started,
            reason="final_recovery_previous_snapshot_drift",
        )
    finally:
        old._watch_cases[case_id] = original


@pytest.mark.parametrize("mutation", ["state", "next_scan_at"])
def test_illegal_current_watch_pointer_drift_is_zero_write(
    recovery_source, mutation: str
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
    outcome = next(
        item
        for item in outcomes
        if old._scan_runs[item.run_record.run_id].state is ScanRunState.NO_ACTION
    )
    case_id = outcome.case.case_id
    original = old._watch_cases[case_id]
    change = (
        {"state": WatchCaseState.ATTENTION_REQUIRED}
        if mutation == "state"
        else {"next_scan_at": None}
    )
    old._watch_cases[case_id] = replace(original, **change)
    try:
        _reject_recovery(
            old=old,
            plan=plan,
            bundle=bundle,
            cycle=cycle,
            recovery=recovery,
            started=started,
            reason="final_recovery_previous_watch_pointer_invalid",
        )
    finally:
        old._watch_cases[case_id] = original


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


@pytest.mark.parametrize(
    ("previous_attempt_id", "error"),
    [
        ("not-a-uuid", "final_recovery_attempt_id_invalid"),
        (SECOND_RECOVERY_ATTEMPT_ID, "final_recovery_previous_attempt_invalid"),
    ],
)
def test_previous_recovery_attempt_authority_fails_closed(
    previous_attempt_id: str,
    error: str,
) -> None:
    plan, _bundle, cycle = _plan_bundle()
    with pytest.raises(RuntimeError, match=error):
        authorize_final_only_recovery(
            plan,
            cycle=cycle,
            recovery_attempt_id=SECOND_RECOVERY_ATTEMPT_ID,
            owner_recovery_reason=FINAL_ONLY_RECOVERY_REASON,
            previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
            previous_source_commit=CURRENT_SOURCE_COMMIT,
            previous_image_digest=CURRENT_IMAGE_DIGEST,
            previous_snapshot_sha256="a" * 64,
            previous_recovery_attempt_id=previous_attempt_id,
        )


@pytest.mark.parametrize("previous_attempt_id", [None, RECOVERY_ATTEMPT_ID])
def test_entrypoint_routes_explicit_recovery_to_strict_new_prefix(
    monkeypatch: pytest.MonkeyPatch,
    previous_attempt_id: str | None,
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
    current_attempt_id = (
        RECOVERY_ATTEMPT_ID
        if previous_attempt_id is None
        else SECOND_RECOVERY_ATTEMPT_ID
    )
    argv = [
            "--owner-release-token",
            FINAL_ONLY_OWNER_RELEASE_TOKEN,
            "--owner-release-reason",
            FINAL_ONLY_OWNER_RELEASE_REASON,
            "--recovery-attempt-id",
            current_attempt_id,
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
        ]
    if previous_attempt_id is not None:
        argv.extend(
            [
                "--previous-recovery-attempt-id",
                previous_attempt_id,
                "--previous-recovery-receipt-hash",
                "c" * 64,
            ]
        )
    result = execute(
        argv,
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
    assert result["owner_release"]["recovery_attempt_id"] == current_attempt_id
    assert (
        result["owner_release"]["previous_recovery_attempt_id"]
        == previous_attempt_id
    )
    assert result["owner_release"]["previous_recovery_receipt_hash"] == (
        None if previous_attempt_id is None else "c" * 64
    )
    assert observed["previous"] is not None
    assert recovery.previous_recovery_attempt_id == previous_attempt_id
    if previous_attempt_id is not None:
        assert recovery.previous_recovery_receipt_hash == "c" * 64
        assert recovery.previous_collection_prefix.startswith("dev_recall_final_")


@pytest.mark.parametrize(
    "argv",
    [
        ["--recovery-attempt-id", RECOVERY_ATTEMPT_ID],
        ["--previous-recovery-attempt-id", RECOVERY_ATTEMPT_ID],
        ["--previous-recovery-receipt-hash", "c" * 64],
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


@pytest.mark.parametrize(
    "receipt_hash",
    [None, "A" * 64, "a" * 63, "not-a-hash"],
)
def test_previous_recovery_receipt_hash_authority_fails_closed(
    receipt_hash: str | None,
) -> None:
    plan, _bundle, cycle = _plan_bundle()
    with pytest.raises(
        RuntimeError, match="final_recovery_previous_receipt_hash_invalid"
    ):
        authorize_final_only_recovery(
            plan,
            cycle=cycle,
            recovery_attempt_id=SECOND_RECOVERY_ATTEMPT_ID,
            owner_recovery_reason=FINAL_ONLY_RECOVERY_REASON,
            previous_execution_id=SECOND_PREVIOUS_EXECUTION_ID,
            previous_source_commit=CURRENT_SOURCE_COMMIT,
            previous_image_digest=CURRENT_IMAGE_DIGEST,
            previous_snapshot_sha256="a" * 64,
            previous_recovery_attempt_id=RECOVERY_ATTEMPT_ID,
            previous_recovery_receipt_hash=receipt_hash,
        )
