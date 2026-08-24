from __future__ import annotations

import json
from collections.abc import Callable
from urllib.parse import parse_qs, urlparse

import pytest

from recall.connectors.live import (
    DataMode,
    PubMedConnector,
    SourceUnavailable,
)


class RecordingTransport:
    def __init__(self, responses: list[bytes | Exception]) -> None:
        self.responses = list(responses)
        self.urls: list[str] = []

    def __call__(self, url: str, timeout_seconds: float) -> bytes:
        assert timeout_seconds == 5.0
        self.urls.append(url)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _summary() -> bytes:
    return json.dumps(
        {
            "result": {
                "uids": ["12345678"],
                "12345678": {
                    "uid": "12345678",
                    "title": "BRCA2 variant evidence.",
                },
            }
        }
    ).encode()


def _connector(
    transport: Callable[[str, float], bytes],
    *,
    clock: Callable[[], float] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> PubMedConnector:
    return PubMedConnector(
        tool="recall-agent",
        email="research@example.org",
        transport=transport,
        timeout_seconds=5.0,
        clock=clock,
        sleeper=sleeper,
    )


def test_pubmed_builds_fixed_esummary_and_efetch_urls_with_ncbi_identity() -> None:
    transport = RecordingTransport([_summary(), b"<PubmedArticleSet />"])

    result = _connector(transport).fetch("12345678")

    assert result.identifier == "12345678"
    assert result.title == "BRCA2 variant evidence."
    assert result.mode is DataMode.LIVE_PUBLIC
    assert result.locator == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
    assert len(result.content_hash) == 64
    assert len(transport.urls) == 2
    for url, endpoint in zip(transport.urls, ("esummary.fcgi", "efetch.fcgi")):
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "eutils.ncbi.nlm.nih.gov"
        assert parsed.path.endswith(endpoint)
        query = parse_qs(parsed.query)
        assert query["db"] == ["pubmed"]
        assert query["id"] == ["12345678"]
        assert query["tool"] == ["recall-agent"]
        assert query["email"] == ["research@example.org"]
    assert parse_qs(urlparse(transport.urls[0]).query)["retmode"] == ["json"]
    assert parse_qs(urlparse(transport.urls[1]).query)["retmode"] == ["xml"]


def test_pubmed_registry_descriptor_and_tool_result_are_credential_free_json() -> None:
    transport = RecordingTransport([_summary(), b"<PubmedArticleSet />"])
    connector = _connector(transport)

    descriptor = connector.registration()
    tool_result = connector.refetch_metadata("12345678")

    assert descriptor == {
        "tool_id": "pubmed_live",
        "capability": "evidence.pubmed.refetch",
        "operation": "refetch_metadata",
        "data_mode": "LIVE_PUBLIC",
        "retry_attempts": 3,
        "fixed_host": "eutils.ncbi.nlm.nih.gov",
    }
    assert tool_result["data_mode"] == "LIVE_PUBLIC"
    serialized = json.dumps({"descriptor": descriptor, "result": tool_result})
    assert "research@example.org" not in serialized


def test_pubmed_rejects_non_numeric_identifier_before_transport() -> None:
    transport = RecordingTransport([])

    with pytest.raises(ValueError, match="pubmed_identifier_invalid"):
        _connector(transport).fetch("https://attacker.invalid/")

    assert transport.urls == []


def test_pubmed_retries_at_most_three_attempts_per_request() -> None:
    transport = RecordingTransport(
        [OSError("one"), TimeoutError("two"), _summary(), b"<ok />"]
    )

    result = _connector(transport).fetch("12345678")

    assert result.identifier == "12345678"
    assert len([url for url in transport.urls if "esummary" in url]) == 3


def test_pubmed_exhaustion_fails_loudly_after_three_attempts() -> None:
    transport = RecordingTransport(
        [OSError("one"), TimeoutError("two"), OSError("three")]
    )

    with pytest.raises(SourceUnavailable, match="pubmed_source_unavailable"):
        _connector(transport).fetch("12345678")

    assert len(transport.urls) == 3


def test_pubmed_enforces_ncbi_rate_limit_between_requests() -> None:
    now = [0.0]
    sleeps: list[float] = []

    def clock() -> float:
        return now[0]

    def sleep(delay: float) -> None:
        sleeps.append(delay)
        now[0] += delay

    transport = RecordingTransport([_summary(), b"<ok />"])

    _connector(transport, clock=clock, sleeper=sleep).fetch("12345678")

    assert sleeps == [pytest.approx(1 / 3)]


def test_pubmed_requires_nonempty_ncbi_tool_and_valid_email() -> None:
    transport = RecordingTransport([])

    with pytest.raises(ValueError, match="ncbi_tool_required"):
        PubMedConnector(tool=" ", email="research@example.org", transport=transport)
    with pytest.raises(ValueError, match="ncbi_email_invalid"):
        PubMedConnector(tool="recall-agent", email="invalid", transport=transport)


def test_pubmed_rejects_malformed_summary_as_schema_failure() -> None:
    transport = RecordingTransport([b'{"result": {}}', b"<ok />"])

    with pytest.raises(RuntimeError, match="pubmed_summary_invalid"):
        _connector(transport).fetch("12345678")
