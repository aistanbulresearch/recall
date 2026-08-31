"""Repoint the cohort job's image and environment as ONE update, then prove it.

The repoint after a code fix moves several values that must agree: the image
digest, the commit the image was built from, and whatever provenance fields the
entrypoint contract stamps into the manifest. They are not independent. A digest
that moves while a commit stays stale writes a provenance claim into the ledger
that nothing in the running system can detect -- entrypoint.py validates
RECALL_SOURCE_COMMIT for shape only, and the one check that binds a commit to a
tree (evidence.py source_commit_not_head) needs a git repo the image does not
have.

So the operational binding is the guard, and it has two halves:

    1. every value moves in the SAME `gcloud run jobs update` call
    2. the read-back proves every one of them moved, TOGETHER

Half 2 is the half that gets skipped when a person is doing this by hand at four
in the morning against a fixed tick, which is the only time this script will ever
be used. `verify` exists so the assertion half can be run on its own, and so it
can be seen to FAIL before anyone depends on it passing.

    python infra/scripts/repoint_cohort_job.py verify \
        --expect-digest sha256:... \
        --expect-env RECALL_PROVIDER_RPM=8 \
        --expect-env RECALL_SOURCE_COMMIT=<sha> \
        --expect-env RECALL_IMAGE_DIGEST=sha256:...

    python infra/scripts/repoint_cohort_job.py repoint \
        --digest sha256:... --env RECALL_PROVIDER_RPM=8 \
        --env RECALL_SOURCE_COMMIT=<sha> --env RECALL_IMAGE_DIGEST=sha256:...

Only non-sensitive, explicitly allowlisted provenance/config env pairs may move.
Secret-backed connector bindings and identity are preserved rather than copied
onto a process command line.

Nothing is repointed unless every expected value is supplied. There is no partial
mode, because a partial repoint is the failure this exists to prevent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gcloud_redacted import resolve_project  # noqa: E402
from recall.platform.redaction import PROJECT_PLACEHOLDER  # noqa: E402

JOB = "recall-cohort-daily"
REGION = "us-central1"
REPOSITORY = "recall-images"
IMAGE_NAME = "recall-cohort-job"
SERVICE_ACCOUNT_LOCAL_PART = "recall-sa-cohort-job"
REDACTED_WRAPPER = Path(__file__).resolve().parent / "gcloud_redacted.py"
GCLOUD_TIMEOUT_SECONDS = 600

EXPECTED_TIMEOUT_SECONDS = 28_800
EXPECTED_MAX_RETRIES = 0
EXPECTED_CPU = "1"
EXPECTED_MEMORY = "512Mi"
EXPECTED_TASK_COUNT = 1
EXPECTED_PROVIDER_RPM = "8"
REQUIRED_REPOINT_ENV = {
    "RECALL_PROVIDER_RPM",
    "RECALL_SOURCE_COMMIT",
    "RECALL_SOURCE_TREE",
    "RECALL_IMAGE_DIGEST",
    "RECALL_COMPRESSED_PREPARATION_SHA256",
    "RECALL_EXPECTED_PROJECT_SHA256",
    "RECALL_SCHEDULER_MODE",
}
SAFE_REPOINT_ENV = REQUIRED_REPOINT_ENV
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
HASH64 = re.compile(r"^[0-9a-f]{64}$")
UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
REQUIRED_SECRET_ENV = {
    "RECALL_TOOL_CAPABILITY_SECRET_B64",
    "RECALL_NCBI_TOOL",
    "RECALL_NCBI_EMAIL",
}

# Fields that must NOT move during a repoint. Listed explicitly rather than
# diffing everything, because generation and resourceVersion are SUPPOSED to move
# and a check that flagged them would be noise people learn to ignore.
FROZEN = ("serviceAccountFingerprint", "nonRepointEnvFingerprint")


def _start_wrapper(command: list[str]) -> subprocess.Popen[str]:
    kwargs: dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(command, **kwargs)


def _terminate_process_tree(process: subprocess.Popen[str]) -> bool:
    """Terminate only the timed-out wrapper tree; never retry the cloud action."""

    tree_cleanup_verified = True
    if os.name == "nt":
        try:
            taskkill = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if taskkill.returncode != 0:
                tree_cleanup_verified = False
                try:
                    process.kill()
                except OSError:
                    pass
        except (OSError, subprocess.TimeoutExpired):
            tree_cleanup_verified = False
            try:
                process.kill()
            except OSError:
                pass
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=10)
        return tree_cleanup_verified
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            try:
                process.kill()
            except OSError:
                tree_cleanup_verified = False
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=10)
            return tree_cleanup_verified
        except subprocess.TimeoutExpired:
            return False


def _run_redacted(
    *args: str,
    timeout_seconds: int = GCLOUD_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    """Invoke gcloud only through the redacted wrapper with bounded execution.

    Child streams are retained only for a successful JSON describe. They are
    never re-emitted on failures, because arbitrary job env values are outside
    the wrapper's identifier redaction contract.
    """

    command = [sys.executable, str(REDACTED_WRAPPER), "--quiet", *args]
    process = _start_wrapper(command)
    try:
        stdout, _stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        cleaned = _terminate_process_tree(process)
        return subprocess.CompletedProcess(
            ["redacted-wrapper"], 124 if cleaned else 125, "", ""
        )
    if process.returncode != 0:
        return subprocess.CompletedProcess(
            ["redacted-wrapper"], process.returncode, "", ""
        )
    return subprocess.CompletedProcess(["redacted-wrapper"], 0, stdout, "")


def describe() -> dict[str, Any]:
    result = _run_redacted(
        "run", "jobs", "describe", JOB, f"--region={REGION}", "--format=json"
    )
    if result.returncode != 0:
        raise SystemExit(f"describe_failed:{result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit("describe_json_invalid") from None


def _expected_build_metadata(
    source_commit: str,
    source_tree: str,
    context_manifest_sha256: str,
) -> tuple[dict[str, str], str]:
    return (
        {
            "_TAG": source_commit,
            "_REGION": REGION,
            "_REPO": REPOSITORY,
            "_SOURCE_COMMIT": source_commit,
            "_SOURCE_TREE": source_tree,
            "_CONTEXT_MANIFEST_SHA256": context_manifest_sha256,
        },
        (
            f"{REGION}-docker.pkg.dev/{PROJECT_PLACEHOLDER}/{REPOSITORY}/"
            f"{IMAGE_NAME}:{source_commit}"
        ),
    )


def verify_authoritative_image(
    project: str,
    build_id: str,
    digest: str,
    source_commit: str,
    source_tree: str,
    context_manifest_sha256: str,
    *,
    run_fn=_run_redacted,
) -> dict[str, Any]:
    """Bind a digest to source through authoritative build and registry reads."""

    if UUID.fullmatch(build_id) is None:
        raise SystemExit("build_id_invalid")
    if DIGEST.fullmatch(digest) is None:
        raise SystemExit("digest_invalid")
    if COMMIT.fullmatch(source_commit) is None:
        raise SystemExit("source_commit_invalid")
    if COMMIT.fullmatch(source_tree) is None:
        raise SystemExit("source_tree_invalid")
    if HASH64.fullmatch(context_manifest_sha256) is None:
        raise SystemExit("context_manifest_sha256_invalid")

    expected_substitutions, expected_name = _expected_build_metadata(
        source_commit, source_tree, context_manifest_sha256
    )
    build_result = run_fn(
        "builds",
        "describe",
        build_id,
        "--format=json(id,status,substitutions,results.images)",
    )
    failures: list[str] = []
    metadata_matched = False
    if build_result.returncode != 0:
        failures.append("build_metadata_read_failed")
    else:
        try:
            value = json.loads(build_result.stdout)
            images = value["results"]["images"]
            image = images[0] if isinstance(images, list) and len(images) == 1 else None
            metadata_matched = (
                isinstance(value, dict)
                and value.get("id") == build_id
                and value.get("status") == "SUCCESS"
                and value.get("substitutions") == expected_substitutions
                and isinstance(image, dict)
                and image.get("name") == expected_name
                and image.get("digest") == digest
            )
        except (json.JSONDecodeError, KeyError, TypeError, IndexError):
            metadata_matched = False
        if not metadata_matched:
            failures.append("build_metadata_mismatch")

    registry_matched = False
    if metadata_matched:
        image_uri = (
            f"{REGION}-docker.pkg.dev/{project}/{REPOSITORY}/"
            f"{IMAGE_NAME}@{digest}"
        )
        registry_result = run_fn(
            "artifacts",
            "docker",
            "images",
            "describe",
            image_uri,
            "--format=value(image_summary.digest)",
        )
        registry_matched = (
            registry_result.returncode == 0
            and registry_result.stdout.strip() == digest
        )
        if not registry_matched:
            failures.append("registry_digest_mismatch")

    return {
        "verdict": "PASS" if not failures else "FAIL",
        "build_metadata_matched": metadata_matched,
        "registry_digest_matched": registry_matched,
        "failures": failures,
    }


def _binding_identity(item: dict[str, Any]) -> tuple[str, dict[str, object], bool]:
    name = item.get("name")
    if not isinstance(name, str) or not name:
        raise SystemExit("env_binding_invalid")
    keys = set(item)
    if keys == {"name", "value"} and isinstance(item["value"], str):
        return name, {"kind": "value", "value": item["value"]}, False
    if keys == {"name", "valueFrom"}:
        source = item["valueFrom"]
        ref = source.get("secretKeyRef") if isinstance(source, dict) else None
        if (
            isinstance(ref, dict)
            and set(ref) == {"name", "key"}
            and all(isinstance(ref[field], str) and ref[field] for field in ref)
        ):
            return name, {"kind": "secretKeyRef", **ref}, True
    if keys == {"name", "valueSource"}:
        source = item["valueSource"]
        ref = source.get("secretKeyRef") if isinstance(source, dict) else None
        if (
            isinstance(ref, dict)
            and set(ref) == {"secret", "version"}
            and all(isinstance(ref[field], str) and ref[field] for field in ref)
        ):
            return name, {"kind": "secretKeyRef", **ref}, True
    raise SystemExit("env_binding_invalid")


def _fingerprint(value: object) -> str:
    wire = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(wire).hexdigest()


def observed(
    job: dict[str, Any],
    project: str,
    *,
    require_secret_bindings: bool = True,
) -> dict[str, Any]:
    try:
        outer = job["spec"]["template"]["spec"]
        spec = outer["template"]["spec"]
        container = spec["containers"][0]
        limits = container.get("resources", {}).get("limits", {})
        image = str(container["image"])
        service_account = spec["serviceAccountName"]
        expected_service_account = (
            f"{SERVICE_ACCOUNT_LOCAL_PART}@{PROJECT_PLACEHOLDER}."
            "iam.gserviceaccount.com"
        )
        candidate_env: dict[str, str] = {}
        non_repoint_bindings: dict[str, dict[str, object]] = {}
        secret_bindings: set[str] = set()
        seen: set[str] = set()
        for item in container.get("env", []):
            name, binding, secret_backed = _binding_identity(item)
            if name in seen:
                raise SystemExit("env_binding_duplicate")
            seen.add(name)
            if name in SAFE_REPOINT_ENV:
                if binding.get("kind") != "value":
                    raise SystemExit("repoint_env_not_literal")
                candidate_env[name] = str(binding["value"])
            else:
                non_repoint_bindings[name] = binding
                if secret_backed:
                    secret_bindings.add(name)
        secret_bindings_present = REQUIRED_SECRET_ENV.issubset(secret_bindings)
        if require_secret_bindings and not secret_bindings_present:
            raise SystemExit("required_secret_binding_missing")
        return {
            "image_digest": image.rpartition("@")[2] if "@" in image else "",
            "env": candidate_env,
            "serviceAccountExpected": service_account == expected_service_account,
            "serviceAccountFingerprint": _fingerprint(service_account),
            "nonRepointEnvFingerprint": _fingerprint(non_repoint_bindings),
            "requiredSecretBindingsPresent": secret_bindings_present,
            "timeoutSeconds": int(str(spec["timeoutSeconds"]).removesuffix("s")),
            "maxRetries": int(spec["maxRetries"]),
            "cpu": str(limits.get("cpu", "")),
            "memory": str(limits.get("memory", "")),
            "taskCount": int(outer["taskCount"]),
            "generation": int(job["metadata"]["generation"]),
            "observedGeneration": int(job["status"]["observedGeneration"]),
            "ready": any(
                c["type"] == "Ready" and c["status"] == "True"
                for c in job["status"].get("conditions", [])
            ),
        }
    except (IndexError, KeyError, TypeError, ValueError):
        raise SystemExit("describe_contract_invalid") from None


def check(
    state: dict[str, Any],
    digest: str,
    env: dict[str, str],
) -> dict[str, Any]:
    """Assert the fixed candidate and emit only allowlisted, non-sensitive facts."""

    failures: list[str] = []
    if state["image_digest"] != digest:
        failures.append("image_digest_mismatch")
    env_checks: dict[str, dict[str, bool]] = {}
    for name in sorted(env):
        want = env[name]
        got = state["env"].get(name)
        env_checks[name] = {"present": got is not None, "matched": got == want}
        if got is None:
            failures.append(f"env_absent:{name}")
        elif got != want:
            failures.append(f"env_mismatch:{name}")

    deployment_checks = {
        "timeout_seconds": int(state["timeoutSeconds"]) == EXPECTED_TIMEOUT_SECONDS,
        "max_retries": int(state["maxRetries"]) == EXPECTED_MAX_RETRIES,
        "cpu": _normalize_cpu(str(state["cpu"])) == EXPECTED_CPU,
        "memory": str(state["memory"]) == EXPECTED_MEMORY,
        "task_count": int(state["taskCount"]) == EXPECTED_TASK_COUNT,
        "ready": bool(state["ready"]),
        "reconciled": state["generation"] == state["observedGeneration"],
    }
    for name, matched in deployment_checks.items():
        if not matched:
            failures.append(f"{name}_mismatch")
    if not state["serviceAccountExpected"]:
        failures.append("service_account_mismatch")
    if not state["requiredSecretBindingsPresent"]:
        failures.append("required_secret_binding_missing")
    return {
        "expected_digest": digest,
        "expected_env_names": sorted(env),
        "env_checks": env_checks,
        "deployment": {
            "timeout_seconds": int(state["timeoutSeconds"]),
            "max_retries": int(state["maxRetries"]),
            "cpu": _safe_resource(_normalize_cpu(str(state["cpu"]))),
            "memory": _safe_resource(str(state["memory"])),
            "task_count": int(state["taskCount"]),
            "ready": bool(state["ready"]),
            "reconciled": state["generation"] == state["observedGeneration"],
        },
        "values_checked": 3 + len(env) + len(deployment_checks),
        "failures": failures,
        "verdict": "PASS" if not failures else "FAIL",
    }


def _normalize_cpu(value: str) -> str:
    return "1" if value == "1000m" else value


def _safe_resource(value: str) -> str:
    return value if re.fullmatch(r"[0-9]+(?:m|Mi|Gi)?", value) else "UNRECOGNIZED"


def _parse_env(pairs: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit("env_pair_malformed")
        name, _, value = pair.partition("=")
        if not name or not value:
            raise SystemExit("env_pair_incomplete")
        if name not in SAFE_REPOINT_ENV:
            raise SystemExit("env_name_not_allowlisted")
        if name in out:
            raise SystemExit("env_name_duplicate")
        out[name] = value
    return out


def _validate_candidate(digest: str, env: dict[str, str]) -> None:
    if not DIGEST.fullmatch(digest):
        raise SystemExit("digest_invalid")
    if set(env) != REQUIRED_REPOINT_ENV:
        raise SystemExit("required_env_missing")
    if any("," in value or "\n" in value or "\r" in value for value in env.values()):
        raise SystemExit("env_value_delimiter_invalid")
    if env["RECALL_PROVIDER_RPM"] != EXPECTED_PROVIDER_RPM:
        raise SystemExit("provider_rpm_not_candidate")
    if not COMMIT.fullmatch(env["RECALL_SOURCE_COMMIT"]):
        raise SystemExit("source_commit_invalid")
    if not COMMIT.fullmatch(env["RECALL_SOURCE_TREE"]):
        raise SystemExit("source_tree_invalid")
    if env["RECALL_IMAGE_DIGEST"] != digest:
        raise SystemExit("image_digest_env_mismatch")
    for name in (
        "RECALL_COMPRESSED_PREPARATION_SHA256",
        "RECALL_EXPECTED_PROJECT_SHA256",
    ):
        if not HASH64.fullmatch(env[name]):
            raise SystemExit("provenance_hash_invalid")
    if env["RECALL_SCHEDULER_MODE"] != "COMPRESSED_V3":
        raise SystemExit("scheduler_mode_not_candidate")


def build_update_args(project: str, digest: str, env: dict[str, str]) -> list[str]:
    """Build the single atomic candidate update; callers must use the wrapper."""

    image = (
        f"{REGION}-docker.pkg.dev/{project}/recall-images/"
        f"recall-cohort-job@{digest}"
    )
    return [
        "run",
        "jobs",
        "update",
        JOB,
        f"--region={REGION}",
        f"--image={image}",
        "--update-env-vars=" + ",".join(f"{key}={value}" for key, value in env.items()),
        f"--task-timeout={EXPECTED_TIMEOUT_SECONDS}s",
        f"--max-retries={EXPECTED_MAX_RETRIES}",
        f"--cpu={EXPECTED_CPU}",
        f"--memory={EXPECTED_MEMORY}",
        f"--tasks={EXPECTED_TASK_COUNT}",
    ]


def execute_repoint(
    project: str,
    digest: str,
    env: dict[str, str],
    build_id: str,
    context_manifest_sha256: str,
    *,
    authority_fn=verify_authoritative_image,
    describe_fn=describe,
    run_fn=_run_redacted,
) -> dict[str, Any]:
    """Attempt one mutation, never retry, and always attempt one exact read-back."""

    _validate_candidate(digest, env)
    authority = authority_fn(
        project,
        build_id,
        digest,
        env["RECALL_SOURCE_COMMIT"],
        env["RECALL_SOURCE_TREE"],
        context_manifest_sha256,
    )
    if authority.get("verdict") != "PASS":
        return {
            "verdict": "FAIL",
            "failures": ["authoritative_image_binding_failed"],
            "build_metadata_matched": bool(
                authority.get("build_metadata_matched", False)
            ),
            "registry_digest_matched": bool(
                authority.get("registry_digest_matched", False)
            ),
        }
    before = observed(describe_fn(), project)
    before_report = check(before, digest, env)
    if not before["serviceAccountExpected"]:
        return {
            "verdict": "FAIL",
            "failures": ["pre_update_service_account_mismatch"],
            "mutation_outcome": "NOT_ATTEMPTED",
        }
    update = run_fn(*build_update_args(project, digest, env))
    try:
        after = observed(
            describe_fn(), project, require_secret_bindings=False
        )
    except SystemExit:
        return {
            "verdict": "FAIL",
            "mutation_outcome": "OUTCOME_UNKNOWN",
            "update_exit_code": int(update.returncode),
            "failures": ["post_update_readback_unavailable"],
            "next_step": "STOP_READBACK_REQUIRED: do not retry mutation.",
        }

    report = check(after, digest, env)
    drifted = [field for field in FROZEN if before[field] != after[field]]
    if drifted:
        if "serviceAccountFingerprint" in drifted:
            report["failures"].append("service_account_drift")
        if "nonRepointEnvFingerprint" in drifted:
            report["failures"].append("non_repoint_env_binding_drift")
        report["verdict"] = "FAIL"
    report["frozen_fields_unchanged"] = not drifted
    report["generation"] = {
        "before": before["generation"],
        "after": after["generation"],
    }
    report["update_exit_code"] = int(update.returncode)
    candidate_state_verified = report["verdict"] == "PASS"
    report["candidate_state_verified"] = candidate_state_verified
    if update.returncode != 0:
        report["mutation_outcome"] = "OUTCOME_UNKNOWN"
        report["failures"].append("update_exit_nonzero")
        report["verdict"] = "FAIL"
    elif not candidate_state_verified:
        report["mutation_outcome"] = "APPLIED_NOT_VERIFIED"
    elif before_report["verdict"] != "PASS" or (
        after["generation"] > before["generation"]
    ):
        report["mutation_outcome"] = "APPLIED_AND_VERIFIED"
    else:
        report["mutation_outcome"] = "TARGET_STATE_VERIFIED"
    report["next_step"] = (
        "STOP_READY: runtime contract and separately authorized smoke remain required."
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("verify", help="assert the deployed job matches expectations")
    v.add_argument("--expect-digest", required=True)
    v.add_argument("--expect-env", action="append", default=[])
    v.add_argument("--build-id", required=True)
    v.add_argument("--context-manifest-sha256", required=True)

    r = sub.add_parser("repoint", help="move image and env in one update, then assert")
    r.add_argument("--digest", required=True)
    r.add_argument("--env", action="append", default=[], required=True)
    r.add_argument("--build-id", required=True)
    r.add_argument("--context-manifest-sha256", required=True)
    r.add_argument("--out", default=None)

    args = parser.parse_args()

    if args.command == "verify":
        env = _parse_env(args.expect_env)
        _validate_candidate(args.expect_digest, env)
        project = resolve_project()
        authority = verify_authoritative_image(
            project,
            args.build_id,
            args.expect_digest,
            env["RECALL_SOURCE_COMMIT"],
            env["RECALL_SOURCE_TREE"],
            args.context_manifest_sha256,
        )
        if authority["verdict"] == "PASS":
            report = check(observed(describe(), project), args.expect_digest, env)
            report["build_metadata_matched"] = True
            report["registry_digest_matched"] = True
        else:
            report = {
                "verdict": "FAIL",
                "failures": ["authoritative_image_binding_failed"],
                "build_metadata_matched": bool(
                    authority.get("build_metadata_matched", False)
                ),
                "registry_digest_matched": bool(
                    authority.get("registry_digest_matched", False)
                ),
            }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["verdict"] == "PASS" else 1

    env = _parse_env(args.env)
    _validate_candidate(args.digest, env)
    project = resolve_project()
    report = execute_repoint(
        project,
        args.digest,
        env,
        args.build_id,
        args.context_manifest_sha256,
    )

    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(rendered + "\n", encoding="utf-8", newline="\n")
    print(rendered)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
