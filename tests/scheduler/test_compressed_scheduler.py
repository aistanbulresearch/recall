from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from uuid import NAMESPACE_URL, uuid5

import pytest
import recall.scheduler.compressed as compressed_module

from recall.contracts import AgentRole, ContractError, content_hash, parse_artifact
from recall.agents.full_audit import FullAuditCoordinator
from recall.controller.tool_gateway_store import InMemoryGatewayInvocationStore
from recall.ledger import COLLECTION_NAMES
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.scheduler.compressed import CompressedCycleScheduler
from recall.scheduler.compressed_cohort import cases_for_cycle
from recall.scheduler.compressed_identity import evidence_legacy_failure_receipt_id
from recall.scheduler.compressed_plan import (
    load_compressed_plan,
)
from recall.scheduler.compressed_preparation import (
    DEFAULT_COMPRESSED_BUNDLE_PATH,
    install_prepared_cycle,
    load_compressed_bundle,
)
from recall.scheduler.compressed_ramp_gate import (
    evaluate_and_persist_ramp_gate,
)
from recall.scheduler.compressed_headroom import (
    _build_headroom_receipt,
    evaluate_and_persist_headroom,
)
from recall.scheduler.compressed_plan import verify_manifest_against_plan
from recall.scheduler.entrypoint import execute
from recall.scheduler.history import DAY1_EVIDENCE_PATH
from recall.scheduler.model_cost import (
    DEFAULT_MODEL_COST_POLICY,
    InMemoryModelCostLedger,
)
from tests.agents.full_audit_double import DeterministicFullAuditRunner
from tests.scheduler.compressed_bundle_fixture import (
    load_rebound_test_bundle,
    rebound_bundle_wire,
    write_rebound_test_repo,
)
from tests.support.compressed_v33_manifest import (
    IMAGE_DIGEST,
    bind_test_c2 as _bind_test_c2,
    load_plan_bundle as _loaded,
    make_full_audit as _full_audit,
    make_ledger as _ledger,
    run_c3 as _run_c3,
    run_legacy_history as _run_legacy_history,
)


ROOT = Path(__file__).resolve().parents[2]


def test_bundle_v22_requires_both_external_source_locks(tmp_path) -> None:
    plan = load_compressed_plan(ROOT)
    history_target = tmp_path / DAY1_EVIDENCE_PATH
    history_target.parent.mkdir(parents=True)
    history_target.write_bytes((ROOT / DAY1_EVIDENCE_PATH).read_bytes())
    wire = rebound_bundle_wire(ROOT, plan)
    wire.update(
        {
            "schema_version": "2.2.0",
            "privacy_receipt_source_lock": {
                "source_sha256": "b" * 64,
                "key_id": "test-only",
                "algorithm": "HMAC-SHA256",
                "key_fingerprint_sha256": "c" * 64,
            },
            "lab_note_source_lock": {
                "source_sha256": "d" * 64,
                "schema_version": "1.1.0",
                "notes_version": "test-only",
            },
        }
    )
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(wire), encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()

    loaded = load_compressed_bundle(
        tmp_path,
        expected_sha256=digest,
        plan=plan,
        path=Path("bundle.json"),
    )

    assert loaded.lab_note_source_lock == wire["lab_note_source_lock"]
    wire.pop("lab_note_source_lock")
    path.write_text(json.dumps(wire), encoding="utf-8")
    with pytest.raises(RuntimeError, match="compressed_preparation_plan_mismatch"):
        load_compressed_bundle(
            tmp_path,
            expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            plan=plan,
            path=Path("bundle.json"),
        )


def test_stale_committed_bundle_fails_before_ledger_construction() -> None:
    plan = load_compressed_plan(ROOT)
    bundle_sha = hashlib.sha256(
        (ROOT / DEFAULT_COMPRESSED_BUNDLE_PATH).read_bytes()
    ).hexdigest()
    ledger_constructions = 0

    def construct_ledger() -> None:
        nonlocal ledger_constructions
        ledger_constructions += 1

    with pytest.raises(RuntimeError, match="compressed_preparation_plan_mismatch"):
        load_compressed_bundle(
            ROOT, expected_sha256=bundle_sha, plan=plan
        )
        construct_ledger()
    assert ledger_constructions == 0


def test_legacy_privacy_rows_fail_closed_for_full_audit_without_writes() -> None:
    plan = load_compressed_plan(ROOT)
    legacy, _bundle_sha = load_rebound_test_bundle(ROOT, plan)
    ledger = _ledger(legacy, live=True)
    before = {
        collection: ledger.read_back_count(collection)
        for collection in COLLECTION_NAMES
    }

    with pytest.raises(RuntimeError, match="full_audit_privacy_receipt_required"):
        install_prepared_cycle(
            ledger,
            legacy,
            plan,
            plan.by_id("c3"),
            now=plan.by_id("c3").window_start,
        )
    assert {
        collection: ledger.read_back_count(collection)
        for collection in COLLECTION_NAMES
    } == before


