from __future__ import annotations

import json
from hashlib import sha256

import pytest

from recall.privacy.minimizer import build_cloud_bound_payload
from recall.scheduler.privacy_note_source import (
    LockedJsonLabNoteSource,
    replay_variant_bindings,
)


CASE_A = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
CASE_B = "518a3c94-bbd1-4fb7-a3d4-3e0ed178429f"


def _row(
    case_id: str,
    *,
    vcv: str | None = None,
    hgvs_p: str | None = "p.Gly2508Arg",
) -> dict[str, object]:
    structured: dict[str, object] = {
        "inherit_case_binding": vcv is not None,
        "gene": "BRCA2",
        "hgvs_c": "c.7522G>C",
        "hgvs_p": hgvs_p,
        "assembly": "GRCh38",
    }
    if vcv is not None:
        structured["vcv"] = vcv
    return {
        "case_id": case_id,
        "language": "en",
        "note_text": f"Synthetic note for {case_id}.",
        "origin": "test",
        "spans": [],
        "structured": structured,
        "template": "test-v1",
    }


def _write_source(tmp_path, rows: list[dict[str, object]]):
    path = tmp_path / "notes.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.1.0",
                "notes_version": "test-notes-v1",
                "seed": 20260827,
                "data_mode": "SYNTHETIC",
                "tenant_id": "synthetic-contest-lab",
                "region": "us-central1",
                "real_data_statement": "All rows are fabricated.",
                "notes": rows,
            }
        ),
        encoding="utf-8",
    )
    return path


def _source(path) -> LockedJsonLabNoteSource:
    return LockedJsonLabNoteSource(
        path, expected_sha256=sha256(path.read_bytes()).hexdigest()
    )


def test_locked_notes_build_case_specific_cloud_payloads(tmp_path) -> None:
    first = _row(CASE_A)
    second = _row(CASE_B)
    second["structured"] = {
        "inherit_case_binding": False,
        "gene": "PALB2",
        "hgvs_c": "c.3113A>G",
        "hgvs_p": "p.Asn1038Ser",
        "assembly": "GRCh38",
    }
    path = _write_source(tmp_path, [first, second])
    source = _source(path)

    source.assert_exact_case_bindings({CASE_A: None, CASE_B: None})
    cloud_a = build_cloud_bound_payload(source.note_for(CASE_A), CASE_A)
    cloud_b = build_cloud_bound_payload(source.note_for(CASE_B), CASE_B)

    assert cloud_a["variant"] != cloud_b["variant"]
    assert source.source_lock == {
        "source_sha256": sha256(path.read_bytes()).hexdigest(),
        "schema_version": "1.1.0",
        "notes_version": "test-notes-v1",
    }


def test_locked_notes_require_exact_case_and_vcv_bindings(tmp_path) -> None:
    vcv = "VCV002895953.1"
    row = _row(CASE_A, vcv=vcv)
    path = _write_source(tmp_path, [row])
    source = _source(path)

    source.assert_exact_case_bindings({CASE_A: vcv})
    with pytest.raises(RuntimeError, match="lab_note_source_case_set_mismatch"):
        source.assert_exact_case_bindings({CASE_A: vcv, CASE_B: None})
    with pytest.raises(RuntimeError, match="lab_note_source_vcv_binding_mismatch"):
        source.assert_exact_case_bindings({CASE_A: "VCV000051100.33"})


def test_locked_notes_reject_unresolved_or_fabricated_vcv_variant(tmp_path) -> None:
    unresolved = _row(CASE_A, vcv="VCV002895953.1")
    unresolved["structured"] = {
        "inherit_case_binding": True,
        "vcv": "VCV002895953.1",
    }
    path = _write_source(tmp_path, [unresolved])
    with pytest.raises(RuntimeError, match="lab_note_source_variant_unresolved"):
        _source(path)

    resolved = _row(CASE_A, vcv="VCV002895953.1")
    path = _write_source(tmp_path, [resolved])
    source = _source(path)
    with pytest.raises(RuntimeError, match="lab_note_source_vcv_binding_mismatch"):
        source.assert_exact_case_bindings({CASE_A: None})

    fabricated = _row(CASE_A, vcv="VCV002895953.1")
    fabricated["structured"]["gene"] = "PALB2"
    path = _write_source(tmp_path, [fabricated])
    source = _source(path)
    with pytest.raises(
        RuntimeError, match="lab_note_source_variant_binding_mismatch"
    ):
        source.assert_exact_case_bindings({CASE_A: "VCV002895953.1"})


def test_locked_notes_support_source_absent_protein_consequence(tmp_path) -> None:
    path = _write_source(
        tmp_path,
        [_row(CASE_A, vcv="VCV000495460.24", hgvs_p=None)],
    )
    note = _source(path).note_for(CASE_A)

    cloud = build_cloud_bound_payload(note, CASE_A)

    assert cloud["payload_version"] == "1.1.0"
    assert cloud["variant"] == {
        "gene": "BRCA2",
        "hgvs_c": "c.7522G>C",
        "assembly": "GRCh38",
    }


def test_replay_variant_bindings_are_derived_for_all_registered_vcvs() -> None:
    bindings = replay_variant_bindings()

    assert set(bindings) == {
        "VCV002895953.1",
        "VCV002895953.4",
        "VCV002895953.5",
        "VCV000495460.24",
        "VCV000051100.33",
    }
    assert bindings["VCV000495460.24"] == {
        "gene": "BRCA2",
        "hgvs_c": "c.425+3A>G",
        "hgvs_p": None,
        "assembly": "GRCh38",
    }


def test_locked_notes_reject_wrong_hash_and_legacy_unresolved_shape(tmp_path) -> None:
    path = _write_source(tmp_path, [_row(CASE_A)])
    with pytest.raises(RuntimeError, match="lab_note_source_hash_mismatch"):
        LockedJsonLabNoteSource(path, expected_sha256="0" * 64)

    value = json.loads(path.read_text(encoding="utf-8"))
    value["schema_version"] = "1.0.0"
    value.pop("tenant_id")
    value.pop("region")
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(RuntimeError, match="lab_note_source_shape_invalid"):
        _source(path)
