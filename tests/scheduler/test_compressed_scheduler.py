from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

from recall.contracts import ContractError, content_hash, parse_artifact
from recall.agents.full_audit import FullAuditCoordinator
from recall.controller.tool_gateway_store import InMemoryGatewayInvocationStore
from recall.ledger import COLLECTION_NAMES
from recall.ledger.memory import InMemoryLedger
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.scheduler.compressed import CompressedCycleScheduler
from recall.scheduler.compressed_cohort import cases_for_cycle
from recall.scheduler.compressed_plan import (
    PLAN3_SHA256,
    PredecessorBinding,
    load_compressed_plan,
)
from recall.scheduler.compressed_preparation import (
    DEFAULT_COMPRESSED_BUNDLE_PATH,
    CompressedPreparationVerifier,
    install_prepared_cycle,
    load_compressed_bundle,
)
from recall.scheduler.compressed_ramp_gate import (
    evaluate_and_persist_ramp_gate,
)
from recall.scheduler.entrypoint import execute
from recall.scheduler.model_cost import (
    DEFAULT_MODEL_COST_POLICY,
    InMemoryModelCostLedger,
)
from tests.agents.full_audit_double import DeterministicFullAuditRunner


ROOT = Path(__file__).resolve().parents[2]
IMAGE_DIGEST = "sha256:" + "a" * 64


class _LiveMemoryLedger(InMemoryLedger):
    def backend_metadata(self):
        return {
            "persistence_surface": "LIVE_FIRESTORE",
            "project_sha256": "test-only",
            "database": "(default)",
        }


def _loaded():
    plan = load_compressed_plan(ROOT)
    bundle_sha = hashlib.sha256(
        (ROOT / DEFAULT_COMPRESSED_BUNDLE_PATH).read_bytes()
    ).hexdigest()
    bundle = load_compressed_bundle(ROOT, expected_sha256=bundle_sha, plan=plan)
    return plan, _test_only_full_audit_receipts(bundle), bundle_sha


def _test_only_full_audit_receipts(bundle):
    """Unit-only receipts; production rows stay legacy and fail closed."""

    cases = []
    for item in bundle.cases:
        if item.cycle_id in {"c3", "c4", "c5", "c6"}:
            receipt = dict(item.privacy_receipt)
            receipt["schema_version"] = "1.1.0"
            gemma = dict(receipt["detectors"]["gemma"])
            gemma.update({"invoked": True, "schema_valid": True})
            receipt["detectors"] = {
                **receipt["detectors"],
                "gemma": gemma,
            }
            receipt.update(
                {
                    "execution_locus": "LAB_LOCAL",
                    "transport_class": "LOCAL_PROCESS",
                    "endpoint_class": "OLLAMA_LOCAL",
                    "model_id": "gemma4:e4b-it-qat",
                    "model_revision": "sha256:" + "a" * 64,
                }
            )
            receipt["content_hash"] = content_hash(receipt)
            item = replace(item, privacy_receipt=receipt)
        cases.append(item)
    return replace(
        bundle,
        cases=tuple(cases),
        privacy_receipt_source_lock={
            "source_sha256": "b" * 64,
            "key_id": "test-only",
            "algorithm": "HMAC-SHA256",
            "key_fingerprint_sha256": "c" * 64,
        },
    )


def _ledger(bundle, *, live=False):
    cls = _LiveMemoryLedger if live else InMemoryLedger
    return cls(privacy_receipt_verifier=CompressedPreparationVerifier(bundle))


def _full_audit(ledger, *, now):
    return FullAuditCoordinator(
        ledger,
        role_runner=DeterministicFullAuditRunner(now=now),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )


def test_committed_legacy_privacy_rows_fail_closed_for_full_audit_cycle() -> None:
    plan = load_compressed_plan(ROOT)
    bundle_sha = hashlib.sha256(
        (ROOT / DEFAULT_COMPRESSED_BUNDLE_PATH).read_bytes()
    ).hexdigest()
    legacy = load_compressed_bundle(
        ROOT, expected_sha256=bundle_sha, plan=plan
    )
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


