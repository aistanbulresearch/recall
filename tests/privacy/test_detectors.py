"""Deterministic detector behaviour, one check per identifier class."""

from __future__ import annotations

import pytest

from recall.privacy.detectors import DeterministicDetector, _national_id_tr_valid


@pytest.fixture(scope="module")
def detector() -> DeterministicDetector:
    return DeterministicDetector()


def surfaces(detector: DeterministicDetector, text: str, identifier_class: str) -> list[str]:
    return [text[span.start : span.end] for span in detector.detect(text) if span.identifier_class == identifier_class]


@pytest.mark.parametrize(
    ("text", "identifier_class", "expected"),
    [
        ("Hasta: Ayse Kaya, kontrol edildi.", "PERSON_NAME", "Ayse Kaya"),
        ("Patient: Sarah Barlow attended.", "PERSON_NAME", "Sarah Barlow"),
        ("Sorumlu hekim: Dr. Ahmet Demir.", "CLINICIAN_NAME", "Ahmet Demir"),
        ("Her mother Emily Barlow was followed.", "RELATIVE_NAME", "Emily Barlow"),
        ("TC Kimlik No: 10000000146 kaydedildi.", "NATIONAL_ID", "10000000146"),
        ("National identifier: 530-61-8093.", "NATIONAL_ID", "530-61-8093"),
        ("Dosya No: MRN-506622.", "MEDICAL_RECORD_NUMBER", "MRN-506622"),
        ("Protokol No: 2023-27206.", "PROTOCOL_NUMBER", "2023-27206"),
        ("Iletisim: 0533 278 29 86", "PHONE", "0533 278 29 86"),
        ("Contact: (844) 860-1423", "PHONE", "(844) 860-1423"),
        ("Adres: pelin.yilmaz@mailbox.example", "EMAIL", "pelin.yilmaz@mailbox.example"),
        ("Dogum tarihi: 03.07.1993 kayitli.", "DATE_OF_BIRTH", "03.07.1993"),
        ("Date of birth: March 8, 1959 recorded.", "DATE_OF_BIRTH", "March 8, 1959"),
        ("Istem tarihi: 2024-02-19", "EVENT_DATE", "2024-02-19"),
        ("Ornek alim tarihi: 13 Aralik 2023.", "EVENT_DATE", "13 Aralik 2023"),
        ("Kurum: Kuzey Universite Hastanesi.", "FACILITY_NAME", "Kuzey Universite Hastanesi"),
        ("Institution: Northgate University Hospital.", "FACILITY_NAME", "Northgate University Hospital"),
        ("Hasta 54 yasinda.", "AGE", "54"),
        ("The patient is age 54.", "AGE", "54"),
        ("Meslegi profesyonel dalgic olarak kayitli.", "OCCUPATION", "profesyonel dalgic"),
        ("Not: hasta Kadikoy bolgesinde ikamet etmektedir.", "ADDRESS", "Kadikoy"),
    ],
)
def test_class_is_detected(detector: DeterministicDetector, text: str, identifier_class: str, expected: str) -> None:
    assert expected in surfaces(detector, text, identifier_class)


def test_street_and_district_form_one_address_span(detector: DeterministicDetector) -> None:
    text = "Adres: Gul Sokak No 12, Kadikoy."
    assert "Gul Sokak No 12, Kadikoy" in surfaces(detector, text, "ADDRESS")


def test_national_id_checksum_rejects_invalid_number(detector: DeterministicDetector) -> None:
    assert _national_id_tr_valid("10000000146") is True
    assert _national_id_tr_valid("10000000147") is False
    assert surfaces(detector, "Kimlik: 10000000147 kaydedildi.", "NATIONAL_ID") == []


def test_detector_reports_the_classes_it_checks(detector: DeterministicDetector) -> None:
    checked = detector.identifier_classes_checked()
    for identifier_class in ("PERSON_NAME", "NATIONAL_ID", "PHONE", "EMAIL", "ADDRESS", "FACILITY_NAME", "AGE"):
        assert identifier_class in checked


def test_spans_never_overlap(detector: DeterministicDetector) -> None:
    text = "Hasta: Ayse Kaya, TC Kimlik No: 10000000146, Dr. Ahmet Demir tarafindan goruldu."
    spans = detector.detect(text)
    for left, right in zip(spans, spans[1:]):
        assert left.end <= right.start


def test_out_of_directory_name_is_not_detected(detector: DeterministicDetector) -> None:
    """A prose name outside the local dictionary is a residual, not a silent pass."""

    text = "Rapor kopyasi Zzyzx Qwertius ile paylasildi."
    assert surfaces(detector, text, "PERSON_NAME") == []
