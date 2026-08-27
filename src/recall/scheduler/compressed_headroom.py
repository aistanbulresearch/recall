from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from recall.contracts import (
    ArtifactStatus,
    ContractError,
    DataMode,
    build_artifact,
    canonical_json_bytes,
    parse_artifact,
)
from recall.contracts.enums import ScanRunEventCode
from recall.controller.lifecycle import transition_target
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY

from .cohort import COHORT_ID
from .compressed_identity import (
    evidence_legacy_failure_receipt_id,
    evidence_manifest_artifact_id,
    evidence_mode_receipt_artifact_id,
    evidence_plan,
    headroom_receipt_id,
    tick_run_id,
)
from .compressed_plan import (
    CompressedCycle,
    CompressedPlan,
    ManifestDeadlinePlanMismatch,
    verify_manifest_against_plan,
)
from .compressed_batch_receipt import verify_batch_execution_binding


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
    batch_receipt_snapshots = []
    for cycle in plan.cycles[:5]:
        ledger = prior_ledgers.get(cycle.cycle_id)
        reasons = []
        cycle_plan = evidence_plan(plan, cycle)
        manifest_id = evidence_manifest_artifact_id(plan, cycle)
        manifest = None if ledger is None else ledger.get_artifact(manifest_id)
        mode_bound = False
        manifest_hash = None
        status = "MISSING"
        created = run_created_events = 0
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
                    cycle_plan,
                    expected_legacy_failure_receipt_id=evidence_legacy_failure_receipt_id(
                        plan
                    ),
                )
                status = parsed.status.value
                authoritative_run_ids = tuple(
                    parsed.payload.delta["authoritative_run_ids"]
                )
                created = len(authoritative_run_ids)
                for run_id in authoritative_run_ids:
                    pointer = ledger.get_scan_run(run_id)
                    events = tuple(ledger.list_scan_run_events(run_id))
                    created_events = tuple(
                        event
                        for event in events
                        if event.event_code is ScanRunEventCode.RUN_CREATED
                    )
                    run_created_events += len(created_events)
                    chain_valid = (
                        pointer is not None
                        and len(created_events) == 1
                        and bool(events)
                        and events[0].sequence == 1
                        and events[0].from_state is None
                        and events[0].to_state.value == "CREATED"
                        and events[0].event_code is ScanRunEventCode.RUN_CREATED
                        and len(events) == pointer.version
                        and events[-1].sequence == pointer.version
                        and events[-1].to_state is pointer.state
                    )
                    previous_state = None
                    expected_lease_epoch = 0
                    for sequence, event in enumerate(events, start=1):
                        if event.event_code in {
                            ScanRunEventCode.LEASE_ACQUIRED,
                            ScanRunEventCode.LEASE_TAKEN_OVER,
                        }:
                            if event.lease_epoch <= expected_lease_epoch:
                                chain_valid = False
                                break
                            expected_lease_epoch = event.lease_epoch
                        if (
                            event.sequence != sequence
                            or event.from_state is not previous_state
                            or event.lease_epoch != expected_lease_epoch
                        ):
                            chain_valid = False
                            break
                        try:
                            if transition_target(
                                event.from_state, event.event_code
                            ) is not event.to_state:
                                chain_valid = False
                                break
                        except Exception:
                            chain_valid = False
                            break
                        previous_state = event.to_state
                    if pointer is not None and pointer.lease_epoch != expected_lease_epoch:
                        chain_valid = False
                    if not chain_valid:
                        reasons.append("event_chain_invalid")
                expected_schema = (
                    "3.0.0" if cycle.cycle_index < 3 else "3.3.0"
                )
                if (
                    parsed.schema_version != expected_schema
                    or parsed.payload.cycle_id != cycle.cycle_id
                    or parsed.payload.plan_sha256 != cycle_plan.sha256
                    or parsed.payload.cumulative["historical_incomplete_attempts"] != 1
                ):
                    reasons.append("manifest_contract_mismatch")
                if parsed.schema_version == "3.3.0":
                    try:
                        batch_wire = verify_batch_execution_binding(
                            ledger=ledger,
                            plan=cycle_plan,
                            cycle=cycle,
                            receipt_id=str(
                                parsed.payload.batch_execution_receipt_id
                            ),
                            expected_ordered_run_ids=tuple(
                                parsed.payload.delta["authoritative_run_ids"]
                            ),
                            expected_created_run_ids=tuple(
                                parsed.payload.delta["newly_created_run_ids"]
                            ),
                            expected_recovered_run_ids=tuple(
                                parsed.payload.delta["reused_run_ids"]
                            ),
                            expected_measurement_status=str(
                                parsed.payload.write_measurement_status
                            ),
                            expected_write_metrics=parsed.payload.write_metrics,
                        )
                        batch_receipt_id = str(batch_wire["artifact_id"])
                        inputs.add(batch_receipt_id)
                        batch_receipt_snapshots.append(
                            {
                                "cycle_id": cycle.cycle_id,
                                "artifact_id": batch_receipt_id,
                                "content_hash": str(batch_wire["content_hash"]),
                            }
                        )
                    except Exception:
                        reasons.append("batch_receipt_missing_or_unbound")
                if status != "VALID" or not parsed.payload.delta["prediction_match"]:
                    reasons.append("manifest_not_valid")
            except ContractError as exc:
                if (
                    exc.code == "contract_value_invalid"
                    and exc.detail == "deadline_policy.plan_binding"
                ):
                    reasons.append("manifest_deadline_plan_mismatch")
                else:
                    reasons.append("manifest_parse_failed")
            except ManifestDeadlinePlanMismatch:
                reasons.append("manifest_deadline_plan_mismatch")
            except Exception:
                reasons.append("manifest_parse_failed")
            mode_id = evidence_mode_receipt_artifact_id(plan, cycle)
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
        if run_count != cycle.runs_predicted or created != cycle.runs_predicted:
            reasons.append("run_count_mismatch")
        if run_created_events != cycle.runs_predicted:
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
                # This frozen field means exact RUN_CREATED events, not all
                # lifecycle events emitted by FULL_AUDIT_V1.
                "run_events": run_created_events,
                "mode_receipt_bound": mode_bound,
                "reason_codes": sorted(set(reasons)),
            }
        )
    snapshot_value = {
        "plan_sha256": plan.sha256,
        "required_cycle_ids": [item.cycle_id for item in plan.cycles[:5]],
        "observed_cycles": rows,
        "batch_execution_receipts": batch_receipt_snapshots,
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
