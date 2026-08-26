from __future__ import annotations

import hashlib
import copy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from recall.contracts import ContractError, content_hash, parse_artifact
from recall.controller.hashes import scan_idempotency_key
from recall.ledger.memory import InMemoryLedger
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.scheduler.compressed import CompressedCycleScheduler
from recall.scheduler.compressed_headroom import (
    evaluate_and_persist_headroom,
    require_headroom_pass,
)
from recall.scheduler.compressed_identity import (
    legacy_failure_receipt_id,
    manifest_artifact_id,
    mode_receipt_artifact_id,
)
from recall.scheduler.compressed_plan import (
    PLAN3_SHA256,
    load_compressed_plan,
    verify_manifest_against_plan,
)
from recall.scheduler.compressed_preparation import (
    DEFAULT_COMPRESSED_BUNDLE_PATH,
    CompressedPreparationVerifier,
    install_prepared_cycle,
    load_compressed_bundle,
)
from recall.scheduler.entrypoint import execute
from recall.scheduler.config import BUDGET_SNAPSHOT


ROOT = Path(__file__).resolve().parents[2]
IMAGE_DIGEST = "sha256:" + "a" * 64
PROJECT_SHA = "b" * 64


class _ScanRunReadbackOverride:
    def __init__(self, ledger, delta: int) -> None:
        self._ledger = ledger
        self._delta = delta

    def __getattr__(self, name):
        return getattr(self._ledger, name)

    def read_back_count(self, collection: str, *, run_id=None) -> int:
        value = self._ledger.read_back_count(collection, run_id=run_id)
        return value + self._delta if collection == "scan_runs" else value


def _loaded():
    plan = load_compressed_plan(ROOT)
    bundle_sha = hashlib.sha256(
        (ROOT / DEFAULT_COMPRESSED_BUNDLE_PATH).read_bytes()
    ).hexdigest()
    bundle = load_compressed_bundle(
        ROOT, expected_sha256=bundle_sha, plan=plan
    )
    return plan, bundle, bundle_sha


def _prepared(cycle_id: str):
    plan, bundle, bundle_sha = _loaded()
    if cycle_id == "c1":
        cycles = list(plan.cycles)
        cycles[0] = replace(cycles[0], write_path="SERIAL_VERIFIED")
        plan = replace(plan, sha256=PLAN3_SHA256, cycles=tuple(cycles))
    cycle = plan.by_id(cycle_id)
    ledger = InMemoryLedger(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )
    install_prepared_cycle(
        ledger, bundle, plan, cycle, now=cycle.window_start
    )
    return plan, bundle, bundle_sha, cycle, ledger


def _run_cycle(cycle_id: str, previous=None):
    plan, bundle, bundle_sha, cycle, ledger = _prepared(cycle_id)
    result = CompressedCycleScheduler(
        ledger,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
    ).trigger(
        now=cycle.window_start,
        previous_manifest=previous,
    )
    return plan, bundle, bundle_sha, cycle, ledger, result


def _serial_c6_context(plan, cycle):
    cycles = list(plan.cycles)
    serial = replace(cycle, write_path="SERIAL_VERIFIED")
    cycles[cycle.cycle_index - 1] = serial
    return replace(plan, cycles=tuple(cycles)), serial


def test_c1_emits_v3_with_visible_failure_and_valid_recovery() -> None:
    plan, _bundle, _sha, cycle, ledger, result = _run_cycle("c1")
    wire = ledger.get_artifact(result.manifest_artifact_id)
    assert wire is not None
    manifest = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
    assert manifest.schema_version == "3.0.0"
    assert manifest.status.value == "VALID"
    assert manifest.payload.cycle_id == "c1"
    assert manifest.payload.plan_sha256 == plan.sha256
    assert manifest.payload.schedule_mode == "COMPRESSED_MACHINE_TRIGGERED"
    history = manifest.payload.execution_history
    assert [item["sequence_index"] for item in history] == [1, 2, 3]
    assert history[1]["execution_status"] == "INCOMPLETE"
    assert history[1]["evidence_state"] == "OWNER_REPORTED"
    assert history[1]["cohort_due_date"] == "2026-08-26"
    assert history[1]["scheduled_for"] == "2026-08-26T16:00:00Z"
    assert history[1]["trigger_code"] == "COHORT_DAY_MANAGED"
    assert history[2]["cohort_due_date"] == "2026-08-26"
    assert history[2]["scheduled_for"] == cycle.schedule_epoch
    assert history[2]["trigger_code"] == "COHORT_COMPRESSED_MACHINE_TRIGGERED"
    assert manifest.payload.cumulative["historical_incomplete_attempts"] == 1
    assert manifest.payload.cumulative["distinct_execution_dates"] == 1
    assert manifest.payload.delta["runs_predicted"] == 3
    assert len(result.newly_created_run_ids) == cycle.runs_predicted


