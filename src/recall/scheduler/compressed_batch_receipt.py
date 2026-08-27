from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID, uuid5

from recall.contracts import ArtifactStatus, DataMode, build_artifact, parse_artifact
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY

from .cohort import COHORT_ID
from .compressed_batch import BatchCaseResult
from .compressed_identity import tick_run_id
from .compressed_plan import CompressedCycle, CompressedPlan


@dataclass(frozen=True, slots=True)
class PersistedBatchExecution:
    receipt: Mapping[str, object]
    write_metrics: Mapping[str, object]
    measurement_status: str


def verify_batch_execution_binding(
    *,
    ledger: LedgerPort,
    plan: CompressedPlan,
    cycle: CompressedCycle,
    receipt_id: str,
    expected_ordered_run_ids: Sequence[str],
    expected_created_run_ids: Sequence[str],
    expected_recovered_run_ids: Sequence[str],
    expected_measurement_status: str,
    expected_write_metrics: Mapping[str, object],
) -> Mapping[str, object]:
    wire = ledger.get_artifact(receipt_id)
    if wire is None:
        raise RuntimeError("compressed_batch_receipt_missing")
    parsed = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
    payload = parsed.payload
    ordered = tuple(sorted(expected_ordered_run_ids))
    created = tuple(sorted(expected_created_run_ids))
    recovered = tuple(sorted(expected_recovered_run_ids))
    pointer_artifact_ids = []
    for run_id in ordered:
        pointer = ledger.get_scan_run(run_id)
        if pointer is None or pointer.scan_run_artifact_id is None:
            raise RuntimeError("compressed_batch_receipt_run_missing")
        artifact_id = str(pointer.scan_run_artifact_id)
        if ledger.get_artifact(artifact_id) is None:
            raise RuntimeError("compressed_batch_receipt_run_artifact_missing")
        pointer_artifact_ids.append(artifact_id)
    if (
        parsed.schema_name != "BatchExecutionReceipt"
        or parsed.run_id != tick_run_id(plan, cycle)
        or payload.plan_sha256 != plan.sha256
        or payload.cycle_id != cycle.cycle_id
        or payload.cycle_attempt_id != tick_run_id(plan, cycle)
        or payload.ordered_run_ids != ordered
        or payload.scan_run_artifact_ids != tuple(sorted(pointer_artifact_ids))
        or payload.created_run_ids != created
        or payload.recovered_current_epoch_run_ids != recovered
        or payload.measurement_status != expected_measurement_status
        or dict(payload.write_metrics) != dict(expected_write_metrics)
        or parsed.input_artifact_ids != tuple(sorted(pointer_artifact_ids))
    ):
        raise RuntimeError("compressed_batch_receipt_binding_invalid")
    return wire


def persist_or_reconcile_batch_execution(
    *,
    ledger: LedgerPort,
    plan: CompressedPlan,
    cycle: CompressedCycle,
    outcomes: Sequence[BatchCaseResult],
    write_metrics: Mapping[str, object],
) -> PersistedBatchExecution:
    attempt_id = tick_run_id(plan, cycle)
    receipt_id = str(uuid5(UUID(attempt_id), "batch-execution-receipt"))
    existing = ledger.get_artifact(receipt_id)
    ordered = tuple(sorted(outcomes, key=lambda item: item.run_record.run_id))
    ordered_ids = tuple(item.run_record.run_id for item in ordered)
    scan_ids = tuple(
        sorted(str(item.run_record.scan_run_artifact_id) for item in ordered)
    )
    if existing is not None:
        parsed = parse_artifact(existing, authorized_producers=PRODUCER_REGISTRY)
        payload = parsed.payload
        if (
            parsed.schema_name != "BatchExecutionReceipt"
            or payload.plan_sha256 != plan.sha256
            or payload.cycle_id != cycle.cycle_id
            or payload.cycle_attempt_id != attempt_id
            or payload.ordered_run_ids != ordered_ids
            or payload.scan_run_artifact_ids != scan_ids
            or any(item.created for item in ordered)
        ):
            raise RuntimeError("compressed_batch_receipt_reconciliation_failed")
        verified = verify_batch_execution_binding(
            ledger=ledger,
            plan=plan,
            cycle=cycle,
            receipt_id=receipt_id,
            expected_ordered_run_ids=payload.ordered_run_ids,
            expected_created_run_ids=payload.created_run_ids,
            expected_recovered_run_ids=payload.recovered_current_epoch_run_ids,
            expected_measurement_status=payload.measurement_status,
            expected_write_metrics=payload.write_metrics,
        )
        return PersistedBatchExecution(
            verified,
            payload.write_metrics,
            payload.measurement_status,
        )
    created = tuple(item.run_record.run_id for item in ordered if item.created)
    recovered = tuple(
        item.run_record.run_id for item in ordered if not item.created
    )
    measurement_status = (
        "MEASURED" if len(created) == len(ordered) else "NOT_EVALUATED"
    )
    wire = build_artifact(
        schema_name="BatchExecutionReceipt",
        schema_version="1.0.0",
        artifact_id=receipt_id,
        case_id=COHORT_ID,
        run_id=attempt_id,
        producer={
            "component": "managed-cohort-scheduler",
            "version": "1.0.0",
            "identity": "cohort-scheduler",
        },
        created_at=str(write_metrics["completed_at"]),
        input_artifact_ids=tuple(sorted(scan_ids)),
        data_mode=DataMode.SYNTHETIC,
        status=(
            ArtifactStatus.VALID
            if measurement_status == "MEASURED"
            else ArtifactStatus.INCOMPLETE
        ),
        payload={
            "plan_sha256": plan.sha256,
            "cycle_id": cycle.cycle_id,
            "cycle_attempt_id": attempt_id,
            "ordered_run_ids": list(ordered_ids),
            "scan_run_artifact_ids": list(scan_ids),
            "created_run_ids": list(created),
            "recovered_current_epoch_run_ids": list(recovered),
            "measurement_status": measurement_status,
            "write_metrics": dict(write_metrics),
        },
        authorized_producers=PRODUCER_REGISTRY,
    )
    ledger.append_artifact(wire)
    persisted = ledger.get_artifact(receipt_id)
    if persisted != wire:
        raise RuntimeError("compressed_batch_receipt_readback_failed")
    verified = verify_batch_execution_binding(
        ledger=ledger,
        plan=plan,
        cycle=cycle,
        receipt_id=receipt_id,
        expected_ordered_run_ids=ordered_ids,
        expected_created_run_ids=created,
        expected_recovered_run_ids=recovered,
        expected_measurement_status=measurement_status,
        expected_write_metrics=write_metrics,
    )
    return PersistedBatchExecution(verified, write_metrics, measurement_status)
