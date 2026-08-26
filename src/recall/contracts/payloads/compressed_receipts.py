from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType
from typing import Any

from ..errors import ContractError
from ..validation import SHA256, non_empty_string, require_exact_fields, uuid_value


@dataclass(frozen=True, slots=True)
class CompressedCycleFailureReceiptPayload:
    cohort_due_date: str
    scheduled_for: str
    failure_code: str
    runs_predicted: int
    runs_created: int
    evidence_state: str
    decision_reference: str
    continuation_policy: str

    def to_wire(self) -> dict[str, object]:
        return {
            "cohort_due_date": self.cohort_due_date,
            "scheduled_for": self.scheduled_for,
            "failure_code": self.failure_code,
            "runs_predicted": self.runs_predicted,
            "runs_created": self.runs_created,
            "evidence_state": self.evidence_state,
            "decision_reference": self.decision_reference,
            "continuation_policy": self.continuation_policy,
        }


@dataclass(frozen=True, slots=True)
class CohortHeadroomReceiptPayload:
    plan_sha256: str
    input_snapshot_sha256: str
    gate_version: str
    required_cycle_ids: tuple[str, ...]
    observed_cycles: tuple[Mapping[str, object], ...]
    aggregate_runs_predicted: int
    aggregate_runs_created: int
    aggregate_run_events: int
    decision: str
    reason_codes: tuple[str, ...]
    evidence_watermark: str

    def to_wire(self) -> dict[str, object]:
        observed = []
        for item in self.observed_cycles:
            row = dict(item)
            row["reason_codes"] = list(row["reason_codes"])
            observed.append(row)
        return {
            "plan_sha256": self.plan_sha256,
            "input_snapshot_sha256": self.input_snapshot_sha256,
            "gate_version": self.gate_version,
            "required_cycle_ids": list(self.required_cycle_ids),
            "observed_cycles": observed,
            "aggregate_runs_predicted": self.aggregate_runs_predicted,
            "aggregate_runs_created": self.aggregate_runs_created,
            "aggregate_run_events": self.aggregate_run_events,
            "decision": self.decision,
            "reason_codes": list(self.reason_codes),
            "evidence_watermark": self.evidence_watermark,
        }


def parse_compressed_cycle_failure_receipt_payload(
    value: Mapping[str, Any],
) -> CompressedCycleFailureReceiptPayload:
    due = _date(value["cohort_due_date"], "cohort_due_date")
    scheduled = _timestamp(value["scheduled_for"], "scheduled_for")
    if (
        due != "2026-08-26"
        or scheduled != "2026-08-26T16:00:00Z"
        or value["failure_code"] != "previous_cohort_manifest_missing"
        or value["runs_predicted"] != 3
        or value["runs_created"] != 0
        or value["evidence_state"] != "OWNER_REPORTED"
        or value["decision_reference"] != "DEC-2026-08-26-046"
        or value["continuation_policy"] != "COMPRESSED_RECOVERY"
        or value["status"] != "INCOMPLETE"
    ):
        raise ContractError("contract_value_invalid", "compressed_failure")
    return CompressedCycleFailureReceiptPayload(
        cohort_due_date=due,
        scheduled_for=scheduled,
        failure_code="previous_cohort_manifest_missing",
        runs_predicted=3,
        runs_created=0,
        evidence_state="OWNER_REPORTED",
        decision_reference="DEC-2026-08-26-046",
        continuation_policy="COMPRESSED_RECOVERY",
    )


