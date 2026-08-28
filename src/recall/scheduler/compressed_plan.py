from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from recall.contracts.errors import ContractError
from recall.contracts.payloads.scheduler_v33 import (
    require_deadline_completion_binding,
)


PLAN_PATH = Path(
    "artifacts/evidence/cohort-compression/COMPRESSED_PREDICTION_PLAN_V2.json"
)
EXPECTED_PLAN_SHA256 = (
    "49fe3ea1f66440b9008aaf9989c3092a599c8554e777bd5ae6797eedca16b213"
)
PLAN_VERSION = "COMPRESSED_PREDICTION_PLAN_V2"
DECISION_REFERENCE = "DEC-2026-08-26-046"
SCHEDULE_MODE = "COMPRESSED_MACHINE_TRIGGERED"
TRIGGER_CODE = "COHORT_COMPRESSED_MACHINE_TRIGGERED"
PLAN3_SHA256 = "5f18998f11c17b8feef52f90edd9319532a36d525dbea9e9a40538425a28dfa4"
PLAN3_C1_PREFIX = "dev_recall_m2_compressed_p5f18998f11c1_c1_20260826_"
PLAN3_C1_MANIFEST_ID = "bd51bd00-fcf4-5d91-a45d-4d203e02127c"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ACTIVATION_SCHEMAS = {"2.3.0", "2.4.0", "2.5.0"}
_PHASE_TIMEOUT_SCHEMAS = {"2.4.0", "2.5.0"}


class ManifestDeadlinePlanMismatch(RuntimeError):
    """Manifest phase budgets disagree with its immutable resolved cycle."""


@dataclass(frozen=True, slots=True)
class PredecessorBinding:
    binding: str
    cycle_id: str
    plan_sha256: str | None
    collection_prefix: str | None
    manifest_artifact_id: str | None
    manifest_content_hash: str | None
    mode_receipt_artifact_id: str | None
    mode_receipt_content_hash: str | None


@dataclass(frozen=True, slots=True)
class CompressedCycle:
    cycle_id: str
    cycle_index: int
    cohort_due_date: date
    runs_predicted: int
    window_start: datetime
    window_end: datetime
    trigger_policy: str
    predecessor: PredecessorBinding | None
    write_path: str
    epoch_label: str
    evaluation_role: str
    execution_timeout_seconds: int
    write_timeout_seconds: int
    agent_timeout_seconds: int
    activation: str
    execution_profile: str

    @property
    def schedule_epoch(self) -> str:
        return _timestamp(self.window_start)

    @property
    def end_to_end_deadline(self) -> datetime:
        return self.window_start + timedelta(seconds=self.execution_timeout_seconds)


@dataclass(frozen=True, slots=True)
class CompressedPlan:
    version: str
    sha256: str
    schedule_mode: str
    decision_reference: str
    window_semantics: str
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
        "window_semantics",
    }:
        raise RuntimeError("compressed_plan_shape_invalid")
    schema_version = value["schema_version"]
    if (
        schema_version not in {"2.2.0", "2.3.0", "2.4.0", "2.5.0"}
        or value["plan_version"] != PLAN_VERSION
        or value["decision_reference"] != DECISION_REFERENCE
        or value["schedule_mode"] != SCHEDULE_MODE
        or value["window_semantics"] != "TRIGGER_START_ONLY"
    ):
        raise RuntimeError("compressed_plan_declaration_invalid")
    raw_cycles = value["cycles"]
    if not isinstance(raw_cycles, list):
        raise RuntimeError("compressed_plan_cycles_invalid")
    cycles = tuple(_parse_cycle(item, schema_version=schema_version) for item in raw_cycles)
    _validate_cycles(cycles, schema_version=schema_version)
    return CompressedPlan(
        version=PLAN_VERSION,
        sha256=sha256,
        schedule_mode=SCHEDULE_MODE,
        decision_reference=DECISION_REFERENCE,
        window_semantics="TRIGGER_START_ONLY",
        cycles=cycles,
    )


def resolve_declared_cycle(now: datetime, plan: CompressedPlan) -> CompressedCycle:
    utc = _aware_utc(now)
    matches = tuple(
        item for item in plan.cycles if item.window_start <= utc <= item.window_end
    )
    if len(matches) != 1:
        raise RuntimeError(f"compressed_cycle_window_match_invalid:{len(matches)}")
    resolved = matches[0]
    if resolved.activation == "PROVISIONAL_R1_GATED":
        raise RuntimeError("compressed_cycle_not_active")
    return resolved


