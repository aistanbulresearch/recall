from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid5

from recall.contracts import (
    ArtifactStatus,
    ContractError,
    DataMode,
    build_artifact,
    canonical_json_bytes,
    parse_artifact,
)
from recall.contracts.enums import ScanRunState, WatchCaseState
from recall.controller.hashes import scan_idempotency_key
from recall.ledger.models import COLLECTION_NAMES, ScanRunRecord, WatchCaseRecord
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
    final_recovery_collection_prefix,
    final_recovery_identity_scope,
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
    previous_recovery_receipt_id: str | None
    previous_recovery_receipt_hash: str | None
    previous_identity_scope: str | None
    previous_reserved_usd_micros: int | None
    previous_reconciled_usd_micros: int | None


@dataclass(frozen=True, slots=True)
class FinalOnlyRecoveryReady:
    recovery_receipt_id: str
    collection_prefix: str
    previous_snapshot_sha256: str
    prepared_case_count: int


def _wire_sha256(value: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _watch_pointer_row(watch: WatchCaseRecord) -> dict[str, object]:
    return {
        "watch_case_id": watch.watch_case_id,
        "artifact_id": watch.artifact_id,
        "state": watch.state.value,
        "version": watch.version,
        "source_cursors": dict(sorted(watch.source_cursors)),
        "last_verified_snapshot_id": watch.last_verified_snapshot_id,
        "pending_observation_hashes": list(watch.pending_observation_hashes),
        "open_review_task_id": watch.open_review_task_id,
        "attention_reason_codes": list(watch.attention_reason_codes),
        "next_scan_at": watch.next_scan_at,
        "updated_at": _timestamp(watch.updated_at),
    }


def _run_pointer_row(run: ScanRunRecord) -> dict[str, object]:
    return {
        "run_id": run.run_id,
        "state": run.state.value,
        "version": run.version,
        "lease_epoch": run.lease_epoch,
        "lease_expires_at": _optional_timestamp(run.lease_expires_at),
        "updated_at": _timestamp(run.updated_at),
        "scan_run_artifact_id": run.scan_run_artifact_id,
        "terminal_policy_decision_id": run.terminal_policy_decision_id,
        "failure_receipt_ids": list(run.failure_receipt_ids),
        "last_repeated_state_hash": run.last_repeated_state_hash,
        "repeated_state_count": run.repeated_state_count,
    }


def _require_runtime_watch_closure(
    watch: WatchCaseRecord,
    run: ScanRunRecord,
    *,
    initial_source_cursors: Mapping[str, str],
    schedule_epoch: str,
) -> None:
    if run.state in {
        ScanRunState.CREATED,
        ScanRunState.WATCHING,
        ScanRunState.AUDITING,
    }:
        valid = (
            watch.state is WatchCaseState.ACTIVE
            and watch.version == 1
            and dict(watch.source_cursors) == dict(initial_source_cursors)
            and watch.last_verified_snapshot_id is None
            and watch.open_review_task_id is None
            and not watch.attention_reason_codes
            and watch.next_scan_at == schedule_epoch
            and run.terminal_policy_decision_id is None
            and not run.failure_receipt_ids
        )
    elif run.state is ScanRunState.HALTED:
        valid = (
            watch.state is WatchCaseState.ATTENTION_REQUIRED
            and watch.version >= 2
            and watch.open_review_task_id is None
            and bool(watch.attention_reason_codes)
            and watch.next_scan_at is None
            and run.terminal_policy_decision_id is None
            and bool(run.failure_receipt_ids)
        )
    elif run.state is ScanRunState.NO_ACTION:
        valid = (
            watch.state is WatchCaseState.ACTIVE
            and watch.version >= 2
            and bool(watch.source_cursors)
            and watch.last_verified_snapshot_id is not None
            and not watch.pending_observation_hashes
            and watch.open_review_task_id is None
            and not watch.attention_reason_codes
            and watch.next_scan_at == schedule_epoch
            and run.terminal_policy_decision_id is not None
            and not run.failure_receipt_ids
        )
    else:
        valid = False
    if not valid:
        raise RuntimeError("final_recovery_previous_watch_pointer_invalid")


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


def _verified_prior_recovery_binding(
    ledger: LedgerPort,
    *,
    plan: CompressedPlan,
    cycle: CompressedCycle,
    bundle: CompressedPreparationBundle,
    previous_recovery_attempt_id: str | None,
    previous_recovery_receipt_hash: str | None,
    previous_source_commit: str | None,
    previous_image_digest: str | None,
) -> Mapping[str, object] | None:
    supplied_lineage = (
        previous_source_commit is not None or previous_image_digest is not None
    )
    if previous_recovery_attempt_id is None:
        if supplied_lineage or previous_recovery_receipt_hash is not None:
            raise RuntimeError("final_recovery_previous_receipt_binding_invalid")
        return None
    if previous_source_commit is None or previous_image_digest is None:
        raise RuntimeError("final_recovery_previous_receipt_binding_invalid")
    try:
        attempt_id = str(UUID(previous_recovery_attempt_id))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("final_recovery_previous_attempt_invalid") from exc
    if attempt_id != previous_recovery_attempt_id:
        raise RuntimeError("final_recovery_previous_attempt_invalid")
    if previous_recovery_receipt_hash is None:
        raise RuntimeError("final_recovery_previous_receipt_hash_invalid")
    receipt_id = str(
        uuid5(UUID(attempt_id), "final-execution-recovery-receipt")
    )
    wire = ledger.get_artifact(receipt_id)
    if wire is None:
        raise RuntimeError("final_recovery_previous_receipt_missing")
    try:
        parsed = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
    except ContractError as exc:
        raise RuntimeError(
            "final_recovery_previous_receipt_binding_invalid"
        ) from exc
    payload = parsed.payload
    expected_scope = final_recovery_identity_scope(attempt_id)
    expected_prefix = final_recovery_collection_prefix(plan, attempt_id)
    expected_base_prefix = collection_prefix(plan, cycle)
    if (
        parsed.schema_name != "FinalExecutionRecoveryReceipt"
        or parsed.schema_version != "1.0.0"
        or parsed.artifact_id != receipt_id
        or parsed.content_hash != previous_recovery_receipt_hash
        or parsed.case_id != COHORT_ID
        or parsed.run_id != tick_run_id(plan, cycle)
        or parsed.status is not ArtifactStatus.VALID
        or parsed.producer.component != "final-execution-recovery-controller"
        or parsed.producer.version != "1.0.0"
        or parsed.producer.identity != "cohort-scheduler"
        or len(parsed.input_artifact_ids) != 457
        or payload.previous_batch_receipt_id not in parsed.input_artifact_ids
        or payload.recovery_attempt_id != attempt_id
        or payload.identity_scope != expected_scope
        or payload.previous_collection_prefix != expected_base_prefix
        or payload.target_collection_prefix != expected_prefix
        or payload.target_source_commit != previous_source_commit
        or payload.target_image_digest != previous_image_digest
        or payload.previous_plan_sha256 != plan.sha256
        or payload.target_plan_sha256 != plan.sha256
        or payload.previous_bundle_sha256 != bundle.bundle_sha256
        or payload.target_bundle_sha256 != bundle.bundle_sha256
        or payload.target_case_count != 456
        or payload.plan_cost_collection != plan_cost_collection_name(plan.sha256)
        or payload.hard_cap_usd_micros
        != DEFAULT_MODEL_COST_POLICY.hard_cap_usd_micros
    ):
        raise RuntimeError("final_recovery_previous_receipt_binding_invalid")
    return {
        "receipt_id": parsed.artifact_id,
        "receipt_hash": parsed.content_hash,
        "recovery_attempt_id": attempt_id,
        "identity_scope": expected_scope,
        "previous_execution_id": payload.previous_execution_id,
        "previous_collection_prefix": payload.previous_collection_prefix,
        "previous_snapshot_sha256": payload.previous_snapshot_sha256,
        "target_collection_prefix": expected_prefix,
        "target_source_commit": payload.target_source_commit,
        "target_image_digest": payload.target_image_digest,
        "plan_cost_collection": payload.plan_cost_collection,
        "hard_cap_usd_micros": payload.hard_cap_usd_micros,
        "baseline_reserved_usd_micros": payload.baseline_reserved_usd_micros,
        "baseline_reconciled_usd_micros": payload.baseline_reconciled_usd_micros,
        "collection_prefix": expected_prefix,
    }


def build_final_execution_recovery_snapshot(
    ledger: LedgerPort,
    *,
    plan: CompressedPlan,
    cycle: CompressedCycle,
    bundle: CompressedPreparationBundle,
    previous_execution_id: str,
    previous_recovery_attempt_id: str | None = None,
    previous_recovery_receipt_hash: str | None = None,
    previous_source_commit: str | None = None,
    previous_image_digest: str | None = None,
) -> FinalExecutionRecoverySnapshot:
    _require_final_only(plan, cycle, bundle)
    if not previous_execution_id.startswith("recall-cohort-daily-"):
        raise RuntimeError("final_recovery_previous_execution_invalid")
    expected_runs = []
    rows: list[Mapping[str, object]] = []
    watch_rows: list[Mapping[str, object]] = []
    preparation_rows: list[Mapping[str, object]] = []
    scan_ids = []
    states: Counter[str] = Counter()
    expected_cases = cases_for_cycle(cycle)
    prior_recovery = _verified_prior_recovery_binding(
        ledger,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        previous_recovery_attempt_id=previous_recovery_attempt_id,
        previous_recovery_receipt_hash=previous_recovery_receipt_hash,
        previous_source_commit=previous_source_commit,
        previous_image_digest=previous_image_digest,
    )
    previous_identity_scope = (
        None if prior_recovery is None else prior_recovery["identity_scope"]
    )
    previous_collection_prefix = (
        collection_prefix(plan, cycle)
        if prior_recovery is None
        else str(prior_recovery["collection_prefix"])
    )
    expected_case_ids = {item.case_id for item in expected_cases}
    prepared_by_case = {
        item.case_id: item
        for item in bundle.cases
        if item.cycle_id == cycle.cycle_id
    }
    watch_records = tuple(ledger.list_watch_cases())
    watch_by_case = {item.watch_case_id: item for item in watch_records}
    if (
        len(prepared_by_case) != len(expected_cases)
        or len(watch_records) != len(expected_cases)
        or len(watch_by_case) != len(watch_records)
        or set(watch_by_case) != expected_case_ids
    ):
        raise RuntimeError("final_recovery_previous_watch_set_invalid")

    identities: dict[str, tuple[Mapping[str, str], str, str]] = {}
    for item in expected_cases:
        initial_source_cursors = {"synthetic-source": item.cursor}
        key = scan_idempotency_key(
            watch_case_id=item.case_id,
            source_cursors=initial_source_cursors,
            schedule_epoch=cycle.schedule_epoch,
            data_mode=DataMode.SYNTHETIC.value,
            identity_scope=previous_identity_scope,
        )
        identities[item.case_id] = (
            initial_source_cursors,
            key,
            str(uuid5(NAMESPACE_URL, f"recall:scan-run:{key}")),
        )
    expected_run_ids = {value[2] for value in identities.values()}
    run_records = tuple(ledger.list_scan_runs())
    run_by_id = {item.run_id: item for item in run_records}
    if (
        len(run_records) != len(expected_cases)
        or len(run_by_id) != len(run_records)
        or set(run_by_id) != expected_run_ids
    ):
        raise RuntimeError("final_recovery_previous_run_set_invalid")

    manifest_id = manifest_artifact_id(plan, cycle)
    mode_id = mode_receipt_artifact_id(plan, cycle)
    batch_id = str(
        uuid5(UUID(tick_run_id(plan, cycle)), "batch-execution-receipt")
    )
    artifact_ids = {manifest_id, mode_id, batch_id}
    for item in expected_cases:
        prepared = prepared_by_case[item.case_id]
        artifact_ids.add(str(prepared.watch_case["artifact_id"]))
        artifact_ids.add(str(prepared.privacy_receipt["artifact_id"]))
        run = run_by_id[identities[item.case_id][2]]
        if run.scan_run_artifact_id is None:
            raise RuntimeError("final_recovery_previous_run_set_invalid")
        artifact_ids.add(run.scan_run_artifact_id)
    artifacts = ledger.get_artifacts(tuple(sorted(artifact_ids)))

    for item in expected_cases:
        prepared = prepared_by_case.get(item.case_id)
        watch = watch_by_case[item.case_id]
        if (
            prepared is None
            or watch.watch_case_id != item.case_id
            or watch.artifact_id != prepared.watch_case["artifact_id"]
        ):
            raise RuntimeError("final_recovery_previous_watch_set_invalid")
        watch_wire = artifacts.get(watch.artifact_id)
        privacy_id = str(prepared.privacy_receipt["artifact_id"])
        privacy_wire = artifacts.get(privacy_id)
        if (
            watch_wire is None
            or _wire_sha256(watch_wire) != _wire_sha256(prepared.watch_case)
        ):
            raise RuntimeError("final_recovery_previous_watch_material_invalid")
        if (
            privacy_wire is None
            or _wire_sha256(privacy_wire)
            != _wire_sha256(prepared.privacy_receipt)
        ):
            raise RuntimeError("final_recovery_previous_privacy_material_invalid")
        try:
            parsed_watch = parse_artifact(
                watch_wire, authorized_producers=PRODUCER_REGISTRY
            )
            parsed_privacy = parse_artifact(
                privacy_wire, authorized_producers=PRODUCER_REGISTRY
            )
        except ContractError as exc:
            raise RuntimeError(
                "final_recovery_previous_preparation_material_invalid"
            ) from exc
        if (
            parsed_watch.schema_name != "WatchCase"
            or parsed_watch.case_id != item.case_id
            or parsed_watch.input_artifact_ids != (privacy_id,)
            or parsed_privacy.schema_name != "PrivacyReceipt"
            or parsed_privacy.schema_version != "1.1.0"
            or parsed_privacy.case_id != item.case_id
        ):
            raise RuntimeError(
                "final_recovery_previous_preparation_material_invalid"
            )
        initial_source_cursors, key, run_id = identities[item.case_id]
        run = run_by_id[run_id]
        if (
            run.run_id != run_id
            or run.scan_run_artifact_id is None
        ):
            raise RuntimeError("final_recovery_previous_run_set_invalid")
        wire = artifacts.get(run.scan_run_artifact_id)
        if wire is None:
            raise RuntimeError("final_recovery_previous_run_artifact_missing")
        parsed = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
        if (
            parsed.schema_name != "ScanRun"
            or parsed.schema_version != "1.1.0"
            or parsed.artifact_id
            != str(uuid5(UUID(run_id), "scan-run-artifact"))
            or parsed.run_id != run_id
            or parsed.case_id != item.case_id
            or parsed.data_mode is not DataMode.SYNTHETIC
            or parsed.input_artifact_ids
            != tuple(sorted((privacy_id, watch.artifact_id)))
            or parsed.payload.watch_case_id != item.case_id
            or parsed.payload.scheduled_for != cycle.schedule_epoch
            or parsed.payload.idempotency_key != key
            or parsed.payload.execution_profile is None
            or parsed.payload.execution_profile.value != "FULL_AUDIT_V1"
        ):
            raise RuntimeError("final_recovery_previous_run_binding_invalid")
        _require_runtime_watch_closure(
            watch,
            run,
            initial_source_cursors=initial_source_cursors,
            schedule_epoch=cycle.schedule_epoch,
        )
        expected_runs.append(run_id)
        scan_ids.append(run.scan_run_artifact_id)
        states[run.state.value] += 1
        watch_rows.append(_watch_pointer_row(watch))
        preparation_rows.append(
            {
                "case_id": item.case_id,
                "watch_artifact_id": watch.artifact_id,
                "watch_content_hash": parsed_watch.content_hash,
                "privacy_receipt_id": privacy_id,
                "privacy_content_hash": parsed_privacy.content_hash,
            }
        )
        rows.append(
            {
                "case_id": item.case_id,
                **_run_pointer_row(run),
            }
        )
    observed_states = dict(sorted(states.items()))
    if observed_states != EXPECTED_CANCELLED_STATE_COUNTS:
        raise RuntimeError("final_recovery_previous_state_counts_invalid")
    if artifacts.get(manifest_id) is not None or artifacts.get(mode_id) is not None:
        raise RuntimeError("final_recovery_previous_manifest_present")
    batch_wire = artifacts.get(batch_id)
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
    loaded_counts = {
        "watch_cases": len(watch_records),
        "scan_runs": len(run_records),
    }
    collection_counts = {
        name: (
            loaded_counts[name]
            if name in loaded_counts
            else ledger.read_back_count(name)
        )
        for name in COLLECTION_NAMES
    }
    snapshot_wire = {
        "schema_version": "1.0.0",
        "previous_execution_id": previous_execution_id,
        "previous_collection_prefix": previous_collection_prefix,
        "plan_sha256": plan.sha256,
        "bundle_sha256": bundle.bundle_sha256,
        "manifest_status": "MISSING_AFTER_CANCELLED_EXECUTION",
        "manifest_artifact_id": manifest_id,
        "mode_receipt_artifact_id": mode_id,
        "batch_receipt_id": batch.artifact_id,
        "batch_receipt_hash": batch.content_hash,
        "state_counts": observed_states,
        "collection_counts": collection_counts,
        "preparation_material_sha256": hashlib.sha256(
            canonical_json_bytes(
                sorted(preparation_rows, key=lambda item: str(item["case_id"]))
            )
        ).hexdigest(),
        "watch_cases": sorted(
            watch_rows, key=lambda item: str(item["watch_case_id"])
        ),
        "runs": sorted(rows, key=lambda item: str(item["run_id"])),
    }
    if prior_recovery is not None:
        snapshot_wire["previous_recovery_receipt"] = dict(prior_recovery)
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
        previous_recovery_receipt_id=(
            None if prior_recovery is None else str(prior_recovery["receipt_id"])
        ),
        previous_recovery_receipt_hash=(
            None if prior_recovery is None else str(prior_recovery["receipt_hash"])
        ),
        previous_identity_scope=previous_identity_scope,
        previous_reserved_usd_micros=(
            None
            if prior_recovery is None
            else int(prior_recovery["baseline_reserved_usd_micros"])
        ),
        previous_reconciled_usd_micros=(
            None
            if prior_recovery is None
            else int(prior_recovery["baseline_reconciled_usd_micros"])
        ),
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
        previous_recovery_attempt_id=recovery.previous_recovery_attempt_id,
        previous_recovery_receipt_hash=(
            recovery.previous_recovery_receipt_hash
        ),
        previous_source_commit=(
            None
            if recovery.previous_recovery_attempt_id is None
            else recovery.previous_source_commit
        ),
        previous_image_digest=(
            None
            if recovery.previous_recovery_attempt_id is None
            else recovery.previous_image_digest
        ),
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
    if snapshot.previous_reserved_usd_micros is not None:
        previous_reconciled = snapshot.previous_reconciled_usd_micros
        if (
            previous_reconciled is None
            or cost_snapshot.reserved_usd_micros
            < snapshot.previous_reserved_usd_micros
            or cost_snapshot.reconciled_usd_micros < previous_reconciled
        ):
            raise RuntimeError("final_recovery_cost_continuity_invalid")
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
        input_artifact_ids=tuple(sorted(_recovery_receipt_inputs(snapshot))),
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
    expected_inputs = tuple(sorted(_recovery_receipt_inputs(snapshot)))
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


def _recovery_receipt_inputs(
    snapshot: FinalExecutionRecoverySnapshot,
) -> set[str]:
    values = {snapshot.batch_receipt_id, *snapshot.scan_run_artifact_ids}
    if snapshot.previous_recovery_receipt_id is not None:
        values.add(snapshot.previous_recovery_receipt_id)
    return values


def _require_recovery_binding(
    plan: CompressedPlan,
    cycle: CompressedCycle,
    recovery: FinalOnlyRecoverySpec,
) -> None:
    _require_final_only(plan, cycle, None)
    expected_previous_prefix = (
        collection_prefix(plan, cycle)
        if recovery.previous_recovery_attempt_id is None
        else final_recovery_collection_prefix(
            plan, recovery.previous_recovery_attempt_id
        )
    )
    if (
        recovery.previous_collection_prefix != expected_previous_prefix
        or recovery.collection_prefix == recovery.previous_collection_prefix
        or recovery.collection_prefix
        != final_recovery_collection_prefix(plan, recovery.recovery_attempt_id)
        or recovery.identity_scope
        != final_recovery_identity_scope(recovery.recovery_attempt_id)
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
