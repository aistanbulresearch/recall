from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType
from typing import Any

from ..errors import ContractError
from ..validation import SHA256, non_empty_string, require_exact_fields, uuid_value
from .scheduler import _parse_anchors, _parse_cases, _parse_delta


_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SCHEDULE_MODE = "COMPRESSED_MACHINE_TRIGGERED"
_TRIGGER_CODE = "COHORT_COMPRESSED_MACHINE_TRIGGERED"
_PLAN_SHA256 = "05e61f4bbe3d6bb7540ecae310e3c6f9423dcae3a7933db59ef4267e84fd9226"
_HISTORY_FIELDS = frozenset(
    {
        "sequence_index",
        "source_schema_version",
        "cycle_id",
        "cycle_index",
        "cohort_due_date",
        "scheduled_for",
        "window_start",
        "window_end",
        "trigger_code",
        "executed_at",
        "runs_created",
        "runs_predicted",
        "execution_status",
        "failure_receipt_id",
        "evidence_state",
        "schedule_mode",
    }
)


@dataclass(frozen=True, slots=True)
class CohortDayManifestV3Payload:
    day_index: int
    selected_for_date: str
    scheduled_for: str
    source_commit: str
    image_digest: str
    trigger_code: str
    previous_manifest_id: str | None
    managed_history_starts_at_day_index: int
    cycle_id: str
    cycle_index: int
    plan_version: str
    plan_sha256: str
    cohort_due_date: str
    window_start: str
    window_end: str
    schedule_mode: str
    headroom_receipt_id: str | None
    delta: Mapping[str, object]
    cumulative: Mapping[str, object]
    cases: tuple[Mapping[str, object], ...]
    vcv_anchors: tuple[Mapping[str, object], ...]
    execution_history: tuple[Mapping[str, object], ...]

    def to_wire(self) -> dict[str, object]:
        delta = dict(self.delta)
        for field in (
            "selected_case_ids",
            "excluded_case_ids",
            "newly_created_run_ids",
            "reused_run_ids",
            "authoritative_run_ids",
        ):
            delta[field] = list(delta[field])
        return {
            "day_index": self.day_index,
            "selected_for_date": self.selected_for_date,
            "scheduled_for": self.scheduled_for,
            "source_commit": self.source_commit,
            "image_digest": self.image_digest,
            "trigger_code": self.trigger_code,
            "previous_manifest_id": self.previous_manifest_id,
            "managed_history_starts_at_day_index": self.managed_history_starts_at_day_index,
            "cycle_id": self.cycle_id,
            "cycle_index": self.cycle_index,
            "plan_version": self.plan_version,
            "plan_sha256": self.plan_sha256,
            "cohort_due_date": self.cohort_due_date,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "schedule_mode": self.schedule_mode,
            "headroom_receipt_id": self.headroom_receipt_id,
            "delta": delta,
            "cumulative": dict(self.cumulative),
            "cases": [dict(item) for item in self.cases],
            "vcv_anchors": [dict(item) for item in self.vcv_anchors],
            "execution_history": [dict(item) for item in self.execution_history],
        }