def _parse_cycle(value: Any, *, schema_version: str) -> CompressedCycle:
    fields = {
        "cycle_id",
        "cycle_index",
        "cohort_due_date",
        "runs_predicted",
        "window_start",
        "window_end",
        "trigger_policy",
        "predecessor",
        "write_path",
        "epoch_label",
        "evaluation_role",
        "execution_timeout_seconds",
    }
    if schema_version in _ACTIVATION_SCHEMAS:
        fields.update({"activation", "execution_profile"})
    if schema_version in _PHASE_TIMEOUT_SCHEMAS:
        fields.update({"write_timeout_seconds", "agent_timeout_seconds"})
    if not isinstance(value, dict) or set(value) != fields:
        raise RuntimeError("compressed_cycle_shape_invalid")
    try:
        due = date.fromisoformat(value["cohort_due_date"])
    except (TypeError, ValueError) as exc:
        raise RuntimeError("compressed_cycle_due_date_invalid") from exc
    index = value["cycle_index"]
    predicted = value["runs_predicted"]
    timeout = value["execution_timeout_seconds"]
    write_timeout = (
        value["write_timeout_seconds"]
        if schema_version in _PHASE_TIMEOUT_SCHEMAS
        else timeout
    )
    agent_timeout = (
        value["agent_timeout_seconds"]
        if schema_version in _PHASE_TIMEOUT_SCHEMAS
        else 0
    )
    if (
        isinstance(index, bool)
        or not isinstance(index, int)
        or isinstance(predicted, bool)
        or not isinstance(predicted, int)
        or predicted < 0
        or isinstance(timeout, bool)
        or not isinstance(timeout, int)
        or timeout <= 0
        or isinstance(write_timeout, bool)
        or not isinstance(write_timeout, int)
        or write_timeout <= 0
        or isinstance(agent_timeout, bool)
        or not isinstance(agent_timeout, int)
        or agent_timeout < 0
        or write_timeout + agent_timeout > timeout
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
        predecessor=_parse_predecessor(value["predecessor"]),
        write_path=_text(value["write_path"]),
        epoch_label=_text(value["epoch_label"]),
        evaluation_role=_text(value["evaluation_role"]),
        execution_timeout_seconds=timeout,
        write_timeout_seconds=write_timeout,
        agent_timeout_seconds=agent_timeout,
        activation=(
            _text(value["activation"])
            if schema_version in _ACTIVATION_SCHEMAS
            else "LEGACY_PLAN5"
        ),
        execution_profile=(
            _text(value["execution_profile"])
            if schema_version in _ACTIVATION_SCHEMAS
            else "CREATE_ONLY_V1"
        ),
    )


