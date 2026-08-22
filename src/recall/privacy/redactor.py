"""Deterministic redaction of approved identifier spans."""

from __future__ import annotations

from dataclasses import dataclass

from recall.privacy.spans import DetectedSpan, resolve_overlaps

REDACTOR_VERSION = "deterministic-redactor@1.0.0"


@dataclass(frozen=True)
class RedactionResult:
    text: str
    replaced_span_count: int
    placeholders: tuple[str, ...]


def placeholder_for(identifier_class: str) -> str:
    return f"[{identifier_class}]"


def redact(text: str, spans: tuple[DetectedSpan, ...] | list[DetectedSpan]) -> RedactionResult:
    """Replace every approved span with its class placeholder.

    Replacement runs from the end of the string so earlier offsets stay valid,
    and overlapping spans are resolved deterministically first.
    """

    ordered = resolve_overlaps(spans)
    redacted = text
    placeholders: list[str] = []
    for span in sorted(ordered, key=lambda item: item.start, reverse=True):
        marker = placeholder_for(span.identifier_class)
        placeholders.append(marker)
        redacted = redacted[: span.start] + marker + redacted[span.end :]
    return RedactionResult(
        text=redacted,
        replaced_span_count=len(ordered),
        placeholders=tuple(sorted(set(placeholders))),
    )
