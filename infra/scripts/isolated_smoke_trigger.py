"""Build a fail-closed, source-less Cloud Build request for two smoke executions.

This module only prepares and validates the request.  The caller that submits it
must use ``gcloud_redacted.py`` and must first validate the deployed job snapshot
with :func:`validate_job_snapshot`.  Preparing the request performs no cloud or
Git operation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any, Mapping, Sequence


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from recall.platform.redaction import PROJECT_PLACEHOLDER  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gcloud_redacted import resolve_project  # noqa: E402


JOB = "recall-cohort-daily"
REGION = "us-central1"
SMOKE_NAMESPACE = "dev_recall_smoke_"
SMOKE_ID = re.compile(r"^[a-z0-9]{8,32}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
EXECUTION = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
BUILD_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}$"
)
MACHINE_SERVICE_ACCOUNT = re.compile(
    r"^(?P<local>[a-z][a-z0-9-]{4,29})@"
    r"(?P<project>[a-z][a-z0-9-]{4,61}[a-z0-9])\.iam\.gserviceaccount\.com$"
)
SERVICE_ACCOUNT_LOCAL_PART = re.compile(r"^[a-z][a-z0-9-]{4,29}$")
PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,61}[a-z0-9]$")
REQUIRED_SECRET_ENV = {
    "RECALL_TOOL_CAPABILITY_SECRET_B64",
    "RECALL_NCBI_TOOL",
    "RECALL_NCBI_EMAIL",
}
POSITIVE_CASE_COUNT = 4
POSITIVE_TURN_LIMIT = 24
POSITIVE_INTENT_ENV = "RECALL_POSITIVE_SMOKE_INTENT_SHA256"
POSITIVE_RECEIPT_SCHEMA = "PositiveIsolatedSmokeIntent/1.0.0"
POSITIVE_RECEIPT_ROOT = Path.home() / ".recall" / "positive-smoke-intents"
REPO_ROOT = Path(__file__).resolve().parents[2]
TRIGGER_RELATIVE_PATH = "infra/scripts/isolated_smoke_trigger.py"
READ_TIMEOUT_SECONDS = 180
SUBMIT_TIMEOUT_SECONDS = 180


class _StoreOnce(argparse.Action):
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


def _positive_core_contract() -> tuple[int, int]:
    from recall.scheduler.smoke import (  # noqa: PLC0415
        SMOKE_MODE_CASE_COUNTS,
        SMOKE_MODE_TURN_LIMITS,
    )

    return (
        int(SMOKE_MODE_CASE_COUNTS.get("positive", -1)),
        int(SMOKE_MODE_TURN_LIMITS.get("positive", -1)),
    )


@dataclass(frozen=True, slots=True)
class PositiveSmokeLaunchIdentity:
    smoke_id: str
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
    positive_prefix: str
    case_count: int
    turn_limit: int
    attempt_key: str
    intent_sha256: str

    @classmethod
    def create(
        cls,
        *,
        smoke_id: str,
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
    ) -> "PositiveSmokeLaunchIdentity":
        if _positive_core_contract() != (
            POSITIVE_CASE_COUNT,
            POSITIVE_TURN_LIMIT,
        ):
            raise RuntimeError("positive_smoke_core_contract_mismatch")
        if not SMOKE_ID.fullmatch(smoke_id) or any(
            blocked in smoke_id for blocked in ("final", "c6", "456")
        ):
            raise ValueError("smoke_id_invalid")
        for value, code in (
            (deployed_source_commit, "source_commit_invalid"),
            (deployed_source_tree, "source_tree_invalid"),
            (coordinator_commit, "coordinator_commit_invalid"),
            (coordinator_tree, "coordinator_tree_invalid"),
        ):
            if not HEX40.fullmatch(value):
                raise ValueError(code)
        if not DIGEST.fullmatch(deployed_image_digest):
            raise ValueError("image_digest_invalid")
        for value, code in (
            (plan_sha256, "plan_sha256_invalid"),
            (bundle_sha256, "bundle_sha256_invalid"),
            (expected_project_sha256, "project_sha256_invalid"),
            (coordinator_trigger_sha256, "trigger_sha256_invalid"),
        ):
            if not HEX64.fullmatch(value):
                raise ValueError(code)
        if not isinstance(expected_generation, int) or expected_generation < 1:
            raise ValueError("generation_invalid")
        positive_prefix = (
            f"{SMOKE_NAMESPACE}{deployed_source_commit[:12]}_"
            f"{plan_sha256[:12]}_positive_{smoke_id}_"
        )
        _validate_prefix(positive_prefix)
        attempt_identity = {
            "smoke_id": smoke_id,
            "mode": "positive",
            "deployed_source_commit": deployed_source_commit,
            "deployed_source_tree": deployed_source_tree,
            "deployed_image_digest": deployed_image_digest,
            "plan_sha256": plan_sha256,
            "bundle_sha256": bundle_sha256,
            "expected_project_sha256": expected_project_sha256,
            "expected_generation": expected_generation,
            "coordinator_commit": coordinator_commit,
            "coordinator_tree": coordinator_tree,
            "coordinator_trigger_sha256": coordinator_trigger_sha256,
            "positive_prefix": positive_prefix,
            "case_count": POSITIVE_CASE_COUNT,
            "turn_limit": POSITIVE_TURN_LIMIT,
        }
        attempt_key = _canonical_hash(attempt_identity)
        intent_sha256 = hashlib.sha256(
            f"recall:positive-isolated-smoke:{attempt_key}".encode("ascii")
        ).hexdigest()
        return cls(
            smoke_id=smoke_id,
            deployed_source_commit=deployed_source_commit,
            deployed_source_tree=deployed_source_tree,
            deployed_image_digest=deployed_image_digest,
            plan_sha256=plan_sha256,
            bundle_sha256=bundle_sha256,
            expected_project_sha256=expected_project_sha256,
            expected_generation=expected_generation,
            coordinator_commit=coordinator_commit,
            coordinator_tree=coordinator_tree,
            coordinator_trigger_sha256=coordinator_trigger_sha256,
            positive_prefix=positive_prefix,
            case_count=POSITIVE_CASE_COUNT,
            turn_limit=POSITIVE_TURN_LIMIT,
            attempt_key=attempt_key,
            intent_sha256=intent_sha256,
        )

    def entrypoint_args(self) -> tuple[str, ...]:
        return (
            "--smoke-mode",
            "positive",
            "--smoke-id",
            self.smoke_id,
            "--smoke-prefix",
            self.positive_prefix,
        )

    def to_receipt(self) -> dict[str, object]:
        return {
            "schema": POSITIVE_RECEIPT_SCHEMA,
            "receipt_state": "LOCAL_INTENT_ONLY",
            "attempt_key": self.attempt_key,
            "intent_sha256": self.intent_sha256,
            "smoke_id": self.smoke_id,
            "mode": "positive",
            "positive_prefix": self.positive_prefix,
            "case_count": self.case_count,
            "turn_limit": self.turn_limit,
            "expected_generation": self.expected_generation,
            "deployed": {
                "source_commit": self.deployed_source_commit,
                "source_tree": self.deployed_source_tree,
                "image_digest": self.deployed_image_digest,
                "plan_sha256": self.plan_sha256,
                "bundle_sha256": self.bundle_sha256,
                "expected_project_sha256": self.expected_project_sha256,
            },
            "coordinator": {
                "source_commit": self.coordinator_commit,
                "source_tree": self.coordinator_tree,
                "trigger_sha256": self.coordinator_trigger_sha256,
            },
        }


@dataclass(frozen=True, slots=True)
class SmokePair:
    smoke_id: str
    source_commit: str
    source_tree: str
    plan_sha256: str
    bundle_sha256: str
    image_digest: str
    positive_prefix: str
    negative_prefix: str

    @classmethod
    def create(
        cls,
        *,
        smoke_id: str,
        source_commit: str,
        source_tree: str,
        plan_sha256: str,
        bundle_sha256: str,
        image_digest: str,
    ) -> "SmokePair":
        if not SMOKE_ID.fullmatch(smoke_id) or any(
            blocked in smoke_id for blocked in ("final", "c6", "456")
        ):
            raise ValueError("smoke_id_invalid")
        if not HEX40.fullmatch(source_commit):
            raise ValueError("source_commit_invalid")
        if not HEX40.fullmatch(source_tree):
            raise ValueError("source_tree_invalid")
        if not HEX64.fullmatch(plan_sha256):
            raise ValueError("plan_sha256_invalid")
        if not HEX64.fullmatch(bundle_sha256):
            raise ValueError("bundle_sha256_invalid")
        if not DIGEST.fullmatch(image_digest):
            raise ValueError("image_digest_invalid")
        base = (
            f"{SMOKE_NAMESPACE}{source_commit[:12]}_{plan_sha256[:12]}_"
        )
        positive = f"{base}positive_{smoke_id}_"
        negative = f"{base}negative_{smoke_id}_"
        for prefix in (positive, negative):
            _validate_prefix(prefix)
        return cls(
            smoke_id=smoke_id,
            source_commit=source_commit,
            source_tree=source_tree,
            plan_sha256=plan_sha256,
            bundle_sha256=bundle_sha256,
            image_digest=image_digest,
            positive_prefix=positive,
            negative_prefix=negative,
        )

    def entrypoint_args(self, mode: str) -> tuple[str, ...]:
        if mode not in {"positive", "negative"}:
            raise ValueError("smoke_mode_invalid")
        prefix = self.positive_prefix if mode == "positive" else self.negative_prefix
        return (
            "--smoke-mode",
            mode,
            "--smoke-id",
            self.smoke_id,
            "--smoke-prefix",
            prefix,
        )


@dataclass(frozen=True, slots=True)
class DeploymentExpectation:
    source_commit: str
    source_tree: str
    expected_project_sha256: str
    bundle_sha256: str
    image_digest: str
    expected_service_account: str
    provider_rpm: str = "8"
    concurrency: str = "2"
    timeout_seconds: int = 28_800
    max_retries: int = 0
    task_count: int = 1
    cpu: str = "1"
    memory: str = "512Mi"

    @classmethod
    def from_pair(
        cls, pair: SmokePair, *, project: str
    ) -> "DeploymentExpectation":
        if not PROJECT.fullmatch(project):
            raise ValueError("project_invalid")
        return cls(
            source_commit=pair.source_commit,
            source_tree=pair.source_tree,
            expected_project_sha256=hashlib.sha256(
                project.encode("utf-8")
            ).hexdigest(),
            bundle_sha256=pair.bundle_sha256,
            image_digest=pair.image_digest,
            expected_service_account=(
                f"recall-sa-cohort-job@{PROJECT_PLACEHOLDER}."
                "iam.gserviceaccount.com"
            ),
        )

    @classmethod
    def from_positive(
        cls, identity: PositiveSmokeLaunchIdentity, *, project: str
    ) -> "DeploymentExpectation":
        if not PROJECT.fullmatch(project):
            raise ValueError("project_invalid")
        return cls(
            source_commit=identity.deployed_source_commit,
            source_tree=identity.deployed_source_tree,
            expected_project_sha256=hashlib.sha256(
                project.encode("utf-8")
            ).hexdigest(),
            bundle_sha256=identity.bundle_sha256,
            image_digest=identity.deployed_image_digest,
            expected_service_account=(
                f"recall-sa-cohort-job@{PROJECT_PLACEHOLDER}."
                "iam.gserviceaccount.com"
            ),
        )


def _validate_prefix(prefix: str) -> None:
    if (
        not prefix.startswith(SMOKE_NAMESPACE)
        or not re.fullmatch(r"[a-z0-9_]+", prefix)
        or not prefix.endswith("_")
        or any(blocked in prefix.lower() for blocked in ("final", "_c6_", "456"))
    ):
        raise ValueError("smoke_prefix_invalid")


def _command(pair: SmokePair, mode: str) -> str:
    args = ",".join(pair.entrypoint_args(mode))
    overrides = ",".join(
        (
            f"RECALL_SMOKE_EXPECTED_PLAN_SHA256={pair.plan_sha256}",
            f"RECALL_SMOKE_EXPECTED_IMAGE_DIGEST={pair.image_digest}",
            "RECALL_SMOKE_JOB_MAX_RETRIES=0",
        )
    )
    return (
        f"gcloud run jobs execute {JOB} --region={REGION} "
        f"--args={args} --update-env-vars={overrides} "
        "--tasks=1 --task-timeout=28800s --wait "
        "--format='value(metadata.name)'"
    )


def build_cloud_build_config(
    pair: SmokePair, *, machine_service_account: str | None = None
) -> dict[str, object]:
    """Return one no-source build body that attempts each smoke exactly once."""

    service_account_resource: str | None = None
    if machine_service_account is not None:
        match = MACHINE_SERVICE_ACCOUNT.fullmatch(machine_service_account)
        if not match:
            raise ValueError("machine_service_account_invalid")
        service_account_resource = (
            f"projects/{match.group('project')}/serviceAccounts/"
            f"{machine_service_account}"
        )
    positive = _command(pair, "positive")
    negative = _command(pair, "negative")
    script = f"""\