def _parse_predecessor(value: Any) -> PredecessorBinding | None:
    if value is None:
        return None
    fields = {
        "binding", "cycle_id", "plan_sha256", "collection_prefix",
        "manifest_artifact_id", "manifest_content_hash",
        "mode_receipt_artifact_id", "mode_receipt_content_hash",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise RuntimeError("compressed_predecessor_shape_invalid")
    binding = _text(value["binding"])
    cycle_id = _text(value["cycle_id"])
    if binding == "CURRENT_PLAN":
        if any(value[field] is not None for field in (
            "plan_sha256", "collection_prefix", "manifest_artifact_id",
            "manifest_content_hash", "mode_receipt_artifact_id",
            "mode_receipt_content_hash",
        )):
            raise RuntimeError("compressed_predecessor_current_binding_invalid")
        return PredecessorBinding(
            binding, cycle_id, None, None, None, None, None, None
        )
    if binding != "EXTERNAL_PLAN":
        raise RuntimeError("compressed_predecessor_binding_invalid")
    plan_sha = _text(value["plan_sha256"])
    prefix = _text(value["collection_prefix"])
    manifest_id = _text(value["manifest_artifact_id"])
    manifest_hash = _text(value["manifest_content_hash"])
    mode_id = _text(value["mode_receipt_artifact_id"])
    mode_hash = _text(value["mode_receipt_content_hash"])
    if (
        not _SHA256.fullmatch(plan_sha)
        or not _SHA256.fullmatch(manifest_hash)
        or not _SHA256.fullmatch(mode_hash)
    ):
        raise RuntimeError("compressed_predecessor_plan_hash_invalid")
    return PredecessorBinding(
        binding, cycle_id, plan_sha, prefix, manifest_id,
        manifest_hash, mode_id, mode_hash,
    )


def _validate_cycles(
    cycles: tuple[CompressedCycle, ...], *, schema_version: str
) -> None:
    if not cycles:
        raise RuntimeError("compressed_plan_table_empty")
    if [item.cycle_id for item in cycles] != [
        f"c{index}" for index in range(1, len(cycles) + 1)
    ] or [item.cycle_index for item in cycles] != list(
        range(1, len(cycles) + 1)
    ):
        raise RuntimeError("compressed_plan_cycle_order_invalid")
    if len(cycles) != 6 or len({item.cohort_due_date for item in cycles}) != len(cycles):
        raise RuntimeError("compressed_plan_due_date_collision")
    for position, item in enumerate(cycles):
        if item.window_end <= item.window_start:
            raise RuntimeError("compressed_cycle_window_invalid")
        if position:
            previous = cycles[position - 1]
            if item.window_start - previous.window_start < timedelta(minutes=20):
                raise RuntimeError("compressed_cycle_start_interval_invalid")
            if item.window_start <= previous.window_end:
                raise RuntimeError("compressed_cycle_window_overlap")
            binding = item.predecessor
            if binding is None or binding.cycle_id != previous.cycle_id:
                raise RuntimeError("compressed_predecessor_cycle_invalid")
        elif item.predecessor is not None:
            raise RuntimeError("compressed_c1_predecessor_forbidden")
    if any(item.write_path != "EXTERNAL_IMMUTABLE" for item in cycles[:2]):
        raise RuntimeError("compressed_c1_execution_binding_invalid")
    if any(item.write_path != "FIRESTORE_BATCH_V1" for item in cycles[2:]):
        raise RuntimeError("compressed_c6_batch_gate_missing")
    expected_roles = (
        "IMMUTABLE_EXECUTED", "IMMUTABLE_EXECUTED",
        "RAMP_FIRST_PASS", "RAMP_FIRST_PASS", "RAMP_FIRST_PASS",
        "PORTFOLIO_REASSESSMENT",
    )
    if tuple(item.evaluation_role for item in cycles) != expected_roles:
        raise RuntimeError("compressed_evaluation_role_invalid")
    if schema_version in _ACTIVATION_SCHEMAS:
        if tuple(item.execution_profile for item in cycles) != (
            "CREATE_ONLY_V1",
            "CREATE_ONLY_V1",
            "FULL_AUDIT_V1",
            "FULL_AUDIT_V1",
            "FULL_AUDIT_V1",
            "FULL_AUDIT_V1",
        ):
            raise RuntimeError("compressed_execution_profile_invalid")
    if schema_version in {"2.3.0", "2.4.0"}:
        if tuple(item.activation for item in cycles) != (
            "IMMUTABLE_EXECUTED",
            "IMMUTABLE_EXECUTED",
            "ACTIVE",
            "PROVISIONAL_R1_GATED",
            "PROVISIONAL_R1_GATED",
            "PROVISIONAL_R1_GATED",
        ):
            raise RuntimeError("compressed_cycle_activation_invalid")
    elif schema_version == "2.5.0":
        activations = tuple(item.activation for item in cycles)
        active_tail = activations[2:]
        first_provisional = (
            active_tail.index("PROVISIONAL_R1_GATED")
            if "PROVISIONAL_R1_GATED" in active_tail
            else len(active_tail)
        )
        if (
            activations[:2] != ("IMMUTABLE_EXECUTED", "IMMUTABLE_EXECUTED")
            or not active_tail
            or active_tail[0] != "ACTIVE"
            or any(
                activation not in {"ACTIVE", "PROVISIONAL_R1_GATED"}
                for activation in active_tail
            )
            or "ACTIVE" in active_tail[first_provisional + 1 :]
        ):
            raise RuntimeError("compressed_cycle_activation_invalid")
    if schema_version in _PHASE_TIMEOUT_SCHEMAS:
        if any(item.agent_timeout_seconds != 0 for item in cycles[:2]) or any(
            item.agent_timeout_seconds <= 0 for item in cycles[2:]
        ):
            raise RuntimeError("compressed_phase_timeout_invalid")
    c2_binding = cycles[1].predecessor
    if (
        c2_binding is None
        or c2_binding.binding != "EXTERNAL_PLAN"
        or c2_binding.plan_sha256 != PLAN3_SHA256
        or c2_binding.collection_prefix != PLAN3_C1_PREFIX
        or c2_binding.manifest_artifact_id != PLAN3_C1_MANIFEST_ID
    ):
        raise RuntimeError("compressed_c2_external_predecessor_invalid")
    if cycles[2].predecessor is None or cycles[2].predecessor.binding != "EXTERNAL_PLAN":
        raise RuntimeError("compressed_c3_external_predecessor_invalid")
    if any(
        item.predecessor is None or item.predecessor.binding != "CURRENT_PLAN"
        for item in cycles[3:]
    ):
        raise RuntimeError("compressed_current_predecessor_invalid")

    # PASS qualification is end-to-end write plus exact readback <=2 s/case.
    # Freeze the worst-case review gaps, not merely nominal trigger spacing.
    for current, successor in zip(cycles[2:5], cycles[3:6], strict=True):
        latest_qualified = current.window_end + timedelta(
            seconds=current.runs_predicted * 2
        )
        if successor.window_start - latest_qualified < timedelta(minutes=20):
            raise RuntimeError("compressed_qualified_review_gap_invalid")
    final_latest = cycles[5].window_end + timedelta(
        seconds=cycles[5].runs_predicted * 2
    )
    if final_latest > cycles[5].window_start + timedelta(
        seconds=cycles[5].execution_timeout_seconds
    ):
        raise RuntimeError("compressed_final_timeout_invalid")


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
        or manifest.schema_version not in {"3.0.0", "3.1.0", "3.2.0", "3.3.0"}
        or payload.plan_version != plan.version
        or payload.plan_sha256 != plan.sha256
        or payload.schedule_mode != plan.schedule_mode
        or current != expected
        or len(compressed_rows) != cycle.cycle_index
        or payload.execution_history[1]["failure_receipt_id"]
        != expected_legacy_failure_receipt_id
    ):
        raise RuntimeError("compressed_manifest_plan_mismatch")
    if manifest.schema_version == "3.3.0":
        _verify_deadline_policy_against_cycle(payload.deadline_policy, cycle)
        try:
            require_deadline_completion_binding(
                manifest.created_at,
                payload.deadline_policy,
            )
        except ContractError as exc:
            raise ManifestDeadlinePlanMismatch(
                "compressed_manifest_deadline_plan_mismatch"
            ) from exc
    completed_at = datetime.fromisoformat(manifest.created_at.replace("Z", "+00:00"))
    end_to_end_deadline = cycle.window_start + timedelta(
        seconds=cycle.execution_timeout_seconds
    )
    if completed_at < cycle.window_start or (
        completed_at > end_to_end_deadline
        and manifest.status.value != "INCOMPLETE"
    ):
        raise RuntimeError("compressed_manifest_completion_timeout")
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


