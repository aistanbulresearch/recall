from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

from ..enums import (
    ReviewTaskState,
    ScanRunEventCode,
    ScanRunState,
    WatchCaseState,
)
from ..errors import ContractError
from ..validation import (
    SHA256,
    enum_value,
    require_exact_fields,
    tuple_of_strings,
    uuid_value,
)


_BUDGET_FIELDS = frozenset(
    {
        "delegation_depth",
        "specialist_invocations",
        "model_calls_per_role",
        "schema_repairs",
        "agent_retries",
        "connector_retries",
        "repeated_state_limit",
        "wall_time_seconds",
        "step_deadlines",
        "token_ceilings",
    }
)


def _timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ContractError("contract_timestamp_invalid", field)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("contract_timestamp_invalid", field) from exc
    return value


def _non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractError("contract_type_invalid", field)
    return value


def _budget(value: Any) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "budget_snapshot")
    require_exact_fields(value, _BUDGET_FIELDS, "budget_snapshot")
    parsed: dict[str, object] = {}
    for field in _BUDGET_FIELDS - {"step_deadlines", "token_ceilings"}:
        parsed[field] = _non_negative_int(value[field], f"budget_snapshot.{field}")
    for field in ("step_deadlines", "token_ceilings"):
        raw = value[field]
        if not isinstance(raw, Mapping):
            raise ContractError("contract_type_invalid", f"budget_snapshot.{field}")
        if any(
            not isinstance(key, str)
            or not key
            or isinstance(item, bool)
            or not isinstance(item, int)
            or item < 0
            for key, item in raw.items()
        ):
            raise ContractError("contract_type_invalid", f"budget_snapshot.{field}")
        parsed[field] = dict(sorted(raw.items()))
    return MappingProxyType(parsed)


@dataclass(frozen=True, slots=True)
class ScanRunPayload:
    watch_case_id: str
    state: ScanRunState
    scheduled_for: str
    attempt: int
    lease_epoch: int
    deadline_at: str
    budget_snapshot: Mapping[str, object]
    idempotency_key: str
    trace_id: str
    terminal_policy_decision_id: str | None
    failure_receipt_ids: tuple[str, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "watch_case_id": self.watch_case_id,
            "state": self.state.value,
            "scheduled_for": self.scheduled_for,
            "attempt": self.attempt,
            "lease_epoch": self.lease_epoch,
            "deadline_at": self.deadline_at,
            "budget_snapshot": dict(self.budget_snapshot),
            "idempotency_key": self.idempotency_key,
            "trace_id": self.trace_id,
            "terminal_policy_decision_id": self.terminal_policy_decision_id,
            "failure_receipt_ids": list(self.failure_receipt_ids),
        }


def parse_scan_run_payload(value: Mapping[str, Any]) -> ScanRunPayload:
    state = enum_value(ScanRunState, value["state"], "state")
    if state is not ScanRunState.CREATED:
        raise ContractError("contract_value_invalid", "ScanRun.state")
    attempt = _non_negative_int(value["attempt"], "attempt")
    lease_epoch = _non_negative_int(value["lease_epoch"], "lease_epoch")
    if attempt != 0 or lease_epoch != 0:
        raise ContractError("contract_value_invalid", "ScanRun.creation_counters")
    idempotency_key = value["idempotency_key"]
    if not isinstance(idempotency_key, str) or not SHA256.fullmatch(idempotency_key):
        raise ContractError("contract_hash_invalid", "idempotency_key")
    failures = tuple_of_strings(value["failure_receipt_ids"], "failure_receipt_ids")
    for artifact_id in failures:
        uuid_value(artifact_id, "failure_receipt_ids")
    terminal_id = uuid_value(
        value["terminal_policy_decision_id"],
        "terminal_policy_decision_id",
        nullable=True,
    )
    if terminal_id is not None or failures:
        raise ContractError("contract_value_invalid", "ScanRun.creation_terminal_fields")
    return ScanRunPayload(
        watch_case_id=str(uuid_value(value["watch_case_id"], "watch_case_id")),
        state=state,
        scheduled_for=_timestamp(value["scheduled_for"], "scheduled_for"),
        attempt=attempt,
        lease_epoch=lease_epoch,
        deadline_at=_timestamp(value["deadline_at"], "deadline_at"),
        budget_snapshot=_budget(value["budget_snapshot"]),
        idempotency_key=idempotency_key,
        trace_id=str(uuid_value(value["trace_id"], "trace_id")),
        terminal_policy_decision_id=terminal_id,
        failure_receipt_ids=failures,
    )


