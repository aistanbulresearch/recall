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
    PositiveSmokeLaunchIdentity,
    SmokePair,
    _positive_parser,
    build_positive_execute_args,
    build_cloud_build_config,
    positive_receipt_path,
    reconcile_positive,
    main,
    parse_execution_markers,
    parse_build_id,
    submit_positive_once,
    submit_smoke_pair,
    validate_job_snapshot,
)
import isolated_smoke_trigger as smoke_trigger  # noqa: E402
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


def _positive_identity() -> PositiveSmokeLaunchIdentity:
    return PositiveSmokeLaunchIdentity.create(
        smoke_id="smoke1234",
        deployed_source_commit=COMMIT,
        deployed_source_tree=TREE,
        deployed_image_digest=DIGEST,
        plan_sha256=PLAN,
        bundle_sha256=BUNDLE,
        expected_project_sha256=PROJECT_HASH,
        expected_generation=27,
        coordinator_commit="1" * 40,
        coordinator_tree="2" * 40,
        coordinator_trigger_sha256="3" * 64,
    )


def _positive_cli_args(action: str = "positive-submit") -> list[str]:
    return [
        action,
        "--smoke-id",
        "smoke1234",
        "--deployed-source-commit",
        COMMIT,
        "--deployed-source-tree",
        TREE,
        "--deployed-image-digest",
        DIGEST,
        "--plan-sha256",
        PLAN,
        "--bundle-sha256",
        BUNDLE,
        "--expected-project-sha256",
        PROJECT_HASH,
        "--expected-generation",
        "27",
        "--coordinator-commit",
        "1" * 40,
        "--coordinator-tree",
        "2" * 40,
        "--coordinator-trigger-sha256",
        "3" * 64,
    ]


def _ready_job() -> dict[str, object]:
    job = _job()
    job["metadata"] = {"generation": 27}
    job["status"] = {
        "observedGeneration": 27,
        "conditions": [{"type": "Ready", "status": "True"}],
    }
    return job


def _positive_execution(
    identity: PositiveSmokeLaunchIdentity,
    *,
    name: str = "recall-cohort-daily-pos12",
    args: list[str] | None = None,
    marker: str | None = None,
) -> dict[str, object]:
    return {
        "metadata": {
            "name": name,
            "labels": {"run.googleapis.com/jobGeneration": "27"},
            "annotations": {"run.googleapis.com/creator": "<principal>"},
        },
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "image": "registry/<project>/job@" + DIGEST,
                            "args": list(
                                args
                                if args is not None
                                else identity.entrypoint_args()
                            ),
                            "env": [
                                {"name": "RECALL_SOURCE_COMMIT", "value": COMMIT},
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
                                {"name": "RECALL_SCHEDULER_MODE", "value": "COMPRESSED_V3"},
                                {"name": "RECALL_PROVIDER_RPM", "value": "8"},
                                {"name": "FULL_AUDIT_CONCURRENCY", "value": "2"},
                                {
                                    "name": "RECALL_SMOKE_EXPECTED_PLAN_SHA256",
                                    "value": PLAN,
                                },
                                {
                                    "name": "RECALL_SMOKE_EXPECTED_IMAGE_DIGEST",
                                    "value": DIGEST,
                                },
                                {"name": "RECALL_SMOKE_JOB_MAX_RETRIES", "value": "0"},
                                {
                                    "name": "RECALL_POSITIVE_SMOKE_INTENT_SHA256",
                                    "value": marker or identity.intent_sha256,
                                },
                            ],
                        }
                    ]
                }
            }
        },
        "status": {
            "runningCount": 1,
            "conditions": [{"type": "Completed", "status": "Unknown"}],
        },
    }


def test_generated_build_is_source_less_machine_trigger_with_two_explicit_overrides() -> None:
    config = build_cloud_build_config(_pair())

    encoded = json.dumps(config, sort_keys=True)
    assert "serviceAccount" not in config
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


def test_generated_build_retains_valid_explicit_machine_identity() -> None:
    config = build_cloud_build_config(
        _pair(),
        machine_service_account="smoke-runner@sample-project.iam.gserviceaccount.com",
    )

    assert config["serviceAccount"].endswith(
        "/serviceAccounts/smoke-runner@sample-project.iam.gserviceaccount.com"
    )


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


