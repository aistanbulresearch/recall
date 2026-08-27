from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ..errors import ContractError
from ..validation import SHA256, non_empty_string, require_exact_fields, uuid_value


_FIELDS = frozenset(
    {
        "target_plan_sha256", "target_cycle_id", "input_snapshot_sha256",
        "gate_version", "metric_policy", "predecessor_binding",
        "observed_metrics", "decision", "reason_codes", "evidence_watermark",
    }
)
_BINDING_FIELDS = frozenset(
    {
        "plan_sha256", "collection_prefix", "cycle_id",
        "manifest_artifact_id", "manifest_content_hash",
        "mode_receipt_artifact_id", "mode_receipt_content_hash",
    }
)
_METRIC_FIELDS = frozenset(
    {
        "runs_predicted", "newly_created_runs", "reused_runs",
        "authoritative_runs", "persistence_surface",
        "committed_case_documents", "total_elapsed_ms",
        "effective_write_millis_per_case",
    }
)
_REASONS = frozenset(
    {
        "manifest_missing", "manifest_hash_mismatch", "mode_receipt_missing",
        "mode_receipt_hash_mismatch", "mode_receipt_unbound",
        "prediction_mismatch", "new_run_parity_failed", "reused_run_present",
        "write_target_exceeded", "non_live_surface", "manifest_invalid",
    }
)


@dataclass(frozen=True, slots=True)
class CohortRampGateReceiptPayload:
    target_plan_sha256: str
    target_cycle_id: str
    input_snapshot_sha256: str
    gate_version: str
    metric_policy: str
    predecessor_binding: Mapping[str, object]
    observed_metrics: Mapping[str, object]
    decision: str
    reason_codes: tuple[str, ...]
    evidence_watermark: str

    def to_wire(self) -> dict[str, object]:
        return {
            "target_plan_sha256": self.target_plan_sha256,
            "target_cycle_id": self.target_cycle_id,
            "input_snapshot_sha256": self.input_snapshot_sha256,
            "gate_version": self.gate_version,
            "metric_policy": self.metric_policy,
            "predecessor_binding": dict(self.predecessor_binding),
            "observed_metrics": dict(self.observed_metrics),
            "decision": self.decision,
            "reason_codes": list(self.reason_codes),
            "evidence_watermark": self.evidence_watermark,
        }


def parse_cohort_ramp_gate_receipt_payload(
    value: Mapping[str, Any],
) -> CohortRampGateReceiptPayload:
    target_hash = _sha(value["target_plan_sha256"], "target_plan_sha256")
    snapshot = _sha(value["input_snapshot_sha256"], "input_snapshot_sha256")
    cycle_id = non_empty_string(value["target_cycle_id"], "target_cycle_id")
    if cycle_id not in {"c3", "c4", "c5", "c6"}:
        raise ContractError("contract_enum_invalid", "target_cycle_id")
    policy = value["metric_policy"]
    if policy not in {"PREDECESSOR_INTEGRITY_ONLY", "RAMP_PARITY_AND_PERFORMANCE"}:
        raise ContractError("contract_enum_invalid", "metric_policy")
    binding = _mapping(value["predecessor_binding"], _BINDING_FIELDS, "predecessor_binding")
    _sha(binding["plan_sha256"], "predecessor_binding.plan_sha256")
    uuid_value(binding["manifest_artifact_id"], "manifest_artifact_id")
    _sha(binding["manifest_content_hash"], "manifest_content_hash")
    uuid_value(binding["mode_receipt_artifact_id"], "mode_receipt_artifact_id")
    _sha(binding["mode_receipt_content_hash"], "mode_receipt_content_hash")
    for field in ("collection_prefix", "cycle_id"):
        non_empty_string(binding[field], f"predecessor_binding.{field}")
    metrics = _mapping(value["observed_metrics"], _METRIC_FIELDS, "observed_metrics")
    for field in _METRIC_FIELDS - {"persistence_surface"}:
        _integer(metrics[field], f"observed_metrics.{field}")
    non_empty_string(metrics["persistence_surface"], "persistence_surface")
    reasons = _strings(value["reason_codes"], "reason_codes")
    if not set(reasons).issubset(_REASONS):
        raise ContractError("contract_enum_invalid", "reason_codes")
    decision = value["decision"]
    if decision not in {"PASS", "DENIED"} or (decision == "DENIED") is not bool(reasons):
        raise ContractError("contract_value_invalid", "decision")
    if value["gate_version"] != "1.0.0":
        raise ContractError("contract_value_invalid", "gate_version")
    watermark = non_empty_string(value["evidence_watermark"], "evidence_watermark")
    if value["created_at"] != watermark:
        raise ContractError("contract_value_invalid", "evidence_watermark")
    return CohortRampGateReceiptPayload(
        target_hash, cycle_id, snapshot, "1.0.0", policy,
        MappingProxyType(dict(binding)), MappingProxyType(dict(metrics)),
        decision, reasons, watermark,
    )


def _mapping(value: Any, fields: frozenset[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", name)
    require_exact_fields(value, fields, name)
    return value


def _sha(value: Any, field: str) -> str:
    text = non_empty_string(value, field)
    if not SHA256.fullmatch(text):
        raise ContractError("contract_hash_invalid", field)
    return text


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractError("contract_type_invalid", field)
    return value


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ContractError("contract_type_invalid", field)
    result = tuple(value)
    if result != tuple(sorted(set(result))):
        raise ContractError("contract_order_or_uniqueness_invalid", field)
    return result
