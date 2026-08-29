from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import MappingProxyType
from typing import Any

from ..errors import ContractError
from ..validation import SHA256, non_empty_string, require_exact_fields, uuid_value
from .scheduler import _parse_anchors, _parse_cases, _parse_delta
from .scheduler_v31 import _parse_metrics
from .scheduler_v32 import (
    _parse_outcomes,
    _parse_summary,
    _validate_outcome_binding,
)
from .scheduler_v34_support import (
    parse_v34_cumulative,
    parse_v34_deadline,
    parse_v34_history,
    parse_v34_parity,
)


_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SCHEDULE_MODE = "COMPRESSED_MACHINE_TRIGGERED"
_TRIGGER_CODE = "COHORT_COMPRESSED_MACHINE_TRIGGERED"
_SUPERSEDED_PLAN_SHA256 = (
    "c3e454c1b593c98a558c3f03c67b7de6f5d0e2d1e3c98efdfb91d4c5530a9791"
)
_SUPERSESSION_FIELDS = frozenset(
    {
        "mode",
        "superseded_plan_sha256",
        "owner_decision",
        "reason_code",
        "historical_evidence",
        "retired_cycles",
        "verified_artifact_ids",
    }
)
_HISTORICAL_FIELDS = frozenset(
    {
        "cycle_id",
        "evidence_role",
        "execution_status",
        "plan_sha256",
        "collection_prefix",
        "manifest_artifact_id",
        "manifest_content_hash",
        "mode_receipt_artifact_id",
        "mode_receipt_content_hash",
    }
)
_RETIRED_FIELDS = frozenset(
    {"cycle_id", "state", "execution_status", "runs_created"}
)


