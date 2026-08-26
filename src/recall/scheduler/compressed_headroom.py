from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from recall.contracts import (
    ArtifactStatus,
    DataMode,
    build_artifact,
    canonical_json_bytes,
    parse_artifact,
)
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY

from .cohort import COHORT_ID
from .compressed_identity import (
    headroom_receipt_id,
    legacy_failure_receipt_id,
    manifest_artifact_id,
    mode_receipt_artifact_id,
    tick_run_id,
)
from .compressed_plan import (
    CompressedCycle,
    CompressedPlan,
    verify_manifest_against_plan,
)


def evaluate_and_persist_headroom(
    *,
    plan: CompressedPlan,
    c6_cycle: CompressedCycle,
    prior_ledgers: Mapping[str, LedgerPort],
    c6_ledger: LedgerPort,
) -> Mapping[str, object]:
    receipt = _build_headroom_receipt(
        plan=plan,
        c6_cycle=c6_cycle,
        prior_ledgers=prior_ledgers,
    )
    existing = c6_ledger.get_artifact(str(receipt["artifact_id"]))
    c6_ledger.append_artifact(receipt)
    persisted = c6_ledger.get_artifact(str(receipt["artifact_id"]))
    if persisted is None or persisted != receipt:
        raise RuntimeError("compressed_headroom_receipt_readback_failed")
    if existing is not None and existing != receipt:
        raise RuntimeError("compressed_headroom_receipt_integrity_failed")
    return receipt


