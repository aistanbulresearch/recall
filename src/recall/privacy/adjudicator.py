"""Deterministic adjudication of local model span proposals.

The local model proposes. This module decides. Every rejection carries a stable
reason code so the receipt can explain why a proposal was not approved without
ever exposing the surface text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from recall.privacy.gemma import GemmaOutcome, GemmaProposal
from recall.privacy.spans import DETECTOR_GEMMA, IDENTIFIER_CLASSES, DetectedSpan

ADJUDICATOR_VERSION = "span-adjudicator@1.0.0"
MAX_APPROVED_RESIDUAL_SPANS = 8
MAX_SPAN_LENGTH = 128
WORD_PATTERN = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]+")


@dataclass(frozen=True)
class AdjudicationResult:
    approved: tuple[DetectedSpan, ...]
    rejected_reason_codes: tuple[str, ...]
    proposal_count: int
    approved_count: int
    rejected_count: int


class SpanAdjudicator:
    """Applies fixed rules to every proposal before it may affect redaction."""

    version = ADJUDICATOR_VERSION

    def __init__(self, safe_words: frozenset[str] | None = None) -> None:
        self._safe_words = safe_words or frozenset()

    def adjudicate(
        self,
        outcome: GemmaOutcome,
        text: str,
        existing_spans: tuple[DetectedSpan, ...] | list[DetectedSpan],
    ) -> AdjudicationResult:
        if not outcome.usable:
            return AdjudicationResult((), (), 0, 0, 0)

        approved: list[DetectedSpan] = []
        rejected: list[str] = []
        for proposal in outcome.proposals:
            reason = self._rejection_reason(proposal, text, existing_spans, approved)
            if reason is not None:
                rejected.append(reason)
                continue
            approved.append(
                DetectedSpan(
                    start=proposal.start,
                    end=proposal.end,
                    identifier_class=proposal.identifier_class,
                    detector=DETECTOR_GEMMA,
                    rule_id="model-proposal-approved",
                )
            )

        return AdjudicationResult(
            approved=tuple(sorted(approved, key=lambda span: (span.start, span.end))),
            rejected_reason_codes=tuple(sorted(set(rejected))),
            proposal_count=len(outcome.proposals),
            approved_count=len(approved),
            rejected_count=len(rejected),
        )

    def _rejection_reason(
        self,
        proposal: GemmaProposal,
        text: str,
        existing_spans: tuple[DetectedSpan, ...] | list[DetectedSpan],
        approved: list[DetectedSpan],
    ) -> str | None:
        if proposal.identifier_class not in IDENTIFIER_CLASSES:
            return "proposal_unregistered_class"
        if proposal.start < 0 or proposal.end <= proposal.start or proposal.end > len(text):
            return "proposal_out_of_bounds"
        if proposal.end - proposal.start > MAX_SPAN_LENGTH:
            return "proposal_span_too_long"
        surface = text[proposal.start : proposal.end]
        if not surface.strip():
            return "proposal_empty_surface"
        if not WORD_PATTERN.search(surface):
            return "proposal_no_word_characters"
        if len(approved) >= MAX_APPROVED_RESIDUAL_SPANS:
            return "proposal_budget_exhausted"

        candidate = DetectedSpan(proposal.start, proposal.end, proposal.identifier_class, DETECTOR_GEMMA)
        if any(candidate.overlaps(existing) for existing in existing_spans):
            return "proposal_overlaps_deterministic_span"
        if any(candidate.overlaps(existing) for existing in approved):
            return "proposal_overlaps_approved_span"

        words = [word.lower() for word in WORD_PATTERN.findall(surface)]
        if words and all(word in self._safe_words for word in words):
            return "proposal_matches_known_safe_vocabulary"
        return None
