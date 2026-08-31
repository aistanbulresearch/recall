"""Adversarial tests for the run script's publish/recovery/selection gates.

External-tour findings A and B, closed:

A — crash between wire.replace and manifest.replace used to read as a "stale
    marker" and got cleared, silently leaving a new wire beside an old
    manifest. Recovery is now phase-aware and hash-proven; the marker is never
    deleted without pair-proven consistency. The three crash boundaries
    (post-marker / post-wire-replace / post-manifest-replace) are injected
    here as directory states — exactly what a crash at each boundary leaves.

B — the checkpoint context hashed the FULL CORPUS, so a limit-20 checkpoint
    resumed into a limit-456 run without a mismatch and out-of-selection
    receipts published. The context now binds the post-limit selection (hash
    + count), entries are membership-checked against the selection, and a
    final publish gate requires published ids == selected ids.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "full_cohort_receipt_run.py"

spec = importlib.util.spec_from_file_location("full_cohort_receipt_run", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules["full_cohort_receipt_run"] = mod
spec.loader.exec_module(mod)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


WIRE = b'{"receipts": "wire-payload"}\n'
MANIFEST = b'{"manifest": "manifest-payload"}\n'


def _marker(out_dir: Path, **overrides: str) -> None:
    body = {
        "run_id": "test-run",
        "wire_staging": "privacy-receipts.abc.tmp",
        "wire_final": "privacy-receipts.json",
        "wire_sha256": _sha(WIRE),
        "manifest_staging": "RUN_MANIFEST.abc.tmp",
        "manifest_final": "RUN_MANIFEST.json",
        "manifest_sha256": _sha(MANIFEST),
    }
    body.update(overrides)
    (out_dir / "COMMIT_MARKER.json").write_text(json.dumps(body), encoding="utf-8")


# ---------------------------------------------------------------------------
# Finding A: the three crash boundaries, plus every unprovable state refusing.
# ---------------------------------------------------------------------------


class TestRecoveryBoundaries:
    def test_crash_after_marker_completes_both(self, tmp_path: Path) -> None:
        # Boundary 1: marker written, neither replace happened.
        (tmp_path / "privacy-receipts.abc.tmp").write_bytes(WIRE)
        (tmp_path / "RUN_MANIFEST.abc.tmp").write_bytes(MANIFEST)
        _marker(tmp_path)

        assert mod.recover_interrupted_publish(tmp_path) is None
        assert (tmp_path / "privacy-receipts.json").read_bytes() == WIRE
        assert (tmp_path / "RUN_MANIFEST.json").read_bytes() == MANIFEST
        assert not (tmp_path / "COMMIT_MARKER.json").exists()

    def test_crash_after_wire_replace_completes_manifest(self, tmp_path: Path) -> None:
        # Boundary 2: wire already final, manifest still staged. This is the
        # exact state finding A's old else-branch destroyed.
        (tmp_path / "privacy-receipts.json").write_bytes(WIRE)
        (tmp_path / "RUN_MANIFEST.abc.tmp").write_bytes(MANIFEST)
        _marker(tmp_path)

        assert mod.recover_interrupted_publish(tmp_path) is None
        assert (tmp_path / "RUN_MANIFEST.json").read_bytes() == MANIFEST
        assert not (tmp_path / "COMMIT_MARKER.json").exists()

    def test_crash_after_manifest_replace_clears_proven_marker(self, tmp_path: Path) -> None:
        # Boundary 3: both replaces done, crash before the marker unlink.
        (tmp_path / "privacy-receipts.json").write_bytes(WIRE)
        (tmp_path / "RUN_MANIFEST.json").write_bytes(MANIFEST)
        _marker(tmp_path)

        assert mod.recover_interrupted_publish(tmp_path) is None
        assert not (tmp_path / "COMMIT_MARKER.json").exists()
        assert (tmp_path / "privacy-receipts.json").read_bytes() == WIRE
        assert (tmp_path / "RUN_MANIFEST.json").read_bytes() == MANIFEST

    def test_phase_b_refuses_unproven_final_wire(self, tmp_path: Path) -> None:
        # Staged wire gone but the final wire is NOT the marker's wire (e.g. a
        # previous publish). Nothing proves the pair; the marker must survive.
        (tmp_path / "privacy-receipts.json").write_bytes(b"an older wire\n")
        old_manifest = b"an older manifest\n"
        (tmp_path / "RUN_MANIFEST.json").write_bytes(old_manifest)
        (tmp_path / "RUN_MANIFEST.abc.tmp").write_bytes(MANIFEST)
        _marker(tmp_path)

        error = mod.recover_interrupted_publish(tmp_path)
        assert error is not None and "cannot be proven paired" in error
        assert (tmp_path / "COMMIT_MARKER.json").exists()
        # The old manifest was not overwritten on unproven evidence.
        assert (tmp_path / "RUN_MANIFEST.json").read_bytes() == old_manifest

    def test_phase_c_refuses_unproven_pair(self, tmp_path: Path) -> None:
        # Staging gone and the finals do not both match: never clear.
        (tmp_path / "privacy-receipts.json").write_bytes(WIRE)
        (tmp_path / "RUN_MANIFEST.json").write_bytes(b"an older manifest\n")
        _marker(tmp_path)

        error = mod.recover_interrupted_publish(tmp_path)
        assert error is not None and "refusing to clear" in error
        assert (tmp_path / "COMMIT_MARKER.json").exists()

    def test_phase_c_refuses_missing_finals(self, tmp_path: Path) -> None:
        _marker(tmp_path)
        error = mod.recover_interrupted_publish(tmp_path)
        assert error is not None and "refusing to clear" in error
        assert (tmp_path / "COMMIT_MARKER.json").exists()

    def test_tampered_staged_wire_refuses(self, tmp_path: Path) -> None:
        (tmp_path / "privacy-receipts.abc.tmp").write_bytes(b"tampered\n")
        (tmp_path / "RUN_MANIFEST.abc.tmp").write_bytes(MANIFEST)
        _marker(tmp_path)

        error = mod.recover_interrupted_publish(tmp_path)
        assert error is not None and "staged wire" in error
        assert (tmp_path / "COMMIT_MARKER.json").exists()
        assert not (tmp_path / "privacy-receipts.json").exists()

    def test_impossible_staging_state_refuses(self, tmp_path: Path) -> None:
        # Staged wire present, staged manifest gone: no crash phase of the
        # publish sequence produces this.
        (tmp_path / "privacy-receipts.abc.tmp").write_bytes(WIRE)
        _marker(tmp_path)

        error = mod.recover_interrupted_publish(tmp_path)
        assert error is not None and "impossible" in error
        assert (tmp_path / "COMMIT_MARKER.json").exists()

    def test_marker_without_manifest_hash_refuses(self, tmp_path: Path) -> None:
        # A pre-fix marker (no manifest_sha256) cannot prove anything.
        (tmp_path / "privacy-receipts.abc.tmp").write_bytes(WIRE)
        (tmp_path / "RUN_MANIFEST.abc.tmp").write_bytes(MANIFEST)
        _marker(tmp_path)
        marker_path = tmp_path / "COMMIT_MARKER.json"
        body = json.loads(marker_path.read_text(encoding="utf-8"))
        del body["manifest_sha256"]
        marker_path.write_text(json.dumps(body), encoding="utf-8")

        error = mod.recover_interrupted_publish(tmp_path)
        assert error is not None and "unreadable" in error
        assert marker_path.exists()

    def test_no_marker_is_a_no_op(self, tmp_path: Path) -> None:
        assert mod.recover_interrupted_publish(tmp_path) is None


# ---------------------------------------------------------------------------
# Finding B: selection binding through main(), with the model leg faked so no
# network or paid call is involved.
# ---------------------------------------------------------------------------


def _notes(count: int) -> list[dict]:
    rows = []
    for index in range(count):
        rows.append(
            {
                "case_id": f"case-{index:04d}",
                "note_text": f"synthetic note {index}",
                "structured": {
                    "gene": "BRCA1",
                    "hgvs_c": "c.68_69del",
                    "hgvs_p": "p.Glu23fs",
                    "assembly": "GRCh38",
                },
            }
        )
    return rows


class _AcceptGate:
    """Stands in for PrivacyGate: accepts and emits a minimal receipt."""

    mangle_case_id = False

    def __init__(self, **_kwargs: object) -> None:
        pass

    def process(self, note: object) -> object:
        case_id = note.case_key  # type: ignore[attr-defined]
        if self.mangle_case_id:
            case_id = f"not-in-selection-{case_id}"
        receipt = {
            "case_id": case_id,
            "detectors": {"gemma": {"invoked": True, "schema_valid": True}},
        }
        return type("Result", (), {"accepted": True, "receipt": receipt})()


class _RefuseGate(_AcceptGate):
    def process(self, note: object) -> object:
        return type("Result", (), {"accepted": False, "receipt": None})()


@pytest.fixture()
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # OUT_DIR must sit under ROOT (the manifest records the wire path
    # relative to it) while key_dir must sit OUTSIDE it, so both are anchored
    # to a fake repo root; code provenance is faked since tmp is not a git
    # checkout.
    repo_root = tmp_path / "repo"
    out_dir = repo_root / "out"
    key_dir = tmp_path / "keys"
    monkeypatch.setattr(mod, "ROOT", repo_root)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "_load_notes", lambda: _notes(6))
    monkeypatch.setattr(
        mod,
        "_code_source",
        lambda: {"code_source_commit": "test", "code_source_dirty": False},
    )

    class _Tags:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"models": [{"name": mod.MODEL_ID}]}).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Tags())

    def run(*extra: str, gate: type, keep_lease: bool = False) -> tuple[int, str]:
        monkeypatch.setattr(mod, "PrivacyGate", gate)
        monkeypatch.setattr(
            sys,
            "argv",
            ["run", "--posture", "local", "--key-dir", str(key_dir), *extra],
        )
        # The lease holds this test process's own live PID after a failed run;
        # a real retry is a new process with a dead predecessor, so model that
        # — except in the lease tests themselves (keep_lease).
        if not keep_lease:
            (out_dir / "run.lease").unlink(missing_ok=True)
        stdout = io.StringIO()
        monkeypatch.setattr(sys, "stdout", stdout)
        try:
            code = mod.main()
        finally:
            monkeypatch.setattr(sys, "stdout", sys.__stdout__)
        return code, stdout.getvalue()

    return out_dir, run


class TestSelectionBinding:
    def test_resume_with_larger_limit_refuses(self, harness) -> None:
        out_dir, run = harness
        code, out = run("--limit", "2", gate=_RefuseGate)
        assert code == 1 and "RUN INCOMPLETE" in out

        code, out = run("--limit", "5", "--resume", gate=_AcceptGate)
        assert code == 1
        assert "checkpoint context mismatch" in out

    def test_resume_with_same_limit_passes_and_publishes(self, harness) -> None:
        out_dir, run = harness
        code, out = run("--limit", "2", gate=_RefuseGate)
        assert code == 1 and "RUN INCOMPLETE" in out

        code, out = run("--limit", "2", "--resume", gate=_AcceptGate)
        assert code == 0, out
        assert "resume: 0 receipted cases verified and skipped" in out
        wire = json.loads((out_dir / "privacy-receipts.json").read_text("utf-8"))
        assert [r["case_id"] for r in wire["receipts"]] == ["case-0000", "case-0001"]
        manifest = json.loads((out_dir / "RUN_MANIFEST.json").read_text("utf-8"))
        assert manifest["receipt_count"] == 2
        assert not (out_dir / "COMMIT_MARKER.json").exists()
        assert not (out_dir / "run.lease").exists()

    def test_out_of_selection_checkpoint_entry_refuses(self, harness) -> None:
        out_dir, run = harness
        code, out = run("--limit", "2", gate=_RefuseGate)
        assert code == 1

        # Defense in depth behind the context hash: an entry smuggled into a
        # context-matching checkpoint for a case outside the selection.
        with (out_dir / "checkpoint.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps({"case_id": "case-0005", "receipt": {"case_id": "case-0005"}})
                + "\n"
            )
        code, out = run("--limit", "2", "--resume", gate=_AcceptGate)
        assert code == 1
        assert "outside this invocation's selection" in out

    def test_publish_gate_refuses_receipts_off_selection(self, harness) -> None:
        out_dir, run = harness

        class _Mangled(_AcceptGate):
            mangle_case_id = True

        code, out = run("--limit", "2", gate=_Mangled)
        assert code == 1
        assert "publish gate: receipt set != declared selection" in out
        assert not (out_dir / "privacy-receipts.json").exists()


# ---------------------------------------------------------------------------
# N-series regression paths, re-fired against the finding-A/B state of the
# script (previously manual drills; durable here).
# ---------------------------------------------------------------------------


class TestNSeriesRegressions:
    def test_fresh_run_refuses_existing_key(self, harness, tmp_path: Path) -> None:
        key_dir = tmp_path / "keys"
        key_dir.mkdir(parents=True, exist_ok=True)
        (key_dir / "privacy-signing-key.json").write_text(
            json.dumps({"key_id": "old", "key": "aa"}), encoding="utf-8"
        )
        _out_dir, run = harness
        code, out = run("--limit", "1", gate=_AcceptGate)
        assert code == 1
        assert "key-dir already holds a key" in out

    def test_resume_refuses_missing_key(self, harness) -> None:
        _out_dir, run = harness
        code, out = run("--limit", "1", "--resume", gate=_AcceptGate)
        assert code == 1
        assert "no key file in key-dir" in out

    def test_live_lease_refuses(self, harness) -> None:
        import os

        out_dir, run = harness
        code, out = run("--limit", "1", gate=_RefuseGate)  # creates out_dir + key
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "run.lease").write_text(
            json.dumps({"pid": os.getpid(), "run_id": "held"}), encoding="utf-8"
        )
        code, out = run("--limit", "1", "--resume", gate=_AcceptGate, keep_lease=True)
        assert code == 1
        assert "another run holds the lease" in out

    def test_dead_lease_taken_over(self, harness) -> None:
        out_dir, run = harness
        code, out = run("--limit", "1", gate=_RefuseGate)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "run.lease").write_text(
            json.dumps({"pid": 999999999, "run_id": "dead"}), encoding="utf-8"
        )
        code, out = run("--limit", "1", "--resume", gate=_AcceptGate, keep_lease=True)
        assert code == 0, out

    def test_torn_tail_dropped_and_run_continues(self, harness) -> None:
        out_dir, run = harness
        code, out = run("--limit", "2", gate=_RefuseGate)
        with (out_dir / "checkpoint.jsonl").open("a", encoding="utf-8") as handle:
            handle.write('{"case_id": "case-0001", "rec')
        code, out = run("--limit", "2", "--resume", gate=_AcceptGate)
        assert code == 0, out
        assert "torn checkpoint tail dropped" in out

    def test_midfile_corruption_refuses(self, harness) -> None:
        out_dir, run = harness
        code, out = run("--limit", "2", gate=_RefuseGate)
        checkpoint = out_dir / "checkpoint.jsonl"
        lines = checkpoint.read_text(encoding="utf-8").splitlines()
        lines[1] = '{"case_id": "case-0000", "err'
        checkpoint.write_text("\n".join(lines) + "\n", encoding="utf-8")
        code, out = run("--limit", "2", "--resume", gate=_AcceptGate)
        assert code == 1
        assert "malformed mid-file" in out

    def test_tampered_checkpoint_receipt_refuses(self, harness) -> None:
        out_dir, run = harness
        code, out = run("--limit", "2", gate=_RefuseGate)
        # In-selection case, forged receipt: fails signature verification.
        forged = {
            "case_id": "case-0000",
            "receipt": {
                "case_id": "case-0000",
                "schema_version": "1.1.0",
                "decision": "ACCEPTED",
                "detectors": {"gemma": {"invoked": True, "schema_valid": True}},
                "signature": "forged",
            },
        }
        with (out_dir / "checkpoint.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(forged) + "\n")
        code, out = run("--limit", "2", "--resume", gate=_AcceptGate)
        assert code == 1
        assert "failed verification" in out

    def test_checkpoint_without_resume_refuses(self, harness) -> None:
        _out_dir, run = harness
        code, out = run("--limit", "2", gate=_RefuseGate)
        code, out = run("--limit", "2", gate=_AcceptGate)
        assert code == 1
        assert "pass --resume" in out