def _coherently_repartition_c3_deadlines(
    wire: dict[str, object],
) -> dict[str, object]:
    mutated = deepcopy(wire)
    deadline = mutated["deadline_policy"]
    assert isinstance(deadline, dict)
    trigger = datetime.fromisoformat(
        str(deadline["trigger_started_at"]).replace("Z", "+00:00")
    )
    write_completed = datetime.fromisoformat(
        str(deadline["write_completed_at"]).replace("Z", "+00:00")
    )
    end_to_end = datetime.fromisoformat(
        str(deadline["authoritative_end_to_end_deadline"]).replace(
            "Z", "+00:00"
        )
    )
    deadline.update(
        {
            "write_timeout_seconds": 3599,
            "write_deadline": min(
                trigger + timedelta(seconds=3599), end_to_end
            ).isoformat().replace("+00:00", "Z"),
            "agent_timeout_seconds": 1,
            "agent_deadline": min(
                write_completed + timedelta(seconds=1), end_to_end
            ).isoformat().replace("+00:00", "Z"),
        }
    )
    mutated["content_hash"] = content_hash(mutated)
    return mutated


def test_executed_c1_c2_are_immutable_before_ledger_construction(
    tmp_path: Path,
) -> None:
    plan = load_compressed_plan(ROOT)
    bundle, bundle_sha = write_rebound_test_repo(ROOT, plan, tmp_path)
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        return _ledger(bundle)

    with pytest.raises(RuntimeError, match="compressed_cycle_external_immutable"):
        execute(
            [],
            environment={
                "RECALL_SCHEDULER_MODE": "COMPRESSED_V3",
                "RECALL_COMPRESSED_PREPARATION_SHA256": bundle_sha,
                "RECALL_SOURCE_COMMIT": bundle.source_commit,
                "RECALL_IMAGE_DIGEST": IMAGE_DIGEST,
                "RECALL_EXPECTED_PROJECT_SHA256": "b" * 64,
            },
            now_factory=lambda: plan.by_id("c2").window_start,
            ledger_factory=factory,
                repo_root=tmp_path,
        )
    assert calls == []


def test_c3_external_binding_denial_is_the_only_target_write() -> None:
    plan, bundle, predecessor, _m2, _mode2 = _run_legacy_history()
    target = _ledger(bundle, live=True)
    c3 = plan.by_id("c3")
    install_prepared_cycle(target, bundle, plan, c3, now=c3.window_start)
    before = {name: target.read_back_count(name) for name in target.collection_names}
    gate = evaluate_and_persist_ramp_gate(
        plan=plan, target_cycle=c3, predecessor_ledger=predecessor,
        target_ledger=target, now=c3.window_start,
    )
    after = {name: target.read_back_count(name) for name in target.collection_names}
    parsed = parse_artifact(gate, authorized_producers=PRODUCER_REGISTRY)
    assert parsed.payload.decision == "DENIED"
    assert after["artifacts"] == before["artifacts"] + 1
    assert after["scan_runs"] == before["scan_runs"] == 0
    assert after["scan_run_events"] == before["scan_run_events"] == 0
    assert after["review_tasks"] == before["review_tasks"] == 0
    assert after["watch_cases"] == before["watch_cases"] == 20


def test_ramp_gate_retry_with_new_clock_reuses_content_addressed_receipt() -> None:
    plan, bundle, predecessor, _m2, _mode2 = _run_legacy_history()
    target = _ledger(bundle, live=True)
    c3 = plan.by_id("c3")
    install_prepared_cycle(target, bundle, plan, c3, now=c3.window_start)
    first = evaluate_and_persist_ramp_gate(
        plan=plan,
        target_cycle=c3,
        predecessor_ledger=predecessor,
        target_ledger=target,
        now=c3.window_start,
    )
    count = target.read_back_count("artifacts")

    second = evaluate_and_persist_ramp_gate(
        plan=plan,
        target_cycle=c3,
        predecessor_ledger=predecessor,
        target_ledger=target,
        now=c3.window_start + timedelta(minutes=1),
    )

    assert second["artifact_id"] == first["artifact_id"]
    assert second["content_hash"] == first["content_hash"]
    assert target.read_back_count("artifacts") == count


