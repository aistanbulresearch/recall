from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ..enums import PolicyOutcome, RunAuditStatus, TerminalState
from ..errors import ContractError
from ..validation import SHA256, enum_value, non_empty_string, require_exact_fields, tuple_of_strings, uuid_value
from .scheduler_v3 import _PLAN_SHA256S
from .scheduler_v31 import CohortDayManifestV31Payload, parse_cohort_day_manifest_v31_payload


_SUMMARY_FIELDS = frozenset(
    {
        "execution_profile", "runtime_class", "concurrency", "model_id",
        "endpoint_class", "total_runs", "complete_runs", "incomplete_runs",
        "not_evaluated_runs", "halted_runs", "total_agent_invocations",
        "total_prompt_tokens", "total_candidate_tokens", "total_thoughts_tokens",
        "total_tokens", "p50_latency_ms", "p95_latency_ms", "http_429_count",
        "projected_cost_usd_micros", "reserved_cost_usd_micros",
        "pricing_policy_sha256", "actual_billed_cost_state",
    }
)
_OUTCOME_FIELDS = frozenset(
    {
        "case_id", "run_id", "epoch_label", "terminal_state", "audit_status",
        "citation_audit_receipt_id", "policy_decision_id", "policy_outcome",
        "policy_reason_codes", "technical_failure_codes", "failure_receipt_ids",
        "agent_execution_receipt_ids", "elapsed_ms",
    }
)


@dataclass(frozen=True, slots=True)
class CohortDayManifestV32Payload:
    base: CohortDayManifestV31Payload
    plan_sha256: str
    epoch_label: str
    agent_execution_summary: Mapping[str, object]
    run_outcomes: tuple[Mapping[str, object], ...]
    execution_history: tuple[Mapping[str, object], ...]

    def __getattr__(self, name: str) -> object:
        return getattr(self.base, name)

    def to_wire(self) -> dict[str, object]:
        value = self.base.to_wire()
        value["plan_sha256"] = self.plan_sha256
        value["epoch_label"] = self.epoch_label
        value["execution_history"] = [dict(item) for item in self.execution_history]
        value["agent_execution_summary"] = dict(self.agent_execution_summary)
        value["run_outcomes"] = [
            {
                **dict(item),
                "policy_reason_codes": list(item["policy_reason_codes"]),
                "technical_failure_codes": list(item["technical_failure_codes"]),
                "failure_receipt_ids": list(item["failure_receipt_ids"]),
                "agent_execution_receipt_ids": list(
                    item["agent_execution_receipt_ids"]
                ),
            }
            for item in self.run_outcomes
        ]
        return value


def parse_cohort_day_manifest_v32_payload(
    value: Mapping[str, Any],
) -> CohortDayManifestV32Payload:
    plan_sha256 = non_empty_string(value["plan_sha256"], "plan_sha256")
    if not SHA256.fullmatch(plan_sha256):
        raise ContractError("contract_hash_invalid", "plan_sha256")
    epoch_label = non_empty_string(value["epoch_label"], "epoch_label")
    if not epoch_label.startswith("PLAN6_"):
        raise ContractError("contract_value_invalid", "epoch_label")
    summary = _parse_summary(value["agent_execution_summary"])
    outcomes = _parse_outcomes(value["run_outcomes"], epoch_label)
    _validate_outcome_binding(value, summary, outcomes)

    legacy = dict(value)
    legacy.pop("agent_execution_summary")
    legacy.pop("run_outcomes")
    legacy["schema_version"] = "3.1.0"
    legacy["plan_sha256"] = sorted(_PLAN_SHA256S)[0]
    legacy["epoch_label"] = "PLAN5_V32_COMPATIBILITY"
    history = [dict(item) for item in value["execution_history"]]
    if history[-1]["source_schema_version"] != "CohortDayManifest/3.2.0":
        raise ContractError("contract_value_invalid", "execution_history.current")
    for row in history:
        if row["source_schema_version"] == "CohortDayManifest/3.2.0":
            row["source_schema_version"] = "CohortDayManifest/3.1.0"
    history[-1]["executed_at"] = value["write_metrics"]["completed_at"]
    legacy["execution_history"] = history
    # V3.1 completion measures only the batched write/readback phase. V3.2's
    # envelope completes after the agent phase, while retaining those original
    # write metrics as a separately auditable measurement.
    legacy["created_at"] = value["write_metrics"]["completed_at"]
    write_qualified = _write_qualified(value)
    legacy["status"] = "VALID" if write_qualified else "INCOMPLETE"
    base = parse_cohort_day_manifest_v31_payload(legacy)

    agent_qualified = (
        summary["halted_runs"] == 0
        and summary["incomplete_runs"] == 0
        and summary["not_evaluated_runs"] == 0
        and summary["complete_runs"] == summary["total_runs"]
        and all(item["policy_outcome"] is not None for item in outcomes)
    )
    expected_status = "VALID" if write_qualified and agent_qualified else "INCOMPLETE"
    if value["status"] != expected_status:
        raise ContractError("contract_value_invalid", "agent_qualification_status")
    return CohortDayManifestV32Payload(
        base=base,
        plan_sha256=plan_sha256,
        epoch_label=epoch_label,
        agent_execution_summary=MappingProxyType(summary),
        run_outcomes=outcomes,
        execution_history=tuple(
            MappingProxyType(dict(item)) for item in value["execution_history"]
        ),
    )


