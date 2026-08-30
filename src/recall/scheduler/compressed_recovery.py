from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from recall.contracts import (
    ArtifactStatus,
    ContractError,
    DataMode,
    build_artifact,
    canonical_json_bytes,
    parse_artifact,
)
from recall.contracts.enums import ScanRunState
from recall.controller.hashes import scan_idempotency_key
from recall.ledger.models import COLLECTION_NAMES
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY

from .cohort import COHORT_ID
from .compressed_cohort import CompressedCohortCase, cases_for_cycle
from .compressed_identity import (
    collection_prefix,
    manifest_artifact_id,
    mode_receipt_artifact_id,
    tick_run_id,
)
from .compressed_plan import (
    FINAL_ONLY_RECOVERY_REASON,
    CompressedCycle,
    CompressedPlan,
    FinalOnlyRecoverySpec,
    authorize_final_only_recovery,
)
from .compressed_preparation import (
    CompressedPreparationBundle,
    install_prepared_cycle,
    verify_prepared_cycle,
)
from .model_cost import (
    CostSnapshot,
    DEFAULT_MODEL_COST_POLICY,
    plan_cost_collection_name,
)


EXPECTED_CANCELLED_STATE_COUNTS = {
    "AUDITING": 1,
    "CREATED": 417,
    "HALTED": 14,
    "NO_ACTION": 23,
    "WATCHING": 1,
}


@dataclass(frozen=True, slots=True)
class FinalExecutionRecoverySnapshot:
    snapshot_sha256: str
    state_counts: Mapping[str, int]
    collection_counts: Mapping[str, int]
    batch_receipt_id: str
    batch_receipt_hash: str
    scan_run_artifact_ids: tuple[str, ...]
    run_rows: tuple[Mapping[str, object], ...]


@dataclass(frozen=True, slots=True)
class FinalOnlyRecoveryReady:
    recovery_receipt_id: str
    collection_prefix: str
    previous_snapshot_sha256: str
    prepared_case_count: int


def recovery_collection_prefix(
    plan: CompressedPlan,
    cycle: CompressedCycle,
    recovery: FinalOnlyRecoverySpec,
) -> str:
    _require_recovery_binding(plan, cycle, recovery)
    return recovery.collection_prefix


def recovery_run_id(
    item: CompressedCohortCase,
    recovery: FinalOnlyRecoverySpec,
) -> str:
    key = scan_idempotency_key(
        watch_case_id=item.case_id,
        source_cursors={"synthetic-source": item.cursor},
        schedule_epoch=item.next_scan_at,
        data_mode=DataMode.SYNTHETIC.value,
        identity_scope=recovery.identity_scope,
    )
    return str(uuid5(NAMESPACE_URL, f"recall:scan-run:{key}"))


def recovery_trace_id(
    plan: CompressedPlan,
    cycle: CompressedCycle,
    case_id: str,
    recovery: FinalOnlyRecoverySpec,
) -> str:
    _require_recovery_binding(plan, cycle, recovery)
    namespace = UUID(recovery.recovery_attempt_id)
    return str(uuid5(namespace, f"trace:{plan.sha256}:{cycle.cycle_id}:{case_id}"))


def require_recovery_for_started_final_prefix(
    ledger: LedgerPort,
    *,
    plan: CompressedPlan,
    cycle: CompressedCycle,
) -> None:
    """Refuse an unscoped owner release after final execution has started."""

    _require_final_only(plan, cycle, None)
    manifest_id = manifest_artifact_id(plan, cycle)
    manifest_wire = ledger.get_artifact(manifest_id)
    if manifest_wire is not None:
        try:
            manifest = parse_artifact(
                manifest_wire, authorized_producers=PRODUCER_REGISTRY
            )
            mode_wire = ledger.get_artifact(mode_receipt_artifact_id(plan, cycle))
            mode = (
                None
                if mode_wire is None
                else parse_artifact(
                    mode_wire, authorized_producers=PRODUCER_REGISTRY
                )
            )
        except ContractError as exc:
            raise RuntimeError("final_recovery_required") from exc
        if (
            manifest.schema_name != "CohortDayManifest"
            or manifest.schema_version != "3.4.0"
            or manifest.artifact_id != manifest_id
            or manifest.run_id != tick_run_id(plan, cycle)
            or manifest.status is not ArtifactStatus.VALID
            or manifest.payload.plan_sha256 != plan.sha256
            or manifest.payload.cycle_id != cycle.cycle_id
            or mode is None
            or mode.schema_name != "DataModeReceipt"
            or mode.schema_version != "2.0.0"
            or mode.artifact_id != mode_receipt_artifact_id(plan, cycle)
            or mode.run_id != tick_run_id(plan, cycle)
            or mode.status is not ArtifactStatus.VALID
            or manifest_id not in mode.payload.subject_artifact_ids
            or mode.payload.propagation_status.value != "PASS"
        ):
            raise RuntimeError("final_recovery_required")
        return
    execution_rows = any(
        ledger.read_back_count(name)
        for name in ("scan_runs", "scan_run_events", "review_tasks")
    )
    cohort_evidence = any(
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY).schema_name
        in {"BatchExecutionReceipt", "CohortExecutionCheckpoint"}
        for wire in ledger.list_by_run(tick_run_id(plan, cycle))
    )
    if execution_rows or cohort_evidence:
        raise RuntimeError("final_recovery_required")