def parse_cohort_day_manifest_v3_payload(
    value: Mapping[str, Any],
) -> CohortDayManifestV3Payload:
    due = _date(value["cohort_due_date"], "cohort_due_date")
    if value["selected_for_date"] != due:
        raise ContractError("contract_date_mismatch", "selected_for_date")
    window_start = _timestamp(value["window_start"], "window_start")
    window_end = _timestamp(value["window_end"], "window_end")
    scheduled_for = _timestamp(value["scheduled_for"], "scheduled_for")
    if not window_start < window_end or scheduled_for != window_start:
        raise ContractError("contract_value_invalid", "cycle_window")
    cycle_id = non_empty_string(value["cycle_id"], "cycle_id")
    cycle_index = _integer(value["cycle_index"], "cycle_index", minimum=1)
    if cycle_id != f"c{cycle_index}" or value["day_index"] != cycle_index + 1:
        raise ContractError("contract_value_invalid", "cycle_identity")
    source_commit = non_empty_string(value["source_commit"], "source_commit")
    if not _COMMIT.fullmatch(source_commit):
        raise ContractError("contract_hash_invalid", "source_commit")
    image_digest = non_empty_string(value["image_digest"], "image_digest")
    if not _IMAGE_DIGEST.fullmatch(image_digest):
        raise ContractError("contract_hash_invalid", "image_digest")
    plan_hash = non_empty_string(value["plan_sha256"], "plan_sha256")
    if not SHA256.fullmatch(plan_hash) or plan_hash != _PLAN_SHA256:
        raise ContractError("contract_hash_invalid", "plan_sha256")
    if (
        value["plan_version"] != "COMPRESSED_PREDICTION_PLAN_V2"
        or value["schedule_mode"] != _SCHEDULE_MODE
        or value["trigger_code"] != _TRIGGER_CODE
    ):
        raise ContractError("contract_value_invalid", "compressed_declaration")
    previous = value["previous_manifest_id"]
    previous_id = None if previous is None else str(
        uuid_value(previous, "previous_manifest_id")
    )
    if (cycle_index == 1) is not (previous_id is None):
        raise ContractError("contract_value_invalid", "previous_manifest_id")
    headroom_raw = value["headroom_receipt_id"]
    headroom_id = None if headroom_raw is None else str(
        uuid_value(headroom_raw, "headroom_receipt_id")
    )
    if (cycle_id == "c6") is not (headroom_id is not None):
        raise ContractError("contract_value_invalid", "headroom_receipt_id")
    delta = _parse_delta(value["delta"])
    cases = _parse_cases(value["cases"])
    anchors = _parse_anchors(value["vcv_anchors"])
    history = _parse_history(value["execution_history"])
    current = history[-1]
    if (
        current["cycle_id"] != cycle_id
        or current["cycle_index"] != cycle_index
        or current["cohort_due_date"] != due
        or current["scheduled_for"] != scheduled_for
        or current["window_start"] != window_start
        or current["window_end"] != window_end
        or current["execution_status"] != "COMPLETE"
        or current["schedule_mode"] != _SCHEDULE_MODE
        or current["source_schema_version"] != "CohortDayManifest/3.0.0"
        or current["trigger_code"] != _TRIGGER_CODE
        or value["created_at"] != current["executed_at"]
    ):
        raise ContractError("contract_value_invalid", "execution_history.current")
    if current["runs_created"] != len(delta["authoritative_run_ids"]):
        raise ContractError("contract_value_invalid", "runs_created")
    if current["runs_predicted"] != delta["runs_predicted"]:
        raise ContractError("contract_value_invalid", "runs_predicted")
    matched = current["runs_created"] == current["runs_predicted"]
    if delta["prediction_match"] is not matched or value["status"] != (
        "VALID" if matched else "INCOMPLETE"
    ):
        raise ContractError("contract_value_invalid", "current_cycle_status")
    cumulative = _parse_cumulative(value["cumulative"], history)
    selected = set(delta["selected_case_ids"])
    excluded = set(delta["excluded_case_ids"])
    if selected & excluded or len(selected | excluded) != 462:
        raise ContractError("contract_value_invalid", "delta.case_partition")
    if {item["case_id"] for item in cases} != selected:
        raise ContractError("contract_value_invalid", "cases")
    replay_vcvs = {item["vcv"] for item in cases if item["vcv"] is not None}
    if {item["vcv"] for item in anchors} != replay_vcvs:
        raise ContractError("contract_value_invalid", "vcv_anchors")
    input_ids = set(value["input_artifact_ids"])
    required = {item["artifact_id"] for item in anchors}
    required |= {
        item["failure_receipt_id"]
        for item in history
        if item["failure_receipt_id"] is not None
    }
    if previous_id is not None:
        required.add(previous_id)
    if headroom_id is not None:
        required.add(headroom_id)
    if not required.issubset(input_ids):
        raise ContractError("contract_value_invalid", "input_artifact_ids")
    return CohortDayManifestV3Payload(
        day_index=_integer(value["day_index"], "day_index", minimum=2),
        selected_for_date=due,
        scheduled_for=scheduled_for,
        source_commit=source_commit,
        image_digest=image_digest,
        trigger_code=_TRIGGER_CODE,
        previous_manifest_id=previous_id,
        managed_history_starts_at_day_index=_managed_start(value),
        cycle_id=cycle_id,
        cycle_index=cycle_index,
        plan_version="COMPRESSED_PREDICTION_PLAN_V2",
        plan_sha256=plan_hash,
        cohort_due_date=due,
        window_start=window_start,
        window_end=window_end,
        schedule_mode=_SCHEDULE_MODE,
        headroom_receipt_id=headroom_id,
        delta=delta,
        cumulative=cumulative,
        cases=cases,
        vcv_anchors=anchors,
        execution_history=history,
    )


