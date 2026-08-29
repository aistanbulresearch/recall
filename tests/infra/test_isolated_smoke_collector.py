from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "infra" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from isolated_smoke_collector import (  # noqa: E402
    _trace_has_required_spans,
    _lease_is_inactive,
    _validate_receipt_topology,
    _validate_terminal_pointers,
    collect_from_receipt,
)
from isolated_smoke_trigger import SmokePair  # noqa: E402


COMMIT = "a" * 40
TREE = "b" * 40
PLAN = "c" * 64
BUNDLE = "d" * 64
DIGEST = "sha256:" + "e" * 64
SMOKE_ID = "smoke1234"
PROJECT = "sample-project"
PROJECT_HASH = hashlib.sha256(PROJECT.encode("utf-8")).hexdigest()


def _pair() -> SmokePair:
    return SmokePair.create(
        smoke_id=SMOKE_ID,
        source_commit=COMMIT,
        source_tree=TREE,
        plan_sha256=PLAN,
        bundle_sha256=BUNDLE,
        image_digest=DIGEST,
    )


def _receipt(path: Path) -> Path:
    pair = _pair()
    path.write_text(
        json.dumps(
            {
                "schema_name": "IsolatedSmokeExecutionPair",
                "schema_version": "1.0.0",
                "positive_execution": "recall-cohort-daily-pos12",
                "negative_execution": "recall-cohort-daily-neg34",
                "positive_prefix": pair.positive_prefix,
                "negative_prefix": pair.negative_prefix,
                "source_commit": COMMIT,
                "source_tree": TREE,
                "plan_sha256": PLAN,
                "bundle_sha256": BUNDLE,
                "image_digest": DIGEST,
                "expected_project_sha256": PROJECT_HASH,
                "smoke_id": SMOKE_ID,
            }
        ),
        encoding="utf-8",
    )
    return path


def _execution(mode: str) -> dict[str, object]:
    pair = _pair()
    prefix = pair.positive_prefix if mode == "positive" else pair.negative_prefix
    return {
        "name": f"recall-cohort-daily-{'pos12' if mode == 'positive' else 'neg34'}",
        "creator": "smoke-runner@sample-project.iam.gserviceaccount.com",
        "conditions": [{"type": "Completed", "state": "CONDITION_SUCCEEDED"}],
        "succeededCount": 1,
        "failedCount": 0,
        "retriedCount": 0,
        "runningCount": 0,
        "template": {
            "taskCount": 1,
            "maxRetries": 0,
            "timeout": "28800s",
            "serviceAccount": (
                "recall-sa-cohort-job@<project>.iam.gserviceaccount.com"
            ),
            "containers": [
                {
                    "image": "us-central1-docker.pkg.dev/<project-id>/repo/job@" + DIGEST,
                    "args": list(pair.entrypoint_args(mode)),
                    "env": [
                        {"name": "RECALL_SOURCE_COMMIT", "value": COMMIT},
                        {"name": "RECALL_SOURCE_TREE", "value": TREE},
                        {"name": "RECALL_PROVIDER_RPM", "value": "8"},
                        {"name": "FULL_AUDIT_CONCURRENCY", "value": "2"},
                        {
                            "name": "RECALL_COMPRESSED_PREPARATION_SHA256",
                            "value": BUNDLE,
                        },
                        {"name": "RECALL_IMAGE_DIGEST", "value": DIGEST},
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
                            "name": "RECALL_EXPECTED_PROJECT_SHA256",
                            "value": PROJECT_HASH,
                        },
                        {
                            "name": "RECALL_SCHEDULER_MODE",
                            "value": "COMPRESSED_V3",
                        },
                        {
                            "name": "RECALL_WATCHER_PRINCIPAL",
                            "value": "recall-sa-watcher@<project>.iam.gserviceaccount.com",
                        },
                        {
                            "name": "RECALL_ASSESSOR_PRINCIPAL",
                            "value": "recall-sa-assessor@<project>.iam.gserviceaccount.com",
                        },
                        {
                            "name": "RECALL_AUDITOR_PRINCIPAL",
                            "value": "recall-sa-auditor@<project>.iam.gserviceaccount.com",
                        },
                        {
                            "name": "RECALL_TOOL_CAPABILITY_SECRET_B64",
                            "valueFrom": {
                                "secretKeyRef": {"name": "capability", "key": "latest"}
                            },
                        },
                        {
                            "name": "RECALL_NCBI_TOOL",
                            "valueSource": {
                                "secretKeyRef": {"secret": "tool", "version": "latest"}
                            },
                        },
                        {
                            "name": "RECALL_NCBI_EMAIL",
                            "valueSource": {
                                "secretKeyRef": {"secret": "email", "version": "3"}
                            },
                        },
                    ],
                    "resources": {"limits": {"cpu": "1", "memory": "512Mi"}},
                }
            ],
        },
    }


