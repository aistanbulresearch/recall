"""Submit one final owner-release execution without waiting for its terminal state.

The initiating client is deliberately not an execution receipt.  This module
separates a bounded, submit-once request from a repeatable, read-only
reconciliation pass.  A local O_EXCL intent receipt and an execution-only
marker make an unknown submit outcome fail closed: the caller reconciles the
same attempt and never sends a second execute request.

This coordinator is intentionally independent of the deployed image source.
The receipt binds both identities, so a coordinator-only safety fix never
silently claims that the image was rebuilt from that coordinator commit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any, Mapping, Sequence


sys.path.insert(0, str(Path(__file__).resolve().parent))

from repoint_cohort_job import (  # noqa: E402
    JOB,
    REGION,
    _run_redacted,
    check as check_deployment,
    observed as observe_deployment,
)
from gcloud_redacted import resolve_project  # noqa: E402


OWNER_RELEASE_TOKEN = "FINAL_ONLY_LATE_MANUAL_RELEASE_V1"
OWNER_RELEASE_REASON = "OWNER_AUTHORIZED_FINAL_TONIGHT"
OWNER_RECOVERY_REASON = "RECOVER_CANCELLED_FINAL_EXECUTION_APPEND_ONLY"
INTENT_ENV = "RECALL_FINAL_OWNER_RELEASE_INTENT_SHA256"
OWNER_RETRY_ENV = "RECALL_FINAL_OWNER_RELEASE_MAX_RETRIES"
CONCURRENCY_ENV = "FULL_AUDIT_CONCURRENCY"
SUBMIT_TIMEOUT_SECONDS = 180
READ_TIMEOUT_SECONDS = 180
RECEIPT_SCHEMA = "FinalOwnerReleaseIntent/1.0.0"
CANONICAL_RECEIPT_ROOT = Path.home() / ".recall" / "final-owner-release-intents"
REPO_ROOT = Path(__file__).resolve().parents[2]
TRIGGER_RELATIVE_PATH = "infra/scripts/final_owner_release_trigger.py"
LOCAL_GIT_TIMEOUT_SECONDS = 30

ATTEMPT_ID = re.compile(r"^[a-z0-9]{8,32}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,61}[a-z0-9]$")
EXECUTION = re.compile(r"^recall-cohort-daily-[a-z0-9-]+$")


class _StoreOnce(argparse.Action):
    """Reject repeated authority inputs instead of accepting last-value-wins."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        if getattr(namespace, self.dest, None) is not None:
            parser.error(f"{option_string or self.dest}_duplicate")
        setattr(namespace, self.dest, values)


def _canonical_hash(value: object) -> str:
    wire = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(wire).hexdigest()


