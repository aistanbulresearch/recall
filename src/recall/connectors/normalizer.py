from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any
from uuid import UUID, uuid5

from recall.contracts import (
    ArtifactStatus,
    DataMode,
    PresenceState,
    build_artifact,
)
from recall.ledger.producers import PRODUCER_REGISTRY


_TRANSCRIPT_HGVS = re.compile(
    r"^(?P<accession>[A-Z]{2}_[0-9]+\.[0-9]+)(?:\([A-Z0-9-]+\))?:(?P<hgvs>c\..+)$"
)


def normalize_transcript_hgvs(value: str) -> str:
    match = _TRANSCRIPT_HGVS.fullmatch(value.strip())
    if match is None:
        raise ValueError("transcript_hgvs_invalid")
    return f"{match.group('accession')}:{match.group('hgvs')}"


class EvidenceNormalizer:
    """Project frozen evidence into a non-clinical candidate-presence receipt."""

    def build_candidate_receipt(
        self,
        *,
        target_transcript_hgvs: str,
        observations: Iterable[Mapping[str, Any]],
        previous_snapshot_id: str | None,
        current_snapshot_id: str,
        last_verified_hashes: frozenset[str],
        snapshot_complete: bool,
        case_id: str,
        run_id: str,
        created_at: str,
    ) -> dict[str, object]:
        target = normalize_transcript_hgvs(target_transcript_hgvs)
        observation_set = tuple(observations)
        exact: list[Mapping[str, Any]] = []
        scoped: list[Mapping[str, Any]] = []
        for observation in observation_set:
            fields = observation.get("structured_fields")
            if not isinstance(fields, Mapping):
                continue
            observed = fields.get("transcript_hgvs")
            if not isinstance(observed, str):
                continue
            if normalize_transcript_hgvs(observed) != target:
                continue
            exact.append(observation)
            if self._in_source_scope(fields):
                scoped.append(observation)

        exact_match = bool(exact)
        scope_match = bool(scoped)
        new_hashes = tuple(
            sorted(
                {
                    str(item["source_content_hash"])
                    for item in scoped
                    if item.get("source_content_hash") not in last_verified_hashes
                }
            )
        )
        state, reasons = self._project_state(
            snapshot_complete=snapshot_complete,
            exact_match=exact_match,
            scope_match=scope_match,
            new_hashes=new_hashes,
        )
        return build_artifact(
            schema_name="CandidateDeltaReceipt",
            schema_version="1.0.0",
            artifact_id=str(uuid5(UUID(run_id), f"candidate:{target}")),
            case_id=case_id,
            run_id=run_id,
            producer={
                "component": "deterministic-evidence-normalizer",
                "version": "1.0.0",
                "identity": "evidence-normalizer",
            },
            created_at=created_at,
            input_artifact_ids=tuple(
                str(item["artifact_id"])
                for item in observation_set
                if "artifact_id" in item
            ),
            data_mode=DataMode.CAPTURED_REPLAY,
            status=ArtifactStatus.VALID,
            payload={
                "previous_snapshot_id": previous_snapshot_id,
                "current_snapshot_id": current_snapshot_id,
                "exact_allele_match": exact_match,
                "scope_match": scope_match,
                "snapshot_complete": snapshot_complete,
                "new_observation_hashes": list(new_hashes),
                "candidate_delta_state": state.value,
                "reason_codes": list(reasons),
            },
            authorized_producers=PRODUCER_REGISTRY,
        )

    @staticmethod
    def _in_source_scope(fields: Mapping[str, Any]) -> bool:
        scope = fields.get("source_scope")
        exon = fields.get("exon")
        if not isinstance(scope, Mapping) or not isinstance(exon, str):
            return False
        try:
            exon_number = float(exon)
            minimum = int(scope["exon_min"])
            maximum = int(scope["exon_max"])
        except (KeyError, TypeError, ValueError):
            return False
        return scope.get("gene") == "BRCA2" and minimum <= exon_number <= maximum

    @staticmethod
    def _project_state(
        *,
        snapshot_complete: bool,
        exact_match: bool,
        scope_match: bool,
        new_hashes: tuple[str, ...],
    ) -> tuple[PresenceState, tuple[str, ...]]:
        if not snapshot_complete:
            return PresenceState.UNKNOWN, ("snapshot_incomplete",)
        if not exact_match:
            return PresenceState.ABSENT, ("exact_allele_absent",)
        if not scope_match:
            return PresenceState.ABSENT, ("source_scope_not_matched",)
        if not new_hashes:
            return PresenceState.ABSENT, ("exact_allele_already_verified",)
        return PresenceState.PRESENT, ("exact_allele_new_in_source_scope",)
