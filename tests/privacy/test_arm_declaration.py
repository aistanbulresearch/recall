"""The arm declaration must follow its governing document, not restate it.

The frozen run manifest `p1-frozen-001` shipped a stale primacy claim because the
declaration lived in the harness as a literal written before
`corpus/PREREGISTRATION_AMENDMENT_001.md` promoted `surface_exact_search`. Nothing
forced the literal to follow the amendment, and nothing noticed when it did not.
See `corpus/ERRATUM_001_p1-frozen-001.md`.

These tests hold the replacement to its promise: the declaration is loaded from a
file, checked against the amendment before any manifest can be written, and the
run stops when the two disagree.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "privacy_eval.py"
DECLARATION_PATH = REPO_ROOT / "corpus" / "ARM_DECLARATION.json"
AMENDMENT_PATH = REPO_ROOT / "corpus" / "PREREGISTRATION_AMENDMENT_001.md"


def load_harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location("recall_privacy_eval_arms", SCRIPT_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - packaging accident
        raise RuntimeError(f"cannot load the P1 harness from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harness() -> ModuleType:
    return load_harness()


def write_declaration(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


# ------------------------------------------------------- the literal is gone


def test_the_harness_carries_no_free_standing_primacy_literal() -> None:
    """Rule 1: a declaration field is derived, never restated in code."""

    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "preregistered primary" not in source
    assert "declared secondary, exploratory" not in source


def test_the_declaration_file_is_the_single_source() -> None:
    declaration = json.loads(DECLARATION_PATH.read_text(encoding="utf-8"))
    assert declaration["governing_document"] == "corpus/PREREGISTRATION_AMENDMENT_001.md"
    assert {declaration["primary"]["arm"], declaration["secondary"]["arm"]} == {
        "surface_exact_search",
        "model_offsets",
    }


# --------------------------------------------- it agrees with the amendment


def test_the_amendment_is_read_from_the_governing_document(harness) -> None:
    assert harness.amendment_primacy() == {
        "surface_exact_search": "primary",
        "model_offsets": "secondary",
    }


def test_the_committed_declaration_matches_the_amendment(harness) -> None:
    declaration = harness.load_arm_declaration()
    assert declaration["primary"]["arm"] == "surface_exact_search"
    assert declaration["secondary"]["arm"] == "model_offsets"


def test_the_ambiguity_rule_travels_with_the_arm_it_describes(harness) -> None:
    """The surface placement rule belongs to the surface arm, wherever it ranks."""

    declaration = harness.load_arm_declaration()
    assert "model_response_surface_not_found" in declaration["primary"]["ambiguity_rule"]
    assert "ambiguity_rule" not in declaration["secondary"]


# ------------------------------------------------------- disagreement stops


def test_a_declaration_that_contradicts_the_amendment_stops_the_run(harness, tmp_path, monkeypatch) -> None:
    """The defect this fix exists to prevent, driven rather than asserted."""

    stale = json.loads(DECLARATION_PATH.read_text(encoding="utf-8"))
    stale["primary"], stale["secondary"] = stale["secondary"], stale["primary"]
    monkeypatch.setattr(harness, "ARM_DECLARATION_PATH", write_declaration(tmp_path / "d.json", stale))

    with pytest.raises(SystemExit) as error:
        harness.load_arm_declaration()
    message = str(error.value)
    assert message.startswith(harness.ARM_DECLARATION_MISMATCH)
    assert "model_offsets" in message


def test_an_unknown_arm_name_stops_the_run(harness, tmp_path, monkeypatch) -> None:
    payload = json.loads(DECLARATION_PATH.read_text(encoding="utf-8"))
    payload["primary"]["arm"] = "something_else"
    monkeypatch.setattr(harness, "ARM_DECLARATION_PATH", write_declaration(tmp_path / "d.json", payload))

    with pytest.raises(SystemExit) as error:
        harness.load_arm_declaration()
    assert "unknown_arm_names" in str(error.value)


def test_a_missing_declaration_stops_the_run(harness, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(harness, "ARM_DECLARATION_PATH", tmp_path / "absent.json")
    with pytest.raises(SystemExit) as error:
        harness.load_arm_declaration()
    assert "arm_declaration_missing" in str(error.value)


def test_an_unreadable_amendment_stops_the_run(harness, tmp_path, monkeypatch) -> None:
    """Silence in the governing document is not consent."""

    empty = tmp_path / "amendment.md"
    empty.write_text("# no arm table here\n", encoding="utf-8")
    monkeypatch.setattr(harness, "AMENDMENT_PATH", empty)

    with pytest.raises(SystemExit) as error:
        harness.load_arm_declaration()
    assert "amendment_unreadable" in str(error.value)
