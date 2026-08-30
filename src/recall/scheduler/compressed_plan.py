from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from recall.contracts.errors import ContractError
from recall.contracts.payloads.scheduler_v33 import (
    require_deadline_completion_binding,
)
from recall.contracts.payloads.scheduler_v34_support import (
    FINAL_ONLY_OWNER_RELEASE_REASON,
    FINAL_ONLY_OWNER_RELEASE_TOKEN,
    final_only_owner_release_warnings,
)


PLAN_PATH = Path(
    "artifacts/evidence/cohort-compression/COMPRESSED_PREDICTION_PLAN_V2.json"
)
PLAN9_HISTORICAL_SHA256 = (
    "c3e454c1b593c98a558c3f03c67b7de6f5d0e2d1e3c98efdfb91d4c5530a9791"
)
FINAL_ONLY_PLAN_SHA256 = (
    "8cb69fbd44403e299ccdc00a9a0c5fe3b18e70f5d7aa43c0d5d2ee48d7e424d7"
)
FINAL_ONLY_RECOVERY_REASON = "RECOVER_CANCELLED_FINAL_EXECUTION_APPEND_ONLY"
EXPECTED_PLAN_SHA256 = FINAL_ONLY_PLAN_SHA256
PLAN_VERSION = "COMPRESSED_PREDICTION_PLAN_V2"
DECISION_REFERENCE = "DEC-2026-08-26-046"
SCHEDULE_MODE = "COMPRESSED_MACHINE_TRIGGERED"
TRIGGER_CODE = "COHORT_COMPRESSED_MACHINE_TRIGGERED"
PLAN3_SHA256 = "5f18998f11c17b8feef52f90edd9319532a36d525dbea9e9a40538425a28dfa4"
PLAN3_C1_PREFIX = "dev_recall_m2_compressed_p5f18998f11c1_c1_20260826_"
PLAN3_C1_MANIFEST_ID = "bd51bd00-fcf4-5d91-a45d-4d203e02127c"
PLAN9_RETRY_EPOCH_LABEL = "PLAN6_RAMP_FIRST_PASS_RETRY"
PLAN9_C4_EPOCH_LABEL = "PLAN6_R2_80_ACTIVE"
PLAN10_C5_EPOCH_LABEL = "PLAN6_R3_200_ACTIVE"
PLAN10_C6_EPOCH_LABEL = "PLAN6_FINAL_456_REASSESSMENT_ACTIVE"
PLAN10_C6_PHASE_TIMEOUTS = (28_800, 1_800, 27_000)
PLAN10_C6_WINDOW_DURATION = timedelta(hours=7, minutes=43, seconds=59)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ACTIVATION_SCHEMAS = {
    "2.3.0", "2.4.0", "2.5.0", "2.6.0", "2.7.0", "2.8.0",
}
_PHASE_TIMEOUT_SCHEMAS = {"2.4.0", "2.5.0", "2.6.0", "2.7.0", "2.8.0"}


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
class HistoricalEvidenceBinding:
    cycle_id: str
    evidence_role: str
    execution_status: str
    plan_sha256: str
    collection_prefix: str
    manifest_artifact_id: str
    manifest_content_hash: str
    mode_receipt_artifact_id: str | None
    mode_receipt_content_hash: str | None


@dataclass(frozen=True, slots=True)
class RetiredCycle:
    cycle_id: str
    state: str
    execution_status: str
    runs_created: int


@dataclass(frozen=True, slots=True)
class PlanSupersession:
    mode: str
    superseded_plan_sha256: str
    owner_decision: str
    reason_code: str
    historical_evidence: tuple[HistoricalEvidenceBinding, ...]
    retired_cycles: tuple[RetiredCycle, ...]


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
    schema_version: str
    version: str
    sha256: str
    schedule_mode: str
    decision_reference: str
    window_semantics: str
    cycles: tuple[CompressedCycle, ...]
    supersession: PlanSupersession | None = None

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


