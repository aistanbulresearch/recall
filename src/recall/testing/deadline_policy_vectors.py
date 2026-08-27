from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from recall.scheduler.compressed_plan import PLAN_PATH


VECTOR_PATH = Path("tests/fixtures/cohort_deadline_policy_vectors.json")


def build_deadline_policy_vectors(repo_root: Path) -> dict[str, object]:
    plan_path = repo_root / PLAN_PATH
    plan_bytes = plan_path.read_bytes()
    plan_document = json.loads(plan_bytes.decode("utf-8"))
    plan_sha256 = hashlib.sha256(plan_bytes).hexdigest()
    cycle = next(item for item in plan_document["cycles"] if item["cycle_id"] == "c3")
    window_start = _timestamp(cycle["window_start"])
    trigger_started = window_start + timedelta(microseconds=123_456)
    write_completed = window_start + timedelta(minutes=5, microseconds=654_321)
    agent_completed = window_start + timedelta(minutes=50, microseconds=999_999)
    end_to_end = window_start + timedelta(
        seconds=cycle["execution_timeout_seconds"]
    )
    shifted_start = window_start + timedelta(hours=2)

    context = {
        "plan_version": plan_document["plan_version"],
        "plan_sha256": plan_sha256,
        "cycle_id": cycle["cycle_id"],
        "window_start": cycle["window_start"],
        "window_end": cycle["window_end"],
        "scheduled_for": cycle["window_start"],
        "created_at": _wire_timestamp(agent_completed),
    }
    valid = {
        "trigger_started_at": _wire_timestamp_with_extra_precision(
            trigger_started
        ),
        "trigger_window_end": cycle["window_end"],
        "write_timeout_seconds": cycle["write_timeout_seconds"],
        "write_deadline": _wire_timestamp(
            min(
                trigger_started
                + timedelta(seconds=cycle["write_timeout_seconds"]),
                end_to_end,
            )
        ),
        "write_completed_at": _wire_timestamp(write_completed),
        "agent_timeout_seconds": cycle["agent_timeout_seconds"],
        "agent_deadline": _wire_timestamp(
            min(
                write_completed
                + timedelta(seconds=cycle["agent_timeout_seconds"]),
                end_to_end,
            )
        ),
        "agent_completed_at": context["created_at"],
        "execution_timeout_seconds": cycle["execution_timeout_seconds"],
        "authoritative_end_to_end_deadline": _wire_timestamp(end_to_end),
    }

    vectors = [
        _vector("valid_c3_fractional_microseconds", True, context, valid),
        _vector(
            "legacy_20_00_plus_3600_to_23_00",
            False,
            {
                **context,
                "window_start": "2026-08-27T20:00:00Z",
                "window_end": "2026-08-27T20:30:00Z",
                "scheduled_for": "2026-08-27T20:00:00Z",
                "created_at": "2026-08-27T21:50:00Z",
            },
            {
                "trigger_started_at": "2026-08-27T20:00:00Z",
                "trigger_window_end": "2026-08-27T20:30:00Z",
                "write_timeout_seconds": 300,
                "write_deadline": "2026-08-27T21:00:00Z",
                "write_completed_at": "2026-08-27T20:40:00Z",
                "agent_timeout_seconds": 600,
                "agent_deadline": "2026-08-27T22:00:00Z",
                "agent_completed_at": "2026-08-27T21:50:00Z",
                "execution_timeout_seconds": 3600,
                "authoritative_end_to_end_deadline": "2026-08-27T23:00:00Z",
            },
        ),
        _mutation(
            "coherent_phase_repartition",
            context,
            valid,
            {
                "write_timeout_seconds": 3599,
                "write_deadline": _wire_timestamp(
                    trigger_started + timedelta(seconds=3599)
                ),
                "agent_timeout_seconds": 1,
                "agent_deadline": _wire_timestamp(
                    write_completed + timedelta(seconds=1)
                ),
            },
        ),
        _mutation(
            "trigger_window_end_mismatch",
            context,
            valid,
            {
                "trigger_window_end": _wire_timestamp(
                    _timestamp(cycle["window_end"]) - timedelta(seconds=1)
                )
            },
        ),
        _mutation(
            "write_deadline_mismatch",
            context,
            valid,
            {
                "write_deadline": _wire_timestamp(
                    trigger_started
                    + timedelta(seconds=cycle["write_timeout_seconds"] + 1)
                )
            },
        ),
        _mutation(
            "agent_deadline_mismatch",
            context,
            valid,
            {
                "agent_deadline": _wire_timestamp(
                    write_completed
                    + timedelta(seconds=cycle["agent_timeout_seconds"] + 1)
                )
            },
        ),
        _mutation(
            "end_to_end_deadline_mismatch",
            context,
            valid,
            {
                "authoritative_end_to_end_deadline": _wire_timestamp(
                    end_to_end + timedelta(seconds=1)
                )
            },
        ),
        _vector(
            "created_at_mismatch",
            False,
            {
                **context,
                "created_at": _wire_timestamp(
                    agent_completed + timedelta(seconds=1)
                ),
            },
            valid,
        ),
        _vector(
            "coherent_window_shift_from_plan",
            False,
            {
                **context,
                "window_start": _wire_timestamp(shifted_start),
                "window_end": _wire_timestamp(
                    _timestamp(cycle["window_end"]) + timedelta(hours=2)
                ),
                "scheduled_for": _wire_timestamp(shifted_start),
                "created_at": _wire_timestamp(agent_completed + timedelta(hours=2)),
            },
            {
                **valid,
                "trigger_started_at": _wire_timestamp_with_extra_precision(
                    trigger_started + timedelta(hours=2)
                ),
                "trigger_window_end": _wire_timestamp(
                    _timestamp(cycle["window_end"]) + timedelta(hours=2)
                ),
                "write_deadline": _wire_timestamp(
                    _timestamp(valid["write_deadline"]) + timedelta(hours=2)
                ),
                "write_completed_at": _wire_timestamp(
                    write_completed + timedelta(hours=2)
                ),
                "agent_deadline": _wire_timestamp(
                    _timestamp(valid["agent_deadline"]) + timedelta(hours=2)
                ),
                "agent_completed_at": _wire_timestamp(
                    agent_completed + timedelta(hours=2)
                ),
                "authoritative_end_to_end_deadline": _wire_timestamp(
                    end_to_end + timedelta(hours=2)
                ),
            },
        ),
        _vector(
            "window_end_plan_mismatch",
            False,
            {
                **context,
                "window_end": _wire_timestamp(
                    _timestamp(cycle["window_end"]) + timedelta(seconds=1)
                ),
            },
            {
                **valid,
                "trigger_window_end": _wire_timestamp(
                    _timestamp(cycle["window_end"]) + timedelta(seconds=1)
                ),
            },
        ),
        _vector(
            "scheduled_for_plan_mismatch",
            False,
            {
                **context,
                "scheduled_for": _wire_timestamp(
                    window_start + timedelta(seconds=1)
                ),
            },
            valid,
        ),
        _vector(
            "unknown_plan_hash",
            False,
            {**context, "plan_sha256": "f" * 64},
            valid,
        ),
    ]
    return {
        "schema_name": "DeadlinePolicyGoldenVectors",
        "schema_version": "1.0.0",
        "plan_artifact": {
            "path": PLAN_PATH.as_posix(),
            "sha256": plan_sha256,
            "raw_text": plan_bytes.decode("utf-8"),
        },
        "vectors": vectors,
    }


def render_deadline_policy_vectors(repo_root: Path) -> bytes:
    value = build_deadline_policy_vectors(repo_root)
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _vector(
    vector_id: str,
    accepted: bool,
    context: dict[str, object],
    policy: dict[str, object],
) -> dict[str, object]:
    return {
        "vector_id": vector_id,
        "expected": "ACCEPT" if accepted else "REJECT",
        "manifest_context": deepcopy(context),
        "deadline_policy": deepcopy(policy),
    }


def _mutation(
    vector_id: str,
    context: dict[str, object],
    policy: dict[str, object],
    changes: dict[str, object],
) -> dict[str, object]:
    changed = deepcopy(policy)
    changed.update(changes)
    return _vector(vector_id, False, context, changed)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("deadline_vector_timestamp_invalid")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo is None:
        raise ValueError("deadline_vector_timestamp_invalid")
    return parsed.astimezone(timezone.utc)


def _wire_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("deadline_vector_timestamp_invalid")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _wire_timestamp_with_extra_precision(value: datetime) -> str:
    rendered = _wire_timestamp(value)
    if "." not in rendered:
        raise ValueError("deadline_vector_fractional_timestamp_required")
    return rendered[:-1] + "7Z"
