"""Mandatory safety gate: no seeded direct identifier reaches an accepted payload.

The check runs over the development split. The frozen test split is reserved
for the preregistered P1 measurement and is deliberately not read here.

Both registered egress profiles are checked. They fail differently, and only one
of them is the demonstrated path:

* `STRUCTURED_ONLY` releases no free-text field, so a missed identifier has no
  field to travel in. Acceptance is structural and does not depend on the
  detectors or on the local model.
* `SUMMARY_TEXT` releases a redacted summary, so acceptance depends entirely on
  what the detectors found and on the outbound allowlist. On this corpus the
  deterministic-only version of that path accepts nothing at all, which is the
  measured reason the demonstrated path is structured-only.
"""

from __future__ import annotations

import json

import pytest
from conftest import note_from_record, residual_transport

from recall.privacy.egress import EGRESS_STRUCTURED_ONLY, EGRESS_SUMMARY_TEXT
from recall.privacy.receipt import DECISION_ACCEPTED

DIRECT_CLASSES = {
    "PERSON_NAME",
    "RELATIVE_NAME",
    "CLINICIAN_NAME",
    "NATIONAL_ID",
    "MEDICAL_RECORD_NUMBER",
    "PROTOCOL_NUMBER",
    "PHONE",
    "EMAIL",
    "ADDRESS",
    "FACILITY_NAME",
    "DATE_OF_BIRTH",
    "EVENT_DATE",
}


def escaped_surfaces(record: dict, payload: dict) -> list[str]:
    blob = json.dumps(payload, ensure_ascii=False)
    text = record["text"]
    escaped = []
    for span in record["spans"]:
        if span["identifier_class"] not in DIRECT_CLASSES:
            continue
        surface = text[span["start"] : span["end"]]
        if surface in blob:
            escaped.append(surface)
    return escaped


@pytest.mark.parametrize("profile", [EGRESS_STRUCTURED_ONLY, EGRESS_SUMMARY_TEXT])
def test_no_direct_identifier_escapes_without_the_local_model(gate_factory, dev_records, profile) -> None:
    gate = gate_factory(None, egress_profile=profile)
    accepted = 0
    for record in dev_records:
        result = gate.process(note_from_record(record))
        if result.decision != DECISION_ACCEPTED:
            continue
        accepted += 1
        assert escaped_surfaces(record, result.cloud_bound_payload) == []
    print(f"{profile} deterministic-only accepted payloads: {accepted}/{len(dev_records)}")


@pytest.mark.parametrize("profile", [EGRESS_STRUCTURED_ONLY, EGRESS_SUMMARY_TEXT])
def test_no_direct_identifier_escapes_with_approved_residual_spans(gate_factory, dev_records, profile) -> None:
    accepted = 0
    for record in dev_records:
        gate = gate_factory(residual_transport(record), egress_profile=profile)
        result = gate.process(note_from_record(record))
        if result.decision != DECISION_ACCEPTED:
            continue
        accepted += 1
        assert escaped_surfaces(record, result.cloud_bound_payload) == []
    assert accepted > 0, "the residual path must accept at least one payload"
    print(f"{profile} residual-assisted accepted payloads: {accepted}/{len(dev_records)}")


def test_structured_only_acceptance_does_not_depend_on_detection(gate_factory, dev_records) -> None:
    """Every well-formed record is released, and none of them carries prose."""

    gate = gate_factory(None)
    accepted = 0
    for record in dev_records:
        result = gate.process(note_from_record(record))
        assert result.decision == DECISION_ACCEPTED, record["record_id"]
        assert "deidentified_summary" not in result.cloud_bound_payload
        assert result.receipt["outbound"]["raw_text_field_count"] == 0
        accepted += 1
    assert accepted == len(dev_records)


def test_free_text_deterministic_path_releases_nothing_on_this_corpus(gate_factory, dev_records) -> None:
    """Records the measured finding that motivated structured-only egress.

    If this ever stops being zero the finding has changed, and the
    preregistration and the demo claim have to be revisited rather than
    quietly updated.
    """

    gate = gate_factory(None, egress_profile=EGRESS_SUMMARY_TEXT)
    accepted = [
        record["record_id"]
        for record in dev_records
        if gate.process(note_from_record(record)).decision == DECISION_ACCEPTED
    ]
    assert accepted == [], f"free-text deterministic path now accepts {len(accepted)} records"


def test_a_hostile_model_cannot_widen_egress(gate_factory, dev_records) -> None:
    """A model that claims there is nothing to redact cannot release the note."""

    record = dev_records[0]
    for profile in (EGRESS_STRUCTURED_ONLY, EGRESS_SUMMARY_TEXT):
        gate = gate_factory(lambda text, timeout: '{"spans": []}', egress_profile=profile)
        result = gate.process(note_from_record(record))
        if result.decision == DECISION_ACCEPTED:
            assert escaped_surfaces(record, result.cloud_bound_payload) == []
        else:
            assert result.cloud_bound_payload is None