def test_v3_contract_rejects_removal_of_historical_failure() -> None:
    _plan, _bundle, _sha, _cycle, ledger, result = _run_cycle("c1")
    wire = copy.deepcopy(ledger.get_artifact(result.manifest_artifact_id))
    assert wire is not None
    wire["execution_history"] = [
        wire["execution_history"][0],
        {**wire["execution_history"][2], "sequence_index": 2},
    ]
    wire["cumulative"]["historical_incomplete_attempts"] = 0
    wire["content_hash"] = content_hash(wire)
    with pytest.raises(ContractError, match="historical_failure"):
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)


def test_v3_contract_rejects_envelope_time_outside_declared_cycle() -> None:
    _plan, _bundle, _sha, _cycle, ledger, result = _run_cycle("c1")
    wire = copy.deepcopy(ledger.get_artifact(result.manifest_artifact_id))
    assert wire is not None
    wire["created_at"] = "2026-08-26T20:50:00Z"
    wire["content_hash"] = content_hash(wire)
    with pytest.raises(ContractError, match="execution_history.current"):
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)


def test_v3_contract_rejects_relabelled_failure_and_cycle_window() -> None:
    _plan, _bundle, _sha, _cycle, ledger, result = _run_cycle("c1")
    original = ledger.get_artifact(result.manifest_artifact_id)
    assert original is not None
    failure = copy.deepcopy(original)
    failure["execution_history"][1]["scheduled_for"] = "2026-08-26T17:00:00Z"
    failure["content_hash"] = content_hash(failure)
    with pytest.raises(ContractError, match="historical_failure"):
        parse_artifact(failure, authorized_producers=PRODUCER_REGISTRY)

    window = copy.deepcopy(original)
    window["scheduled_for"] = "2026-08-26T20:39:59Z"
    window["window_start"] = "2026-08-26T20:39:59Z"
    window["execution_history"][-1]["scheduled_for"] = "2026-08-26T20:39:59Z"
    window["execution_history"][-1]["window_start"] = "2026-08-26T20:39:59Z"
    window["content_hash"] = content_hash(window)
    parsed = parse_artifact(window, authorized_producers=PRODUCER_REGISTRY)
    with pytest.raises(RuntimeError, match="compressed_manifest_plan_mismatch"):
        verify_manifest_against_plan(
            parsed,
            _plan,
            expected_legacy_failure_receipt_id=legacy_failure_receipt_id(
                _plan, _plan.by_id("c1")
            ),
        )


def test_same_cycle_retry_reuses_runs_manifest_and_events() -> None:
    plan, bundle, _sha, cycle, ledger, first = _run_cycle("c1")
    first_wire = ledger.get_artifact(first.manifest_artifact_id)
    before = (
        ledger.read_back_count("scan_runs"),
        ledger.read_back_count("scan_run_events"),
        ledger.read_back_count("artifacts"),
    )
    second = CompressedCycleScheduler(
        ledger,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
    ).trigger(
        now=datetime(2026, 8, 26, 20, 41, tzinfo=timezone.utc),
        previous_manifest=None,
    )
    assert second.newly_created_run_ids == ()
    assert second.reused_run_ids == first.authoritative_run_ids
    assert ledger.get_artifact(first.manifest_artifact_id) == first_wire
    assert before == (
        ledger.read_back_count("scan_runs"),
        ledger.read_back_count("scan_run_events"),
        ledger.read_back_count("artifacts"),
    )