@pytest.mark.parametrize("name", sorted(smoke_trigger.REQUIRED_SECRET_ENV))
def test_job_preflight_requires_exactly_one_secret_only_binding(name: str) -> None:
    duplicate = _job()
    rows = duplicate["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]["env"]  # type: ignore[index]
    rows.append({"name": name, "value": "inline-forbidden"})
    assert "required_secret_binding_invalid" in validate_job_snapshot(
        duplicate, DeploymentExpectation.from_pair(_pair(), project=PROJECT)
    )

    mixed = _job()
    rows = mixed["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]["env"]  # type: ignore[index]
    row = next(item for item in rows if item["name"] == name)
    row["value"] = "inline-forbidden"
    assert "required_secret_binding_missing" in validate_job_snapshot(
        mixed, DeploymentExpectation.from_pair(_pair(), project=PROJECT)
    )


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


@pytest.mark.parametrize(
    ("machine_service_account_local_part", "expects_explicit_account"),
    [(None, False), ("smoke-runner", True)],
)
def test_submit_uses_default_or_explicit_machine_identity(
    tmp_path: Path,
    machine_service_account_local_part: str | None,
    expects_explicit_account: bool,
) -> None:
    calls: list[tuple[str, ...]] = []

    def run_fn(*args: str, timeout_seconds: int = 600) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:3] == ("run", "jobs", "describe"):
            return subprocess.CompletedProcess([], 0, json.dumps(_job()), "")
        if args[:2] == ("builds", "submit"):
            assert "--no-source" in args
            has_explicit_account = any(
                item.startswith("--service-account=projects/") for item in args
            )
            assert has_explicit_account is expects_explicit_account
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

    submit_kwargs = {
        "project": "sample-project",
        "receipt_path": tmp_path / "receipt.json",
        "run_fn": run_fn,
    }
    if machine_service_account_local_part is not None:
        submit_kwargs["machine_service_account_local_part"] = (
            machine_service_account_local_part
        )
    report = submit_smoke_pair(_pair(), **submit_kwargs)
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


def test_positive_identity_is_exact_four_case_contract_without_negative_surface() -> None:
    identity = _positive_identity()

    assert identity.case_count == 4
    assert identity.turn_limit == 24
    assert identity.positive_prefix == (
        f"dev_recall_smoke_{COMMIT[:12]}_{PLAN[:12]}_positive_smoke1234_"
    )
    assert identity.entrypoint_args() == (
        "--smoke-mode",
        "positive",
        "--smoke-id",
        "smoke1234",
        "--smoke-prefix",
        identity.positive_prefix,
    )
    wire = json.dumps(identity.to_receipt(), sort_keys=True)
    assert "negative" not in wire
    assert "_c6_" not in wire
    assert "456" not in wire


def test_positive_identity_never_constructs_pair_and_fails_on_core_contract_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        SmokePair,
        "create",
        classmethod(lambda cls, **kwargs: (_ for _ in ()).throw(AssertionError())),
    )
    _positive_identity()

    monkeypatch.setattr(smoke_trigger, "_positive_core_contract", lambda: (5, 24))
    with pytest.raises(RuntimeError, match="positive_smoke_core_contract_mismatch"):
        _positive_identity()


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("smoke_id", "short", "smoke_id_invalid"),
        ("deployed_source_commit", "a" * 39, "source_commit_invalid"),
        ("deployed_source_tree", "b" * 39, "source_tree_invalid"),
        ("deployed_image_digest", "sha256:bad", "image_digest_invalid"),
        ("plan_sha256", "c" * 63, "plan_sha256_invalid"),
        ("bundle_sha256", "d" * 63, "bundle_sha256_invalid"),
        ("expected_project_sha256", "f" * 63, "project_sha256_invalid"),
        ("expected_generation", 0, "generation_invalid"),
        ("coordinator_commit", "1" * 39, "coordinator_commit_invalid"),
        ("coordinator_tree", "2" * 39, "coordinator_tree_invalid"),
        ("coordinator_trigger_sha256", "3" * 63, "trigger_sha256_invalid"),
    ],
)
def test_positive_identity_rejects_missing_or_malformed_authority_fields(
    field: str, value: object, error: str
) -> None:
    values: dict[str, object] = {
        "smoke_id": "smoke1234",
        "deployed_source_commit": COMMIT,
        "deployed_source_tree": TREE,
        "deployed_image_digest": DIGEST,
        "plan_sha256": PLAN,
        "bundle_sha256": BUNDLE,
        "expected_project_sha256": PROJECT_HASH,
        "expected_generation": 27,
        "coordinator_commit": "1" * 40,
        "coordinator_tree": "2" * 40,
        "coordinator_trigger_sha256": "3" * 64,
    }
    values[field] = value
    with pytest.raises(ValueError, match=error):
        PositiveSmokeLaunchIdentity.create(**values)  # type: ignore[arg-type]


