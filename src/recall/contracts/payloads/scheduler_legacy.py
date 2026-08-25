from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType
from typing import Any

from ..errors import ContractError
from ..validation import SHA256, non_empty_string, require_exact_fields, uuid_value


_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_MODES = frozenset({"SYNTHETIC_ONLY", "SYNTHETIC_WITH_CAPTURED_REPLAY"})


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ContractError("contract_type_invalid", field)
    return value


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
    if not isinstance(value, list):
        raise ContractError("contract_type_invalid", field)
    values = tuple(str(uuid_value(item, field)) for item in value)
    if values != tuple(sorted(set(values))):
        raise ContractError("contract_order_or_uniqueness_invalid", field)
    return values


@dataclass(frozen=True, slots=True)
class CohortDayManifestV20Payload:
    day_index: int
    selected_for_date: str
    scheduled_for: str
    source_commit: str
    image_digest: str
    trigger_code: str
    previous_manifest_id: str | None
    managed_history_starts_at_day_index: int
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
            "delta": delta,
            "cumulative": dict(self.cumulative),
            "cases": [dict(item) for item in self.cases],
            "vcv_anchors": [dict(item) for item in self.vcv_anchors],
            "execution_history": [dict(item) for item in self.execution_history],
        }


def parse_cohort_day_manifest_v20_payload(
    value: Mapping[str, Any],
) -> CohortDayManifestV20Payload:
    selected_for_date = _date(value["selected_for_date"], "selected_for_date")
    scheduled_for = _timestamp(value["scheduled_for"], "scheduled_for")
    if scheduled_for[:10] != selected_for_date:
        raise ContractError("contract_date_mismatch", "scheduled_for")
    source_commit = non_empty_string(value["source_commit"], "source_commit")
    if not _COMMIT.fullmatch(source_commit):
        raise ContractError("contract_hash_invalid", "source_commit")
    image_digest = non_empty_string(value["image_digest"], "image_digest")
    if not _IMAGE_DIGEST.fullmatch(image_digest):
        raise ContractError("contract_hash_invalid", "image_digest")
    previous = value["previous_manifest_id"]
    previous_manifest_id = (
        None
        if previous is None
        else str(uuid_value(previous, "previous_manifest_id"))
    )
    delta = _parse_delta(value["delta"])
    cumulative = _parse_cumulative(value["cumulative"])
    cases = _parse_cases(value["cases"])
    anchors = _parse_anchors(value["vcv_anchors"])
    history = _parse_history(value["execution_history"])
    day_index = _integer(value["day_index"], "day_index", minimum=1)
    if history[-1]["day_index"] != day_index:
        raise ContractError("contract_value_invalid", "execution_history.day_index")
    if history[-1]["selected_for_date"] != selected_for_date:
        raise ContractError("contract_date_mismatch", "execution_history")
    if history[-1]["runs_created"] != len(delta["authoritative_run_ids"]):
        raise ContractError("contract_value_invalid", "runs_created")
    if history[-1]["runs_predicted"] != delta["runs_predicted"]:
        raise ContractError("contract_value_invalid", "runs_predicted")
    if delta["prediction_match"] is not (
        history[-1]["runs_created"] == history[-1]["runs_predicted"]
    ):
        raise ContractError("contract_value_invalid", "prediction_match")
    if value["trigger_code"] != "COHORT_DAY_MANAGED":
        raise ContractError("contract_value_invalid", "trigger_code")
    managed_start = _integer(
        value["managed_history_starts_at_day_index"],
        "managed_history_starts_at_day_index",
        minimum=1,
    )
    if managed_start != 2:
        raise ContractError(
            "contract_value_invalid", "managed_history_starts_at_day_index"
        )
    if (day_index == 2) is not (previous_manifest_id is None):
        raise ContractError("contract_value_invalid", "previous_manifest_id")
    _validate_manifest_topology(value, delta, cumulative, cases, anchors, history)
    return CohortDayManifestV20Payload(
        day_index=day_index,
        selected_for_date=selected_for_date,
        scheduled_for=scheduled_for,
        source_commit=source_commit,
        image_digest=image_digest,
        trigger_code="COHORT_DAY_MANAGED",
        previous_manifest_id=previous_manifest_id,
        managed_history_starts_at_day_index=managed_start,
        delta=delta,
        cumulative=cumulative,
        cases=cases,
        vcv_anchors=anchors,
        execution_history=history,
    )


def _parse_delta(value: Any) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "delta")
    fields = frozenset(
        {
            "selected_case_ids",
            "excluded_case_ids",
            "newly_created_run_ids",
            "reused_run_ids",
            "authoritative_run_ids",
            "runs_predicted",
            "prediction_match",
        }
    )
    require_exact_fields(value, fields, "delta")
    parsed = {
        field: _uuid_list(value[field], f"delta.{field}")
        for field in fields
        if field.endswith("_ids")
    }
    parsed["runs_predicted"] = _integer(
        value["runs_predicted"], "delta.runs_predicted"
    )
    if not isinstance(value["prediction_match"], bool):
        raise ContractError("contract_type_invalid", "delta.prediction_match")
    parsed["prediction_match"] = value["prediction_match"]
    if set(parsed["newly_created_run_ids"]) & set(parsed["reused_run_ids"]):
        raise ContractError("contract_value_invalid", "delta.run_ids")
    if set(parsed["newly_created_run_ids"]) | set(parsed["reused_run_ids"]) != set(
        parsed["authoritative_run_ids"]
    ):
        raise ContractError("contract_value_invalid", "delta.authoritative_run_ids")
    return MappingProxyType(parsed)