def test_in_window_late_trigger_is_the_real_admission_and_event_time() -> None:
    plan, bundle, _sha, cycle, ledger = _prepared("c1")
    invoked_at = datetime(2026, 8, 26, 20, 41, 7, tzinfo=timezone.utc)
    result = CompressedCycleScheduler(
        ledger,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
    ).trigger(now=invoked_at, previous_manifest=None)
    expected = "2026-08-26T20:41:07Z"
    for run_id in result.authoritative_run_ids:
        record = ledger.get_scan_run(run_id)
        assert record is not None
        wire = ledger.get_artifact(str(record.scan_run_artifact_id))
        assert wire is not None and wire["created_at"] == expected
        events = ledger.list_scan_run_events(run_id)
        assert len(events) == 1 and events[0].created_at == invoked_at


def test_retry_rejects_changed_provenance_before_run_work() -> None:
    plan, bundle, _sha, cycle, ledger, first = _run_cycle("c1")
    before = {
        name: ledger.read_back_count(name) for name in ledger.collection_names
    }
    with pytest.raises(
        RuntimeError, match="compressed_existing_manifest_context_mismatch"
    ):
        CompressedCycleScheduler(
            ledger,
            plan=plan,
            cycle=cycle,
            bundle=bundle,
            source_commit="c" * 40,
            image_digest=IMAGE_DIGEST,
        ).trigger(now=cycle.window_start, previous_manifest=None)
    assert ledger.get_artifact(first.manifest_artifact_id) is not None
    assert before == {
        name: ledger.read_back_count(name) for name in ledger.collection_names
    }


def test_c2_same_execution_date_has_distinct_epoch_and_predecessor() -> None:
    plan, _bundle, _sha, _c1, c1_ledger, c1_result = _run_cycle("c1")
    c1_manifest = c1_ledger.get_artifact(c1_result.manifest_artifact_id)
    assert c1_manifest is not None
    _plan, _bundle, _sha, c2, c2_ledger, c2_result = _run_cycle(
        "c2", c1_manifest
    )
    parsed = parse_artifact(
        c2_ledger.get_artifact(c2_result.manifest_artifact_id),
        authorized_producers=PRODUCER_REGISTRY,
    )
    assert parsed.payload.previous_manifest_id == c1_result.manifest_artifact_id
    assert parsed.payload.execution_history[-1]["scheduled_for"] == c2.schedule_epoch
    assert parsed.payload.cumulative["distinct_execution_dates"] == 1
    assert parsed.payload.cumulative["logical_days_covered"] == 2
    assert c2_result.manifest_artifact_id != c1_result.manifest_artifact_id


def test_c2_contract_rejects_relabelled_inherited_c1_window() -> None:
    _plan, _bundle, _sha, _c1, c1_ledger, c1_result = _run_cycle("c1")
    c1_manifest = c1_ledger.get_artifact(c1_result.manifest_artifact_id)
    assert c1_manifest is not None
    _plan, _bundle, _sha, _c2, c2_ledger, c2_result = _run_cycle(
        "c2", c1_manifest
    )
    wire = copy.deepcopy(c2_ledger.get_artifact(c2_result.manifest_artifact_id))
    assert wire is not None
    inherited = wire["execution_history"][2]
    inherited["scheduled_for"] = "2026-08-26T20:39:59Z"
    inherited["window_start"] = "2026-08-26T20:39:59Z"
    wire["content_hash"] = content_hash(wire)
    parsed = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
    with pytest.raises(
        RuntimeError, match="compressed_manifest_plan_mismatch"
    ):
        verify_manifest_against_plan(
            parsed,
            _plan,
            expected_legacy_failure_receipt_id=legacy_failure_receipt_id(
                _plan, _plan.by_id("c1")
            ),
        )


def test_epoch_only_and_day1_to_compressed_epoch_change_idempotency_key() -> None:
    fields = {
        "watch_case_id": "b54d172c-d4c7-53d9-b6ea-a8ae154a84d3",
        "source_cursors": {"synthetic-source": "same"},
        "data_mode": "SYNTHETIC",
    }
    day1 = scan_idempotency_key(
        **fields, schedule_epoch="2026-08-25T15:00:00Z"
    )
    compressed = scan_idempotency_key(
        **fields, schedule_epoch="2026-08-26T20:40:00Z"
    )
    adjacent = scan_idempotency_key(
        **fields, schedule_epoch="2026-08-26T21:10:00Z"
    )
    assert len({day1, compressed, adjacent}) == 3