@dataclass(frozen=True, slots=True)
class ReviewTaskPayload:
    watch_case_id: str
    trigger_decision_id: str
    state: ReviewTaskState
    priority_band: str
    claim_ids: tuple[str, ...]
    audit_receipt_id: str
    simulation: bool
    deduplication_key: str

    def to_wire(self) -> dict[str, object]:
        return {
            "watch_case_id": self.watch_case_id,
            "trigger_decision_id": self.trigger_decision_id,
            "state": self.state.value,
            "priority_band": self.priority_band,
            "claim_ids": list(self.claim_ids),
            "audit_receipt_id": self.audit_receipt_id,
            "simulation": self.simulation,
            "deduplication_key": self.deduplication_key,
        }


def parse_review_task_payload(value: Mapping[str, Any]) -> ReviewTaskPayload:
    state = enum_value(ReviewTaskState, value["state"], "state")
    if state is not ReviewTaskState.OPEN:
        raise ContractError("contract_value_invalid", "ReviewTask.creation_state")
    priority = value["priority_band"]
    if not isinstance(priority, str) or not priority:
        raise ContractError("contract_type_invalid", "priority_band")
    claims = tuple_of_strings(value["claim_ids"], "claim_ids")
    if not claims:
        raise ContractError("contract_required_value_missing", "claim_ids")
    simulation = value["simulation"]
    if simulation is not True:
        raise ContractError("contract_value_invalid", "simulation")
    deduplication_key = value["deduplication_key"]
    if not isinstance(deduplication_key, str) or not SHA256.fullmatch(
        deduplication_key
    ):
        raise ContractError("contract_hash_invalid", "deduplication_key")
    return ReviewTaskPayload(
        watch_case_id=str(uuid_value(value["watch_case_id"], "watch_case_id")),
        trigger_decision_id=str(
            uuid_value(value["trigger_decision_id"], "trigger_decision_id")
        ),
        state=state,
        priority_band=priority,
        claim_ids=claims,
        audit_receipt_id=str(
            uuid_value(value["audit_receipt_id"], "audit_receipt_id")
        ),
        simulation=True,
        deduplication_key=deduplication_key,
    )


@dataclass(frozen=True, slots=True)
class ScanRunEventPayload:
    event_id: str
    sequence: int
    from_state: ScanRunState | None
    to_state: ScanRunState
    event_code: ScanRunEventCode
    agent_id: None
    lease_epoch: int

    def to_wire(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "sequence": self.sequence,
            "from_state": None if self.from_state is None else self.from_state.value,
            "to_state": self.to_state.value,
            "event_code": self.event_code.value,
            "agent_id": None,
            "lease_epoch": self.lease_epoch,
        }


def parse_scan_run_event_payload(
    value: Mapping[str, Any],
) -> ScanRunEventPayload:
    if value["agent_id"] is not None:
        raise ContractError("producer_not_authorized", "ScanRunEvent.agent_id")
    sequence = _non_negative_int(value["sequence"], "sequence")
    if sequence < 1:
        raise ContractError("contract_value_invalid", "sequence")
    raw_from = value["from_state"]
    return ScanRunEventPayload(
        event_id=str(uuid_value(value["event_id"], "event_id")),
        sequence=sequence,
        from_state=(
            None
            if raw_from is None
            else enum_value(ScanRunState, raw_from, "from_state")
        ),
        to_state=enum_value(ScanRunState, value["to_state"], "to_state"),
        event_code=enum_value(
            ScanRunEventCode, value["event_code"], "event_code"
        ),
        agent_id=None,
        lease_epoch=_non_negative_int(value["lease_epoch"], "lease_epoch"),
    )


