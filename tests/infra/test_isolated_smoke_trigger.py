from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "infra" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from isolated_smoke_trigger import (  # noqa: E402
    DeploymentExpectation,
    SmokePair,
    build_cloud_build_config,
    parse_execution_markers,
    parse_build_id,
    submit_smoke_pair,
    validate_job_snapshot,
)
from gcloud_redacted import scrub  # noqa: E402


COMMIT = "a" * 40
TREE = "b" * 40
PLAN = "c" * 64
BUNDLE = "d" * 64
DIGEST = "sha256:" + "e" * 64
PROJECT = "sample-project"
PROJECT_HASH = hashlib.sha256(PROJECT.encode("utf-8")).hexdigest()


def _pair() -> SmokePair:
    return SmokePair.create(
        smoke_id="smoke1234",
        source_commit=COMMIT,
        source_tree=TREE,
        plan_sha256=PLAN,
        bundle_sha256=BUNDLE,
        image_digest=DIGEST,
    )


def _job() -> dict[str, object]:
    raw = {
        "spec": {
            "template": {
                "spec": {
                    "taskCount": 1,
                    "template": {
                        "spec": {
                            "serviceAccountName": (
                                "recall-sa-cohort-job@sample-project."
                                "iam.gserviceaccount.com"
                            ),
                            "maxRetries": 0,
                            "timeoutSeconds": "28800",
                            "containers": [
                                {
                                    "image": "us-central1-docker.pkg.dev/<project-id>/recall-images/recall-cohort-job@"
                                    + DIGEST,
                                    "env": [
                                        {"name": "RECALL_PROVIDER_RPM", "value": "8"},
                                        {"name": "FULL_AUDIT_CONCURRENCY", "value": "2"},
                                        {"name": "RECALL_SOURCE_COMMIT", "value": COMMIT},
                                        {"name": "RECALL_SOURCE_TREE", "value": TREE},
                                        {"name": "RECALL_IMAGE_DIGEST", "value": DIGEST},
                                        {
                                            "name": "RECALL_EXPECTED_PROJECT_SHA256",
                                            "value": PROJECT_HASH,
                                        },
                                        {
                                            "name": "RECALL_SCHEDULER_MODE",
                                            "value": "COMPRESSED_V3",
                                        },
                                        {
                                            "name": "RECALL_TOOL_CAPABILITY_SECRET_B64",
                                            "valueFrom": {
                                                "secretKeyRef": {
                                                    "name": "capability-secret",
                                                    "key": "latest",
                                                }
                                            },
                                        },
                                        {
                                            "name": "RECALL_NCBI_TOOL",
                                            "valueSource": {
                                                "secretKeyRef": {
                                                    "secret": "tool-secret",
                                                    "version": "latest",
                                                }
                                            },
                                        },
                                        {
                                            "name": "RECALL_NCBI_EMAIL",
                                            "valueSource": {
                                                "secretKeyRef": {
                                                    "secret": "email-secret",
                                                    "version": "3",
                                                }
                                            },
                                        },
                                        {
                                            "name": "RECALL_COMPRESSED_PREPARATION_SHA256",
                                            "value": BUNDLE,
                                        },
                                    ],
                                    "resources": {
                                        "limits": {"cpu": "1", "memory": "512Mi"}
                                    },
                                }
                            ],
                        }
                    },
                }
            }
        }
    }
    return json.loads(scrub(json.dumps(raw), PROJECT, None, None))


def test_generated_build_is_source_less_machine_trigger_with_two_explicit_overrides() -> None:
    config = build_cloud_build_config(
        _pair(),
        machine_service_account="smoke-runner@sample-project.iam.gserviceaccount.com",
    )

    encoded = json.dumps(config, sort_keys=True)
    assert config["serviceAccount"].endswith(
        "/serviceAccounts/smoke-runner@sample-project.iam.gserviceaccount.com"
    )
    assert encoded.count("run jobs execute") == 2
    assert encoded.count("--args=") == 2
    assert encoded.count("--update-env-vars=") == 2
    assert "--wait" in encoded
    assert "--smoke-mode,positive" in encoded
    assert "--smoke-mode,negative" in encoded
    assert "RECALL_SMOKE_EXPECTED_PLAN_SHA256=" + PLAN in encoded
    assert "RECALL_SMOKE_EXPECTED_IMAGE_DIGEST=" + DIGEST in encoded
    assert "RECALL_SMOKE_JOB_MAX_RETRIES=0" in encoded
    assert _pair().positive_prefix in encoded
    assert _pair().negative_prefix in encoded
    assert "c6" not in encoded.lower()
    assert "final" not in encoded.lower()
    assert "exit 93" not in encoded
    assert encoded.count("RECALL_SMOKE_TERMINAL_RC") == 2


