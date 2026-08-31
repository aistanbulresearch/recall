from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from recall.ledger import FirestoreLedger
from recall.privacy.signing import LocalSigner, load_signer
from recall.scheduler.config import (
    COLLECTION_PREFIX,
    DATABASE,
    EXPECTED_PROJECT_SHA256,
    TRIGGER_AT,
    TRIGGER_CODE,
    enforce_execution_window,
)
from recall.scheduler.day1 import Day1Scheduler, receipt_verifier
from recall.scheduler.evidence import (
    git_provenance,
    readback,
    validate_first_evidence,
    write_json,
)


EVIDENCE_DIR = Path("artifacts/evidence/day1-manual-20260825-a7f31c9d")


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _ledger(signer: LocalSigner) -> FirestoreLedger:
    return FirestoreLedger.from_default_credentials(
        collection_prefix=COLLECTION_PREFIX,
        privacy_receipt_verifier=receipt_verifier(signer),
        expected_project_sha256=EXPECTED_PROJECT_SHA256,
        database=DATABASE,
        require_live=True,
    )


def run(phase: str, source_commit: str) -> dict[str, object]:
    now = datetime.now(UTC)
    enforce_execution_window(now)
    signer = load_signer()
    provenance = git_provenance(source_commit)
    phase_path = EVIDENCE_DIR / f"{phase}.json"
    if phase_path.exists():
        raise RuntimeError("day1_evidence_collision")
    if phase == "first" and EVIDENCE_DIR.exists():
        raise RuntimeError("day1_evidence_directory_collision")
    if phase == "second" and not (EVIDENCE_DIR / "first.json").is_file():
        raise RuntimeError("day1_first_phase_evidence_missing")
    first_evidence = None
    if phase == "second":
        first_evidence = json.loads(
            (EVIDENCE_DIR / "first.json").read_text(encoding="utf-8")
        )
        if (
            first_evidence.get("source_commit") != source_commit
            or first_evidence.get("phase") != "first"
        ):
            raise RuntimeError("day1_first_phase_evidence_mismatch")

    ledger = _ledger(signer)
    if phase == "first" and any(
        ledger.read_back_count(name) for name in ledger.collection_names
    ):
        # No reservation exists, so failure handling cannot claim or delete a
        # namespace that this invocation did not prove was initially empty.
        raise RuntimeError("day1_namespace_not_empty")
    marker = _reserve_evidence(
        phase, cleanup_owned=(phase == "first")
    )
    scheduler = Day1Scheduler(
        ledger, source_commit=source_commit, signer=signer
    )
    before = readback(ledger) if phase == "second" else None
    if phase == "second":
        assert first_evidence is not None and before is not None
        validate_first_evidence(
            first_evidence,
            source_commit=source_commit,
            before=before,
            backend=ledger.backend_metadata(),
            provenance=provenance,
        )
    if phase == "first":
        seeded = scheduler.seed(now=_timestamp(TRIGGER_AT))
    else:
        seeded = ()
    result = scheduler.trigger(now=now)
    after = readback(ledger)

    expected_counts = {
        "artifacts": 7,
        "watch_cases": 3,
        "scan_runs": 1,
        "scan_run_events": 1,
        "review_tasks": 0,
    }
    checks = {
        "01_live_firestore": ledger.backend_metadata().get("persistence_surface")
        == "LIVE_FIRESTORE",
        "02_project_bound": ledger.backend_metadata().get("project_sha256")
        == EXPECTED_PROJECT_SHA256,
        "03_default_database": ledger.backend_metadata().get("database")
        == DATABASE,
        "04_three_watch_cases": after["counts"]["watch_cases"] == 3,
        "05_one_due_selected": len(result.selected_case_ids) == 1,
        "06_two_future_excluded": len(result.excluded_case_ids) == 2,
        "07_one_created_total": after["counts"]["scan_runs"] == 1,
        "08_run_created_event": after["counts"]["scan_run_events"] == 1,
        "09_no_review_task": after["counts"]["review_tasks"] == 0,
        "10_exact_counts": after["counts"] == expected_counts,
    }
    if phase == "first":
        checks["11_first_trigger_created_one"] = (
            len(seeded) == 3 and len(result.created_run_ids) == 1
        )
    else:
        checks["11_second_trigger_created_zero"] = (
            len(result.created_run_ids) == 0
            and len(result.reused_run_ids) == 1
            and before is not None
            and before == after
        )
    if not all(checks.values()):
        raise RuntimeError("day1_atomic_check_failed")

    report: dict[str, object] = {
        **provenance,
        "phase": phase,
        "trigger_code": TRIGGER_CODE,
        "repo_relative_command": (
            "python scripts/run_day1_scheduler.py --phase "
            f"{phase} --source-commit {source_commit}"
        ),
        "logical_trigger_at": TRIGGER_AT,
        "executed_at": now.isoformat().replace("+00:00", "Z"),
        "backend": ledger.backend_metadata(),
        "dependency_lock_sha256": provenance["runtime_blobs"]["uv.lock"][
            "committed_blob_sha256"
        ],
        "successful_process_exit_contract": 0,
        "seeded_case_ids": list(seeded),
        "trigger_result": {
            "selected_case_ids": list(result.selected_case_ids),
            "excluded_case_ids": list(result.excluded_case_ids),
            "created_run_ids": list(result.created_run_ids),
            "reused_run_ids": list(result.reused_run_ids),
        },
        "atomic_checks": checks,
        "readback": after,
        "inventory_reconciliation": {
            "cloud_resources_created": 0,
            "cloud_resources_deleted": 0,
            "cloud_resources_remaining": 0,
                "firestore_documents_created_or_retained": sum(
                    after["counts"].values()
                ),
            "firestore_documents_deleted": 0,
            "firestore_documents_remaining": after["counts"],
        },
        "claim_boundary": {
            "proved": "working cohort selection and durable day-1 scheduling record",
            "managed_recurring_schedule": "NOT_IMPLEMENTED_NOT_CLAIMED",
            "terminal_agent_execution": "NOT_RUN_NOT_CLAIMED",
            "privacy_signature_scope": "LOCAL_HMAC_TEST_RUN_NOT_CLOUD_VERIFICATION",
        },
    }
    sha256 = write_json(phase_path, report)
    _finalize_phase(
        phase=phase,
        marker=marker,
        report=report,
        phase_sha256=sha256,
        first_evidence=first_evidence,
    )
    return report


