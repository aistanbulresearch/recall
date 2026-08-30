from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ..errors import ContractError
from ..validation import SHA256, non_empty_string, require_exact_fields, uuid_value


_SOURCE_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_STATE_FIELDS = frozenset(
    {"CREATED", "HALTED", "NO_ACTION", "AUDITING", "WATCHING"}
)


@dataclass(frozen=True, slots=True)
class FinalExecutionRecoveryReceiptPayload:
    recovery_attempt_id: str
    identity_scope: str
    owner_decision: str
    owner_recovery_reason: str
    previous_execution_id: str
    previous_collection_prefix: str
    previous_source_commit: str
    previous_image_digest: str
    previous_plan_sha256: str
    previous_bundle_sha256: str
    previous_snapshot_sha256: str
    previous_state_counts: Mapping[str, int]
    previous_manifest_status: str
    previous_batch_receipt_id: str
    previous_batch_receipt_hash: str
    target_collection_prefix: str
    target_source_commit: str
    target_image_digest: str
    target_plan_sha256: str
    target_bundle_sha256: str
    target_case_count: int
    plan_cost_collection: str
    hard_cap_usd_micros: int
    baseline_reserved_usd_micros: int
    baseline_reconciled_usd_micros: int

    def to_wire(self) -> dict[str, object]:
        return {
            "recovery_attempt_id": self.recovery_attempt_id,
            "identity_scope": self.identity_scope,
            "owner_decision": self.owner_decision,
            "owner_recovery_reason": self.owner_recovery_reason,
            "previous_execution_id": self.previous_execution_id,
            "previous_collection_prefix": self.previous_collection_prefix,
            "previous_source_commit": self.previous_source_commit,
            "previous_image_digest": self.previous_image_digest,
            "previous_plan_sha256": self.previous_plan_sha256,
            "previous_bundle_sha256": self.previous_bundle_sha256,
            "previous_snapshot_sha256": self.previous_snapshot_sha256,
            "previous_state_counts": dict(self.previous_state_counts),
            "previous_manifest_status": self.previous_manifest_status,
            "previous_batch_receipt_id": self.previous_batch_receipt_id,
            "previous_batch_receipt_hash": self.previous_batch_receipt_hash,
            "target_collection_prefix": self.target_collection_prefix,
            "target_source_commit": self.target_source_commit,
            "target_image_digest": self.target_image_digest,
            "target_plan_sha256": self.target_plan_sha256,
            "target_bundle_sha256": self.target_bundle_sha256,
            "target_case_count": self.target_case_count,
            "plan_cost_collection": self.plan_cost_collection,
            "hard_cap_usd_micros": self.hard_cap_usd_micros,
            "baseline_reserved_usd_micros": self.baseline_reserved_usd_micros,
            "baseline_reconciled_usd_micros": self.baseline_reconciled_usd_micros,
        }