def _parse_summary(value: Any) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "agent_execution_summary")
    require_exact_fields(value, _SUMMARY_FIELDS, "agent_execution_summary")
    parsed = dict(value)
    if value["execution_profile"] != "FULL_AUDIT_V1":
        raise ContractError("contract_value_invalid", "execution_profile")
    if value["runtime_class"] != "IN_PROCESS_ADK_CLOUD_RUN":
        raise ContractError("contract_value_invalid", "runtime_class")
    if value["model_id"] != "gemini-3.7-flash" or value["endpoint_class"] != "VERTEX_AI_GLOBAL":
        raise ContractError("contract_value_invalid", "model_endpoint")
    if value["actual_billed_cost_state"] != "NOT_VERIFIED":
        raise ContractError("contract_value_invalid", "actual_billed_cost_state")
    for field in _SUMMARY_FIELDS - {
        "execution_profile", "runtime_class", "model_id", "endpoint_class",
        "pricing_policy_sha256", "actual_billed_cost_state",
    }:
        parsed[field] = _integer(value[field], field)
    if not 1 <= parsed["concurrency"] <= 4:
        raise ContractError("contract_value_invalid", "concurrency")
    if parsed["total_tokens"] != (
        parsed["total_prompt_tokens"]
        + parsed["total_candidate_tokens"]
        + parsed["total_thoughts_tokens"]
    ):
        raise ContractError("contract_value_invalid", "total_tokens")
    if parsed["p95_latency_ms"] < parsed["p50_latency_ms"]:
        raise ContractError("contract_value_invalid", "latency_percentiles")
    if parsed["reserved_cost_usd_micros"] < parsed["projected_cost_usd_micros"]:
        raise ContractError("contract_value_invalid", "projected_cost")
    if parsed["reserved_cost_usd_micros"] > 75_000_000:
        raise ContractError("contract_value_invalid", "projected_cost_cap")
    pricing_hash = non_empty_string(
        value["pricing_policy_sha256"], "pricing_policy_sha256"
    )
    if not SHA256.fullmatch(pricing_hash):
        raise ContractError("contract_hash_invalid", "pricing_policy_sha256")
    parsed["pricing_policy_sha256"] = pricing_hash
    return parsed


