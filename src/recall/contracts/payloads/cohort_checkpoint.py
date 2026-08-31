from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ..errors import ContractError
from ..validation import (
    non_empty_string,
    require_exact_fields,
    tuple_of_strings,
    uuid_value,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMPLETED_FIELDS = frozenset(
    {
        "case_id", "run_id", "terminal_state", "audit_status",
        "citation_audit_receipt_id", "policy_decision_id", "failure_receipt_ids",
        "agent_execution_receipt_ids",
    }
)
_FAILED_FIELDS = frozenset({"case_id", "run_id", "error_code"})
_BATCH_METRIC_FIELDS = frozenset(
    {
        "scope", "measurement_semantics", "persistence_surface",
        "batch_max_workers", "selected_case_count", "ledger_operation_counts",
        "committed_case_documents", "started_at", "completed_at",
        "worker_elapsed_ms", "readback_elapsed_ms", "total_elapsed_ms",
        "effective_write_millis_per_case",
    }
)


@dataclass(frozen=True, slots=True)
class CohortExecutionCheckpointPayload:
    plan_sha256: str
    cycle_id: str
    expected_manifest_id: str
    checkpoint_status: str
    total_cases: int
    completed_outcomes: tuple[Mapping[str, object], ...]
    failed_cases: tuple[Mapping[str, str], ...]
    policy_outcomes_synthesized: bool

    def to_wire(self) -> dict[str, object]:
        return {
            "plan_sha256": self.plan_sha256,
            "cycle_id": self.cycle_id,
            "expected_manifest_id": self.expected_manifest_id,
            "checkpoint_status": self.checkpoint_status,
            "total_cases": self.total_cases,
            "completed_outcomes": [
                {
                    **dict(item),
                    "failure_receipt_ids": list(item["failure_receipt_ids"]),
                    "agent_execution_receipt_ids": list(
                        item["agent_execution_receipt_ids"]
                    ),
                }
                for item in self.completed_outcomes
            ],
            "failed_cases": [dict(item) for item in self.failed_cases],
            "policy_outcomes_synthesized": self.policy_outcomes_synthesized,
        }


@dataclass(frozen=True, slots=True)
class BatchExecutionReceiptPayload:
    plan_sha256: str
    cycle_id: str
    cycle_attempt_id: str
    ordered_run_ids: tuple[str, ...]
    scan_run_artifact_ids: tuple[str, ...]
    created_run_ids: tuple[str, ...]
    recovered_current_epoch_run_ids: tuple[str, ...]
    measurement_status: str
    write_metrics: Mapping[str, object]

    def to_wire(self) -> dict[str, object]:
        return {
            "plan_sha256": self.plan_sha256,
            "cycle_id": self.cycle_id,
            "cycle_attempt_id": self.cycle_attempt_id,
            "ordered_run_ids": list(self.ordered_run_ids),
            "scan_run_artifact_ids": list(self.scan_run_artifact_ids),
            "created_run_ids": list(self.created_run_ids),
            "recovered_current_epoch_run_ids": list(
                self.recovered_current_epoch_run_ids
            ),
            "measurement_status": self.measurement_status,
            "write_metrics": dict(self.write_metrics),
        }


def parse_batch_execution_receipt_payload(
    value: Mapping[str, Any],
) -> BatchExecutionReceiptPayload:
    plan_sha = non_empty_string(value["plan_sha256"], "plan_sha256")
    if not _SHA256.fullmatch(plan_sha):
        raise ContractError("contract_hash_invalid", "plan_sha256")
    cycle_id = non_empty_string(value["cycle_id"], "cycle_id")
    if not re.fullmatch(r"c[1-9][0-9]*", cycle_id):
        raise ContractError("contract_value_invalid", "cycle_id")
    attempt_id = str(uuid_value(value["cycle_attempt_id"], "cycle_attempt_id"))
    ordered = _uuid_tuple(value["ordered_run_ids"], "ordered_run_ids")
    scan_ids = _uuid_tuple(
        value["scan_run_artifact_ids"], "scan_run_artifact_ids"
    )
    created = _uuid_tuple(value["created_run_ids"], "created_run_ids")
    recovered = _uuid_tuple(
        value["recovered_current_epoch_run_ids"],
        "recovered_current_epoch_run_ids",
    )
    if (
        not ordered
        or len(ordered) != len(scan_ids)
        or set(created) & set(recovered)
        or set(created) | set(recovered) != set(ordered)
        or set(scan_ids) != set(value["input_artifact_ids"])
    ):
        raise ContractError("contract_value_invalid", "batch_run_partition")
    status = value["measurement_status"]
    if status not in {"MEASURED", "NOT_EVALUATED"}:
        raise ContractError("contract_enum_invalid", "measurement_status")
    if (status == "MEASURED") is not (len(created) == len(ordered)):
        raise ContractError("contract_value_invalid", "measurement_status")
    metrics = value["write_metrics"]
    if not isinstance(metrics, Mapping):
        raise ContractError("contract_type_invalid", "write_metrics")
    require_exact_fields(metrics, _BATCH_METRIC_FIELDS, "write_metrics")
    if metrics["selected_case_count"] != len(ordered):
        raise ContractError("contract_value_invalid", "selected_case_count")
    return BatchExecutionReceiptPayload(
        plan_sha,
        cycle_id,
        attempt_id,
        ordered,
        scan_ids,
        created,
        recovered,
        status,
        MappingProxyType(dict(metrics)),
    )


def parse_cohort_execution_checkpoint_payload(
    value: Mapping[str, Any],
) -> CohortExecutionCheckpointPayload:
    plan_sha = non_empty_string(value["plan_sha256"], "plan_sha256")
    if not _SHA256.fullmatch(plan_sha):
        raise ContractError("contract_hash_invalid", "plan_sha256")
    cycle_id = non_empty_string(value["cycle_id"], "cycle_id")
    if not re.fullmatch(r"c[1-9][0-9]*", cycle_id):
        raise ContractError("contract_value_invalid", "cycle_id")
    expected_manifest_id = str(
        uuid_value(value["expected_manifest_id"], "expected_manifest_id")
    )
    if value["checkpoint_status"] != "INCOMPLETE":
        raise ContractError("contract_value_invalid", "checkpoint_status")
    total_cases = _integer(value["total_cases"], "total_cases", minimum=1)
    completed = _completed(value["completed_outcomes"])
    failed = _failed(value["failed_cases"])
    if not failed or len(completed) + len(failed) != total_cases:
        raise ContractError("contract_value_invalid", "checkpoint_case_partition")
    case_ids = [str(item["case_id"]) for item in (*completed, *failed)]
    run_ids = [str(item["run_id"]) for item in (*completed, *failed)]
    if len(set(case_ids)) != total_cases or len(set(run_ids)) != total_cases:
        raise ContractError("contract_order_or_uniqueness_invalid", "checkpoint_cases")
    if value["policy_outcomes_synthesized"] is not False:
        raise ContractError("contract_value_invalid", "policy_outcomes_synthesized")
    required_inputs = set()
    for item in completed:
        required_inputs.update(item["failure_receipt_ids"])
        required_inputs.update(item["agent_execution_receipt_ids"])
        if item["citation_audit_receipt_id"] is not None:
            required_inputs.add(item["citation_audit_receipt_id"])
        if item["policy_decision_id"] is not None:
            required_inputs.add(item["policy_decision_id"])
    if not required_inputs.issubset(set(value["input_artifact_ids"])):
        raise ContractError("contract_value_invalid", "checkpoint_inputs")
    if value["status"] != "INCOMPLETE":
        raise ContractError("contract_value_invalid", "status")
    return CohortExecutionCheckpointPayload(
        plan_sha,
        cycle_id,
        expected_manifest_id,
        "INCOMPLETE",
        total_cases,
        completed,
        failed,
        False,
    )


def _completed(value: Any) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list):
        raise ContractError("contract_type_invalid", "completed_outcomes")
    rows = []
    for raw in value:
        if not isinstance(raw, Mapping):
            raise ContractError("contract_type_invalid", "completed_outcomes")
        require_exact_fields(raw, _COMPLETED_FIELDS, "completed_outcomes")
        policy = raw["policy_decision_id"]
        terminal = non_empty_string(raw["terminal_state"], "terminal_state")
        audit = non_empty_string(raw["audit_status"], "audit_status")
        if terminal not in {"NO_ACTION", "ABSTAIN", "REVIEW_REQUIRED", "HALTED"}:
            raise ContractError("contract_enum_invalid", "terminal_state")
        if audit not in {"COMPLETE", "INCOMPLETE", "NOT_EVALUATED"}:
            raise ContractError("contract_enum_invalid", "audit_status")
        citation = (
            None
            if raw["citation_audit_receipt_id"] is None
            else str(uuid_value(raw["citation_audit_receipt_id"], "citation_audit_receipt_id"))
        )
        failures = tuple(
            str(uuid_value(item, "failure_receipt_ids"))
            for item in tuple_of_strings(raw["failure_receipt_ids"], "failure_receipt_ids")
        )
        agent_receipts = tuple(
            str(uuid_value(item, "agent_execution_receipt_ids"))
            for item in tuple_of_strings(
                raw["agent_execution_receipt_ids"], "agent_execution_receipt_ids"
            )
        )
        policy_id = None if policy is None else str(uuid_value(policy, "policy_decision_id"))
        if terminal == "HALTED":
            if policy_id is not None or not failures:
                raise ContractError("contract_value_invalid", "completed_outcomes")
        elif policy_id is None or citation is None or failures:
            raise ContractError("contract_value_invalid", "completed_outcomes")
        if (audit == "NOT_EVALUATED") is not (citation is None):
            raise ContractError("contract_value_invalid", "audit_status")
        rows.append(
            MappingProxyType(
                {
                    "case_id": str(uuid_value(raw["case_id"], "case_id")),
                    "run_id": str(uuid_value(raw["run_id"], "run_id")),
                    "terminal_state": terminal,
                    "audit_status": audit,
                    "citation_audit_receipt_id": citation,
                    "policy_decision_id": policy_id,
                    "failure_receipt_ids": failures,
                    "agent_execution_receipt_ids": agent_receipts,
                }
            )
        )
    return tuple(rows)


def _failed(value: Any) -> tuple[Mapping[str, str], ...]:
    if not isinstance(value, list):
        raise ContractError("contract_type_invalid", "failed_cases")
    rows = []
    for raw in value:
        if not isinstance(raw, Mapping):
            raise ContractError("contract_type_invalid", "failed_cases")
        require_exact_fields(raw, _FAILED_FIELDS, "failed_cases")
        rows.append(
            MappingProxyType(
                {
                    "case_id": str(uuid_value(raw["case_id"], "case_id")),
                    "run_id": str(uuid_value(raw["run_id"], "run_id")),
                    "error_code": non_empty_string(raw["error_code"], "error_code"),
                }
            )
        )
    return tuple(rows)


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ContractError("contract_type_invalid", field)
    return value


def _uuid_tuple(value: Any, field: str) -> tuple[str, ...]:
    return tuple(
        str(uuid_value(item, field))
        for item in tuple_of_strings(value, field)
    )