def _reserve_evidence(phase: str, *, cleanup_owned: bool) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    marker = EVIDENCE_DIR / f".{phase}.reserved"
    with marker.open("x", encoding="ascii") as handle:
        json.dump(
            {"phase": phase, "cleanup_owned": cleanup_owned},
            handle,
            sort_keys=True,
        )
        handle.write("\n")
    return marker


def _write_checksum_atomic(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        f"{value}  manifest.json\n", encoding="ascii", newline="\n"
    )
    temporary.replace(path)


def _finalize_phase(
    *,
    phase: str,
    marker: Path,
    report: dict[str, object],
    phase_sha256: str,
    first_evidence: dict[str, object] | None,
) -> None:
    if phase == "first":
        marker.unlink()
        return
    assert first_evidence is not None
    after = report["readback"]
    if first_evidence.get("readback", {}).get("counts") != after["counts"]:
        raise RuntimeError("day1_first_phase_evidence_mismatch")
    manifest = {
        **report,
        "evidence_files": {
            "first.json": hashlib.sha256(
                (EVIDENCE_DIR / "first.json").read_bytes()
            ).hexdigest(),
            "second.json": phase_sha256,
        },
    }
    manifest_sha = write_json(EVIDENCE_DIR / "manifest.json", manifest)
    _write_checksum_atomic(
        EVIDENCE_DIR / "manifest.json.sha256", manifest_sha
    )
    report["manifest_sha256"] = manifest_sha
    marker.unlink()


def _cleanup_failed_attempt(
    phase: str, source_commit: str, error: Exception
) -> None:
    marker = EVIDENCE_DIR / f".{phase}.reserved"
    if not marker.exists():
        return
    try:
        reservation = json.loads(marker.read_text(encoding="ascii"))
        signer = load_signer()
        ledger = _ledger(signer)
        before = {
            name: ledger.read_back_count(name) for name in ledger.collection_names
        }
        cleanup_owned = (
            phase == "first"
            and reservation.get("phase") == "first"
            and reservation.get("cleanup_owned") is True
        )
        if cleanup_owned:
            ledger.cleanup_collections()
        after = {
            name: ledger.read_back_count(name) for name in ledger.collection_names
        }
        write_json(
            EVIDENCE_DIR / f"failed-{phase}.json",
            {
                "status": (
                    "FAIL_CLEANED" if cleanup_owned else "FAIL_PRESERVED"
                ),
                "phase": phase,
                "source_commit": source_commit,
                "error_class": type(error).__name__,
                "error_code": str(error).split(":", 1)[0],
                "inventory_reconciliation": {
                    "before_cleanup": before,
                    "after_cleanup": after,
                },
            },
        )
        if cleanup_owned:
            marker.unlink()
    except Exception:
        # The reservation marker remains as a fail-closed recovery signal.
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("first", "second"))
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    try:
        result = run(args.phase, args.source_commit)
    except Exception as exc:
        _cleanup_failed_attempt(args.phase, args.source_commit, exc)
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_class": type(exc).__name__,
                    "error_code": str(exc).split(":", 1)[0],
                },
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": "PASS",
                "phase": args.phase,
                "source_commit": args.source_commit,
                "counts": result["readback"]["counts"],
                "atomic_checks": result["atomic_checks"],
                "manifest_sha256": result.get("manifest_sha256"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