def _parse_outcomes(
    value: Any, epoch_label: str
) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list):
        raise ContractError("contract_type_invalid", "run_outcomes")
    outcomes: list[Mapping[str, object]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise ContractError("contract_type_invalid", "run_outcomes")
        require_exact_fields(raw, _OUTCOME_FIELDS, f"run_outcomes[{index}]")
        audit = enum_value(RunAuditStatus, raw["audit_status"], "audit_status")
        terminal = enum_value(TerminalState, raw["terminal_state"], "terminal_state")
        citation_id = uuid_value(
            raw["citation_audit_receipt_id"],
            "citation_audit_receipt_id",
            nullable=True,
        )
        policy_id = uuid_value(
            raw["policy_decision_id"], "policy_decision_id", nullable=True
        )
        raw_outcome = raw["policy_outcome"]
        policy_outcome = (
            None
            if raw_outcome is None
            else enum_value(PolicyOutcome, raw_outcome, "policy_outcome")
        )
        failure_codes = tuple_of_strings(
            raw["technical_failure_codes"], "technical_failure_codes"
        )
        failure_ids = _uuid_tuple(raw["failure_receipt_ids"], "failure_receipt_ids")
        execution_ids = _uuid_tuple(
            raw["agent_execution_receipt_ids"], "agent_execution_receipt_ids"
        )
        if (
            len(execution_ids) > 12
            or len(execution_ids) % 2 != 0
            or len(set(execution_ids)) != len(execution_ids)
            or (terminal is not TerminalState.HALTED and len(execution_ids) < 6)
        ):
            raise ContractError(
                "contract_value_invalid", "agent_execution_receipt_ids"
            )
        if (audit is RunAuditStatus.NOT_EVALUATED) is not (citation_id is None):
            raise ContractError("contract_value_invalid", "audit_status")
        if terminal is TerminalState.HALTED:
            if policy_id is not None or policy_outcome is not None or not failure_codes or not failure_ids:
                raise ContractError("contract_value_invalid", "halted_outcome")
        elif policy_id is None or policy_outcome is None or failure_codes or failure_ids:
            raise ContractError("contract_value_invalid", "policy_outcome")
        if raw["epoch_label"] != epoch_label:
            raise ContractError("contract_value_invalid", "run_outcomes.epoch_label")
        outcomes.append(
            MappingProxyType(
                {
                    "case_id": str(uuid_value(raw["case_id"], "case_id")),
                    "run_id": str(uuid_value(raw["run_id"], "run_id")),
                    "epoch_label": epoch_label,
                    "terminal_state": terminal.value,
                    "audit_status": audit.value,
                    "citation_audit_receipt_id": citation_id,
                    "policy_decision_id": policy_id,
                    "policy_outcome": None if policy_outcome is None else policy_outcome.value,
                    "policy_reason_codes": tuple_of_strings(raw["policy_reason_codes"], "policy_reason_codes"),
                    "technical_failure_codes": failure_codes,
                    "failure_receipt_ids": failure_ids,
                    "agent_execution_receipt_ids": execution_ids,
                    "elapsed_ms": _integer(raw["elapsed_ms"], "elapsed_ms"),
                }
            )
        )
    return tuple(outcomes)


def _validate_outcome_binding(
    value: Mapping[str, Any],
    summary: Mapping[str, object],
    outcomes: tuple[Mapping[str, object], ...],
) -> None:
    run_ids = [item["run_id"] for item in outcomes]
    case_ids = [item["case_id"] for item in outcomes]
    if (
        len(set(run_ids)) != len(run_ids)
        or len(set(case_ids)) != len(case_ids)
        or set(run_ids) != set(value["delta"]["authoritative_run_ids"])
        or set(case_ids) != set(value["delta"]["selected_case_ids"])
    ):
        raise ContractError("contract_value_invalid", "run_outcomes.binding")
    audits = [item["audit_status"] for item in outcomes]
    terminals = [item["terminal_state"] for item in outcomes]
    expected_counts = {
        "total_runs": len(outcomes),
        "complete_runs": audits.count("COMPLETE"),
        "incomplete_runs": audits.count("INCOMPLETE"),
        "not_evaluated_runs": audits.count("NOT_EVALUATED"),
        "halted_runs": terminals.count("HALTED"),
        "total_agent_invocations": sum(
            len(item["agent_execution_receipt_ids"]) // 2 for item in outcomes
        ),
    }
    if any(summary[field] != expected for field, expected in expected_counts.items()):
        raise ContractError("contract_value_invalid", "agent_execution_summary")
    inputs = set(value["input_artifact_ids"])
    required = set()
    for item in outcomes:
        required.update(item["agent_execution_receipt_ids"])
        required.update(item["failure_receipt_ids"])
        if item["citation_audit_receipt_id"] is not None:
            required.add(item["citation_audit_receipt_id"])
        if item["policy_decision_id"] is not None:
            required.add(item["policy_decision_id"])
    if not required.issubset(inputs):
        raise ContractError("contract_value_invalid", "run_outcomes.inputs")


def _write_qualified(value: Mapping[str, Any]) -> bool:
    metrics = value["write_metrics"]
    parity = value["parity"]
    return bool(
        parity["parity_match"]
        and metrics["persistence_surface"] == "LIVE_FIRESTORE"
        and int(metrics["effective_write_millis_per_case"]) <= 2000
        and len(value["delta"]["authoritative_run_ids"])
        == value["delta"]["runs_predicted"]
    )


def _uuid_tuple(value: Any, field: str) -> tuple[str, ...]:
    values = tuple_of_strings(value, field)
    return tuple(str(uuid_value(item, field)) for item in values)


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractError("contract_type_invalid", field)
    return value
