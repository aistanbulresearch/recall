from __future__ import annotations

from pathlib import Path

import pytest

from recall.connectors.normalizer import EvidenceNormalizer, normalize_transcript_hgvs
from recall.connectors.replay import ReplayConnector
from recall.contracts import PresenceState, ReplayStage


REPO_ROOT = Path(__file__).parents[2]
MANIFEST = REPO_ROOT / "docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json"
CASE_ID = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
RUN_ID = "b1d74cb8-25ac-4a84-ab9d-5a71a366c2da"
SNAPSHOT_ID = "f7617fa1-2f75-47f3-b88d-ec72e88e3051"


def observations(stage: ReplayStage) -> tuple[dict[str, object], ...]:
    return ReplayConnector(REPO_ROOT, MANIFEST).build_observations(
        stage=stage,
        case_id=CASE_ID,
        run_id=RUN_ID,
        created_at="2026-08-22T06:30:00Z",
    )


def normalize(target: str, *, complete: bool = True) -> dict[str, object]:
    return EvidenceNormalizer().build_candidate_receipt(
        target_transcript_hgvs=target,
        observations=observations(ReplayStage.STAGE_1),
        previous_snapshot_id=None,
        current_snapshot_id=SNAPSHOT_ID,
        last_verified_hashes=frozenset(),
        snapshot_complete=complete,
        case_id=CASE_ID,
        run_id=RUN_ID,
        created_at="2026-08-22T06:30:00Z",
    )


def test_gene_annotation_is_removed_without_changing_exact_allele() -> None:
    assert normalize_transcript_hgvs("NM_000059.4:c.7522G>C") == (
        normalize_transcript_hgvs("NM_000059.4(BRCA2):c.7522G>C")
    )


def test_exact_allele_in_source_scope_is_present() -> None:
    receipt = normalize("NM_000059.4:c.7522G>C")

    assert receipt["candidate_delta_state"] == PresenceState.PRESENT.value
    assert receipt["exact_allele_match"] is True
    assert receipt["scope_match"] is True
    assert receipt["new_observation_hashes"]
    assert receipt["producer"]["identity"] == "evidence-normalizer"


@pytest.mark.parametrize(
    "target",
    ["NM_000059.4:c.425+3A>G", "NM_000059.4:c.1315T>G"],
)
def test_same_gene_negative_controls_are_absent(target: str) -> None:
    receipt = normalize(target)

    assert receipt["candidate_delta_state"] == PresenceState.ABSENT.value
    assert receipt["exact_allele_match"] is False
    assert receipt["scope_match"] is False
    assert receipt["new_observation_hashes"] == []
    assert "exact_allele_absent" in receipt["reason_codes"]


def test_gene_only_match_never_creates_candidate() -> None:
    receipt = normalize("NM_000059.4:c.9999A>T")

    assert receipt["candidate_delta_state"] == PresenceState.ABSENT.value
    assert receipt["exact_allele_match"] is False


def test_already_verified_exact_observation_is_not_new() -> None:
    stage_observations = observations(ReplayStage.STAGE_1)
    matching_hash = next(
        item["source_content_hash"]
        for item in stage_observations
        if item["source_record_id"] == "geo_gse248438_results_xlsx"
    )
    receipt = EvidenceNormalizer().build_candidate_receipt(
        target_transcript_hgvs="NM_000059.4:c.7522G>C",
        observations=stage_observations,
        previous_snapshot_id=None,
        current_snapshot_id=SNAPSHOT_ID,
        last_verified_hashes=frozenset({matching_hash}),
        snapshot_complete=True,
        case_id=CASE_ID,
        run_id=RUN_ID,
        created_at="2026-08-22T06:30:00Z",
    )

    assert receipt["candidate_delta_state"] == PresenceState.ABSENT.value
    assert receipt["reason_codes"] == ["exact_allele_already_verified"]


def test_incomplete_snapshot_is_unknown_even_with_exact_match() -> None:
    receipt = normalize("NM_000059.4:c.7522G>C", complete=False)

    assert receipt["candidate_delta_state"] == PresenceState.UNKNOWN.value
    assert receipt["snapshot_complete"] is False