@pytest.mark.parametrize(
    "smoke_id",
    ["short", "UPPERCASE1", "contains-hyphen", "a" * 33, "final456x"],
)
def test_smoke_id_rejects_unsafe_or_final_shaped_values(smoke_id: str) -> None:
    with pytest.raises(ValueError):
        SmokePair.create(
            smoke_id=smoke_id,
            source_commit=COMMIT,
            source_tree=TREE,
            plan_sha256=PLAN,
            bundle_sha256=BUNDLE,
            image_digest=DIGEST,
        )


def test_job_preflight_accepts_only_exact_candidate_config() -> None:
    expectation = DeploymentExpectation.from_pair(_pair(), project=PROJECT)
    assert validate_job_snapshot(_job(), expectation) == ()

    changed = _job()
    changed["spec"]["template"]["spec"]["template"]["spec"]["maxRetries"] = 1  # type: ignore[index]
    assert validate_job_snapshot(changed, expectation) == ("max_retries_mismatch",)


@pytest.mark.parametrize("cpu", ["1", "1000m"])
def test_job_preflight_accepts_equivalent_single_cpu_forms(cpu: str) -> None:
    job = _job()
    spec = job["spec"]["template"]["spec"]["template"]["spec"]  # type: ignore[index]
    container = spec["containers"][0]
    container["resources"]["limits"]["cpu"] = cpu

    expectation = DeploymentExpectation.from_pair(_pair(), project=PROJECT)
    assert validate_job_snapshot(job, expectation) == ()


@pytest.mark.parametrize(
    "cpu",
    ["999m", "1001m", "2", "", "1.0", "1000M", None, {"value": "1"}],
)
def test_job_preflight_rejects_non_equivalent_or_malformed_cpu(cpu: object) -> None:
    job = _job()
    spec = job["spec"]["template"]["spec"]["template"]["spec"]  # type: ignore[index]
    container = spec["containers"][0]
    container["resources"]["limits"]["cpu"] = cpu

    expectation = DeploymentExpectation.from_pair(_pair(), project=PROJECT)
    assert validate_job_snapshot(job, expectation) == ("cpu_mismatch",)


