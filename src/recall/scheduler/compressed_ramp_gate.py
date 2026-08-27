from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime, timezone

from recall.contracts import (
    ArtifactStatus,
    DataMode,
    build_artifact,
    canonical_json_bytes,
    parse_artifact,
)
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY

from .compressed_identity import (
    collection_prefix,
    manifest_artifact_id,
    mode_receipt_artifact_id,
    ramp_gate_receipt_id,
    tick_run_id,
)
from .compressed_plan import CompressedCycle, CompressedPlan


ZERO_SHA256 = "0" * 64


def evaluate_and_persist_ramp_gate(
    *,
    plan: CompressedPlan,
    target_cycle: CompressedCycle,
    predecessor_ledger: LedgerPort,
    target_ledger: LedgerPort,
    now: datetime,
) -> dict[str, object]:
    binding = _declared_binding(plan, target_cycle)
    manifest = predecessor_ledger.get_artifact(
        str(binding["manifest_artifact_id"])
    )
    mode = predecessor_ledger.get_artifact(
        str(binding["mode_receipt_artifact_id"])
    )
    observed, reasons = _observe(binding, manifest, mode, predecessor_ledger)
    policy = (
        "PREDECESSOR_INTEGRITY_ONLY"
        if target_cycle.cycle_id == "c3"
        else "RAMP_PARITY_AND_PERFORMANCE"
    )
    if policy == "RAMP_PARITY_AND_PERFORMANCE":
        if observed["newly_created_runs"] != observed["runs_predicted"]:
            reasons.add("new_run_parity_failed")
        if observed["reused_runs"]:
            reasons.add("reused_run_present")
        if observed["authoritative_runs"] != observed["runs_predicted"]:
            reasons.add("prediction_mismatch")
        if observed["effective_write_millis_per_case"] > 2000:
            reasons.add("write_target_exceeded")
        if observed["persistence_surface"] != "LIVE_FIRESTORE":
            reasons.add("non_live_surface")
    snapshot = {
        "target_plan_sha256": plan.sha256,
        "target_cycle_id": target_cycle.cycle_id,
        "metric_policy": policy,
        "predecessor_binding": binding,
        "manifest": manifest,
        "mode_receipt": mode,
        "observed_metrics": observed,
    }
    snapshot_sha = hashlib.sha256(canonical_json_bytes(snapshot)).hexdigest()
    receipt_id = ramp_gate_receipt_id(plan, target_cycle, snapshot_sha)
    existing = target_ledger.get_artifact(receipt_id)
    if existing is not None:
        parsed_existing = parse_artifact(
            existing, authorized_producers=PRODUCER_REGISTRY
        )
        if (
            parsed_existing.schema_name != "CohortRampGateReceipt"
            or parsed_existing.payload.input_snapshot_sha256 != snapshot_sha
            or parsed_existing.payload.target_plan_sha256 != plan.sha256
            or parsed_existing.payload.target_cycle_id != target_cycle.cycle_id
        ):
            raise RuntimeError("compressed_ramp_gate_existing_invalid")
        return existing
    watermark = _timestamp(now)
    inputs = tuple(
        sorted(
            str(item["artifact_id"])
            for item in (manifest, mode)
            if item is not None
        )
    )
    receipt = build_artifact(
        schema_name="CohortRampGateReceipt",
        schema_version="1.0.0",
        artifact_id=receipt_id,
        case_id=None,
        run_id=tick_run_id(plan, target_cycle),
        producer={
            "component": "managed-cohort-scheduler",
            "version": "3.1.0",
            "identity": "cohort-scheduler",
        },
        created_at=watermark,
        input_artifact_ids=inputs,
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID if not reasons else ArtifactStatus.INCOMPLETE,
        payload={
            "target_plan_sha256": plan.sha256,
            "target_cycle_id": target_cycle.cycle_id,
            "input_snapshot_sha256": snapshot_sha,
            "gate_version": "1.0.0",
            "metric_policy": policy,
            "predecessor_binding": binding,
            "observed_metrics": observed,
            "decision": "PASS" if not reasons else "DENIED",
            "reason_codes": sorted(reasons),
            "evidence_watermark": watermark,
        },
        authorized_producers=PRODUCER_REGISTRY,
    )
    target_ledger.append_artifact(receipt)
    persisted = target_ledger.get_artifact(str(receipt["artifact_id"]))
    if persisted is None or persisted["content_hash"] != receipt["content_hash"]:
        raise RuntimeError("compressed_ramp_gate_readback_failed")
    return receipt