@dataclass(frozen=True, slots=True)
class FinalOnlyOwnerRelease:
    cycle_id: str
    token: str
    reason: str
    actual_start: datetime
    write_deadline: datetime
    execution_deadline: datetime
    agent_timeout_seconds: int
    max_retries: int
    recovery: "FinalOnlyRecoverySpec | None" = None


@dataclass(frozen=True, slots=True)
class FinalOnlyRecoverySpec:
    recovery_attempt_id: str
    owner_recovery_reason: str
    previous_execution_id: str
    previous_collection_prefix: str
    previous_source_commit: str
    previous_image_digest: str
    previous_snapshot_sha256: str
    identity_scope: str
    collection_prefix: str


def authorize_final_only_owner_release(
    plan: CompressedPlan,
    *,
    token: str,
    reason: str,
    actual_start: datetime,
    max_retries: int,
    recovery: FinalOnlyRecoverySpec | None = None,
) -> FinalOnlyOwnerRelease:
    if token != FINAL_ONLY_OWNER_RELEASE_TOKEN:
        raise RuntimeError("final_only_owner_release_token_invalid")
    if reason != FINAL_ONLY_OWNER_RELEASE_REASON:
        raise RuntimeError("final_only_owner_release_reason_invalid")
    if isinstance(max_retries, bool) or max_retries != 0:
        raise RuntimeError("final_only_owner_release_max_retries_invalid")
    active = tuple(item for item in plan.cycles if item.activation == "ACTIVE")
    if (
        plan.schema_version != "2.8.0"
        or plan.supersession is None
        or len(active) != 1
        or active[0].cycle_id != "c6"
    ):
        raise RuntimeError("final_only_owner_release_plan_invalid")
    cycle = active[0]
    if (
        cycle.runs_predicted != 456
        or cycle.execution_profile != "FULL_AUDIT_V1"
        or (
            cycle.execution_timeout_seconds,
            cycle.write_timeout_seconds,
            cycle.agent_timeout_seconds,
        )
        != PLAN10_C6_PHASE_TIMEOUTS
    ):
        raise RuntimeError("final_only_owner_release_cycle_invalid")
    start = _aware_utc(actual_start)
    if start <= cycle.window_end:
        raise RuntimeError("final_only_owner_release_not_late")
    return FinalOnlyOwnerRelease(
        cycle_id=cycle.cycle_id,
        token=token,
        reason=reason,
        actual_start=start,
        write_deadline=start + timedelta(seconds=cycle.write_timeout_seconds),
        execution_deadline=start
        + timedelta(seconds=cycle.execution_timeout_seconds),
        agent_timeout_seconds=cycle.agent_timeout_seconds,
        max_retries=max_retries,
        recovery=recovery,
    )


