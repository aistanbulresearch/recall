"""Local model adapter: every failure mode must be typed and fail closed."""

from __future__ import annotations

import json

from recall.privacy.gemma import (
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
    payload = json.dumps({"spans": [{"start": 0, "end": 4, "identifier_class": "PERSON_NAME"}]})
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
    assert parse_span_response('{"spans":[{"start":1,"end":2,"identifier_class":"PERSON_NAME","note":"x"}]}')[1] == (
        "model_response_unknown_field",
    )
    assert parse_span_response('{"spans":[{"start":"1","end":2,"identifier_class":"PERSON_NAME"}]}')[1] == (
        "model_response_type_error",
    )
    assert parse_span_response('{"spans":[{"start":1,"end":2,"identifier_class":"NOT_A_CLASS"}]}')[1] == (
        "model_response_unknown_identifier_class",
    )
    assert parse_span_response('{"spans": {}}')[1] == ("model_response_spans_not_array",)
    assert parse_span_response('{"spans": [], "confidence": 0.9}')[1] == ("model_response_unknown_field",)
    assert parse_span_response("")[1] == ("empty_model_response",)


def test_proposal_count_is_bounded() -> None:
    many = {"spans": [{"start": i, "end": i + 1, "identifier_class": "PERSON_NAME"} for i in range(20)]}
    assert parse_span_response(json.dumps(many))[1] == ("model_response_too_many_spans",)


def test_json_embedded_in_prose_is_recovered() -> None:
    outcome = detector(lambda text, timeout: 'Result: {"spans": []} done').propose("note")
    assert outcome.usable is True
