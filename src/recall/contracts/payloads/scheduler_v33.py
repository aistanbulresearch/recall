from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any

from ..errors import ContractError
from ..validation import require_exact_fields, uuid_value
from .scheduler_v32 import (
    CohortDayManifestV32Payload,
    parse_cohort_day_manifest_v32_payload,
)


_DEADLINE_FIELDS = frozenset(
    {
        "trigger_started_at",
        "trigger_window_end",
        "write_timeout_seconds",
        "write_deadline",
        "write_completed_at",
        "agent_timeout_seconds",
        "agent_deadline",
        "agent_completed_at",
        "execution_timeout_seconds",
        "authoritative_end_to_end_deadline",
    }
)

_APPROVED_PHASE_BUDGETS = MappingProxyType(
    {
        (
            "COMPRESSED_PREDICTION_PLAN_V2",
            "fe3a1d5650daf27fd72b31030d5f7e26cf75b7ffd6cb1f7220c5c86f4c869b61",
            "c3",
        ): (3600, 600, 3000),
        (
            "COMPRESSED_PREDICTION_PLAN_V2",
            "fe3a1d5650daf27fd72b31030d5f7e26cf75b7ffd6cb1f7220c5c86f4c869b61",
            "c4",
        ): (7200, 1200, 6000),
        (
            "COMPRESSED_PREDICTION_PLAN_V2",
            "fe3a1d5650daf27fd72b31030d5f7e26cf75b7ffd6cb1f7220c5c86f4c869b61",
            "c5",
        ): (14400, 1800, 12600),
        (
            "COMPRESSED_PREDICTION_PLAN_V2",
            "fe3a1d5650daf27fd72b31030d5f7e26cf75b7ffd6cb1f7220c5c86f4c869b61",
            "c6",
        ): (32400, 1800, 30600),
        (
            "COMPRESSED_PREDICTION_PLAN_V2",
            "52d5f3d8651987474870dc1d2fead318ea3520a91fb54b0f41d7772ae90b7338",
            "c3",
        ): (3600, 600, 3000),
        (
            "COMPRESSED_PREDICTION_PLAN_V2",
            "52d5f3d8651987474870dc1d2fead318ea3520a91fb54b0f41d7772ae90b7338",
            "c4",
        ): (7200, 1200, 6000),
        (
            "COMPRESSED_PREDICTION_PLAN_V2",
            "52d5f3d8651987474870dc1d2fead318ea3520a91fb54b0f41d7772ae90b7338",
            "c5",
        ): (14400, 1800, 12600),
        (
            "COMPRESSED_PREDICTION_PLAN_V2",
            "52d5f3d8651987474870dc1d2fead318ea3520a91fb54b0f41d7772ae90b7338",
            "c6",
        ): (32400, 1800, 30600),
    }
)


@dataclass(frozen=True, slots=True)
class CohortDayManifestV33Payload:
    base: CohortDayManifestV32Payload
    cycle_attempt_id: str
    batch_execution_receipt_id: str
    write_measurement_status: str
    deadline_policy: Mapping[str, object]
    parity: Mapping[str, object]
    execution_history: tuple[Mapping[str, object], ...]

    def __getattr__(self, name: str) -> object:
        return getattr(self.base, name)

    def to_wire(self) -> dict[str, object]:
        value = self.base.to_wire()
        value.update(
            {
                "cycle_attempt_id": self.cycle_attempt_id,
                "batch_execution_receipt_id": self.batch_execution_receipt_id,
                "write_measurement_status": self.write_measurement_status,
                "deadline_policy": dict(self.deadline_policy),
                "parity": dict(self.parity),
                "execution_history": [
                    dict(item) for item in self.execution_history
                ],
            }
        )
        return value