def authorize_final_only_recovery(
    plan: CompressedPlan,
    *,
    cycle: CompressedCycle,
    recovery_attempt_id: str,
    owner_recovery_reason: str,
    previous_execution_id: str,
    previous_source_commit: str,
    previous_image_digest: str,
    previous_snapshot_sha256: str,
) -> FinalOnlyRecoverySpec:
    try:
        canonical_attempt = str(UUID(recovery_attempt_id))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("final_recovery_attempt_id_invalid") from exc
    if canonical_attempt != recovery_attempt_id:
        raise RuntimeError("final_recovery_attempt_id_invalid")
    if owner_recovery_reason != FINAL_ONLY_RECOVERY_REASON:
        raise RuntimeError("final_recovery_reason_invalid")
    if (
        plan.schema_version != "2.8.0"
        or cycle != plan.by_id("c6")
        or cycle.activation != "ACTIVE"
        or cycle.runs_predicted != 456
    ):
        raise RuntimeError("final_recovery_plan_invalid")
    if not re.fullmatch(r"recall-cohort-daily-[a-z0-9-]+", previous_execution_id):
        raise RuntimeError("final_recovery_previous_execution_invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", previous_source_commit):
        raise RuntimeError("final_recovery_previous_source_invalid")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", previous_image_digest):
        raise RuntimeError("final_recovery_previous_image_invalid")
    if not _SHA256.fullmatch(previous_snapshot_sha256):
        raise RuntimeError("final_recovery_previous_snapshot_invalid")
    attempt_hash = hashlib.sha256(canonical_attempt.encode("ascii")).hexdigest()
    identity_scope = f"final-only-recovery:{attempt_hash}"
    prefix = (
        f"dev_recall_final_p{plan.sha256[:8]}_c6_r{attempt_hash[:10]}_"
    )
    old_prefix = (
        f"dev_recall_m2_compressed_p{plan.sha256[:12]}_c6_"
        f"{cycle.cohort_due_date:%Y%m%d}_"
    )
    if (
        prefix == old_prefix
        or len(f"{prefix}tool_gateway_invocations") > 75
    ):
        raise RuntimeError("final_recovery_namespace_invalid")
    return FinalOnlyRecoverySpec(
        recovery_attempt_id=canonical_attempt,
        owner_recovery_reason=owner_recovery_reason,
        previous_execution_id=previous_execution_id,
        previous_collection_prefix=old_prefix,
        previous_source_commit=previous_source_commit,
        previous_image_digest=previous_image_digest,
        previous_snapshot_sha256=previous_snapshot_sha256,
        identity_scope=identity_scope,
        collection_prefix=prefix,
    )


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
    if not isinstance(value, dict):
        raise RuntimeError("compressed_plan_shape_invalid")
    schema_version = value.get("schema_version")
    expected_fields = {
        "schema_version",
        "plan_version",
        "decision_reference",
        "schedule_mode",
        "cycles",
        "window_semantics",
    }
    if schema_version == "2.8.0":
        expected_fields.add("supersession")
    if set(value) != expected_fields:
        raise RuntimeError("compressed_plan_shape_invalid")
    if (
        schema_version
        not in {
            "2.2.0", "2.3.0", "2.4.0", "2.5.0", "2.6.0", "2.7.0", "2.8.0",
        }
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
    supersession = (
        _parse_supersession(value["supersession"])
        if schema_version == "2.8.0"
        else None
    )
    _validate_cycles(
        cycles,
        schema_version=schema_version,
        supersession=supersession,
    )
    return CompressedPlan(
        schema_version=schema_version,
        version=PLAN_VERSION,
        sha256=sha256,
        schedule_mode=SCHEDULE_MODE,
        decision_reference=DECISION_REFERENCE,
        window_semantics="TRIGGER_START_ONLY",
        cycles=cycles,
        supersession=supersession,
    )


def resolve_declared_cycle(now: datetime, plan: CompressedPlan) -> CompressedCycle:
    utc = _aware_utc(now)
    matches = tuple(
        item
        for item in plan.cycles
        if item.window_start <= utc <= item.window_end
        and (plan.schema_version != "2.8.0" or item.activation == "ACTIVE")
    )
    if len(matches) != 1:
        raise RuntimeError(f"compressed_cycle_window_match_invalid:{len(matches)}")
    resolved = matches[0]
    if (
        resolved.activation == "PROVISIONAL_R1_GATED"
        or (
            plan.schema_version in {"2.7.0", "2.8.0"}
            and resolved.activation != "ACTIVE"
        )
    ):
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


def _parse_supersession(value: Any) -> PlanSupersession:
    fields = {
        "mode", "superseded_plan_sha256", "owner_decision", "reason_code",
        "historical_evidence", "retired_cycles",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise RuntimeError("compressed_final_only_supersession_shape_invalid")
    if (
        value["mode"] != "FINAL_ONLY_TIMEBOX"
        or value["superseded_plan_sha256"] != PLAN9_HISTORICAL_SHA256
        or value["owner_decision"]
        != "RETIRE_RAMP_DUE_TIMEBOX_AND_AUTHORIZE_FINAL_456"
        or value["reason_code"] != "RAMP_TIMEBOX_EXHAUSTED"
    ):
        raise RuntimeError("compressed_final_only_supersession_invalid")
    raw_evidence = value["historical_evidence"]
    raw_retired = value["retired_cycles"]
    if not isinstance(raw_evidence, list) or not isinstance(raw_retired, list):
        raise RuntimeError("compressed_final_only_supersession_shape_invalid")
    evidence = tuple(_parse_historical_evidence(item) for item in raw_evidence)
    retired = tuple(_parse_retired_cycle(item) for item in raw_retired)
    if (
        [(item.cycle_id, item.evidence_role, item.execution_status) for item in evidence[:2]]
        != [
            ("c1", "IMMUTABLE_EXECUTED", "COMPLETE"),
            ("c2", "IMMUTABLE_EXECUTED", "COMPLETE"),
        ]
        or len(evidence) < 3
        or any(
            item.cycle_id != "c3"
            or item.evidence_role != "HISTORICAL_ATTEMPT"
            or item.execution_status != "INCOMPLETE"
            for item in evidence[2:]
        )
    ):
        raise RuntimeError("compressed_final_only_history_invalid")
    if [(item.cycle_id, item.state, item.execution_status, item.runs_created) for item in retired] != [
        ("c4", "RETIRED_TIMEBOX", "NOT_EXECUTED", 0),
        ("c5", "RETIRED_TIMEBOX", "NOT_EXECUTED", 0),
    ]:
        raise RuntimeError("compressed_final_only_retirement_invalid")
    return PlanSupersession(
        mode=value["mode"],
        superseded_plan_sha256=value["superseded_plan_sha256"],
        owner_decision=value["owner_decision"],
        reason_code=value["reason_code"],
        historical_evidence=evidence,
        retired_cycles=retired,
    )


def _parse_historical_evidence(value: Any) -> HistoricalEvidenceBinding:
    fields = {
        "cycle_id", "evidence_role", "execution_status", "plan_sha256",
        "collection_prefix", "manifest_artifact_id", "manifest_content_hash",
        "mode_receipt_artifact_id", "mode_receipt_content_hash",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise RuntimeError("compressed_final_only_evidence_shape_invalid")
    manifest_hash = value["manifest_content_hash"]
    mode_id = value["mode_receipt_artifact_id"]
    mode_hash = value["mode_receipt_content_hash"]
    if (
        not _SHA256.fullmatch(str(value["plan_sha256"]))
        or not _SHA256.fullmatch(str(manifest_hash))
        or not _canonical_uuid(value["manifest_artifact_id"])
        or (mode_id is None) is not (mode_hash is None)
        or (
            mode_id is not None
            and (
                not _canonical_uuid(mode_id)
                or not _SHA256.fullmatch(str(mode_hash))
            )
        )
    ):
        raise RuntimeError("compressed_final_only_evidence_hash_invalid")
    return HistoricalEvidenceBinding(
        cycle_id=_text(value["cycle_id"]),
        evidence_role=_text(value["evidence_role"]),
        execution_status=_text(value["execution_status"]),
        plan_sha256=str(value["plan_sha256"]),
        collection_prefix=_text(value["collection_prefix"]),
        manifest_artifact_id=str(value["manifest_artifact_id"]),
        manifest_content_hash=str(manifest_hash),
        mode_receipt_artifact_id=None if mode_id is None else str(mode_id),
        mode_receipt_content_hash=None if mode_hash is None else str(mode_hash),
    )


def _parse_retired_cycle(value: Any) -> RetiredCycle:
    fields = {"cycle_id", "state", "execution_status", "runs_created"}
    if not isinstance(value, dict) or set(value) != fields:
        raise RuntimeError("compressed_final_only_retirement_invalid")
    return RetiredCycle(
        cycle_id=_text(value["cycle_id"]),
        state=_text(value["state"]),
        execution_status=_text(value["execution_status"]),
        runs_created=value["runs_created"],
    )


def _validate_cycles(
    cycles: tuple[CompressedCycle, ...],
    *,
    schema_version: str,
    supersession: PlanSupersession | None,
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
            if schema_version != "2.8.0":
                if item.window_start - previous.window_start < timedelta(minutes=20):
                    raise RuntimeError("compressed_cycle_start_interval_invalid")
                if item.window_start <= previous.window_end:
                    raise RuntimeError("compressed_cycle_window_overlap")
            binding = item.predecessor
            if schema_version == "2.8.0" and position >= 3:
                if binding is not None:
                    raise RuntimeError("compressed_final_only_predecessor_forbidden")
            elif binding is None or binding.cycle_id != previous.cycle_id:
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
    elif schema_version == "2.6.0":
        if tuple(item.activation for item in cycles) != (
            "IMMUTABLE_EXECUTED",
            "IMMUTABLE_EXECUTED",
            "ACTIVE",
            "ACTIVE",
            "PROVISIONAL_R1_GATED",
            "PROVISIONAL_R1_GATED",
        ):
            raise RuntimeError("compressed_cycle_activation_invalid")
    elif schema_version == "2.7.0":
        if tuple(item.activation for item in cycles) != (
            "IMMUTABLE_EXECUTED",
            "IMMUTABLE_EXECUTED",
            "IMMUTABLE_EXECUTED",
            "IMMUTABLE_EXECUTED",
            "ACTIVE",
            "ACTIVE",
        ):
            raise RuntimeError("compressed_cycle_activation_invalid")
    elif schema_version == "2.8.0":
        if tuple(item.activation for item in cycles) != (
            "IMMUTABLE_EXECUTED",
            "IMMUTABLE_EXECUTED",
            "HISTORICAL_ATTEMPTS_PRESERVED",
            "RETIRED_TIMEBOX",
            "RETIRED_TIMEBOX",
            "ACTIVE",
        ):
            raise RuntimeError("compressed_cycle_activation_invalid")
        if supersession is None:
            raise RuntimeError("compressed_final_only_supersession_invalid")
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
    if schema_version in {"2.6.0", "2.7.0", "2.8.0"}:
        if cycles[2].epoch_label != PLAN9_RETRY_EPOCH_LABEL:
            raise RuntimeError("compressed_retry_epoch_invalid")
        if cycles[3].epoch_label != PLAN9_C4_EPOCH_LABEL:
            raise RuntimeError("compressed_active_epoch_invalid")
    elif cycles[2].epoch_label == PLAN9_RETRY_EPOCH_LABEL:
        raise RuntimeError("compressed_retry_schema_invalid")
    if schema_version == "2.7.0":
        _require_plan10_external_predecessor(cycles[3], cycles[2])
        _require_plan10_external_predecessor(cycles[4], cycles[3])
        if cycles[4].epoch_label != PLAN10_C5_EPOCH_LABEL:
            raise RuntimeError("compressed_plan10_c5_epoch_invalid")
        if cycles[5].epoch_label != PLAN10_C6_EPOCH_LABEL:
            raise RuntimeError("compressed_plan10_c6_epoch_invalid")
        c6_predecessor = cycles[5].predecessor
        if (
            c6_predecessor is None
            or c6_predecessor.binding != "CURRENT_PLAN"
            or c6_predecessor.cycle_id != "c5"
        ):
            raise RuntimeError("compressed_plan10_c6_predecessor_invalid")
        c6 = cycles[5]
        if (
            c6.execution_timeout_seconds,
            c6.write_timeout_seconds,
            c6.agent_timeout_seconds,
        ) != PLAN10_C6_PHASE_TIMEOUTS:
            raise RuntimeError("compressed_plan10_c6_phase_timeout_invalid")
        if c6.window_end - c6.window_start != PLAN10_C6_WINDOW_DURATION:
            raise RuntimeError("compressed_plan10_c6_window_duration_invalid")
    elif schema_version == "2.8.0":
        c6 = cycles[5]
        if c6.epoch_label != PLAN10_C6_EPOCH_LABEL:
            raise RuntimeError("compressed_final_only_epoch_invalid")
        if (
            c6.execution_timeout_seconds,
            c6.write_timeout_seconds,
            c6.agent_timeout_seconds,
        ) != PLAN10_C6_PHASE_TIMEOUTS:
            raise RuntimeError("compressed_plan10_c6_phase_timeout_invalid")
        if c6.window_end - c6.window_start != PLAN10_C6_WINDOW_DURATION:
            raise RuntimeError("compressed_plan10_c6_window_duration_invalid")
        if c6.runs_predicted != 456 or c6.execution_profile != "FULL_AUDIT_V1":
            raise RuntimeError("compressed_final_only_scope_invalid")
    elif any(
        item.predecessor is None or item.predecessor.binding != "CURRENT_PLAN"
        for item in cycles[3:]
    ):
        raise RuntimeError("compressed_current_predecessor_invalid")

    # PASS qualification is end-to-end write plus exact readback <=2 s/case.
    # Freeze the worst-case review gaps, not merely nominal trigger spacing.
    for current, successor in zip(cycles[2:5], cycles[3:6], strict=True):
        if schema_version == "2.8.0":
            break
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


def _require_plan10_external_predecessor(
    successor: CompressedCycle,
    predecessor: CompressedCycle,
) -> None:
    binding = successor.predecessor
    error = f"compressed_plan10_{successor.cycle_id}_predecessor_invalid"
    expected_prefix = (
        f"dev_recall_m2_compressed_p{PLAN9_HISTORICAL_SHA256[:12]}_"
        f"{predecessor.cycle_id}_{predecessor.cohort_due_date:%Y%m%d}_"
    )
    if (
        binding is None
        or binding.binding != "EXTERNAL_PLAN"
        or binding.cycle_id != predecessor.cycle_id
        or binding.plan_sha256 != PLAN9_HISTORICAL_SHA256
        or binding.collection_prefix != expected_prefix
        or not _canonical_uuid(binding.manifest_artifact_id)
        or not _canonical_uuid(binding.mode_receipt_artifact_id)
    ):
        raise RuntimeError(error)


def _canonical_uuid(value: str | None) -> bool:
    if value is None:
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


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
        or manifest.schema_version
        not in {"3.0.0", "3.1.0", "3.2.0", "3.3.0", "3.4.0"}
        or payload.plan_version != plan.version
        or payload.plan_sha256 != plan.sha256
        or payload.schedule_mode != plan.schedule_mode
        or current != expected
        or len(compressed_rows) != cycle.cycle_index
        or payload.execution_history[1]["failure_receipt_id"]
        != expected_legacy_failure_receipt_id
    ):
        raise RuntimeError("compressed_manifest_plan_mismatch")
    to_wire = getattr(manifest, "to_wire", None)
    manifest_warnings = to_wire()["warnings"] if callable(to_wire) else []
    owner_release = (
        manifest.schema_version == "3.4.0"
        and manifest_warnings == list(final_only_owner_release_warnings())
    )
    if manifest.schema_version in {"3.3.0", "3.4.0"}:
        _verify_deadline_policy_against_cycle(
            payload.deadline_policy, cycle, owner_release=owner_release
        )
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
    effective_start = (
        _parse_timestamp(payload.deadline_policy["trigger_started_at"])
        if owner_release
        else cycle.window_start
    )
    end_to_end_deadline = effective_start + timedelta(
        seconds=cycle.execution_timeout_seconds
    )
    if completed_at < effective_start or (
        completed_at > end_to_end_deadline
        and manifest.status.value != "INCOMPLETE"
    ):
        raise RuntimeError("compressed_manifest_completion_timeout")
    if manifest.schema_version == "3.4.0":
        _verify_final_only_manifest_against_plan(manifest, plan)
        return
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


def _verify_final_only_manifest_against_plan(
    manifest: Any,
    plan: CompressedPlan,
) -> None:
    if plan.schema_version != "2.8.0" or plan.supersession is None:
        raise RuntimeError("compressed_final_only_manifest_plan_mismatch")
    payload = manifest.payload
    supersession = payload.final_only_supersession
    observed_history = tuple(
        (
            item["cycle_id"],
            item["evidence_role"],
            item["execution_status"],
            item["plan_sha256"],
            item["collection_prefix"],
            item["manifest_artifact_id"],
            item["manifest_content_hash"],
            item["mode_receipt_artifact_id"],
            item["mode_receipt_content_hash"],
        )
        for item in supersession["historical_evidence"]
    )
    expected_history = tuple(
        (
            item.cycle_id,
            item.evidence_role,
            item.execution_status,
            item.plan_sha256,
            item.collection_prefix,
            item.manifest_artifact_id,
            item.manifest_content_hash,
            item.mode_receipt_artifact_id,
            item.mode_receipt_content_hash,
        )
        for item in plan.supersession.historical_evidence
    )
    observed_retired = tuple(
        (
            item["cycle_id"],
            item["state"],
            item["execution_status"],
            item["runs_created"],
        )
        for item in supersession["retired_cycles"]
    )
    expected_retired = tuple(
        (item.cycle_id, item.state, item.execution_status, item.runs_created)
        for item in plan.supersession.retired_cycles
    )
    expected_ids = tuple(
        artifact_id
        for item in plan.supersession.historical_evidence
        for artifact_id in (
            item.manifest_artifact_id,
            item.mode_receipt_artifact_id,
        )
        if artifact_id is not None
    )
    current_status = (
        "COMPLETE" if manifest.status.value == "VALID" else "INCOMPLETE"
    )
    expected_rows = []
    for cycle_id in ("c4", "c5"):
        cycle = plan.by_id(cycle_id)
        expected_rows.append(
            (
                cycle.cycle_id,
                cycle.cycle_index,
                cycle.cohort_due_date.isoformat(),
                0,
                0,
                cycle.schedule_epoch,
                _timestamp(cycle.window_end),
                cycle.schedule_epoch,
                TRIGGER_CODE,
                "OwnerSupersession/1.0.0",
                "RETIRED_TIMEBOX",
                None,
                "OWNER_DECISION",
                None,
                plan.schedule_mode,
            )
        )
    c6 = plan.by_id("c6")
    expected_rows.append(
        (
            c6.cycle_id,
            c6.cycle_index,
            c6.cohort_due_date.isoformat(),
            len(payload.delta["authoritative_run_ids"]),
            c6.runs_predicted,
            c6.schedule_epoch,
            _timestamp(c6.window_end),
            c6.schedule_epoch,
            TRIGGER_CODE,
            "CohortDayManifest/3.4.0",
            current_status,
            manifest.created_at,
            "LIVE_INFRASTRUCTURE_SYNTHETIC_DATA",
            None,
            plan.schedule_mode,
        )
    )
    observed_rows = [
        (
            row["cycle_id"],
            row["cycle_index"],
            row["cohort_due_date"],
            row["runs_created"],
            row["runs_predicted"],
            row["window_start"],
            row["window_end"],
            row["scheduled_for"],
            row["trigger_code"],
            row["source_schema_version"],
            row["execution_status"],
            row["executed_at"],
            row["evidence_state"],
            row["failure_receipt_id"],
            row["schedule_mode"],
        )
        for row in payload.execution_history[-3:]
    ]
    if (
        supersession["mode"] != plan.supersession.mode
        or supersession["superseded_plan_sha256"]
        != plan.supersession.superseded_plan_sha256
        or supersession["owner_decision"] != plan.supersession.owner_decision
        or supersession["reason_code"] != plan.supersession.reason_code
        or observed_history != expected_history
        or observed_retired != expected_retired
        or tuple(supersession["verified_artifact_ids"]) != expected_ids
        or observed_rows != expected_rows
        or not set(expected_ids).issubset(set(manifest.input_artifact_ids))
        or payload.previous_manifest_id is not None
        or payload.ramp_gate_receipt_id is not None
        or payload.headroom_receipt_id is not None
    ):
        raise RuntimeError("compressed_final_only_manifest_plan_mismatch")


def _verify_deadline_policy_against_cycle(
    deadline: Any,
    cycle: CompressedCycle,
    *,
    owner_release: bool = False,
) -> None:
    trigger_started_at = _parse_timestamp(deadline["trigger_started_at"])
    write_completed_at = _parse_timestamp(deadline["write_completed_at"])
    end_to_end_deadline = (
        trigger_started_at + timedelta(seconds=cycle.execution_timeout_seconds)
        if owner_release
        else cycle.end_to_end_deadline
    )
    expected = (
        cycle.execution_timeout_seconds,
        cycle.write_timeout_seconds,
        cycle.agent_timeout_seconds,
        _timestamp(trigger_started_at if owner_release else cycle.window_end),
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