def build_final_execution_recovery_snapshot(
    ledger: LedgerPort,
    *,
    plan: CompressedPlan,
    cycle: CompressedCycle,
    bundle: CompressedPreparationBundle,
    previous_execution_id: str,
) -> FinalExecutionRecoverySnapshot:
    _require_final_only(plan, cycle, bundle)
    if not previous_execution_id.startswith("recall-cohort-daily-"):
        raise RuntimeError("final_recovery_previous_execution_invalid")
    expected_runs = []
    rows: list[Mapping[str, object]] = []
    scan_ids = []
    states: Counter[str] = Counter()
    for item in cases_for_cycle(cycle):
        watch = ledger.get_watch_case(item.case_id)
        if (
            watch is None
            or watch.next_scan_at != cycle.schedule_epoch
            or dict(watch.source_cursors) != {"synthetic-source": item.cursor}
        ):
            raise RuntimeError("final_recovery_previous_watch_set_invalid")
        key = scan_idempotency_key(
            watch_case_id=item.case_id,
            source_cursors=dict(watch.source_cursors),
            schedule_epoch=cycle.schedule_epoch,
            data_mode=DataMode.SYNTHETIC.value,
        )
        run_id = str(uuid5(NAMESPACE_URL, f"recall:scan-run:{key}"))
        run = ledger.get_scan_run(run_id)
        if run is None or run.scan_run_artifact_id is None:
            raise RuntimeError("final_recovery_previous_run_set_invalid")
        wire = ledger.get_artifact(run.scan_run_artifact_id)
        if wire is None:
            raise RuntimeError("final_recovery_previous_run_artifact_missing")
        parsed = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
        if (
            parsed.schema_name != "ScanRun"
            or parsed.run_id != run_id
            or parsed.case_id != item.case_id
            or parsed.payload.scheduled_for != cycle.schedule_epoch
            or parsed.payload.idempotency_key != key
        ):
            raise RuntimeError("final_recovery_previous_run_binding_invalid")
        expected_runs.append(run_id)
        scan_ids.append(run.scan_run_artifact_id)
        states[run.state.value] += 1
        rows.append(
            {
                "case_id": item.case_id,
                "run_id": run_id,
                "state": run.state.value,
                "version": run.version,
                "lease_epoch": run.lease_epoch,
                "lease_expires_at": _optional_timestamp(run.lease_expires_at),
                "updated_at": _timestamp(run.updated_at),
                "scan_run_artifact_id": run.scan_run_artifact_id,
                "terminal_policy_decision_id": run.terminal_policy_decision_id,
                "failure_receipt_ids": list(run.failure_receipt_ids),
            }
        )
    observed_states = dict(sorted(states.items()))
    if observed_states != EXPECTED_CANCELLED_STATE_COUNTS:
        raise RuntimeError("final_recovery_previous_state_counts_invalid")
    manifest_id = manifest_artifact_id(plan, cycle)
    mode_id = mode_receipt_artifact_id(plan, cycle)
    if ledger.get_artifact(manifest_id) is not None or ledger.get_artifact(mode_id) is not None:
        raise RuntimeError("final_recovery_previous_manifest_present")
    batch_id = str(
        uuid5(UUID(tick_run_id(plan, cycle)), "batch-execution-receipt")
    )
    batch_wire = ledger.get_artifact(batch_id)
    if batch_wire is None:
        raise RuntimeError("final_recovery_previous_batch_receipt_missing")
    batch = parse_artifact(batch_wire, authorized_producers=PRODUCER_REGISTRY)
    if (
        batch.schema_name != "BatchExecutionReceipt"
        or batch.payload.plan_sha256 != plan.sha256
        or batch.payload.cycle_id != "c6"
        or tuple(batch.payload.ordered_run_ids) != tuple(sorted(expected_runs))
        or tuple(batch.payload.scan_run_artifact_ids) != tuple(sorted(scan_ids))
        or tuple(batch.payload.created_run_ids) != tuple(sorted(expected_runs))
        or batch.payload.recovered_current_epoch_run_ids
        or batch.payload.measurement_status != "MEASURED"
    ):
        raise RuntimeError("final_recovery_previous_batch_receipt_invalid")
    collection_counts = {
        name: ledger.read_back_count(name) for name in COLLECTION_NAMES
    }
    snapshot_wire = {
        "schema_version": "1.0.0",
        "previous_execution_id": previous_execution_id,
        "previous_collection_prefix": collection_prefix(plan, cycle),
        "plan_sha256": plan.sha256,
        "bundle_sha256": bundle.bundle_sha256,
        "manifest_status": "MISSING_AFTER_CANCELLED_EXECUTION",
        "manifest_artifact_id": manifest_id,
        "mode_receipt_artifact_id": mode_id,
        "batch_receipt_id": batch.artifact_id,
        "batch_receipt_hash": batch.content_hash,
        "state_counts": observed_states,
        "collection_counts": collection_counts,
        "runs": sorted(rows, key=lambda item: str(item["run_id"])),
    }
    return FinalExecutionRecoverySnapshot(
        snapshot_sha256=hashlib.sha256(
            canonical_json_bytes(snapshot_wire)
        ).hexdigest(),
        state_counts=observed_states,
        collection_counts=collection_counts,
        batch_receipt_id=batch.artifact_id,
        batch_receipt_hash=batch.content_hash,
        scan_run_artifact_ids=tuple(sorted(scan_ids)),
        run_rows=tuple(snapshot_wire["runs"]),
    )


