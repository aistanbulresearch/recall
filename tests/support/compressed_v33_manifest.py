from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from recall.agents.full_audit import FullAuditCoordinator
from recall.contracts import content_hash, parse_artifact
from recall.controller.tool_gateway_store import InMemoryGatewayInvocationStore
from recall.ledger.memory import InMemoryLedger
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.scheduler.compressed import CompressedCycleScheduler
from recall.scheduler.compressed_identity import (
    evidence_legacy_failure_receipt_id,
)
from recall.scheduler.compressed_plan import (
    PLAN3_SHA256,
    PredecessorBinding,
    load_compressed_plan,
)
from recall.scheduler.compressed_preparation import (
    CompressedPreparationVerifier,
    install_prepared_cycle,
)
from recall.scheduler.compressed_ramp_gate import (
    evaluate_and_persist_ramp_gate,
)
from recall.scheduler.model_cost import (
    DEFAULT_MODEL_COST_POLICY,
    InMemoryModelCostLedger,
)
from tests.agents.full_audit_double import DeterministicFullAuditRunner
from tests.scheduler.compressed_bundle_fixture import load_rebound_test_bundle


REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_DIGEST = "sha256:" + "a" * 64


class LiveMemoryLedger(InMemoryLedger):
    def backend_metadata(self):
        return {
            "persistence_surface": "LIVE_FIRESTORE",
            "project_sha256": "test-only",
            "database": "(default)",
        }


def load_plan_bundle():
    plan = load_compressed_plan(REPO_ROOT)
    bundle, bundle_sha = load_rebound_test_bundle(REPO_ROOT, plan)
    return plan, with_test_full_audit_receipts(bundle), bundle_sha


def with_test_full_audit_receipts(bundle):
    """Return unit-only admitted receipts; production legacy rows stay stale."""

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
        lab_note_source_lock={
            "source_sha256": "d" * 64,
            "schema_version": "1.1.0",
            "notes_version": "test-only",
        },
    )


def make_ledger(bundle, *, live: bool = False):
    ledger_type = LiveMemoryLedger if live else InMemoryLedger
    return ledger_type(
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle)
    )


def make_full_audit(ledger, *, now):
    return FullAuditCoordinator(
        ledger,
        role_runner=DeterministicFullAuditRunner(now=now),
        invocation_store=InMemoryGatewayInvocationStore(),
        cost_ledger=InMemoryModelCostLedger(hard_cap_usd_micros=75_000_000),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
    )


def run_legacy_history():
    plan, bundle, _sha = load_plan_bundle()
    c1 = replace(plan.by_id("c1"), write_path="SERIAL_VERIFIED")
    plan3 = replace(plan, sha256=PLAN3_SHA256, cycles=(c1, *plan.cycles[1:]))
    ledger1 = make_ledger(bundle)
    install_prepared_cycle(
        ledger1, bundle, plan3, c1, now=c1.window_start
    )
    result1 = CompressedCycleScheduler(
        ledger1,
        plan=plan3,
        cycle=c1,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
    ).trigger(now=c1.window_start, previous_manifest=None)
    manifest1 = ledger1.get_artifact(result1.manifest_artifact_id)
    if manifest1 is None:
        raise RuntimeError("test_c1_manifest_missing")

    c2 = replace(plan.by_id("c2"), write_path="SERIAL_VERIFIED")
    plan2 = replace(plan, cycles=(plan.cycles[0], c2, *plan.cycles[2:]))
    ledger2 = make_ledger(bundle)
    install_prepared_cycle(
        ledger2, bundle, plan2, c2, now=c2.window_start
    )
    result2 = CompressedCycleScheduler(
        ledger2,
        plan=plan2,
        cycle=c2,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
    ).trigger(now=c2.window_start, previous_manifest=manifest1)
    manifest2 = ledger2.get_artifact(result2.manifest_artifact_id)
    mode2 = ledger2.get_artifact(result2.data_mode_receipt_id)
    if manifest2 is None or mode2 is None:
        raise RuntimeError("test_c2_artifact_missing")
    return plan, bundle, ledger2, manifest2, mode2


def bind_test_c2(plan, manifest2, mode2):
    binding = PredecessorBinding(
        "EXTERNAL_PLAN",
        "c2",
        plan.sha256,
        "test_plan5_c2_",
        str(manifest2["artifact_id"]),
        str(manifest2["content_hash"]),
        str(mode2["artifact_id"]),
        str(mode2["content_hash"]),
    )
    c3 = replace(plan.by_id("c3"), predecessor=binding)
    return replace(
        plan,
        cycles=(*plan.cycles[:2], c3, *plan.cycles[3:]),
    ), c3


def run_c3(*, live: bool = True):
    plan, bundle, predecessor, manifest2, mode2 = run_legacy_history()
    plan, c3 = bind_test_c2(plan, manifest2, mode2)
    target = make_ledger(bundle, live=live)
    install_prepared_cycle(target, bundle, plan, c3, now=c3.window_start)
    gate = evaluate_and_persist_ramp_gate(
        plan=plan,
        target_cycle=c3,
        predecessor_ledger=predecessor,
        target_ledger=target,
        now=c3.window_start,
    )
    result = CompressedCycleScheduler(
        target,
        plan=plan,
        cycle=c3,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
        full_audit_coordinator=make_full_audit(target, now=c3.window_start),
    ).trigger(
        now=c3.window_start,
        previous_manifest=manifest2,
        ramp_gate_receipt=gate,
    )
    return plan, bundle, c3, target, gate, result


def build_valid_c3_manifest():
    """Return a production-generated, hash-verified V3.3 certification seed."""

    plan, _bundle, cycle, ledger, _gate, result = run_c3()
    wire = ledger.get_artifact(result.manifest_artifact_id)
    if wire is None:
        raise RuntimeError("test_c3_manifest_missing")
    parsed = parse_artifact(
        wire,
        authorized_producers=PRODUCER_REGISTRY,
        verify_hash=True,
    )
    if (
        parsed.schema_name != "CohortDayManifest"
        or parsed.schema_version != "3.3.0"
        or parsed.payload.cycle_id != "c3"
        or parsed.payload.plan_sha256 != plan.sha256
        or cycle.cycle_id != "c3"
    ):
        raise RuntimeError("test_v33_seed_binding_invalid")
    return plan, parsed, evidence_legacy_failure_receipt_id(plan)
