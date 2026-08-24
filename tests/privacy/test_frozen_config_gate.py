"""The frozen configuration gate, exercised rather than trusted.

The auditor approval is bound to the values in `corpus/FROZEN_CONFIG.json`. A run
that no longer matches them is not the run that was approved. These tests drive
the refusal, including through `main`, to show that a drifted configuration stops
the harness before it processes a single record rather than producing a manifest
that already looks authoritative.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "privacy_eval.py"
FROZEN_CONFIG_PATH = REPO_ROOT / "corpus" / "FROZEN_CONFIG.json"

BOUND_VALUES = (
    "prompt_sha256",
    "adapter_version",
    "locator_version",
    "max_proposals",
    "timeout_seconds",
    "concurrency",
    "transport",
    "model",
    "corpus_split_sha256",
)


def load_harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location("recall_privacy_eval_gate", SCRIPT_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - packaging accident
        raise RuntimeError(f"cannot load the P1 harness from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harness() -> ModuleType:
    return load_harness()


@pytest.fixture
def model_file(tmp_path) -> Path:
    path = tmp_path / "weights.gguf"
    path.write_bytes(b"stand-in for the served model file")
    return path


def args_for(model_file: Path) -> argparse.Namespace:
    return argparse.Namespace(
        gemma_url="http://127.0.0.1:11434",
        model_id="gemma4:e4b-it-qat",
        server_kind="ollama",
        num_ctx=2048,
        num_thread=14,
        num_predict=1024,
        keep_alive="30m",
        response_format="json",
        timeout_seconds=900.0,
        concurrency=3,
        reasoning_effort=None,
        model_repo="registry.ollama.ai/library/gemma4",
        model_revision="e4b-it-qat",
        model_quantization="q4_0",
        model_path=str(model_file),
    )


def frozen_file(tmp_path: Path, expected: dict) -> Path:
    path = tmp_path / "FROZEN_CONFIG.json"
    path.write_text(json.dumps({"expected": expected}), encoding="utf-8")
    return path


# ------------------------------------------------------------------ the file


def test_the_committed_frozen_configuration_declares_every_bound_value() -> None:
    payload = json.loads(FROZEN_CONFIG_PATH.read_text(encoding="utf-8"))
    expected = payload["expected"]
    for field in BOUND_VALUES:
        assert field in expected, field
    assert expected["transport"]["options"]["num_predict"] == 1024
    assert set(expected["corpus_split_sha256"]) == {"dev", "test", "train"}


# ------------------------------------------------------------------ the gate


def test_the_matching_configuration_passes_and_returns_the_file_hash(harness, tmp_path, model_file, monkeypatch) -> None:
    args = args_for(model_file)
    args.model_identity_record = harness.model_identity(args)
    path = frozen_file(tmp_path, harness.effective_config(args))
    monkeypatch.setattr(harness, "FROZEN_CONFIG_PATH", path)

    digest = harness.assert_frozen_config(args)
    assert digest == __import__("hashlib").sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("mutate", "field"),
    [
        (lambda c: c["transport"]["options"].__setitem__("num_predict", 512), "transport.options.num_predict"),
        (lambda c: c["transport"].__setitem__("format", None), "transport.format"),
        (lambda c: c.__setitem__("timeout_seconds", 300.0), "timeout_seconds"),
        (lambda c: c.__setitem__("prompt_sha256", "0" * 64), "prompt_sha256"),
        (lambda c: c.__setitem__("locator_version", "surface-exact-search-locator@9.9.9"), "locator_version"),
        (lambda c: c["model"].__setitem__("file_sha256", "0" * 64), "model.file_sha256"),
        (lambda c: c["corpus_split_sha256"].__setitem__("test", "0" * 64), "corpus_split_sha256.test"),
    ],
)
def test_any_drifted_field_refuses_the_run(harness, tmp_path, model_file, monkeypatch, mutate, field) -> None:
    args = args_for(model_file)
    args.model_identity_record = harness.model_identity(args)
    expected = harness.effective_config(args)
    mutate(expected)
    monkeypatch.setattr(harness, "FROZEN_CONFIG_PATH", frozen_file(tmp_path, expected))

    with pytest.raises(SystemExit) as error:
        harness.assert_frozen_config(args)
    message = str(error.value)
    assert message.startswith(f"{harness.FROZEN_CONFIG_MISMATCH}:{field}"), message


def test_a_missing_frozen_configuration_refuses_the_run(harness, tmp_path, model_file, monkeypatch) -> None:
    args = args_for(model_file)
    args.model_identity_record = harness.model_identity(args)
    monkeypatch.setattr(harness, "FROZEN_CONFIG_PATH", tmp_path / "absent.json")
    with pytest.raises(SystemExit) as error:
        harness.assert_frozen_config(args)
    assert "frozen_config_missing" in str(error.value)


def test_a_field_the_frozen_configuration_does_not_declare_refuses_the_run(harness, tmp_path, model_file, monkeypatch) -> None:
    """Silence is not approval: an undeclared field is refused, not ignored."""

    args = args_for(model_file)
    args.model_identity_record = harness.model_identity(args)
    expected = harness.effective_config(args)
    del expected["concurrency"]
    monkeypatch.setattr(harness, "FROZEN_CONFIG_PATH", frozen_file(tmp_path, expected))

    with pytest.raises(SystemExit) as error:
        harness.assert_frozen_config(args)
    assert "concurrency" in str(error.value)


# ------------------------------------------------------------------ through main


def test_a_drifted_run_stops_before_a_single_record_is_processed(harness, tmp_path, model_file, monkeypatch) -> None:
    """The refusal happens in `main`, before any evidence directory exists."""

    out_dir = tmp_path / "evidence"
    argv = [
        "privacy_eval.py",
        "--split", "dev",
        "--assert-frozen-config",
        "--gemma-url", "http://127.0.0.1:11434",
        "--model-id", "gemma4:e4b-it-qat",
        "--model-repo", "registry.ollama.ai/library/gemma4",
        "--model-revision", "e4b-it-qat",
        "--model-quantization", "q4_0",
        "--model-path", str(model_file),
        "--out", str(out_dir),
        "--run-id", "gate-test",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as error:
        harness.main()

    # The stand-in model file cannot match the approved file hash, so the gate fires.
    assert harness.FROZEN_CONFIG_MISMATCH in str(error.value)
    assert not out_dir.exists(), "the run created an evidence directory before failing the gate"