def current_trigger_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class FinalLaunchIdentity:
    owner_start_attempt_id: str
    deployed_source_commit: str
    deployed_source_tree: str
    deployed_image_digest: str
    plan_sha256: str
    bundle_sha256: str
    expected_project_sha256: str
    expected_generation: int
    coordinator_commit: str
    coordinator_tree: str
    coordinator_trigger_sha256: str
    recovery_attempt_id: str
    owner_recovery_reason: str
    recovery_previous_execution_id: str
    recovery_previous_source_commit: str
    recovery_previous_image_digest: str
    recovery_previous_snapshot_sha256: str
    previous_recovery_attempt_id: str | None
    previous_recovery_receipt_hash: str | None
    recovery_prefix: str
    recovery_receipt_artifact_id: str
    attempt_key: str
    intent_sha256: str

    @classmethod
    def create(
        cls,
        *,
        owner_start_attempt_id: str,
        deployed_source_commit: str,
        deployed_source_tree: str,
        deployed_image_digest: str,
        plan_sha256: str,
        bundle_sha256: str,
        expected_project_sha256: str,
        expected_generation: int,
        coordinator_commit: str,
        coordinator_tree: str,
        coordinator_trigger_sha256: str,
        recovery_attempt_id: str,
        owner_recovery_reason: str,
        recovery_previous_execution_id: str,
        recovery_previous_source_commit: str,
        recovery_previous_image_digest: str,
        recovery_previous_snapshot_sha256: str,
        previous_recovery_attempt_id: str | None = None,
        previous_recovery_receipt_hash: str | None = None,
    ) -> "FinalLaunchIdentity":
        if ATTEMPT_ID.fullmatch(owner_start_attempt_id) is None:
            raise ValueError("owner_start_attempt_id_invalid")
        for name, value in (
            ("deployed_source_commit", deployed_source_commit),
            ("deployed_source_tree", deployed_source_tree),
            ("coordinator_commit", coordinator_commit),
            ("coordinator_tree", coordinator_tree),
        ):
            if HEX40.fullmatch(value) is None:
                raise ValueError(f"{name}_invalid")
        if DIGEST.fullmatch(deployed_image_digest) is None:
            raise ValueError("deployed_image_digest_invalid")
        for name, value in (
            ("plan_sha256", plan_sha256),
            ("bundle_sha256", bundle_sha256),
            ("expected_project_sha256", expected_project_sha256),
            ("coordinator_trigger_sha256", coordinator_trigger_sha256),
        ):
            if HEX64.fullmatch(value) is None:
                raise ValueError(f"{name}_invalid")
        if expected_generation < 1:
            raise ValueError("expected_generation_invalid")
        if coordinator_trigger_sha256 != current_trigger_sha256():
            raise ValueError("coordinator_trigger_sha256_mismatch")
        try:
            recovery_uuid = uuid.UUID(recovery_attempt_id)
        except (AttributeError, TypeError, ValueError):
            raise ValueError("recovery_attempt_id_invalid") from None
        if str(recovery_uuid) != recovery_attempt_id:
            raise ValueError("recovery_attempt_id_invalid")
        if owner_recovery_reason != OWNER_RECOVERY_REASON:
            raise ValueError("owner_recovery_reason_mismatch")
        if EXECUTION.fullmatch(recovery_previous_execution_id) is None:
            raise ValueError("recovery_previous_execution_id_invalid")
        if HEX40.fullmatch(recovery_previous_source_commit) is None:
            raise ValueError("recovery_previous_source_commit_invalid")
        if DIGEST.fullmatch(recovery_previous_image_digest) is None:
            raise ValueError("recovery_previous_image_digest_invalid")
        if HEX64.fullmatch(recovery_previous_snapshot_sha256) is None:
            raise ValueError("recovery_previous_snapshot_sha256_invalid")
        if (previous_recovery_attempt_id is None) != (
            previous_recovery_receipt_hash is None
        ):
            raise ValueError("previous_recovery_pair_invalid")
        if previous_recovery_attempt_id is not None:
            try:
                previous_recovery_uuid = uuid.UUID(previous_recovery_attempt_id)
            except (AttributeError, TypeError, ValueError):
                raise ValueError("previous_recovery_attempt_id_invalid") from None
            if str(previous_recovery_uuid) != previous_recovery_attempt_id:
                raise ValueError("previous_recovery_attempt_id_invalid")
            if previous_recovery_attempt_id == recovery_attempt_id:
                raise ValueError("previous_recovery_attempt_id_reused")
            if (
                previous_recovery_receipt_hash is None
                or HEX64.fullmatch(previous_recovery_receipt_hash) is None
            ):
                raise ValueError("previous_recovery_receipt_hash_invalid")
        recovery_prefix = (
            f"dev_recall_final_p{plan_sha256[:8]}_c6_r"
            f"{hashlib.sha256(recovery_attempt_id.encode('ascii')).hexdigest()[:10]}_"
        )
        recovery_receipt_artifact_id = str(
            uuid.uuid5(recovery_uuid, "final-execution-recovery-receipt")
        )
        recovery_identity = {
            "recovery_attempt_id": recovery_attempt_id,
            "owner_recovery_reason": owner_recovery_reason,
            "recovery_previous_execution_id": recovery_previous_execution_id,
            "recovery_previous_source_commit": recovery_previous_source_commit,
            "recovery_previous_image_digest": recovery_previous_image_digest,
            "recovery_previous_snapshot_sha256": recovery_previous_snapshot_sha256,
            "recovery_prefix": recovery_prefix,
            "recovery_receipt_artifact_id": recovery_receipt_artifact_id,
        }
        if previous_recovery_attempt_id is not None:
            recovery_identity.update(
                {
                    "previous_recovery_attempt_id": previous_recovery_attempt_id,
                    "previous_recovery_receipt_hash": previous_recovery_receipt_hash,
                }
            )
        attempt_identity = {
            "owner_start_attempt_id": owner_start_attempt_id,
            "deployed_source_commit": deployed_source_commit,
            "deployed_source_tree": deployed_source_tree,
            "deployed_image_digest": deployed_image_digest,
            "plan_sha256": plan_sha256,
            "bundle_sha256": bundle_sha256,
            **recovery_identity,
        }
        identity = {
            **attempt_identity,
            "expected_project_sha256": expected_project_sha256,
            "expected_generation": expected_generation,
            "coordinator_commit": coordinator_commit,
            "coordinator_tree": coordinator_tree,
            "coordinator_trigger_sha256": coordinator_trigger_sha256,
            **recovery_identity,
        }
        identity["previous_recovery_attempt_id"] = previous_recovery_attempt_id
        identity["previous_recovery_receipt_hash"] = previous_recovery_receipt_hash
        attempt_key = _canonical_hash(attempt_identity)
        intent_sha256 = hashlib.sha256(
            f"recall:final-owner-release:{attempt_key}".encode("ascii")
        ).hexdigest()
        return cls(
            **identity,
            attempt_key=attempt_key,
            intent_sha256=intent_sha256,
        )


