from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ..enums import FactState, PresenceState
from ..errors import ContractError
from ..validation import SHA256, enum_value, tuple_of_strings, uuid_value
from .lifecycle import _timestamp


@dataclass(frozen=True, slots=True)
class EvidenceSnapshotPayload:
    effective_at: str
    observation_ids: tuple[str, ...]
    coverage_status: FactState
    source_cursors: Mapping[str, str]
    normalized_facts: Mapping[str, object]
    conflicts: tuple[Mapping[str, object], ...]
    snapshot_hash: str

    def to_wire(self) -> dict[str, object]:
        return {
            "effective_at": self.effective_at,
            "observation_ids": list(self.observation_ids),
            "coverage_status": self.coverage_status.value,
            "source_cursors": dict(self.source_cursors),
            "normalized_facts": dict(self.normalized_facts),
            "conflicts": [dict(item) for item in self.conflicts],
            "snapshot_hash": self.snapshot_hash,
        }


def parse_evidence_snapshot_payload(
    value: Mapping[str, Any],
) -> EvidenceSnapshotPayload:
    observation_ids = tuple_of_strings(value["observation_ids"], "observation_ids")
    for artifact_id in observation_ids:
        uuid_value(artifact_id, "observation_ids")
    cursors = value["source_cursors"]
    facts = value["normalized_facts"]
    conflicts = value["conflicts"]
    if not isinstance(cursors, Mapping) or any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in cursors.items()
    ):
        raise ContractError("contract_type_invalid", "source_cursors")
    if not isinstance(facts, Mapping):
        raise ContractError("contract_type_invalid", "normalized_facts")
    if not isinstance(conflicts, list) or any(
        not isinstance(item, Mapping) for item in conflicts
    ):
        raise ContractError("contract_type_invalid", "conflicts")
    snapshot_hash = value["snapshot_hash"]
    if not isinstance(snapshot_hash, str) or not SHA256.fullmatch(snapshot_hash):
        raise ContractError("contract_hash_invalid", "snapshot_hash")
    coverage_status = enum_value(
        FactState, value["coverage_status"], "coverage_status"
    )
    if coverage_status is FactState.PASS and (not cursors or not facts):
        raise ContractError(
            "contract_required_value_missing", "source_cursors_or_normalized_facts"
        )
    return EvidenceSnapshotPayload(
        effective_at=_timestamp(value["effective_at"], "effective_at"),
        observation_ids=observation_ids,
        coverage_status=coverage_status,
        source_cursors=MappingProxyType(dict(sorted(cursors.items()))),
        normalized_facts=MappingProxyType(dict(facts)),
        conflicts=tuple(MappingProxyType(dict(item)) for item in conflicts),
        snapshot_hash=snapshot_hash,
    )


@dataclass(frozen=True, slots=True)
class CandidateDeltaPayload:
    previous_snapshot_id: str | None
    current_snapshot_id: str
    exact_allele_match: bool
    scope_match: bool
    snapshot_complete: bool
    new_observation_hashes: tuple[str, ...]
    candidate_delta_state: PresenceState
    reason_codes: tuple[str, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "previous_snapshot_id": self.previous_snapshot_id,
            "current_snapshot_id": self.current_snapshot_id,
            "exact_allele_match": self.exact_allele_match,
            "scope_match": self.scope_match,
            "snapshot_complete": self.snapshot_complete,
            "new_observation_hashes": list(self.new_observation_hashes),
            "candidate_delta_state": self.candidate_delta_state.value,
            "reason_codes": list(self.reason_codes),
        }


def parse_candidate_delta_payload(
    value: Mapping[str, Any],
) -> CandidateDeltaPayload:
    for field in ("exact_allele_match", "scope_match", "snapshot_complete"):
        if not isinstance(value[field], bool):
            raise ContractError("contract_type_invalid", field)
    hashes = tuple_of_strings(
        value["new_observation_hashes"], "new_observation_hashes"
    )
    if any(not SHA256.fullmatch(item) for item in hashes):
        raise ContractError("contract_hash_invalid", "new_observation_hashes")
    state = enum_value(
        PresenceState, value["candidate_delta_state"], "candidate_delta_state"
    )
    if state is PresenceState.PRESENT and not hashes:
        raise ContractError(
            "contract_required_value_missing", "new_observation_hashes"
        )
    if state is PresenceState.ABSENT and hashes:
        raise ContractError("contract_value_invalid", "new_observation_hashes")
    return CandidateDeltaPayload(
        previous_snapshot_id=uuid_value(
            value["previous_snapshot_id"], "previous_snapshot_id", nullable=True
        ),
        current_snapshot_id=str(
            uuid_value(value["current_snapshot_id"], "current_snapshot_id")
        ),
        exact_allele_match=value["exact_allele_match"],
        scope_match=value["scope_match"],
        snapshot_complete=value["snapshot_complete"],
        new_observation_hashes=hashes,
        candidate_delta_state=state,
        reason_codes=tuple_of_strings(value["reason_codes"], "reason_codes"),
    )