def install_final_only_recovery(
    *,
    previous_ledger: LedgerPort,
    target_ledger: LedgerPort,
    plan: CompressedPlan,
    cycle: CompressedCycle,
    bundle: CompressedPreparationBundle,
    recovery: FinalOnlyRecoverySpec,
    source_commit: str,
    image_digest: str,
    cost_snapshot: CostSnapshot,
    now: datetime,
) -> FinalOnlyRecoveryReady:
    if previous_ledger is target_ledger:
        raise RuntimeError("final_recovery_namespace_collision")
    snapshot = _verify_previous(
        previous_ledger, plan=plan, cycle=cycle, bundle=bundle, recovery=recovery
    )
    receipt_id = _receipt_id(recovery)
    existing = target_ledger.get_artifact(receipt_id)
    counts = {name: target_ledger.read_back_count(name) for name in COLLECTION_NAMES}
    if counts["scan_runs"] or counts["scan_run_events"] or counts["review_tasks"]:
        raise RuntimeError("final_recovery_target_execution_started")
    if existing is None:
        if any(counts.values()):
            raise RuntimeError("final_recovery_target_not_empty")
        receipt = _build_receipt(
            plan=plan,
            cycle=cycle,
            bundle=bundle,
            recovery=recovery,
            snapshot=snapshot,
            source_commit=source_commit,
            image_digest=image_digest,
            cost_snapshot=cost_snapshot,
            now=now,
        )
        target_ledger.append_artifact(receipt)
    _verify_receipt(
        target_ledger,
        plan=plan,
        bundle=bundle,
        recovery=recovery,
        snapshot=snapshot,
        source_commit=source_commit,
        image_digest=image_digest,
        cost_snapshot=cost_snapshot,
    )
    install_prepared_cycle(
        target_ledger, bundle, plan, cycle, now=now
    )
    return verify_final_only_recovery_ready(
        previous_ledger=previous_ledger,
        target_ledger=target_ledger,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        recovery=recovery,
        source_commit=source_commit,
        image_digest=image_digest,
        cost_snapshot=cost_snapshot,
    )


