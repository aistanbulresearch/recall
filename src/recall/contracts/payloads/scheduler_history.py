from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from types import MappingProxyType
from typing import Any

from ..errors import ContractError
from ..validation import require_exact_fields, uuid_value


def parse_execution_history(value: Any) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or not value:
        raise ContractError("contract_type_invalid", "execution_history")
    parsed = []
    fields = frozenset(
        {
            "day_index",
            "executed_at",
            "selected_for_date",
            "runs_created",
            "runs_predicted",
            "execution_status",
            "failure_receipt_id",
        }
    )
    for item in value:
        if not isinstance(item, Mapping):
            raise ContractError("contract_type_invalid", "execution_history")
        require_exact_fields(item, fields, "execution_history")
        selected = _date(
            item["selected_for_date"], "execution_history.selected_for_date"
        )
        execution_status = item["execution_status"]
        if execution_status not in {"COMPLETE", "INCOMPLETE"}:
            raise ContractError(
                "contract_enum_invalid", "execution_history.execution_status"
            )
        raw_executed_at = item["executed_at"]
        raw_failure_id = item["failure_receipt_id"]
        if execution_status == "COMPLETE":
            executed_at = _timestamp(
                raw_executed_at, "execution_history.executed_at"
            )
            if executed_at[:10] != selected:
                raise ContractError("contract_date_mismatch", "execution_history")
            if raw_failure_id is not None:
                raise ContractError(
                    "contract_value_invalid", "execution_history.failure_receipt_id"
                )
            failure_receipt_id = None
        else:
            if raw_executed_at is not None:
                raise ContractError(
                    "contract_value_invalid", "execution_history.executed_at"
                )
            executed_at = None
            failure_receipt_id = str(
                uuid_value(raw_failure_id, "execution_history.failure_receipt_id")
            )
        runs_created = _integer(
            item["runs_created"], "execution_history.runs_created"
        )
        if execution_status == "INCOMPLETE" and runs_created != 0:
            raise ContractError(
                "contract_value_invalid", "execution_history.runs_created"
            )
        parsed.append(
            MappingProxyType(
                {
                    "day_index": _integer(
                        item["day_index"],
                        "execution_history.day_index",
                        minimum=1,
                    ),
                    "executed_at": executed_at,
                    "selected_for_date": selected,
                    "runs_created": runs_created,
                    "runs_predicted": _integer(
                        item["runs_predicted"],
                        "execution_history.runs_predicted",
                    ),
                    "execution_status": execution_status,
                    "failure_receipt_id": failure_receipt_id,
                }
            )
        )
    if [item["day_index"] for item in parsed] != list(range(1, len(parsed) + 1)):
        raise ContractError("contract_order_or_uniqueness_invalid", "execution_history")
    if len({item["selected_for_date"] for item in parsed}) != len(parsed):
        raise ContractError("contract_order_or_uniqueness_invalid", "selected_for_date")
    if [item["selected_for_date"] for item in parsed] != sorted(
        item["selected_for_date"] for item in parsed
    ):
        raise ContractError("contract_order_or_uniqueness_invalid", "selected_for_date")
    return tuple(parsed)


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ContractError("contract_type_invalid", field)
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


def _timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ContractError("contract_timestamp_invalid", field)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("contract_timestamp_invalid", field) from exc
    return value