def test_r1_manifest_proves_epoch_parity_metrics_and_exact_counts() -> None:
    _plan, _bundle, c3, ledger, gate, result = _run_c3()
    gate_parsed = parse_artifact(gate, authorized_producers=PRODUCER_REGISTRY)
    assert gate_parsed.payload.decision == "PASS"
    wire = ledger.get_artifact(result.manifest_artifact_id)
    assert wire is not None
    manifest = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
    assert manifest.schema_version == "3.3.0"
    assert manifest.status.value == "VALID"
    assert manifest.payload.epoch_label == "PLAN6_R1_20"
    assert manifest.payload.agent_execution_summary["complete_runs"] == 20
    assert manifest.payload.agent_execution_summary["concurrency"] == 2
    assert len(manifest.payload.run_outcomes) == 20
    assert manifest.payload.evaluation_role == "RAMP_FIRST_PASS"
    assert manifest.payload.ramp_gate_receipt_id == gate["artifact_id"]
    assert manifest.payload.parity["actual_newly_created_runs"] == 20
    assert manifest.payload.parity["actual_reused_runs"] == 0
    assert manifest.payload.parity["parity_match"] is True
    metrics = manifest.payload.write_metrics
    assert metrics["selected_case_count"] == 20
    assert metrics["committed_case_documents"] == 60
    assert metrics["ledger_operation_counts"]["create_run_transaction_calls"] == 20
    assert metrics["total_elapsed_ms"] == (
        metrics["worker_elapsed_ms"] + metrics["readback_elapsed_ms"]
    )
    assert len(result.newly_created_run_ids) == c3.runs_predicted
    assert result.reused_run_ids == ()
    assert result.data_mode_receipt_id is not None


def test_halted_agent_outcome_emits_parseable_incomplete_manifest() -> None:
    plan, bundle, predecessor, m2, mode2 = _run_legacy_history()
    plan, c3 = _bind_test_c2(plan, m2, mode2)
    target = _ledger(bundle, live=True)
    install_prepared_cycle(target, bundle, plan, c3, now=c3.window_start)
    gate = evaluate_and_persist_ramp_gate(
        plan=plan,
        target_cycle=c3,
        predecessor_ledger=predecessor,
        target_ledger=target,
        now=c3.window_start,
    )
    failed_case_id = cases_for_cycle(c3)[0].case_id

    class OneHaltedRunner(DeterministicFullAuditRunner):
        async def execute(self, role, prompt, tools, context):
            if (
                role is AgentRole.EVIDENCE_WATCHER
                and context.case_id == failed_case_id
            ):
                raise TimeoutError("one-case synthetic timeout")
            return await super().execute(role, prompt, tools, context)

    coordinator = FullAuditCoordinator(
        target,
        role_runner=OneHaltedRunner(now=c3.window_start),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )
    result = CompressedCycleScheduler(
        target,
        plan=plan,
        cycle=c3,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
        full_audit_coordinator=coordinator,
    ).trigger(
        now=c3.window_start,
        previous_manifest=m2,
        ramp_gate_receipt=gate,
    )

    wire = target.get_artifact(result.manifest_artifact_id)
    assert wire is not None
    manifest = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
    halted = [
        item for item in manifest.payload.run_outcomes
        if item["terminal_state"] == "HALTED"
    ]
    assert manifest.status.value == "INCOMPLETE"
    assert manifest.payload.execution_history[-1]["execution_status"] == "COMPLETE"
    assert manifest.payload.agent_execution_summary["halted_runs"] == 1
    assert manifest.payload.agent_execution_summary["not_evaluated_runs"] == 1
    assert len(halted) == 1
    assert halted[0]["failure_receipt_ids"]
    assert halted[0]["policy_decision_id"] is None
    assert result.data_mode_receipt_id is None


def test_same_epoch_reuses_but_new_epoch_has_distinct_run_identity() -> None:
    plan, bundle, c3, ledger, gate, first = _run_c3()
    previous = _run_legacy_history()[3]
    second = CompressedCycleScheduler(
        ledger, plan=plan, cycle=c3, bundle=bundle,
        source_commit=bundle.source_commit, image_digest=IMAGE_DIGEST,
        full_audit_coordinator=_full_audit(ledger, now=c3.window_start),
    ).trigger(now=c3.window_start, previous_manifest=previous, ramp_gate_receipt=gate)
    assert len(second.reused_run_ids) == 20
    assert second.newly_created_run_ids == ()
    c6_ids = {item.case_id for item in cases_for_cycle(plan.by_id("c6"))}
    overlap = next(item for item in cases_for_cycle(c3) if item.case_id in c6_ids)
    from recall.controller.hashes import scan_idempotency_key
    from recall.contracts import DataMode
    key_r1 = scan_idempotency_key(
        watch_case_id=overlap.case_id,
        source_cursors={"synthetic-source": overlap.cursor},
        schedule_epoch=c3.schedule_epoch,
        data_mode=DataMode.SYNTHETIC.value,
    )
    key_final = scan_idempotency_key(
        watch_case_id=overlap.case_id,
        source_cursors={"synthetic-source": overlap.cursor},
        schedule_epoch=plan.by_id("c6").schedule_epoch,
        data_mode=DataMode.SYNTHETIC.value,
    )
    assert key_r1 != key_final
    assert set(first.newly_created_run_ids).isdisjoint(second.newly_created_run_ids)


