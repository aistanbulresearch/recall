"""Privacy Gate decisions: acceptance, quarantine, and model failure modes."""

from __future__ import annotations

import json

import pytest
from conftest import note_from_record, residual_transport

from recall.privacy.gemma import TransportTimeout, TransportUnavailable
from recall.privacy.minimizer import LabInputRejected, LabNote
from recall.privacy.receipt import DECISION_ACCEPTED, DECISION_QUARANTINED


def test_deterministic_only_path_quarantines_a_note_with_residuals(gate_factory, dev_records) -> None:
    record = dev_records[0]
    result = gate_factory(None).process(note_from_record(record))
    assert result.decision == DECISION_QUARANTINED
    assert result.cloud_bound_payload is None
    assert result.receipt["outbound"]["scan_status"] == "BLOCKED"
    assert result.receipt["outbound"]["raw_text_field_count"] >= 1


def test_approved_residual_spans_can_convert_quarantine_into_acceptance(gate_factory, dev_records) -> None:
    record = dev_records[0]
    result = gate_factory(residual_transport(record)).process(note_from_record(record))
    assert result.decision == DECISION_ACCEPTED
    assert result.cloud_bound_payload is not None
    assert result.receipt["detectors"]["gemma"]["invoked"] is True
    assert len(result.receipt["detectors"]["gemma"]["approved_residual_spans"]) >= 1


@pytest.mark.parametrize(
    ("transport", "expected_code"),
    [
        (lambda text, timeout: "no identifiers found", "model_response_not_json"),
        (lambda text, timeout: '{"spans": [], "confidence": 1.0}', "model_response_unknown_field"),
    ],
)
def test_invalid_model_output_quarantines_instead_of_passing(gate_factory, dev_records, transport, expected_code) -> None:
    result = gate_factory(transport).process(note_from_record(dev_records[0]))
    assert result.decision == DECISION_QUARANTINED
    assert result.receipt["detectors"]["gemma"]["schema_valid"] is False
    assert expected_code in {warning["code"] for warning in result.receipt["warnings"]}


def test_model_timeout_quarantines(gate_factory, dev_records) -> None:
    def transport(text, timeout):
        raise TransportTimeout("deadline")

    result = gate_factory(transport).process(note_from_record(dev_records[0]))
    assert result.decision == DECISION_QUARANTINED
    assert "local_model_timeout" in {warning["code"] for warning in result.receipt["warnings"]}


def test_unavailable_model_quarantines(gate_factory, dev_records) -> None:
    def transport(text, timeout):
        raise TransportUnavailable("connection refused")

    result = gate_factory(transport).process(note_from_record(dev_records[0]))
    assert result.decision == DECISION_QUARANTINED
    assert result.receipt["detectors"]["gemma"]["invoked"] is True


def test_accepted_payload_contains_no_raw_note_text(gate_factory, dev_records) -> None:
    record = dev_records[0]
    result = gate_factory(residual_transport(record)).process(note_from_record(record))
    payload = json.dumps(result.cloud_bound_payload, ensure_ascii=False)
    assert record["text"] not in payload
    assert result.cloud_bound_payload["deidentified_summary"] != record["text"]
    assert result.receipt["outbound"]["raw_text_field_count"] == 0


def test_case_token_is_stable_and_not_the_case_key(gate_factory, dev_records) -> None:
    record = dev_records[0]
    first = gate_factory(residual_transport(record)).process(note_from_record(record, "CASE-KEY-1"))
    second = gate_factory(residual_transport(record)).process(note_from_record(record, "CASE-KEY-1"))
    third = gate_factory(residual_transport(record)).process(note_from_record(record, "CASE-KEY-2"))
    assert first.receipt["case_id"] == second.receipt["case_id"]
    assert first.receipt["case_id"] != third.receipt["case_id"]
    assert "CASE-KEY-1" not in json.dumps(first.receipt)


def test_same_input_produces_the_same_receipt_body(gate_factory, dev_records) -> None:
    record = dev_records[1]
    first = gate_factory(residual_transport(record)).process(note_from_record(record))
    second = gate_factory(residual_transport(record)).process(note_from_record(record))
    assert first.receipt["content_hash"] == second.receipt["content_hash"]


def test_unknown_input_field_is_rejected() -> None:
    with pytest.raises(LabInputRejected):
        LabNote.parse(
            {
                "case_key": "c",
                "note_text": "t",
                "tenant_id": "l",
                "region": "eu",
                "gene": "BRCA1",
                "hgvs_c": "c.1A>T",
                "hgvs_p": "p.Met1Leu",
                "assembly": "GRCh38",
                "patient_name": "Ayse Kaya",
            }
        )


def test_missing_required_input_field_is_rejected() -> None:
    with pytest.raises(LabInputRejected):
        LabNote.parse({"case_key": "c", "note_text": "t"})


def test_unregistered_data_mode_is_rejected() -> None:
    with pytest.raises(LabInputRejected):
        LabNote.parse(
            {
                "case_key": "c",
                "note_text": "t",
                "tenant_id": "l",
                "region": "eu",
                "gene": "BRCA1",
                "hgvs_c": "c.1A>T",
                "hgvs_p": "p.Met1Leu",
                "assembly": "GRCh38",
                "data_mode": "PRODUCTION",
            }
        )
