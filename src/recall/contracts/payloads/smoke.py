from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ..errors import ContractError
from ..validation import non_empty_string, tuple_of_strings, uuid_value


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_PREFIX = re.compile(
    r"^dev_recall_smoke_[0-9a-f]{12}_[0-9a-f]{12}_"
    r"(?:positive|negative)_[a-z0-9]{8,32}_$"
)


@dataclass(frozen=True, slots=True)
class IsolatedSmokeManifestPayload:
    smoke_id: str
    smoke_mode: str
    collection_prefix: str
    source_commit: str
    plan_sha256: str
    preparation_bundle_sha256: str
    image_digest: str
    selected_case_ids: tuple[str, ...]
    run_ids: tuple[str, ...]
    terminal_states: tuple[str, ...]
    audit_statuses: tuple[str, ...]
    agent_execution_receipt_ids: tuple[str, ...]
    policy_decision_ids: tuple[str, ...]
    failure_receipt_ids: tuple[str, ...]
    role_receipt_counts: Mapping[str, int]
    total_model_turns: int
    turn_budget_limit: int
    aggregate_turn_budget_limit: int
    provider_max_429_retries: int
    job_max_retries: int
    http_429_count: int
    reserved_cost_usd_micros: int
    reconciled_cost_usd_micros: int
    execution_status: str

    def to_wire(self) -> dict[str, object]:
        return {
            "smoke_id": self.smoke_id,
            "smoke_mode": self.smoke_mode,
            "collection_prefix": self.collection_prefix,
            "source_commit": self.source_commit,
            "plan_sha256": self.plan_sha256,
            "preparation_bundle_sha256": self.preparation_bundle_sha256,
            "image_digest": self.image_digest,
            "selected_case_ids": list(self.selected_case_ids),
            "run_ids": list(self.run_ids),
            "terminal_states": list(self.terminal_states),
            "audit_statuses": list(self.audit_statuses),
            "agent_execution_receipt_ids": list(
                self.agent_execution_receipt_ids
            ),
            "policy_decision_ids": list(self.policy_decision_ids),
            "failure_receipt_ids": list(self.failure_receipt_ids),
            "role_receipt_counts": dict(self.role_receipt_counts),
            "total_model_turns": self.total_model_turns,
            "turn_budget_limit": self.turn_budget_limit,
            "aggregate_turn_budget_limit": self.aggregate_turn_budget_limit,
            "provider_max_429_retries": self.provider_max_429_retries,
            "job_max_retries": self.job_max_retries,
            "http_429_count": self.http_429_count,
            "reserved_cost_usd_micros": self.reserved_cost_usd_micros,
            "reconciled_cost_usd_micros": self.reconciled_cost_usd_micros,
            "execution_status": self.execution_status,
        }


@dataclass(frozen=True, slots=True)
class IsolatedSmokeModeReceiptPayload:
    smoke_id: str
    collection_prefix: str
    source_commit: str
    plan_sha256: str
    preparation_bundle_sha256: str
    image_digest: str
    manifest_artifact_id: str
    manifest_content_hash: str
    agent_execution_receipt_ids: tuple[str, ...]
    mode_set: tuple[str, ...]
    declared_composition: str
    validation_status: str
    reason_codes: tuple[str, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "smoke_id": self.smoke_id,
            "collection_prefix": self.collection_prefix,
            "source_commit": self.source_commit,
            "plan_sha256": self.plan_sha256,
            "preparation_bundle_sha256": self.preparation_bundle_sha256,
            "image_digest": self.image_digest,
            "manifest_artifact_id": self.manifest_artifact_id,
            "manifest_content_hash": self.manifest_content_hash,
            "agent_execution_receipt_ids": list(
                self.agent_execution_receipt_ids
            ),
            "mode_set": list(self.mode_set),
            "declared_composition": self.declared_composition,
            "validation_status": self.validation_status,
            "reason_codes": list(self.reason_codes),
        }