def _verify_deadline_policy_against_cycle(
    deadline: Any,
    cycle: CompressedCycle,
) -> None:
    trigger_started_at = _parse_timestamp(deadline["trigger_started_at"])
    write_completed_at = _parse_timestamp(deadline["write_completed_at"])
    end_to_end_deadline = cycle.end_to_end_deadline
    expected = (
        cycle.execution_timeout_seconds,
        cycle.write_timeout_seconds,
        cycle.agent_timeout_seconds,
        _timestamp(cycle.window_end),
        _timestamp(
            min(
                trigger_started_at
                + timedelta(seconds=cycle.write_timeout_seconds),
                end_to_end_deadline,
            )
        ),
        _timestamp(
            min(
                write_completed_at
                + timedelta(seconds=cycle.agent_timeout_seconds),
                end_to_end_deadline,
            )
        ),
        _timestamp(end_to_end_deadline),
    )
    observed = (
        deadline["execution_timeout_seconds"],
        deadline["write_timeout_seconds"],
        deadline["agent_timeout_seconds"],
        deadline["trigger_window_end"],
        deadline["write_deadline"],
        deadline["agent_deadline"],
        deadline["authoritative_end_to_end_deadline"],
    )
    if observed != expected:
        raise ManifestDeadlinePlanMismatch(
            "compressed_manifest_deadline_plan_mismatch"
        )


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
