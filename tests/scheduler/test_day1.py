from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
import scripts.run_day1_scheduler as day1_runner

from recall.contracts import ContractError
from recall.ledger import InMemoryLedger
from recall.privacy.signing import LocalSigner
from recall.privacy.signing import SigningKeyUnavailable, load_signer
from recall.scheduler.config import COHORT, TRIGGER_AT
from recall.scheduler.config import enforce_execution_window
from recall.scheduler.day1 import Day1Scheduler, receipt_verifier
from recall.scheduler.evidence import readback
from recall.scheduler.evidence import (
    redact_evidence,
    validate_first_evidence,
    validate_source_clean,
)


SOURCE_COMMIT = "a" * 40
SIGNER = LocalSigner("day1-test", b"day1-test-secret")


def test_day1_selects_one_due_case_and_second_trigger_is_idempotent() -> None:
    ledger = InMemoryLedger(
        privacy_receipt_verifier=receipt_verifier(SIGNER)
    )
    scheduler = Day1Scheduler(
        ledger, source_commit=SOURCE_COMMIT, signer=SIGNER
    )
    trigger = datetime.fromisoformat(TRIGGER_AT.replace("Z", "+00:00"))

    seeded = scheduler.seed(now=trigger)
    first = scheduler.trigger(now=trigger)
    counts_after_first = readback(ledger)["counts"]
    second = scheduler.trigger(now=trigger)
    counts_after_second = readback(ledger)["counts"]

    assert seeded == tuple(item.case_id for item in COHORT)
    assert first.selected_case_ids == (COHORT[0].case_id,)
    assert first.excluded_case_ids == (COHORT[1].case_id, COHORT[2].case_id)
    assert len(first.created_run_ids) == 1
    assert first.reused_run_ids == ()
    assert second.created_run_ids == ()
    assert second.reused_run_ids == first.created_run_ids
    assert counts_after_first == counts_after_second == {
        "artifacts": 7,
        "watch_cases": 3,
        "scan_runs": 1,
        "scan_run_events": 1,
        "review_tasks": 0,
    }


def test_day1_backend_is_explicitly_not_live_in_unit_test() -> None:
    ledger = InMemoryLedger(
        privacy_receipt_verifier=receipt_verifier(SIGNER)
    )

    assert ledger.backend_metadata() == {
        "persistence_surface": "IN_MEMORY_TEST",
        "project_sha256": "NOT_APPLICABLE",
        "database": "NOT_APPLICABLE",
    }


def test_untracked_source_blocks_execution_preflight() -> None:
    with pytest.raises(RuntimeError, match="source_critical_untracked_file"):
        validate_source_clean("", "src/recall/scheduler/injected.py")


def test_dirty_omitted_runtime_dependency_blocks_execution_preflight() -> None:
    with pytest.raises(RuntimeError, match="source_critical_tree_dirty"):
        validate_source_clean(" M src/recall/privacy/gate.py", "")


def test_same_count_different_hash_first_evidence_is_rejected() -> None:
    before = {"counts": {"scan_runs": 1}, "artifacts": {"a": {"hash": "1"}}}
    first = {
        "source_commit": SOURCE_COMMIT,
        "phase": "first",
        "readback": {
            "counts": {"scan_runs": 1},
            "artifacts": {"a": {"hash": "2"}},
        },
        "backend": {"persistence_surface": "LIVE_FIRESTORE"},
        "git_tree": "tree",
        "runtime_blobs": {},
    }
    with pytest.raises(RuntimeError, match="first_phase_evidence_mismatch"):
        validate_first_evidence(
            first,
            source_commit=SOURCE_COMMIT,
            before=before,
            backend={"persistence_surface": "LIVE_FIRESTORE"},
            provenance={"git_tree": "tree", "runtime_blobs": {}},
        )


def test_execution_window_rejects_before_trigger_and_after_deadline() -> None:
    trigger = datetime.fromisoformat(TRIGGER_AT.replace("Z", "+00:00"))
    enforce_execution_window(trigger)
    with pytest.raises(RuntimeError, match="outside_frozen_window"):
        enforce_execution_window(trigger.replace(minute=59) - timedelta(hours=1))
    with pytest.raises(RuntimeError, match="outside_frozen_window"):
        enforce_execution_window(trigger + timedelta(minutes=10))


def test_redaction_preserves_cryptographic_numeric_runs() -> None:
    sha = "abcd12345678901234ef" + "0" * 44
    redacted = redact_evidence(
        {"source_commit": sha[:40], "artifact_sha256": sha, "resource": "projects/secret"}
    )

    assert redacted["source_commit"] == sha[:40]
    assert redacted["artifact_sha256"] == sha
    assert redacted["resource"] == "projects/<project>"