def parse_isolated_smoke_manifest_payload(
    value: Mapping[str, Any],
) -> IsolatedSmokeManifestPayload:
    mode = _closed(value["smoke_mode"], "smoke_mode", {"POSITIVE", "NEGATIVE"})
    status = _closed(
        value["execution_status"],
        "execution_status",
        {"COMPLETE", "INCOMPLETE"},
    )
    selected = _ordered_strings(value["selected_case_ids"], "selected_case_ids")
    runs = _uuid_tuple(value["run_ids"], "run_ids")
    terminals = _ordered_strings(value["terminal_states"], "terminal_states")
    audits = _ordered_strings(value["audit_statuses"], "audit_statuses")
    if not (len(selected) == len(runs) == len(terminals) == len(audits)):
        raise ContractError("contract_value_invalid", "run_ids")
    expected_count = 4 if mode == "POSITIVE" else 1
    if len(selected) != expected_count or len(set(selected)) != expected_count:
        raise ContractError("contract_value_invalid", "selected_case_ids")
    agents = _uuid_tuple(
        value["agent_execution_receipt_ids"],
        "agent_execution_receipt_ids",
    )
    policies = _uuid_tuple(value["policy_decision_ids"], "policy_decision_ids")
    failures = _uuid_tuple(value["failure_receipt_ids"], "failure_receipt_ids")
    inputs = _uuid_tuple(value["input_artifact_ids"], "input_artifact_ids")
    if set(inputs) != set((*agents, *policies, *failures)):
        raise ContractError("contract_value_invalid", "input_artifact_ids")
    role_counts = _role_counts(value["role_receipt_counts"])
    turns = _non_negative(value["total_model_turns"], "total_model_turns")
    turn_limit = _non_negative(value["turn_budget_limit"], "turn_budget_limit")
    aggregate_limit = _non_negative(
        value["aggregate_turn_budget_limit"], "aggregate_turn_budget_limit"
    )
    provider_retries = _non_negative(
        value["provider_max_429_retries"], "provider_max_429_retries"
    )
    job_retries = _non_negative(value["job_max_retries"], "job_max_retries")
    http_429 = _non_negative(value["http_429_count"], "http_429_count")
    reserved = _non_negative(
        value["reserved_cost_usd_micros"], "reserved_cost_usd_micros"
    )
    reconciled = _non_negative(
        value["reconciled_cost_usd_micros"], "reconciled_cost_usd_micros"
    )
    expected_turn_limit = 24 if mode == "POSITIVE" else 2
    if (
        reserved != reconciled
        or http_429 != 0
        or turn_limit != expected_turn_limit
        or aggregate_limit != 26
        or provider_retries != 0
        or job_retries != 0
    ):
        raise ContractError("contract_value_invalid", "cost_or_429")
    if mode == "POSITIVE":
        if (
            status != "COMPLETE"
            or turns > 24
            or terminals != ("NO_ACTION",) * 4
            or set(audits) != {"COMPLETE"}
            or len(policies) != 4
            or failures
            or len(agents) != 12
            or role_counts
            != {
                "CITATION_AUDITOR": 4,
                "EVIDENCE_ASSESSOR": 4,
                "EVIDENCE_WATCHER": 4,
            }
        ):
            raise ContractError("contract_value_invalid", "smoke_positive")
    elif (
        status != "INCOMPLETE"
        or turns > 2
        or terminals != ("HALTED",)
        or audits != ("INCOMPLETE",)
        or policies
        or not failures
        or len(agents) != 1
        or role_counts != {"EVIDENCE_WATCHER": 1}
    ):
        raise ContractError("contract_value_invalid", "smoke_negative")
    smoke_id = _smoke_id(value["smoke_id"])
    prefix = _prefix(value["collection_prefix"])
    source_commit = _source(value["source_commit"])
    plan_sha256 = _sha(value["plan_sha256"], "plan_sha256")
    verify_smoke_prefix_binding(
        prefix=prefix,
        source_commit=source_commit,
        plan_sha256=plan_sha256,
        mode=mode,
    )
    return IsolatedSmokeManifestPayload(
        smoke_id=smoke_id,
        smoke_mode=mode,
        collection_prefix=prefix,
        source_commit=source_commit,
        plan_sha256=plan_sha256,
        preparation_bundle_sha256=_sha(
            value["preparation_bundle_sha256"],
            "preparation_bundle_sha256",
        ),
        image_digest=_image(value["image_digest"]),
        selected_case_ids=selected,
        run_ids=runs,
        terminal_states=terminals,
        audit_statuses=audits,
        agent_execution_receipt_ids=agents,
        policy_decision_ids=policies,
        failure_receipt_ids=failures,
        role_receipt_counts=MappingProxyType(role_counts),
        total_model_turns=turns,
        turn_budget_limit=turn_limit,
        aggregate_turn_budget_limit=aggregate_limit,
        provider_max_429_retries=provider_retries,
        job_max_retries=job_retries,
        http_429_count=http_429,
        reserved_cost_usd_micros=reserved,
        reconciled_cost_usd_micros=reconciled,
        execution_status=status,
    )