def test_admission_rejects_mismatched_epoch_without_writes() -> None:
    plan, bundle, _sha, cycle, ledger = _prepared("c1")
    case = next(item for item in bundle.cases if item.cycle_id == "c1")
    before = (ledger.read_back_count("scan_runs"), ledger.read_back_count("scan_run_events"))
    record = ledger.get_watch_case(case.case_id)
    assert record is not None
    watch = parse_artifact(
        ledger.get_artifact(record.artifact_id), authorized_producers=PRODUCER_REGISTRY
    )
    with pytest.raises(ContractError, match="watch_case_not_due"):
        CompressedCycleScheduler(
            ledger,
            plan=plan,
            cycle=cycle,
            bundle=bundle,
            source_commit=bundle.source_commit,
            image_digest=IMAGE_DIGEST,
        ).controller.create_run(
            watch_case_id=case.case_id,
            source_cursors=dict(record.source_cursors),
            schedule_epoch="2026-08-26T20:41:00Z",
            data_mode=watch.data_mode,
            privacy_receipt_id=watch.input_artifact_ids[0],
            expected_watch_case_version=record.version,
            triggered_at=cycle.window_start,
            budget_snapshot=BUDGET_SNAPSHOT,
            trace_id="00000000-0000-4000-8000-000000000001",
            deadline_at="2026-08-26T20:49:59Z",
            now=cycle.window_start,
        )
    assert before == (ledger.read_back_count("scan_runs"), ledger.read_back_count("scan_run_events"))


def test_verify_prefix_reads_live_shape_and_writes_zero() -> None:
    plan, bundle, bundle_sha, cycle, ledger = _prepared("c2")
    before = {name: ledger.read_back_count(name) for name in ledger.collection_names}
    calls = []

    def factory(**kwargs):
        calls.append(kwargs["collection_prefix"])
        return ledger

    result = execute(
        ["--verify-prefix", "20260827"],
        environment={
            "RECALL_SCHEDULER_MODE": "COMPRESSED_V3",
            "RECALL_COMPRESSED_PREPARATION_SHA256": bundle_sha,
            "RECALL_SOURCE_COMMIT": bundle.source_commit,
            "RECALL_IMAGE_DIGEST": IMAGE_DIGEST,
            "RECALL_EXPECTED_PROJECT_SHA256": PROJECT_SHA,
        },
        ledger_factory=factory,
        repo_root=ROOT,
    )
    assert result["verified"] is True
    assert result["writes"] == 0
    assert result["plan_sha256"] == plan.sha256
    assert calls == [f"dev_recall_m2_compressed_p{plan.sha256[:12]}_c2_20260827_"]
    assert before == {name: ledger.read_back_count(name) for name in ledger.collection_names}


def test_entrypoint_resolves_cycle_from_clock_without_runtime_override() -> None:
    _old, _old_bundle, _old_sha, _c1, c1_ledger, c1_result = _run_cycle("c1")
    c1_manifest = c1_ledger.get_artifact(c1_result.manifest_artifact_id)
    assert c1_manifest is not None
    plan, bundle, bundle_sha, cycle, ledger = _prepared("c2")

    def factory(**kwargs):
        prefix = kwargs["collection_prefix"]
        if prefix == f"dev_recall_m2_compressed_p{plan.sha256[:12]}_c2_20260827_":
            return ledger
        if prefix == "dev_recall_m2_compressed_p5f18998f11c1_c1_20260826_":
            return c1_ledger
        raise AssertionError(prefix)

    result = execute(
        [],
        environment={
            "RECALL_SCHEDULER_MODE": "COMPRESSED_V3",
            "RECALL_COMPRESSED_PREPARATION_SHA256": bundle_sha,
            "RECALL_SOURCE_COMMIT": bundle.source_commit,
            "RECALL_IMAGE_DIGEST": IMAGE_DIGEST,
            "RECALL_EXPECTED_PROJECT_SHA256": PROJECT_SHA,
        },
        now_factory=lambda: cycle.window_start,
        ledger_factory=factory,
        repo_root=ROOT,
    )
    assert result["cycle_id"] == "c2"
    assert result["schedule_mode"] == "COMPRESSED_MACHINE_TRIGGERED"
    assert result["plan_sha256"] == plan.sha256
    assert len(result["newly_created_run_ids"]) == 2