@dataclass(frozen=True, slots=True)
class CohortDayManifestV34Payload:
    fields: Mapping[str, object]

    def __getattr__(self, name: str) -> object:
        try:
            return self.fields[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def to_wire(self) -> dict[str, object]:
        return _mutable(self.fields)


def parse_cohort_day_manifest_v34_payload(
    value: Mapping[str, Any],
) -> CohortDayManifestV34Payload:
    cycle_id = non_empty_string(value["cycle_id"], "cycle_id")
    cycle_index = _integer(value["cycle_index"], "cycle_index", minimum=1)
    due = _date(value["cohort_due_date"], "cohort_due_date")
    window_start = _timestamp(value["window_start"], "window_start")
    window_end = _timestamp(value["window_end"], "window_end")
    scheduled_for = _timestamp(value["scheduled_for"], "scheduled_for")
    if (
        cycle_id != "c6"
        or cycle_index != 6
        or value["day_index"] != 7
        or value["selected_for_date"] != due
        or scheduled_for != window_start
        or _datetime(window_end) <= _datetime(window_start)
        or value["plan_version"] != "COMPRESSED_PREDICTION_PLAN_V2"
        or value["schedule_mode"] != _SCHEDULE_MODE
        or value["trigger_code"] != _TRIGGER_CODE
        or value["previous_manifest_id"] is not None
        or value["ramp_gate_receipt_id"] is not None
        or value["headroom_receipt_id"] is not None
        or value["evaluation_role"] != "PORTFOLIO_REASSESSMENT"
        or value["epoch_label"] != "PLAN6_FINAL_456_REASSESSMENT_ACTIVE"
        or _datetime(window_end) - _datetime(window_start)
        != timedelta(hours=7, minutes=43, seconds=59)
    ):
        raise ContractError("contract_value_invalid", "final_only_declaration")
    source_commit = non_empty_string(value["source_commit"], "source_commit")
    image_digest = non_empty_string(value["image_digest"], "image_digest")
    plan_sha = non_empty_string(value["plan_sha256"], "plan_sha256")
    if not _COMMIT.fullmatch(source_commit):
        raise ContractError("contract_hash_invalid", "source_commit")
    if not _IMAGE_DIGEST.fullmatch(image_digest):
        raise ContractError("contract_hash_invalid", "image_digest")
    if not SHA256.fullmatch(plan_sha):
        raise ContractError("contract_hash_invalid", "plan_sha256")

    delta = _parse_delta(value["delta"])
    cases = _parse_cases(value["cases"])
    anchors = _parse_anchors(value["vcv_anchors"])
    if (
        set(delta["selected_case_ids"]) & set(delta["excluded_case_ids"])
        or len(set(delta["selected_case_ids"]) | set(delta["excluded_case_ids"]))
        != 462
        or {item["case_id"] for item in cases}
        != set(delta["selected_case_ids"])
        or {item["vcv"] for item in cases if item["vcv"] is not None}
        != {item["vcv"] for item in anchors}
    ):
        raise ContractError("contract_value_invalid", "final_only_case_binding")

    metrics = _parse_metrics(value["write_metrics"])
    parity = parse_v34_parity(value["parity"], value)
    summary = _parse_summary(value["agent_execution_summary"])
    outcomes = _parse_outcomes(value["run_outcomes"], str(value["epoch_label"]))
    _validate_outcome_binding(value, summary, outcomes)
    deadline = parse_v34_deadline(value)
    if (
        deadline["execution_timeout_seconds"],
        deadline["write_timeout_seconds"],
        deadline["agent_timeout_seconds"],
    ) != (28_800, 1_800, 27_000):
        raise ContractError(
            "contract_value_invalid", "deadline_policy.phase_binding"
        )
    supersession = _parse_supersession(value["final_only_supersession"])
    history = parse_v34_history(value["execution_history"], value)
    cumulative = parse_v34_cumulative(
        value["cumulative"], history, supersession
    )

    batch_id = str(
        uuid_value(value["batch_execution_receipt_id"], "batch_execution_receipt_id")
    )
    attempt_id = str(uuid_value(value["cycle_attempt_id"], "cycle_attempt_id"))
    if (
        batch_id not in value["input_artifact_ids"]
        or value["write_measurement_status"] not in {"MEASURED", "NOT_EVALUATED"}
    ):
        raise ContractError("contract_value_invalid", "final_only_write_binding")
    required_inputs = {
        item["artifact_id"] for item in anchors
    } | set(supersession["verified_artifact_ids"])
    if not required_inputs.issubset(set(value["input_artifact_ids"])):
        raise ContractError("contract_value_invalid", "final_only_inputs")

    agent_qualified = (
        summary["halted_runs"] == 0
        and summary["incomplete_runs"] == 0
        and summary["not_evaluated_runs"] == 0
        and summary["complete_runs"] == summary["total_runs"]
    )
    deadline_qualified = (
        deadline["write_completed_at"] <= deadline["write_deadline"]
        and deadline["agent_completed_at"] <= deadline["agent_deadline"]
        and deadline["agent_completed_at"]
        <= deadline["authoritative_end_to_end_deadline"]
    )
    qualifies = (
        parity["parity_match"]
        and value["write_measurement_status"] == "MEASURED"
        and metrics["persistence_surface"] == "LIVE_FIRESTORE"
        and metrics["effective_write_millis_per_case"] <= 2000
        and agent_qualified
        and deadline_qualified
    )
    if value["status"] != ("VALID" if qualifies else "INCOMPLETE"):
        raise ContractError("contract_value_invalid", "v34_qualification_status")

    fields = dict(value)
    fields.update(
        {
            "day_index": 7,
            "cycle_index": 6,
            "source_commit": source_commit,
            "image_digest": image_digest,
            "plan_sha256": plan_sha,
            "delta": delta,
            "cases": cases,
            "vcv_anchors": anchors,
            "write_metrics": metrics,
            "parity": parity,
            "agent_execution_summary": summary,
            "run_outcomes": outcomes,
            "deadline_policy": deadline,
            "final_only_supersession": supersession,
            "execution_history": history,
            "cumulative": cumulative,
            "batch_execution_receipt_id": batch_id,
            "cycle_attempt_id": attempt_id,
        }
    )
    return CohortDayManifestV34Payload(MappingProxyType(fields))


def _parse_supersession(value: Any) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "final_only_supersession")
    require_exact_fields(value, _SUPERSESSION_FIELDS, "final_only_supersession")
    if (
        value["mode"] != "FINAL_ONLY_TIMEBOX"
        or value["superseded_plan_sha256"] != _SUPERSEDED_PLAN_SHA256
        or value["owner_decision"]
        != "RETIRE_RAMP_DUE_TIMEBOX_AND_AUTHORIZE_FINAL_456"
        or value["reason_code"] != "RAMP_TIMEBOX_EXHAUSTED"
    ):
        raise ContractError("contract_value_invalid", "final_only_supersession")
    raw_evidence = value["historical_evidence"]
    raw_retired = value["retired_cycles"]
    raw_verified = value["verified_artifact_ids"]
    if (
        not isinstance(raw_evidence, list)
        or not isinstance(raw_retired, list)
        or not isinstance(raw_verified, list)
    ):
        raise ContractError("contract_type_invalid", "final_only_supersession")
    evidence = tuple(_parse_historical(item) for item in raw_evidence)
    retired = tuple(_parse_retired(item) for item in raw_retired)
    verified = tuple(str(uuid_value(item, "verified_artifact_ids")) for item in raw_verified)
    expected_verified = tuple(
        artifact_id
        for item in evidence
        for artifact_id in (
            item["manifest_artifact_id"],
            item["mode_receipt_artifact_id"],
        )
        if artifact_id is not None
    )
    if (
        [(item["cycle_id"], item["evidence_role"], item["execution_status"]) for item in evidence[:2]]
        != [
            ("c1", "IMMUTABLE_EXECUTED", "COMPLETE"),
            ("c2", "IMMUTABLE_EXECUTED", "COMPLETE"),
        ]
        or len(evidence) < 3
        or any(
            item["cycle_id"] != "c3"
            or item["evidence_role"] != "HISTORICAL_ATTEMPT"
            or item["execution_status"] != "INCOMPLETE"
            for item in evidence[2:]
        )
        or [(item["cycle_id"], item["state"], item["execution_status"], item["runs_created"]) for item in retired]
        != [
            ("c4", "RETIRED_TIMEBOX", "NOT_EXECUTED", 0),
            ("c5", "RETIRED_TIMEBOX", "NOT_EXECUTED", 0),
        ]
        or verified != expected_verified
    ):
        raise ContractError("contract_value_invalid", "final_only_supersession")
    return MappingProxyType(
        {
            **dict(value),
            "historical_evidence": evidence,
            "retired_cycles": retired,
            "verified_artifact_ids": verified,
        }
    )