def _parse_history(value: Any) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or not value:
        raise ContractError("contract_type_invalid", "execution_history")
    parsed: list[Mapping[str, object]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            raise ContractError("contract_type_invalid", "execution_history")
        require_exact_fields(raw, _HISTORY_FIELDS, "execution_history")
        row = dict(raw)
        sequence = _integer(row["sequence_index"], "sequence_index", minimum=1)
        due = _date(row["cohort_due_date"], "cohort_due_date")
        scheduled = _timestamp(row["scheduled_for"], "scheduled_for")
        status = row["execution_status"]
        if status not in {"COMPLETE", "INCOMPLETE"}:
            raise ContractError("contract_enum_invalid", "execution_status")
        if status == "INCOMPLETE":
            if (
                row["executed_at"] is not None
                or row["runs_created"] != 0
                or row["failure_receipt_id"] is None
                or row["evidence_state"] != "OWNER_REPORTED"
            ):
                raise ContractError("contract_value_invalid", "incomplete_history")
            failure_id = str(uuid_value(row["failure_receipt_id"], "failure_receipt_id"))
            executed = None
        else:
            executed = _timestamp(row["executed_at"], "executed_at")
            if row["failure_receipt_id"] is not None:
                raise ContractError("contract_value_invalid", "failure_receipt_id")
            failure_id = None
            if row["source_schema_version"] == "CohortHistoryReceipt/1.0.0":
                if executed[:10] != due or row["trigger_code"] != "DAY1_MANUAL":
                    raise ContractError("contract_date_mismatch", "historical_day1")
            else:
                start = _timestamp(row["window_start"], "window_start")
                end = _timestamp(row["window_end"], "window_end")
                if not start <= executed <= end or scheduled != start:
                    raise ContractError("contract_date_mismatch", "compressed_window")
        row.update(
            {
                "sequence_index": sequence,
                "cohort_due_date": due,
                "scheduled_for": scheduled,
                "executed_at": executed,
                "failure_receipt_id": failure_id,
                "runs_created": _integer(row["runs_created"], "runs_created"),
                "runs_predicted": _integer(row["runs_predicted"], "runs_predicted"),
            }
        )
        parsed.append(MappingProxyType(row))
    if [item["sequence_index"] for item in parsed] != list(range(1, len(parsed) + 1)):
        raise ContractError("contract_order_or_uniqueness_invalid", "sequence_index")
    if len(parsed) < 3 or not _legacy_prefix_is_exact(parsed[:2]):
        raise ContractError("contract_required_value_missing", "historical_failure")
    if sum(item["execution_status"] == "INCOMPLETE" for item in parsed) != 1:
        raise ContractError("contract_value_invalid", "historical_failure_count")
    _validate_compressed_history(parsed[2:])
    return tuple(parsed)


def _legacy_prefix_is_exact(rows: list[Mapping[str, object]]) -> bool:
    day1, failure = rows
    return (
        day1["source_schema_version"] == "CohortHistoryReceipt/1.0.0"
        and day1["cycle_id"] is None
        and day1["cycle_index"] is None
        and day1["cohort_due_date"] == "2026-08-25"
        and day1["scheduled_for"] == "2026-08-25T15:00:00Z"
        and day1["window_start"] is None
        and day1["window_end"] is None
        and day1["trigger_code"] == "DAY1_MANUAL"
        and day1["executed_at"] == "2026-08-25T15:00:03.280432Z"
        and day1["runs_created"] == 1
        and day1["runs_predicted"] == 1
        and day1["execution_status"] == "COMPLETE"
        and day1["failure_receipt_id"] is None
        and day1["evidence_state"] == "LIVE_INFRASTRUCTURE_SYNTHETIC_DATA"
        and day1["schedule_mode"] is None
        and failure["source_schema_version"]
        == "CompressedCycleFailureReceipt/1.0.0"
        and failure["cycle_id"] is None
        and failure["cycle_index"] is None
        and failure["cohort_due_date"] == "2026-08-26"
        and failure["scheduled_for"] == "2026-08-26T16:00:00Z"
        and failure["window_start"] is None
        and failure["window_end"] is None
        and failure["trigger_code"] == "COHORT_DAY_MANAGED"
        and failure["executed_at"] is None
        and failure["runs_created"] == 0
        and failure["runs_predicted"] == 3
        and failure["execution_status"] == "INCOMPLETE"
        and failure["failure_receipt_id"] is not None
        and failure["evidence_state"] == "OWNER_REPORTED"
        and failure["schedule_mode"] is None
    )


def _validate_compressed_history(rows: list[Mapping[str, object]]) -> None:
    expected_ids = [f"c{index}" for index in range(1, len(rows) + 1)]
    if [item["cycle_id"] for item in rows] != expected_ids:
        raise ContractError(
            "contract_order_or_uniqueness_invalid", "compressed_history"
        )
    for expected_index, row in enumerate(rows, start=1):
        if (
            row["cycle_index"] != expected_index
            or row["scheduled_for"] != row["window_start"]
            or row["runs_created"] != row["runs_predicted"]
            or row["source_schema_version"] != "CohortDayManifest/3.0.0"
            or row["trigger_code"] != _TRIGGER_CODE
            or row["execution_status"] != "COMPLETE"
            or row["failure_receipt_id"] is not None
            or row["evidence_state"]
            != "LIVE_INFRASTRUCTURE_SYNTHETIC_DATA"
            or row["schedule_mode"] != _SCHEDULE_MODE
        ):
            raise ContractError("contract_value_invalid", "compressed_history")


def _parse_cumulative(
    value: Any, history: tuple[Mapping[str, object], ...]
) -> Mapping[str, object]:
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
    parsed = {field: _integer(value[field], f"cumulative.{field}") for field in fields}
    compressed = [item for item in history if item["schedule_mode"] == _SCHEDULE_MODE]
    expected = {
        "compressed_cycles_completed": len(compressed),
        "successful_compressed_cycles": sum(
            item["runs_created"] == item["runs_predicted"] for item in compressed
        ),
        "runs_predicted": sum(int(item["runs_predicted"]) for item in compressed),
        "runs_created": sum(int(item["runs_created"]) for item in compressed),
        "distinct_execution_dates": len({str(item["executed_at"])[:10] for item in compressed}),
        "logical_days_covered": len({str(item["cohort_due_date"]) for item in compressed}),
        "historical_incomplete_attempts": sum(
            item["execution_status"] == "INCOMPLETE" for item in history
        ),
    }
    if parsed != expected:
        raise ContractError("contract_value_invalid", "cumulative")
    return MappingProxyType(parsed)


def _managed_start(value: Mapping[str, Any]) -> int:
    parsed = _integer(
        value["managed_history_starts_at_day_index"],
        "managed_history_starts_at_day_index",
        minimum=2,
    )
    if parsed != 2:
        raise ContractError("contract_value_invalid", "managed_history_starts_at_day_index")
    return parsed


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
