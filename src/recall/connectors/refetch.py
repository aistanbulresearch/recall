from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from recall.contracts import CitationVerdict, DataMode

from .live import LiveSourceRecord, SourceResponseInvalid, SourceUnavailable


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SourceMetadata(Protocol):
    identifier: str
    title: str
    locator: str
    content_hash: str
    mode: DataMode


@dataclass(frozen=True, slots=True)
class CitedSource:
    identifier: str
    title: str
    locator: str
    content_hash: str
    mode: DataMode

    def __post_init__(self) -> None:
        if self.mode not in {DataMode.CAPTURED_REPLAY, DataMode.LIVE_PUBLIC}:
            raise ValueError("cited_source_mode_invalid")
        _validate_metadata(self, "cited_source")


@dataclass(frozen=True, slots=True)
class RefetchedSource:
    identifier: str
    title: str
    locator: str
    content_hash: str
    mode: DataMode

    def __post_init__(self) -> None:
        if self.mode not in {DataMode.CAPTURED_REPLAY, DataMode.LIVE_PUBLIC}:
            raise ValueError("refetched_source_mode_invalid")
        _validate_metadata(self, "refetched_source")

    @classmethod
    def from_live(cls, source: LiveSourceRecord) -> RefetchedSource:
        return cls(
            identifier=source.identifier,
            title=source.title,
            locator=source.locator,
            content_hash=source.content_hash,
            mode=source.mode,
        )


@dataclass(frozen=True, slots=True)
class RefetchResult:
    verdict: CitationVerdict
    reason_codes: tuple[str, ...]
    refetched_source: SourceMetadata | None
    mode: DataMode

    def to_claim_verdict(self, claim_id: str) -> dict[str, object]:
        if not claim_id:
            raise ValueError("claim_id_required")
        return {
            "claim_id": claim_id,
            "verdict": self.verdict.value,
            "reason_codes": list(self.reason_codes),
            "refetched_source": (
                None
                if self.refetched_source is None
                else _source_wire(self.refetched_source)
            ),
        }

    def to_metadata_refetch(self) -> dict[str, str] | None:
        if self.refetched_source is None:
            return None
        return _source_wire(self.refetched_source)


def normalize_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", title).casefold()
    tokens = re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)
    return " ".join(tokens)


class RefetchAdapter:
    """Compute citation verdicts deterministically outside the model."""

    def compare(
        self, cited: CitedSource, refetched: SourceMetadata
    ) -> RefetchResult:
        if refetched.mode not in {DataMode.CAPTURED_REPLAY, DataMode.LIVE_PUBLIC}:
            raise ValueError("refetched_source_mode_invalid")
        _validate_metadata(refetched, "refetched_source")
        reasons: list[str] = []
        if cited.identifier != refetched.identifier:
            reasons.append("refetch_identifier_mismatch")
        if normalize_title(cited.title) != normalize_title(refetched.title):
            reasons.append("refetch_title_mismatch")
        if cited.content_hash != refetched.content_hash:
            reasons.append("refetch_content_hash_mismatch")
        if reasons:
            return RefetchResult(
                verdict=CitationVerdict.MISMATCH,
                reason_codes=tuple(reasons),
                refetched_source=refetched,
                mode=refetched.mode,
            )
        return RefetchResult(
            verdict=CitationVerdict.VERIFIED,
            reason_codes=("refetch_metadata_verified",),
            refetched_source=refetched,
            mode=refetched.mode,
        )

    def refetch(
        self,
        cited: CitedSource,
        fetcher: Callable[[str], LiveSourceRecord],
    ) -> RefetchResult:
        try:
            refetched = fetcher(cited.identifier)
        except (SourceResponseInvalid, SourceUnavailable):
            return RefetchResult(
                verdict=CitationVerdict.UNAVAILABLE,
                reason_codes=("refetch_source_unavailable",),
                refetched_source=None,
                mode=DataMode.LIVE_PUBLIC,
            )
        return self.compare(cited, refetched)


def _validate_metadata(source: SourceMetadata, field: str) -> None:
    if not source.identifier or not source.title or not source.locator:
        raise ValueError(f"{field}_field_required")
    if not _SHA256.fullmatch(source.content_hash):
        raise ValueError(f"{field}_hash_invalid")


def _source_wire(source: SourceMetadata) -> dict[str, str]:
    return {
        "identifier": source.identifier,
        "title": source.title,
        "locator": source.locator,
        "content_hash": source.content_hash,
    }
