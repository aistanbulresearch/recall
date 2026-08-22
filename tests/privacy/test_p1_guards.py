"""Protocol P1 stop points, exercised rather than trusted.

`corpus/PREREGISTRATION.md` conditions 4 and 5 are only worth writing down if
the harness refuses to run when they are not met. These tests drive the
refusals directly, including the second-frozen-run case, which cannot be
provoked by hand without leaving a real frozen manifest behind.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "privacy_eval.py"


def load_eval_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("recall_privacy_eval", SCRIPT_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - packaging accident
        raise RuntimeError(f"cannot load the P1 harness from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harness() -> ModuleType:
    return load_eval_module()


def namespace(**overrides) -> argparse.Namespace:
    defaults = {
        "gemma_url": None,
        "model_repo": None,
        "model_revision": None,
        "model_quantization": None,
        "model_path": None,
        "preregistration_approved": None,
        "frozen_test_run_id": None,
        "supersedes": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def write_frozen_report(root: Path, frozen_id: str) -> None:
    directory = root / frozen_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "p1-privacy-report.json").write_text(
        json.dumps({"split": "test", "run_id": frozen_id, "frozen_test_run_id": frozen_id}),
        encoding="utf-8",
    )


# --------------------------------------------------------------- condition 4


def test_a_model_backed_run_without_model_identity_is_refused(harness) -> None:
    args = namespace(gemma_url="http://127.0.0.1:8080")
    with pytest.raises(SystemExit) as error:
        harness.model_identity(args)
    message = str(error.value)
    assert "--model-repo" in message and "--model-path" in message


def test_a_model_file_that_is_not_there_cannot_be_identified(harness, tmp_path) -> None:
    args = namespace(
        gemma_url="http://127.0.0.1:8080",
        model_repo="example/repo",
        model_revision="main",
        model_quantization="q4_0",
        model_path=str(tmp_path / "absent.gguf"),
    )
    with pytest.raises(SystemExit):
        harness.model_identity(args)


def test_the_model_hash_is_computed_from_the_file_on_disk(harness, tmp_path) -> None:
    model_file = tmp_path / "gemma-4-E4B-it-q4_0.gguf"
    model_file.write_bytes(b"not a real model, but a real file")
    args = namespace(
        gemma_url="http://127.0.0.1:8080",
        model_repo="google/gemma-4-E4B-it-qat-q4_0-gguf",
        model_revision="main",
        model_quantization="q4_0",
        model_path=str(model_file),
    )
    identity = harness.model_identity(args)
    assert identity["file_sha256"] == hashlib.sha256(model_file.read_bytes()).hexdigest()
    assert identity["file_name"] == model_file.name
    assert identity["file_bytes"] == model_file.stat().st_size


def test_a_deterministic_run_records_no_model_identity(harness) -> None:
    assert harness.model_identity(namespace()) is None


def test_the_prompt_hash_follows_the_instruction_text(harness) -> None:
    first = harness.prompt_identity()
    assert first["prompt_sha256"] == harness.prompt_identity()["prompt_sha256"]
    expected = hashlib.sha256(
        (harness.GEMMA_ADAPTER_VERSION + "::" + harness.SYSTEM_INSTRUCTION).encode("utf-8")
    ).hexdigest()
    assert first["prompt_sha256"] == expected
    assert first["instruction_characters"] == len(harness.SYSTEM_INSTRUCTION)


# --------------------------------------------------------------- condition 5


def test_the_frozen_split_needs_a_recorded_approval(harness, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(harness, "EVIDENCE_ROOT", tmp_path)
    with pytest.raises(SystemExit) as error:
        harness.guard_frozen_split(namespace())
    assert "preregistration-approved" in str(error.value)


def test_the_frozen_split_needs_a_frozen_run_identifier(harness, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(harness, "EVIDENCE_ROOT", tmp_path)
    with pytest.raises(SystemExit) as error:
        harness.guard_frozen_split(namespace(preregistration_approved="AUD-2026-08-22"))
    assert "frozen-test-run-id" in str(error.value)


def test_the_first_frozen_run_is_allowed(harness, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(harness, "EVIDENCE_ROOT", tmp_path)
    harness.guard_frozen_split(
        namespace(preregistration_approved="AUD-2026-08-22", frozen_test_run_id="p1-frozen-001")
    )


def test_a_second_frozen_run_is_refused(harness, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(harness, "EVIDENCE_ROOT", tmp_path)
    write_frozen_report(tmp_path, "p1-frozen-001")
    with pytest.raises(SystemExit) as error:
        harness.guard_frozen_split(
            namespace(preregistration_approved="AUD-2026-08-22", frozen_test_run_id="p1-frozen-002")
        )
    message = str(error.value)
    assert "already been measured" in message and "p1-frozen-001" in message


def test_a_replacement_run_must_name_the_run_it_replaces(harness, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(harness, "EVIDENCE_ROOT", tmp_path)
    write_frozen_report(tmp_path, "p1-frozen-001")
    with pytest.raises(SystemExit) as error:
        harness.guard_frozen_split(
            namespace(
                preregistration_approved="AUD-2026-08-23",
                frozen_test_run_id="p1-frozen-002",
                supersedes="p1-frozen-999",
            )
        )
    assert "does not name a recorded frozen run" in str(error.value)


def test_a_replacement_run_may_not_reuse_the_superseded_identifier(harness, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(harness, "EVIDENCE_ROOT", tmp_path)
    write_frozen_report(tmp_path, "p1-frozen-001")
    with pytest.raises(SystemExit) as error:
        harness.guard_frozen_split(
            namespace(
                preregistration_approved="AUD-2026-08-23",
                frozen_test_run_id="p1-frozen-001",
                supersedes="p1-frozen-001",
            )
        )
    assert "already recorded" in str(error.value)


def test_an_approved_replacement_run_is_allowed(harness, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(harness, "EVIDENCE_ROOT", tmp_path)
    write_frozen_report(tmp_path, "p1-frozen-001")
    harness.guard_frozen_split(
        namespace(
            preregistration_approved="AUD-2026-08-23",
            frozen_test_run_id="p1-frozen-002",
            supersedes="p1-frozen-001",
        )
    )
