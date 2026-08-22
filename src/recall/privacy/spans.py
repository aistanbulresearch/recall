"""Span value objects shared by the detectors, adjudicator, and redactor."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Iterable

DIRECT_IDENTIFIER_CLASSES = (
    "PERSON_NAME",
    "RELATIVE_NAME",
    "CLINICIAN_NAME",
    "NATIONAL_ID",
    "MEDICAL_RECORD_NUMBER",
    "PROTOCOL_NUMBER",
    "PHONE",
    "EMAIL",
    "ADDRESS",
    "FACILITY_NAME",
    "DATE_OF_BIRTH",
    "EVENT_DATE",
)
QUASI_IDENTIFIER_CLASSES = ("AGE", "OCCUPATION")
IDENTIFIER_CLASSES = DIRECT_IDENTIFIER_CLASSES + QUASI_IDENTIFIER_CLASSES

DETECTOR_DETERMINISTIC = "deterministic"
DETECTOR_GEMMA = "gemma"


@dataclass(frozen=True, order=True)
class DetectedSpan:
    """One identifier surface located in laboratory-local text.

    The raw surface is never carried in this object beyond the offsets, and
    `to_wire` emits only the fields permitted by the `PrivacyReceipt` contract.
    """

    start: int
    end: int
    identifier_class: str
    detector: str = DETECTOR_DETERMINISTIC
    rule_id: str = "unspecified"
    priority: int = 0
    """Lower wins when two rules cover the same surface: a labelled cue is more
    specific than a bare dictionary match, and both outrank a model proposal."""

    def __post_init__(self) -> None:
        if self.identifier_class not in IDENTIFIER_CLASSES:
            raise ValueError(f"unregistered identifier class: {self.identifier_class}")
        if self.start < 0 or self.end <= self.start:
            raise ValueError(f"invalid span offsets: {self.start}, {self.end}")

    @property
    def length(self) -> int:
        return self.end - self.start

    def overlaps(self, other: "DetectedSpan") -> bool:
        return self.start < other.end and other.start < self.end

    def surface(self, text: str) -> str:
        return text[self.start : self.end]

    def to_wire(self, text: str, span_key: bytes) -> dict[str, Any]:
        """Contract shape: only `span_hash`, `identifier_class`, `start`, `end`."""

        return {
            "span_hash": span_hash(text[self.start : self.end], self.identifier_class, span_key),
            "identifier_class": self.identifier_class,
            "start": self.start,
            "end": self.end,
        }


def span_hash(surface: str, identifier_class: str, span_key: bytes) -> str:
    """Keyed hash of an identifier surface.

    A plain digest of a short surface such as a telephone number is
    brute-forceable, so the laboratory-local key is required. The key never
    leaves the laboratory boundary, so a cloud reader cannot invert the value.
    """

    if not span_key:
        raise ValueError("span hashing requires a laboratory-local key")
    message = json.dumps([identifier_class, surface], ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hmac.new(span_key, message, hashlib.sha256).hexdigest()


def resolve_overlaps(spans: Iterable[DetectedSpan]) -> list[DetectedSpan]:
    """Deterministically drop overlapping spans, keeping the longest surface.

    Ties are resolved by earliest start, then deterministic detector before
    model proposal, then identifier class name. Determinism matters because the
    receipt and the redaction must be reproducible from the same input.
    """

    ordered = sorted(
        spans,
        key=lambda s: (
            -s.length,
            s.start,
            0 if s.detector == DETECTOR_DETERMINISTIC else 1,
            s.priority,
            s.identifier_class,
            s.rule_id,
        ),
    )
    kept: list[DetectedSpan] = []
    for candidate in ordered:
        if any(candidate.overlaps(existing) for existing in kept):
            continue
        kept.append(candidate)
    return sorted(kept, key=lambda s: (s.start, s.end, s.identifier_class))
