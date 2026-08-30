from __future__ import annotations

import importlib.util
import hashlib
import inspect
import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "infra" / "scripts" / "final_owner_release_trigger.py"
PROJECT = "project-canary-123"
SOURCE = "a" * 40
TREE = "b" * 40
PLAN = "c" * 64
BUNDLE = "d" * 64
DIGEST = "sha256:" + "e" * 64
PROJECT_HASH = hashlib.sha256(PROJECT.encode("utf-8")).hexdigest()
COORDINATOR_COMMIT = "1" * 40
COORDINATOR_TREE = "2" * 40
RECOVERY_ATTEMPT_ID = "123e4567-e89b-12d3-a456-426614174000"
RECOVERY_REASON = "RECOVER_CANCELLED_FINAL_EXECUTION_APPEND_ONLY"
PREVIOUS_EXECUTION = "recall-cohort-daily-5tqxh"
PREVIOUS_SOURCE = "3" * 40
PREVIOUS_DIGEST = "sha256:" + "4" * 64
PREVIOUS_SNAPSHOT = "5" * 64


def _load():
    spec = importlib.util.spec_from_file_location("final_owner_release_trigger", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module._real_verify_coordinator_checkout = module.verify_coordinator_checkout
    module.verify_coordinator_checkout = lambda _identity: ()
    return module


def _identity(trigger, **overrides):
    values = {
        "owner_start_attempt_id": "ownerstart01",
        "deployed_source_commit": SOURCE,
        "deployed_source_tree": TREE,
        "deployed_image_digest": DIGEST,
        "plan_sha256": PLAN,
        "bundle_sha256": BUNDLE,
        "expected_project_sha256": PROJECT_HASH,
        "expected_generation": 23,
        "coordinator_commit": COORDINATOR_COMMIT,
        "coordinator_tree": COORDINATOR_TREE,
        "coordinator_trigger_sha256": trigger.current_trigger_sha256(),
        "recovery_attempt_id": RECOVERY_ATTEMPT_ID,
        "owner_recovery_reason": RECOVERY_REASON,
        "recovery_previous_execution_id": PREVIOUS_EXECUTION,
        "recovery_previous_source_commit": PREVIOUS_SOURCE,
        "recovery_previous_image_digest": PREVIOUS_DIGEST,
        "recovery_previous_snapshot_sha256": PREVIOUS_SNAPSHOT,
    }
    values.update(overrides)
    return trigger.FinalLaunchIdentity.create(**values)


def _cli_args(trigger) -> list[str]:
    identity = _identity(trigger)
    return [
        "submit",
        "--owner-start-attempt-id",
        identity.owner_start_attempt_id,
        "--deployed-source-commit",
        identity.deployed_source_commit,
        "--deployed-source-tree",
        identity.deployed_source_tree,
        "--deployed-image-digest",
        identity.deployed_image_digest,
        "--plan-sha256",
        identity.plan_sha256,
        "--bundle-sha256",
        identity.bundle_sha256,
        "--expected-project-sha256",
        identity.expected_project_sha256,
        "--expected-generation",
        str(identity.expected_generation),
        "--coordinator-commit",
        identity.coordinator_commit,
        "--coordinator-tree",
        identity.coordinator_tree,
        "--coordinator-trigger-sha256",
        identity.coordinator_trigger_sha256,
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


def _bind_receipt_root(trigger, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(trigger, "CANONICAL_RECEIPT_ROOT", tmp_path)


def _job(*, generation: int = 23, ready: bool = True) -> dict[str, object]:
    return {
        "metadata": {"generation": generation},
        "spec": {
            "template": {
                "spec": {
                    "taskCount": 1,
                    "template": {
                        "spec": {
                            "serviceAccountName": (
                                "recall-sa-cohort-job@<project>.iam.gserviceaccount.com"
                            ),
                            "timeoutSeconds": 28800,
                            "maxRetries": 0,
                            "containers": [
                                {
                                    "image": (
                                        "us-central1-docker.pkg.dev/<project>/recall-images/"
                                        f"recall-cohort-job@{DIGEST}"
                                    ),
                                    "env": [
                                        {"name": "RECALL_PROVIDER_RPM", "value": "8"},
                                        {"name": "FULL_AUDIT_CONCURRENCY", "value": "2"},
                                        {"name": "RECALL_SOURCE_COMMIT", "value": SOURCE},
                                        {"name": "RECALL_SOURCE_TREE", "value": TREE},
                                        {"name": "RECALL_IMAGE_DIGEST", "value": DIGEST},
                                        {
                                            "name": "RECALL_COMPRESSED_PREPARATION_SHA256",
                                            "value": BUNDLE,
                                        },
                                        {
                                            "name": "RECALL_EXPECTED_PROJECT_SHA256",
                                            "value": PROJECT_HASH,
                                        },
                                        {
                                            "name": "RECALL_SCHEDULER_MODE",
                                            "value": "COMPRESSED_V3",
                                        },
                                        {
                                            "name": "RECALL_FINAL_OWNER_RELEASE_MAX_RETRIES",
                                            "value": "0",
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
                                        {"name": "PRIVATE_OWNER", "value": "owner@example.invalid"},
                                    ],
                                    "resources": {
                                        "limits": {"cpu": "1000m", "memory": "512Mi"}
                                    },
                                }
                            ],
                        }
                    },
                }
            }
        },
        "status": {
            "observedGeneration": generation,
            "conditions": [
                {"type": "Ready", "status": "True" if ready else "False"}
            ],
        },
    }


def _completed(value: object, code: int = 0) -> subprocess.CompletedProcess[str]:
    stdout = value if isinstance(value, str) else json.dumps(value)
    return subprocess.CompletedProcess(["redacted-wrapper"], code, stdout, "")


def _execution(
    name: str,
    *,
    marker: str,
    creator: str = "runner@x.iam.gserviceaccount.com",
    generation: int | None = 23,
):
    labels = (
        {}
        if generation is None
        else {"run.googleapis.com/jobGeneration": str(generation)}
    )
    return {
        "metadata": {
            "name": name,
            "creationTimestamp": "2026-08-30T01:04:15Z",
            "annotations": {"run.googleapis.com/creator": creator},
            "labels": labels,
        },
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "image": (
                                "us-central1-docker.pkg.dev/<project>/recall-images/"
                                f"recall-cohort-job@{DIGEST}"
                            ),
                            "args": [
                                "--owner-release-token",
                                "FINAL_ONLY_LATE_MANUAL_RELEASE_V1",
                                "--owner-release-reason",
                                "OWNER_AUTHORIZED_FINAL_TONIGHT",
                                "--recovery-attempt-id",
                                RECOVERY_ATTEMPT_ID,
                                "--owner-recovery-reason",
                                RECOVERY_REASON,
                                "--recovery-previous-execution-id",
                                PREVIOUS_EXECUTION,
                                "--recovery-previous-source-commit",
                                PREVIOUS_SOURCE,
                                "--recovery-previous-image-digest",
                                PREVIOUS_DIGEST,
                                "--recovery-previous-snapshot-sha256",
                                PREVIOUS_SNAPSHOT,
                            ],
                            "env": [
                                {"name": "RECALL_PROVIDER_RPM", "value": "8"},
                                {"name": "FULL_AUDIT_CONCURRENCY", "value": "2"},
                                {"name": "RECALL_SOURCE_COMMIT", "value": SOURCE},
                                {"name": "RECALL_SOURCE_TREE", "value": TREE},
                                {"name": "RECALL_IMAGE_DIGEST", "value": DIGEST},
                                {
                                    "name": "RECALL_COMPRESSED_PREPARATION_SHA256",
                                    "value": BUNDLE,
                                },
                                {
                                    "name": "RECALL_EXPECTED_PROJECT_SHA256",
                                    "value": PROJECT_HASH,
                                },
                                {
                                    "name": "RECALL_SCHEDULER_MODE",
                                    "value": "COMPRESSED_V3",
                                },
                                {
                                    "name": "RECALL_FINAL_OWNER_RELEASE_INTENT_SHA256",
                                    "value": marker,
                                },
                                {
                                    "name": "RECALL_FINAL_OWNER_RELEASE_MAX_RETRIES",
                                    "value": "0",
                                },
                            ]
                        }
                    ]
                }
            }
        },
        "status": {
            "conditions": [{"type": "Completed", "status": "Unknown"}],
            "runningCount": 1,
        },
    }