def test_plan4_c1_is_immutable_and_c6_batch_gate_precedes_writes() -> None:
    plan, bundle, _sha = _loaded()
    for cycle_id, reason in (
        ("c1", "compressed_cycle_external_immutable"),
        ("c6", "compressed_batch_write_path_required"),
    ):
        cycle = plan.by_id(cycle_id)
        ledger = InMemoryLedger(
            privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
        )
        before = tuple(ledger.read_back_count(name) for name in ledger.collection_names)
        with pytest.raises(RuntimeError, match=reason):
            CompressedCycleScheduler(
                ledger,
                plan=plan,
                cycle=cycle,
                bundle=bundle,
                source_commit=bundle.source_commit,
                image_digest=IMAGE_DIGEST,
            ).trigger(now=cycle.window_start, previous_manifest=None)
        assert before == tuple(
            ledger.read_back_count(name) for name in ledger.collection_names
        )


def test_entrypoint_c6_batch_gate_precedes_ledger_construction() -> None:
    plan, bundle, bundle_sha = _loaded()
    c6 = plan.by_id("c6")
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        raise AssertionError("ledger construction is forbidden before batch support")

    with pytest.raises(RuntimeError, match="compressed_batch_write_path_required"):
        execute(
            [],
            environment={
                "RECALL_SCHEDULER_MODE": "COMPRESSED_V3",
                "RECALL_COMPRESSED_PREPARATION_SHA256": bundle_sha,
                "RECALL_SOURCE_COMMIT": bundle.source_commit,
                "RECALL_IMAGE_DIGEST": IMAGE_DIGEST,
                "RECALL_EXPECTED_PROJECT_SHA256": PROJECT_SHA,
            },
            now_factory=lambda: c6.window_start,
            ledger_factory=factory,
            repo_root=ROOT,
        )
    assert calls == []


def test_entrypoint_rejects_premature_cycle_before_ledger_creation() -> None:
    _plan, bundle, bundle_sha, cycle, _ledger = _prepared("c1")
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        raise AssertionError("ledger must not be created outside a declared window")

    with pytest.raises(
        RuntimeError, match="compressed_cycle_window_match_invalid:0"
    ):
        execute(
            [],
            environment={
                "RECALL_SCHEDULER_MODE": "COMPRESSED_V3",
                "RECALL_COMPRESSED_PREPARATION_SHA256": bundle_sha,
                "RECALL_SOURCE_COMMIT": bundle.source_commit,
                "RECALL_IMAGE_DIGEST": IMAGE_DIGEST,
                "RECALL_EXPECTED_PROJECT_SHA256": PROJECT_SHA,
            },
            now_factory=lambda: datetime(
                2026, 8, 26, 20, 39, 59, tzinfo=timezone.utc
            ),
            ledger_factory=factory,
            repo_root=ROOT,
        )
    assert cycle.window_start.isoformat() == "2026-08-26T20:40:00+00:00"
    assert calls == []


def test_entrypoint_requires_explicit_scheduler_mode_before_ledger_creation() -> None:
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        raise AssertionError("ledger must not be created without an explicit mode")

    with pytest.raises(
        RuntimeError,
        match="cohort_required_environment_missing:RECALL_SCHEDULER_MODE",
    ):
        execute(
            [],
            environment={},
            ledger_factory=factory,
            repo_root=ROOT,
        )
    assert calls == []


def test_headroom_denial_is_snapshot_addressed_and_zero_run_write() -> None:
    plan, _bundle, _sha, c6, c6_ledger = _prepared("c6")
    first = evaluate_and_persist_headroom(
        plan=plan, c6_cycle=c6, prior_ledgers={}, c6_ledger=c6_ledger
    )
    with pytest.raises(RuntimeError, match="compressed_headroom_denied"):
        require_headroom_pass(
            first,
            plan=plan,
            c6_cycle=c6,
            prior_ledgers={},
            c6_ledger=c6_ledger,
        )
    count = c6_ledger.read_back_count("artifacts")
    second = evaluate_and_persist_headroom(
        plan=plan, c6_cycle=c6, prior_ledgers={}, c6_ledger=c6_ledger
    )
    assert second == first
    assert c6_ledger.read_back_count("artifacts") == count
    assert c6_ledger.read_back_count("scan_runs") == 0
    assert c6_ledger.read_back_count("scan_run_events") == 0
    assert c6_ledger.get_artifact(manifest_artifact_id(plan, c6)) is None
    assert c6_ledger.get_artifact(mode_receipt_artifact_id(plan, c6)) is None