def verify_final_only_recovery_ready(
    *,
    previous_ledger: LedgerPort,
    target_ledger: LedgerPort,
    plan: CompressedPlan,
    cycle: CompressedCycle,
    bundle: CompressedPreparationBundle,
    recovery: FinalOnlyRecoverySpec,
    source_commit: str,
    image_digest: str,
    cost_snapshot: CostSnapshot,
) -> FinalOnlyRecoveryReady:
    snapshot = _verify_previous(
        previous_ledger, plan=plan, cycle=cycle, bundle=bundle, recovery=recovery
    )
    _verify_receipt(
        target_ledger,
        plan=plan,
        bundle=bundle,
        recovery=recovery,
        snapshot=snapshot,
        source_commit=source_commit,
        image_digest=image_digest,
        cost_snapshot=cost_snapshot,
    )
    verify_prepared_cycle(target_ledger, bundle, plan, cycle)
    if any(
        target_ledger.read_back_count(name)
        for name in ("scan_runs", "scan_run_events", "review_tasks")
    ):
        raise RuntimeError("final_recovery_target_execution_started")
    return FinalOnlyRecoveryReady(
        recovery_receipt_id=_receipt_id(recovery),
        collection_prefix=recovery.collection_prefix,
        previous_snapshot_sha256=snapshot.snapshot_sha256,
        prepared_case_count=target_ledger.read_back_count("watch_cases"),
    )


def _verify_previous(
    ledger: LedgerPort,
    *,
    plan: CompressedPlan,
    cycle: CompressedCycle,
    bundle: CompressedPreparationBundle,
    recovery: FinalOnlyRecoverySpec,
) -> FinalExecutionRecoverySnapshot:
    _require_recovery_binding(plan, cycle, recovery)
    snapshot = build_final_execution_recovery_snapshot(
        ledger,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_execution_id=recovery.previous_execution_id,
    )
    if snapshot.snapshot_sha256 != recovery.previous_snapshot_sha256:
        raise RuntimeError("final_recovery_previous_snapshot_drift")
    return snapshot


def _build_receipt(
    *,
    plan: CompressedPlan,
    cycle: CompressedCycle,
    bundle: CompressedPreparationBundle,
    recovery: FinalOnlyRecoverySpec,
    snapshot: FinalExecutionRecoverySnapshot,
    source_commit: str,
    image_digest: str,
    cost_snapshot: CostSnapshot,
    now: datetime,
) -> dict[str, object]:
    if (
        cost_snapshot.reserved_usd_micros > DEFAULT_MODEL_COST_POLICY.hard_cap_usd_micros
        or cost_snapshot.reconciled_usd_micros > cost_snapshot.reserved_usd_micros
    ):
        raise RuntimeError("final_recovery_cost_snapshot_invalid")
    return build_artifact(
        schema_name="FinalExecutionRecoveryReceipt",
        schema_version="1.0.0",
        artifact_id=_receipt_id(recovery),
        case_id=COHORT_ID,
        run_id=tick_run_id(plan, cycle),
        producer={
            "component": "final-execution-recovery-controller",
            "version": "1.0.0",
            "identity": "cohort-scheduler",
        },
        created_at=_timestamp(now),
        input_artifact_ids=tuple(
            sorted(
                {
                    snapshot.batch_receipt_id,
                    *snapshot.scan_run_artifact_ids,
                }
            )
        ),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID,
        payload={
            "recovery_attempt_id": recovery.recovery_attempt_id,
            "identity_scope": recovery.identity_scope,
            "owner_decision": "AUTHORIZE_APPEND_ONLY_FINAL_RECOVERY",
            "owner_recovery_reason": recovery.owner_recovery_reason,
            "previous_execution_id": recovery.previous_execution_id,
            "previous_collection_prefix": recovery.previous_collection_prefix,
            "previous_source_commit": recovery.previous_source_commit,
            "previous_image_digest": recovery.previous_image_digest,
            "previous_plan_sha256": plan.sha256,
            "previous_bundle_sha256": bundle.bundle_sha256,
            "previous_snapshot_sha256": snapshot.snapshot_sha256,
            "previous_state_counts": dict(snapshot.state_counts),
            "previous_manifest_status": "MISSING_AFTER_CANCELLED_EXECUTION",
            "previous_batch_receipt_id": snapshot.batch_receipt_id,
            "previous_batch_receipt_hash": snapshot.batch_receipt_hash,
            "target_collection_prefix": recovery.collection_prefix,
            "target_source_commit": source_commit,
            "target_image_digest": image_digest,
            "target_plan_sha256": plan.sha256,
            "target_bundle_sha256": bundle.bundle_sha256,
            "target_case_count": 456,
            "plan_cost_collection": plan_cost_collection_name(plan.sha256),
            "hard_cap_usd_micros": DEFAULT_MODEL_COST_POLICY.hard_cap_usd_micros,
            "baseline_reserved_usd_micros": cost_snapshot.reserved_usd_micros,
            "baseline_reconciled_usd_micros": cost_snapshot.reconciled_usd_micros,
        },
        authorized_producers=PRODUCER_REGISTRY,
    )


