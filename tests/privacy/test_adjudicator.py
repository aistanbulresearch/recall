"""Deterministic adjudication keeps model proposals non-authoritative."""

from __future__ import annotations

from recall.privacy.adjudicator import SpanAdjudicator
from recall.privacy.gemma import GemmaOutcome, GemmaProposal, STATUS_OK, STATUS_TIMEOUT
from recall.privacy.spans import DetectedSpan

TEXT = "Rapor kopyasi Zzyzx Qwertius ile paylasildi. Kurum: Bati Genetik Laboratuvari."


def outcome(*proposals: GemmaProposal, status: str = STATUS_OK, schema_valid: bool = True) -> GemmaOutcome:
    return GemmaOutcome(invoked=True, status=status, schema_valid=schema_valid, proposals=proposals)


def test_in_bounds_proposal_is_approved() -> None:
    result = SpanAdjudicator().adjudicate(outcome(GemmaProposal(14, 28, "PERSON_NAME")), TEXT, ())
    assert result.approved_count == 1
    assert result.approved[0].detector == "gemma"


def test_out_of_bounds_proposal_is_rejected() -> None:
    result = SpanAdjudicator().adjudicate(outcome(GemmaProposal(0, len(TEXT) + 50, "PERSON_NAME")), TEXT, ())
    assert result.approved_count == 0
    assert "proposal_span_too_long" in result.rejected_reason_codes or "proposal_out_of_bounds" in result.rejected_reason_codes


def test_inverted_span_is_rejected() -> None:
    result = SpanAdjudicator().adjudicate(outcome(GemmaProposal(20, 10, "PERSON_NAME")), TEXT, ())
    assert result.rejected_reason_codes == ("proposal_out_of_bounds",)


def test_overlap_with_deterministic_span_is_rejected() -> None:
    existing = (DetectedSpan(14, 28, "PERSON_NAME"),)
    result = SpanAdjudicator().adjudicate(outcome(GemmaProposal(14, 20, "PERSON_NAME")), TEXT, existing)
    assert result.approved_count == 0
    assert result.rejected_reason_codes == ("proposal_overlaps_deterministic_span",)


def test_known_safe_vocabulary_is_not_redacted_on_model_request() -> None:
    adjudicator = SpanAdjudicator(safe_words=frozenset({"rapor", "kopyasi"}))
    result = adjudicator.adjudicate(outcome(GemmaProposal(0, 13, "PERSON_NAME")), TEXT, ())
    assert result.rejected_reason_codes == ("proposal_matches_known_safe_vocabulary",)


def test_unusable_outcome_yields_no_approved_spans() -> None:
    result = SpanAdjudicator().adjudicate(
        outcome(GemmaProposal(14, 28, "PERSON_NAME"), status=STATUS_TIMEOUT, schema_valid=False), TEXT, ()
    )
    assert result.approved == ()
    assert result.proposal_count == 0


def test_approved_span_budget_is_bounded() -> None:
    proposals = tuple(GemmaProposal(i * 3, i * 3 + 2, "PERSON_NAME") for i in range(12))
    result = SpanAdjudicator().adjudicate(outcome(*proposals), TEXT * 3, ())
    assert result.approved_count <= 8
    assert "proposal_budget_exhausted" in result.rejected_reason_codes
