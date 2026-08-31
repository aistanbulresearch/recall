from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from recall.contracts.enums import (
    ScanRunEventCode,
    ScanRunState,
    WatchCaseState,
)


COLLECTION_NAMES = (
    "artifacts",
    "watch_cases",
    "scan_runs",
    "scan_run_events",
    "review_tasks",
)


@dataclass(frozen=True, slots=True)
class ScanRunRecord:
    run_id: str
    state: ScanRunState
    version: int
    lease_epoch: int
    lease_expires_at: datetime | None
    updated_at: datetime
    scan_run_artifact_id: str | None
    terminal_policy_decision_id: str | None
    failure_receipt_ids: tuple[str, ...]
    last_repeated_state_hash: str | None
    repeated_state_count: int

    def to_wire(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "state": self.state.value,
            "version": self.version,
            "lease_epoch": self.lease_epoch,
            "lease_expires_at": self.lease_expires_at,
            "updated_at": self.updated_at,
            "scan_run_artifact_id": self.scan_run_artifact_id,
            "terminal_policy_decision_id": self.terminal_policy_decision_id,
            "failure_receipt_ids": list(self.failure_receipt_ids),
            "last_repeated_state_hash": self.last_repeated_state_hash,
            "repeated_state_count": self.repeated_state_count,
        }

    @classmethod
    def from_wire(cls, value: dict[str, object]) -> "ScanRunRecord":
        return cls(
            run_id=str(value["run_id"]),
            state=ScanRunState(value["state"]),
            version=int(value["version"]),
            lease_epoch=int(value["lease_epoch"]),
            lease_expires_at=value.get("lease_expires_at"),  # type: ignore[arg-type]
            updated_at=value["updated_at"],  # type: ignore[arg-type]
            scan_run_artifact_id=(
                None
                if value.get("scan_run_artifact_id") is None
                else str(value["scan_run_artifact_id"])
            ),
            terminal_policy_decision_id=(
                None
                if value.get("terminal_policy_decision_id") is None
                else str(value["terminal_policy_decision_id"])
            ),
            failure_receipt_ids=tuple(value.get("failure_receipt_ids", ())),
            last_repeated_state_hash=(
                None
                if value.get("last_repeated_state_hash") is None
                else str(value["last_repeated_state_hash"])
            ),
            repeated_state_count=int(value.get("repeated_state_count", 0)),
        )


@dataclass(frozen=True, slots=True)
class ScanRunEventRecord:
    event_id: str
    run_id: str
    sequence: int
    from_state: ScanRunState | None
    to_state: ScanRunState
    event_code: ScanRunEventCode
    agent_id: str | None
    lease_epoch: int
    created_at: datetime

    def to_wire(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "sequence": self.sequence,
            "from_state": None if self.from_state is None else self.from_state.value,
            "to_state": self.to_state.value,
            "event_code": self.event_code.value,
            "agent_id": self.agent_id,
            "lease_epoch": self.lease_epoch,
            "created_at": self.created_at,
        }

    @classmethod
    def from_wire(cls, value: dict[str, object]) -> "ScanRunEventRecord":
        raw_from = value.get("from_state")
        return cls(
            event_id=str(value["event_id"]),
            run_id=str(value["run_id"]),
            sequence=int(value["sequence"]),
            from_state=None if raw_from is None else ScanRunState(raw_from),
            to_state=ScanRunState(value["to_state"]),
            event_code=ScanRunEventCode(value["event_code"]),
            agent_id=None if value.get("agent_id") is None else str(value["agent_id"]),
            lease_epoch=int(value["lease_epoch"]),
            created_at=value["created_at"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class ReviewTaskRecord:
    task_id: str
    run_id: str
    watch_case_id: str
    policy_decision_id: str
    deduplication_key: str
    artifact_id: str
    state: str
    delivery_state: str
    created_at: datetime

    def to_wire(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "watch_case_id": self.watch_case_id,
            "policy_decision_id": self.policy_decision_id,
            "deduplication_key": self.deduplication_key,
            "artifact_id": self.artifact_id,
            "state": self.state,
            "delivery_state": self.delivery_state,
            "created_at": self.created_at,
        }

    @classmethod
    def from_wire(cls, value: dict[str, object]) -> "ReviewTaskRecord":
        return cls(
            task_id=str(value["task_id"]),
            run_id=str(value["run_id"]),
            watch_case_id=str(value["watch_case_id"]),
            policy_decision_id=str(value["policy_decision_id"]),
            deduplication_key=str(value["deduplication_key"]),
            artifact_id=str(value["artifact_id"]),
            state=str(value["state"]),
            delivery_state=str(value["delivery_state"]),
            created_at=value["created_at"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class WatchCaseRecord:
    watch_case_id: str
    artifact_id: str
    state: WatchCaseState
    version: int
    source_cursors: tuple[tuple[str, str], ...]
    last_verified_snapshot_id: str | None
    pending_observation_hashes: tuple[str, ...]
    open_review_task_id: str | None
    attention_reason_codes: tuple[str, ...]
    next_scan_at: str | None
    updated_at: datetime

    def to_wire(self) -> dict[str, object]:
        return {
            "watch_case_id": self.watch_case_id,
            "artifact_id": self.artifact_id,
            "state": self.state.value,
            "version": self.version,
            "source_cursors": dict(self.source_cursors),
            "last_verified_snapshot_id": self.last_verified_snapshot_id,
            "pending_observation_hashes": list(self.pending_observation_hashes),
            "open_review_task_id": self.open_review_task_id,
            "attention_reason_codes": list(self.attention_reason_codes),
            "next_scan_at": self.next_scan_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_wire(cls, value: dict[str, object]) -> "WatchCaseRecord":
        raw_cursors = value["source_cursors"]
        if not isinstance(raw_cursors, dict):
            raise TypeError("watch_case_source_cursors_invalid")
        return cls(
            watch_case_id=str(value["watch_case_id"]),
            artifact_id=str(value["artifact_id"]),
            state=WatchCaseState(value["state"]),
            version=int(value["version"]),
            source_cursors=tuple(
                sorted((str(key), str(item)) for key, item in raw_cursors.items())
            ),
            last_verified_snapshot_id=(
                None
                if value.get("last_verified_snapshot_id") is None
                else str(value["last_verified_snapshot_id"])
            ),
            pending_observation_hashes=tuple(
                value.get("pending_observation_hashes", ())
            ),
            open_review_task_id=(
                None
                if value.get("open_review_task_id") is None
                else str(value["open_review_task_id"])
            ),
            attention_reason_codes=tuple(value.get("attention_reason_codes", ())),
            next_scan_at=(
                None if value.get("next_scan_at") is None else str(value["next_scan_at"])
            ),
            updated_at=value["updated_at"],  # type: ignore[arg-type]
        )