def test_same_attempt_recovery_uses_durable_batch_receipt_for_manifest_parity(
    monkeypatch,
) -> None:
    plan, bundle, predecessor, m2, mode2 = _run_legacy_history()
    plan, c3 = _bind_test_c2(plan, m2, mode2)
    target = _ledger(bundle, live=True)
    install_prepared_cycle(target, bundle, plan, c3, now=c3.window_start)
    gate = evaluate_and_persist_ramp_gate(
        plan=plan,
        target_cycle=c3,
        predecessor_ledger=predecessor,
        target_ledger=target,
        now=c3.window_start,
    )
    scheduler = CompressedCycleScheduler(
        target,
        plan=plan,
        cycle=c3,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
        full_audit_coordinator=_full_audit(target, now=c3.window_start),
    )
    real_phase = compressed_module.execute_full_audit_phase

    def crash_after_batch(*_args, **_kwargs):
        raise KeyboardInterrupt("crash after durable batch receipt")

    monkeypatch.setattr(
        compressed_module, "execute_full_audit_phase", crash_after_batch
    )
    with pytest.raises(KeyboardInterrupt, match="durable batch receipt"):
        scheduler.trigger(
            now=c3.window_start,
            previous_manifest=m2,
            ramp_gate_receipt=gate,
        )
    event_count = target.read_back_count("scan_run_events")
    monkeypatch.setattr(
        compressed_module, "execute_full_audit_phase", real_phase
    )

    recovered = scheduler.trigger(
        now=c3.window_start,
        previous_manifest=m2,
        ramp_gate_receipt=gate,
    )
    manifest = parse_artifact(
        target.get_artifact(recovered.manifest_artifact_id),
        authorized_producers=PRODUCER_REGISTRY,
    )
    assert len(recovered.reused_run_ids) == 20
    assert recovered.newly_created_run_ids == ()
    assert target.read_back_count("scan_run_events") > event_count
    assert manifest.status.value == "VALID"
    assert manifest.payload.write_measurement_status == "MEASURED"
    assert manifest.payload.parity["epoch_parity_match"] is True
    assert manifest.payload.parity["fresh_write_parity_match"] is True


def test_partial_pre_receipt_recovery_is_not_reported_as_measured() -> None:
    plan, bundle, predecessor, m2, mode2 = _run_legacy_history()
    plan, c3 = _bind_test_c2(plan, m2, mode2)
    target = _ledger(bundle, live=True)
    install_prepared_cycle(target, bundle, plan, c3, now=c3.window_start)
    gate = evaluate_and_persist_ramp_gate(
        plan=plan,
        target_cycle=c3,
        predecessor_ledger=predecessor,
        target_ledger=target,
        now=c3.window_start,
    )
    scheduler = CompressedCycleScheduler(
        target,
        plan=plan,
        cycle=c3,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
        full_audit_coordinator=_full_audit(target, now=c3.window_start),
    )
    scheduler._create_case(cases_for_cycle(c3)[0], now=c3.window_start)

    result = scheduler.trigger(
        now=c3.window_start,
        previous_manifest=m2,
        ramp_gate_receipt=gate,
    )
    manifest = parse_artifact(
        target.get_artifact(result.manifest_artifact_id),
        authorized_producers=PRODUCER_REGISTRY,
    )
    assert manifest.status.value == "INCOMPLETE"
    assert manifest.payload.write_measurement_status == "NOT_EVALUATED"
    assert manifest.payload.parity["epoch_parity_match"] is True
    assert manifest.payload.parity["fresh_write_parity_match"] is False
    assert result.data_mode_receipt_id is None


def test_r2_remains_provisional_even_after_r1_until_owner_rebinds_plan() -> None:
    plan, bundle, _c3, prior, _gate, r1 = _run_c3()
    previous = prior.get_artifact(r1.manifest_artifact_id)
    assert previous is not None
    c4 = plan.by_id("c4")
    target = _ledger(bundle, live=True)
    install_prepared_cycle(target, bundle, plan, c4, now=c4.window_start)
    before = {name: target.read_back_count(name) for name in target.collection_names}
    with pytest.raises(RuntimeError, match="compressed_cycle_not_active"):
        CompressedCycleScheduler(
            target, plan=plan, cycle=c4, bundle=bundle,
            source_commit=bundle.source_commit, image_digest=IMAGE_DIGEST,
            full_audit_coordinator=_full_audit(target, now=c4.window_start),
        ).trigger(now=c4.window_start, previous_manifest=previous)
    after = {name: target.read_back_count(name) for name in target.collection_names}
    assert after == before