def receipt_path(identity: FinalLaunchIdentity) -> Path:
    """Return the only permitted receipt path for an attempt identity."""

    return CANONICAL_RECEIPT_ROOT / f"final-owner-release-{identity.attempt_key}.json"


def execution_alias(execution_name: str) -> str:
    if EXECUTION.fullmatch(execution_name) is None:
        raise ValueError("execution_name_invalid")
    return hashlib.sha256(execution_name.encode("ascii")).hexdigest()[:16]


def _attempt_alias(identity: FinalLaunchIdentity) -> str:
    return identity.attempt_key[:16]


def _expected_env(identity: FinalLaunchIdentity) -> dict[str, str]:
    return {
        "RECALL_PROVIDER_RPM": "8",
        "RECALL_SOURCE_COMMIT": identity.deployed_source_commit,
        "RECALL_SOURCE_TREE": identity.deployed_source_tree,
        "RECALL_IMAGE_DIGEST": identity.deployed_image_digest,
        "RECALL_COMPRESSED_PREPARATION_SHA256": identity.bundle_sha256,
        "RECALL_EXPECTED_PROJECT_SHA256": identity.expected_project_sha256,
        "RECALL_SCHEDULER_MODE": "COMPRESSED_V3",
    }


def _nested(value: Mapping[str, Any], *paths: Sequence[str]) -> Any:
    for path in paths:
        current: Any = value
        for key in path:
            if not isinstance(current, Mapping) or key not in current:
                break
            current = current[key]
        else:
            return current
    return None


def _container(value: Mapping[str, Any]) -> Mapping[str, Any]:
    candidates = _nested(
        value,
        ("spec", "template", "spec", "template", "spec", "containers"),
        ("spec", "template", "spec", "containers"),
        ("template", "template", "containers"),
        ("template", "containers"),
    )
    if isinstance(candidates, list) and len(candidates) == 1:
        candidate = candidates[0]
        if isinstance(candidate, Mapping):
            return candidate
    return {}


def _literal_env(container: Mapping[str, Any]) -> tuple[dict[str, str], set[str]]:
    rows = container.get("env", [])
    if not isinstance(rows, list):
        return {}, {"env_contract_invalid"}
    values: dict[str, str] = {}
    failures: set[str] = set()
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            failures.add("env_contract_invalid")
            continue
        name = row.get("name")
        if not isinstance(name, str) or not name:
            failures.add("env_contract_invalid")
            continue
        if name in seen:
            failures.add(f"env_duplicate:{name}")
            continue
        seen.add(name)
        if set(row) == {"name", "value"} and isinstance(row.get("value"), str):
            values[name] = str(row["value"])
    return values, failures


def validate_job_snapshot(
    job: Mapping[str, Any], identity: FinalLaunchIdentity, project: str
) -> tuple[str, ...]:
    """Run the accepted deployment checks plus final-only launch assertions."""

    failures: set[str] = set()
    try:
        state = observe_deployment(dict(job), project)
        checked = check_deployment(
            state, identity.deployed_image_digest, _expected_env(identity)
        )
        failures.update(str(item) for item in checked.get("failures", []))
        if state.get("generation") != identity.expected_generation:
            failures.add("generation_mismatch")
        if state.get("observedGeneration") != identity.expected_generation:
            failures.add("observed_generation_mismatch")
    except SystemExit as exc:
        failures.add(str(exc.code) if exc.code else "job_contract_invalid")

    env, env_failures = _literal_env(_container(job))
    failures.update(env_failures)
    for name, expected, code in (
        (CONCURRENCY_ENV, "2", "concurrency"),
        (OWNER_RETRY_ENV, "0", "owner_release_max_retries"),
    ):
        if name not in env:
            failures.add(f"{code}_missing")
        elif env[name] != expected:
            failures.add(f"{code}_mismatch")
    return tuple(sorted(failures))


def build_execute_args(identity: FinalLaunchIdentity, project: str) -> list[str]:
    """Build the immutable one-shot command; no caller-supplied args are accepted."""

    runtime_args = (
        "--args=--owner-release-token,"
        f"{OWNER_RELEASE_TOKEN},--owner-release-reason,{OWNER_RELEASE_REASON},"
        f"--recovery-attempt-id,{identity.recovery_attempt_id},"
        f"--owner-recovery-reason,{identity.owner_recovery_reason},"
        "--recovery-previous-execution-id,"
        f"{identity.recovery_previous_execution_id},"
        "--recovery-previous-source-commit,"
        f"{identity.recovery_previous_source_commit},"
        "--recovery-previous-image-digest,"
        f"{identity.recovery_previous_image_digest},"
        "--recovery-previous-snapshot-sha256,"
        f"{identity.recovery_previous_snapshot_sha256}"
    )
    if identity.previous_recovery_attempt_id is not None:
        runtime_args += (
            ",--previous-recovery-attempt-id,"
            f"{identity.previous_recovery_attempt_id},"
            "--previous-recovery-receipt-hash,"
            f"{identity.previous_recovery_receipt_hash}"
        )
    return [
        "run",
        "jobs",
        "execute",
        JOB,
        f"--region={REGION}",
        f"--project={project}",
        runtime_args,
        (
            "--update-env-vars="
            f"{INTENT_ENV}={identity.intent_sha256},{OWNER_RETRY_ENV}=0"
        ),
        "--tasks=1",
        "--task-timeout=28800s",
        "--async",
        "--format=json",
    ]


