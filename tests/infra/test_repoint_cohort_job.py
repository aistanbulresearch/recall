from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "infra" / "scripts" / "repoint_cohort_job.py"
PROJECT = "project-canary-123"
BUILD_ID = "12345678-1234-1234-1234-1234567890ab"
CONTEXT_SHA = "e" * 64


def _load_repoint():
    spec = importlib.util.spec_from_file_location("repoint_cohort_job", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _job(
    *,
    rpm: str = "8",
    retries: int = 0,
    cpu: str = "1",
    memory: str = "512Mi",
    task_count: int = 1,
    service_project: str = "<project>",
):
    return {
        "metadata": {"generation": 19},
        "spec": {
            "template": {
                "spec": {
                    "taskCount": task_count,
                    "template": {
                        "spec": {
                            "serviceAccountName": (
                                f"recall-sa-cohort-job@{service_project}."
                                "iam.gserviceaccount.com"
                            ),
                            "timeoutSeconds": 28800,
                            "maxRetries": retries,
                            "containers": [
                                {
                                    "image": "region-docker.pkg.dev/project-canary-123/repo/job@sha256:"
                                    + "a" * 64,
                                    "env": [
                                        {"name": "RECALL_PROVIDER_RPM", "value": rpm},
                                        {"name": "RECALL_SOURCE_COMMIT", "value": "b" * 40},
                                        {"name": "RECALL_SOURCE_TREE", "value": "f" * 40},
                                        {
                                            "name": "RECALL_IMAGE_DIGEST",
                                            "value": "sha256:" + "a" * 64,
                                        },
                                        {
                                            "name": "RECALL_COMPRESSED_PREPARATION_SHA256",
                                            "value": "c" * 64,
                                        },
                                        {
                                            "name": "RECALL_EXPECTED_PROJECT_SHA256",
                                            "value": "d" * 64,
                                        },
                                        {
                                            "name": "RECALL_SCHEDULER_MODE",
                                            "value": "COMPRESSED_V3",
                                        },
                                        {
                                            "name": "RECALL_TOOL_CAPABILITY_SECRET_B64",
                                            "valueFrom": {
                                                "secretKeyRef": {
                                                    "name": "secret-canary-capability",
                                                    "key": "latest",
                                                }
                                            },
                                        },
                                        {
                                            "name": "RECALL_NCBI_TOOL",
                                            "valueSource": {
                                                "secretKeyRef": {
                                                    "secret": "secret-canary-tool",
                                                    "version": "latest",
                                                }
                                            },
                                        },
                                        {
                                            "name": "RECALL_NCBI_EMAIL",
                                            "valueSource": {
                                                "secretKeyRef": {
                                                    "secret": "secret-canary-email",
                                                    "version": "3",
                                                }
                                            },
                                        },
                                        {"name": "PRIVATE_TOKEN", "value": "token-canary-abc"},
                                        {"name": "PRIVATE_PROJECT", "value": "project-canary-123"},
                                        {"name": "PRIVATE_NUMBER", "value": "123456789012"},
                                        {"name": "PRIVATE_OWNER", "value": "owner@example.invalid"},
                                        {"name": "PRIVATE_BILLING", "value": "billing-canary-456"},
                                        {"name": "PRIVATE_SECRET", "value": "secret-canary-789"},
                                    ],
                                    "resources": {"limits": {"cpu": cpu, "memory": memory}},
                                }
                            ],
                        }
                    },
                }
            }
        },
        "status": {
            "observedGeneration": 19,
            "conditions": [{"type": "Ready", "status": "True"}],
        },
    }


def _expected_env() -> dict[str, str]:
    return {
        "RECALL_PROVIDER_RPM": "8",
        "RECALL_SOURCE_COMMIT": "b" * 40,
        "RECALL_SOURCE_TREE": "f" * 40,
        "RECALL_IMAGE_DIGEST": "sha256:" + "a" * 64,
        "RECALL_COMPRESSED_PREPARATION_SHA256": "c" * 64,
        "RECALL_EXPECTED_PROJECT_SHA256": "d" * 64,
        "RECALL_SCHEDULER_MODE": "COMPRESSED_V3",
    }


def _authority_pass() -> dict[str, object]:
    return {
        "verdict": "PASS",
        "build_metadata_matched": True,
        "registry_digest_matched": True,
        "failures": [],
    }


def test_observed_and_check_cover_exact_candidate_without_value_leak() -> None:
    repoint = _load_repoint()
    state = repoint.observed(_job(), PROJECT)

    report = repoint.check(state, "sha256:" + "a" * 64, _expected_env())
    rendered = json.dumps(report, sort_keys=True)

    assert report["verdict"] == "PASS"
    assert report["deployment"] == {
        "timeout_seconds": 28800,
        "max_retries": 0,
        "cpu": "1",
        "memory": "512Mi",
        "task_count": 1,
        "ready": True,
        "reconciled": True,
    }
    assert report["env_checks"] == {
        name: {"present": True, "matched": True} for name in sorted(_expected_env())
    }
    for canary in (
        "project-canary-123",
        "123456789012",
        "owner@example.invalid",
        "runtime@example.invalid",
        "token-canary-abc",
        "billing-canary-456",
        "secret-canary-789",
        "b" * 40,
    ):
        assert canary not in rendered


@pytest.mark.parametrize(
    ("job", "failure"),
    [
        (_job(rpm="6"), "env_mismatch:RECALL_PROVIDER_RPM"),
        (_job(retries=1), "max_retries_mismatch"),
        (_job(cpu="2"), "cpu_mismatch"),
        (_job(memory="1Gi"), "memory_mismatch"),
    ],
)
def test_check_fails_closed_for_each_candidate_drift(job, failure: str) -> None:
    repoint = _load_repoint()

    report = repoint.check(
        repoint.observed(job, PROJECT), "sha256:" + "a" * 64, _expected_env()
    )

    assert report["verdict"] == "FAIL"
    assert failure in report["failures"]


def test_repoint_command_is_atomic_and_uses_only_redacted_wrapper(monkeypatch) -> None:
    repoint = _load_repoint()
    calls: list[list[str]] = []

    class SuccessfulProcess:
        pid = 2121
        returncode = 0

        def communicate(self, timeout):
            assert timeout == repoint.GCLOUD_TIMEOUT_SECONDS
            return "{}", ""

    def fake_start(command):
        calls.append(command)
        return SuccessfulProcess()

    monkeypatch.setattr(repoint, "_start_wrapper", fake_start)
    repoint._run_redacted(
        "run",
        "jobs",
        "update",
        repoint.JOB,
        "--task-timeout=28800s",
        "--max-retries=0",
        "--cpu=1",
        "--memory=512Mi",
    )

    command = calls[0]
    assert command[0] == repoint.sys.executable
    assert Path(command[1]).resolve() == repoint.REDACTED_WRAPPER.resolve()
    assert command[2:4] == ["--quiet", "run"]
    assert "gcloud" not in command[:2]


def test_completed_process_args_are_sanitized(monkeypatch) -> None:
    repoint = _load_repoint()

    class SuccessfulProcess:
        pid = 2222
        returncode = 0

        def communicate(self, timeout):
            return "{}", ""

    monkeypatch.setattr(repoint, "_start_wrapper", lambda _command: SuccessfulProcess())

    result = repoint._run_redacted(
        "run", "jobs", "describe", "project-canary-123"
    )

    assert result.args == ["redacted-wrapper"]


def test_atomic_update_builder_contains_every_fixed_candidate_field() -> None:
    repoint = _load_repoint()
    digest = "sha256:" + "a" * 64
    env = _expected_env()

    args = repoint.build_update_args("project-canary-123", digest, env)

    assert args[:4] == ["run", "jobs", "update", repoint.JOB]
    assert args.count("--task-timeout=28800s") == 1
    assert args.count("--max-retries=0") == 1
    assert args.count("--cpu=1") == 1
    assert args.count("--memory=512Mi") == 1
    assert args.count("--tasks=1") == 1
    assert sum(value.startswith("--image=") for value in args) == 1
    assert sum(value.startswith("--update-env-vars=") for value in args) == 1


def _build_metadata(
    *, source_commit: str = "b" * 40, project_segment: str = "<project>"
) -> str:
    return json.dumps(
        {
            "id": BUILD_ID,
            "status": "SUCCESS",
            "substitutions": {
                "_TAG": source_commit,
                "_REGION": "us-central1",
                "_REPO": "recall-images",
                "_SOURCE_COMMIT": source_commit,
                "_SOURCE_TREE": "f" * 40,
                "_CONTEXT_MANIFEST_SHA256": CONTEXT_SHA,
            },
            "results": {
                "images": [
                    {
                        "name": (
                            f"us-central1-docker.pkg.dev/{project_segment}/recall-images/"
                            f"recall-cohort-job:{source_commit}"
                        ),
                        "digest": "sha256:" + "a" * 64,
                    }
                ]
            },
        }
    )


def test_authoritative_build_and_registry_binding_passes_without_path_output() -> None:
    repoint = _load_repoint()
    wrapper = sys.modules["gcloud_redacted"]
    calls: list[tuple[str, ...]] = []

    def run(*args: str, **_kwargs):
        calls.append(args)
        if args[:2] == ("builds", "describe"):
            return subprocess.CompletedProcess(
                ["redacted-wrapper"],
                0,
                wrapper.scrub(
                    _build_metadata(project_segment=PROJECT), PROJECT, None, None
                ),
                "",
            )
        return subprocess.CompletedProcess(
            ["redacted-wrapper"], 0, "sha256:" + "a" * 64 + "\n", ""
        )

    report = repoint.verify_authoritative_image(
        PROJECT,
        BUILD_ID,
        "sha256:" + "a" * 64,
        "b" * 40,
        "f" * 40,
        CONTEXT_SHA,
        run_fn=run,
    )
    rendered = json.dumps(report, sort_keys=True)

    assert report["verdict"] == "PASS"
    assert len(calls) == 2
    assert "project-canary-123" not in rendered
    assert "docker.pkg.dev" not in rendered


def test_actual_wrapper_scrubbed_service_account_is_accepted() -> None:
    repoint = _load_repoint()
    wrapper = sys.modules["gcloud_redacted"]
    raw = json.dumps(_job(service_project=PROJECT))
    scrubbed = json.loads(wrapper.scrub(raw, PROJECT, None, None))

    state = repoint.observed(scrubbed, PROJECT)

    assert state["serviceAccountExpected"] is True


def test_unexpected_pre_state_service_account_blocks_update() -> None:
    repoint = _load_repoint()
    job = _job()
    job["spec"]["template"]["spec"]["template"]["spec"][
        "serviceAccountName"
    ] = "unexpected@<project>.iam.gserviceaccount.com"
    calls = {"update": 0}

    def update(*_args):
        calls["update"] += 1
        return subprocess.CompletedProcess([], 0, "", "")

    report = repoint.execute_repoint(
        PROJECT,
        "sha256:" + "a" * 64,
        _expected_env(),
        BUILD_ID,
        CONTEXT_SHA,
        authority_fn=lambda *_args, **_kwargs: _authority_pass(),
        describe_fn=lambda: job,
        run_fn=update,
    )

    assert report == {
        "verdict": "FAIL",
        "failures": ["pre_update_service_account_mismatch"],
        "mutation_outcome": "NOT_ATTEMPTED",
    }
    assert calls["update"] == 0


def test_forged_consistent_claim_fails_before_job_read_or_mutation() -> None:
    repoint = _load_repoint()
    calls = {"job_describe": 0, "update": 0}

    def authority(*_args, **_kwargs):
        return {
            "verdict": "FAIL",
            "build_metadata_matched": False,
            "registry_digest_matched": False,
            "failures": ["build_source_commit_mismatch"],
        }

    def job_describe():
        calls["job_describe"] += 1
        return _job()

    def update(*_args):
        calls["update"] += 1
        return subprocess.CompletedProcess([], 0, "", "")

    report = repoint.execute_repoint(
        PROJECT,
        "sha256:" + "a" * 64,
        _expected_env(),
        BUILD_ID,
        CONTEXT_SHA,
        authority_fn=authority,
        describe_fn=job_describe,
        run_fn=update,
    )

    assert report["verdict"] == "FAIL"
    assert report["failures"] == ["authoritative_image_binding_failed"]
    assert calls == {"job_describe": 0, "update": 0}


def test_required_secret_binding_missing_fails_without_leak() -> None:
    repoint = _load_repoint()
    job = _job()
    env = job["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]["env"]
    env[:] = [
        item for item in env if item["name"] != "RECALL_NCBI_EMAIL"
    ]

    with pytest.raises(SystemExit, match="required_secret_binding_missing"):
        repoint.observed(job, PROJECT)


def test_secret_key_ref_drift_fails_post_readback_without_value_leak() -> None:
    repoint = _load_repoint()
    before = _job()
    after = copy.deepcopy(before)
    after_env = after["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]["env"]
    for item in after_env:
        if item["name"] == "RECALL_NCBI_EMAIL":
            item["valueSource"]["secretKeyRef"]["version"] = "4"
    after["metadata"]["generation"] = 20
    after["status"]["observedGeneration"] = 20
    states = iter((before, after))

    report = repoint.execute_repoint(
        PROJECT,
        "sha256:" + "a" * 64,
        _expected_env(),
        BUILD_ID,
        CONTEXT_SHA,
        authority_fn=lambda *_args, **_kwargs: _authority_pass(),
        describe_fn=lambda: next(states),
        run_fn=lambda *_args: subprocess.CompletedProcess([], 0, "", ""),
    )
    rendered = json.dumps(report, sort_keys=True)

    assert report["verdict"] == "FAIL"
    assert "non_repoint_env_binding_drift" in report["failures"]
    for canary in ("secret-canary-email", "secret-canary-tool", "latest"):
        assert canary not in rendered


def test_secret_key_ref_removal_fails_exact_post_readback_without_leak() -> None:
    repoint = _load_repoint()
    before = _job()
    after = copy.deepcopy(before)
    after_env = after["spec"]["template"]["spec"]["template"]["spec"][
        "containers"
    ][0]["env"]
    after_env[:] = [
        item for item in after_env if item["name"] != "RECALL_NCBI_TOOL"
    ]
    after["metadata"]["generation"] = 20
    after["status"]["observedGeneration"] = 20
    states = iter((before, after))

    report = repoint.execute_repoint(
        PROJECT,
        "sha256:" + "a" * 64,
        _expected_env(),
        BUILD_ID,
        CONTEXT_SHA,
        authority_fn=lambda *_args, **_kwargs: _authority_pass(),
        describe_fn=lambda: next(states),
        run_fn=lambda *_args: subprocess.CompletedProcess([], 0, "", ""),
    )
    rendered = json.dumps(report, sort_keys=True)

    assert report["verdict"] == "FAIL"
    assert "required_secret_binding_missing" in report["failures"]
    assert "non_repoint_env_binding_drift" in report["failures"]
    assert "secret-canary-tool" not in rendered


def test_candidate_validation_rejects_non_candidate_without_value_leak(capsys) -> None:
    repoint = _load_repoint()
    env = _expected_env()
    env["RECALL_PROVIDER_RPM"] = "secret-canary-789"

    with pytest.raises(SystemExit, match="provider_rpm_not_candidate"):
        repoint._validate_candidate("sha256:" + "a" * 64, env)

    captured = capsys.readouterr()
    assert "secret-canary-789" not in captured.out + captured.err


def test_candidate_validation_rejects_missing_required_env_with_extra_field() -> None:
    repoint = _load_repoint()
    env = _expected_env()
    del env["RECALL_IMAGE_DIGEST"]
    env["RECALL_SCHEDULER_MODE"] = "COMPRESSED_V3"

    with pytest.raises(SystemExit, match="required_env_missing"):
        repoint._validate_candidate("sha256:" + "a" * 64, env)


def test_env_parser_rejects_unallowlisted_name_without_echoing_value(capsys) -> None:
    repoint = _load_repoint()

    with pytest.raises(SystemExit, match="env_name_not_allowlisted"):
        repoint._parse_env(["PRIVATE_TOKEN=token-canary-abc"])

    captured = capsys.readouterr()
    assert "token-canary-abc" not in captured.out + captured.err


def test_env_parser_rejects_duplicate_and_delimiter_injection() -> None:
    repoint = _load_repoint()

    with pytest.raises(SystemExit, match="env_name_duplicate"):
        repoint._parse_env(["RECALL_PROVIDER_RPM=8", "RECALL_PROVIDER_RPM=6"])

    env = _expected_env()
    env["RECALL_SCHEDULER_MODE"] = "COMPRESSED_V3,PRIVATE_TOKEN=token-canary-abc"
    with pytest.raises(SystemExit, match="env_value_delimiter_invalid"):
        repoint._validate_candidate("sha256:" + "a" * 64, env)


def test_malformed_describe_value_fails_with_typed_non_sensitive_code(capsys) -> None:
    repoint = _load_repoint()
    job = _job()
    job["spec"]["template"]["spec"]["template"]["spec"]["timeoutSeconds"] = (
        "secret-canary-789"
    )

    with pytest.raises(SystemExit, match="describe_contract_invalid"):
        repoint.observed(job, PROJECT)

    captured = capsys.readouterr()
    assert "secret-canary-789" not in captured.out + captured.err


def test_timeout_cleanup_is_scoped_and_error_is_non_sensitive(monkeypatch, capsys) -> None:
    repoint = _load_repoint()
    cleaned: list[int] = []

    class TimeoutProcess:
        pid = 4242

        def communicate(self, timeout):
            raise subprocess.TimeoutExpired("secret-canary-789", timeout)

    monkeypatch.setattr(repoint, "_start_wrapper", lambda _command: TimeoutProcess())
    def clean(process):
        cleaned.append(process.pid)
        return True

    monkeypatch.setattr(repoint, "_terminate_process_tree", clean)

    result = repoint._run_redacted("run", "jobs", "describe", repoint.JOB)

    captured = capsys.readouterr()
    assert cleaned == [4242]
    assert result.returncode == 124
    assert "secret-canary-789" not in captured.out + captured.err


def test_wrapper_failure_never_reemits_child_streams(monkeypatch, capsys) -> None:
    repoint = _load_repoint()

    class FailedProcess:
        pid = 3131

        def communicate(self, timeout):
            return (
                "project-canary-123 123456789012 owner@example.invalid",
                "runtime@example.invalid billing-canary-456 secret-canary-789 token-canary-abc",
            )

        returncode = 7

    monkeypatch.setattr(repoint, "_start_wrapper", lambda _command: FailedProcess())

    result = repoint._run_redacted("run", "jobs", "describe", repoint.JOB)
    captured = capsys.readouterr()

    assert result.returncode == 7
    assert result.stdout == ""
    assert result.stderr == ""
    rendered = captured.out + captured.err
    for canary in (
        "project-canary-123",
        "123456789012",
        "owner@example.invalid",
        "runtime@example.invalid",
        "billing-canary-456",
        "secret-canary-789",
        "token-canary-abc",
    ):
        assert canary not in rendered


def test_nonzero_update_keeps_mutation_unknown_after_exact_readback() -> None:
    repoint = _load_repoint()
    calls = {"describe": 0, "update": 0}

    def describe_once_each():
        calls["describe"] += 1
        return _job()

    def failed_update(*_args):
        calls["update"] += 1
        return subprocess.CompletedProcess([], 7, "", "")

    report = repoint.execute_repoint(
        PROJECT,
        "sha256:" + "a" * 64,
        _expected_env(),
        BUILD_ID,
        CONTEXT_SHA,
        authority_fn=lambda *_args, **_kwargs: _authority_pass(),
        describe_fn=describe_once_each,
        run_fn=failed_update,
    )

    assert calls == {"describe": 2, "update": 1}
    assert report["verdict"] == "FAIL"
    assert report["mutation_outcome"] == "OUTCOME_UNKNOWN"
    assert report["candidate_state_verified"] is True
    assert report["update_exit_code"] == 7
    assert report["failures"] == ["update_exit_nonzero"]


def test_post_update_readback_failure_is_outcome_unknown_and_no_retry() -> None:
    repoint = _load_repoint()
    calls = {"describe": 0, "update": 0}

    def describe_then_fail():
        calls["describe"] += 1
        if calls["describe"] == 1:
            return _job()
        raise SystemExit("describe_failed:124")

    def timed_out_update(*_args):
        calls["update"] += 1
        return subprocess.CompletedProcess([], 124, "", "")

    report = repoint.execute_repoint(
        PROJECT,
        "sha256:" + "a" * 64,
        _expected_env(),
        BUILD_ID,
        CONTEXT_SHA,
        authority_fn=lambda *_args, **_kwargs: _authority_pass(),
        describe_fn=describe_then_fail,
        run_fn=timed_out_update,
    )

    assert calls == {"describe": 2, "update": 1}
    assert report == {
        "verdict": "FAIL",
        "mutation_outcome": "OUTCOME_UNKNOWN",
        "update_exit_code": 124,
        "failures": ["post_update_readback_unavailable"],
        "next_step": "STOP_READBACK_REQUIRED: do not retry mutation.",
    }


def test_atomic_update_corrects_preexisting_task_count_drift() -> None:
    repoint = _load_repoint()
    states = iter((_job(task_count=2), _job(task_count=1)))

    report = repoint.execute_repoint(
        PROJECT,
        "sha256:" + "a" * 64,
        _expected_env(),
        BUILD_ID,
        CONTEXT_SHA,
        authority_fn=lambda *_args, **_kwargs: _authority_pass(),
        describe_fn=lambda: next(states),
        run_fn=lambda *_args: subprocess.CompletedProcess([], 0, "", ""),
    )

    assert report["verdict"] == "PASS"
    assert report["deployment"]["task_count"] == 1
    assert report["frozen_fields_unchanged"] is True
    assert report["mutation_outcome"] == "APPLIED_AND_VERIFIED"


def test_windows_tree_cleanup_waits_and_reaps(monkeypatch) -> None:
    repoint = _load_repoint()
    taskkill: list[list[str]] = []
    waits: list[int] = []

    class Process:
        pid = 5151

        def wait(self, timeout):
            waits.append(timeout)
            return 0

    monkeypatch.setattr(repoint.os, "name", "nt")
    monkeypatch.setattr(
        repoint.subprocess,
        "run",
        lambda command, **_kwargs: (
            taskkill.append(command) or subprocess.CompletedProcess(command, 0)
        ),
    )

    cleaned = repoint._terminate_process_tree(Process())

    assert cleaned is True
    assert taskkill == [["taskkill", "/PID", "5151", "/T", "/F"]]
    assert waits == [10]


def test_cleanup_force_kills_and_reaps_after_grace_timeout(monkeypatch) -> None:
    repoint = _load_repoint()
    waits: list[int] = []
    killed: list[bool] = []

    class Process:
        pid = 6161

        def wait(self, timeout):
            waits.append(timeout)
            if len(waits) == 1:
                raise subprocess.TimeoutExpired("hidden-canary", timeout)
            return 0

        def kill(self):
            killed.append(True)

    monkeypatch.setattr(repoint.os, "name", "nt")
    monkeypatch.setattr(
        repoint.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0),
    )

    cleaned = repoint._terminate_process_tree(Process())

    assert cleaned is True
    assert waits == [10, 10]
    assert killed == [True]


def test_cleanup_final_timeout_returns_typed_status_without_argv_leak(monkeypatch) -> None:
    repoint = _load_repoint()

    class Process:
        pid = 7171
        args = ["--image=project-canary-123", "owner@example.invalid"]

        def wait(self, timeout):
            raise subprocess.TimeoutExpired(self.args, timeout)

        def kill(self):
            return None

    monkeypatch.setattr(repoint.os, "name", "nt")
    monkeypatch.setattr(
        repoint.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0),
    )

    assert repoint._terminate_process_tree(Process()) is False


def test_windows_taskkill_timeout_falls_back_and_returns_unverified(monkeypatch) -> None:
    repoint = _load_repoint()
    waits: list[int] = []
    killed: list[bool] = []

    class Process:
        pid = 8181

        def wait(self, timeout):
            waits.append(timeout)
            return 0

        def kill(self):
            killed.append(True)

    def timed_out(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["taskkill", "8181"], 30)

    monkeypatch.setattr(repoint.os, "name", "nt")
    monkeypatch.setattr(repoint.subprocess, "run", timed_out)

    assert repoint._terminate_process_tree(Process()) is False
    assert killed == [True]
    assert waits == [10]


def test_windows_taskkill_nonzero_keeps_tree_cleanup_unverified(monkeypatch) -> None:
    repoint = _load_repoint()
    killed: list[bool] = []

    class Process:
        pid = 9191

        def wait(self, timeout):
            return 0

        def kill(self):
            killed.append(True)

    monkeypatch.setattr(repoint.os, "name", "nt")
    monkeypatch.setattr(
        repoint.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 7),
    )

    assert repoint._terminate_process_tree(Process()) is False
    assert killed == [True]
