"""Deterministic identifier detectors for laboratory-local text.

These rules are the authoritative detection layer. They are frozen, inspectable,
and independent of any model. A local model may later propose additional spans,
but it can never remove or weaken what these rules find.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from recall.privacy.spans import DETECTOR_DETERMINISTIC, DetectedSpan, resolve_overlaps

DETECTOR_VERSION = "deterministic-detectors@1.0.0"
DEFAULT_DIRECTORY_PATH = Path(__file__).resolve().parent / "data" / "lab_directory.json"

UPPER = "A-ZÇĞİÖŞÜ"
LOWER = "a-zçğıöşü"
NAME_TOKEN = rf"[{UPPER}][{LOWER}]+"
NAME_PAIR = rf"{NAME_TOKEN}\s+{NAME_TOKEN}"

TR_MONTHS = "Ocak|Subat|Şubat|Mart|Nisan|Mayis|Mayıs|Haziran|Temmuz|Agustos|Ağustos|Eylul|Eylül|Ekim|Kasim|Kasım|Aralik|Aralık"
EN_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"

DATE_OF_BIRTH_CUES = ("dogum tarihi", "doğum tarihi", "date of birth", "dob")
DATE_CUE_WINDOW = 24


@dataclass(frozen=True)
class PatternRule:
    rule_id: str
    identifier_class: str
    pattern: re.Pattern[str]
    group: int = 0


def _national_id_tr_valid(value: str) -> bool:
    """Public checksum rule for an eleven-digit Turkish national identifier."""

    if len(value) != 11 or not value.isdigit() or value[0] == "0":
        return False
    digits = [int(character) for character in value]
    odd_sum = sum(digits[0:9:2])
    even_sum = sum(digits[1:8:2])
    if (odd_sum * 7 - even_sum) % 10 != digits[9]:
        return False
    return sum(digits[:10]) % 10 == digits[10]


PATTERN_RULES: tuple[PatternRule, ...] = (
    PatternRule("email", "EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    PatternRule("national-id-11-digit", "NATIONAL_ID", re.compile(r"\b[1-9][0-9]{10}\b")),
    PatternRule("national-id-grouped", "NATIONAL_ID", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    PatternRule("phone-tr", "PHONE", re.compile(r"(?:\+90[ ]?)?\b0?5\d{2}[ ]\d{3}[ ]\d{2}[ ]\d{2}\b")),
    PatternRule("phone-en", "PHONE", re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}")),
    PatternRule("medical-record-number", "MEDICAL_RECORD_NUMBER", re.compile(r"\bMRN-\d{6,8}\b")),
    PatternRule("protocol-number", "PROTOCOL_NUMBER", re.compile(r"\b(?:19|20)\d{2}-\d{5}\b")),
    PatternRule("date-dotted", "EVENT_DATE", re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")),
    PatternRule("date-iso", "EVENT_DATE", re.compile(r"\b\d{4}-\d{2}-\d{2}\b")),
    PatternRule("date-long-tr", "EVENT_DATE", re.compile(rf"\b\d{{1,2}} (?:{TR_MONTHS}) \d{{4}}\b")),
    PatternRule("date-long-en", "EVENT_DATE", re.compile(rf"\b(?:{EN_MONTHS}) \d{{1,2}}, \d{{4}}\b")),
    PatternRule("age-tr", "AGE", re.compile(r"\b(\d{1,3})(?= yasinda| yaşında)"), group=1),
    PatternRule("age-en", "AGE", re.compile(r"(?<=age )(\d{1,3})\b"), group=1),
)

NAME_CUE_RULES: tuple[PatternRule, ...] = (
    PatternRule("name-cue-patient", "PERSON_NAME", re.compile(rf"(?:Hasta|Ad Soyad|Patient|Full name)\s*:\s*({NAME_PAIR})"), group=1),
    PatternRule("name-cue-counsellee", "PERSON_NAME", re.compile(rf"(?:Danisan|Danışan|Counsellee)\s+({NAME_PAIR})"), group=1),
    PatternRule("name-cue-clinician", "CLINICIAN_NAME", re.compile(rf"Dr\.\s+({NAME_PAIR})"), group=1),
    PatternRule(
        "name-cue-relative",
        "RELATIVE_NAME",
        re.compile(rf"(?:Annesi|Babasi|Babası|Kardesi|Kardeşi|(?:Her|His|Their)\s+(?:mother|father|sister|brother))\s+({NAME_PAIR})"),
        group=1,
    ),
)


class LabDirectory:
    """Laboratory-local reference lists used by the gazetteer rules."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.version = str(payload.get("version", "unversioned"))
        self.first_names = self._collect(payload, "first_names")
        self.surnames = self._collect(payload, "surnames")
        self.districts = self._collect(payload, "districts")
        self.streets = self._collect(payload, "streets")
        self.facilities = self._collect(payload, "facilities")
        self.occupations = self._collect(payload, "occupations")

    @staticmethod
    def _collect(payload: dict[str, Any], field_name: str) -> tuple[str, ...]:
        values: list[str] = []
        for language in ("tr", "en"):
            values.extend(payload.get(language, {}).get(field_name, []))
        return tuple(sorted(set(values), key=lambda value: (-len(value), value)))

    @classmethod
    def load(cls, path: Path | None = None) -> "LabDirectory":
        source = path or DEFAULT_DIRECTORY_PATH
        return cls(json.loads(source.read_text(encoding="utf-8")))


