from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PLAN_PATH = Path(
    "artifacts/evidence/cohort-compression/COMPRESSED_PREDICTION_PLAN_V2.json"
)
EXPECTED_PLAN_SHA256 = (
    "93393476b4162f0cd6036048d3e5692c6ae1b91f1ede74b6911f80c56930531b"
)
PLAN_VERSION = "COMPRESSED_PREDICTION_PLAN_V2"
DECISION_REFERENCE = "DEC-2026-08-26-046"
SCHEDULE_MODE = "COMPRESSED_MACHINE_TRIGGERED"
TRIGGER_CODE = "COHORT_COMPRESSED_MACHINE_TRIGGERED"


@dataclass(frozen=True, slots=True)
class CompressedCycle:
    cycle_id: str
    cycle_index: int
    cohort_due_date: date
    runs_predicted: int
    window_start: datetime
    window_end: datetime
    trigger_policy: str

    @property
    def schedule_epoch(self) -> str:
        return _timestamp(self.window_start)


@dataclass(frozen=True, slots=True)
class CompressedPlan:
    version: str
    sha256: str
    schedule_mode: str
    decision_reference: str
    cycles: tuple[CompressedCycle, ...]

    def by_id(self, cycle_id: str) -> CompressedCycle:
        matches = tuple(item for item in self.cycles if item.cycle_id == cycle_id)
        if len(matches) != 1:
            raise RuntimeError("compressed_cycle_identity_invalid")
        return matches[0]

    def by_due_date(self, due_date: date) -> CompressedCycle:
        matches = tuple(
            item for item in self.cycles if item.cohort_due_date == due_date
        )
        if len(matches) != 1:
            raise RuntimeError("compressed_cycle_due_date_invalid")
        return matches[0]


def load_compressed_plan(repo_root: Path) -> CompressedPlan:
    root = repo_root.resolve()
    path = (root / PLAN_PATH).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise RuntimeError("compressed_plan_path_invalid")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_PLAN_SHA256:
        raise RuntimeError("compressed_plan_hash_mismatch")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("compressed_plan_json_invalid") from exc
    return parse_compressed_plan(value, sha256=digest)


def parse_compressed_plan(value: Any, *, sha256: str) -> CompressedPlan:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "plan_version",
        "decision_reference",
        "schedule_mode",
        "cycles",
    }:
        raise RuntimeError("compressed_plan_shape_invalid")
    if (
        value["schema_version"] != "2.0.0"
        or value["plan_version"] != PLAN_VERSION
        or value["decision_reference"] != DECISION_REFERENCE
        or value["schedule_mode"] != SCHEDULE_MODE
    ):
        raise RuntimeError("compressed_plan_declaration_invalid")
    raw_cycles = value["cycles"]
    if not isinstance(raw_cycles, list):
        raise RuntimeError("compressed_plan_cycles_invalid")
    cycles = tuple(_parse_cycle(item) for item in raw_cycles)
    _validate_cycles(cycles)
    return CompressedPlan(
        version=PLAN_VERSION,
        sha256=sha256,
        schedule_mode=SCHEDULE_MODE,
        decision_reference=DECISION_REFERENCE,
        cycles=cycles,
    )


def resolve_declared_cycle(now: datetime, plan: CompressedPlan) -> CompressedCycle:
    utc = _aware_utc(now)
    matches = tuple(
        item for item in plan.cycles if item.window_start <= utc <= item.window_end
    )
    if len(matches) != 1:
        raise RuntimeError(f"compressed_cycle_window_match_invalid:{len(matches)}")
    return matches[0]