def test_c6_headroom_accepts_v33_ramp_manifest_contract() -> None:
    plan, _bundle, _c3, ledger, _gate, _result = _run_c3()
    receipt = _build_headroom_receipt(
        plan=plan,
        c6_cycle=plan.by_id("c6"),
        prior_ledgers={"c3": ledger},
    )
    parsed = parse_artifact(receipt, authorized_producers=PRODUCER_REGISTRY)
    c3_row = next(
        item
        for item in parsed.payload.observed_cycles
        if item["cycle_id"] == "c3"
    )
    assert "manifest_contract_mismatch" not in c3_row["reason_codes"]
    assert "manifest_parse_failed" not in c3_row["reason_codes"]
    assert "event_chain_invalid" not in c3_row["reason_codes"]
    assert c3_row["run_events"] == 20


def test_c6_headroom_denies_a_broken_full_audit_event_chain() -> None:
    plan, _bundle, _c3, ledger, _gate, result = _run_c3()
    run_id = result.authoritative_run_ids[0]
    final_event = ledger.list_scan_run_events(run_id)[-1]
    ledger._scan_run_events.pop(final_event.event_id)

    receipt = _build_headroom_receipt(
        plan=plan,
        c6_cycle=plan.by_id("c6"),
        prior_ledgers={"c3": ledger},
    )
    parsed = parse_artifact(receipt, authorized_producers=PRODUCER_REGISTRY)
    c3_row = next(
        item for item in parsed.payload.observed_cycles if item["cycle_id"] == "c3"
    )
    assert "event_chain_invalid" in c3_row["reason_codes"]
    assert parsed.payload.decision == "DENIED"


def test_c6_headroom_denies_illegal_event_code_and_missing_batch_receipt() -> None:
    plan, _bundle, _c3, ledger, _gate, result = _run_c3()
    run_id = result.authoritative_run_ids[0]
    final_event = ledger.list_scan_run_events(run_id)[-1]
    ledger._scan_run_events[final_event.event_id] = replace(
        final_event,
        event_code=type(final_event.event_code).TECHNICAL_HALTED,
    )
    manifest = parse_artifact(
        ledger.get_artifact(result.manifest_artifact_id),
        authorized_producers=PRODUCER_REGISTRY,
    )
    ledger._artifacts.pop(manifest.payload.batch_execution_receipt_id)

    receipt = _build_headroom_receipt(
        plan=plan,
        c6_cycle=plan.by_id("c6"),
        prior_ledgers={"c3": ledger},
    )
    parsed = parse_artifact(receipt, authorized_producers=PRODUCER_REGISTRY)
    c3_row = next(
        item for item in parsed.payload.observed_cycles if item["cycle_id"] == "c3"
    )
    assert "event_chain_invalid" in c3_row["reason_codes"]
    assert "batch_receipt_missing_or_unbound" in c3_row["reason_codes"]
    assert parsed.payload.decision == "DENIED"


def test_c6_headroom_denies_coherent_deadline_repartition_without_c6_writes() -> None:
    plan, bundle, _c3, ledger, _gate, result = _run_c3()
    manifest = ledger.get_artifact(result.manifest_artifact_id)
    assert manifest is not None
    ledger._artifacts[result.manifest_artifact_id] = (
        _coherently_repartition_c3_deadlines(manifest)
    )
    c6_ledger = _ledger(bundle, live=True)

    receipt = evaluate_and_persist_headroom(
        plan=plan,
        c6_cycle=plan.by_id("c6"),
        prior_ledgers={"c3": ledger},
        c6_ledger=c6_ledger,
    )
    parsed = parse_artifact(receipt, authorized_producers=PRODUCER_REGISTRY)
    c3_row = next(
        item
        for item in parsed.payload.observed_cycles
        if item["cycle_id"] == "c3"
    )

    assert "manifest_deadline_plan_mismatch" in c3_row["reason_codes"]
    assert parsed.payload.decision == "DENIED"
    assert c6_ledger.read_back_count("artifacts") == 1
    assert c6_ledger.read_back_count("scan_runs") == 0
    assert c6_ledger.read_back_count("scan_run_events") == 0
    assert c6_ledger.read_back_count("review_tasks") == 0
    assert c6_ledger.read_back_count("watch_cases") == 0


def test_existing_manifest_requires_its_durable_batch_receipt_before_retry() -> None:
    plan, bundle, c3, ledger, gate, result = _run_c3()
    manifest = parse_artifact(
        ledger.get_artifact(result.manifest_artifact_id),
        authorized_producers=PRODUCER_REGISTRY,
    )
    receipt_id = manifest.payload.batch_execution_receipt_id
    ledger._artifacts.pop(receipt_id)
    event_count = ledger.read_back_count("scan_run_events")

    scheduler = CompressedCycleScheduler(
        ledger,
        plan=plan,
        cycle=c3,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
        full_audit_coordinator=_full_audit(ledger, now=c3.window_start),
    )
    with pytest.raises(RuntimeError, match="compressed_batch_receipt_missing"):
        scheduler.trigger(
            now=c3.window_start,
            previous_manifest={
                "artifact_id": manifest.payload.previous_manifest_id
            },
            ramp_gate_receipt=gate,
        )
    assert ledger.read_back_count("scan_run_events") == event_count


