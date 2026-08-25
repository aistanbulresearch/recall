from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from recall.contracts import ContractError, content_hash, parse_artifact
from recall.ledger.memory import InMemoryLedger
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.scheduler.history import (
    DAY1_EVIDENCE_PATH,
    DAY1_EVIDENCE_BLOB_OID,
    DAY1_EVIDENCE_SHA256,
    HISTORY_RECEIPT_CREATED_AT,
    load_day1_history_receipt,
)
from recall.scheduler.preparation import (
    DEFAULT_BUNDLE_PATH,
    LockedPreparationVerifier,
    install_prepared_day,
    load_preparation_bundle,
)


ROOT = Path(__file__).resolve().parents[2]
BUNDLE_SHA = "c460340e75bf186980c8e7a938c5c5e0b4da89599890b2864af7dabdb4ffe841"


def _isolated_root(tmp_path: Path) -> Path:
    for relative in (DAY1_EVIDENCE_PATH, DEFAULT_BUNDLE_PATH):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    return tmp_path


def test_history_receipt_is_deterministic_and_derived_from_first_execution() -> None:
    first = load_day1_history_receipt(ROOT)
    second = load_day1_history_receipt(ROOT)
    assert first == second
    artifact = parse_artifact(first, authorized_producers=PRODUCER_REGISTRY)
    assert artifact.schema_name == "CohortHistoryReceipt"
    assert artifact.schema_version == "1.0.0"
    assert artifact.created_at == HISTORY_RECEIPT_CREATED_AT
    assert artifact.payload.evidence_sha256 == DAY1_EVIDENCE_SHA256
    assert artifact.payload.executed_at == "2026-08-25T15:00:03.280432Z"
    assert artifact.payload.created_run_ids == (
        "37ec818b-719b-5dc2-8995-e85f1b67cfdf",
    )
    assert artifact.payload.readback_counts["scan_runs"] == 1
    assert artifact.payload.readback_counts["scan_run_events"] == 1
    assert artifact.payload.direct_exit_code == 0


def test_packaged_history_bytes_match_the_committed_git_blob() -> None:
    relative = DAY1_EVIDENCE_PATH.as_posix()
    blob = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT)
    oid = subprocess.run(
        ["git", "rev-parse", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert oid == DAY1_EVIDENCE_BLOB_OID
    assert hashlib.sha256(blob).hexdigest() == DAY1_EVIDENCE_SHA256
    assert (ROOT / DAY1_EVIDENCE_PATH).read_bytes() == blob


def test_history_loader_rejects_missing_or_mutated_packaged_blob(tmp_path: Path) -> None:
    isolated = _isolated_root(tmp_path)
    (isolated / DAY1_EVIDENCE_PATH).unlink()
    with pytest.raises(RuntimeError, match="cohort_history_evidence_missing"):
        load_day1_history_receipt(isolated)
    isolated = _isolated_root(tmp_path)
    path = isolated / DAY1_EVIDENCE_PATH
    value = json.loads(path.read_text(encoding="utf-8"))
    value["executed_at"] = "2026-08-25T15:01:07.720049Z"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(RuntimeError, match="cohort_history_evidence_hash_mismatch"):
        load_day1_history_receipt(isolated)


def test_history_contract_rejects_semantic_contradiction() -> None:
    wire = copy.deepcopy(load_day1_history_receipt(ROOT))
    wire["runs_created"] = 0
    with pytest.raises(ContractError, match="contract_value_invalid:runs_created"):
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY, verify_hash=False)


def test_history_receipt_is_persisted_before_other_preparation_writes() -> None:
    bundle = load_preparation_bundle(ROOT, expected_sha256=BUNDLE_SHA)

    class DroppingLedger(InMemoryLedger):
        def append_artifact(self, value):
            if value["schema_name"] == "CohortHistoryReceipt":
                return parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
            return super().append_artifact(value)

    ledger = DroppingLedger(
        privacy_receipt_verifier=LockedPreparationVerifier(bundle)
    )
    with pytest.raises(RuntimeError, match="cohort_history_receipt_missing"):
        install_prepared_day(ledger, bundle, now=_day2_now())
    assert ledger.read_back_count("artifacts") == 0
    assert ledger.read_back_count("watch_cases") == 0


def test_duplicate_history_id_with_different_hash_fails_closed() -> None:
    receipt = load_day1_history_receipt(ROOT)
    ledger = InMemoryLedger()
    ledger.append_artifact(receipt)
    conflicting = copy.deepcopy(receipt)
    conflicting["created_at"] = "2026-08-25T15:00:04Z"
    conflicting["content_hash"] = content_hash(conflicting)
    with pytest.raises(ContractError, match="artifact_integrity_failed"):
        ledger.append_artifact(conflicting)
    assert ledger.read_back_count("artifacts") == 1


def _day2_now():
    from datetime import datetime, timezone

    return datetime(2026, 8, 26, 16, 1, tzinfo=timezone.utc)