def parse_isolated_smoke_mode_receipt_payload(
    value: Mapping[str, Any],
) -> IsolatedSmokeModeReceiptPayload:
    manifest_id = str(uuid_value(value["manifest_artifact_id"], "manifest_artifact_id"))
    agent_ids = _uuid_tuple(
        value["agent_execution_receipt_ids"],
        "agent_execution_receipt_ids",
    )
    mode_inputs = tuple(value["input_artifact_ids"])
    if (
        len(mode_inputs) != 1 + len(agent_ids)
        or set(mode_inputs) != {manifest_id, *agent_ids}
    ):
        raise ContractError("contract_value_invalid", "manifest_artifact_id")
    modes = tuple_of_strings(value["mode_set"], "mode_set")
    reasons = tuple_of_strings(value["reason_codes"], "reason_codes")
    if (
        modes != ("SYNTHETIC",)
        or value["declared_composition"] != "SMOKE_ONLY_SYNTHETIC"
        or value["validation_status"] != "PASS"
        or reasons
    ):
        raise ContractError("contract_value_invalid", "validation_status")
    smoke_id = _smoke_id(value["smoke_id"])
    prefix = _prefix(value["collection_prefix"])
    source_commit = _source(value["source_commit"])
    plan_sha256 = _sha(value["plan_sha256"], "plan_sha256")
    verify_smoke_prefix_binding(
        prefix=prefix,
        source_commit=source_commit,
        plan_sha256=plan_sha256,
        mode="POSITIVE",
    )
    return IsolatedSmokeModeReceiptPayload(
        smoke_id=smoke_id,
        collection_prefix=prefix,
        source_commit=source_commit,
        plan_sha256=plan_sha256,
        preparation_bundle_sha256=_sha(
            value["preparation_bundle_sha256"],
            "preparation_bundle_sha256",
        ),
        image_digest=_image(value["image_digest"]),
        manifest_artifact_id=manifest_id,
        manifest_content_hash=_sha(
            value["manifest_content_hash"], "manifest_content_hash"
        ),
        agent_execution_receipt_ids=agent_ids,
        mode_set=modes,
        declared_composition="SMOKE_ONLY_SYNTHETIC",
        validation_status="PASS",
        reason_codes=reasons,
    )


def _uuid_tuple(value: Any, field: str) -> tuple[str, ...]:
    raw = _ordered_strings(value, field)
    parsed = tuple(str(uuid_value(item, field)) for item in raw)
    if len(set(parsed)) != len(parsed):
        raise ContractError("contract_value_invalid", field)
    return parsed


def _ordered_strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ContractError("contract_type_invalid", field)
    return tuple(non_empty_string(item, field) for item in value)


def _role_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "role_receipt_counts")
    allowed = {"EVIDENCE_WATCHER", "EVIDENCE_ASSESSOR", "CITATION_AUDITOR"}
    if not set(value).issubset(allowed):
        raise ContractError("contract_enum_invalid", "role_receipt_counts")
    return {
        str(key): _non_negative(item, f"role_receipt_counts.{key}")
        for key, item in value.items()
    }


def _non_negative(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractError("contract_type_invalid", field)
    return value


def _closed(value: Any, field: str, allowed: set[str]) -> str:
    parsed = non_empty_string(value, field)
    if parsed not in allowed:
        raise ContractError("contract_enum_invalid", field)
    return parsed


def _smoke_id(value: Any) -> str:
    parsed = non_empty_string(value, "smoke_id")
    if not re.fullmatch(r"[a-z0-9]{8,32}", parsed):
        raise ContractError("contract_value_invalid", "smoke_id")
    return parsed


def _prefix(value: Any) -> str:
    parsed = non_empty_string(value, "collection_prefix")
    if not _PREFIX.fullmatch(parsed):
        raise ContractError("contract_value_invalid", "collection_prefix")
    return parsed


def verify_smoke_prefix_binding(
    *, prefix: str, source_commit: str, plan_sha256: str, mode: str
) -> None:
    expected_mode = mode.lower()
    expected = (
        f"dev_recall_smoke_{source_commit[:12]}_{plan_sha256[:12]}_"
        f"{expected_mode}_"
    )
    if not prefix.startswith(expected):
        raise ContractError("contract_value_invalid", "collection_prefix")


def _source(value: Any) -> str:
    parsed = non_empty_string(value, "source_commit")
    if not _SOURCE_COMMIT.fullmatch(parsed):
        raise ContractError("contract_value_invalid", "source_commit")
    return parsed


def _sha(value: Any, field: str) -> str:
    parsed = non_empty_string(value, field)
    if not _SHA256.fullmatch(parsed):
        raise ContractError("contract_value_invalid", field)
    return parsed


def _image(value: Any) -> str:
    parsed = non_empty_string(value, "image_digest")
    if not _IMAGE_DIGEST.fullmatch(parsed):
        raise ContractError("contract_value_invalid", "image_digest")
    return parsed