def _parse_historical(value: Any) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "historical_evidence")
    require_exact_fields(value, _HISTORICAL_FIELDS, "historical_evidence")
    mode_id = value["mode_receipt_artifact_id"]
    mode_hash = value["mode_receipt_content_hash"]
    if (
        not SHA256.fullmatch(str(value["plan_sha256"]))
        or not SHA256.fullmatch(str(value["manifest_content_hash"]))
        or (mode_id is None) is not (mode_hash is None)
        or (mode_hash is not None and not SHA256.fullmatch(str(mode_hash)))
    ):
        raise ContractError("contract_hash_invalid", "historical_evidence")
    parsed = dict(value)
    parsed["manifest_artifact_id"] = str(
        uuid_value(value["manifest_artifact_id"], "manifest_artifact_id")
    )
    parsed["mode_receipt_artifact_id"] = (
        None if mode_id is None else str(uuid_value(mode_id, "mode_receipt_artifact_id"))
    )
    return MappingProxyType(parsed)


def _parse_retired(value: Any) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "retired_cycles")
    require_exact_fields(value, _RETIRED_FIELDS, "retired_cycles")
    if isinstance(value["runs_created"], bool) or value["runs_created"] != 0:
        raise ContractError("contract_value_invalid", "retired_cycles")
    return MappingProxyType(dict(value))


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
    _datetime(value)
    return value


def _datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("contract_timestamp_invalid", "timestamp") from exc


def _mutable(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _mutable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_mutable(item) for item in value]
    return value