def parse_cohort_day_manifest_v33_payload(
    value: Mapping[str, Any],
) -> CohortDayManifestV33Payload:
    attempt_id = str(uuid_value(value["cycle_attempt_id"], "cycle_attempt_id"))
    batch_id = str(
        uuid_value(
            value["batch_execution_receipt_id"],
            "batch_execution_receipt_id",
        )
    )
    if batch_id not in value["input_artifact_ids"]:
        raise ContractError("contract_value_invalid", "batch_execution_receipt_id")
    measurement = value["write_measurement_status"]
    if measurement not in {"MEASURED", "NOT_EVALUATED"}:
        raise ContractError("contract_enum_invalid", "write_measurement_status")
    deadline = _parse_deadline(value)
    parity = value["parity"]
    if not isinstance(parity, Mapping):
        raise ContractError("contract_type_invalid", "parity")
    expected_parity_fields = {
        "expected_newly_created_runs",
        "actual_newly_created_runs",
        "expected_reused_runs",
        "actual_reused_runs",
        "new_epoch_required",
        "same_write_path_as_ramp",
        "parity_match",
        "epoch_parity_match",
        "fresh_write_parity_match",
    }
    require_exact_fields(parity, frozenset(expected_parity_fields), "parity")
    authoritative = value["delta"]["authoritative_run_ids"]
    epoch_match = len(authoritative) == value["delta"]["runs_predicted"]
    fresh_match = (
        len(value["delta"]["newly_created_run_ids"])
        == value["delta"]["runs_predicted"]
        and not value["delta"]["reused_run_ids"]
    )
    if (
        parity["epoch_parity_match"] is not epoch_match
        or parity["fresh_write_parity_match"] is not fresh_match
        or parity["parity_match"] is not fresh_match
    ):
        raise ContractError("contract_value_invalid", "parity")

    legacy = dict(value)
    for field in (
        "cycle_attempt_id",
        "batch_execution_receipt_id",
        "write_measurement_status",
        "deadline_policy",
    ):
        legacy.pop(field)
    legacy["schema_version"] = "3.2.0"
    legacy["parity"] = {
        key: parity[key]
        for key in expected_parity_fields
        if key not in {"epoch_parity_match", "fresh_write_parity_match"}
    }
    history = [dict(item) for item in value["execution_history"]]
    if history[-1]["source_schema_version"] != "CohortDayManifest/3.3.0":
        raise ContractError("contract_value_invalid", "execution_history.current")
    for row in history:
        if row["source_schema_version"] == "CohortDayManifest/3.3.0":
            row["source_schema_version"] = "CohortDayManifest/3.2.0"
    legacy["execution_history"] = history
    legacy["status"] = _legacy_v32_status(legacy)
    base = parse_cohort_day_manifest_v32_payload(legacy)

    agent = value["agent_execution_summary"]
    agent_qualified = (
        agent["halted_runs"] == 0
        and agent["incomplete_runs"] == 0
        and agent["not_evaluated_runs"] == 0
        and agent["complete_runs"] == agent["total_runs"]
    )
    deadline_qualified = (
        deadline["write_completed_at"] <= deadline["write_deadline"]
        and deadline["agent_completed_at"] <= deadline["agent_deadline"]
        and deadline["agent_completed_at"]
        <= deadline["authoritative_end_to_end_deadline"]
    )
    metrics = value["write_metrics"]
    expected_status = (
        "VALID"
        if (
            epoch_match
            and measurement == "MEASURED"
            and metrics["persistence_surface"] == "LIVE_FIRESTORE"
            and metrics["effective_write_millis_per_case"] <= 2000
            and agent_qualified
            and deadline_qualified
        )
        else "INCOMPLETE"
    )
    if value["status"] != expected_status:
        raise ContractError("contract_value_invalid", "v33_qualification_status")
    return CohortDayManifestV33Payload(
        base,
        attempt_id,
        batch_id,
        measurement,
        MappingProxyType(deadline),
        MappingProxyType(dict(parity)),
        tuple(MappingProxyType(dict(item)) for item in value["execution_history"]),
    )


def _parse_deadline(value: Mapping[str, Any]) -> dict[str, object]:
    raw = value["deadline_policy"]
    if not isinstance(raw, Mapping):
        raise ContractError("contract_type_invalid", "deadline_policy")
    require_exact_fields(raw, _DEADLINE_FIELDS, "deadline_policy")
    parsed = dict(raw)
    for field in _DEADLINE_FIELDS - {
        "write_timeout_seconds",
        "agent_timeout_seconds",
        "execution_timeout_seconds",
    }:
        parsed[field] = _timestamp(raw[field], field)
    for field in (
        "write_timeout_seconds",
        "agent_timeout_seconds",
        "execution_timeout_seconds",
    ):
        parsed[field] = _integer(raw[field], field)
    binding = (
        value["plan_version"],
        value["plan_sha256"],
        value["cycle_id"],
    )
    observed_budget = (
        parsed["execution_timeout_seconds"],
        parsed["write_timeout_seconds"],
        parsed["agent_timeout_seconds"],
    )
    if _APPROVED_PHASE_BUDGETS.get(binding) != observed_budget:
        raise ContractError(
            "contract_value_invalid", "deadline_policy.plan_binding"
        )
    start = _datetime(value["window_start"])
    window_end = _datetime(value["window_end"])
    trigger = _datetime(parsed["trigger_started_at"])
    write_completed = _datetime(parsed["write_completed_at"])
    e2e = start + timedelta(seconds=int(parsed["execution_timeout_seconds"]))
    expected_write = min(
        trigger + timedelta(seconds=int(parsed["write_timeout_seconds"])), e2e
    )
    expected_agent = min(
        write_completed + timedelta(seconds=int(parsed["agent_timeout_seconds"])),
        e2e,
    )
    agent_completed = _datetime(parsed["agent_completed_at"])
    require_deadline_completion_binding(value["created_at"], parsed)
    if (
        not start <= trigger <= window_end
        or not trigger <= write_completed <= agent_completed
        or parsed["trigger_window_end"] != value["window_end"]
        or _datetime(parsed["write_deadline"]) != expected_write
        or _datetime(parsed["agent_deadline"]) != expected_agent
        or _datetime(parsed["authoritative_end_to_end_deadline"]) != e2e
    ):
        raise ContractError("contract_value_invalid", "deadline_policy")
    return parsed


def require_deadline_completion_binding(
    created_at: object,
    deadline_policy: Mapping[str, object],
) -> None:
    """Require the artifact timestamp to name the observed agent completion."""

    if created_at != deadline_policy.get("agent_completed_at"):
        raise ContractError("contract_value_invalid", "deadline_policy")


def _legacy_v32_status(value: Mapping[str, Any]) -> str:
    metrics = value["write_metrics"]
    parity = value["parity"]
    agent = value["agent_execution_summary"]
    qualified = (
        parity["parity_match"]
        and metrics["persistence_surface"] == "LIVE_FIRESTORE"
        and metrics["effective_write_millis_per_case"] <= 2000
        and len(value["delta"]["authoritative_run_ids"])
        == value["delta"]["runs_predicted"]
        and agent["halted_runs"] == 0
        and agent["incomplete_runs"] == 0
        and agent["not_evaluated_runs"] == 0
        and agent["complete_runs"] == agent["total_runs"]
    )
    return "VALID" if qualified else "INCOMPLETE"


def _timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ContractError("contract_timestamp_invalid", field)
    _datetime(value)
    return value


def _datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("contract_timestamp_invalid", "deadline_policy") from exc


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractError("contract_type_invalid", field)
    return value
