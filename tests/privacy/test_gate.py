"""Privacy Gate decisions: acceptance, quarantine, and model failure modes.

Two registered egress profiles are exercised separately. `STRUCTURED_ONLY` is
the default and the demonstrated path: it declares no free-text field, so the
decision cannot depend on a detector or a model having found every identifier.
`SUMMARY_TEXT` is the protocol P1 comparator that still releases a redacted
summary, and it is the only profile where a model failure can block egress.
"""

from __future__ import annotations

import json

import pytest
from conftest import note_from_record, residual_transport

from recall.privacy.egress import (
    EGRESS_STRUCTURED_ONLY,
    EGRESS_SUMMARY_TEXT,
    REASON_MODEL_FAILURE_BLOCKS_TEXT,
)
from recall.privacy.gemma import TransportTimeout, TransportUnavailable
from recall.privacy.minimizer import LabInputRejected, LabNote
from recall.privacy.receipt import DECISION_ACCEPTED, DECISION_QUARANTINED


def test_free_text_path_quarantines_a_note_with_residuals(gate_factory, dev_records) -> None:
    record = dev_records[0]
    result = gate_factory(None, egress_profile=EGRESS_SUMMARY_TEXT).process(note_from_record(record))
    assert result.decision == DECISION_QUARANTINED
    assert result.cloud_bound_payload is None
    assert result.receipt["outbound"]["scan_status"] == "BLOCKED"
    assert result.receipt["outbound"]["raw_text_field_count"] >= 1


def test_approved_residual_spans_can_convert_quarantine_into_acceptance(gate_factory, dev_records) -> None:
    record = dev_records[0]
    result = gate_factory(residual_transport(record), egress_profile=EGRESS_SUMMARY_TEXT).process(
        note_from_record(record)
    )
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
    result = gate_factory(transport, egress_profile=EGRESS_SUMMARY_TEXT).process(note_from_record(dev_records[0]))
    assert result.decision == DECISION_QUARANTINED
    assert result.receipt["detectors"]["gemma"]["schema_valid"] is False
    assert expected_code in {warning["code"] for warning in result.receipt["warnings"]}


def test_model_timeout_quarantines(gate_factory, dev_records) -> None:
    def transport(text, timeout):
        raise TransportTimeout("deadline")

    result = gate_factory(transport, egress_profile=EGRESS_SUMMARY_TEXT).process(note_from_record(dev_records[0]))
    assert result.decision == DECISION_QUARANTINED
    assert "local_model_timeout" in {warning["code"] for warning in result.receipt["warnings"]}




def test_accepted_free_text_payload_contains_no_raw_note_text(gate_factory, dev_records) -> None:
    record = dev_records[0]
    result = gate_factory(residual_transport(record), egress_profile=EGRESS_SUMMARY_TEXT).process(
        note_from_record(record)
    )
    payload = json.dumps(result.cloud_bound_payload, ensure_ascii=False)
    assert record["text"] not in payload
    assert result.cloud_bound_payload["deidentified_summary"] != record["text"]
    assert result.receipt["outbound"]["raw_text_field_count"] == 0


def test_structured_only_egress_accepts_without_any_free_text_field(gate_factory, dev_records) -> None:
    """The demonstrated path releases structured fields and no prose at all."""

    record = dev_records[0]
    result = gate_factory(None).process(note_from_record(record))
    assert result.decision == DECISION_ACCEPTED
    assert result.receipt["detector_versions"]["egress_profile"].startswith(EGRESS_STRUCTURED_ONLY)
    assert result.receipt["outbound"]["raw_text_field_count"] == 0
    assert "deidentified_summary" not in result.cloud_bound_payload
    assert set(result.cloud_bound_payload) == {
        "payload_kind",
        "payload_version",
        "case_token",
        "tenant_id",
        "region",
        "data_mode",
        "variant",
    }
    assert record["text"] not in json.dumps(result.cloud_bound_payload, ensure_ascii=False)


def test_structured_only_egress_does_not_depend_on_the_local_model(gate_factory, dev_records) -> None:
    """A broken model is recorded, but it cannot decide a prose-free payload."""

    def transport(text, timeout):
        raise TransportUnavailable("connection refused")

    result = gate_factory(transport).process(note_from_record(dev_records[0]))
    assert result.decision == DECISION_ACCEPTED
    assert result.receipt["detectors"]["gemma"]["invoked"] is True
    assert result.receipt["detectors"]["gemma"]["schema_valid"] is False
    codes = {warning["code"] for warning in result.receipt["warnings"]}
    assert "local_model_unavailable" in codes
    assert REASON_MODEL_FAILURE_BLOCKS_TEXT not in codes


def test_model_failure_blocks_the_free_text_profile_by_rule(gate_factory, dev_records) -> None:
    """On the prose path an unanswered residual question is never a clean result."""

    def transport(text, timeout):
        raise TransportUnavailable("connection refused")

    result = gate_factory(transport, egress_profile=EGRESS_SUMMARY_TEXT).process(note_from_record(dev_records[0]))
    assert result.decision == DECISION_QUARANTINED
    assert result.receipt["detectors"]["gemma"]["invoked"] is True
    assert REASON_MODEL_FAILURE_BLOCKS_TEXT in {warning["code"] for warning in result.receipt["warnings"]}


def test_structured_field_carrying_an_identifier_is_refused(gate_factory, dev_records) -> None:
    """A structured field is released on its registered shape, not on trust."""

    record = dev_records[0]
    note = note_from_record(record)
    poisoned = LabNote.parse(
        {
            "case_key": note.case_key,
            "note_text": note.note_text,
            "tenant_id": note.tenant_id,
            "region": note.region,
            "gene": "Ayse Kaya 0533 278 29 86",
            "hgvs_c": note.hgvs_c,
            "hgvs_p": note.hgvs_p,
            "assembly": note.assembly,
        }
    )
    result = gate_factory(None).process(poisoned)
    assert result.decision == DECISION_QUARANTINED
    assert result.cloud_bound_payload is None
    assert "$.variant.gene" in result.outbound.blocked_structured_field_paths
    assert "outbound_structured_value_rejected" in {warning["code"] for warning in result.receipt["warnings"]}


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
