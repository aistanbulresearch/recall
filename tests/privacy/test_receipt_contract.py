"""`PrivacyReceipt` wire shape, signature, and non-leakage."""

from __future__ import annotations

import json
import re

import pytest
from conftest import note_from_record, residual_transport

from recall.contracts import parse_artifact
from recall.contracts.canonical import content_hash as artifact_content_hash
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.privacy.egress import EGRESS_SUMMARY_TEXT
from recall.privacy.receipt import (
    DECISION_ACCEPTED,
    DECISION_QUARANTINED,
    verify_privacy_receipt,
)
from recall.privacy.signing import LocalSigner, SigningKeyUnavailable, content_hash, load_signer

ENVELOPE_FIELDS = {
    "schema_name",
    "schema_version",
    "artifact_id",
    "case_id",
    "run_id",
    "producer",
    "created_at",
    "input_artifact_ids",
    "content_hash",
    "data_mode",
    "status",
    "warnings",
    "extensions",
}
PAYLOAD_FIELDS = {
    "decision",
    "detector_versions",
    "identifier_classes_checked",
    "detectors",
    "outbound",
    "payload_hash",
    "signature_ref",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


@pytest.fixture
def accepted_receipt(gate_factory, dev_records):
    record = dev_records[0]
    result = gate_factory(residual_transport(record)).process(note_from_record(record))
    assert result.decision == DECISION_ACCEPTED
    return record, result


def test_receipt_contains_exactly_the_contract_fields(accepted_receipt) -> None:
    _, result = accepted_receipt
    assert set(result.receipt) == ENVELOPE_FIELDS | PAYLOAD_FIELDS


def test_envelope_values_follow_the_contract(accepted_receipt) -> None:
    _, result = accepted_receipt
    receipt = result.receipt
    assert receipt["schema_name"] == "PrivacyReceipt"
    assert receipt["schema_version"] == "1.0.0"
    assert receipt["run_id"] is None
    assert receipt["input_artifact_ids"] == []
    assert receipt["extensions"] == {}
    assert receipt["data_mode"] == "SYNTHETIC"
    assert set(receipt["producer"]) == {"component", "version", "identity"}
    assert "@" not in receipt["producer"]["identity"]


def test_warnings_use_the_typed_shape(gate_factory, dev_records) -> None:
    result = gate_factory(None).process(note_from_record(dev_records[0]))
    assert result.receipt["warnings"], "a quarantined run must explain itself"
    for warning in result.receipt["warnings"]:
        assert set(warning) == {"code", "message_key", "related_artifact_ids"}


def test_span_entries_expose_only_keyed_hash_references(accepted_receipt) -> None:
    _, result = accepted_receipt
    detectors = result.receipt["detectors"]
    assert set(detectors) == {"deterministic", "gemma"}
    assert set(detectors["deterministic"]) == {"version", "approved_spans"}
    assert set(detectors["gemma"]) == {"version", "invoked", "schema_valid", "approved_residual_spans"}
    for group in ("deterministic", "gemma"):
        key = "approved_spans" if group == "deterministic" else "approved_residual_spans"
        for span_ref in detectors[group][key]:
            assert isinstance(span_ref, str)
            assert SHA256.fullmatch(span_ref)


def test_outbound_block_uses_the_contract_shape(accepted_receipt) -> None:
    _, result = accepted_receipt
    outbound = result.receipt["outbound"]
    assert set(outbound) == {"scan_status", "allowed_field_paths", "raw_text_field_count"}
    assert outbound["raw_text_field_count"] == 0


def test_content_hash_and_signature_verify(accepted_receipt, signer) -> None:
    _, result = accepted_receipt
    valid, reasons = verify_privacy_receipt(result.receipt, signer)
    assert valid, reasons


def test_real_receipt_round_trips_through_authoritative_parser(
    accepted_receipt,
) -> None:
    _, result = accepted_receipt

    parsed = parse_artifact(
        result.receipt,
        authorized_producers=PRODUCER_REGISTRY,
    )

    assert parsed.to_wire() == result.receipt


def test_real_quarantined_receipt_round_trips_through_authoritative_parser(
    gate_factory, dev_records
) -> None:
    result = gate_factory(None, egress_profile=EGRESS_SUMMARY_TEXT).process(
        note_from_record(dev_records[0])
    )
    assert result.decision == DECISION_QUARANTINED

    parsed = parse_artifact(
        result.receipt,
        authorized_producers=PRODUCER_REGISTRY,
    )

    assert parsed.to_wire() == result.receipt


def test_tampering_with_the_decision_breaks_verification(accepted_receipt, signer) -> None:
    _, result = accepted_receipt
    tampered = dict(result.receipt)
    tampered["decision"] = DECISION_ACCEPTED if tampered["decision"] != DECISION_ACCEPTED else DECISION_QUARANTINED
    valid, reasons = verify_privacy_receipt(tampered, signer)
    assert valid is False
    assert "content_hash_mismatch" in reasons


def test_algorithm_substitution_fails_after_public_hash_refresh(
    accepted_receipt, signer
) -> None:
    _, result = accepted_receipt
    tampered = dict(result.receipt)
    tampered["signature_ref"] = {
        **result.receipt["signature_ref"],
        "algorithm": "UNSUPPORTED",
    }
    tampered["content_hash"] = artifact_content_hash(tampered)

    valid, reasons = verify_privacy_receipt(tampered, signer)

    assert valid is False
    assert reasons == ("signature_algorithm_mismatch",)


def test_receipt_carries_no_identifier_surface(accepted_receipt) -> None:
    """No ground-truth surface may appear in any non-hash receipt value."""

    record, result = accepted_receipt
    text = record["text"]
    hash_keys = {"span_hash", "content_hash", "payload_hash", "signature"}

    def string_values(node, key=None):
        if isinstance(node, dict):
            for child_key, child in node.items():
                yield from string_values(child, child_key)
        elif isinstance(node, list):
            for child in node:
                yield from string_values(child, key)
        elif isinstance(node, str) and key not in hash_keys:
            yield node

    values = list(string_values(result.receipt))
    for span in record["spans"]:
        surface = text[span["start"] : span["end"]]
        if len(surface) < 4:
            continue
        assert not any(surface in value for value in values), surface


def test_redacted_text_never_enters_the_receipt(accepted_receipt) -> None:
    record, result = accepted_receipt
    blob = json.dumps(result.receipt, ensure_ascii=False)
    assert "[PERSON_NAME]" not in blob
    assert result.local_only.redacted_summary not in blob


def test_missing_signing_key_fails_loudly(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("RECALL_PRIVACY_SIGNING_KEY", raising=False)
    with pytest.raises(SigningKeyUnavailable):
        load_signer(tmp_path / "absent")


def test_signing_key_from_environment_is_used(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RECALL_PRIVACY_SIGNING_KEY", "unit-test-key")
    loaded = load_signer(tmp_path)
    assert loaded.verify("message", loaded.sign("message")) is True


def test_span_key_differs_from_signing_key() -> None:
    signer = LocalSigner("k", b"material")
    assert signer.span_key() != b"material"
    assert content_hash({"a": 1}) == content_hash({"a": 1})
