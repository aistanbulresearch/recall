from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID

from recall.connectors.replay import ReplayConnector
from recall.privacy.minimizer import LabNote

from .cohort import REPLAY_ANCHORS, SOURCE_MANIFEST


_ROOT = Path(__file__).resolve().parents[3]
_SOURCE_FIELDS = {
    "schema_version",
    "notes_version",
    "seed",
    "data_mode",
    "tenant_id",
    "region",
    "real_data_statement",
    "notes",
}
_ROW_FIELDS = {
    "case_id",
    "language",
    "note_text",
    "origin",
    "spans",
    "structured",
    "template",
}
_VARIANT_FIELDS = {
    "inherit_case_binding",
    "gene",
    "hgvs_c",
    "hgvs_p",
    "assembly",
}


class LockedJsonLabNoteSource:
    """SHA-locked per-case laboratory notes with resolved variant bindings."""

    def __init__(
        self,
        path: Path,
        *,
        expected_sha256: str,
        repo_root: Path = _ROOT,
    ) -> None:
        try:
            raw = path.read_bytes()
            value = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("lab_note_source_unavailable") from exc
        actual_sha256 = sha256(raw).hexdigest()
        if not _sha256(expected_sha256) or actual_sha256 != expected_sha256:
            raise RuntimeError("lab_note_source_hash_mismatch")
        if (
            not isinstance(value, dict)
            or set(value) != _SOURCE_FIELDS
            or value["schema_version"] != "1.1.0"
            or value["data_mode"] != "SYNTHETIC"
            or not isinstance(value["notes"], list)
            or not isinstance(value["seed"], int)
        ):
            raise RuntimeError("lab_note_source_shape_invalid")
        self._tenant_id = _text(value["tenant_id"])
        self._region = _text(value["region"])
        self._notes_version = _text(value["notes_version"])
        _text(value["real_data_statement"])
        self._notes: dict[str, LabNote] = {}
        self._vcvs: dict[str, str | None] = {}
        self._variants: dict[str, Mapping[str, str | None]] = {}
        self._replay_variants = replay_variant_bindings(repo_root)
        for row in value["notes"]:
            case_id, note, vcv, variant = self._parse_row(row)
            if case_id in self._notes:
                raise RuntimeError("lab_note_source_duplicate_case")
            self._notes[case_id] = note
            self._vcvs[case_id] = vcv
            self._variants[case_id] = variant
        self._source_lock = {
            "source_sha256": actual_sha256,
            "schema_version": "1.1.0",
            "notes_version": self._notes_version,
        }

    @property
    def source_lock(self) -> Mapping[str, str]:
        return dict(self._source_lock)

    def note_for(self, case_id: str) -> LabNote:
        try:
            return self._notes[case_id]
        except KeyError as exc:
            raise RuntimeError(f"lab_note_source_missing:{case_id}") from exc

    def assert_exact_case_bindings(
        self, expected: Mapping[str, str | None]
    ) -> None:
        if set(self._notes) != set(expected):
            raise RuntimeError("lab_note_source_case_set_mismatch")
        if any(self._vcvs[case_id] != vcv for case_id, vcv in expected.items()):
            raise RuntimeError("lab_note_source_vcv_binding_mismatch")
        for case_id, vcv in expected.items():
            if (
                vcv is not None
                and self._variants[case_id] != self._replay_variants.get(vcv)
            ):
                raise RuntimeError("lab_note_source_variant_binding_mismatch")

    def _parse_row(
        self, row: Any
    ) -> tuple[str, LabNote, str | None, Mapping[str, str | None]]:
        if not isinstance(row, Mapping) or set(row) != _ROW_FIELDS:
            raise RuntimeError("lab_note_source_row_shape_invalid")
        case_id = _uuid(row["case_id"])
        if (
            row["language"] not in {"en", "tr"}
            or not isinstance(row["spans"], list)
        ):
            raise RuntimeError("lab_note_source_row_shape_invalid")
        _text(row["origin"])
        _text(row["template"])
        structured = row["structured"]
        if not isinstance(structured, Mapping):
            raise RuntimeError("lab_note_source_variant_unresolved")
        inherited = structured.get("inherit_case_binding")
        expected_fields = _VARIANT_FIELDS | ({"vcv"} if inherited is True else set())
        if (
            not isinstance(inherited, bool)
            or set(structured) != expected_fields
        ):
            raise RuntimeError("lab_note_source_variant_unresolved")
        vcv = None
        if inherited:
            vcv = _text(structured["vcv"])
            if not vcv.startswith("VCV"):
                raise RuntimeError("lab_note_source_vcv_binding_mismatch")
        hgvs_p = structured["hgvs_p"]
        if hgvs_p is not None:
            hgvs_p = _text(hgvs_p)
        variant = {
            "gene": _text(structured["gene"]),
            "hgvs_c": _text(structured["hgvs_c"]),
            "hgvs_p": hgvs_p,
            "assembly": _text(structured["assembly"]),
        }
        try:
            note = LabNote.parse(
                {
                    "case_key": case_id,
                    "note_text": _text(row["note_text"]),
                    "tenant_id": self._tenant_id,
                    "region": self._region,
                    "gene": variant["gene"],
                    "hgvs_c": variant["hgvs_c"],
                    "hgvs_p": hgvs_p,
                    "assembly": variant["assembly"],
                    "data_mode": "SYNTHETIC",
                }
            )
        except ValueError as exc:
            raise RuntimeError("lab_note_source_variant_invalid") from exc
        return case_id, note, vcv, variant


def replay_variant_bindings(
    repo_root: Path = _ROOT,
) -> Mapping[str, Mapping[str, str | None]]:
    """Derive the five VCV variants from the hash-verified replay manifest."""

    replay = ReplayConnector(repo_root, repo_root / SOURCE_MANIFEST)
    verified = {item["semantic_anchor"]: item for item in replay.verify_manifest()}
    values: dict[str, Mapping[str, str | None]] = {}
    for anchor in REPLAY_ANCHORS:
        source = verified[anchor.vcv]
        capture = (repo_root / str(source["capture_path"])).resolve()
        if (
            not capture.is_relative_to(repo_root.resolve())
            or b"GRCh38" not in capture.read_bytes()
        ):
            raise RuntimeError("lab_note_source_variant_assembly_unverified")
        projection = replay.source_projection(str(source["source_id"]))
        values[anchor.vcv] = {
            "gene": _text(projection["gene"]),
            "hgvs_c": _hgvs_suffix(projection["transcript_hgvs"], "c."),
            "hgvs_p": (
                None
                if "protein_hgvs" not in projection
                else _hgvs_suffix(projection["protein_hgvs"], "p.")
            ),
            "assembly": "GRCh38",
        }
    return values


def _hgvs_suffix(value: object, marker: str) -> str:
    text = _text(value)
    index = text.find(marker)
    if index < 0:
        raise RuntimeError("lab_note_source_variant_invalid")
    return text[index:]


def _uuid(value: object) -> str:
    try:
        return str(UUID(_text(value)))
    except ValueError as exc:
        raise RuntimeError("lab_note_source_case_id_invalid") from exc


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError("lab_note_source_shape_invalid")
    return value


def _sha256(value: str) -> bool:
    return len(value) == 64 and all(item in "0123456789abcdef" for item in value)
