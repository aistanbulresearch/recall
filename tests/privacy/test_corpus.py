"""Synthetic corpus properties required before any measurement."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "corpus"))

import generator  # noqa: E402

MANIFEST_PATH = REPO_ROOT / "corpus" / "PRIVACY_CORPUS_MANIFEST.json"


@pytest.fixture(scope="module")
def manifest() -> dict:
    if not MANIFEST_PATH.exists():
        pytest.skip("corpus manifest is not generated")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_generation_is_deterministic_for_a_fixed_seed() -> None:
    gazetteers = json.loads(generator.GAZETTEER_PATH.read_text(encoding="utf-8"))
    first = generator.generate_records(20, generator.DEFAULT_SEED, gazetteers)
    second = generator.generate_records(20, generator.DEFAULT_SEED, gazetteers)
    assert first == second


def test_a_different_seed_changes_the_corpus() -> None:
    gazetteers = json.loads(generator.GAZETTEER_PATH.read_text(encoding="utf-8"))
    assert generator.generate_records(20, 1, gazetteers) != generator.generate_records(20, 2, gazetteers)


def test_spans_are_inside_the_text_and_never_overlap() -> None:
    gazetteers = json.loads(generator.GAZETTEER_PATH.read_text(encoding="utf-8"))
    for record in generator.generate_records(40, generator.DEFAULT_SEED, gazetteers):
        previous_end = 0
        for span in record["spans"]:
            assert 0 <= span["start"] < span["end"] <= len(record["text"])
            assert span["start"] >= previous_end
            previous_end = span["end"]
            assert record["text"][span["start"] : span["end"]].strip()


def test_every_identifier_class_is_represented() -> None:
    gazetteers = json.loads(generator.GAZETTEER_PATH.read_text(encoding="utf-8"))
    counts = generator.class_counts(generator.generate_records(60, generator.DEFAULT_SEED, gazetteers))
    for identifier_class in generator.IDENTIFIER_CLASSES:
        assert counts.get(identifier_class, 0) > 0, identifier_class


def test_both_languages_are_balanced() -> None:
    gazetteers = json.loads(generator.GAZETTEER_PATH.read_text(encoding="utf-8"))
    records = generator.generate_records(60, generator.DEFAULT_SEED, gazetteers)
    assert sum(1 for r in records if r["language"] == "tr") == 30
    assert sum(1 for r in records if r["language"] == "en") == 30


def test_national_identifier_is_shaped_but_fabricated() -> None:
    import random

    from recall.privacy.detectors import _national_id_tr_valid

    value = generator.tckn(random.Random("seed"))
    assert len(value) == 11 and value.isdigit()
    assert _national_id_tr_valid(value) is True


def test_splits_are_disjoint_and_recorded(manifest: dict) -> None:
    seen: set[str] = set()
    for split, entry in manifest["splits"].items():
        records = json.loads((REPO_ROOT / entry["file"]).read_text(encoding="utf-8"))
        assert len(records) == entry["record_count"]
        identifiers = {record["record_id"] for record in records}
        assert not identifiers & seen, f"{split} overlaps an earlier split"
        seen |= identifiers


def test_manifest_records_the_no_real_data_statement(manifest: dict) -> None:
    assert manifest["data_mode"] == "SYNTHETIC"
    assert "No real person" in manifest["real_data_statement"]
    assert manifest["seed"] == generator.DEFAULT_SEED


def test_manifest_hashes_match_the_generated_files(manifest: dict) -> None:
    for entry in manifest["splits"].values():
        data = (REPO_ROOT / entry["file"]).read_bytes()
        assert generator.sha256_hex(data) == entry["sha256"]


def test_test_split_is_large_enough_for_the_protocol(manifest: dict) -> None:
    assert manifest["splits"]["test"]["record_count"] >= 100