def _semantic(mode: str) -> dict[str, object]:
    pair = _pair()
    positive = mode == "positive"
    return {
        "schema_name": "IsolatedSmokeCollectionVerification",
        "schema_version": "1.0.0",
        "verified": True,
        "writes": 0,
        "smoke_id": SMOKE_ID,
        "mode": mode.upper(),
        "collection_prefix": pair.positive_prefix if positive else pair.negative_prefix,
        "source_commit": COMMIT,
        "plan_sha256": PLAN,
        "preparation_bundle_sha256": BUNDLE,
        "image_digest": DIGEST,
        "manifest_artifact_id": "manifest-id",
        "manifest_content_hash": "f" * 64,
        "mode_receipt_artifact_id": "mode-id" if positive else None,
        "mode_receipt_content_hash": "1" * 64 if positive else None,
        "execution_status": "COMPLETE" if positive else "INCOMPLETE",
        "selected_case_ids": [f"case-{index}" for index in range(4 if positive else 1)],
        "run_ids": [f"run-{index}" for index in range(4 if positive else 1)],
        "cost": {"reserved_usd_micros": 120, "reconciled_usd_micros": 120},
    }


def _role(role: str, *, status: str = "COMPLETED") -> dict[str, object]:
    return {
        "role": role,
        "status": status,
        "turn_count": 1,
        "http_429_count": 0,
        "tool_call_count": 1,
        "tool_response_count": 1,
        "authorization_linked": True,
        "actual_caller_verified": True,
        "trace_observed": True,
        "cost_reconciled": True,
    }


def _telemetry(mode: str) -> dict[str, object]:
    if mode == "positive":
        roles = [
            _role(role)
            for _ in range(4)
            for role in (
                "EVIDENCE_WATCHER",
                "EVIDENCE_ASSESSOR",
                "CITATION_AUDITOR",
            )
        ]
        return {
            "roles": roles,
            "terminal_states": ["NO_ACTION"] * 4,
            "policy_decision_count": 4,
            "failure_receipt_count": 0,
            "failure_codes": [],
            "total_model_turns": 12,
            "manifest_status": "COMPLETE",
            "mode_receipt_verified": True,
            "idempotency_verified": True,
            "lease_terminal_verified": True,
        }
    return {
        "roles": [_role("EVIDENCE_WATCHER", status="FAILED")],
        "terminal_states": ["HALTED"],
        "policy_decision_count": 0,
        "failure_receipt_count": 1,
        "failure_codes": ["agent_schema_invalid"],
        "total_model_turns": 1,
        "manifest_status": "INCOMPLETE",
        "mode_receipt_verified": False,
        "idempotency_verified": True,
        "lease_terminal_verified": True,
    }


def _collect(
    tmp_path: Path,
    *,
    execution_mutator=None,
    telemetry_mutator=None,
    semantic_error: Exception | None = None,
):
    def run_fn(*args: str, timeout_seconds: int = 600):
        execution_id = args[4]
        mode = "positive" if execution_id.endswith("pos12") else "negative"
        value = _execution(mode)
        if execution_mutator is not None:
            execution_mutator(mode, value)
        return subprocess.CompletedProcess([], 0, json.dumps(value), "")

    def semantic_fn(mode: str, _pair_value: SmokePair):
        if mode == "positive" and semantic_error is not None:
            raise semantic_error
        return _semantic(mode)

    def telemetry_fn(mode: str, _pair_value: SmokePair, _semantic_value):
        value = _telemetry(mode)
        if telemetry_mutator is not None:
            telemetry_mutator(mode, value)
        return value

    return collect_from_receipt(
        _receipt(tmp_path / "receipt.json"),
        run_fn=run_fn,
        semantic_collect_fn=semantic_fn,
        telemetry_collect_fn=telemetry_fn,
    )


def test_pair_collector_joins_execution_semantic_and_runtime_evidence(tmp_path: Path) -> None:
    report = _collect(tmp_path)
    assert report["verdict"] == "PASS"
    assert report["positive"] == "PASS"
    assert report["negative"] == "PASS"
    assert report["aggregate_model_turns"] == 13


def test_execution_args_or_machine_creator_drift_fails(tmp_path: Path) -> None:
    def mutate(mode: str, value: dict[str, object]) -> None:
        if mode == "positive":
            value["creator"] = "human@example.com"
        else:
            value["template"]["containers"][0]["args"] = []  # type: ignore[index]

    report = _collect(tmp_path, execution_mutator=mutate)
    assert report["verdict"] == "FAIL"
    assert "machine_creator_required" in report["codes"]
    assert "execution_args_invalid" in report["codes"]


def test_immutable_execution_candidate_or_role_principal_drift_fails(
    tmp_path: Path,
) -> None:
    def mutate(mode: str, value: dict[str, object]) -> None:
        container = value["template"]["containers"][0]  # type: ignore[index]
        env = container["env"]
        if mode == "positive":
            next(row for row in env if row["name"] == "RECALL_PROVIDER_RPM")["value"] = "9"
        else:
            next(row for row in env if row["name"] == "RECALL_WATCHER_PRINCIPAL")["value"] = "human@example.com"

    report = _collect(tmp_path, execution_mutator=mutate)
    assert report["verdict"] == "FAIL"
    assert "provider_rpm_mismatch" in report["codes"]
    assert "actual_caller_config_invalid" in report["codes"]


