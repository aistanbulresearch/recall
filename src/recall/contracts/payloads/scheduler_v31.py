from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from math import ceil
from types import MappingProxyType
from typing import Any

from ..errors import ContractError
from ..validation import require_exact_fields, uuid_value
from .scheduler_v3 import CohortDayManifestV3Payload, parse_cohort_day_manifest_v3_payload


_WRITE_FIELDS = frozenset(
    {
        "scope", "measurement_semantics", "persistence_surface",
        "batch_max_workers", "selected_case_count", "ledger_operation_counts",
        "committed_case_documents", "started_at", "completed_at",
        "worker_elapsed_ms", "readback_elapsed_ms", "total_elapsed_ms",
        "effective_write_millis_per_case",
    }
)
_COUNT_FIELDS = frozenset(
    {
        "watch_case_reads", "watch_artifact_reads", "idempotency_run_reads",
        "create_run_transaction_calls", "post_create_or_reuse_artifact_reads",
        "exact_run_pointer_reads", "exact_run_artifact_reads",
        "exact_run_event_queries", "aggregate_count_reads",
    }
)
_PARITY_FIELDS = frozenset(
    {
        "expected_newly_created_runs", "actual_newly_created_runs",
        "expected_reused_runs", "actual_reused_runs", "new_epoch_required",
        "same_write_path_as_ramp", "parity_match",
    }
)


@dataclass(frozen=True, slots=True)
class CohortDayManifestV31Payload:
    base: CohortDayManifestV3Payload
    epoch_label: str
    evaluation_role: str
    ramp_gate_receipt_id: str
    write_metrics: Mapping[str, object]
    parity: Mapping[str, object]
    execution_history: tuple[Mapping[str, object], ...]

    def __getattr__(self, name: str) -> object:
        return getattr(self.base, name)

    def to_wire(self) -> dict[str, object]:
        value = self.base.to_wire()
        value.update(
            {
                "epoch_label": self.epoch_label,
                "evaluation_role": self.evaluation_role,
                "ramp_gate_receipt_id": self.ramp_gate_receipt_id,
                "write_metrics": _mutable(self.write_metrics),
                "parity": dict(self.parity),
            }
        )
        value["execution_history"] = [dict(item) for item in self.execution_history]
        return value


def parse_cohort_day_manifest_v31_payload(
    value: Mapping[str, Any],
) -> CohortDayManifestV31Payload:
    metrics = _parse_metrics(value["write_metrics"])
    parity = _parse_parity(value["parity"])
    role = value["evaluation_role"]
    if role not in {"RAMP_FIRST_PASS", "PORTFOLIO_REASSESSMENT"}:
        raise ContractError("contract_enum_invalid", "evaluation_role")
    epoch = value["epoch_label"]
    if not isinstance(epoch, str) or not epoch.startswith("PLAN5_"):
        raise ContractError("contract_value_invalid", "epoch_label")
    gate_id = str(uuid_value(value["ramp_gate_receipt_id"], "ramp_gate_receipt_id"))
    if gate_id not in value["input_artifact_ids"]:
        raise ContractError("contract_value_invalid", "ramp_gate_receipt_id")

    # Reuse the mature 3.0 structural/history validation. The copy only
    # normalizes the new completion/status semantics for that validator.
    legacy = dict(value)
    for field in (
        "epoch_label", "evaluation_role", "ramp_gate_receipt_id",
        "write_metrics", "parity",
    ):
        legacy.pop(field)
    history = [dict(item) for item in legacy["execution_history"]]
    for row in history:
        if row["source_schema_version"] == "CohortDayManifest/3.1.0":
            row["source_schema_version"] = "CohortDayManifest/3.0.0"
            row["executed_at"] = row["window_start"]
    legacy["execution_history"] = history
    legacy["created_at"] = legacy["window_start"]
    legacy["status"] = "VALID"
    legacy["delta"] = {**legacy["delta"], "prediction_match": True}
    base = parse_cohort_day_manifest_v3_payload(legacy)

    current = value["execution_history"][-1]
    if current["source_schema_version"] != "CohortDayManifest/3.1.0":
        raise ContractError("contract_value_invalid", "execution_history.current")
    if current["executed_at"] != metrics["completed_at"] or value["created_at"] != metrics["completed_at"]:
        raise ContractError("contract_value_invalid", "completed_at")
    if metrics["selected_case_count"] != len(value["delta"]["selected_case_ids"]):
        raise ContractError("contract_value_invalid", "selected_case_count")
    actual_new = len(value["delta"]["newly_created_run_ids"])
    actual_reused = len(value["delta"]["reused_run_ids"])
    expected = value["delta"]["runs_predicted"]
    if (
        parity["expected_newly_created_runs"] != expected
        or parity["actual_newly_created_runs"] != actual_new
        or parity["expected_reused_runs"] != 0
        or parity["actual_reused_runs"] != actual_reused
    ):
        raise ContractError("contract_value_invalid", "parity_counts")
    computed_parity = actual_new == expected and actual_reused == 0
    if parity["parity_match"] is not computed_parity:
        raise ContractError("contract_value_invalid", "parity_match")
    counts = metrics["ledger_operation_counts"]
    selected_count = int(metrics["selected_case_count"])
    expected_counts = {
        "watch_case_reads": selected_count,
        "watch_artifact_reads": selected_count,
        "idempotency_run_reads": selected_count,
        "create_run_transaction_calls": actual_new,
        "post_create_or_reuse_artifact_reads": selected_count,
        "exact_run_pointer_reads": selected_count,
        "exact_run_artifact_reads": selected_count,
        "exact_run_event_queries": selected_count,
        "aggregate_count_reads": 2,
    }
    if dict(counts) != expected_counts or metrics["committed_case_documents"] != actual_new * 3:
        raise ContractError("contract_value_invalid", "ledger_operation_counts")
    expected_effective = 0 if not selected_count else ceil(int(metrics["total_elapsed_ms"]) / selected_count)
    if metrics["effective_write_millis_per_case"] != expected_effective:
        raise ContractError("contract_value_invalid", "effective_write_millis_per_case")
    qualifies = (
        computed_parity
        and metrics["persistence_surface"] == "LIVE_FIRESTORE"
        and metrics["effective_write_millis_per_case"] <= 2000
        and len(value["delta"]["authoritative_run_ids"]) == expected
    )
    if value["status"] != ("VALID" if qualifies else "INCOMPLETE"):
        raise ContractError("contract_value_invalid", "qualification_status")
    return CohortDayManifestV31Payload(
        base, epoch, role, gate_id,
        MappingProxyType(metrics), MappingProxyType(parity),
        tuple(MappingProxyType(dict(item)) for item in value["execution_history"]),
    )


