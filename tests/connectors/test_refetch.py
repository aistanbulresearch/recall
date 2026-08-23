from __future__ import annotations

from hashlib import sha256

import pytest

from recall.connectors.live import (
    LiveSourceRecord,
    SourceResponseInvalid,
    SourceUnavailable,
)
from recall.connectors.refetch import (
    CitedSource,
    RefetchAdapter,
    RefetchedSource,
    normalize_title,
)
from recall.contracts import CitationVerdict, DataMode


HASH_A = sha256(b"a").hexdigest()
HASH_B = sha256(b"b").hexdigest()


def _cited(**changes: str) -> CitedSource:
    values = {
        "identifier": "12345678",
        "title": "BRCA2: variant evidence — a study.",
        "locator": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        "content_hash": HASH_A,
        "mode": DataMode.CAPTURED_REPLAY,
    }
    values.update(changes)
    return CitedSource(**values)


def _refetched(**changes: str) -> LiveSourceRecord:
    values = {
        "identifier": "12345678",
        "title": "brca2 variant evidence a study",
        "locator": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        "content_hash": HASH_A,
        "mode": DataMode.LIVE_PUBLIC,
    }
    values.update(changes)
    return LiveSourceRecord(**values)


def test_normalized_title_is_unicode_case_and_punctuation_stable() -> None:
    assert normalize_title(" BRCA2: Evidence — Study. ") == normalize_title(
        "brca2 evidence study"
    )


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"identifier": "87654321"}, "refetch_identifier_mismatch"),
        ({"title": "Different title"}, "refetch_title_mismatch"),
        ({"content_hash": HASH_B}, "refetch_content_hash_mismatch"),
    ],
)
def test_any_identifier_title_or_hash_difference_is_mismatch(
    changes: dict[str, str], reason: str
) -> None:
    result = RefetchAdapter().compare(_cited(), _refetched(**changes))

    assert result.verdict is CitationVerdict.MISMATCH
    assert reason in result.reason_codes
    assert result.refetched_source is not None


def test_all_three_equal_is_verified_and_wire_shape_matches_audit_contract() -> None:
    result = RefetchAdapter().compare(_cited(), _refetched())

    assert result.verdict is CitationVerdict.VERIFIED
    assert result.reason_codes == ("refetch_metadata_verified",)
    assert result.mode is DataMode.LIVE_PUBLIC
    assert result.to_claim_verdict("claim-001") == {
        "claim_id": "claim-001",
        "verdict": "VERIFIED",
        "reason_codes": ["refetch_metadata_verified"],
        "refetched_source": {
            "identifier": "12345678",
            "title": "brca2 variant evidence a study",
            "locator": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
            "content_hash": HASH_A,
        },
    }


def test_multiple_differences_are_reported_in_fixed_order() -> None:
    result = RefetchAdapter().compare(
        _cited(),
        _refetched(
            identifier="87654321", title="Different", content_hash=HASH_B
        ),
    )

    assert result.reason_codes == (
        "refetch_identifier_mismatch",
        "refetch_title_mismatch",
        "refetch_content_hash_mismatch",
    )


def test_network_absence_is_unavailable_never_verified() -> None:
    def unavailable(identifier: str) -> LiveSourceRecord:
        raise SourceUnavailable("pubmed_source_unavailable")

    result = RefetchAdapter().refetch(_cited(), unavailable)

    assert result.verdict is CitationVerdict.UNAVAILABLE
    assert result.reason_codes == ("refetch_source_unavailable",)
    assert result.refetched_source is None
    assert result.mode is DataMode.LIVE_PUBLIC
    assert result.to_claim_verdict("claim-001")["refetched_source"] is None


def test_invalid_public_response_is_unavailable_never_verified() -> None:
    def malformed(identifier: str) -> LiveSourceRecord:
        raise SourceResponseInvalid("pubmed_summary_invalid")

    result = RefetchAdapter().refetch(_cited(), malformed)

    assert result.verdict is CitationVerdict.UNAVAILABLE
    assert result.refetched_source is None


def test_captured_replay_refetch_keeps_replay_mode_explicit() -> None:
    replay_source = RefetchedSource(
        identifier="12345678",
        title="brca2 variant evidence a study",
        locator="capture://pubmed/12345678",
        content_hash=HASH_A,
        mode=DataMode.CAPTURED_REPLAY,
    )

    result = RefetchAdapter().compare(_cited(), replay_source)

    assert result.verdict is CitationVerdict.VERIFIED
    assert result.mode is DataMode.CAPTURED_REPLAY


def test_replay_and_live_boundaries_are_explicit_and_closed() -> None:
    with pytest.raises(ValueError, match="cited_source_mode_invalid"):
        _cited(mode=DataMode.SYNTHETIC)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="refetched_source_mode_invalid"):
        _refetched(mode=DataMode.MOCK)  # type: ignore[arg-type]