def test_headroom_denied_then_changed_evidence_creates_distinct_pass_receipt() -> None:
    plan, _bundle, _sha, c6, c6_ledger = _prepared("c6")
    denied = evaluate_and_persist_headroom(
        plan=plan, c6_cycle=c6, prior_ledgers={}, c6_ledger=c6_ledger
    )
    ledgers = {}
    previous = None
    for cycle_id in ("c1", "c2", "c3", "c4", "c5"):
        _plan, _bundle, _sha, cycle, ledger, result = _run_cycle(
            cycle_id, previous
        )
        previous = ledger.get_artifact(result.manifest_artifact_id)
        assert previous is not None
        ledgers[cycle_id] = ledger
    passed = evaluate_and_persist_headroom(
        plan=plan, c6_cycle=c6, prior_ledgers=ledgers, c6_ledger=c6_ledger
    )
    require_headroom_pass(
        passed,
        plan=plan,
        c6_cycle=c6,
        prior_ledgers=ledgers,
        c6_ledger=c6_ledger,
    )
    assert passed["artifact_id"] != denied["artifact_id"]
    assert c6_ledger.get_artifact(str(denied["artifact_id"])) == denied
    assert c6_ledger.get_artifact(str(passed["artifact_id"])) == passed
    parsed = parse_artifact(passed, authorized_producers=PRODUCER_REGISTRY)
    assert parsed.payload.aggregate_runs_predicted == 11
    assert parsed.payload.aggregate_runs_created == 11
    assert parsed.payload.aggregate_run_events == 11


def test_headroom_snapshot_id_changes_with_scan_run_readback() -> None:
    plan, _bundle, _sha, c6, _prepared_c6 = _prepared("c6")
    ledgers = {}
    previous = None
    for cycle_id in ("c1", "c2", "c3", "c4", "c5"):
        _plan, _bundle, _sha, _cycle, ledger, result = _run_cycle(
            cycle_id, previous
        )
        previous = ledger.get_artifact(result.manifest_artifact_id)
        assert previous is not None
        ledgers[cycle_id] = ledger
    exact = evaluate_and_persist_headroom(
        plan=plan,
        c6_cycle=c6,
        prior_ledgers=ledgers,
        c6_ledger=InMemoryLedger(),
    )
    drifted_ledgers = {
        **ledgers,
        "c1": _ScanRunReadbackOverride(ledgers["c1"], 1),
    }
    drifted = evaluate_and_persist_headroom(
        plan=plan,
        c6_cycle=c6,
        prior_ledgers=drifted_ledgers,
        c6_ledger=InMemoryLedger(),
    )
    assert exact["artifact_id"] != drifted["artifact_id"]
    assert exact["input_snapshot_sha256"] != drifted["input_snapshot_sha256"]
    assert exact["observed_cycles"][0]["scan_runs_readback"] == 3
    assert drifted["observed_cycles"][0]["scan_runs_readback"] == 4
    assert drifted["decision"] == "DENIED"


def test_c4_mode_receipt_carries_transitive_replay_provenance() -> None:
    previous = None
    c4_ledger = None
    c4_result = None
    for cycle_id in ("c1", "c2", "c3", "c4"):
        _plan, _bundle, _sha, _cycle, ledger, result = _run_cycle(
            cycle_id, previous
        )
        previous = ledger.get_artifact(result.manifest_artifact_id)
        assert previous is not None
        c4_ledger, c4_result = ledger, result
    assert c4_ledger is not None and c4_result is not None
    receipt = parse_artifact(
        c4_ledger.get_artifact(c4_result.data_mode_receipt_id),
        authorized_producers=PRODUCER_REGISTRY,
    )
    assert receipt.payload.declared_composition == "SYNTHETIC_WITH_CAPTURED_REPLAY"
    assert receipt.payload.mode_set == ("CAPTURED_REPLAY", "SYNTHETIC")