def _build_headroom_receipt(
    *,
    plan: CompressedPlan,
    c6_cycle: CompressedCycle,
    prior_ledgers: Mapping[str, LedgerPort],
) -> Mapping[str, object]:
    if c6_cycle.cycle_id != "c6":
        raise RuntimeError("compressed_headroom_only_c6")
    rows = []
    inputs = set()
    watermarks = []
    for cycle in plan.cycles[:5]:
        ledger = prior_ledgers.get(cycle.cycle_id)
        reasons = []
        manifest_id = manifest_artifact_id(plan, cycle)
        manifest = None if ledger is None else ledger.get_artifact(manifest_id)
        mode_bound = False
        manifest_hash = None
        status = "MISSING"
        created = events = 0
        if manifest is None:
            reasons.append("manifest_missing")
        else:
            inputs.add(manifest_id)
            manifest_hash = str(manifest["content_hash"])
            watermarks.append(str(manifest["created_at"]))
            try:
                parsed = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
                verify_manifest_against_plan(
                    parsed,
                    plan,
                    expected_legacy_failure_receipt_id=legacy_failure_receipt_id(
                        plan, plan.by_id("c1")
                    ),
                )
                status = parsed.status.value
                created = len(parsed.payload.delta["authoritative_run_ids"])
                if (
                    parsed.schema_version != "3.0.0"
                    or parsed.payload.cycle_id != cycle.cycle_id
                    or parsed.payload.plan_sha256 != plan.sha256
                    or parsed.payload.cumulative["historical_incomplete_attempts"] != 1
                ):
                    reasons.append("manifest_contract_mismatch")
                if status != "VALID" or not parsed.payload.delta["prediction_match"]:
                    reasons.append("manifest_not_valid")
            except Exception:
                reasons.append("manifest_parse_failed")
            mode_id = mode_receipt_artifact_id(plan, cycle)
            mode = ledger.get_artifact(mode_id)
            if mode is not None:
                try:
                    parsed_mode = parse_artifact(mode, authorized_producers=PRODUCER_REGISTRY)
                    mode_bound = manifest_id in parsed_mode.payload.subject_artifact_ids
                    if mode_bound:
                        inputs.add(mode_id)
                except Exception:
                    mode_bound = False
            if not mode_bound:
                reasons.append("mode_receipt_missing_or_unbound")
        run_count = 0 if ledger is None else ledger.read_back_count("scan_runs")
        events = 0 if ledger is None else ledger.read_back_count("scan_run_events")
        if run_count != cycle.runs_predicted or created != cycle.runs_predicted:
            reasons.append("run_count_mismatch")
        if events != cycle.runs_predicted:
            reasons.append("event_count_mismatch")
        rows.append(
            {
                "cycle_id": cycle.cycle_id,
                "manifest_artifact_id": manifest_id if manifest is not None else None,
                "manifest_content_hash": manifest_hash,
                "manifest_status": status,
                "runs_predicted": cycle.runs_predicted,
                "runs_created": created,
                "scan_runs_readback": run_count,
                "run_events": events,
                "mode_receipt_bound": mode_bound,
                "reason_codes": sorted(set(reasons)),
            }
        )
    snapshot_value = {
        "plan_sha256": plan.sha256,
        "required_cycle_ids": [item.cycle_id for item in plan.cycles[:5]],
        "observed_cycles": rows,
    }
    snapshot_sha = hashlib.sha256(canonical_json_bytes(snapshot_value)).hexdigest()
    reasons = sorted(
        {f"{row['cycle_id']}:{reason}" for row in rows for reason in row["reason_codes"]}
    )
    predicted = sum(item.runs_predicted for item in plan.cycles[:5])
    created = sum(int(item["runs_created"]) for item in rows)
    events = sum(int(item["run_events"]) for item in rows)
    decision = (
        "PASS"
        if not reasons and predicted == created == events
        else "DENIED"
    )
    watermark = max(watermarks) if watermarks else c6_cycle.schedule_epoch
    receipt = build_artifact(
        schema_name="CohortHeadroomReceipt",
        schema_version="1.0.0",
        artifact_id=headroom_receipt_id(plan, c6_cycle, snapshot_sha),
        case_id=COHORT_ID,
        run_id=tick_run_id(plan, c6_cycle),
        producer={"component": "managed-cohort-scheduler", "version": "3.0.0", "identity": "cohort-scheduler"},
        created_at=watermark,
        input_artifact_ids=tuple(sorted(inputs)),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID if decision == "PASS" else ArtifactStatus.INCOMPLETE,
        payload={
            "plan_sha256": plan.sha256,
            "input_snapshot_sha256": snapshot_sha,
            "gate_version": "1.0.0",
            "required_cycle_ids": [item.cycle_id for item in plan.cycles[:5]],
            "observed_cycles": rows,
            "aggregate_runs_predicted": predicted,
            "aggregate_runs_created": created,
            "aggregate_run_events": events,
            "decision": decision,
            "reason_codes": reasons,
            "evidence_watermark": watermark,
        },
        authorized_producers=PRODUCER_REGISTRY,
    )
    return receipt


def require_headroom_pass(
    receipt: Mapping[str, Any],
    *,
    plan: CompressedPlan,
    c6_cycle: CompressedCycle,
    prior_ledgers: Mapping[str, LedgerPort],
    c6_ledger: LedgerPort,
) -> None:
    expected = _build_headroom_receipt(
        plan=plan,
        c6_cycle=c6_cycle,
        prior_ledgers=prior_ledgers,
    )
    if receipt != expected:
        raise RuntimeError("compressed_headroom_receipt_stale_or_forged")
    persisted = c6_ledger.get_artifact(str(receipt["artifact_id"]))
    if persisted != receipt:
        raise RuntimeError("compressed_headroom_receipt_not_persisted")
    parsed = parse_artifact(receipt, authorized_producers=PRODUCER_REGISTRY)
    if (
        parsed.schema_name != "CohortHeadroomReceipt"
        or parsed.payload.decision != "PASS"
        or parsed.payload.plan_sha256 != plan.sha256
        or parsed.run_id != tick_run_id(plan, c6_cycle)
        or parsed.artifact_id
        != headroom_receipt_id(
            plan, c6_cycle, parsed.payload.input_snapshot_sha256
        )
    ):
        raise RuntimeError("compressed_headroom_denied")