def test_attempt_key_and_receipt_path_are_canonical_and_no_path_bypass(
    tmp_path: Path, monkeypatch
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    again = _identity(trigger)

    assert identity.attempt_key == again.attempt_key
    assert identity.intent_sha256 == again.intent_sha256
    assert trigger.receipt_path(identity) == (
        tmp_path / f"final-owner-release-{identity.attempt_key}.json"
    )
    assert "receipt_path" not in inspect.signature(trigger.submit_once).parameters
    assert "receipt_dir" not in inspect.signature(trigger.submit_once).parameters
    assert "receipt_dir" not in inspect.signature(trigger.reconcile).parameters
    assert "--receipt-dir" not in trigger._parser().format_help()
    assert "--target-prefix" not in trigger._parser().format_help()
    assert "ownerstart01" not in trigger.receipt_path(identity).name


def test_recovery_identity_derives_prefix_and_receipt_id_without_caller_prefix(
) -> None:
    trigger = _load()
    identity = _identity(trigger)

    suffix = hashlib.sha256(RECOVERY_ATTEMPT_ID.encode("ascii")).hexdigest()[:10]
    assert identity.recovery_prefix == f"dev_recall_final_p{PLAN[:8]}_c6_r{suffix}_"
    assert identity.recovery_receipt_artifact_id == str(
        uuid.uuid5(
            uuid.UUID(RECOVERY_ATTEMPT_ID),
            "final-execution-recovery-receipt",
        )
    )
    assert "target_prefix" not in inspect.signature(
        trigger.FinalLaunchIdentity.create
    ).parameters


@pytest.mark.parametrize(
    ("field", "invalid", "code"),
    [
        (
            "recovery_attempt_id",
            "123E4567-E89B-12D3-A456-426614174000",
            "recovery_attempt_id_invalid",
        ),
        (
            "owner_recovery_reason",
            "RECOVER_SOMETHING_ELSE",
            "owner_recovery_reason_mismatch",
        ),
        (
            "recovery_previous_execution_id",
            "other-job-5tqxh",
            "recovery_previous_execution_id_invalid",
        ),
        (
            "recovery_previous_source_commit",
            "A" * 40,
            "recovery_previous_source_commit_invalid",
        ),
        (
            "recovery_previous_image_digest",
            "sha256:" + "A" * 64,
            "recovery_previous_image_digest_invalid",
        ),
        (
            "recovery_previous_snapshot_sha256",
            "A" * 64,
            "recovery_previous_snapshot_sha256_invalid",
        ),
    ],
)
def test_every_recovery_field_fails_closed_on_invalid_or_fixed_reason_mismatch(
    field: str, invalid: str, code: str
) -> None:
    trigger = _load()

    with pytest.raises(ValueError, match=code):
        _identity(trigger, **{field: invalid})


@pytest.mark.parametrize(
    "field",
    [
        "recovery_attempt_id",
        "recovery_previous_execution_id",
        "recovery_previous_source_commit",
        "recovery_previous_image_digest",
        "recovery_previous_snapshot_sha256",
    ],
)
def test_every_recovery_field_is_immutable_attempt_identity(field: str) -> None:
    trigger = _load()
    first = _identity(trigger)
    replacements = {
        "recovery_attempt_id": "123e4567-e89b-12d3-a456-426614174001",
        "recovery_previous_execution_id": "recall-cohort-daily-other1",
        "recovery_previous_source_commit": "6" * 40,
        "recovery_previous_image_digest": "sha256:" + "7" * 64,
        "recovery_previous_snapshot_sha256": "8" * 64,
    }
    changed = _identity(trigger, **{field: replacements[field]})

    assert changed.attempt_key != first.attempt_key
    assert changed.intent_sha256 != first.intent_sha256


def test_fixed_recovery_reason_and_derived_values_are_bound_into_attempt_key() -> None:
    trigger = _load()
    identity = _identity(trigger)
    expected = trigger._canonical_hash(
        {
            "owner_start_attempt_id": identity.owner_start_attempt_id,
            "deployed_source_commit": identity.deployed_source_commit,
            "deployed_source_tree": identity.deployed_source_tree,
            "deployed_image_digest": identity.deployed_image_digest,
            "plan_sha256": identity.plan_sha256,
            "bundle_sha256": identity.bundle_sha256,
            "recovery_attempt_id": identity.recovery_attempt_id,
            "owner_recovery_reason": identity.owner_recovery_reason,
            "recovery_previous_execution_id": (
                identity.recovery_previous_execution_id
            ),
            "recovery_previous_source_commit": (
                identity.recovery_previous_source_commit
            ),
            "recovery_previous_image_digest": (
                identity.recovery_previous_image_digest
            ),
            "recovery_previous_snapshot_sha256": (
                identity.recovery_previous_snapshot_sha256
            ),
            "recovery_prefix": identity.recovery_prefix,
            "recovery_receipt_artifact_id": (
                identity.recovery_receipt_artifact_id
            ),
        }
    )

    assert identity.owner_recovery_reason == RECOVERY_REASON
    assert identity.attempt_key == expected


@pytest.mark.parametrize(
    "option",
    [
        "--recovery-attempt-id",
        "--owner-recovery-reason",
        "--recovery-previous-execution-id",
        "--recovery-previous-source-commit",
        "--recovery-previous-image-digest",
        "--recovery-previous-snapshot-sha256",
    ],
)
def test_cli_omission_of_each_recovery_field_fails_before_identity_or_cloud(
    option: str,
) -> None:
    trigger = _load()
    argv = _cli_args(trigger)
    index = argv.index(option)
    del argv[index : index + 2]

    with pytest.raises(SystemExit):
        trigger._parser().parse_args(argv)


def test_caller_supplied_target_prefix_is_rejected_by_parser() -> None:
    trigger = _load()
    argv = _cli_args(trigger) + ["--target-prefix", "dev_recall_final_attacker_"]

    with pytest.raises(SystemExit):
        trigger._parser().parse_args(argv)


def test_attempt_key_ignores_generation_and_coordinator_only_identity() -> None:
    trigger = _load()
    first = _identity(trigger)
    changed = trigger.FinalLaunchIdentity.create(
        owner_start_attempt_id="ownerstart01",
        deployed_source_commit=SOURCE,
        deployed_source_tree=TREE,
        deployed_image_digest=DIGEST,
        plan_sha256=PLAN,
        bundle_sha256=BUNDLE,
        expected_project_sha256="0" * 64,
        expected_generation=99,
        coordinator_commit="3" * 40,
        coordinator_tree="4" * 40,
        coordinator_trigger_sha256=trigger.current_trigger_sha256(),
        recovery_attempt_id=RECOVERY_ATTEMPT_ID,
        owner_recovery_reason=RECOVERY_REASON,
        recovery_previous_execution_id=PREVIOUS_EXECUTION,
        recovery_previous_source_commit=PREVIOUS_SOURCE,
        recovery_previous_image_digest=PREVIOUS_DIGEST,
        recovery_previous_snapshot_sha256=PREVIOUS_SNAPSHOT,
    )

    assert changed.attempt_key == first.attempt_key
    assert changed.intent_sha256 == first.intent_sha256


def test_execute_command_is_exact_async_one_shot_without_wait() -> None:
    trigger = _load()
    identity = _identity(trigger)

    args = trigger.build_execute_args(identity, PROJECT)

    assert args[:4] == ["run", "jobs", "execute", trigger.JOB]
    assert args.count("--async") == 1
    assert not any(arg == "--wait" or arg.startswith("--wait=") for arg in args)
    assert args.count("--tasks=1") == 1
    assert args.count("--task-timeout=28800s") == 1
    assert args.count(f"--project={PROJECT}") == 1
    expected_runtime_args = (
        "--args=--owner-release-token,FINAL_ONLY_LATE_MANUAL_RELEASE_V1,"
        "--owner-release-reason,OWNER_AUTHORIZED_FINAL_TONIGHT,"
        f"--recovery-attempt-id,{RECOVERY_ATTEMPT_ID},"
        f"--owner-recovery-reason,{RECOVERY_REASON},"
        f"--recovery-previous-execution-id,{PREVIOUS_EXECUTION},"
        f"--recovery-previous-source-commit,{PREVIOUS_SOURCE},"
        f"--recovery-previous-image-digest,{PREVIOUS_DIGEST},"
        f"--recovery-previous-snapshot-sha256,{PREVIOUS_SNAPSHOT}"
    )
    assert args.count(expected_runtime_args) == 1
    for option in (
        "--recovery-attempt-id",
        "--owner-recovery-reason",
        "--recovery-previous-execution-id",
        "--recovery-previous-source-commit",
        "--recovery-previous-image-digest",
        "--recovery-previous-snapshot-sha256",
    ):
        assert expected_runtime_args.count(option) == 1
    assert not any("target-prefix" in arg for arg in args)
    override = next(arg for arg in args if arg.startswith("--update-env-vars="))
    assert "RECALL_FINAL_OWNER_RELEASE_MAX_RETRIES=0" in override
    assert f"RECALL_FINAL_OWNER_RELEASE_INTENT_SHA256={identity.intent_sha256}" in override


def test_full_preflight_then_marker_list_then_durable_receipt_then_one_execute(
    tmp_path: Path, monkeypatch
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    calls: list[tuple[str, ...]] = []
    fsync_calls: list[int] = []

    def run(*args: str, **kwargs):
        calls.append(args)
        if args[:4] == ("run", "jobs", "describe", trigger.JOB):
            assert kwargs["timeout_seconds"] == trigger.READ_TIMEOUT_SECONDS
            return _completed(_job())
        if args[:4] == ("run", "jobs", "executions", "list"):
            return _completed([])
        assert args[:4] == ("run", "jobs", "execute", trigger.JOB)
        assert trigger.receipt_path(identity).exists()
        assert kwargs["timeout_seconds"] == trigger.SUBMIT_TIMEOUT_SECONDS
        return _completed("ignored-sensitive-client-output")

    monkeypatch.setattr(trigger.os, "fsync", lambda fd: fsync_calls.append(fd))
    report = trigger.submit_once(identity, project=PROJECT, run_fn=run)

    assert report == {
        "verdict": "SUBMIT_ACCEPTED_NOT_RECONCILED",
        "attempt_alias": identity.attempt_key[:16],
        "execute_count": 1,
        "receipt_state": "LOCAL_INTENT_ONLY",
    }
    assert [call[:4] for call in calls] == [
        ("run", "jobs", "describe", trigger.JOB),
        ("run", "jobs", "executions", "list"),
        ("run", "jobs", "execute", trigger.JOB),
    ]
    assert fsync_calls
    receipt = json.loads(trigger.receipt_path(identity).read_text("utf-8"))
    assert receipt["receipt_state"] == "LOCAL_INTENT_ONLY"
    assert receipt["created_at_utc"].endswith("Z")
    assert receipt["deployed"]["source_commit"] == SOURCE
    assert receipt["coordinator"]["source_commit"] == COORDINATOR_COMMIT
    assert receipt["coordinator"]["source_commit"] != receipt["deployed"]["source_commit"]
    assert receipt["recovery"] == {
        "attempt_id": RECOVERY_ATTEMPT_ID,
        "owner_reason": RECOVERY_REASON,
        "previous_execution_id": PREVIOUS_EXECUTION,
        "previous_source_commit": PREVIOUS_SOURCE,
        "previous_image_digest": PREVIOUS_DIGEST,
        "previous_snapshot_sha256": PREVIOUS_SNAPSHOT,
        "derived_prefix": identity.recovery_prefix,
        "receipt_artifact_id": identity.recovery_receipt_artifact_id,
    }


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda job: job["metadata"].update(generation=22), "generation_mismatch"),
        (
            lambda job: job["status"].update(observedGeneration=22),
            "observed_generation_mismatch",
        ),
        (
            lambda job: job["spec"]["template"]["spec"]["template"]["spec"][
                "containers"
            ][0].update(image="x@sha256:" + "9" * 64),
            "image_digest_mismatch",
        ),
        (
            lambda job: next(
                row
                for row in job["spec"]["template"]["spec"]["template"]["spec"][
                    "containers"
                ][0]["env"]
                if row["name"] == "RECALL_SOURCE_TREE"
            ).update(value="9" * 40),
            "env_mismatch:RECALL_SOURCE_TREE",
        ),
        (
            lambda job: job["status"]["conditions"][0].update(status="False"),
            "ready_mismatch",
        ),
        (
            lambda job: job["spec"]["template"]["spec"]["template"]["spec"].update(
                maxRetries=1
            ),
            "max_retries_mismatch",
        ),
        (
            lambda job: job["spec"]["template"]["spec"]["template"]["spec"][
                "containers"
            ][0]["resources"]["limits"].update(cpu="2"),
            "cpu_mismatch",
        ),
        (
            lambda job: job["spec"]["template"]["spec"]["template"]["spec"].update(
                serviceAccountName="other@<project>.iam.gserviceaccount.com"
            ),
            "service_account_mismatch",
        ),
        (
            lambda job: job["spec"]["template"]["spec"]["template"]["spec"][
                "containers"
            ][0]["env"].__setitem__(
                slice(None),
                [
                    row
                    for row in job["spec"]["template"]["spec"]["template"]["spec"][
                        "containers"
                    ][0]["env"]
                    if row["name"] != "RECALL_NCBI_EMAIL"
                ],
            ),
            "required_secret_binding_missing",
        ),
        (
            lambda job: next(
                row
                for row in job["spec"]["template"]["spec"]["template"]["spec"][
                    "containers"
                ][0]["env"]
                if row["name"] == "FULL_AUDIT_CONCURRENCY"
            ).update(value="4"),
            "concurrency_mismatch",
        ),
    ],
)
def test_every_preflight_drift_blocks_receipt_and_execute(
    tmp_path: Path, monkeypatch, mutate, code: str
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    job = _job()
    mutate(job)
    calls: list[tuple[str, ...]] = []

    def run(*args: str, **_kwargs):
        calls.append(args)
        return _completed(job)

    report = trigger.submit_once(identity, project=PROJECT, run_fn=run)

    assert report["verdict"] == "FAIL"
    assert code in report["codes"]
    assert len(calls) == 1
    assert not trigger.receipt_path(identity).exists()


def test_incomplete_existing_receipt_blocks_without_cloud_or_execute(
    tmp_path: Path, monkeypatch
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    trigger.receipt_path(identity).write_text("{", encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    report = trigger.submit_once(
        identity,
        project=PROJECT,
        run_fn=lambda *args, **_kwargs: calls.append(args),
    )

    assert report["verdict"] == "FAIL"
    assert report["codes"] == ["attempt_receipt_exists"]
    assert calls == []


def test_existing_marker_blocks_before_receipt_and_execute(
    tmp_path: Path, monkeypatch
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    calls: list[tuple[str, ...]] = []

    def run(*args: str, **_kwargs):
        calls.append(args)
        if args[:4] == ("run", "jobs", "describe", trigger.JOB):
            return _completed(_job())
        return _completed([_execution("recall-cohort-daily-old", marker=identity.intent_sha256)])

    report = trigger.submit_once(identity, project=PROJECT, run_fn=run)

    assert report["verdict"] == "FAIL"
    assert report["codes"] == ["intent_marker_already_present"]
    assert len(calls) == 2
    assert not trigger.receipt_path(identity).exists()


@pytest.mark.parametrize("exit_code", [7, 124])
def test_nonzero_or_timeout_is_outcome_unknown_and_never_retried(
    tmp_path: Path, monkeypatch, exit_code: int
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    execute_count = 0

    def run(*args: str, **_kwargs):
        nonlocal execute_count
        if args[:4] == ("run", "jobs", "describe", trigger.JOB):
            return _completed(_job())
        if args[:4] == ("run", "jobs", "executions", "list"):
            return _completed([])
        execute_count += 1
        return _completed("secret-canary-789", exit_code)

    report = trigger.submit_once(identity, project=PROJECT, run_fn=run)

    assert report == {
        "verdict": "OUTCOME_UNKNOWN",
        "attempt_alias": identity.attempt_key[:16],
        "execute_count": 1,
        "receipt_state": "LOCAL_INTENT_ONLY",
        "submit_exit_code": exit_code,
        "next_step": "STOP_AND_RECONCILE",
    }
    assert execute_count == 1


def _write_intent(trigger, identity) -> None:
    trigger.write_intent_receipt(identity, baseline_aliases=())


def test_reconcile_zero_is_repeatable_pending_and_never_executes(
    tmp_path: Path, monkeypatch
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    _write_intent(trigger, identity)
    calls: list[tuple[str, ...]] = []

    def run(*args: str, **_kwargs):
        calls.append(args)
        assert args[:4] == ("run", "jobs", "executions", "list")
        return _completed([])

    first = trigger.reconcile(identity, project=PROJECT, run_fn=run)
    second = trigger.reconcile(identity, project=PROJECT, run_fn=run)

    assert first == second == {
        "verdict": "NOT_VERIFIED",
        "state": "PENDING",
        "attempt_alias": identity.attempt_key[:16],
        "execution_count": 0,
    }
    assert len(calls) == 2


def test_reconcile_exactly_one_new_marker_candidate_describes_once_safely(
    tmp_path: Path, monkeypatch
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    old = _execution("recall-cohort-daily-old", marker="9" * 64)
    baseline = (trigger.execution_alias("recall-cohort-daily-old"),)
    trigger.write_intent_receipt(identity, baseline_aliases=baseline)
    candidate = _execution(
        "recall-cohort-daily-newsecret", marker=identity.intent_sha256
    )
    calls: list[tuple[str, ...]] = []

    def run(*args: str, **_kwargs):
        calls.append(args)
        if args[:4] == ("run", "jobs", "executions", "list"):
            return _completed([old, candidate])
        assert args[:4] == ("run", "jobs", "executions", "describe")
        return _completed(candidate)

    report = trigger.reconcile(identity, project=PROJECT, run_fn=run)
    rendered = json.dumps(report, sort_keys=True)

    assert report["verdict"] == "PASS"
    assert report["state"] == "RUNNING"
    assert report["creator_class"] == "MACHINE"
    assert report["execution_generation_evidence"] == "VERIFIED"
    assert report["execution_alias"] == trigger.execution_alias(
        "recall-cohort-daily-newsecret"
    )
    assert len(calls) == 2
    for canary in (
        "recall-cohort-daily-newsecret",
        "runner@x.iam.gserviceaccount.com",
        PROJECT,
        "secret-canary",
        "owner@example.invalid",
        "token-canary-abc",
    ):
        assert canary not in rendered


@pytest.mark.parametrize(
    "option",
    [
        "--recovery-attempt-id",
        "--owner-recovery-reason",
        "--recovery-previous-execution-id",
        "--recovery-previous-source-commit",
        "--recovery-previous-image-digest",
        "--recovery-previous-snapshot-sha256",
    ],
)
@pytest.mark.parametrize("mutation", ["omit", "mismatch"])
def test_reconcile_rejects_each_omitted_or_mismatched_recovery_argument(
    tmp_path: Path,
    monkeypatch,
    option: str,
    mutation: str,
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    trigger.write_intent_receipt(identity, baseline_aliases=())
    candidate = _execution(
        "recall-cohort-daily-recovery-binding",
        marker=identity.intent_sha256,
    )
    runtime_args = candidate["spec"]["template"]["spec"]["containers"][0]["args"]
    index = runtime_args.index(option)
    if mutation == "omit":
        del runtime_args[index : index + 2]
    else:
        runtime_args[index + 1] = "mismatch"

    def run(*args: str, **_kwargs):
        if args[:4] == ("run", "jobs", "executions", "list"):
            return _completed([candidate])
        return _completed(candidate)

    report = trigger.reconcile(identity, project=PROJECT, run_fn=run)

    assert report["verdict"] == "FAIL"
    assert report["state"] == "BINDING_MISMATCH"
    assert report["codes"] == ["execution_args_mismatch"]


@pytest.mark.parametrize(
    ("generation", "creator", "expected_verdict", "expected_evidence", "code"),
    [
        (24, "runner@x.iam.gserviceaccount.com", "FAIL", None, "execution_generation_mismatch"),
        (None, "<account>", "NOT_VERIFIED", "NOT_VERIFIED", None),
    ],
)
def test_reconcile_generation_and_redacted_caller_fail_closed(
    tmp_path: Path,
    monkeypatch,
    generation: int | None,
    creator: str,
    expected_verdict: str,
    expected_evidence: str | None,
    code: str | None,
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    trigger.write_intent_receipt(identity, baseline_aliases=())
    candidate = _execution(
        "recall-cohort-daily-generation-check",
        marker=identity.intent_sha256,
        creator=creator,
        generation=generation,
    )

    def run(*args: str, **_kwargs):
        if args[:4] == ("run", "jobs", "executions", "list"):
            return _completed([candidate])
        return _completed(candidate)

    report = trigger.reconcile(identity, project=PROJECT, run_fn=run)

    assert report["verdict"] == expected_verdict
    if code is not None:
        assert code in report["codes"]
    else:
        assert report["execution_generation_evidence"] == expected_evidence
        assert report["creator_class"] == "CONFIGURED_CALLER_REDACTED"


def test_reconcile_multiple_new_marker_candidates_is_ambiguous_without_describe(
    tmp_path: Path, monkeypatch
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    _write_intent(trigger, identity)
    candidates = [
        _execution("recall-cohort-daily-one", marker=identity.intent_sha256),
        _execution("recall-cohort-daily-two", marker=identity.intent_sha256),
    ]
    calls: list[tuple[str, ...]] = []

    def run(*args: str, **_kwargs):
        calls.append(args)
        return _completed(candidates)

    report = trigger.reconcile(identity, project=PROJECT, run_fn=run)

    assert report == {
        "verdict": "FAIL",
        "state": "AMBIGUOUS",
        "attempt_alias": identity.attempt_key[:16],
        "execution_count": 2,
        "codes": ["multiple_execution_candidates"],
    }
    assert len(calls) == 1


@pytest.mark.parametrize(
    "wire",
    (
        "{}",
        '{"baseline_execution_aliases":"not-a-list"}',
        '{"baseline_execution_aliases":17}',
    ),
)
def test_malformed_receipt_blocks_reconcile_without_cloud(
    tmp_path: Path, monkeypatch, wire: str
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    trigger.receipt_path(identity).write_text(wire, encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    report = trigger.reconcile(
        identity,
        project=PROJECT,
        run_fn=lambda *args, **_kwargs: calls.append(args),
    )

    assert report == {
        "verdict": "FAIL",
        "state": "BLOCKED",
        "attempt_alias": identity.attempt_key[:16],
        "codes": ["attempt_receipt_invalid"],
    }
    assert calls == []


@pytest.mark.parametrize(
    "field",
    [
        "attempt_id",
        "owner_reason",
        "previous_execution_id",
        "previous_source_commit",
        "previous_image_digest",
        "previous_snapshot_sha256",
        "derived_prefix",
        "receipt_artifact_id",
    ],
)
def test_recovery_receipt_tamper_blocks_reconcile_without_cloud(
    tmp_path: Path, monkeypatch, field: str
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    trigger.write_intent_receipt(identity, baseline_aliases=())
    path = trigger.receipt_path(identity)
    wire = json.loads(path.read_text("utf-8"))
    wire["recovery"][field] = "tampered"
    path.write_text(json.dumps(wire), encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    report = trigger.reconcile(
        identity,
        project=PROJECT,
        run_fn=lambda *args, **_kwargs: calls.append(args),
    )

    assert report["verdict"] == "FAIL"
    assert report["codes"] == ["attempt_receipt_invalid"]
    assert calls == []


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("head", "coordinator_head_mismatch"),
        ("tree", "coordinator_tree_mismatch"),
        ("status", "coordinator_checkout_dirty"),
        ("blob", "coordinator_trigger_blob_mismatch"),
    ],
)
def test_coordinator_checkout_is_bound_to_clean_head_tree_and_blob(
    mutation: str, code: str
) -> None:
    trigger = _load()
    identity = _identity(trigger)

    def git_run(*args: str):
        values = {
            ("rev-parse", "HEAD"): COORDINATOR_COMMIT,
            ("rev-parse", "HEAD^{tree}"): COORDINATOR_TREE,
            ("status", "--porcelain=v1", "--untracked-files=all"): "",
            (
                "rev-parse",
                f"HEAD:{trigger.TRIGGER_RELATIVE_PATH}",
            ): "blob123",
        }
        if args[0] == "hash-object":
            value = "other" if mutation == "blob" else "blob123"
        else:
            value = values[args]
        if mutation == "head" and args == ("rev-parse", "HEAD"):
            value = "9" * 40
        if mutation == "tree" and args == ("rev-parse", "HEAD^{tree}"):
            value = "8" * 40
        if mutation == "status" and args[0] == "status":
            value = "?? unsafe.py"
        return _completed(value)

    failures = trigger._real_verify_coordinator_checkout(identity, run_fn=git_run)

    assert code in failures


def test_project_hash_mismatch_blocks_submit_and_reconcile_before_any_command(
    tmp_path: Path, monkeypatch
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    calls: list[tuple[str, ...]] = []

    submitted = trigger.submit_once(
        identity,
        project="different-project-123",
        run_fn=lambda *args, **_kwargs: calls.append(args),
    )
    reconciled = trigger.reconcile(
        identity,
        project="different-project-123",
        run_fn=lambda *args, **_kwargs: calls.append(args),
    )

    assert submitted["codes"] == ["project_hash_mismatch"]
    assert reconciled["codes"] == ["project_hash_mismatch"]
    assert calls == []


@pytest.mark.parametrize(
    ("state", "status", "failed", "succeeded", "running", "verdict", "result"),
    [
        ("CONDITION_SUCCEEDED", None, 0, 1, 0, "PASS", "SUCCEEDED"),
        ("CONDITION_FAILED", None, 1, 0, 0, "FAIL", "TERMINAL_FAILED"),
        (None, "True", 0, 1, 0, "PASS", "SUCCEEDED"),
        (None, "False", 1, 0, 0, "FAIL", "TERMINAL_FAILED"),
        ("CONDITION_SUCCEEDED", None, 1, 1, 0, "NOT_VERIFIED", "CONTRADICTORY"),
        (None, "Unknown", 0, 0, 1, "PASS", "RUNNING"),
        (None, "Unknown", 0, 0, 0, "NOT_VERIFIED", "UNKNOWN"),
    ],
)
def test_terminal_condition_shapes_never_hide_failure_or_unknown(
    tmp_path: Path,
    monkeypatch,
    state: str | None,
    status: str | None,
    failed: int,
    succeeded: int,
    running: int,
    verdict: str,
    result: str,
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    trigger.write_intent_receipt(identity, baseline_aliases=())
    candidate = _execution(
        "recall-cohort-daily-terminal-check", marker=identity.intent_sha256
    )
    condition: dict[str, str] = {"type": "Completed"}
    if state is not None:
        condition["state"] = state
    if status is not None:
        condition["status"] = status
    candidate["status"] = {
        "conditions": [condition],
        "failedCount": failed,
        "succeededCount": succeeded,
        "runningCount": running,
    }

    def run(*args: str, **_kwargs):
        if args[:4] == ("run", "jobs", "executions", "list"):
            return _completed([candidate])
        return _completed(candidate)

    report = trigger.reconcile(identity, project=PROJECT, run_fn=run)

    assert report["verdict"] == verdict
    assert report["state"] == result


def test_completed_failure_dominates_ancillary_success_conditions(
    tmp_path: Path, monkeypatch
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    trigger.write_intent_receipt(identity, baseline_aliases=())
    candidate = _execution(
        "recall-cohort-daily-multi-condition", marker=identity.intent_sha256
    )
    candidate["status"] = {
        "conditions": [
            {"type": "ResourcesAvailable", "state": "CONDITION_SUCCEEDED"},
            {"type": "Started", "state": "CONDITION_SUCCEEDED"},
            {"type": "Completed", "state": "CONDITION_FAILED"},
        ],
        "failedCount": 1,
        "succeededCount": 0,
        "runningCount": 0,
    }

    def run(*args: str, **_kwargs):
        if args[:4] == ("run", "jobs", "executions", "list"):
            return _completed([candidate])
        return _completed(candidate)

    report = trigger.reconcile(identity, project=PROJECT, run_fn=run)

    assert report["verdict"] == "FAIL"
    assert report["state"] == "TERMINAL_FAILED"


@pytest.mark.parametrize(
    ("conditions", "succeeded", "running"),
    [
        (
            [
                {"type": "ResourcesAvailable", "state": "CONDITION_SUCCEEDED"},
                {"type": "Completed", "state": "CONDITION_PENDING"},
            ],
            0,
            0,
        ),
        ([{"type": "Completed", "state": "CONDITION_SUCCEEDED"}], 1, 1),
    ],
)
def test_auxiliary_success_or_running_terminal_success_is_not_pass(
    tmp_path: Path,
    monkeypatch,
    conditions: list[dict[str, str]],
    succeeded: int,
    running: int,
) -> None:
    trigger = _load()
    _bind_receipt_root(trigger, monkeypatch, tmp_path)
    identity = _identity(trigger)
    trigger.write_intent_receipt(identity, baseline_aliases=())
    candidate = _execution(
        "recall-cohort-daily-terminal-contradiction",
        marker=identity.intent_sha256,
    )
    candidate["status"] = {
        "conditions": conditions,
        "failedCount": 0,
        "succeededCount": succeeded,
        "runningCount": running,
    }

    def run(*args: str, **_kwargs):
        if args[:4] == ("run", "jobs", "executions", "list"):
            return _completed([candidate])
        return _completed(candidate)

    report = trigger.reconcile(identity, project=PROJECT, run_fn=run)

    assert report["verdict"] == "NOT_VERIFIED"
    assert report["state"] in {"UNKNOWN", "CONTRADICTORY"}


def test_trigger_sha_and_coordinator_identity_are_separate_from_deployed_image() -> None:
    trigger = _load()
    identity = _identity(trigger)

    assert identity.coordinator_commit == COORDINATOR_COMMIT
    assert identity.deployed_source_commit == SOURCE
    assert identity.coordinator_commit != identity.deployed_source_commit
    with pytest.raises(ValueError, match="coordinator_trigger_sha256_mismatch"):
        trigger.FinalLaunchIdentity.create(
            owner_start_attempt_id="ownerstart01",
            deployed_source_commit=SOURCE,
            deployed_source_tree=TREE,
            deployed_image_digest=DIGEST,
            plan_sha256=PLAN,
            bundle_sha256=BUNDLE,
            expected_project_sha256=PROJECT_HASH,
            expected_generation=23,
            coordinator_commit=COORDINATOR_COMMIT,
            coordinator_tree=COORDINATOR_TREE,
            coordinator_trigger_sha256="0" * 64,
            recovery_attempt_id=RECOVERY_ATTEMPT_ID,
            owner_recovery_reason=RECOVERY_REASON,
            recovery_previous_execution_id=PREVIOUS_EXECUTION,
            recovery_previous_source_commit=PREVIOUS_SOURCE,
            recovery_previous_image_digest=PREVIOUS_DIGEST,
            recovery_previous_snapshot_sha256=PREVIOUS_SNAPSHOT,
        )