def _parse_cumulative(value: Any) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "cumulative")
    fields = frozenset(
        {
            "daily_cycles",
            "successful_daily_cycles",
            "runs_predicted",
            "runs_created",
            "distinct_execution_dates",
        }
    )
    require_exact_fields(value, fields, "cumulative")
    return MappingProxyType(
        {field: _integer(value[field], f"cumulative.{field}") for field in fields}
    )


def _parse_cases(value: Any) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list):
        raise ContractError("contract_type_invalid", "cases")
    parsed = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ContractError("contract_type_invalid", f"cases[{index}]")
        require_exact_fields(item, frozenset({"case_id", "data_mode", "vcv"}), "cases")
        mode = item["data_mode"]
        if mode not in _MODES:
            raise ContractError("contract_enum_invalid", "cases.data_mode")
        vcv = item["vcv"]
        if vcv is not None and (not isinstance(vcv, str) or not vcv.startswith("VCV")):
            raise ContractError("contract_type_invalid", "cases.vcv")
        if (vcv is None) is not (mode == "SYNTHETIC_ONLY"):
            raise ContractError("data_mode_conflict", "cases.vcv")
        parsed.append(
            MappingProxyType(
                {
                    "case_id": str(uuid_value(item["case_id"], "cases.case_id")),
                    "data_mode": mode,
                    "vcv": vcv,
                }
            )
        )
    if [item["case_id"] for item in parsed] != sorted(
        {item["case_id"] for item in parsed}
    ):
        raise ContractError("contract_order_or_uniqueness_invalid", "cases")
    return tuple(parsed)


def _parse_anchors(value: Any) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list):
        raise ContractError("contract_type_invalid", "vcv_anchors")
    parsed = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ContractError("contract_type_invalid", "vcv_anchors")
        require_exact_fields(
            item,
            frozenset({"vcv", "capture_path", "sha256", "artifact_id"}),
            "vcv_anchors",
        )
        digest = item["sha256"]
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ContractError("contract_hash_invalid", "vcv_anchors.sha256")
        path = non_empty_string(item["capture_path"], "vcv_anchors.capture_path")
        if path.startswith(("/", "\\")) or ".." in path.replace("\\", "/").split("/"):
            raise ContractError("contract_path_invalid", "vcv_anchors.capture_path")
        parsed.append(
            MappingProxyType(
                {
                    "vcv": non_empty_string(item["vcv"], "vcv_anchors.vcv"),
                    "capture_path": path,
                    "sha256": digest,
                    "artifact_id": str(
                        uuid_value(item["artifact_id"], "vcv_anchors.artifact_id")
                    ),
                }
            )
        )
    if [item["vcv"] for item in parsed] != sorted({item["vcv"] for item in parsed}):
        raise ContractError("contract_order_or_uniqueness_invalid", "vcv_anchors")
    return tuple(parsed)


def _parse_history(value: Any) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or not value:
        raise ContractError("contract_type_invalid", "execution_history")
    parsed = []
    fields = frozenset(
        {"day_index", "executed_at", "selected_for_date", "runs_created", "runs_predicted"}
    )
    for item in value:
        if not isinstance(item, Mapping):
            raise ContractError("contract_type_invalid", "execution_history")
        require_exact_fields(item, fields, "execution_history")
        executed_at = _timestamp(item["executed_at"], "execution_history.executed_at")
        selected = _date(
            item["selected_for_date"], "execution_history.selected_for_date"
        )
        if executed_at[:10] != selected:
            raise ContractError("contract_date_mismatch", "execution_history")
        parsed.append(
            MappingProxyType(
                {
                    "day_index": _integer(item["day_index"], "execution_history.day_index", minimum=1),
                    "executed_at": executed_at,
                    "selected_for_date": selected,
                    "runs_created": _integer(item["runs_created"], "execution_history.runs_created"),
                    "runs_predicted": _integer(item["runs_predicted"], "execution_history.runs_predicted"),
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


def _validate_manifest_topology(
    value: Mapping[str, Any],
    delta: Mapping[str, object],
    cumulative: Mapping[str, object],
    cases: tuple[Mapping[str, object], ...],
    anchors: tuple[Mapping[str, object], ...],
    history: tuple[Mapping[str, object], ...],
) -> None:
    selected = set(delta["selected_case_ids"])
    excluded = set(delta["excluded_case_ids"])
    if selected & excluded or len(selected | excluded) != 12:
        raise ContractError("contract_value_invalid", "delta.case_partition")
    if {item["case_id"] for item in cases} != selected:
        raise ContractError("contract_value_invalid", "cases")
    replay_vcvs = {item["vcv"] for item in cases if item["vcv"] is not None}
    if {item["vcv"] for item in anchors} != replay_vcvs:
        raise ContractError("contract_value_invalid", "vcv_anchors")
    input_ids = set(value["input_artifact_ids"])
    if not {item["artifact_id"] for item in anchors}.issubset(input_ids):
        raise ContractError("contract_value_invalid", "vcv_anchors.artifact_id")
    expected_cumulative = {
        "daily_cycles": len(history),
        "successful_daily_cycles": sum(
            int(item["runs_created"] == item["runs_predicted"]) for item in history
        ),
        "runs_predicted": sum(int(item["runs_predicted"]) for item in history),
        "runs_created": sum(int(item["runs_created"]) for item in history),
        "distinct_execution_dates": len(
            {str(item["selected_for_date"]) for item in history}
        ),
    }
    if dict(cumulative) != expected_cumulative:
        raise ContractError("contract_value_invalid", "cumulative")
    expected_status = "VALID" if delta["prediction_match"] else "INCOMPLETE"
    if value["status"] != expected_status:
        raise ContractError("contract_value_invalid", "status")