class DeterministicDetector:
    """Frozen rule set that locates identifier surfaces in laboratory text."""

    version = DETECTOR_VERSION

    def __init__(self, directory: LabDirectory | None = None) -> None:
        self.directory = directory or LabDirectory.load()
        self._facility_pattern = self._alternation(self.directory.facilities)
        self._occupation_pattern = self._alternation(self.directory.occupations)
        self._district_pattern = self._alternation(self.directory.districts)
        self._street_pattern = self._alternation(self.directory.streets)
        self._name_dictionary = {value.lower() for value in self.directory.first_names}
        self._surname_dictionary = {value.lower() for value in self.directory.surnames}

    @staticmethod
    def _alternation(values: Iterable[str]) -> re.Pattern[str] | None:
        escaped = [re.escape(value) for value in values]
        if not escaped:
            return None
        return re.compile(rf"(?<![{LOWER}{UPPER}])(?:{'|'.join(escaped)})(?![{LOWER}{UPPER}])")

    def identifier_classes_checked(self) -> tuple[str, ...]:
        classes = {rule.identifier_class for rule in PATTERN_RULES}
        classes.update(rule.identifier_class for rule in NAME_CUE_RULES)
        classes.update({"FACILITY_NAME", "ADDRESS", "OCCUPATION", "PERSON_NAME", "DATE_OF_BIRTH"})
        return tuple(sorted(classes))

    def detect(self, text: str) -> list[DetectedSpan]:
        found: list[DetectedSpan] = []
        found.extend(self._pattern_spans(text))
        found.extend(self._name_cue_spans(text))
        found.extend(self._name_dictionary_spans(text))
        found.extend(self._gazetteer_spans(text))
        found.extend(self._address_spans(text))
        return resolve_overlaps(found)

    def _pattern_spans(self, text: str) -> list[DetectedSpan]:
        spans: list[DetectedSpan] = []
        for rule in PATTERN_RULES:
            for match in rule.pattern.finditer(text):
                start, end = match.span(rule.group)
                surface = text[start:end]
                if rule.rule_id == "national-id-11-digit" and not _national_id_tr_valid(surface):
                    continue
                identifier_class = rule.identifier_class
                if identifier_class == "EVENT_DATE" and self._has_birth_cue(text, start):
                    identifier_class = "DATE_OF_BIRTH"
                spans.append(DetectedSpan(start, end, identifier_class, DETECTOR_DETERMINISTIC, rule.rule_id))
        return spans

    @staticmethod
    def _has_birth_cue(text: str, start: int) -> bool:
        window = text[max(0, start - DATE_CUE_WINDOW) : start].lower()
        return any(cue in window for cue in DATE_OF_BIRTH_CUES)

    def _name_cue_spans(self, text: str) -> list[DetectedSpan]:
        spans: list[DetectedSpan] = []
        for rule in NAME_CUE_RULES:
            for match in rule.pattern.finditer(text):
                start, end = match.span(rule.group)
                spans.append(DetectedSpan(start, end, rule.identifier_class, DETECTOR_DETERMINISTIC, rule.rule_id))
        return spans

    def _name_dictionary_spans(self, text: str) -> list[DetectedSpan]:
        """Names without a field label are found only through the local dictionary."""

        spans: list[DetectedSpan] = []
        for match in re.finditer(rf"\b({NAME_TOKEN})\s+({NAME_TOKEN})\b", text):
            first, second = match.group(1).lower(), match.group(2).lower()
            if first in self._name_dictionary and second in self._surname_dictionary:
                spans.append(
                    DetectedSpan(
                        match.start(),
                        match.end(),
                        "PERSON_NAME",
                        DETECTOR_DETERMINISTIC,
                        "name-dictionary",
                        priority=1,
                    )
                )
        return spans

    def _gazetteer_spans(self, text: str) -> list[DetectedSpan]:
        spans: list[DetectedSpan] = []
        for pattern, identifier_class, rule_id in (
            (self._facility_pattern, "FACILITY_NAME", "facility-directory"),
            (self._occupation_pattern, "OCCUPATION", "occupation-directory"),
        ):
            if pattern is None:
                continue
            for match in pattern.finditer(text):
                spans.append(DetectedSpan(match.start(), match.end(), identifier_class, DETECTOR_DETERMINISTIC, rule_id))
        return spans

    def _address_spans(self, text: str) -> list[DetectedSpan]:
        spans: list[DetectedSpan] = []
        if self._district_pattern is None:
            return spans
        district_spans = list(self._district_pattern.finditer(text))
        street_spans = list(self._street_pattern.finditer(text)) if self._street_pattern else []

        for district in district_spans:
            start, end = district.span()
            for street in street_spans:
                if 0 <= start - street.end() <= 12:
                    prefix = text[street.start() - 6 : street.start()]
                    number_prefix = re.search(r"(\d{1,4})\s+$", prefix)
                    span_start = street.start() - len(number_prefix.group(1)) - 1 if number_prefix else street.start()
                    spans.append(
                        DetectedSpan(span_start, end, "ADDRESS", DETECTOR_DETERMINISTIC, "address-street-district")
                    )
                    break
            else:
                spans.append(DetectedSpan(start, end, "ADDRESS", DETECTOR_DETERMINISTIC, "address-district"))
        return spans
