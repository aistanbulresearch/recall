from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any

from ..errors import ContractError
from ..validation import require_exact_fields
from .scheduler_v3 import _HISTORY_FIELDS
from .scheduler_v33 import _DEADLINE_FIELDS, require_deadline_completion_binding


def parse_v34_history(
    value: Any, envelope: Mapping[str, Any]
) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or len(value) != 8:
        raise ContractError("contract_type_invalid", "execution_history")
    rows: list[Mapping[str, object]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            raise ContractError("contract_type_invalid", "execution_history")
        require_exact_fields(raw, _HISTORY_FIELDS, "execution_history")
        row = dict(raw)
        row["sequence_index"] = integer(
            row["sequence_index"], "sequence_index", minimum=1
        )
        row["runs_created"] = integer(row["runs_created"], "runs_created")
        row["runs_predicted"] = integer(row["runs_predicted"], "runs_predicted")
        rows.append(MappingProxyType(row))
    if [item["sequence_index"] for item in rows] != list(range(1, 9)):
        raise ContractError(
            "contract_order_or_uniqueness_invalid", "execution_history"
        )
    compressed = rows[2:]
    current_status = "COMPLETE" if envelope["status"] == "VALID" else "INCOMPLETE"
    expected = [
        ("c1", "COMPLETE"),
        ("c2", "COMPLETE"),
        ("c3", "HISTORICAL_ATTEMPTS_PRESERVED"),
        ("c4", "RETIRED_TIMEBOX"),
        ("c5", "RETIRED_TIMEBOX"),
        ("c6", current_status),
    ]
    if [(item["cycle_id"], item["execution_status"]) for item in compressed] != expected:
        raise ContractError("contract_value_invalid", "final_only_history")
    for row in compressed[3:5]:
        if row["executed_at"] is not None or row["runs_created"] != 0:
            raise ContractError("contract_value_invalid", "retired_history")
    current = compressed[-1]
    if (
        current["source_schema_version"] != "CohortDayManifest/3.4.0"
        or current["executed_at"] != envelope["created_at"]
        or current["runs_created"]
        != len(envelope["delta"]["authoritative_run_ids"])
        or current["runs_predicted"] != envelope["delta"]["runs_predicted"]
    ):
        raise ContractError("contract_value_invalid", "execution_history.current")
    return tuple(rows)


def parse_v34_cumulative(
    value: Any,
    history: tuple[Mapping[str, object], ...],
    supersession: Mapping[str, object],
) -> Mapping[str, int]:
    fields = frozenset(
        {
            "compressed_cycles_completed",
            "successful_compressed_cycles",
            "runs_predicted",
            "runs_created",
            "distinct_execution_dates",
            "logical_days_covered",
            "historical_incomplete_attempts",
        }
    )
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "cumulative")
    require_exact_fields(value, fields, "cumulative")
    parsed = {field: integer(value[field], field) for field in fields}
    compressed = history[2:]
    active = [
        item for item in compressed if item["execution_status"] != "RETIRED_TIMEBOX"
    ]
    expected = {
        "compressed_cycles_completed": sum(
            item["execution_status"] == "COMPLETE" for item in compressed
        ),
        "successful_compressed_cycles": sum(
            item["execution_status"] == "COMPLETE"
            and item["runs_created"] == item["runs_predicted"]
            for item in compressed
        ),
        "runs_predicted": sum(int(item["runs_predicted"]) for item in active),
        "runs_created": sum(int(item["runs_created"]) for item in active),
        "distinct_execution_dates": len(
            {
                str(item["executed_at"])[:10]
                for item in active
                if item["executed_at"] is not None
            }
        ),
        "logical_days_covered": len(active),
        "historical_incomplete_attempts": len(
            supersession["historical_evidence"]
        )
        - 2,
    }
    if parsed != expected:
        raise ContractError("contract_value_invalid", "cumulative")
    return MappingProxyType(parsed)


def parse_v34_parity(value: Any, envelope: Mapping[str, Any]) -> Mapping[str, object]:
    bool_fields = {
        "new_epoch_required",
        "same_write_path_as_ramp",
        "parity_match",
        "epoch_parity_match",
        "fresh_write_parity_match",
    }
    fields = frozenset(
        {
            "expected_newly_created_runs",
            "actual_newly_created_runs",
            "expected_reused_runs",
            "actual_reused_runs",
            *bool_fields,
        }
    )
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "parity")
    require_exact_fields(value, fields, "parity")
    parsed = dict(value)
    for field in fields - bool_fields:
        parsed[field] = integer(value[field], field)
    for field in bool_fields:
        if not isinstance(value[field], bool):
            raise ContractError("contract_type_invalid", field)
    delta = envelope["delta"]
    fresh = (
        len(delta["newly_created_run_ids"]) == delta["runs_predicted"]
        and not delta["reused_run_ids"]
    )
    epoch = len(delta["authoritative_run_ids"]) == delta["runs_predicted"]
    if (
        parsed["expected_newly_created_runs"] != delta["runs_predicted"]
        or parsed["actual_newly_created_runs"]
        != len(delta["newly_created_run_ids"])
        or parsed["expected_reused_runs"] != 0
        or parsed["actual_reused_runs"] != len(delta["reused_run_ids"])
        or not value["new_epoch_required"]
        or not value["same_write_path_as_ramp"]
        or value["parity_match"] is not fresh
        or value["fresh_write_parity_match"] is not fresh
        or value["epoch_parity_match"] is not epoch
    ):
        raise ContractError("contract_value_invalid", "parity")
    return MappingProxyType(parsed)


def parse_v34_deadline(value: Mapping[str, Any]) -> Mapping[str, object]:
    raw = value["deadline_policy"]
    if not isinstance(raw, Mapping):
        raise ContractError("contract_type_invalid", "deadline_policy")
    require_exact_fields(raw, _DEADLINE_FIELDS, "deadline_policy")
    parsed = dict(raw)
    numeric = {
        "write_timeout_seconds",
        "agent_timeout_seconds",
        "execution_timeout_seconds",
    }
    for field in _DEADLINE_FIELDS - numeric:
        parsed[field] = timestamp(raw[field], field)
    for field in numeric:
        parsed[field] = integer(raw[field], field)
    start = datetime_value(value["window_start"])
    window_end = datetime_value(value["window_end"])
    trigger = datetime_value(parsed["trigger_started_at"])
    write_completed = datetime_value(parsed["write_completed_at"])
    agent_completed = datetime_value(parsed["agent_completed_at"])
    end_to_end = start + timedelta(seconds=int(parsed["execution_timeout_seconds"]))
    if (
        not start <= trigger <= window_end
        or not trigger <= write_completed <= agent_completed
        or parsed["trigger_window_end"] != value["window_end"]
        or datetime_value(parsed["write_deadline"])
        != min(
            trigger + timedelta(seconds=int(parsed["write_timeout_seconds"])),
            end_to_end,
        )
        or datetime_value(parsed["agent_deadline"])
        != min(
            write_completed + timedelta(seconds=int(parsed["agent_timeout_seconds"])),
            end_to_end,
        )
        or datetime_value(parsed["authoritative_end_to_end_deadline"])
        != end_to_end
    ):
        raise ContractError("contract_value_invalid", "deadline_policy")
    require_deadline_completion_binding(value["created_at"], parsed)
    return MappingProxyType(parsed)


def integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ContractError("contract_type_invalid", field)
    return value


def timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ContractError("contract_timestamp_invalid", field)
    datetime_value(value)
    return value


def datetime_value(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("contract_timestamp_invalid", "timestamp") from exc