def _verify_receipt(
    ledger: LedgerPort,
    *,
    plan: CompressedPlan,
    bundle: CompressedPreparationBundle,
    recovery: FinalOnlyRecoverySpec,
    snapshot: FinalExecutionRecoverySnapshot,
    source_commit: str,
    image_digest: str,
    cost_snapshot: CostSnapshot,
) -> None:
    wire = ledger.get_artifact(_receipt_id(recovery))
    if wire is None:
        raise RuntimeError("final_recovery_receipt_missing")
    parsed = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
    payload = parsed.payload
    expected_inputs = tuple(
        sorted({snapshot.batch_receipt_id, *snapshot.scan_run_artifact_ids})
    )
    if (
        parsed.schema_name != "FinalExecutionRecoveryReceipt"
        or parsed.schema_version != "1.0.0"
        or parsed.artifact_id != _receipt_id(recovery)
        or parsed.case_id != COHORT_ID
        or parsed.run_id != tick_run_id(plan, plan.by_id("c6"))
        or parsed.status is not ArtifactStatus.VALID
        or parsed.input_artifact_ids != expected_inputs
        or payload.recovery_attempt_id != recovery.recovery_attempt_id
        or payload.identity_scope != recovery.identity_scope
        or payload.previous_execution_id != recovery.previous_execution_id
        or payload.previous_collection_prefix
        != recovery.previous_collection_prefix
        or payload.previous_source_commit != recovery.previous_source_commit
        or payload.previous_image_digest != recovery.previous_image_digest
        or payload.previous_plan_sha256 != plan.sha256
        or payload.previous_bundle_sha256 != bundle.bundle_sha256
        or payload.previous_snapshot_sha256 != snapshot.snapshot_sha256
        or dict(payload.previous_state_counts) != dict(snapshot.state_counts)
        or payload.previous_batch_receipt_id != snapshot.batch_receipt_id
        or payload.previous_batch_receipt_hash != snapshot.batch_receipt_hash
        or payload.target_collection_prefix != recovery.collection_prefix
        or payload.target_source_commit != source_commit
        or payload.target_image_digest != image_digest
        or payload.target_plan_sha256 != plan.sha256
        or payload.target_bundle_sha256 != bundle.bundle_sha256
        or payload.target_case_count != 456
        or payload.plan_cost_collection != plan_cost_collection_name(plan.sha256)
        or payload.hard_cap_usd_micros
        != DEFAULT_MODEL_COST_POLICY.hard_cap_usd_micros
        or payload.baseline_reserved_usd_micros != cost_snapshot.reserved_usd_micros
        or payload.baseline_reconciled_usd_micros != cost_snapshot.reconciled_usd_micros
    ):
        raise RuntimeError("final_recovery_receipt_binding_invalid")


def _receipt_id(recovery: FinalOnlyRecoverySpec) -> str:
    return str(
        uuid5(UUID(recovery.recovery_attempt_id), "final-execution-recovery-receipt")
    )


def _require_recovery_binding(
    plan: CompressedPlan,
    cycle: CompressedCycle,
    recovery: FinalOnlyRecoverySpec,
) -> None:
    _require_final_only(plan, cycle, None)
    if (
        recovery.previous_collection_prefix != collection_prefix(plan, cycle)
        or recovery.collection_prefix == recovery.previous_collection_prefix
        or not recovery.identity_scope.startswith("final-only-recovery:")
    ):
        raise RuntimeError("final_recovery_binding_invalid")


def _require_final_only(
    plan: CompressedPlan,
    cycle: CompressedCycle,
    bundle: CompressedPreparationBundle | None,
) -> None:
    if (
        plan.schema_version != "2.8.0"
        or cycle != plan.by_id("c6")
        or cycle.activation != "ACTIVE"
        or cycle.runs_predicted != 456
        or (bundle is not None and (
            bundle.schema_version != "2.3.0"
            or bundle.plan_sha256 != plan.sha256
            or len(bundle.cases) != 456
        ))
    ):
        raise RuntimeError("final_recovery_plan_invalid")


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _optional_timestamp(value: datetime | None) -> str | None:
    return None if value is None else _timestamp(value)


__all__ = [
    "FINAL_ONLY_RECOVERY_REASON",
    "FinalExecutionRecoverySnapshot",
    "FinalOnlyRecoveryReady",
    "authorize_final_only_recovery",
    "build_final_execution_recovery_snapshot",
    "install_final_only_recovery",
    "recovery_collection_prefix",
    "recovery_run_id",
    "recovery_trace_id",
    "require_recovery_for_started_final_prefix",
    "verify_final_only_recovery_ready",
]
