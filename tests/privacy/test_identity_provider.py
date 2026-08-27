"""The run-side identity provider: shape, error paths, and no token leakage."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import gcloud_identity_provider as provider  # noqa: E402


class _Completed:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_mints_bearer_header_from_gcloud(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _Completed(0, stdout="tok-abc\n")

    monkeypatch.setattr(provider, "_gcloud_executable", lambda: "gcloud")
    monkeypatch.setattr(subprocess, "run", fake_run)
    header = provider.identity_token_header()
    assert header == {"Authorization": "Bearer tok-abc"}
    assert calls == [["gcloud", "auth", "print-identity-token"]]


def test_every_call_mints_fresh(monkeypatch) -> None:
    tokens = iter(["one", "two"])
    monkeypatch.setattr(provider, "_gcloud_executable", lambda: "gcloud")
    monkeypatch.setattr(
        subprocess, "run", lambda cmd, **kw: _Completed(0, stdout=next(tokens))
    )
    assert provider.identity_token_header()["Authorization"] == "Bearer one"
    assert provider.identity_token_header()["Authorization"] == "Bearer two"


def test_failure_raises_with_stderr_and_no_token(monkeypatch) -> None:
    monkeypatch.setattr(provider, "_gcloud_executable", lambda: "gcloud")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kw: _Completed(1, stdout="secret-should-not-leak", stderr="Reauthentication required"),
    )
    with pytest.raises(RuntimeError) as excinfo:
        provider.identity_token_header()
    assert "Reauthentication required" in str(excinfo.value)
    assert "secret-should-not-leak" not in str(excinfo.value)


def test_empty_token_is_an_error_not_an_empty_header(monkeypatch) -> None:
    monkeypatch.setattr(provider, "_gcloud_executable", lambda: "gcloud")
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: _Completed(0, stdout="  \n"))
    with pytest.raises(RuntimeError, match="gcloud_identity_token_empty"):
        provider.identity_token_header()