def test_write_deadline_is_fail_closed_and_retry_does_not_extend_it() -> None:
    plan, bundle, predecessor, m2, mode2 = _run_legacy_history()
    plan, c3 = _bind_test_c2(plan, m2, mode2)
    target = _ledger(bundle, live=True)
    install_prepared_cycle(target, bundle, plan, c3, now=c3.window_start)
    gate = evaluate_and_persist_ramp_gate(
        plan=plan,
        target_cycle=c3,
        predecessor_ledger=predecessor,
        target_ledger=target,
        now=c3.window_start,
    )
    exact_deadline = c3.window_start + timedelta(
        seconds=c3.write_timeout_seconds
    )
    scheduler = CompressedCycleScheduler(
        target,
        plan=plan,
        cycle=c3,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
        full_audit_coordinator=_full_audit(target, now=c3.window_start),
        clock=lambda: exact_deadline,
    )

    for _attempt in range(2):
        with pytest.raises(
            RuntimeError, match="compressed_write_phase_deadline_exceeded"
        ):
            scheduler.trigger(
                now=c3.window_start,
                previous_manifest=m2,
                ramp_gate_receipt=gate,
            )
    checkpoints = [
        item
        for item in target._artifacts.values()
        if item["schema_name"] == "CohortExecutionCheckpoint"
    ]
    assert len(checkpoints) == 1
    assert target.read_back_count("scan_runs") == 0
    assert not any(
        item["schema_name"] == "AgentExecutionReceipt"
        for item in target._artifacts.values()
    )


def test_write_deadline_checkpoint_classifies_partial_durable_creates(
    monkeypatch,
) -> None:
    plan, bundle, predecessor, m2, mode2 = _run_legacy_history()
    plan, c3 = _bind_test_c2(plan, m2, mode2)
    target = _ledger(bundle, live=True)
    install_prepared_cycle(target, bundle, plan, c3, now=c3.window_start)
    gate = evaluate_and_persist_ramp_gate(
        plan=plan,
        target_cycle=c3,
        predecessor_ledger=predecessor,
        target_ledger=target,
        now=c3.window_start,
    )
    scheduler = CompressedCycleScheduler(
        target,
        plan=plan,
        cycle=c3,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
        full_audit_coordinator=_full_audit(target, now=c3.window_start),
    )

    def one_write_then_deadline(cases, **_kwargs):
        scheduler._create_case(cases[0], now=c3.window_start)
        raise compressed_module.WritePhaseDeadlineExceeded(
            "compressed_write_phase_deadline_exceeded"
        )

    monkeypatch.setattr(
        compressed_module, "execute_verified_batch", one_write_then_deadline
    )
    with pytest.raises(
        RuntimeError, match="compressed_write_phase_deadline_exceeded"
    ):
        scheduler.trigger(
            now=c3.window_start,
            previous_manifest=m2,
            ramp_gate_receipt=gate,
        )
    checkpoint = next(
        item
        for item in target._artifacts.values()
        if item["schema_name"] == "CohortExecutionCheckpoint"
    )
    codes = [item["error_code"] for item in checkpoint["failed_cases"]]
    assert codes.count("write_phase_deadline_exceeded_after_durable_create") == 1
    assert codes.count("write_phase_deadline_exceeded_before_create") == 19


@pytest.mark.parametrize(
    ("headroom_passes", "expected_error"),
    ((False, "compressed_headroom_denied"), (True, "batch_path_reached")),
)
def test_c6_trigger_requires_headroom_before_any_case_write(
    monkeypatch, headroom_passes: bool, expected_error: str
) -> None:
    plan, bundle, _sha = _loaded()
    c6 = replace(plan.by_id("c6"), activation="ACTIVE")
    plan = replace(plan, cycles=(*plan.cycles[:5], c6))
    ledger = _ledger(bundle, live=True)
    scheduler = CompressedCycleScheduler(
        ledger,
        plan=plan,
        cycle=c6,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
        full_audit_coordinator=_full_audit(ledger, now=c6.window_start),
    )
    monkeypatch.setattr(compressed_module, "verify_prepared_cycle", lambda *_a: None)
    monkeypatch.setattr(
        compressed_module, "require_ramp_gate_pass", lambda *_a, **_k: None
    )

    def headroom_gate(*_args, **_kwargs):
        if not headroom_passes:
            raise RuntimeError("compressed_headroom_denied")

    def batch_reached(*_args, **_kwargs):
        raise RuntimeError("batch_path_reached")

    monkeypatch.setattr(compressed_module, "require_headroom_pass", headroom_gate)
    monkeypatch.setattr(compressed_module, "execute_verified_batch", batch_reached)

    with pytest.raises(RuntimeError, match=expected_error):
        scheduler.trigger(
            now=c6.window_start,
            previous_manifest={},
            ramp_gate_receipt={},
            headroom_receipt={},
            prior_ledgers={},
        )
    assert ledger.read_back_count("scan_runs") == 0
    assert ledger.read_back_count("scan_run_events") == 0


