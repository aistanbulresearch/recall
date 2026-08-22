"""Redaction determinism and the positive-allowlist outbound gate."""

from __future__ import annotations

from recall.privacy.outbound import SCAN_STATUS_BLOCKED, SCAN_STATUS_CLEAR, OutboundScanner
from recall.privacy.redactor import redact
from recall.privacy.spans import DetectedSpan

TEXT = "Hasta: Ayse Kaya, telefon 0533 278 29 86."


def test_redaction_replaces_every_span_with_a_class_placeholder() -> None:
    spans = [DetectedSpan(7, 16, "PERSON_NAME"), DetectedSpan(26, 40, "PHONE")]
    result = redact(TEXT, spans)
    assert result.text == "Hasta: [PERSON_NAME], telefon [PHONE]."
    assert result.replaced_span_count == 2


def test_redaction_is_deterministic_regardless_of_span_order() -> None:
    spans = [DetectedSpan(7, 16, "PERSON_NAME"), DetectedSpan(26, 40, "PHONE")]
    assert redact(TEXT, spans).text == redact(TEXT, list(reversed(spans))).text


def test_overlapping_spans_are_resolved_before_replacement() -> None:
    spans = [DetectedSpan(7, 16, "PERSON_NAME"), DetectedSpan(12, 16, "RELATIVE_NAME")]
    assert redact(TEXT, spans).text.count("[") == 1


def test_scanner_releases_only_recognised_tokens() -> None:
    scanner = OutboundScanner()
    assert scanner.token_allowed("[PERSON_NAME]") is True
    assert scanner.token_allowed("c.3113A>G") is True
    assert scanner.token_allowed("(p.Asn1038Ser)") is True
    assert scanner.token_allowed("GRCh38.") is True
    assert scanner.token_allowed("kanser") is True


def test_scanner_blocks_unknown_words_and_any_bare_number() -> None:
    scanner = OutboundScanner()
    assert scanner.token_allowed("Qwertius") is False
    assert scanner.token_allowed("08/11/25") is False
    assert scanner.token_allowed("MRN-506622") is False
    assert scanner.token_allowed("1974") is False


def test_payload_scan_reports_blocked_field_and_raw_text_count() -> None:
    scanner = OutboundScanner()
    payload = {"deidentified_summary": "Kontrol randevusu 08/11/25 tarihine verildi.", "region": "eu"}
    result = scanner.scan_payload(payload, ("$.deidentified_summary",))
    assert result.scan_status == SCAN_STATUS_BLOCKED
    assert result.raw_text_field_count == 1
    assert result.blocked_field_paths == ("$.deidentified_summary",)
    assert "outbound_unknown_token_present" in result.reason_codes


def test_clean_payload_scan_reports_zero_raw_text_fields() -> None:
    scanner = OutboundScanner()
    payload = {"deidentified_summary": "Kontrol randevusu [EVENT_DATE] tarihine verildi.", "region": "eu"}
    result = scanner.scan_payload(payload, ("$.deidentified_summary",))
    assert result.scan_status == SCAN_STATUS_CLEAR
    assert result.raw_text_field_count == 0
    assert "$.deidentified_summary" in result.allowed_field_paths
    assert "$.region" in result.allowed_field_paths


def test_missing_declared_text_field_blocks_rather_than_passes() -> None:
    result = OutboundScanner().scan_payload({"region": "eu"}, ("$.deidentified_summary",))
    assert result.scan_status == SCAN_STATUS_BLOCKED
    assert result.reason_codes == ("outbound_field_missing",)