def test_c6_requires_fresh_persisted_headroom_and_binds_manifest() -> None:
    plan, bundle, _sha, c6, c6_ledger = _prepared("c6")
    plan, c6 = _serial_c6_context(plan, c6)
    ledgers = {}
    previous = None
    for cycle_id in ("c1", "c2", "c3", "c4", "c5"):
        _plan, _bundle, _sha, _cycle, ledger, result = _run_cycle(
            cycle_id, previous
        )
        previous = ledger.get_artifact(result.manifest_artifact_id)
        assert previous is not None
        ledgers[cycle_id] = ledger
    receipt = evaluate_and_persist_headroom(
        plan=plan,
        c6_cycle=c6,
        prior_ledgers=ledgers,
        c6_ledger=c6_ledger,
    )
    result = CompressedCycleScheduler(
        c6_ledger,
        plan=plan,
        cycle=c6,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
    ).trigger(
        now=c6.window_start,
        previous_manifest=previous,
        headroom_receipt=receipt,
        headroom_prior_ledgers=ledgers,
    )
    manifest_wire = c6_ledger.get_artifact(result.manifest_artifact_id)
    assert manifest_wire is not None
    manifest = parse_artifact(
        manifest_wire, authorized_producers=PRODUCER_REGISTRY
    )
    assert manifest.payload.headroom_receipt_id == receipt["artifact_id"]
    assert receipt["artifact_id"] in manifest.input_artifact_ids
    mode = parse_artifact(
        c6_ledger.get_artifact(result.data_mode_receipt_id),
        authorized_producers=PRODUCER_REGISTRY,
    )
    assert mode.payload.declared_composition == "SYNTHETIC_WITH_CAPTURED_REPLAY"

    omitted = copy.deepcopy(manifest_wire)
    omitted["headroom_receipt_id"] = None
    omitted["content_hash"] = content_hash(omitted)
    with pytest.raises(ContractError, match="headroom_receipt_id"):
        parse_artifact(omitted, authorized_producers=PRODUCER_REGISTRY)


def test_c6_rejects_unpersisted_and_stale_headroom_without_run_writes() -> None:
    plan, bundle, _sha, c6, c6_ledger = _prepared("c6")
    plan, c6 = _serial_c6_context(plan, c6)
    ledgers = {}
    previous = None
    for cycle_id in ("c1", "c2", "c3", "c4", "c5"):
        _plan, _bundle, _sha, _cycle, ledger, result = _run_cycle(
            cycle_id, previous
        )
        previous = ledger.get_artifact(result.manifest_artifact_id)
        assert previous is not None
        ledgers[cycle_id] = ledger
    detached = InMemoryLedger()
    receipt = evaluate_and_persist_headroom(
        plan=plan,
        c6_cycle=c6,
        prior_ledgers=ledgers,
        c6_ledger=detached,
    )
    before = (
        c6_ledger.read_back_count("scan_runs"),
        c6_ledger.read_back_count("scan_run_events"),
    )
    scheduler = CompressedCycleScheduler(
        c6_ledger,
        plan=plan,
        cycle=c6,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
    )
    with pytest.raises(RuntimeError, match="not_persisted"):
        scheduler.trigger(
            now=c6.window_start,
            previous_manifest=previous,
            headroom_receipt=receipt,
            headroom_prior_ledgers=ledgers,
        )
    assert before == (
        c6_ledger.read_back_count("scan_runs"),
        c6_ledger.read_back_count("scan_run_events"),
    )

    c6_ledger.append_artifact(receipt)
    stale_ledgers = {**ledgers, "c1": InMemoryLedger()}
    with pytest.raises(RuntimeError, match="stale_or_forged"):
        scheduler.trigger(
            now=c6.window_start,
            previous_manifest=previous,
            headroom_receipt=receipt,
            headroom_prior_ledgers=stale_ledgers,
        )
    assert before == (
        c6_ledger.read_back_count("scan_runs"),
        c6_ledger.read_back_count("scan_run_events"),
    )