def test_non_live_surface_emits_incomplete_manifest_and_no_mode_receipt() -> None:
    _plan, _bundle, _c3, ledger, _gate, result = _run_c3(live=False)
    wire = ledger.get_artifact(result.manifest_artifact_id)
    assert wire is not None
    manifest = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
    assert manifest.status.value == "INCOMPLETE"
    assert result.data_mode_receipt_id is None


def test_agent_deadline_overrun_persists_parseable_incomplete_manifest(
    monkeypatch,
) -> None:
    plan, bundle, predecessor, m2, mode2 = _run_legacy_history()
    plan, c3 = _bind_test_c2(plan, m2, mode2)
    target = _ledger(bundle, live=True)
    install_prepared_cycle(target, bundle, plan, c3, now=c3.window_start)
    gate = evaluate_and_persist_ramp_gate(
        plan=plan,
        target_cycle=c3,
        predecessor_ledger=predecessor,
        target_ledger=target,
        now=c3.window_start,
    )
    real_phase = compressed_module.execute_full_audit_phase
    completed_after_deadline = c3.end_to_end_deadline + timedelta(seconds=1)

    def phase_finishing_after_deadline(*args, **kwargs):
        phase = real_phase(*args, **kwargs)
        return replace(
            phase,
            completed_at=completed_after_deadline.isoformat().replace(
                "+00:00", "Z"
            ),
        )

    monkeypatch.setattr(
        compressed_module,
        "execute_full_audit_phase",
        phase_finishing_after_deadline,
    )
    result = CompressedCycleScheduler(
        target,
        plan=plan,
        cycle=c3,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
        full_audit_coordinator=_full_audit(target, now=c3.window_start),
    ).trigger(
        now=c3.window_start,
        previous_manifest=m2,
        ramp_gate_receipt=gate,
    )
    wire = target.get_artifact(result.manifest_artifact_id)
    assert wire is not None
    parsed = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)

    assert parsed.status.value == "INCOMPLETE"
    assert wire["deadline_policy"]["agent_completed_at"] == (
        completed_after_deadline.isoformat().replace("+00:00", "Z")
    )
    assert result.data_mode_receipt_id is None


def test_v33_parser_rejects_coherent_deadline_repartition() -> None:
    _plan, _bundle, _c3, ledger, _gate, result = _run_c3()
    wire = ledger.get_artifact(result.manifest_artifact_id)
    assert wire is not None
    mutated = _coherently_repartition_c3_deadlines(wire)

    with pytest.raises(
        ContractError, match="contract_value_invalid:deadline_policy.plan_binding"
    ):
        parse_artifact(mutated, authorized_producers=PRODUCER_REGISTRY)


def test_v33_parser_rejects_unknown_plan_phase_binding() -> None:
    _plan, _bundle, _c3, ledger, _gate, result = _run_c3()
    wire = deepcopy(ledger.get_artifact(result.manifest_artifact_id))
    assert wire is not None
    wire["plan_sha256"] = "f" * 64
    wire["content_hash"] = content_hash(wire)

    with pytest.raises(
        ContractError, match="contract_value_invalid:deadline_policy.plan_binding"
    ):
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)


def test_plan_verifier_rejects_coherent_deadline_repartition() -> None:
    plan, _bundle, c3, ledger, _gate, result = _run_c3()
    wire = ledger.get_artifact(result.manifest_artifact_id)
    assert wire is not None
    parsed = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
    mutated_wire = _coherently_repartition_c3_deadlines(wire)
    mutated_deadline = MappingProxyType(
        dict(mutated_wire["deadline_policy"])
    )
    mutated_payload = replace(
        parsed.payload,
        deadline_policy=mutated_deadline,
    )
    bypassed_parser = replace(parsed, payload=mutated_payload)

    with pytest.raises(
        RuntimeError, match="compressed_manifest_deadline_plan_mismatch"
    ):
        verify_manifest_against_plan(
            bypassed_parser,
            plan,
            expected_legacy_failure_receipt_id=(
                evidence_legacy_failure_receipt_id(plan)
            ),
        )


def test_v33_manifest_rejects_unbound_authoritative_deadline() -> None:
    _plan, _bundle, _c3, ledger, _gate, result = _run_c3()
    wire = deepcopy(ledger.get_artifact(result.manifest_artifact_id))
    assert wire is not None
    wire["deadline_policy"]["authoritative_end_to_end_deadline"] = wire[
        "window_end"
    ]
    wire["content_hash"] = content_hash(wire)

    with pytest.raises(ContractError, match="contract_value_invalid"):
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)


