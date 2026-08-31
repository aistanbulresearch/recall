from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType
from typing import Any

from ..errors import ContractError
from ..validation import SHA256, non_empty_string, require_exact_fields, tuple_of_strings, uuid_value


_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_READBACK_FIELDS = frozenset(
    {"artifacts", "watch_cases", "scan_runs", "scan_run_events", "review_tasks"}
)


@dataclass(frozen=True, slots=True)
class CohortHistoryReceiptPayload:
    evidence_path: str
    evidence_sha256: str
    evidence_git_blob_oid: str
    source_commit: str
    source_tree: str
    phase: str
    trigger_code: str
    day_index: int
    executed_at: str
    selected_for_date: str
    created_run_ids: tuple[str, ...]
    selected_case_ids: tuple[str, ...]
    excluded_case_ids: tuple[str, ...]
    runs_created: int
    runs_predicted: int
    readback_counts: Mapping[str, int]
    direct_exit_code: int
    evidence_classification: str
    atomic_check_ids: tuple[str, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "evidence_path": self.evidence_path,
            "evidence_sha256": self.evidence_sha256,
            "evidence_git_blob_oid": self.evidence_git_blob_oid,
            "source_commit": self.source_commit,
            "source_tree": self.source_tree,
            "phase": self.phase,
            "trigger_code": self.trigger_code,
            "day_index": self.day_index,
            "executed_at": self.executed_at,
            "selected_for_date": self.selected_for_date,
            "created_run_ids": list(self.created_run_ids),
            "selected_case_ids": list(self.selected_case_ids),
            "excluded_case_ids": list(self.excluded_case_ids),
            "runs_created": self.runs_created,
            "runs_predicted": self.runs_predicted,
            "readback_counts": dict(self.readback_counts),
            "direct_exit_code": self.direct_exit_code,
            "evidence_classification": self.evidence_classification,
            "atomic_check_ids": list(self.atomic_check_ids),
        }


def parse_cohort_history_receipt_payload(
    value: Mapping[str, Any],
) -> CohortHistoryReceiptPayload:
    evidence_path = non_empty_string(value["evidence_path"], "evidence_path")
    if evidence_path.startswith(("/", "\\")) or ".." in evidence_path.replace(
        "\\", "/"
    ).split("/"):
        raise ContractError("contract_path_invalid", "evidence_path")
    evidence_sha256 = non_empty_string(value["evidence_sha256"], "evidence_sha256")
    if not SHA256.fullmatch(evidence_sha256):
        raise ContractError("contract_hash_invalid", "evidence_sha256")
    blob_oid = _hex40(value["evidence_git_blob_oid"], "evidence_git_blob_oid")
    source_commit = _hex40(value["source_commit"], "source_commit")
    source_tree = _hex40(value["source_tree"], "source_tree")
    executed_at = _timestamp(value["executed_at"], "executed_at")
    selected_for_date = _date(value["selected_for_date"], "selected_for_date")
    if executed_at[:10] != selected_for_date:
        raise ContractError("contract_date_mismatch", "executed_at")
    created = _uuid_list(value["created_run_ids"], "created_run_ids")
    selected = _uuid_list(value["selected_case_ids"], "selected_case_ids")
    excluded = _uuid_list(value["excluded_case_ids"], "excluded_case_ids")
    runs_created = _integer(value["runs_created"], "runs_created")
    runs_predicted = _integer(value["runs_predicted"], "runs_predicted")
    readback = _readback_counts(value["readback_counts"])
    atomic_ids = tuple_of_strings(value["atomic_check_ids"], "atomic_check_ids")
    if atomic_ids != tuple(sorted(set(atomic_ids))) or not atomic_ids:
        raise ContractError("contract_order_or_uniqueness_invalid", "atomic_check_ids")
    if value["phase"] != "first" or value["trigger_code"] != "DAY1_MANUAL":
        raise ContractError("contract_value_invalid", "historical_execution_identity")
    if _integer(value["day_index"], "day_index", minimum=1) != 1:
        raise ContractError("contract_value_invalid", "day_index")
    if runs_created != len(created) or runs_created != 1:
        raise ContractError("contract_value_invalid", "runs_created")
    if runs_predicted != 1 or len(selected) != 1 or len(excluded) != 2:
        raise ContractError("contract_value_invalid", "historical_execution_counts")
    if value["run_id"] != created[0]:
        raise ContractError("contract_value_invalid", "run_id")
    if readback["scan_runs"] != 1 or readback["scan_run_events"] != 1:
        raise ContractError("contract_value_invalid", "readback_counts")
    if _integer(value["direct_exit_code"], "direct_exit_code") != 0:
        raise ContractError("contract_value_invalid", "direct_exit_code")
    classification = non_empty_string(
        value["evidence_classification"], "evidence_classification"
    )
    if classification != "LIVE_INFRASTRUCTURE_SYNTHETIC_DATA":
        raise ContractError("contract_value_invalid", "evidence_classification")
    return CohortHistoryReceiptPayload(
        evidence_path=evidence_path,
        evidence_sha256=evidence_sha256,
        evidence_git_blob_oid=blob_oid,
        source_commit=source_commit,
        source_tree=source_tree,
        phase="first",
        trigger_code="DAY1_MANUAL",
        day_index=1,
        executed_at=executed_at,
        selected_for_date=selected_for_date,
        created_run_ids=created,
        selected_case_ids=selected,
        excluded_case_ids=excluded,
        runs_created=runs_created,
        runs_predicted=runs_predicted,
        readback_counts=readback,
        direct_exit_code=0,
        evidence_classification=classification,
        atomic_check_ids=atomic_ids,
    )


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ContractError("contract_type_invalid", field)
    return value


def _hex40(value: Any, field: str) -> str:
    text = non_empty_string(value, field)
    if not _HEX40.fullmatch(text):
        raise ContractError("contract_hash_invalid", field)
    return text


def _timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ContractError("contract_timestamp_invalid", field)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("contract_timestamp_invalid", field) from exc
    return value


def _date(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ContractError("contract_type_invalid", field)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError("contract_date_invalid", field) from exc
    if parsed.isoformat() != value:
        raise ContractError("contract_date_invalid", field)
    return value


def _uuid_list(value: Any, field: str) -> tuple[str, ...]:
    values = tuple_of_strings(value, field)
    for item in values:
        uuid_value(item, field)
    if values != tuple(sorted(set(values))):
        raise ContractError("contract_order_or_uniqueness_invalid", field)
    return values


def _readback_counts(value: Any) -> Mapping[str, int]:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "readback_counts")
    require_exact_fields(value, _READBACK_FIELDS, "readback_counts")
    return MappingProxyType(
        {field: _integer(value[field], f"readback_counts.{field}") for field in _READBACK_FIELDS}
    )
