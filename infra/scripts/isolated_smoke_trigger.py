"""Build a fail-closed, source-less Cloud Build request for two smoke executions.

This module only prepares and validates the request.  The caller that submits it
must use ``gcloud_redacted.py`` and must first validate the deployed job snapshot
with :func:`validate_job_snapshot`.  Preparing the request performs no cloud or
Git operation.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any, Mapping


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from recall.platform.redaction import PROJECT_PLACEHOLDER  # noqa: E402


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
    pair: SmokePair, *, machine_service_account: str
) -> dict[str, object]:
    """Return one no-source build body that attempts each smoke exactly once."""

    match = MACHINE_SERVICE_ACCOUNT.fullmatch(machine_service_account)
    if not match:
        raise ValueError("machine_service_account_invalid")
    project = match.group("project")
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
    return {
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
        "serviceAccount": (
            f"projects/{project}/serviceAccounts/{machine_service_account}"
        ),
        "options": {"logging": "CLOUD_LOGGING_ONLY"},
    }


def _nested(value: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _container(job: Mapping[str, Any]) -> Mapping[str, Any]:
    candidates = (
        ("spec", "template", "spec", "template", "spec", "containers"),
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
    secret_bindings = {
        str(item.get("name"))
        for item in env_rows
        if isinstance(item, Mapping)
        and isinstance(item.get("name"), str)
        and _is_secret_binding(item)
    }
    if not REQUIRED_SECRET_ENV.issubset(secret_bindings):
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
    if not isinstance(limits, Mapping) or str(limits.get("cpu")) != expectation.cpu:
        failures.append("cpu_mismatch")
    if not isinstance(limits, Mapping) or str(limits.get("memory")) != expectation.memory:
        failures.append("memory_mismatch")
    return tuple(failures)


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
    machine_service_account_local_part: str,
    project: str,
    receipt_path: Path,
    run_fn: Any = None,
) -> dict[str, object]:
    """Preflight, submit one source-less build, and persist a private handoff.

    The returned report contains one-way aliases only.  Exact execution names
    and prefixes are written once to ``receipt_path`` for the read-only
    collector.  The function never retries either the build or an execution.
    """

    if not SERVICE_ACCOUNT_LOCAL_PART.fullmatch(machine_service_account_local_part):
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
        service_account_resource = (
            f"projects/{project}/serviceAccounts/{service_account}"
        )
        submitted: CompletedProcess[str] = run_fn(
            "builds",
            "submit",
            "--no-source",
            f"--config={config_path}",
            f"--service-account={service_account_resource}",
            "--format=value(id)",
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
