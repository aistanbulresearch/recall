from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol

from recall.contracts import Artifact
from recall.contracts.enums import ScanRunEventCode

from .models import (
    ReviewTaskRecord,
    ScanRunEventRecord,
    ScanRunRecord,
    WatchCaseRecord,
)


class LedgerPort(Protocol):
    def create_watch_case(
        self,
        value: Mapping[str, Any],
        *,
        cloud_bound_payload: Mapping[str, Any],
        now: datetime,
    ) -> tuple[WatchCaseRecord, bool]: ...

    def create_scan_run(
        self,
        value: Mapping[str, Any],
        *,
        expected_watch_case_version: int,
        expected_source_cursors: Mapping[str, str],
        triggered_at: datetime,
        now: datetime,
    ) -> tuple[ScanRunRecord, bool]: ...

    def append_artifact(self, value: Mapping[str, Any]) -> Artifact: ...

    def get_artifact(self, artifact_id: str) -> dict[str, object] | None: ...

    def list_by_run(self, run_id: str) -> Sequence[dict[str, object]]: ...

    def transition_with_cas(
        self,
        run_id: str,
        *,
        expected_version: int,
        lease_epoch: int,
        to_state: str,
        event_code: ScanRunEventCode,
        now: datetime,
        next_lease_expires_at: datetime | None = None,
    ) -> ScanRunRecord: ...

    def commit_agent_step(
        self,
        run_id: str,
        *,
        expected_version: int,
        lease_epoch: int,
        event_code: ScanRunEventCode,
        artifacts: Sequence[Mapping[str, Any]],
        now: datetime,
    ) -> ScanRunRecord: ...

    def acquire_lease(
        self,
        run_id: str,
        *,
        expected_version: int,
        new_epoch: int,
        expires_at: datetime,
        now: datetime,
    ) -> ScanRunRecord: ...

    def get_scan_run(self, run_id: str) -> ScanRunRecord | None: ...

    def list_scan_run_events(
        self, run_id: str
    ) -> Sequence[ScanRunEventRecord]: ...

    def commit_terminal(
        self,
        run_id: str,
        *,
        expected_version: int,
        lease_epoch: int,
        target_state: str,
        event_code: ScanRunEventCode,
        policy_decision: Mapping[str, Any] | None,
        failure_receipt: Mapping[str, Any] | None,
        review_task: Mapping[str, Any] | None,
        watch_case_update: WatchCaseRecord | None,
        now: datetime,
        terminal_artifacts: Sequence[Mapping[str, Any]] = (),
    ) -> tuple[ScanRunRecord, ReviewTaskRecord | None]: ...

    def list_review_tasks(self, run_id: str) -> Sequence[ReviewTaskRecord]: ...

    def mark_task_delivered(self, task_id: str) -> ReviewTaskRecord: ...

    def get_watch_case(self, watch_case_id: str) -> WatchCaseRecord | None: ...

    def observe_state_hash(
        self,
        run_id: str,
        *,
        expected_version: int,
        lease_epoch: int,
        state_hash: str,
        failure_receipt: Mapping[str, Any],
        now: datetime,
    ) -> tuple[ScanRunRecord, bool]: ...

    def read_back_count(
        self, collection: str, *, run_id: str | None = None
    ) -> int: ...

    def backend_metadata(self) -> Mapping[str, str]: ...
