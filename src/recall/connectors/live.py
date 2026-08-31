from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from recall.contracts import DataMode, canonical_json_bytes


_PUBMED_ID = re.compile(r"^[1-9][0-9]*$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_EUTILS_ROOT = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class SourceUnavailable(RuntimeError):
    """A public source could not be reached within its retry budget."""


class SourceResponseInvalid(RuntimeError):
    """A public source responded, but its payload could not be trusted."""


@dataclass(frozen=True, slots=True)
class LiveSourceRecord:
    identifier: str
    title: str
    locator: str
    content_hash: str
    mode: DataMode = DataMode.LIVE_PUBLIC

    def __post_init__(self) -> None:
        if self.mode is not DataMode.LIVE_PUBLIC:
            raise ValueError("refetched_source_mode_invalid")
        if not self.identifier or not self.title or not self.locator:
            raise ValueError("live_source_field_required")
        if not re.fullmatch(r"[0-9a-f]{64}", self.content_hash):
            raise ValueError("live_source_hash_invalid")

    def to_wire(self) -> dict[str, str]:
        return {
            "identifier": self.identifier,
            "title": self.title,
            "locator": self.locator,
            "content_hash": self.content_hash,
        }


def canonical_pubmed_metadata_hash(
    identifier: str, title: str, locator: str
) -> str:
    """Hash the same bounded PubMed metadata representation in replay and live."""

    from hashlib import sha256

    return sha256(
        canonical_json_bytes(
            {"identifier": identifier, "title": title, "locator": locator}
        )
    ).hexdigest()


def _stdlib_transport(url: str, timeout_seconds: float) -> bytes:
    request = Request(url, headers={"Accept": "application/json, application/xml"})
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return response.read()


class PubMedConnector:
    """Fixed-endpoint PubMed metadata connector for approved public evidence."""

    tool_id = "pubmed_live"
    capability = "evidence.pubmed.refetch"
    mode = DataMode.LIVE_PUBLIC
    retry_attempts = 3
    requests_per_second = 3

    def __init__(
        self,
        *,
        tool: str,
        email: str,
        transport: Callable[[str, float], bytes] = _stdlib_transport,
        timeout_seconds: float = 10.0,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        if not tool.strip():
            raise ValueError("ncbi_tool_required")
        if not _EMAIL.fullmatch(email):
            raise ValueError("ncbi_email_invalid")
        if timeout_seconds <= 0:
            raise ValueError("connector_timeout_invalid")
        self._tool = tool.strip()
        self._email = email
        self._transport = transport
        self._timeout_seconds = timeout_seconds
        self._clock = clock or time.monotonic
        self._sleep = sleeper or time.sleep
        self._last_request_at: float | None = None

    def registration(self) -> dict[str, object]:
        """Return a credential-free descriptor suitable for Registry binding."""
        return {
            "tool_id": self.tool_id,
            "capability": self.capability,
            "operation": "refetch_metadata",
            "data_mode": self.mode.value,
            "retry_attempts": self.retry_attempts,
            "fixed_host": "eutils.ncbi.nlm.nih.gov",
        }

    def refetch_metadata(self, identifier: str) -> dict[str, str]:
        """Expose a JSON-serializable, FunctionTool-compatible operation."""
        record = self.fetch(identifier)
        return {**record.to_wire(), "data_mode": record.mode.value}

    def fetch(self, identifier: str) -> LiveSourceRecord:
        if not _PUBMED_ID.fullmatch(identifier):
            raise ValueError("pubmed_identifier_invalid")
        summary_url = self._build_url(
            "esummary.fcgi", identifier=identifier, retmode="json"
        )
        summary_bytes = self._request(summary_url)
        returned_identifier, title = self._parse_summary(summary_bytes)
        locator = f"https://pubmed.ncbi.nlm.nih.gov/{returned_identifier}/"
        return LiveSourceRecord(
            identifier=returned_identifier,
            title=title,
            locator=locator,
            content_hash=canonical_pubmed_metadata_hash(
                returned_identifier, title, locator
            ),
        )

    def _build_url(self, endpoint: str, *, identifier: str, retmode: str) -> str:
        query = urlencode(
            {
                "db": "pubmed",
                "id": identifier,
                "retmode": retmode,
                "tool": self._tool,
                "email": self._email,
            }
        )
        return f"{_EUTILS_ROOT}/{endpoint}?{query}"

    def _request(self, url: str) -> bytes:
        last_error: Exception | None = None
        for _attempt in range(1, self.retry_attempts + 1):
            self._apply_rate_limit()
            try:
                body = self._transport(url, self._timeout_seconds)
                if not body:
                    raise OSError("empty response")
                return body
            except (OSError, TimeoutError) as exc:
                last_error = exc
        raise SourceUnavailable("pubmed_source_unavailable") from last_error

    def _apply_rate_limit(self) -> None:
        now = self._clock()
        if self._last_request_at is not None:
            minimum_interval = 1 / self.requests_per_second
            delay = minimum_interval - (now - self._last_request_at)
            if delay > 0:
                self._sleep(delay)
                now = self._clock()
        self._last_request_at = now

    @staticmethod
    def _parse_summary(raw: bytes) -> tuple[str, str]:
        try:
            document = json.loads(raw)
            result = document["result"]
            identifiers = result["uids"]
            identifier = identifiers[0]
            record = result[identifier]
            returned_identifier = record["uid"]
            title = record["title"].strip()
        except (
            AttributeError,
            IndexError,
            KeyError,
            TypeError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise SourceResponseInvalid("pubmed_summary_invalid") from exc
        if (
            not isinstance(returned_identifier, str)
            or not _PUBMED_ID.fullmatch(returned_identifier)
            or not title
        ):
            raise SourceResponseInvalid("pubmed_summary_invalid")
        return returned_identifier, title