set -u
positive_output=$({positive} 2>/tmp/positive.stderr)
positive_rc=$?
negative_output=$({negative} 2>/tmp/negative.stderr)
negative_rc=$?
set -e
positive_name="${{positive_output##*/}}"
negative_name="${{negative_output##*/}}"
case "$positive_name" in recall-cohort-daily-*) ;; *) exit 91 ;; esac
case "$negative_name" in recall-cohort-daily-*) ;; *) exit 92 ;; esac
printf 'RECALL_SMOKE_EXECUTION positive %s\\n' "$positive_name"
printf 'RECALL_SMOKE_EXECUTION negative %s\\n' "$negative_name"
printf 'RECALL_SMOKE_TERMINAL_RC positive %s\\n' "$positive_rc"
printf 'RECALL_SMOKE_TERMINAL_RC negative %s\\n' "$negative_rc"
"""
    config: dict[str, object] = {
        "steps": [
            {
                "id": "isolated-smoke-pair",
                "name": "gcr.io/google.com/cloudsdktool/cloud-sdk:slim",
                "entrypoint": "bash",
                "args": ["-c", script],
                "timeout": "60000s",
            }
        ],
        "timeout": "60000s",
        "options": {"logging": "CLOUD_LOGGING_ONLY"},
    }
    if service_account_resource is not None:
        config["serviceAccount"] = service_account_resource
    return config


def _nested(value: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _canonical_cpu(value: Any) -> str | None:
    if isinstance(value, str) and value in {"1", "1000m"}:
        return "1"
    return None


def _container(job: Mapping[str, Any]) -> Mapping[str, Any]:
    candidates = (
        ("spec", "template", "spec", "template", "spec", "containers"),
        ("spec", "template", "spec", "containers"),
        ("template", "template", "containers"),
        ("template", "containers"),
    )
    for path in candidates:
        containers = _nested(job, path)
        if isinstance(containers, list) and len(containers) == 1:
            item = containers[0]
            if isinstance(item, Mapping):
                return item
    return {}


def _template_value(job: Mapping[str, Any], name: str) -> Any:
    paths = {
        "taskCount": (
            ("spec", "template", "spec", "taskCount"),
            ("template", "taskCount"),
        ),
        "maxRetries": (
            ("spec", "template", "spec", "template", "spec", "maxRetries"),
            ("template", "template", "maxRetries"),
            ("template", "maxRetries"),
        ),
        "timeoutSeconds": (
            ("spec", "template", "spec", "template", "spec", "timeoutSeconds"),
            ("template", "template", "timeout"),
            ("template", "timeout"),
        ),
    }
    for path in paths[name]:
        found = _nested(job, path)
        if found is not None:
            return found
    return None


def _service_account(job: Mapping[str, Any]) -> Any:
    for path in (
        ("spec", "template", "spec", "template", "spec", "serviceAccountName"),
        ("template", "template", "serviceAccount"),
        ("template", "serviceAccount"),
    ):
        found = _nested(job, path)
        if found is not None:
            return found
    return None


def _is_secret_binding(item: Mapping[str, Any]) -> bool:
    for source_name, required_fields in (
        ("valueFrom", {"name", "key"}),
        ("valueSource", {"secret", "version"}),
    ):
        if set(item) != {"name", source_name}:
            continue
        source = item.get(source_name)
        reference = source.get("secretKeyRef") if isinstance(source, Mapping) else None
        if (
            isinstance(reference, Mapping)
            and set(reference) == required_fields
            and all(
                isinstance(reference[field], str) and reference[field]
                for field in required_fields
            )
        ):
            return True
    return False


def validate_job_snapshot(
    job: Mapping[str, Any], expectation: DeploymentExpectation
) -> tuple[str, ...]:
    """Validate the already-deployed candidate without returning sensitive data."""

    failures: list[str] = []
    container = _container(job)
    env_rows = container.get("env", []) if isinstance(container, Mapping) else []
    env = {
        str(item.get("name")): item.get("value")
        for item in env_rows
        if isinstance(item, Mapping) and isinstance(item.get("name"), str)
    }
    required_env = {
        "RECALL_PROVIDER_RPM": (expectation.provider_rpm, "provider_rpm"),
        "FULL_AUDIT_CONCURRENCY": (expectation.concurrency, "concurrency"),
        "RECALL_SOURCE_COMMIT": (expectation.source_commit, "source_commit"),
        "RECALL_SOURCE_TREE": (expectation.source_tree, "source_tree"),
        "RECALL_IMAGE_DIGEST": (expectation.image_digest, "image_digest"),
        "RECALL_COMPRESSED_PREPARATION_SHA256": (
            expectation.bundle_sha256,
            "bundle_sha256",
        ),
        "RECALL_EXPECTED_PROJECT_SHA256": (
            expectation.expected_project_sha256,
            "expected_project_sha256",
        ),
        "RECALL_SCHEDULER_MODE": ("COMPRESSED_V3", "scheduler_mode"),
    }
    for name, (expected, code) in required_env.items():
        if name not in env:
            failures.append(f"{code}_missing")
        elif str(env[name]) != str(expected):
            failures.append(f"{code}_mismatch")
    image = str(container.get("image", ""))
    if not image.endswith("@" + expectation.image_digest):
        failures.append("deployed_digest_mismatch")
    if _service_account(job) != expectation.expected_service_account:
        failures.append("service_account_mismatch")
    for required_name in sorted(REQUIRED_SECRET_ENV):
        matches = [
            item
            for item in env_rows
            if isinstance(item, Mapping) and item.get("name") == required_name
        ]
        if len(matches) != 1:
            failures.append("required_secret_binding_invalid")
        elif not _is_secret_binding(matches[0]):
            failures.append("required_secret_binding_missing")
    task_count = _template_value(job, "taskCount")
    if str(task_count) != str(expectation.task_count):
        failures.append("task_count_mismatch")
    max_retries = _template_value(job, "maxRetries")
    if str(max_retries) != str(expectation.max_retries):
        failures.append("max_retries_mismatch")
    timeout = str(_template_value(job, "timeoutSeconds") or "").removesuffix("s")
    if timeout != str(expectation.timeout_seconds):
        failures.append("timeout_mismatch")
    limits = _nested(container, ("resources", "limits"))
    actual_cpu = (
        _canonical_cpu(limits.get("cpu"))
        if isinstance(limits, Mapping)
        else None
    )
    expected_cpu = _canonical_cpu(expectation.cpu)
    if actual_cpu is None or expected_cpu is None or actual_cpu != expected_cpu:
        failures.append("cpu_mismatch")
    if not isinstance(limits, Mapping) or str(limits.get("memory")) != expectation.memory:
        failures.append("memory_mismatch")
    return tuple(failures)


def positive_receipt_path(identity: PositiveSmokeLaunchIdentity) -> Path:
    return POSITIVE_RECEIPT_ROOT / f"positive-smoke-{identity.attempt_key}.json"


def _write_positive_intent_receipt(identity: PositiveSmokeLaunchIdentity) -> None:
    POSITIVE_RECEIPT_ROOT.mkdir(parents=True, exist_ok=True)
    target = positive_receipt_path(identity)
    with target.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(
            identity.to_receipt(),
            handle,
            sort_keys=True,
            separators=(",", ":"),
        )
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _read_positive_intent_receipt(
    identity: PositiveSmokeLaunchIdentity,
) -> dict[str, object] | None:
    try:
        value = json.loads(
            positive_receipt_path(identity).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return None
    expected = identity.to_receipt()
    return dict(value) if value == expected else None


def build_positive_execute_args(
    identity: PositiveSmokeLaunchIdentity, project: str
) -> list[str]:
    if not PROJECT.fullmatch(project):
        raise ValueError("project_invalid")
    runtime_args = ",".join(identity.entrypoint_args())
    overrides = ",".join(
        (
            f"RECALL_SMOKE_EXPECTED_PLAN_SHA256={identity.plan_sha256}",
            (
                "RECALL_SMOKE_EXPECTED_IMAGE_DIGEST="
                f"{identity.deployed_image_digest}"
            ),
            "RECALL_SMOKE_JOB_MAX_RETRIES=0",
            f"{POSITIVE_INTENT_ENV}={identity.intent_sha256}",
        )
    )
    return [
        "run",
        "jobs",
        "execute",
        JOB,
        f"--region={REGION}",
        f"--project={project}",
        f"--args={runtime_args}",
        f"--update-env-vars={overrides}",
        "--tasks=1",
        "--task-timeout=28800s",
        "--async",
        "--format=json",
    ]


def _positive_list_args(project: str) -> tuple[str, ...]:
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
        [
            "git",
            "-c",
            f"safe.directory={REPO_ROOT.as_posix()}",
            "-C",
            str(REPO_ROOT),
            *args,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def verify_positive_coordinator_checkout(
    identity: PositiveSmokeLaunchIdentity, *, run_fn: Any = _run_local_git
) -> tuple[str, ...]:
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
    values: dict[str, str] = {}
    for name, command in commands.items():
        try:
            result = run_fn(*command)
        except (OSError, subprocess.TimeoutExpired):
            failures.add(f"coordinator_git_{name}_unavailable")
            continue
        if result.returncode != 0:
            failures.add(f"coordinator_git_{name}_failed")
            continue
        values[name] = result.stdout.strip()
    if values.get("head") != identity.coordinator_commit:
        failures.add("coordinator_head_mismatch")
    if values.get("tree") != identity.coordinator_tree:
        failures.add("coordinator_tree_mismatch")
    if values.get("status") != "":
        failures.add("coordinator_checkout_dirty")
    if not values.get("head_blob") or values.get("head_blob") != values.get(
        "worktree_blob"
    ):
        failures.add("coordinator_trigger_blob_mismatch")
    current_sha = hashlib.sha256(
        (REPO_ROOT / TRIGGER_RELATIVE_PATH).read_bytes()
    ).hexdigest()
    if current_sha != identity.coordinator_trigger_sha256:
        failures.add("coordinator_trigger_sha256_mismatch")
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


def _job_activation_failures(
    job: Mapping[str, Any],
    identity: PositiveSmokeLaunchIdentity,
    project: str,
) -> tuple[str, ...]:
    failures = list(
        validate_job_snapshot(
            job, DeploymentExpectation.from_positive(identity, project=project)
        )
    )
    _, env_failures = _literal_env(_container(job))
    failures.extend(env_failures)
    generation = _nested(job, ("metadata", "generation"))
    observed = _nested(job, ("status", "observedGeneration"))
    try:
        generation_value = int(generation)
        observed_value = int(observed)
    except (TypeError, ValueError):
        failures.append("job_generation_invalid")
    else:
        if generation_value != identity.expected_generation:
            failures.append("job_generation_mismatch")
        if observed_value != generation_value:
            failures.append("job_generation_not_observed")
    conditions = _nested(job, ("status", "conditions"))
    ready = (
        [
            item
            for item in conditions
            if isinstance(item, Mapping) and item.get("type") == "Ready"
        ]
        if isinstance(conditions, list)
        else []
    )
    ready_values = (
        {
            str(ready[0].get(name, "")).upper()
            for name in ("status", "state")
            if ready[0].get(name) is not None
        }
        if len(ready) == 1
        else set()
    )
    success_values = {"TRUE", "CONDITION_SUCCEEDED", "SUCCEEDED"}
    failure_values = {"FALSE", "CONDITION_FAILED", "FAILED"}
    if (
        len(ready) != 1
        or not (ready_values & success_values)
        or bool(ready_values & failure_values)
    ):
        failures.append("job_not_ready")
    return tuple(sorted(set(failures)))


def _literal_env(container: Mapping[str, Any]) -> tuple[dict[str, str], set[str]]:
    rows = container.get("env", [])
    if not isinstance(rows, list):
        return {}, {"execution_env_contract_invalid"}
    values: dict[str, str] = {}
    failures: set[str] = set()
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            failures.add("execution_env_contract_invalid")
            continue
        name = row.get("name")
        if not isinstance(name, str) or not name or name in seen:
            failures.add("execution_env_contract_invalid")
            continue
        seen.add(name)
        if set(row) == {"name", "value"} and isinstance(row.get("value"), str):
            values[name] = str(row["value"])
    return values, failures


def _execution_name(value: Mapping[str, Any]) -> str | None:
    raw = _nested(value, ("metadata", "name"))
    if raw is None:
        raw = value.get("name")
    if not isinstance(raw, str):
        return None
    name = raw.rsplit("/", 1)[-1]
    return name if EXECUTION.fullmatch(name) else None


def _execution_alias(name: str) -> str:
    return hashlib.sha256(name.encode("ascii")).hexdigest()[:16]


def _execution_marker(value: Mapping[str, Any]) -> str | None:
    env, _ = _literal_env(_container(value))
    marker = env.get(POSITIVE_INTENT_ENV)
    return marker if marker is not None and HEX64.fullmatch(marker) else None


def _parse_execution_list(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or any(
        not isinstance(item, Mapping) or _execution_name(item) is None
        for item in value
    ):
        raise RuntimeError("execution_list_contract_invalid")
    return list(value)


def _safe_positive_failure(
    identity: PositiveSmokeLaunchIdentity, *codes: str
) -> dict[str, object]:
    return {
        "verdict": "FAIL",
        "attempt_alias": identity.attempt_key[:16],
        "execute_count": 0,
        "codes": list(codes),
    }


def submit_positive_once(
    identity: PositiveSmokeLaunchIdentity,
    *,
    project: str,
    run_fn: Any = None,
) -> dict[str, object]:
    """Create one immutable intent, then send at most one async positive smoke."""

    if not PROJECT.fullmatch(project):
        raise ValueError("project_invalid")
    if run_fn is None:
        from repoint_cohort_job import _run_redacted  # noqa: PLC0415

        run_fn = _run_redacted
    if hashlib.sha256(project.encode("utf-8")).hexdigest() != (
        identity.expected_project_sha256
    ):
        return _safe_positive_failure(identity, "project_hash_mismatch")
    checkout_failures = verify_positive_coordinator_checkout(identity)
    if checkout_failures:
        return _safe_positive_failure(identity, *checkout_failures)
    if positive_receipt_path(identity).exists():
        return _safe_positive_failure(identity, "attempt_receipt_exists")
    try:
        _write_positive_intent_receipt(identity)
    except FileExistsError:
        return _safe_positive_failure(identity, "attempt_receipt_exists")

    described = run_fn(
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
        return _safe_positive_failure(identity, str(exc))
    if not isinstance(job, Mapping):
        return _safe_positive_failure(identity, "job_describe_contract_invalid")
    failures = _job_activation_failures(job, identity, project)
    if failures:
        return _safe_positive_failure(identity, *failures)

    listed = run_fn(
        *_positive_list_args(project), timeout_seconds=READ_TIMEOUT_SECONDS
    )
    try:
        executions = _parse_execution_list(
            _parse_json_result(listed, failure_code="execution_list_failed")
        )
    except RuntimeError as exc:
        return _safe_positive_failure(identity, str(exc))
    if any(_execution_marker(item) == identity.intent_sha256 for item in executions):
        return _safe_positive_failure(identity, "intent_marker_already_present")

    common = {
        "attempt_alias": identity.attempt_key[:16],
        "execute_count": 1,
        "receipt_state": "LOCAL_INTENT_ONLY",
    }
    try:
        submitted = run_fn(
            *build_positive_execute_args(identity, project),
            timeout_seconds=SUBMIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {
            "verdict": "OUTCOME_UNKNOWN",
            **common,
            "submit_exit_code": None,
            "next_step": "STOP_AND_RECONCILE",
        }
    if submitted.returncode != 0:
        return {
            "verdict": "OUTCOME_UNKNOWN",
            **common,
            "submit_exit_code": int(submitted.returncode),
            "next_step": "STOP_AND_RECONCILE",
        }
    return {"verdict": "SUBMIT_ACCEPTED_NOT_RECONCILED", **common}


def _execution_binding_failures(
    execution: Mapping[str, Any], identity: PositiveSmokeLaunchIdentity
) -> tuple[str, ...]:
    failures: set[str] = set()
    container = _container(execution)
    if not str(container.get("image", "")).endswith(
        "@" + identity.deployed_image_digest
    ):
        failures.add("execution_image_digest_mismatch")
    env, env_failures = _literal_env(container)
    failures.update(env_failures)
    required_env = {
        "RECALL_SOURCE_COMMIT": identity.deployed_source_commit,
        "RECALL_SOURCE_TREE": identity.deployed_source_tree,
        "RECALL_IMAGE_DIGEST": identity.deployed_image_digest,
        "RECALL_COMPRESSED_PREPARATION_SHA256": identity.bundle_sha256,
        "RECALL_EXPECTED_PROJECT_SHA256": identity.expected_project_sha256,
        "RECALL_SCHEDULER_MODE": "COMPRESSED_V3",
        "RECALL_PROVIDER_RPM": "8",
        "FULL_AUDIT_CONCURRENCY": "2",
        "RECALL_SMOKE_EXPECTED_PLAN_SHA256": identity.plan_sha256,
        "RECALL_SMOKE_EXPECTED_IMAGE_DIGEST": identity.deployed_image_digest,
        "RECALL_SMOKE_JOB_MAX_RETRIES": "0",
        POSITIVE_INTENT_ENV: identity.intent_sha256,
    }
    for name, expected in required_env.items():
        if env.get(name) != expected:
            failures.add(f"execution_env_mismatch:{name}")
    if container.get("args") != list(identity.entrypoint_args()):
        failures.add("execution_args_mismatch")
    generation = _nested(
        execution, ("metadata", "labels", "run.googleapis.com/jobGeneration")
    )
    try:
        generation_value = int(generation)
    except (TypeError, ValueError):
        failures.add("execution_generation_not_verified")
    else:
        if generation_value != identity.expected_generation:
            failures.add("execution_generation_mismatch")
    return tuple(sorted(failures))


def _execution_state(execution: Mapping[str, Any]) -> str:
    status = execution.get("status", {})
    if not isinstance(status, Mapping):
        return "UNKNOWN"
    try:
        running = int(status.get("runningCount", 0) or 0)
        succeeded = int(status.get("succeededCount", 0) or 0)
        failed = int(status.get("failedCount", 0) or 0)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if failed > 0:
        return "FAILED" if running == 0 and succeeded == 0 else "CONTRADICTORY"
    if succeeded > 0:
        return "SUCCEEDED" if running == 0 else "CONTRADICTORY"
    return "RUNNING" if running > 0 else "UNKNOWN"


def _creator_class(execution: Mapping[str, Any]) -> str:
    creator = _nested(
        execution, ("metadata", "annotations", "run.googleapis.com/creator")
    )
    if not isinstance(creator, str) or not creator:
        return "UNKNOWN"
    if creator in {"<account>", "<principal>"}:
        return "CONFIGURED_CALLER_REDACTED"
    if creator.lower().endswith(".gserviceaccount.com"):
        return "MACHINE"
    return "HUMAN" if "@" in creator else "UNKNOWN"


def reconcile_positive(
    identity: PositiveSmokeLaunchIdentity,
    *,
    project: str,
    run_fn: Any = None,
) -> dict[str, object]:
    """Read-only exact-intent reconciliation; this function cannot submit."""

    if not PROJECT.fullmatch(project):
        raise ValueError("project_invalid")
    if run_fn is None:
        from repoint_cohort_job import _run_redacted  # noqa: PLC0415

        run_fn = _run_redacted
    if hashlib.sha256(project.encode("utf-8")).hexdigest() != (
        identity.expected_project_sha256
    ):
        return _safe_positive_failure(identity, "project_hash_mismatch")
    checkout_failures = verify_positive_coordinator_checkout(identity)
    if checkout_failures:
        return _safe_positive_failure(identity, *checkout_failures)
    if _read_positive_intent_receipt(identity) is None:
        return _safe_positive_failure(identity, "attempt_receipt_invalid")
    listed = run_fn(
        *_positive_list_args(project), timeout_seconds=READ_TIMEOUT_SECONDS
    )
    try:
        executions = _parse_execution_list(
            _parse_json_result(listed, failure_code="execution_list_failed")
        )
    except RuntimeError as exc:
        return {
            "verdict": "NOT_VERIFIED",
            "state": "READ_FAILED",
            "attempt_alias": identity.attempt_key[:16],
            "codes": [str(exc)],
        }
    candidates = [
        item
        for item in executions
        if _execution_marker(item) == identity.intent_sha256
    ]
    if not candidates:
        return {
            "verdict": "NOT_VERIFIED",
            "state": "PENDING",
            "attempt_alias": identity.attempt_key[:16],
            "execution_count": 0,
        }
    if len(candidates) != 1:
        return {
            "verdict": "FAIL",
            "state": "AMBIGUOUS",
            "attempt_alias": identity.attempt_key[:16],
            "execution_count": len(candidates),
            "codes": ["multiple_execution_candidates"],
        }
    listed_execution = candidates[0]
    name = _execution_name(listed_execution)
    if name is None:
        return _safe_positive_failure(identity, "execution_name_invalid")
    described = run_fn(
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
            "attempt_alias": identity.attempt_key[:16],
            "execution_count": 1,
            "execution_alias": _execution_alias(name),
            "codes": [str(exc)],
        }
    if not isinstance(execution, Mapping) or _execution_name(execution) != name:
        return {
            "verdict": "FAIL",
            "state": "IDENTITY_MISMATCH",
            "attempt_alias": identity.attempt_key[:16],
            "execution_count": 1,
            "execution_alias": _execution_alias(name),
            "codes": ["execution_describe_identity_mismatch"],
        }
    failures = _execution_binding_failures(execution, identity)
    if failures:
        return {
            "verdict": "FAIL",
            "state": "BINDING_MISMATCH",
            "attempt_alias": identity.attempt_key[:16],
            "execution_count": 1,
            "execution_alias": _execution_alias(name),
            "codes": list(failures),
        }
    state = _execution_state(execution)
    verdict = "PASS" if state in {"RUNNING", "SUCCEEDED"} else "FAIL"
    if state in {"UNKNOWN", "CONTRADICTORY"}:
        verdict = "NOT_VERIFIED"
    return {
        "verdict": verdict,
        "state": state,
        "attempt_alias": identity.attempt_key[:16],
        "execution_count": 1,
        "execution_alias": _execution_alias(name),
        "creator_class": _creator_class(execution),
    }


def parse_execution_markers(output: str) -> dict[str, str]:
    markers: dict[str, list[str]] = {"positive": [], "negative": []}
    pattern = re.compile(
        r"(?:^|: )RECALL_SMOKE_EXECUTION (positive|negative) "
        r"([a-z][a-z0-9-]{0,62})$"
    )
    for line in output.splitlines():
        match = pattern.search(line.strip())
        if match:
            markers[match.group(1)].append(match.group(2))
    if any(len(values) != 1 for values in markers.values()):
        raise ValueError("execution_markers_invalid")
    result = {mode: values[0] for mode, values in markers.items()}
    if any(not EXECUTION.fullmatch(value) for value in result.values()):
        raise ValueError("execution_markers_invalid")
    return result


def parse_build_id(output: str) -> str:
    candidates = [line.strip() for line in output.splitlines() if line.strip()]
    if len(candidates) != 1 or not BUILD_ID.fullmatch(candidates[0]):
        raise ValueError("build_id_invalid")
    return candidates[0]


def _alias(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def submit_smoke_pair(
    pair: SmokePair,
    *,
    machine_service_account_local_part: str | None = None,
    project: str,
    receipt_path: Path,
    run_fn: Any = None,
) -> dict[str, object]:
    """Preflight, submit one source-less build, and persist a private handoff.

    The returned report contains one-way aliases only.  Exact execution names
    and prefixes are written once to ``receipt_path`` for the read-only
    collector.  The function never retries either the build or an execution.
    """

    if machine_service_account_local_part is not None and not (
        SERVICE_ACCOUNT_LOCAL_PART.fullmatch(machine_service_account_local_part)
    ):
        raise ValueError("machine_service_account_local_part_invalid")
    if not PROJECT.fullmatch(project):
        raise ValueError("project_invalid")
    if receipt_path.exists() or not receipt_path.parent.is_dir():
        raise ValueError("receipt_path_not_new_file")
    if run_fn is None:
        from repoint_cohort_job import _run_redacted

        run_fn = _run_redacted

    described: CompletedProcess[str] = run_fn(
        "run", "jobs", "describe", JOB, f"--region={REGION}", "--format=json"
    )
    if described.returncode != 0:
        raise RuntimeError(f"job_describe_failed:{described.returncode}")
    try:
        job = json.loads(described.stdout)
    except json.JSONDecodeError:
        raise RuntimeError("job_describe_json_invalid") from None
    failures = validate_job_snapshot(
        job, DeploymentExpectation.from_pair(pair, project=project)
    )
    if failures:
        raise RuntimeError("job_preflight_failed:" + ",".join(failures))

    service_account = (
        f"{machine_service_account_local_part}@{project}.iam.gserviceaccount.com"
        if machine_service_account_local_part is not None
        else None
    )
    config = build_cloud_build_config(
        pair, machine_service_account=service_account
    )
    with tempfile.TemporaryDirectory(prefix="recall-smoke-build-") as directory:
        config_path = Path(directory) / "cloudbuild.json"
        config_path.write_text(
            json.dumps(config, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        submit_args = [
            "builds",
            "submit",
            "--no-source",
            f"--config={config_path}",
        ]
        if service_account is not None:
            submit_args.append(
                f"--service-account=projects/{project}/serviceAccounts/"
                f"{service_account}"
            )
        submit_args.append("--format=value(id)")
        submitted: CompletedProcess[str] = run_fn(
            *submit_args,
            timeout_seconds=60_600,
        )
    if submitted.returncode != 0:
        raise RuntimeError(f"smoke_build_failed:{submitted.returncode}")
    try:
        build_id = parse_build_id(submitted.stdout)
    except ValueError:
        raise RuntimeError("smoke_build_id_invalid") from None
    build = run_fn(
        "builds",
        "describe",
        build_id,
        "--format=json(id,status)",
    )
    if build.returncode != 0:
        raise RuntimeError(f"smoke_build_readback_failed:{build.returncode}")
    try:
        build_value = json.loads(build.stdout)
    except json.JSONDecodeError:
        raise RuntimeError("smoke_build_readback_invalid") from None
    if build_value != {"id": build_id, "status": "SUCCESS"}:
        raise RuntimeError("smoke_build_readback_invalid")
    build_log = run_fn("builds", "log", build_id, timeout_seconds=600)
    if build_log.returncode != 0:
        raise RuntimeError(f"smoke_build_log_failed:{build_log.returncode}")
    executions = parse_execution_markers(build_log.stdout)
    receipt = {
        "schema_name": "IsolatedSmokeExecutionPair",
        "schema_version": "1.0.0",
        "smoke_id": pair.smoke_id,
        "positive_execution": executions["positive"],
        "negative_execution": executions["negative"],
        "positive_prefix": pair.positive_prefix,
        "negative_prefix": pair.negative_prefix,
        "source_commit": pair.source_commit,
        "source_tree": pair.source_tree,
        "plan_sha256": pair.plan_sha256,
        "bundle_sha256": pair.bundle_sha256,
        "image_digest": pair.image_digest,
        "expected_project_sha256": hashlib.sha256(
            project.encode("utf-8")
        ).hexdigest(),
    }
    with receipt_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(receipt, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    return {
        "verdict": "READY_FOR_COLLECTION",
        "execution_count": 2,
        "positive_execution_alias": _alias(executions["positive"]),
        "negative_execution_alias": _alias(executions["negative"]),
    }


def _positive_identity_from_args(
    args: argparse.Namespace,
) -> PositiveSmokeLaunchIdentity:
    return PositiveSmokeLaunchIdentity.create(
        smoke_id=args.smoke_id,
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
    )


def _positive_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("positive-submit", "positive-reconcile")
    )
    parser.add_argument("--smoke-id", required=True, action=_StoreOnce)
    parser.add_argument(
        "--deployed-source-commit", required=True, action=_StoreOnce
    )
    parser.add_argument(
        "--deployed-source-tree", required=True, action=_StoreOnce
    )
    parser.add_argument(
        "--deployed-image-digest", required=True, action=_StoreOnce
    )
    parser.add_argument("--plan-sha256", required=True, action=_StoreOnce)
    parser.add_argument("--bundle-sha256", required=True, action=_StoreOnce)
    parser.add_argument(
        "--expected-project-sha256", required=True, action=_StoreOnce
    )
    parser.add_argument(
        "--expected-generation", required=True, type=int, action=_StoreOnce
    )
    parser.add_argument(
        "--coordinator-commit", required=True, action=_StoreOnce
    )
    parser.add_argument(
        "--coordinator-tree", required=True, action=_StoreOnce
    )
    parser.add_argument(
        "--coordinator-trigger-sha256", required=True, action=_StoreOnce
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _positive_parser().parse_args(argv)
    identity = _positive_identity_from_args(args)
    project = resolve_project()
    if args.action == "positive-submit":
        report = submit_positive_once(identity, project=project)
    else:
        report = reconcile_positive(identity, project=project)
    print(json.dumps(report, sort_keys=True))
    return 0 if report.get("verdict") in {
        "PASS",
        "SUBMIT_ACCEPTED_NOT_RECONCILED",
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
