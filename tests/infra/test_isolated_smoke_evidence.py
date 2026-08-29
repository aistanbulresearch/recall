from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[2] / "infra" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from isolated_smoke_evidence import evaluate_evidence  # noqa: E402


COMMIT = "a" * 40
TREE = "b" * 40
PLAN = "c" * 64
BUNDLE = "d" * 64
DIGEST = "sha256:" + "e" * 64


def _role(role: str, *, status: str = "COMPLETED", turns: int = 2) -> dict[str, object]:
    return {
        "role": role,
        "status": status,
        "turn_count": turns,
        "http_429_count": 0,
        "tool_call_count": 1,
        "tool_response_count": 1,
        "authorization_linked": True,
        "actual_caller_verified": True,
        "trace_observed": True,
        "cost_reconciled": True,
    }


def _execution(mode: str) -> dict[str, object]:
    return {
        "mode": mode,
        "terminal": True,
        "condition": "SUCCEEDED",
        "succeeded_count": 1,
        "failed_count": 0,
        "retried_count": 0,
        "task_count": 1,
        "creator_class": "MACHINE_SERVICE_ACCOUNT",
        "image_digest": DIGEST,
        "source_commit": COMMIT,
        "source_tree": TREE,
        "plan_sha256": PLAN,
        "bundle_sha256": BUNDLE,
        "actual_caller_config_verified": True,
    }


def _snapshot() -> dict[str, object]:
    positive_roles = [
        _role(role)
        for _ in range(4)
        for role in ("EVIDENCE_WATCHER", "EVIDENCE_ASSESSOR", "CITATION_AUDITOR")
    ]
    negative_role = _role("EVIDENCE_WATCHER", status="FAILED", turns=2)
    return {
        "positive": {
            "prefix_valid": True,
            "execution": _execution("positive"),
            "result": {
                "schema_name": "IsolatedSmokeResult",
                "schema_version": "1.0.0",
                "mode": "POSITIVE",
                "case_count": 4,
                "run_count": 4,
                "terminal_states": ["NO_ACTION"] * 4,
                "policy_decision_count": 4,
                "failure_receipt_count": 0,
                "total_model_turns": 24,
                "budget_limit": 24,
                "budget_observed": 24,
                "writes_scope_exact": True,
            },
            "roles": positive_roles,
            "manifest_status": "COMPLETE",
            "mode_receipt_verified": True,
            "idempotency_verified": True,
            "lease_terminal_verified": True,
        },
        "negative": {
            "prefix_valid": True,
            "execution": _execution("negative"),
            "result": {
                "schema_name": "IsolatedSmokeResult",
                "schema_version": "1.0.0",
                "mode": "NEGATIVE",
                "case_count": 1,
                "run_count": 1,
                "terminal_states": ["HALTED"],
                "policy_decision_count": 0,
                "failure_receipt_count": 1,
                "failure_codes": ["agent_schema_invalid"],
                "total_model_turns": 2,
                "budget_limit": 2,
                "budget_observed": 2,
                "writes_scope_exact": True,
            },
            "roles": [negative_role],
            "manifest_status": "INCOMPLETE",
            "mode_receipt_verified": False,
            "idempotency_verified": True,
            "lease_terminal_verified": True,
        },
    }


def test_exact_runtime_evidence_passes_both_smoke_modes() -> None:
    report = evaluate_evidence(_snapshot())
    assert report["verdict"] == "PASS"
    assert report["positive"] == "PASS"
    assert report["negative"] == "PASS"
    assert report["aggregate_model_turns"] == 26


def test_missing_runtime_surface_is_not_verified_not_inferred_from_config() -> None:
    snapshot = _snapshot()
    snapshot["positive"]["roles"][0]["trace_observed"] = None  # type: ignore[index]
    report = evaluate_evidence(snapshot)
    assert report["verdict"] == "NOT_VERIFIED"
    assert "trace_not_verified" in report["codes"]


def test_actual_caller_must_be_runtime_verified() -> None:
    snapshot = _snapshot()
    snapshot["positive"]["roles"][0]["actual_caller_verified"] = None  # type: ignore[index]
    report = evaluate_evidence(snapshot)
    assert report["verdict"] == "NOT_VERIFIED"
    assert "actual_caller_not_verified" in report["codes"]


def test_actual_caller_config_must_match_immutable_execution() -> None:
    snapshot = _snapshot()
    snapshot["positive"]["execution"]["actual_caller_config_verified"] = False  # type: ignore[index]
    report = evaluate_evidence(snapshot)
    assert report["verdict"] == "FAIL"
    assert "actual_caller_config_invalid" in report["codes"]


def test_contradictory_runtime_or_429_is_fail() -> None:
    snapshot = _snapshot()
    snapshot["positive"]["roles"][0]["http_429_count"] = 1  # type: ignore[index]
    report = evaluate_evidence(snapshot)
    assert report["verdict"] == "FAIL"
    assert "http_429_observed" in report["codes"]


def test_negative_probe_requires_real_tool_roundtrip_and_no_policy_decision() -> None:
    snapshot = _snapshot()
    snapshot["negative"]["roles"][0]["tool_response_count"] = 0  # type: ignore[index]
    report = evaluate_evidence(snapshot)
    assert report["negative"] == "FAIL"
    assert "negative_tool_roundtrip_invalid" in report["codes"]


def test_provenance_or_creator_drift_is_fail_closed() -> None:
    snapshot = _snapshot()
    snapshot["positive"]["execution"]["creator_class"] = "HUMAN"  # type: ignore[index]
    snapshot["negative"]["execution"]["source_tree"] = "f" * 40  # type: ignore[index]
    report = evaluate_evidence(snapshot)
    assert report["verdict"] == "FAIL"
    assert "machine_creator_required" in report["codes"]
    assert "cross_execution_provenance_mismatch" in report["codes"]


def test_safe_report_contains_no_raw_identifiers_or_addresses() -> None:
    snapshot = _snapshot()
    snapshot["positive"]["execution"]["raw_execution_id"] = "recall-cohort-daily-secret"
    snapshot["positive"]["execution"]["creator"] = "human@example.com"
    report = evaluate_evidence(snapshot)
    encoded = json.dumps(report, sort_keys=True)
    assert "recall-cohort-daily-secret" not in encoded
    assert "human@example.com" not in encoded


def test_aggregate_budget_is_hard_capped_at_26() -> None:
    snapshot = deepcopy(_snapshot())
    snapshot["negative"]["result"]["total_model_turns"] = 3  # type: ignore[index]
    snapshot["negative"]["result"]["budget_observed"] = 3  # type: ignore[index]
    report = evaluate_evidence(snapshot)
    assert report["verdict"] == "FAIL"
    assert "aggregate_turn_budget_exceeded" in report["codes"]