def test_positive_execute_args_are_async_exact_once_and_have_no_negative_or_wait() -> None:
    args = build_positive_execute_args(_positive_identity(), PROJECT)
    encoded = " ".join(args)

    assert args[:4] == ["run", "jobs", "execute", "recall-cohort-daily"]
    assert encoded.count("--args=") == 1
    assert "--smoke-mode,positive,--smoke-id,smoke1234,--smoke-prefix," in encoded
    assert encoded.count("RECALL_POSITIVE_SMOKE_INTENT_SHA256=") == 1
    assert "RECALL_SMOKE_JOB_MAX_RETRIES=0" in encoded
    assert "negative" not in encoded
    assert "--wait" not in args
    assert "--async" in args


def test_positive_cli_is_source_controlled_and_rejects_duplicate_missing_or_prefix_args(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    parsed = _positive_parser().parse_args(_positive_cli_args())
    assert parsed.action == "positive-submit"
    assert parsed.smoke_id == "smoke1234"

    with pytest.raises(SystemExit):
        _positive_parser().parse_args(
            _positive_cli_args() + ["--smoke-id", "smoke5678"]
        )
    with pytest.raises(SystemExit):
        _positive_parser().parse_args(_positive_cli_args()[0:-2])
    with pytest.raises(SystemExit):
        _positive_parser().parse_args(
            _positive_cli_args()
            + ["--smoke-prefix", "dev_recall_smoke_caller_override_"]
        )

    calls: list[PositiveSmokeLaunchIdentity] = []
    monkeypatch.setattr(smoke_trigger, "resolve_project", lambda: PROJECT)
    monkeypatch.setattr(
        smoke_trigger,
        "submit_positive_once",
        lambda identity, *, project: (
            calls.append(identity)
            or {
                "verdict": "SUBMIT_ACCEPTED_NOT_RECONCILED",
                "execute_count": 1,
                "attempt_alias": identity.attempt_key[:16],
            }
        ),
    )
    assert main(_positive_cli_args()) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == "SUBMIT_ACCEPTED_NOT_RECONCILED"
    assert len(calls) == 1
    assert calls[0].positive_prefix == _positive_identity().positive_prefix


def test_positive_submit_writes_o_excl_intent_before_cloud_and_executes_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = _positive_identity()
    monkeypatch.setattr(smoke_trigger, "POSITIVE_RECEIPT_ROOT", tmp_path)
    monkeypatch.setattr(
        smoke_trigger, "verify_positive_coordinator_checkout", lambda _identity: ()
    )
    calls: list[tuple[str, ...]] = []

    def run_fn(*args: str, timeout_seconds: int = 600) -> subprocess.CompletedProcess[str]:
        assert positive_receipt_path(identity).exists()
        calls.append(args)
        if args[:3] == ("run", "jobs", "describe"):
            return subprocess.CompletedProcess([], 0, json.dumps(_ready_job()), "")
        if args[:5] == ("run", "jobs", "executions", "list", "--job=recall-cohort-daily"):
            return subprocess.CompletedProcess([], 0, "[]", "")
        assert args[:4] == ("run", "jobs", "execute", "recall-cohort-daily")
        return subprocess.CompletedProcess([], 0, "{}", "")

    report = submit_positive_once(identity, project=PROJECT, run_fn=run_fn)

    assert report["verdict"] == "SUBMIT_ACCEPTED_NOT_RECONCILED"
    assert report["execute_count"] == 1
    assert len([call for call in calls if call[:3] == ("run", "jobs", "execute")]) == 1
    assert json.loads(positive_receipt_path(identity).read_text(encoding="utf-8")) == (
        identity.to_receipt()
    )


@pytest.mark.parametrize("exit_code", [1, 124])
def test_positive_submit_nonzero_is_unknown_and_same_attempt_never_resubmits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int
) -> None:
    identity = _positive_identity()
    monkeypatch.setattr(smoke_trigger, "POSITIVE_RECEIPT_ROOT", tmp_path)
    monkeypatch.setattr(
        smoke_trigger, "verify_positive_coordinator_checkout", lambda _identity: ()
    )
    execute_count = 0

    def run_fn(*args: str, timeout_seconds: int = 600) -> subprocess.CompletedProcess[str]:
        nonlocal execute_count
        if args[:3] == ("run", "jobs", "describe"):
            return subprocess.CompletedProcess([], 0, json.dumps(_ready_job()), "")
        if args[:4] == ("run", "jobs", "executions", "list"):
            return subprocess.CompletedProcess([], 0, "[]", "")
        execute_count += 1
        return subprocess.CompletedProcess([], exit_code, "", "safe-error")

    first = submit_positive_once(identity, project=PROJECT, run_fn=run_fn)
    second = submit_positive_once(identity, project=PROJECT, run_fn=run_fn)

    assert first["verdict"] == "OUTCOME_UNKNOWN"
    assert first["execute_count"] == 1
    assert second["verdict"] == "FAIL"
    assert second["codes"] == ["attempt_receipt_exists"]
    assert execute_count == 1


