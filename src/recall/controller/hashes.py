from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from recall.contracts.canonical import canonical_json_bytes
from recall.contracts.errors import ContractError
from recall.contracts.validation import SHA256


def _hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def scan_idempotency_key(
    *,
    watch_case_id: str,
    source_cursors: Mapping[str, str],
    schedule_epoch: str,
    data_mode: str,
) -> str:
    return _hash(
        {
            "watch_case_id": watch_case_id,
            "source_cursors": dict(sorted(source_cursors.items())),
            "schedule_epoch": schedule_epoch,
            "data_mode": data_mode,
        }
    )

def review_deduplication_key(
    *, case_id: str, policy_decision_id: str, verified_delta_hash: str
) -> str:
    if not SHA256.fullmatch(verified_delta_hash):
        raise ContractError("contract_hash_invalid", "verified_delta_hash")
    return _hash(
        {
            "case_id": case_id,
            "policy_decision_id": policy_decision_id,
            "verified_delta_hash": verified_delta_hash,
        }
    )


def repeated_state_hash(state: Mapping[str, Any]) -> str:
    required = {
        "source_cursors",
        "last_verified_snapshot_id",
        "pending_observation_hashes",
        "latest_artifact_hashes",
    }
    missing = required - set(state)
    if missing:
        raise ContractError(
            "contract_required_field_missing", f"repeated_state:{sorted(missing)}"
        )
    cursors = state["source_cursors"]
    pending = state["pending_observation_hashes"]
    latest = state["latest_artifact_hashes"]
    if not isinstance(cursors, Mapping):
        raise ContractError("contract_type_invalid", "source_cursors")
    if not isinstance(pending, (list, tuple)) or not isinstance(
        latest, (list, tuple)
    ):
        raise ContractError("contract_type_invalid", "state_hashes")
    return _hash(
        {
            "source_cursors": dict(sorted(cursors.items())),
            "last_verified_snapshot_id": state["last_verified_snapshot_id"],
            "pending_observation_hashes": sorted(set(pending)),
            "latest_artifact_hashes": sorted(set(latest)),
        }
    )