def _parse_metrics(value: Any) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "write_metrics")
    require_exact_fields(value, _WRITE_FIELDS, "write_metrics")
    counts = value["ledger_operation_counts"]
    if not isinstance(counts, Mapping):
        raise ContractError("contract_type_invalid", "ledger_operation_counts")
    require_exact_fields(counts, _COUNT_FIELDS, "ledger_operation_counts")
    parsed = dict(value)
    parsed["ledger_operation_counts"] = MappingProxyType(
        {field: _integer(counts[field], field) for field in _COUNT_FIELDS}
    )
    for field in _WRITE_FIELDS - {
        "scope", "measurement_semantics", "persistence_surface", "started_at",
        "completed_at", "ledger_operation_counts",
    }:
        parsed[field] = _integer(value[field], field)
    if value["scope"] != "CASE_WRITE_AND_EXACT_READBACK" or value["measurement_semantics"] != "LEDGER_METHOD_INVOCATIONS_AND_COMMITTED_CASE_DOCUMENTS":
        raise ContractError("contract_value_invalid", "write_metrics.scope")
    started = _timestamp(value["started_at"], "started_at")
    completed = _timestamp(value["completed_at"], "completed_at")
    if datetime.fromisoformat(completed.replace("Z", "+00:00")) < datetime.fromisoformat(started.replace("Z", "+00:00")):
        raise ContractError("contract_value_invalid", "write_metrics.time_order")
    parsed["started_at"] = started
    parsed["completed_at"] = completed
    if parsed["total_elapsed_ms"] != parsed["worker_elapsed_ms"] + parsed["readback_elapsed_ms"]:
        raise ContractError("contract_value_invalid", "total_elapsed_ms")
    elapsed = datetime.fromisoformat(completed.replace("Z", "+00:00")) - datetime.fromisoformat(started.replace("Z", "+00:00"))
    if round(elapsed.total_seconds() * 1000) != parsed["total_elapsed_ms"]:
        raise ContractError("contract_value_invalid", "elapsed_time_binding")
    return parsed


def _parse_parity(value: Any) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "parity")
    require_exact_fields(value, _PARITY_FIELDS, "parity")
    parsed = dict(value)
    for field in _PARITY_FIELDS - {"new_epoch_required", "same_write_path_as_ramp", "parity_match"}:
        parsed[field] = _integer(value[field], field)
    for field in ("new_epoch_required", "same_write_path_as_ramp", "parity_match"):
        if not isinstance(value[field], bool):
            raise ContractError("contract_type_invalid", field)
    if not value["new_epoch_required"] or not value["same_write_path_as_ramp"]:
        raise ContractError("contract_value_invalid", "parity_declaration")
    return parsed


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractError("contract_type_invalid", field)
    return value


def _timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ContractError("contract_timestamp_invalid", field)
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _mutable(value: Mapping[str, object]) -> dict[str, object]:
    result = dict(value)
    result["ledger_operation_counts"] = dict(result["ledger_operation_counts"])
    return result
