from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


TRIGGER_CODE = "DAY1_MANUAL"
TRIGGER_AT = "2026-08-25T15:00:00Z"
WINDOW_START = TRIGGER_AT
WINDOW_END = DEADLINE_AT = "2026-08-25T15:09:59Z"
COLLECTION_PREFIX = "dev_recall_m2_day1_20260825_a7f31c9d_"
EXPECTED_PROJECT_SHA256 = (
    "24d93341d7712d0bce1d290be5e86ee7dbf80bfbe29476568a3e083fec064a24"
)
DATABASE = "(default)"


@dataclass(frozen=True, slots=True)
class CohortCase:
    case_id: str
    next_scan_at: str
    cursor: str
    expected_selected: bool


COHORT = (
    CohortCase(
        "b54d172c-d4c7-53d9-b6ea-a8ae154a84d3",
        TRIGGER_AT,
        "day1-due-001",
        True,
    ),
    CohortCase(
        "b8390531-4c50-5f26-83da-0a1dadf07acf",
        "2026-08-26T15:00:00Z",
        "day1-future-001",
        False,
    ),
    CohortCase(
        "6c0e023a-69de-57f3-8f0b-f1107ac7d1e4",
        "2026-08-27T15:00:00Z",
        "day1-future-002",
        False,
    ),
)


BUDGET_SNAPSHOT = {
    "delegation_depth": 0,
    "specialist_invocations": 0,
    "model_calls_per_role": 0,
    "schema_repairs": 0,
    "agent_retries": 0,
    "connector_retries": 0,
    "repeated_state_limit": 1,
    "wall_time_seconds": 599,
    "step_deadlines": {},
    "token_ceilings": {},
}


def enforce_execution_window(now: datetime) -> None:
    start = datetime.fromisoformat(WINDOW_START.replace("Z", "+00:00"))
    end = datetime.fromisoformat(WINDOW_END.replace("Z", "+00:00"))
    if not start <= now <= end:
        raise RuntimeError("day1_execution_outside_frozen_window")