def parse_cohort_headroom_receipt_payload(
    value: Mapping[str, Any],
) -> CohortHeadroomReceiptPayload:
    plan_hash = _sha(value["plan_sha256"], "plan_sha256")
    snapshot = _sha(value["input_snapshot_sha256"], "input_snapshot_sha256")
    if value["gate_version"] != "1.0.0":
        raise ContractError("contract_value_invalid", "gate_version")
    cycle_ids = _strings(value["required_cycle_ids"], "required_cycle_ids")
    if cycle_ids != ("c1", "c2", "c3", "c4", "c5"):
        raise ContractError("contract_value_invalid", "required_cycle_ids")
    observed = _observed_cycles(value["observed_cycles"])
    decision = value["decision"]
    reasons = _strings(value["reason_codes"], "reason_codes")
    if decision not in {"PASS", "DENIED"} or (decision == "DENIED") is not bool(reasons):
        raise ContractError("contract_value_invalid", "headroom_decision")
    predicted = _integer(value["aggregate_runs_predicted"], "aggregate_runs_predicted")
    created = _integer(value["aggregate_runs_created"], "aggregate_runs_created")
    events = _integer(value["aggregate_run_events"], "aggregate_run_events")
    if decision == "PASS" and not predicted == created == events:
        raise ContractError("contract_value_invalid", "headroom_aggregate")
    watermark = _timestamp(value["evidence_watermark"], "evidence_watermark")
    if value["created_at"] != watermark:
        raise ContractError("contract_value_invalid", "evidence_watermark")
    return CohortHeadroomReceiptPayload(
        plan_sha256=plan_hash,
        input_snapshot_sha256=snapshot,
        gate_version="1.0.0",
        required_cycle_ids=cycle_ids,
        observed_cycles=observed,
        aggregate_runs_predicted=predicted,
        aggregate_runs_created=created,
        aggregate_run_events=events,
        decision=decision,
        reason_codes=reasons,
        evidence_watermark=watermark,
    )


def _observed_cycles(value: Any) -> tuple[Mapping[str, object], ...]:
    fields = frozenset(
        {
            "cycle_id",
            "manifest_artifact_id",
            "manifest_content_hash",
            "manifest_status",
            "runs_predicted",
            "runs_created",
            "scan_runs_readback",
            "run_events",
            "mode_receipt_bound",
            "reason_codes",
        }
    )
    if not isinstance(value, list):
        raise ContractError("contract_type_invalid", "observed_cycles")
    if len(value) != 5:
        raise ContractError("contract_value_invalid", "observed_cycles")
    parsed = []
    for expected_cycle_id, item in zip(
        ("c1", "c2", "c3", "c4", "c5"), value, strict=True
    ):
        if not isinstance(item, Mapping):
            raise ContractError("contract_type_invalid", "observed_cycles")
        require_exact_fields(item, fields, "observed_cycles")
        manifest_id = item["manifest_artifact_id"]
        manifest_hash = item["manifest_content_hash"]
        if manifest_id is not None:
            uuid_value(manifest_id, "manifest_artifact_id")
        if manifest_hash is not None:
            _sha(manifest_hash, "manifest_content_hash")
        if item["cycle_id"] != expected_cycle_id:
            raise ContractError(
                "contract_order_or_uniqueness_invalid", "observed_cycles"
            )
        for field in (
            "runs_predicted",
            "runs_created",
            "scan_runs_readback",
            "run_events",
        ):
            _integer(item[field], field)
        if not isinstance(item["mode_receipt_bound"], bool):
            raise ContractError("contract_type_invalid", "mode_receipt_bound")
        if item["manifest_status"] not in {"MISSING", "VALID", "INCOMPLETE"}:
            raise ContractError("contract_enum_invalid", "manifest_status")
        parsed.append(
            MappingProxyType(
                {
                    **dict(item),
                    "reason_codes": _strings(item["reason_codes"], "reason_codes"),
                }
            )
        )
    return tuple(parsed)


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ContractError("contract_type_invalid", field)
    values = tuple(value)
    if values != tuple(sorted(set(values))):
        raise ContractError("contract_order_or_uniqueness_invalid", field)
    return values


def _sha(value: Any, field: str) -> str:
    text = non_empty_string(value, field)
    if not SHA256.fullmatch(text):
        raise ContractError("contract_hash_invalid", field)
    return text


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractError("contract_type_invalid", field)
    return value


def _date(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ContractError("contract_type_invalid", field)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError("contract_date_invalid", field) from exc
    return value


def _timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ContractError("contract_timestamp_invalid", field)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("contract_timestamp_invalid", field) from exc
    return value