def test_cycle_scoped_preparation_identity_differs_for_reassessment() -> None:
    plan, bundle, _sha = _loaded()
    shared = set(item.case_id for item in cases_for_cycle(plan.by_id("c3"))) & set(
        item.case_id for item in cases_for_cycle(plan.by_id("c6"))
    )
    case_id = next(iter(shared))
    rows = [
        item
        for item in bundle.cases
        if item.case_id == case_id and item.cycle_id in {"c3", "c6"}
    ]
    assert len(rows) == 2
    assert rows[0].watch_case["artifact_id"] != rows[1].watch_case["artifact_id"]
    assert rows[0].watch_case["next_scan_at"] != rows[1].watch_case["next_scan_at"]


def _v32_wire() -> dict[str, object]:
    _plan, _bundle, _cycle, ledger, _gate, result = _run_c3()
    wire = deepcopy(ledger.get_artifact(result.manifest_artifact_id))
    assert wire is not None
    outcomes = []
    inputs = set(wire["input_artifact_ids"])
    for case_id, run_id in zip(
        wire["delta"]["selected_case_ids"],
        wire["delta"]["authoritative_run_ids"],
        strict=True,
    ):
        citation_id = str(uuid5(NAMESPACE_URL, f"{run_id}:citation"))
        policy_id = str(uuid5(NAMESPACE_URL, f"{run_id}:policy"))
        receipt_ids = sorted(
            [
            str(uuid5(NAMESPACE_URL, f"{run_id}:agent:{index}"))
            for index in range(6)
            ]
        )
        inputs.update((citation_id, policy_id, *receipt_ids))
        outcomes.append(
            {
                "case_id": case_id,
                "run_id": run_id,
                "epoch_label": "PLAN6_R1_20",
                "terminal_state": "NO_ACTION",
                "audit_status": "COMPLETE",
                "citation_audit_receipt_id": citation_id,
                "policy_decision_id": policy_id,
                "policy_outcome": "NO_ACTION",
                "policy_reason_codes": ["no_candidate_delta"],
                "technical_failure_codes": [],
                "failure_receipt_ids": [],
                "agent_execution_receipt_ids": receipt_ids,
                "elapsed_ms": 3000,
            }
        )
    wire["schema_version"] = "3.2.0"
    batch_receipt_id = wire.pop("batch_execution_receipt_id")
    wire.pop("cycle_attempt_id")
    wire.pop("write_measurement_status")
    wire.pop("deadline_policy")
    inputs.discard(batch_receipt_id)
    wire["parity"].pop("epoch_parity_match")
    wire["parity"].pop("fresh_write_parity_match")
    wire["epoch_label"] = "PLAN6_R1_20"
    wire["execution_history"][-1]["source_schema_version"] = (
        "CohortDayManifest/3.2.0"
    )
    wire["input_artifact_ids"] = sorted(inputs)
    wire["agent_execution_summary"] = {
        "execution_profile": "FULL_AUDIT_V1",
        "runtime_class": "IN_PROCESS_ADK_CLOUD_RUN",
        "concurrency": 4,
        "model_id": "gemini-3.7-flash",
        "endpoint_class": "VERTEX_AI_GLOBAL",
        "total_runs": 20,
        "complete_runs": 20,
        "incomplete_runs": 0,
        "not_evaluated_runs": 0,
        "halted_runs": 0,
        "total_agent_invocations": 60,
        "total_prompt_tokens": 6000,
        "total_candidate_tokens": 1200,
        "total_thoughts_tokens": 300,
        "total_tokens": 7500,
        "p50_latency_ms": 900,
        "p95_latency_ms": 1500,
        "http_429_count": 0,
        "projected_cost_usd_micros": 9000,
        "reserved_cost_usd_micros": 12000,
        "pricing_policy_sha256": "f" * 64,
        "actual_billed_cost_state": "NOT_VERIFIED",
    }
    wire["run_outcomes"] = outcomes
    wire["content_hash"] = content_hash(wire)
    return wire


def test_v32_manifest_exposes_full_audit_outcomes_and_telemetry() -> None:
    parsed = parse_artifact(_v32_wire(), authorized_producers=PRODUCER_REGISTRY)

    assert parsed.schema_version == "3.2.0"
    assert parsed.payload.agent_execution_summary["concurrency"] == 4
    assert len(parsed.payload.run_outcomes) == 20
    assert parsed.status.value == "VALID"


def test_v32_manifest_cannot_hide_not_evaluated_audit_behind_valid_status() -> None:
    wire = _v32_wire()
    outcome = wire["run_outcomes"][0]
    outcome["audit_status"] = "NOT_EVALUATED"
    outcome["citation_audit_receipt_id"] = None
    wire["agent_execution_summary"]["complete_runs"] = 19
    wire["agent_execution_summary"]["not_evaluated_runs"] = 1
    wire["status"] = "VALID"
    wire["content_hash"] = content_hash(wire)

    with pytest.raises(ContractError, match="contract_value_invalid"):
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
