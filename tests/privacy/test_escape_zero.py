"""Mandatory safety gate: no seeded direct identifier reaches an accepted payload.

The check runs over the development split. The frozen test split is reserved
for the preregistered P1 measurement and is deliberately not read here.
"""

from __future__ import annotations

import json

from conftest import note_from_record, residual_transport

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


def test_no_direct_identifier_escapes_without_the_local_model(gate_factory, dev_records) -> None:
    gate = gate_factory(None)
    accepted = 0
    for record in dev_records:
        result = gate.process(note_from_record(record))
        if result.decision != DECISION_ACCEPTED:
            continue
        accepted += 1
        assert escaped_surfaces(record, result.cloud_bound_payload) == []
    print(f"deterministic-only accepted payloads: {accepted}/{len(dev_records)}")


def test_no_direct_identifier_escapes_with_approved_residual_spans(gate_factory, dev_records) -> None:
    accepted = 0
    for record in dev_records:
        result = gate_factory(residual_transport(record)).process(note_from_record(record))
        if result.decision != DECISION_ACCEPTED:
            continue
        accepted += 1
        assert escaped_surfaces(record, result.cloud_bound_payload) == []
    assert accepted > 0, "the residual path must accept at least one payload"
    print(f"residual-assisted accepted payloads: {accepted}/{len(dev_records)}")


def test_a_hostile_model_cannot_widen_egress(gate_factory, dev_records) -> None:
    """A model that claims there is nothing to redact cannot release the note."""

    record = dev_records[0]
    result = gate_factory(lambda text, timeout: '{"spans": []}').process(note_from_record(record))
    if result.decision == DECISION_ACCEPTED:
        assert escaped_surfaces(record, result.cloud_bound_payload) == []
    else:
        assert result.cloud_bound_payload is None