def _parse_cycle(value: Any) -> CompressedCycle:
    fields = {
        "cycle_id",
        "cycle_index",
        "cohort_due_date",
        "runs_predicted",
        "window_start",
        "window_end",
        "trigger_policy",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise RuntimeError("compressed_cycle_shape_invalid")
    try:
        due = date.fromisoformat(value["cohort_due_date"])
    except (TypeError, ValueError) as exc:
        raise RuntimeError("compressed_cycle_due_date_invalid") from exc
    index = value["cycle_index"]
    predicted = value["runs_predicted"]
    if (
        isinstance(index, bool)
        or not isinstance(index, int)
        or isinstance(predicted, bool)
        or not isinstance(predicted, int)
        or predicted < 0
    ):
        raise RuntimeError("compressed_cycle_count_invalid")
    return CompressedCycle(
        cycle_id=_text(value["cycle_id"]),
        cycle_index=index,
        cohort_due_date=due,
        runs_predicted=predicted,
        window_start=_parse_timestamp(value["window_start"]),
        window_end=_parse_timestamp(value["window_end"]),
        trigger_policy=_text(value["trigger_policy"]),
    )


def _validate_cycles(cycles: tuple[CompressedCycle, ...]) -> None:
    if not cycles:
        raise RuntimeError("compressed_plan_table_empty")
    if [item.cycle_id for item in cycles] != [
        f"c{index}" for index in range(1, len(cycles) + 1)
    ] or [item.cycle_index for item in cycles] != list(
        range(1, len(cycles) + 1)
    ):
        raise RuntimeError("compressed_plan_cycle_order_invalid")
    if len({item.cohort_due_date for item in cycles}) != len(cycles):
        raise RuntimeError("compressed_plan_due_date_collision")
    for position, item in enumerate(cycles):
        if item.window_end <= item.window_start:
            raise RuntimeError("compressed_cycle_window_invalid")
        if position:
            gap = item.window_start - cycles[position - 1].window_end
            if gap < timedelta(minutes=20):
                raise RuntimeError("compressed_cycle_verification_gap_invalid")


def verify_manifest_against_plan(
    manifest: Any,
    plan: CompressedPlan,
    *,
    expected_legacy_failure_receipt_id: str,
) -> None:
    payload = manifest.payload
    cycle = plan.by_id(payload.cycle_id)
    current = (
        payload.cycle_index,
        payload.cohort_due_date,
        payload.delta["runs_predicted"],
        payload.window_start,
        payload.window_end,
        payload.scheduled_for,
    )
    expected = (
        cycle.cycle_index,
        cycle.cohort_due_date.isoformat(),
        cycle.runs_predicted,
        cycle.schedule_epoch,
        _timestamp(cycle.window_end),
        cycle.schedule_epoch,
    )
    compressed_rows = [
        item
        for item in payload.execution_history
        if item["schedule_mode"] == plan.schedule_mode
    ]
    if (
        manifest.schema_name != "CohortDayManifest"
        or manifest.schema_version != "3.0.0"
        or payload.plan_version != plan.version
        or payload.plan_sha256 != plan.sha256
        or payload.schedule_mode != plan.schedule_mode
        or current != expected
        or len(compressed_rows) != cycle.cycle_index
        or payload.execution_history[1]["failure_receipt_id"]
        != expected_legacy_failure_receipt_id
    ):
        raise RuntimeError("compressed_manifest_plan_mismatch")
    for row, expected_cycle in zip(
        compressed_rows, plan.cycles[: cycle.cycle_index], strict=True
    ):
        observed = (
            row["cycle_id"],
            row["cycle_index"],
            row["cohort_due_date"],
            row["runs_predicted"],
            row["runs_created"],
            row["window_start"],
            row["window_end"],
            row["scheduled_for"],
        )
        locked = (
            expected_cycle.cycle_id,
            expected_cycle.cycle_index,
            expected_cycle.cohort_due_date.isoformat(),
            expected_cycle.runs_predicted,
            expected_cycle.runs_predicted,
            expected_cycle.schedule_epoch,
            _timestamp(expected_cycle.window_end),
            expected_cycle.schedule_epoch,
        )
        if observed != locked:
            raise RuntimeError("compressed_manifest_history_plan_mismatch")


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RuntimeError("compressed_cycle_timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError("compressed_cycle_timestamp_invalid") from exc
    return _aware_utc(parsed)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RuntimeError("compressed_cycle_timestamp_not_aware")
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError("compressed_plan_text_invalid")
    return value