def test_positive_submit_timeout_is_unknown_and_o_excl_blocks_resubmit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = _positive_identity()
    monkeypatch.setattr(smoke_trigger, "POSITIVE_RECEIPT_ROOT", tmp_path)
    monkeypatch.setattr(
        smoke_trigger, "verify_positive_coordinator_checkout", lambda _identity: ()
    )
    execute_count = 0

    def run_fn(*args: str, timeout_seconds: int = 600) -> subprocess.CompletedProcess[str]:
        nonlocal execute_count
        if args[:3] == ("run", "jobs", "describe"):
            return subprocess.CompletedProcess([], 0, json.dumps(_ready_job()), "")
        if args[:4] == ("run", "jobs", "executions", "list"):
            return subprocess.CompletedProcess([], 0, "[]", "")
        execute_count += 1
        raise subprocess.TimeoutExpired(args, timeout_seconds)

    first = submit_positive_once(identity, project=PROJECT, run_fn=run_fn)
    second = submit_positive_once(identity, project=PROJECT, run_fn=run_fn)

    assert first["verdict"] == "OUTCOME_UNKNOWN"
    assert first["submit_exit_code"] is None
    assert second["codes"] == ["attempt_receipt_exists"]
    assert execute_count == 1


def test_positive_submit_fails_closed_on_readiness_or_existing_marker_before_execute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = _positive_identity()
    monkeypatch.setattr(smoke_trigger, "POSITIVE_RECEIPT_ROOT", tmp_path)
    monkeypatch.setattr(
        smoke_trigger, "verify_positive_coordinator_checkout", lambda _identity: ()
    )
    not_ready = _ready_job()
    not_ready["status"]["conditions"][0]["status"] = "False"  # type: ignore[index]

    def not_ready_fn(*args: str, timeout_seconds: int = 600) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, json.dumps(not_ready), "")

    result = submit_positive_once(identity, project=PROJECT, run_fn=not_ready_fn)
    assert result["execute_count"] == 0
    assert "job_not_ready" in result["codes"]

    other = PositiveSmokeLaunchIdentity.create(
        smoke_id="smoke5678",
        deployed_source_commit=COMMIT,
        deployed_source_tree=TREE,
        deployed_image_digest=DIGEST,
        plan_sha256=PLAN,
        bundle_sha256=BUNDLE,
        expected_project_sha256=PROJECT_HASH,
        expected_generation=27,
        coordinator_commit="1" * 40,
        coordinator_tree="2" * 40,
        coordinator_trigger_sha256="3" * 64,
    )

    # Bind the existing row to the fresh attempt marker to prove duplicate detection.
    existing = _positive_execution(other, marker=other.intent_sha256)
    def exact_marker_fn(*args: str, timeout_seconds: int = 600) -> subprocess.CompletedProcess[str]:
        if args[:3] == ("run", "jobs", "describe"):
            return subprocess.CompletedProcess([], 0, json.dumps(_ready_job()), "")
        return subprocess.CompletedProcess([], 0, json.dumps([existing]), "")

    result = submit_positive_once(other, project=PROJECT, run_fn=exact_marker_fn)
    assert result["execute_count"] == 0
    assert result["codes"] == ["intent_marker_already_present"]


