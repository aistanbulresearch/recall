"""Fail-closed semantic verdict for the isolated fleet smoke evidence.

The live collector normalizes only allowlisted fields into the shape accepted by
``evaluate_evidence``.  This evaluator deliberately returns codes and counts,
never execution IDs, case IDs, trace IDs, principals, or artifact contents.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


PASS = "PASS"
FAIL = "FAIL"
NOT_VERIFIED = "NOT_VERIFIED"
ROLES = ("EVIDENCE_WATCHER", "EVIDENCE_ASSESSOR", "CITATION_AUDITOR")
PROVENANCE_FIELDS = (
    "image_digest",
    "source_commit",
    "source_tree",
    "plan_sha256",
    "bundle_sha256",
)


class _Verdict:
    def __init__(self) -> None:
        self.failed: set[str] = set()
        self.unknown: set[str] = set()

    def require(self, value: Any, code: str) -> None:
        if value is None:
            self.unknown.add(f"{code}_not_verified")
        elif value is not True:
            self.failed.add(f"{code}_invalid")

    @property
    def state(self) -> str:
        if self.failed:
            return FAIL
        if self.unknown:
            return NOT_VERIFIED
        return PASS


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    return value if isinstance(value, Sequence) and not isinstance(value, str) else ()


def _execution(verdict: _Verdict, value: Mapping[str, Any]) -> None:
    verdict.require(value.get("terminal"), "execution_terminal")
    verdict.require(value.get("condition") == "SUCCEEDED", "execution_condition")
    verdict.require(value.get("succeeded_count") == 1, "execution_succeeded_count")
    verdict.require(value.get("failed_count") == 0, "execution_failed_count")
    verdict.require(value.get("retried_count") == 0, "execution_retry_count")
    verdict.require(value.get("task_count") == 1, "execution_task_count")
    if value.get("creator_class") is None:
        verdict.unknown.add("creator_class_not_verified")
    elif value.get("creator_class") != "MACHINE_SERVICE_ACCOUNT":
        verdict.failed.add("machine_creator_required")
    verdict.require(
        value.get("actual_caller_config_verified"),
        "actual_caller_config",
    )
    for field in PROVENANCE_FIELDS:
        if not value.get(field):
            verdict.unknown.add(f"{field}_not_verified")


def _common_result(
    verdict: _Verdict, result: Mapping[str, Any], *, mode: str, limit: int
) -> int:
    verdict.require(
        result.get("schema_name") == "IsolatedSmokeResult"
        and result.get("schema_version") == "1.0.0",
        "smoke_result_schema",
    )
    verdict.require(result.get("mode") == mode.upper(), "smoke_result_mode")
    verdict.require(result.get("writes_scope_exact"), "writes_scope")
    observed = result.get("total_model_turns")
    budget_limit = result.get("budget_limit")
    budget_observed = result.get("budget_observed")
    if not all(isinstance(item, int) for item in (observed, budget_limit, budget_observed)):
        verdict.unknown.add("turn_budget_not_verified")
        return 0
    if budget_limit != limit or budget_observed != observed or observed > limit:
        verdict.failed.add(f"{mode}_turn_budget_exceeded")
    return int(observed)


def _role_checks(verdict: _Verdict, roles: Sequence[Any], *, mode: str) -> None:
    rows = [_mapping(item) for item in roles]
    counts = Counter(str(item.get("role")) for item in rows)
    if mode == "positive":
        expected = Counter({role: 4 for role in ROLES})
        if counts != expected or len(rows) != 12:
            verdict.failed.add("positive_role_topology_invalid")
        if any(item.get("status") != "COMPLETED" for item in rows):
            verdict.failed.add("positive_role_status_invalid")
    else:
        if counts != Counter({"EVIDENCE_WATCHER": 1}) or len(rows) != 1:
            verdict.failed.add("negative_role_topology_invalid")
        elif rows[0].get("status") != "FAILED":
            verdict.failed.add("negative_role_status_invalid")
    for item in rows:
        turns = item.get("turn_count")
        if not isinstance(turns, int):
            verdict.unknown.add("role_turn_count_not_verified")
        elif turns < 1 or turns > 2:
            verdict.failed.add("role_turn_count_invalid")
        http_429 = item.get("http_429_count")
        if http_429 is None:
            verdict.unknown.add("http_429_not_verified")
        elif http_429 != 0:
            verdict.failed.add("http_429_observed")
        for field, code in (
            ("authorization_linked", "authorization_linkage"),
            ("actual_caller_verified", "actual_caller"),
            ("trace_observed", "trace"),
            ("cost_reconciled", "cost_reconciliation"),
        ):
            verdict.require(item.get(field), code)
        calls = item.get("tool_call_count")
        responses = item.get("tool_response_count")
        if calls is None or responses is None:
            verdict.unknown.add("tool_roundtrip_not_verified")
        elif calls < 1 or calls != responses:
            verdict.failed.add(
                "negative_tool_roundtrip_invalid"
                if mode == "negative"
                else "positive_tool_roundtrip_invalid"
            )


def _positive(value: Mapping[str, Any]) -> tuple[_Verdict, int]:
    verdict = _Verdict()
    verdict.require(value.get("prefix_valid"), "positive_prefix")
    _execution(verdict, _mapping(value.get("execution")))
    result = _mapping(value.get("result"))
    turns = _common_result(verdict, result, mode="positive", limit=24)
    verdict.require(result.get("case_count") == 4, "positive_case_count")
    verdict.require(result.get("run_count") == 4, "positive_run_count")
    verdict.require(
        tuple(_sequence(result.get("terminal_states"))) == ("NO_ACTION",) * 4,
        "positive_terminal_states",
    )
    verdict.require(result.get("policy_decision_count") == 4, "positive_policy_count")
    verdict.require(result.get("failure_receipt_count") == 0, "positive_failures")
    _role_checks(verdict, _sequence(value.get("roles")), mode="positive")
    verdict.require(value.get("manifest_status") == "COMPLETE", "positive_manifest")
    verdict.require(value.get("mode_receipt_verified"), "positive_mode_receipt")
    verdict.require(value.get("idempotency_verified"), "positive_idempotency")
    verdict.require(value.get("lease_terminal_verified"), "positive_lease_terminal")
    return verdict, turns


def _negative(value: Mapping[str, Any]) -> tuple[_Verdict, int]:
    verdict = _Verdict()
    verdict.require(value.get("prefix_valid"), "negative_prefix")
    _execution(verdict, _mapping(value.get("execution")))
    result = _mapping(value.get("result"))
    turns = _common_result(verdict, result, mode="negative", limit=2)
    verdict.require(result.get("case_count") == 1, "negative_case_count")
    verdict.require(result.get("run_count") == 1, "negative_run_count")
    verdict.require(
        tuple(_sequence(result.get("terminal_states"))) == ("HALTED",),
        "negative_terminal_state",
    )
    verdict.require(result.get("policy_decision_count") == 0, "negative_policy_absence")
    verdict.require(result.get("failure_receipt_count") == 1, "negative_failure_count")
    verdict.require(
        tuple(_sequence(result.get("failure_codes"))) == ("agent_schema_invalid",),
        "negative_failure_code",
    )
    _role_checks(verdict, _sequence(value.get("roles")), mode="negative")
    verdict.require(value.get("manifest_status") == "INCOMPLETE", "negative_manifest")
    verdict.require(value.get("mode_receipt_verified") is False, "negative_mode_absence")
    verdict.require(value.get("idempotency_verified"), "negative_idempotency")
    verdict.require(value.get("lease_terminal_verified"), "negative_lease_terminal")
    return verdict, turns


def evaluate_evidence(
    snapshot: Mapping[str, Any], *, expected: Mapping[str, str] | None = None
) -> dict[str, object]:
    """Return only a typed verdict, safe reason codes, and aggregate counts."""

    positive = _mapping(snapshot.get("positive"))
    negative = _mapping(snapshot.get("negative"))
    positive_verdict, positive_turns = _positive(positive)
    negative_verdict, negative_turns = _negative(negative)
    positive_execution = _mapping(positive.get("execution"))
    negative_execution = _mapping(negative.get("execution"))
    cross_failures: set[str] = set()
    cross_unknown: set[str] = set()
    for field in PROVENANCE_FIELDS:
        left = positive_execution.get(field)
        right = negative_execution.get(field)
        if left is None or right is None:
            cross_unknown.add(f"{field}_not_verified")
        elif left != right:
            cross_failures.add("cross_execution_provenance_mismatch")
        if expected is not None and field in expected and left != expected[field]:
            cross_failures.add(f"expected_{field}_mismatch")
    aggregate = positive_turns + negative_turns
    if aggregate > 26:
        cross_failures.add("aggregate_turn_budget_exceeded")
    all_failures = (
        positive_verdict.failed | negative_verdict.failed | cross_failures
    )
    all_unknown = (
        positive_verdict.unknown | negative_verdict.unknown | cross_unknown
    )
    overall = FAIL if all_failures else NOT_VERIFIED if all_unknown else PASS
    return {
        "verdict": overall,
        "positive": positive_verdict.state,
        "negative": negative_verdict.state,
        "aggregate_model_turns": aggregate,
        "codes": sorted(all_failures | all_unknown),
    }