def test_job_preflight_fails_closed_on_provenance_or_candidate_drift() -> None:
    expectation = DeploymentExpectation.from_pair(_pair(), project=PROJECT)
    changed = _job()
    env = changed["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]["env"]  # type: ignore[index]
    env[:] = [item for item in env if item["name"] != "RECALL_SOURCE_TREE"]
    failures = validate_job_snapshot(changed, expectation)
    assert failures == ("source_tree_missing",)


@pytest.mark.parametrize(
    ("mutation", "failure"),
    [
        ("scheduler", "scheduler_mode_mismatch"),
        ("plan", "expected_project_sha256_mismatch"),
        ("service", "service_account_mismatch"),
        ("secret", "required_secret_binding_missing"),
    ],
)
def test_job_preflight_rejects_candidate_identity_or_binding_drift(
    mutation: str, failure: str
) -> None:
    job = _job()
    spec = job["spec"]["template"]["spec"]["template"]["spec"]  # type: ignore[index]
    env = spec["containers"][0]["env"]  # type: ignore[index]
    if mutation == "scheduler":
        next(row for row in env if row["name"] == "RECALL_SCHEDULER_MODE")["value"] = "LEGACY_DAYN"
    elif mutation == "plan":
        next(row for row in env if row["name"] == "RECALL_EXPECTED_PROJECT_SHA256")["value"] = "0" * 64
    elif mutation == "service":
        spec["serviceAccountName"] = "other@<project>.iam.gserviceaccount.com"
    else:
        row = next(row for row in env if row["name"] == "RECALL_NCBI_EMAIL")
        row.clear()
        row.update({"name": "RECALL_NCBI_EMAIL", "value": "not-secret-backed"})
    failures = validate_job_snapshot(
        job,
        DeploymentExpectation.from_pair(_pair(), project=PROJECT),
    )
    assert failure in failures


def test_project_hash_is_derived_from_project_not_plan() -> None:
    expectation = DeploymentExpectation.from_pair(_pair(), project=PROJECT)
    assert PROJECT_HASH != PLAN
    assert expectation.expected_project_sha256 == PROJECT_HASH
    job = _job()
    env = job["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]["env"]  # type: ignore[index]
    next(row for row in env if row["name"] == "RECALL_EXPECTED_PROJECT_SHA256")["value"] = PLAN
    assert "expected_project_sha256_mismatch" in validate_job_snapshot(
        job, expectation
    )


def test_execution_marker_parser_requires_exactly_one_per_mode_and_never_returns_logs() -> None:
    markers = parse_execution_markers(
        "noise\nRECALL_SMOKE_EXECUTION positive recall-cohort-daily-a1b2c\n"
        "RECALL_SMOKE_EXECUTION negative recall-cohort-daily-d4e5f\nmore noise\n"
    )
    assert markers == {
        "positive": "recall-cohort-daily-a1b2c",
        "negative": "recall-cohort-daily-d4e5f",
    }
    prefixed = parse_execution_markers(
        'Step #0 - "isolated-smoke-pair": RECALL_SMOKE_EXECUTION positive '
        "recall-cohort-daily-a1b2c\n"
        'Step #0 - "isolated-smoke-pair": RECALL_SMOKE_EXECUTION negative '
        "recall-cohort-daily-d4e5f\n"
    )
    assert prefixed == markers

    with pytest.raises(ValueError, match="execution_markers_invalid"):
        parse_execution_markers(
            "RECALL_SMOKE_EXECUTION positive recall-cohort-daily-a1b2c\n"
            "RECALL_SMOKE_EXECUTION positive recall-cohort-daily-other\n"
        )


def test_build_id_parser_requires_one_exact_uuid() -> None:
    build_id = "12345678-1234-1234-1234-123456789abc"
    assert parse_build_id(build_id + "\n") == build_id
    with pytest.raises(ValueError, match="build_id_invalid"):
        parse_build_id(build_id + "\n" + "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def test_submit_uses_redacted_runner_no_source_and_returns_only_aliases(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []

    def run_fn(*args: str, timeout_seconds: int = 600) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:3] == ("run", "jobs", "describe"):
            return subprocess.CompletedProcess([], 0, json.dumps(_job()), "")
        if args[:2] == ("builds", "submit"):
            assert "--no-source" in args
            assert any(item.startswith("--service-account=projects/") for item in args)
            assert timeout_seconds == 60_600
            return subprocess.CompletedProcess(
                [], 0, "12345678-1234-1234-1234-123456789abc\n", ""
            )
        if args[:2] == ("builds", "describe"):
            return subprocess.CompletedProcess(
                [],
                0,
                json.dumps(
                    {
                        "id": "12345678-1234-1234-1234-123456789abc",
                        "status": "SUCCESS",
                    }
                ),
                "",
            )
        assert args[:2] == ("builds", "log")
        return subprocess.CompletedProcess(
            [], 0,
            "RECALL_SMOKE_EXECUTION positive recall-cohort-daily-a1b2c\n"
            "RECALL_SMOKE_EXECUTION negative recall-cohort-daily-d4e5f\n", ""
        )

    report = submit_smoke_pair(
        _pair(),
        machine_service_account_local_part="smoke-runner",
        project="sample-project",
        receipt_path=tmp_path / "receipt.json",
        run_fn=run_fn,
    )
    assert report == {
        "verdict": "READY_FOR_COLLECTION",
        "execution_count": 2,
        "positive_execution_alias": report["positive_execution_alias"],
        "negative_execution_alias": report["negative_execution_alias"],
    }
    assert "recall-cohort-daily" not in json.dumps(report)
    assert len(calls) == 4
    receipt = json.loads((tmp_path / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["positive_execution"] == "recall-cohort-daily-a1b2c"
    assert receipt["negative_execution"] == "recall-cohort-daily-d4e5f"
    assert receipt["expected_project_sha256"] == PROJECT_HASH


def test_submit_stops_before_build_when_job_preflight_fails(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []
    wrong = _job()
    wrong["spec"]["template"]["spec"]["template"]["spec"]["maxRetries"] = 1  # type: ignore[index]

    def run_fn(*args: str, timeout_seconds: int = 600) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess([], 0, json.dumps(wrong), "")

    with pytest.raises(RuntimeError, match="job_preflight_failed:max_retries_mismatch"):
        submit_smoke_pair(
            _pair(),
            machine_service_account_local_part="smoke-runner",
            project="sample-project",
            receipt_path=tmp_path / "receipt.json",
            run_fn=run_fn,
        )
    assert len(calls) == 1
    assert not (tmp_path / "receipt.json").exists()