def test_positive_reconcile_requires_exact_single_candidate_and_bindings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = _positive_identity()
    monkeypatch.setattr(smoke_trigger, "POSITIVE_RECEIPT_ROOT", tmp_path)
    monkeypatch.setattr(
        smoke_trigger, "verify_positive_coordinator_checkout", lambda _identity: ()
    )
    positive_receipt_path(identity).write_text(
        json.dumps(identity.to_receipt(), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    execution = _positive_execution(identity)

    def run_fn(*args: str, timeout_seconds: int = 600) -> subprocess.CompletedProcess[str]:
        if args[:4] == ("run", "jobs", "executions", "list"):
            return subprocess.CompletedProcess([], 0, json.dumps([execution]), "")
        return subprocess.CompletedProcess([], 0, json.dumps(execution), "")

    report = reconcile_positive(identity, project=PROJECT, run_fn=run_fn)
    assert report["verdict"] == "PASS"
    assert report["execution_count"] == 1
    assert "recall-cohort-daily" not in json.dumps(report)

    def duplicate_fn(*args: str, timeout_seconds: int = 600) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            [],
            0,
            json.dumps(
                [
                    execution,
                    _positive_execution(identity, name="recall-cohort-daily-pos34"),
                ]
            ),
            "",
        )

    ambiguous = reconcile_positive(identity, project=PROJECT, run_fn=duplicate_fn)
    assert ambiguous["verdict"] == "FAIL"
    assert ambiguous["codes"] == ["multiple_execution_candidates"]


@pytest.mark.parametrize(
    "mutation",
    ["prefix", "missing_arg", "duplicate_arg", "marker", "generation", "digest"],
)
def test_positive_reconcile_rejects_argument_marker_or_deployment_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    identity = _positive_identity()
    monkeypatch.setattr(smoke_trigger, "POSITIVE_RECEIPT_ROOT", tmp_path)
    monkeypatch.setattr(
        smoke_trigger, "verify_positive_coordinator_checkout", lambda _identity: ()
    )
    positive_receipt_path(identity).write_text(
        json.dumps(identity.to_receipt(), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    execution = _positive_execution(identity)
    container = execution["spec"]["template"]["spec"]["containers"][0]  # type: ignore[index]
    if mutation == "prefix":
        container["args"][-1] = "dev_recall_smoke_deadbeefdead_deadbeefdead_positive_smoke1234_"
    elif mutation == "missing_arg":
        container["args"].pop()
    elif mutation == "duplicate_arg":
        container["args"].extend(["--smoke-mode", "positive"])
    elif mutation == "marker":
        next(
            row
            for row in container["env"]
            if row["name"] == "RECALL_POSITIVE_SMOKE_INTENT_SHA256"
        )["value"] = "0" * 64
    elif mutation == "generation":
        execution["metadata"]["labels"]["run.googleapis.com/jobGeneration"] = "26"  # type: ignore[index]
    else:
        container["image"] = "registry/<project>/job@sha256:" + "f" * 64

    def run_fn(*args: str, timeout_seconds: int = 600) -> subprocess.CompletedProcess[str]:
        payload: object = (
            [execution]
            if args[:4] == ("run", "jobs", "executions", "list")
            else execution
        )
        return subprocess.CompletedProcess([], 0, json.dumps(payload), "")

    report = reconcile_positive(identity, project=PROJECT, run_fn=run_fn)
    assert report["verdict"] != "PASS"
    expected = {
        "prefix": "execution_args_mismatch",
        "missing_arg": "execution_args_mismatch",
        "duplicate_arg": "execution_args_mismatch",
        "marker": None,
        "generation": "execution_generation_mismatch",
        "digest": "execution_image_digest_mismatch",
    }[mutation]
    if expected is None:
        assert report["state"] == "PENDING"
    else:
        assert expected in report["codes"]


def test_positive_reconcile_rejects_receipt_tamper_without_cloud_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = _positive_identity()
    monkeypatch.setattr(smoke_trigger, "POSITIVE_RECEIPT_ROOT", tmp_path)
    monkeypatch.setattr(
        smoke_trigger, "verify_positive_coordinator_checkout", lambda _identity: ()
    )
    wire = identity.to_receipt()
    wire["intent_sha256"] = "0" * 64
    positive_receipt_path(identity).write_text(json.dumps(wire), encoding="utf-8")
    cloud_calls = 0

    def run_fn(*args: str, timeout_seconds: int = 600) -> subprocess.CompletedProcess[str]:
        nonlocal cloud_calls
        cloud_calls += 1
        return subprocess.CompletedProcess([], 0, "[]", "")

    report = reconcile_positive(identity, project=PROJECT, run_fn=run_fn)
    assert report["codes"] == ["attempt_receipt_invalid"]
    assert cloud_calls == 0