@dataclass(frozen=True, slots=True)
class WatchCasePayload:
    tenant_id: str
    region: str
    state: WatchCaseState
    monitoring_started_at: str
    monitoring_policy: Mapping[str, object]
    next_scan_at: str | None
    source_cursors: Mapping[str, str]
    last_verified_snapshot_id: str | None
    last_verified_scan: Mapping[str, object]
    pending_observation_hashes: tuple[str, ...]
    attention_marker: Mapping[str, object] | None
    open_review_task_id: str | None
    retention_policy: Mapping[str, object]

    def to_wire(self) -> dict[str, object]:
        return {
            "tenant_id": self.tenant_id,
            "region": self.region,
            "state": self.state.value,
            "monitoring_started_at": self.monitoring_started_at,
            "monitoring_policy": dict(self.monitoring_policy),
            "next_scan_at": self.next_scan_at,
            "source_cursors": dict(self.source_cursors),
            "last_verified_snapshot_id": self.last_verified_snapshot_id,
            "last_verified_scan": dict(self.last_verified_scan),
            "pending_observation_hashes": list(self.pending_observation_hashes),
            "attention_marker": (
                None if self.attention_marker is None else dict(self.attention_marker)
            ),
            "open_review_task_id": self.open_review_task_id,
            "retention_policy": dict(self.retention_policy),
        }


def parse_watch_case_payload(value: Mapping[str, Any]) -> WatchCasePayload:
    policy = value["monitoring_policy"]
    retention = value["retention_policy"]
    cursors = value["source_cursors"]
    last_scan = value["last_verified_scan"]
    if not all(isinstance(item, Mapping) for item in (policy, retention, cursors, last_scan)):
        raise ContractError("contract_type_invalid", "WatchCase.mapping")
    require_exact_fields(last_scan, frozenset({"run_id", "completed_at"}), "last_verified_scan")
    last_run = uuid_value(last_scan["run_id"], "last_verified_scan.run_id", nullable=True)
    last_completed = last_scan["completed_at"]
    if (last_run is None) is not (last_completed is None):
        raise ContractError("contract_value_invalid", "last_verified_scan")
    if last_completed is not None:
        _timestamp(last_completed, "last_verified_scan.completed_at")
    if any(not isinstance(key, str) or not isinstance(item, str) for key, item in cursors.items()):
        raise ContractError("contract_type_invalid", "source_cursors")
    pending = tuple_of_strings(
        value["pending_observation_hashes"], "pending_observation_hashes"
    )
    if any(not SHA256.fullmatch(item) for item in pending):
        raise ContractError("contract_hash_invalid", "pending_observation_hashes")
    next_scan = value["next_scan_at"]
    if next_scan is not None:
        _timestamp(next_scan, "next_scan_at")
    attention = value["attention_marker"]
    if attention is not None and not isinstance(attention, Mapping):
        raise ContractError("contract_type_invalid", "attention_marker")
    return WatchCasePayload(
        tenant_id=str(value["tenant_id"]),
        region=str(value["region"]),
        state=enum_value(WatchCaseState, value["state"], "state"),
        monitoring_started_at=_timestamp(
            value["monitoring_started_at"], "monitoring_started_at"
        ),
        monitoring_policy=MappingProxyType(dict(policy)),
        next_scan_at=next_scan,
        source_cursors=MappingProxyType(dict(sorted(cursors.items()))),
        last_verified_snapshot_id=uuid_value(
            value["last_verified_snapshot_id"],
            "last_verified_snapshot_id",
            nullable=True,
        ),
        last_verified_scan=MappingProxyType(dict(last_scan)),
        pending_observation_hashes=pending,
        attention_marker=(
            None if attention is None else MappingProxyType(dict(attention))
        ),
        open_review_task_id=uuid_value(
            value["open_review_task_id"], "open_review_task_id", nullable=True
        ),
        retention_policy=MappingProxyType(dict(retention)),
    )