def _list_args(project: str) -> tuple[str, ...]:
    return (
        "run",
        "jobs",
        "executions",
        "list",
        f"--job={JOB}",
        f"--region={REGION}",
        f"--project={project}",
        "--limit=1000",
        "--format=json",
    )


def _run_local_git(*args: str) -> CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        timeout=LOCAL_GIT_TIMEOUT_SECONDS,
        check=False,
    )


def verify_coordinator_checkout(
    identity: FinalLaunchIdentity, *, run_fn: Any = _run_local_git
) -> tuple[str, ...]:
    """Bind the launcher bytes to the claimed clean coordinator commit/tree."""

    failures: set[str] = set()
    commands = {
        "head": ("rev-parse", "HEAD"),
        "tree": ("rev-parse", "HEAD^{tree}"),
        "status": ("status", "--porcelain=v1", "--untracked-files=all"),
        "head_blob": ("rev-parse", f"HEAD:{TRIGGER_RELATIVE_PATH}"),
        "worktree_blob": (
            "hash-object",
            f"--path={TRIGGER_RELATIVE_PATH}",
            str(REPO_ROOT / TRIGGER_RELATIVE_PATH),
        ),
    }
    results: dict[str, str] = {}
    for name, command in commands.items():
        try:
            result = run_fn(*command)
        except (OSError, subprocess.TimeoutExpired):
            failures.add(f"coordinator_git_{name}_unavailable")
            continue
        if result.returncode != 0:
            failures.add(f"coordinator_git_{name}_failed")
            continue
        results[name] = result.stdout.strip()
    if results.get("head") != identity.coordinator_commit:
        failures.add("coordinator_head_mismatch")
    if results.get("tree") != identity.coordinator_tree:
        failures.add("coordinator_tree_mismatch")
    if results.get("status") != "":
        failures.add("coordinator_checkout_dirty")
    if not results.get("head_blob") or results.get("head_blob") != results.get(
        "worktree_blob"
    ):
        failures.add("coordinator_trigger_blob_mismatch")
    return tuple(sorted(failures))