def parse_final_execution_recovery_receipt_payload(
    value: Mapping[str, Any],
) -> FinalExecutionRecoveryReceiptPayload:
    attempt_id = str(uuid_value(value["recovery_attempt_id"], "recovery_attempt_id"))
    identity_scope = non_empty_string(value["identity_scope"], "identity_scope")
    owner_decision = non_empty_string(value["owner_decision"], "owner_decision")
    owner_reason = non_empty_string(
        value["owner_recovery_reason"], "owner_recovery_reason"
    )
    if (
        not identity_scope.startswith("final-only-recovery:")
        or owner_decision != "AUTHORIZE_APPEND_ONLY_FINAL_RECOVERY"
        or owner_reason != "RECOVER_CANCELLED_FINAL_EXECUTION_APPEND_ONLY"
        or value["previous_manifest_status"] != "MISSING_AFTER_CANCELLED_EXECUTION"
    ):
        raise ContractError("contract_value_invalid", "final_recovery_authority")
    previous_execution = non_empty_string(
        value["previous_execution_id"], "previous_execution_id"
    )
    if not re.fullmatch(r"recall-cohort-daily-[a-z0-9-]+", previous_execution):
        raise ContractError("contract_value_invalid", "previous_execution_id")
    previous_prefix = _prefix(value["previous_collection_prefix"], "previous_collection_prefix")
    target_prefix = _prefix(value["target_collection_prefix"], "target_collection_prefix")
    if previous_prefix == target_prefix or not target_prefix.startswith("dev_recall_final_"):
        raise ContractError("contract_value_invalid", "target_collection_prefix")
    previous_source = _source(value["previous_source_commit"], "previous_source_commit")
    target_source = _source(value["target_source_commit"], "target_source_commit")
    previous_image = _image(value["previous_image_digest"], "previous_image_digest")
    target_image = _image(value["target_image_digest"], "target_image_digest")
    previous_plan = _sha(value["previous_plan_sha256"], "previous_plan_sha256")
    target_plan = _sha(value["target_plan_sha256"], "target_plan_sha256")
    previous_bundle = _sha(value["previous_bundle_sha256"], "previous_bundle_sha256")
    target_bundle = _sha(value["target_bundle_sha256"], "target_bundle_sha256")
    snapshot = _sha(value["previous_snapshot_sha256"], "previous_snapshot_sha256")
    batch_hash = _sha(value["previous_batch_receipt_hash"], "previous_batch_receipt_hash")
    batch_id = str(uuid_value(value["previous_batch_receipt_id"], "previous_batch_receipt_id"))
    states = value["previous_state_counts"]
    if not isinstance(states, Mapping):
        raise ContractError("contract_type_invalid", "previous_state_counts")
    require_exact_fields(states, _STATE_FIELDS, "previous_state_counts")
    state_counts = {key: _integer(states[key], key) for key in sorted(states)}
    if state_counts != {
        "AUDITING": 1,
        "CREATED": 417,
        "HALTED": 14,
        "NO_ACTION": 23,
        "WATCHING": 1,
    }:
        raise ContractError("contract_value_invalid", "previous_state_counts")
    target_count = _integer(value["target_case_count"], "target_case_count")
    cap = _integer(value["hard_cap_usd_micros"], "hard_cap_usd_micros")
    reserved = _integer(
        value["baseline_reserved_usd_micros"], "baseline_reserved_usd_micros"
    )
    reconciled = _integer(
        value["baseline_reconciled_usd_micros"],
        "baseline_reconciled_usd_micros",
    )
    cost_collection = non_empty_string(
        value["plan_cost_collection"], "plan_cost_collection"
    )
    if (
        target_count != 456
        or previous_plan != target_plan
        or previous_bundle != target_bundle
        or reserved > cap
        or reconciled > reserved
        or cost_collection != f"recall_plan6_cost_{target_plan[:16]}"
        or value["status"] != "VALID"
    ):
        raise ContractError("contract_value_invalid", "final_recovery_binding")
    return FinalExecutionRecoveryReceiptPayload(
        attempt_id,
        identity_scope,
        owner_decision,
        owner_reason,
        previous_execution,
        previous_prefix,
        previous_source,
        previous_image,
        previous_plan,
        previous_bundle,
        snapshot,
        MappingProxyType(state_counts),
        "MISSING_AFTER_CANCELLED_EXECUTION",
        batch_id,
        batch_hash,
        target_prefix,
        target_source,
        target_image,
        target_plan,
        target_bundle,
        target_count,
        cost_collection,
        cap,
        reserved,
        reconciled,
    )


def _sha(value: Any, field: str) -> str:
    text = non_empty_string(value, field)
    if not SHA256.fullmatch(text):
        raise ContractError("contract_hash_invalid", field)
    return text


def _source(value: Any, field: str) -> str:
    text = non_empty_string(value, field)
    if not _SOURCE_COMMIT.fullmatch(text):
        raise ContractError("contract_hash_invalid", field)
    return text


def _image(value: Any, field: str) -> str:
    text = non_empty_string(value, field)
    if not _IMAGE_DIGEST.fullmatch(text):
        raise ContractError("contract_hash_invalid", field)
    return text


def _prefix(value: Any, field: str) -> str:
    text = non_empty_string(value, field)
    if not re.fullmatch(r"dev_recall_[a-z0-9_]+", text):
        raise ContractError("contract_value_invalid", field)
    return text


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractError("contract_type_invalid", field)
    return value
