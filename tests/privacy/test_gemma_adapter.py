"""Local model adapter: every failure mode must be typed and fail closed."""

from __future__ import annotations

import json

from recall.privacy.gemma import (
    MAX_PROPOSALS,
    STATUS_DISABLED,
    STATUS_INVALID_JSON,
    STATUS_OK,
    STATUS_TIMEOUT,
    STATUS_UNAVAILABLE,
    GemmaResidualDetector,
    TransportTimeout,
    TransportUnavailable,
    parse_span_response,
)

CLOCK = lambda: 0.0  # noqa: E731 - deterministic latency in tests


def detector(transport):
    return GemmaResidualDetector(transport, model_id="test-model", clock=CLOCK)


def test_valid_response_yields_proposals() -> None:
    payload = json.dumps(
        {"spans": [{"surface": "note", "start": 0, "end": 4, "identifier_class": "PERSON_NAME"}]}
    )
    outcome = detector(lambda text, timeout: payload).propose("Ayse")
    assert outcome.status == STATUS_OK
    assert outcome.schema_valid is True
    assert outcome.usable is True
    assert outcome.proposals[0].identifier_class == "PERSON_NAME"


def test_empty_span_list_is_valid_and_empty() -> None:
    outcome = detector(lambda text, timeout: '{"spans": []}').propose("note")
    assert outcome.usable is True
    assert outcome.proposals == ()


def test_invalid_json_is_not_a_clean_result() -> None:
    outcome = detector(lambda text, timeout: "I could not find any identifiers.").propose("note")
    assert outcome.status == STATUS_INVALID_JSON
    assert outcome.schema_valid is False
    assert outcome.usable is False


def test_timeout_is_typed() -> None:
    def transport(text, timeout):
        raise TransportTimeout("deadline exceeded")

    outcome = detector(transport).propose("note")
    assert outcome.status == STATUS_TIMEOUT
    assert outcome.invoked is True
    assert outcome.schema_valid is False
    assert "local_model_timeout" in outcome.reason_codes


def test_unavailable_model_is_typed() -> None:
    def transport(text, timeout):
        raise TransportUnavailable("connection refused")

    outcome = detector(transport).propose("note")
    assert outcome.status == STATUS_UNAVAILABLE
    assert outcome.usable is False


def test_unconfigured_model_is_disabled_not_clean() -> None:
    outcome = GemmaResidualDetector(None, clock=CLOCK).propose("note")
    assert outcome.status == STATUS_DISABLED
    assert outcome.invoked is False
    assert outcome.usable is False


def test_schema_rejects_unknown_and_wrong_typed_fields() -> None:
    assert parse_span_response(
        '{"spans":[{"surface":"a","start":1,"end":2,"identifier_class":"PERSON_NAME","note":"x"}]}'
    )[1] == (
        "model_response_unknown_field",
    )
    assert parse_span_response(
        '{"spans":[{"surface":"a","start":"1","end":2,"identifier_class":"PERSON_NAME"}]}'
    )[1] == (
        "model_response_type_error",
    )
    assert parse_span_response(
        '{"spans":[{"surface":"a","start":1,"end":2,"identifier_class":"NOT_A_CLASS"}]}'
    )[1] == (
        "model_response_unknown_identifier_class",
    )
    assert parse_span_response('{"spans": {}}')[1] == ("model_response_spans_not_array",)
    assert parse_span_response('{"spans": [], "confidence": 0.9}')[1] == ("model_response_unknown_field",)
    assert parse_span_response("")[1] == ("empty_model_response",)


def test_proposal_count_is_bounded() -> None:
    many = {
        "spans": [
            {"surface": "a", "start": i, "end": i + 1, "identifier_class": "PERSON_NAME"}
            for i in range(MAX_PROPOSALS + 1)
        ]
    }
    assert parse_span_response(json.dumps(many))[1] == ("model_response_too_many_spans",)


def test_json_embedded_in_prose_is_recovered() -> None:
    outcome = detector(lambda text, timeout: 'Result: {"spans": []} done').propose("note")
    assert outcome.usable is True


class _CapturingOpener:
    """Records the headers urllib would send, without any network."""

    def __init__(self) -> None:
        self.headers: list[dict[str, str]] = []


def test_auth_header_provider_is_called_per_request(monkeypatch) -> None:
    """A short-lived credential must be re-read on every call, not captured once.

    A Cloud Run ID token expires in about an hour; a run takes several. The
    transport therefore takes a provider and asks it per request, so token
    refresh is the provider's problem and never the transport's state.
    """

    import urllib.request

    from recall.privacy.gemma import OllamaChatTransport

    seen: list[str] = []
    tokens = iter(["token-1", "token-2"])

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"message": {"content": "{}"}}'

    def fake_urlopen(request, timeout):
        seen.append(request.get_header("Authorization"))
        return _Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    transport = OllamaChatTransport(
        base_url="https://gpu.internal.example",
        model_id="gemma-test",
        auth_header_provider=lambda: {"Authorization": f"Bearer {next(tokens)}"},
    )
    transport("note one", timeout_seconds=5.0)
    transport("note two", timeout_seconds=5.0)
    assert seen == ["Bearer token-1", "Bearer token-2"]


def test_request_settings_reports_auth_as_flag_never_value() -> None:
    """Credentials must not reach the evidence manifest."""

    from recall.privacy.gemma import OllamaChatTransport

    secret = "Bearer definitely-a-credential"
    transport = OllamaChatTransport(
        auth_header_provider=lambda: {"Authorization": secret}
    )
    settings = transport.request_settings()
    assert settings["authenticated"] is True
    assert secret not in repr(settings)
    plain = OllamaChatTransport()
    assert plain.request_settings()["authenticated"] is False