def _parse_json_result(
    result: CompletedProcess[str], *, failure_code: str
) -> object:
    if result.returncode != 0:
        raise RuntimeError(f"{failure_code}:{result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"{failure_code}_json_invalid") from None


def _execution_name(value: Mapping[str, Any]) -> str | None:
    name = _nested(value, ("metadata", "name"), ("name",))
    if not isinstance(name, str):
        return None
    short = name.rsplit("/", 1)[-1]
    return short if EXECUTION.fullmatch(short) else None


def _execution_marker(value: Mapping[str, Any]) -> str | None:
    env, _failures = _literal_env(_container(value))
    marker = env.get(INTENT_ENV)
    return marker if marker is not None and HEX64.fullmatch(marker) else None


def _parse_execution_list(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise RuntimeError("execution_list_contract_invalid")
    result: list[Mapping[str, Any]] = []
    for item in value:
        if _execution_name(item) is None:
            raise RuntimeError("execution_list_contract_invalid")
        result.append(item)
    return result


def _receipt_wire(
    identity: FinalLaunchIdentity,
    *,
    baseline_aliases: Sequence[str],
    created_at_utc: str,
) -> dict[str, object]:
    if any(re.fullmatch(r"^[0-9a-f]{16}$", item) is None for item in baseline_aliases):
        raise ValueError("baseline_alias_invalid")
    return {
        "schema": RECEIPT_SCHEMA,
        "receipt_state": "LOCAL_INTENT_ONLY",
        "created_at_utc": created_at_utc,
        "attempt_key": identity.attempt_key,
        "intent_sha256": identity.intent_sha256,
        "owner_start_attempt_id": identity.owner_start_attempt_id,
        "expected_generation": identity.expected_generation,
        "deployed": {
            "source_commit": identity.deployed_source_commit,
            "source_tree": identity.deployed_source_tree,
            "image_digest": identity.deployed_image_digest,
            "plan_sha256": identity.plan_sha256,
            "bundle_sha256": identity.bundle_sha256,
            "expected_project_sha256": identity.expected_project_sha256,
        },
        "coordinator": {
            "source_commit": identity.coordinator_commit,
            "source_tree": identity.coordinator_tree,
            "trigger_sha256": identity.coordinator_trigger_sha256,
        },
        "recovery": {
            "attempt_id": identity.recovery_attempt_id,
            "owner_reason": identity.owner_recovery_reason,
            "previous_execution_id": identity.recovery_previous_execution_id,
            "previous_source_commit": identity.recovery_previous_source_commit,
            "previous_image_digest": identity.recovery_previous_image_digest,
            "previous_snapshot_sha256": identity.recovery_previous_snapshot_sha256,
            "derived_prefix": identity.recovery_prefix,
            "receipt_artifact_id": identity.recovery_receipt_artifact_id,
            **(
                {}
                if identity.previous_recovery_attempt_id is None
                else {
                    "previous_recovery_attempt_id": (
                        identity.previous_recovery_attempt_id
                    ),
                    "previous_recovery_receipt_hash": (
                        identity.previous_recovery_receipt_hash
                    ),
                }
            ),
        },
        "baseline_execution_aliases": sorted(set(baseline_aliases)),
    }


def write_intent_receipt(
    identity: FinalLaunchIdentity,
    *,
    baseline_aliases: Sequence[str],
    now_fn: Any = lambda: datetime.now(timezone.utc),
) -> Path:
    """Durably create the canonical receipt using O_EXCL semantics."""

    CANONICAL_RECEIPT_ROOT.mkdir(parents=True, exist_ok=True)
    target = receipt_path(identity)
    observed_now = now_fn()
    if not isinstance(observed_now, datetime) or observed_now.tzinfo is None:
        raise ValueError("receipt_clock_invalid")
    created_at_utc = observed_now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    wire = _receipt_wire(
        identity,
        baseline_aliases=baseline_aliases,
        created_at_utc=created_at_utc,
    )
    with target.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(wire, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return target


def _read_intent_receipt(identity: FinalLaunchIdentity) -> dict[str, object] | None:
    target = receipt_path(identity)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        created_at_utc = value.get("created_at_utc") if isinstance(value, Mapping) else None
        if not isinstance(created_at_utc, str) or not created_at_utc.endswith("Z"):
            return None
        datetime.fromisoformat(created_at_utc[:-1] + "+00:00")
        expected = _receipt_wire(
            identity,
            baseline_aliases=(
                value.get("baseline_execution_aliases", ())
                if isinstance(value, Mapping)
                else ()
            ),
            created_at_utc=created_at_utc,
        )
    except (TypeError, ValueError):
        return None
    return dict(value) if value == expected else None


def _safe_failure(identity: FinalLaunchIdentity, *codes: str) -> dict[str, object]:
    return {
        "verdict": "FAIL",
        "attempt_alias": _attempt_alias(identity),
        "execute_count": 0,
        "codes": list(codes),
    }


def submit_once(
    identity: FinalLaunchIdentity,
    *,
    project: str,
    run_fn: Any = _run_redacted,
) -> dict[str, object]:
    """Preflight and send exactly one async execute request, never a retry."""

    if PROJECT.fullmatch(project) is None:
        raise ValueError("project_invalid")
    if hashlib.sha256(project.encode("utf-8")).hexdigest() != (
        identity.expected_project_sha256
    ):
        return _safe_failure(identity, "project_hash_mismatch")
    coordinator_failures = verify_coordinator_checkout(identity)
    if coordinator_failures:
        return _safe_failure(identity, *coordinator_failures)
    target = receipt_path(identity)
    if target.exists():
        return _safe_failure(identity, "attempt_receipt_exists")

    described: CompletedProcess[str] = run_fn(
        "run",
        "jobs",
        "describe",
        JOB,
        f"--region={REGION}",
        f"--project={project}",
        "--format=json",
        timeout_seconds=READ_TIMEOUT_SECONDS,
    )
    try:
        job = _parse_json_result(described, failure_code="job_describe_failed")
    except RuntimeError as exc:
        return _safe_failure(identity, str(exc))
    if not isinstance(job, Mapping):
        return _safe_failure(identity, "job_describe_contract_invalid")
    failures = validate_job_snapshot(job, identity, project)
    if failures:
        return _safe_failure(identity, *failures)

    listed: CompletedProcess[str] = run_fn(
        *_list_args(project), timeout_seconds=READ_TIMEOUT_SECONDS
    )
    try:
        executions = _parse_execution_list(
            _parse_json_result(listed, failure_code="execution_list_failed")
        )
    except RuntimeError as exc:
        return _safe_failure(identity, str(exc))
    if any(_execution_marker(item) == identity.intent_sha256 for item in executions):
        return _safe_failure(identity, "intent_marker_already_present")
    baseline_aliases = tuple(
        execution_alias(name)
        for item in executions
        if (name := _execution_name(item)) is not None
    )
    try:
        write_intent_receipt(
            identity, baseline_aliases=baseline_aliases
        )
    except FileExistsError:
        return _safe_failure(identity, "attempt_receipt_exists")

    submitted: CompletedProcess[str] = run_fn(
        *build_execute_args(identity, project), timeout_seconds=SUBMIT_TIMEOUT_SECONDS
    )
    common = {
        "attempt_alias": _attempt_alias(identity),
        "execute_count": 1,
        "receipt_state": "LOCAL_INTENT_ONLY",
    }
    if submitted.returncode != 0:
        return {
            "verdict": "OUTCOME_UNKNOWN",
            **common,
            "submit_exit_code": int(submitted.returncode),
            "next_step": "STOP_AND_RECONCILE",
        }
    return {"verdict": "SUBMIT_ACCEPTED_NOT_RECONCILED", **common}


def _creator_class(execution: Mapping[str, Any]) -> str:
    creator = _nested(
        execution,
        ("metadata", "annotations", "run.googleapis.com/creator"),
        ("metadata", "labels", "run.googleapis.com/creator"),
        ("creator",),
    )
    if not isinstance(creator, str) or not creator:
        return "UNKNOWN"
    lowered = creator.lower()
    if lowered.endswith(".gserviceaccount.com") or lowered.startswith("serviceaccount:"):
        return "MACHINE"
    if creator in {"<account>", "<principal>"}:
        return "CONFIGURED_CALLER_REDACTED"
    if "@" in creator:
        return "HUMAN"
    return "UNKNOWN"


def _execution_state(execution: Mapping[str, Any]) -> str:
    failed_count = _nested(execution, ("status", "failedCount"), ("failedCount",))
    succeeded_count = _nested(
        execution, ("status", "succeededCount"), ("succeededCount",)
    )
    running_count = _nested(
        execution, ("status", "runningCount"), ("runningCount",)
    )
    if not isinstance(failed_count, int):
        failed_count = 0
    if not isinstance(succeeded_count, int):
        succeeded_count = 0
    if not isinstance(running_count, int):
        running_count = 0

    conditions = _nested(execution, ("status", "conditions"), ("conditions",))
    completed_conditions = (
        [
            condition
            for condition in conditions
            if isinstance(condition, Mapping) and condition.get("type") == "Completed"
        ]
        if isinstance(conditions, list)
        else []
    )
    if len(completed_conditions) != 1:
        return "UNKNOWN"

    completed = completed_conditions[0]
    state = str(completed.get("state", "")).strip().upper()
    status = str(completed.get("status", "")).strip().upper()
    reason = str(completed.get("reason", "")).strip().upper()
    message = str(completed.get("message", "")).strip().lower()
    condition_success = state in {"CONDITION_SUCCEEDED", "SUCCEEDED"} or status in {
        "TRUE",
        "CONDITION_SUCCEEDED",
        "SUCCEEDED",
    }
    failure_shaped = state in {"CONDITION_FAILED", "FAILED"} or status in {
        "FALSE",
        "CONDITION_FAILED",
        "FAILED",
    }
    cancelled = reason in {"CANCELLED", "CANCELED"} or re.fullmatch(
        r"(?:the )?execution (?:(?:was|has been) )?(?:cancelled|canceled)"
        r"(?: by (?:the )?(?:user|client))?[.!]?",
        message,
    ) is not None
    condition_failed = state in {"CONDITION_FAILED", "FAILED"} or (
        status in {"FALSE", "CONDITION_FAILED", "FAILED"}
        and ("FAIL" in reason or failed_count > 0 or cancelled)
    )
    if cancelled and not failure_shaped:
        return "CONTRADICTORY" if condition_success or succeeded_count > 0 else "UNKNOWN"
    if failed_count > 0 and not condition_failed:
        return (
            "CONTRADICTORY"
            if condition_success or succeeded_count > 0 or running_count > 0
            else "UNKNOWN"
        )
    if condition_failed:
        return (
            "CONTRADICTORY"
            if condition_success or succeeded_count > 0 or running_count > 0
            else "FAILED"
        )
    if condition_success:
        return (
            "SUCCEEDED"
            if succeeded_count > 0 and running_count == 0
            else "CONTRADICTORY"
        )
    if succeeded_count > 0:
        return "CONTRADICTORY"
    if running_count > 0:
        return "RUNNING"
    return "UNKNOWN"


def _execution_generation(execution: Mapping[str, Any]) -> int | None:
    raw = _nested(
        execution,
        ("metadata", "labels", "run.googleapis.com/jobGeneration"),
        ("metadata", "annotations", "run.googleapis.com/jobGeneration"),
        ("spec", "jobGeneration"),
        ("jobGeneration",),
    )
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


def _execution_binding_failures(
    execution: Mapping[str, Any], identity: FinalLaunchIdentity
) -> tuple[tuple[str, ...], str]:
    failures: set[str] = set()
    container = _container(execution)
    image = container.get("image") if isinstance(container, Mapping) else None
    if not isinstance(image, str) or not image.endswith(
        "@" + identity.deployed_image_digest
    ):
        failures.add("execution_image_digest_mismatch")
    env, env_failures = _literal_env(container)
    failures.update(env_failures)
    required = {
        **_expected_env(identity),
        CONCURRENCY_ENV: "2",
        INTENT_ENV: identity.intent_sha256,
        OWNER_RETRY_ENV: "0",
    }
    for name, expected in required.items():
        if env.get(name) != expected:
            failures.add(f"execution_env_mismatch:{name}")
    expected_args = [
        "--owner-release-token",
        OWNER_RELEASE_TOKEN,
        "--owner-release-reason",
        OWNER_RELEASE_REASON,
        "--recovery-attempt-id",
        identity.recovery_attempt_id,
        "--owner-recovery-reason",
        identity.owner_recovery_reason,
        "--recovery-previous-execution-id",
        identity.recovery_previous_execution_id,
        "--recovery-previous-source-commit",
        identity.recovery_previous_source_commit,
        "--recovery-previous-image-digest",
        identity.recovery_previous_image_digest,
        "--recovery-previous-snapshot-sha256",
        identity.recovery_previous_snapshot_sha256,
    ]
    if identity.previous_recovery_attempt_id is not None:
        expected_args.extend(
            [
                "--previous-recovery-attempt-id",
                identity.previous_recovery_attempt_id,
                "--previous-recovery-receipt-hash",
                identity.previous_recovery_receipt_hash,
            ]
        )
    if container.get("args") != expected_args:
        failures.add("execution_args_mismatch")
    generation = _execution_generation(execution)
    generation_evidence = "NOT_VERIFIED"
    if generation is not None:
        generation_evidence = "VERIFIED"
        if generation != identity.expected_generation:
            failures.add("execution_generation_mismatch")
    return tuple(sorted(failures)), generation_evidence


def reconcile(
    identity: FinalLaunchIdentity,
    *,
    project: str,
    run_fn: Any = _run_redacted,
) -> dict[str, object]:
    """Read-only reconcile one intent; this function cannot submit executions."""

    if PROJECT.fullmatch(project) is None:
        raise ValueError("project_invalid")
    if hashlib.sha256(project.encode("utf-8")).hexdigest() != (
        identity.expected_project_sha256
    ):
        return {
            "verdict": "FAIL",
            "state": "BLOCKED",
            "attempt_alias": _attempt_alias(identity),
            "codes": ["project_hash_mismatch"],
        }
    coordinator_failures = verify_coordinator_checkout(identity)
    if coordinator_failures:
        return {
            "verdict": "FAIL",
            "state": "BLOCKED",
            "attempt_alias": _attempt_alias(identity),
            "codes": list(coordinator_failures),
        }
    receipt = _read_intent_receipt(identity)
    if receipt is None:
        return {
            "verdict": "FAIL",
            "state": "BLOCKED",
            "attempt_alias": _attempt_alias(identity),
            "codes": ["attempt_receipt_invalid"],
        }
    baseline = set(receipt["baseline_execution_aliases"])
    listed: CompletedProcess[str] = run_fn(
        *_list_args(project), timeout_seconds=READ_TIMEOUT_SECONDS
    )
    try:
        executions = _parse_execution_list(
            _parse_json_result(listed, failure_code="execution_list_failed")
        )
    except RuntimeError as exc:
        return {
            "verdict": "NOT_VERIFIED",
            "state": "READ_FAILED",
            "attempt_alias": _attempt_alias(identity),
            "codes": [str(exc)],
        }
    candidates: list[tuple[str, Mapping[str, Any]]] = []
    for execution in executions:
        name = _execution_name(execution)
        if (
            name is not None
            and _execution_marker(execution) == identity.intent_sha256
            and execution_alias(name) not in baseline
        ):
            candidates.append((name, execution))
    if not candidates:
        return {
            "verdict": "NOT_VERIFIED",
            "state": "PENDING",
            "attempt_alias": _attempt_alias(identity),
            "execution_count": 0,
        }
    if len(candidates) != 1:
        return {
            "verdict": "FAIL",
            "state": "AMBIGUOUS",
            "attempt_alias": _attempt_alias(identity),
            "execution_count": len(candidates),
            "codes": ["multiple_execution_candidates"],
        }

    name, _listed = candidates[0]
    described: CompletedProcess[str] = run_fn(
        "run",
        "jobs",
        "executions",
        "describe",
        name,
        f"--region={REGION}",
        f"--project={project}",
        "--format=json",
        timeout_seconds=READ_TIMEOUT_SECONDS,
    )
    try:
        execution = _parse_json_result(
            described, failure_code="execution_describe_failed"
        )
    except RuntimeError as exc:
        return {
            "verdict": "NOT_VERIFIED",
            "state": "READ_FAILED",
            "attempt_alias": _attempt_alias(identity),
            "execution_count": 1,
            "execution_alias": execution_alias(name),
            "codes": [str(exc)],
        }
    if not isinstance(execution, Mapping) or _execution_name(execution) != name:
        return {
            "verdict": "FAIL",
            "state": "IDENTITY_MISMATCH",
            "attempt_alias": _attempt_alias(identity),
            "execution_count": 1,
            "execution_alias": execution_alias(name),
            "codes": ["execution_describe_identity_mismatch"],
        }
    failures, generation_evidence = _execution_binding_failures(execution, identity)
    if failures:
        return {
            "verdict": "FAIL",
            "state": "BINDING_MISMATCH",
            "attempt_alias": _attempt_alias(identity),
            "execution_count": 1,
            "execution_alias": execution_alias(name),
            "codes": list(failures),
        }
    if generation_evidence != "VERIFIED":
        return {
            "verdict": "NOT_VERIFIED",
            "state": "GENERATION_UNVERIFIED",
            "attempt_alias": _attempt_alias(identity),
            "execution_count": 1,
            "execution_alias": execution_alias(name),
            "creator_class": _creator_class(execution),
            "execution_generation_evidence": generation_evidence,
        }
    state = _execution_state(execution)
    if state == "FAILED":
        return {
            "verdict": "FAIL",
            "state": "TERMINAL_FAILED",
            "attempt_alias": _attempt_alias(identity),
            "execution_count": 1,
            "execution_alias": execution_alias(name),
            "creator_class": _creator_class(execution),
            "execution_generation_evidence": generation_evidence,
        }
    if state in {"UNKNOWN", "CONTRADICTORY"}:
        return {
            "verdict": "NOT_VERIFIED",
            "state": state,
            "attempt_alias": _attempt_alias(identity),
            "execution_count": 1,
            "execution_alias": execution_alias(name),
            "creator_class": _creator_class(execution),
            "execution_generation_evidence": generation_evidence,
        }
    return {
        "verdict": "PASS",
        "state": state,
        "attempt_alias": _attempt_alias(identity),
        "execution_count": 1,
        "execution_alias": execution_alias(name),
        "creator_class": _creator_class(execution),
        "execution_generation_evidence": generation_evidence,
    }


def _identity_from_args(args: argparse.Namespace) -> FinalLaunchIdentity:
    return FinalLaunchIdentity.create(
        owner_start_attempt_id=args.owner_start_attempt_id,
        deployed_source_commit=args.deployed_source_commit,
        deployed_source_tree=args.deployed_source_tree,
        deployed_image_digest=args.deployed_image_digest,
        plan_sha256=args.plan_sha256,
        bundle_sha256=args.bundle_sha256,
        expected_project_sha256=args.expected_project_sha256,
        expected_generation=args.expected_generation,
        coordinator_commit=args.coordinator_commit,
        coordinator_tree=args.coordinator_tree,
        coordinator_trigger_sha256=args.coordinator_trigger_sha256,
        recovery_attempt_id=args.recovery_attempt_id,
        owner_recovery_reason=args.owner_recovery_reason,
        recovery_previous_execution_id=args.recovery_previous_execution_id,
        recovery_previous_source_commit=args.recovery_previous_source_commit,
        recovery_previous_image_digest=args.recovery_previous_image_digest,
        recovery_previous_snapshot_sha256=args.recovery_previous_snapshot_sha256,
        previous_recovery_attempt_id=args.previous_recovery_attempt_id,
        previous_recovery_receipt_hash=args.previous_recovery_receipt_hash,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("submit", "reconcile"))
    parser.add_argument("--owner-start-attempt-id", required=True)
    parser.add_argument("--deployed-source-commit", required=True)
    parser.add_argument("--deployed-source-tree", required=True)
    parser.add_argument("--deployed-image-digest", required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--expected-project-sha256", required=True)
    parser.add_argument("--expected-generation", type=int, required=True)
    parser.add_argument("--coordinator-commit", required=True)
    parser.add_argument("--coordinator-tree", required=True)
    parser.add_argument("--coordinator-trigger-sha256", required=True)
    parser.add_argument("--recovery-attempt-id", required=True)
    parser.add_argument("--owner-recovery-reason", required=True)
    parser.add_argument("--recovery-previous-execution-id", required=True)
    parser.add_argument("--recovery-previous-source-commit", required=True)
    parser.add_argument("--recovery-previous-image-digest", required=True)
    parser.add_argument("--recovery-previous-snapshot-sha256", required=True)
    parser.add_argument("--previous-recovery-attempt-id", action=_StoreOnce)
    parser.add_argument("--previous-recovery-receipt-hash", action=_StoreOnce)
    return parser


def main() -> int:
    args = _parser().parse_args()
    identity = _identity_from_args(args)
    project = resolve_project()
    if args.action == "submit":
        report = submit_once(
            identity,
            project=project,
        )
    else:
        report = reconcile(identity, project=project)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["verdict"] in {"PASS", "SUBMIT_ACCEPTED_NOT_RECONCILED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