def test_missing_local_signing_key_fails_loudly(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("RECALL_PRIVACY_SIGNING_KEY", raising=False)

    with pytest.raises(SigningKeyUnavailable):
        load_signer(tmp_path)


def test_wrong_signing_key_cannot_verify_day1_receipt() -> None:
    ledger = InMemoryLedger(
        privacy_receipt_verifier=receipt_verifier(
            LocalSigner("wrong", b"wrong-secret")
        )
    )
    scheduler = Day1Scheduler(
        ledger, source_commit=SOURCE_COMMIT, signer=SIGNER
    )
    trigger = datetime.fromisoformat(TRIGGER_AT.replace("Z", "+00:00"))

    with pytest.raises(ContractError, match="privacy_not_accepted"):
        scheduler.seed(now=trigger)

    assert ledger.read_back_count("watch_cases") == 0


def test_nonempty_namespace_failure_has_no_cleanup_ownership(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(day1_runner, "EVIDENCE_DIR", tmp_path / "evidence")

    def unexpected_ledger(_signer):
        raise AssertionError("cleanup must not inspect or delete an unowned namespace")

    monkeypatch.setattr(day1_runner, "_ledger", unexpected_ledger)
    day1_runner._cleanup_failed_attempt(
        "first", SOURCE_COMMIT, RuntimeError("day1_namespace_not_empty")
    )

    assert not (tmp_path / "evidence").exists()


def test_evidence_directory_collision_precedes_ledger_and_reservation(
    monkeypatch, tmp_path
) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    monkeypatch.setattr(day1_runner, "EVIDENCE_DIR", evidence_dir)
    monkeypatch.setattr(
        day1_runner, "enforce_execution_window", lambda _now: None
    )
    monkeypatch.setattr(day1_runner, "load_signer", lambda: SIGNER)
    monkeypatch.setattr(
        day1_runner,
        "git_provenance",
        lambda _source: {"git_tree": "tree", "runtime_blobs": {}},
    )

    def unexpected_ledger(_signer):
        raise AssertionError("collision must precede ledger creation")

    monkeypatch.setattr(day1_runner, "_ledger", unexpected_ledger)

    with pytest.raises(RuntimeError, match="evidence_directory_collision"):
        day1_runner.run("first", SOURCE_COMMIT)

    assert list(evidence_dir.iterdir()) == []


def test_second_phase_failure_preserves_first_phase_namespace(
    monkeypatch, tmp_path
) -> None:
    evidence_dir = tmp_path / "evidence"
    monkeypatch.setattr(day1_runner, "EVIDENCE_DIR", evidence_dir)
    marker = day1_runner._reserve_evidence("second", cleanup_owned=False)

    class FakeLedger:
        collection_names = ("artifacts",)
        cleanup_calls = 0

        def read_back_count(self, _name):
            return 7

        def cleanup_collections(self):
            self.cleanup_calls += 1

    ledger = FakeLedger()
    monkeypatch.setattr(day1_runner, "load_signer", lambda: SIGNER)
    monkeypatch.setattr(day1_runner, "_ledger", lambda _signer: ledger)

    day1_runner._cleanup_failed_attempt(
        "second", SOURCE_COMMIT, RuntimeError("second_phase_failure")
    )

    failure = json.loads(
        (evidence_dir / "failed-second.json").read_text(encoding="utf-8")
    )
    assert failure["status"] == "FAIL_PRESERVED"
    assert ledger.cleanup_calls == 0
    assert marker.exists()


def test_manifest_failure_retains_recovery_marker(
    monkeypatch, tmp_path
) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "first.json").write_text(
        '{"phase":"first"}\n', encoding="utf-8"
    )
    monkeypatch.setattr(day1_runner, "EVIDENCE_DIR", evidence_dir)
    marker = day1_runner._reserve_evidence("second", cleanup_owned=False)

    def fail_manifest(_path, _payload):
        raise OSError("injected_manifest_failure")

    monkeypatch.setattr(day1_runner, "write_json", fail_manifest)
    report = {"readback": {"counts": {"scan_runs": 1}}}
    first = {"readback": {"counts": {"scan_runs": 1}}}

    with pytest.raises(OSError, match="injected_manifest_failure"):
        day1_runner._finalize_phase(
            phase="second",
            marker=marker,
            report=report,
            phase_sha256="b" * 64,
            first_evidence=first,
        )

    assert marker.exists()
    assert not (evidence_dir / "manifest.json.sha256").exists()