def _run_legacy_history():
    plan, bundle, _sha = _loaded()
    c1 = replace(plan.by_id("c1"), write_path="SERIAL_VERIFIED")
    plan3 = replace(plan, sha256=PLAN3_SHA256, cycles=(c1, *plan.cycles[1:]))
    l1 = _ledger(bundle)
    install_prepared_cycle(l1, bundle, plan3, c1, now=c1.window_start)
    r1 = CompressedCycleScheduler(
        l1, plan=plan3, cycle=c1, bundle=bundle,
        source_commit=bundle.source_commit, image_digest=IMAGE_DIGEST,
    ).trigger(now=c1.window_start, previous_manifest=None)
    m1 = l1.get_artifact(r1.manifest_artifact_id)
    assert m1 is not None

    c2 = replace(plan.by_id("c2"), write_path="SERIAL_VERIFIED")
    plan2 = replace(plan, cycles=(plan.cycles[0], c2, *plan.cycles[2:]))
    l2 = _ledger(bundle)
    install_prepared_cycle(l2, bundle, plan2, c2, now=c2.window_start)
    r2 = CompressedCycleScheduler(
        l2, plan=plan2, cycle=c2, bundle=bundle,
        source_commit=bundle.source_commit, image_digest=IMAGE_DIGEST,
    ).trigger(now=c2.window_start, previous_manifest=m1)
    m2 = l2.get_artifact(r2.manifest_artifact_id)
    mode2 = l2.get_artifact(r2.data_mode_receipt_id)
    assert m2 is not None and mode2 is not None
    return plan, bundle, l2, m2, mode2


def _bind_test_c2(plan, m2, mode2):
    binding = PredecessorBinding(
        "EXTERNAL_PLAN", "c2", plan.sha256, "test_plan5_c2_",
        str(m2["artifact_id"]), str(m2["content_hash"]),
        str(mode2["artifact_id"]), str(mode2["content_hash"]),
    )
    c3 = replace(plan.by_id("c3"), predecessor=binding)
    return replace(plan, cycles=(*plan.cycles[:2], c3, *plan.cycles[3:])), c3


def _run_c3(*, live=True):
    plan, bundle, predecessor, m2, mode2 = _run_legacy_history()
    plan, c3 = _bind_test_c2(plan, m2, mode2)
    target = _ledger(bundle, live=live)
    install_prepared_cycle(target, bundle, plan, c3, now=c3.window_start)
    gate = evaluate_and_persist_ramp_gate(
        plan=plan, target_cycle=c3, predecessor_ledger=predecessor,
        target_ledger=target, now=c3.window_start,
    )
    result = CompressedCycleScheduler(
        target, plan=plan, cycle=c3, bundle=bundle,
        source_commit=bundle.source_commit, image_digest=IMAGE_DIGEST,
        full_audit_coordinator=_full_audit(target, now=c3.window_start),
    ).trigger(
        now=c3.window_start, previous_manifest=m2, ramp_gate_receipt=gate
    )
    return plan, bundle, c3, target, gate, result


def test_executed_c1_c2_are_immutable_before_ledger_construction() -> None:
    plan, bundle, bundle_sha = _loaded()
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
            repo_root=ROOT,
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
    assert manifest.schema_version == "3.2.0"
    assert manifest.status.value == "VALID"
    assert manifest.payload.epoch_label == "PLAN6_R1_20"
    assert manifest.payload.agent_execution_summary["complete_runs"] == 20
    assert manifest.payload.agent_execution_summary["concurrency"] == 4
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
    assert metrics["total_elapsed_ms"] == metrics["worker_elapsed_ms"] + metrics["readback_elapsed_ms"]
    assert len(result.newly_created_run_ids) == c3.runs_predicted
    assert result.reused_run_ids == ()
    assert result.data_mode_receipt_id is not None


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


def test_non_live_surface_emits_incomplete_manifest_and_no_mode_receipt() -> None:
    _plan, _bundle, _c3, ledger, _gate, result = _run_c3(live=False)
    wire = ledger.get_artifact(result.manifest_artifact_id)
    assert wire is not None
    manifest = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
    assert manifest.status.value == "INCOMPLETE"
    assert result.data_mode_receipt_id is None


def test_cycle_scoped_preparation_identity_differs_for_reassessment() -> None:
    plan, bundle, _sha = _loaded()
    shared = set(item.case_id for item in cases_for_cycle(plan.by_id("c3"))) & set(
        item.case_id for item in cases_for_cycle(plan.by_id("c6"))
    )
    case_id = next(iter(shared))
    rows = [item for item in bundle.cases if item.case_id == case_id and item.cycle_id in {"c3", "c6"}]
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
