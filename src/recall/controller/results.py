from __future__ import annotations

from dataclasses import dataclass

from recall.ledger.models import ScanRunRecord, WatchCaseRecord


@dataclass(frozen=True, slots=True)
class CreateRunResult:
    record: ScanRunRecord
    created: bool


@dataclass(frozen=True, slots=True)
class CreateWatchCaseResult:
    record: WatchCaseRecord
    created: bool


@dataclass(frozen=True, slots=True)
class TerminalCommitResult:
    record: ScanRunRecord
    policy_decision_id: str | None
    task_id: str | None
    reused: bool


@dataclass(frozen=True, slots=True)
class GuardedStepResult:
    record: ScanRunRecord
    loop_detected: bool
    step_result: object | None