def test_missing_live_trace_is_not_verified(tmp_path: Path) -> None:
    def mutate(mode: str, value: dict[str, object]) -> None:
        if mode == "positive":
            value["roles"][0]["trace_observed"] = None  # type: ignore[index]

    report = _collect(tmp_path, telemetry_mutator=mutate)
    assert report["verdict"] == "NOT_VERIFIED"
    assert "trace_not_verified" in report["codes"]


def test_durable_contract_mismatch_fails_without_exception_details(tmp_path: Path) -> None:
    report = _collect(
        tmp_path,
        semantic_error=RuntimeError("smoke_cost_snapshot_mismatch:raw-artifact-id"),
    )
    encoded = json.dumps(report, sort_keys=True)
    assert report["verdict"] == "FAIL"
    assert "positive_durable_evidence_invalid" in report["codes"]
    assert "raw-artifact-id" not in encoded


def test_unavailable_external_evidence_remains_not_verified(tmp_path: Path) -> None:
    report = _collect(tmp_path, semantic_error=OSError("credentials unavailable"))
    assert report["verdict"] == "NOT_VERIFIED"
    assert "positive_durable_evidence_not_verified" in report["codes"]


def test_receipt_topology_rejects_missing_or_invalid_started_and_auth_bindings() -> None:
    terminal = SimpleNamespace(
        payload=SimpleNamespace(
            started_receipt_id="started",
            tool_records=({"authorization_receipt_id": "auth"},),
        )
    )
    with pytest.raises(RuntimeError, match="smoke_started_receipt_missing"):
        _validate_receipt_topology(terminal, {})

    artifacts = {"started": object(), "auth": object()}

    def invalid_started(_terminal, _started) -> None:
        from recall.contracts import ContractError

        raise ContractError("ledger_integrity_failed", "started_receipt_binding")

    with pytest.raises(RuntimeError, match="smoke_receipt_topology_invalid"):
        _validate_receipt_topology(
            terminal,
            artifacts,
            started_validator=invalid_started,
            authorization_validator=lambda *_args: None,
        )

    def invalid_auth(_terminal, _receipts) -> None:
        from recall.contracts import ContractError

        raise ContractError("ledger_integrity_failed", "tool_authorization_binding")

    with pytest.raises(RuntimeError, match="smoke_receipt_topology_invalid"):
        _validate_receipt_topology(
            terminal,
            artifacts,
            started_validator=lambda *_args: None,
            authorization_validator=invalid_auth,
        )


def test_terminal_pointer_sets_and_full_trace_topology_are_exact() -> None:
    record = SimpleNamespace(
        failure_receipt_ids=("failure",), terminal_policy_decision_id="policy"
    )
    artifacts = [
        SimpleNamespace(schema_name="FailureReceipt", artifact_id="failure"),
        SimpleNamespace(schema_name="PolicyDecision", artifact_id="policy"),
    ]
    _validate_terminal_pointers(record, artifacts)
    with pytest.raises(RuntimeError, match="smoke_terminal_pointer_mismatch"):
        _validate_terminal_pointers(
            record,
            artifacts + [SimpleNamespace(schema_name="FailureReceipt", artifact_id="extra")],
        )
    assert _trace_has_required_spans(
        {
            "state": "OBSERVED",
            "span_names": [
                "recall.controller.scan_run",
                "recall.agent.evidence_watcher",
                "recall.agent.evidence_assessor",
                "recall.agent.citation_auditor",
            ],
        },
        mode="positive",
    ) is True
    assert _trace_has_required_spans(
        {"state": "OBSERVED", "span_names": ["recall.controller.scan_run"]},
        mode="positive",
    ) is False


def test_terminal_lease_must_be_inactive_at_collection_time() -> None:
    now = datetime(2026, 8, 29, 10, 0, tzinfo=UTC)
    assert _lease_is_inactive(
        SimpleNamespace(lease_expires_at=None), now=now
    ) is True
    assert _lease_is_inactive(
        SimpleNamespace(lease_expires_at=now - timedelta(seconds=1)), now=now
    ) is True
    assert _lease_is_inactive(
        SimpleNamespace(lease_expires_at=now + timedelta(seconds=1)), now=now
    ) is False


def test_report_never_emits_raw_execution_artifact_case_run_or_email_ids(tmp_path: Path) -> None:
    encoded = json.dumps(_collect(tmp_path), sort_keys=True)
    for forbidden in (
        "recall-cohort-daily-pos12",
        "manifest-id",
        "case-0",
        "run-0",
        "smoke-runner@sample-project.iam.gserviceaccount.com",
    ):
        assert forbidden not in encoded