def require_ramp_gate_pass(
    receipt: Mapping[str, object],
    *,
    plan: CompressedPlan,
    target_cycle: CompressedCycle,
    target_ledger: LedgerPort,
) -> None:
    parsed = parse_artifact(receipt, authorized_producers=PRODUCER_REGISTRY)
    persisted = target_ledger.get_artifact(parsed.artifact_id)
    if (
        parsed.schema_name != "CohortRampGateReceipt"
        or parsed.payload.target_plan_sha256 != plan.sha256
        or parsed.payload.target_cycle_id != target_cycle.cycle_id
        or persisted is None
        or persisted["content_hash"] != parsed.content_hash
    ):
        raise RuntimeError("compressed_ramp_gate_stale_or_unpersisted")
    if parsed.payload.decision != "PASS":
        raise RuntimeError("compressed_ramp_gate_denied")


def _declared_binding(
    plan: CompressedPlan, target: CompressedCycle
) -> dict[str, object]:
    predecessor = target.predecessor
    if predecessor is None:
        raise RuntimeError("compressed_ramp_predecessor_missing")
    if predecessor.binding == "EXTERNAL_PLAN":
        assert predecessor.plan_sha256 is not None
        assert predecessor.collection_prefix is not None
        assert predecessor.manifest_artifact_id is not None
        assert predecessor.manifest_content_hash is not None
        assert predecessor.mode_receipt_artifact_id is not None
        assert predecessor.mode_receipt_content_hash is not None
        return {
            "plan_sha256": predecessor.plan_sha256,
            "collection_prefix": predecessor.collection_prefix,
            "cycle_id": predecessor.cycle_id,
            "manifest_artifact_id": predecessor.manifest_artifact_id,
            "manifest_content_hash": predecessor.manifest_content_hash,
            "mode_receipt_artifact_id": predecessor.mode_receipt_artifact_id,
            "mode_receipt_content_hash": predecessor.mode_receipt_content_hash,
        }
    prior = plan.by_id(predecessor.cycle_id)
    return {
        "plan_sha256": plan.sha256,
        "collection_prefix": collection_prefix(plan, prior),
        "cycle_id": prior.cycle_id,
        "manifest_artifact_id": manifest_artifact_id(plan, prior),
        "manifest_content_hash": ZERO_SHA256,
        "mode_receipt_artifact_id": mode_receipt_artifact_id(plan, prior),
        "mode_receipt_content_hash": ZERO_SHA256,
    }


def _observe(
    binding: dict[str, object],
    manifest: Mapping[str, object] | None,
    mode: Mapping[str, object] | None,
    ledger: LedgerPort,
) -> tuple[dict[str, object], set[str]]:
    reasons: set[str] = set()
    expected_manifest_hash = str(binding["manifest_content_hash"])
    expected_mode_hash = str(binding["mode_receipt_content_hash"])
    if manifest is None:
        reasons.add("manifest_missing")
    elif expected_manifest_hash != ZERO_SHA256 and manifest["content_hash"] != expected_manifest_hash:
        reasons.add("manifest_hash_mismatch")
    if mode is None:
        reasons.add("mode_receipt_missing")
    elif expected_mode_hash != ZERO_SHA256 and mode["content_hash"] != expected_mode_hash:
        reasons.add("mode_receipt_hash_mismatch")
    predicted = created = reused = authoritative = documents = total_ms = effective = 0
    try:
        if manifest is not None:
            parsed = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
            if parsed.status is not ArtifactStatus.VALID:
                reasons.add("manifest_invalid")
            predicted = int(parsed.payload.delta["runs_predicted"])
            created = len(parsed.payload.delta["newly_created_run_ids"])
            reused = len(parsed.payload.delta["reused_run_ids"])
            authoritative = len(parsed.payload.delta["authoritative_run_ids"])
            if parsed.schema_version in {"3.1.0", "3.2.0"}:
                metrics = parsed.payload.write_metrics
                documents = int(metrics["committed_case_documents"])
                total_ms = int(metrics["total_elapsed_ms"])
                effective = int(metrics["effective_write_millis_per_case"])
            else:
                documents = created * 3
    except Exception:
        reasons.add("manifest_invalid")
    try:
        if mode is not None:
            parsed_mode = parse_artifact(mode, authorized_producers=PRODUCER_REGISTRY)
            if (
                parsed_mode.schema_name != "DataModeReceipt"
                or str(binding["manifest_artifact_id"])
                not in parsed_mode.payload.subject_artifact_ids
            ):
                reasons.add("mode_receipt_unbound")
    except Exception:
        reasons.add("mode_receipt_unbound")
    if manifest is not None and expected_manifest_hash == ZERO_SHA256:
        binding["manifest_content_hash"] = str(manifest["content_hash"])
    if mode is not None and expected_mode_hash == ZERO_SHA256:
        binding["mode_receipt_content_hash"] = str(mode["content_hash"])
    surface = str(ledger.backend_metadata().get("persistence_surface", "UNKNOWN"))
    return {
        "runs_predicted": predicted,
        "newly_created_runs": created,
        "reused_runs": reused,
        "authoritative_runs": authoritative,
        "persistence_surface": surface,
        "committed_case_documents": documents,
        "total_elapsed_ms": total_ms,
        "effective_write_millis_per_case": effective,
    }, reasons


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
