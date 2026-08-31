from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from recall.contracts import parse_artifact
from recall.contracts.canonical import canonical_json_bytes
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.platform.redaction import redact_json

from .config import COHORT


RUNTIME_ENTRY_PATHS = (
    "docs/evidence/predictions/2026-08-25--day1-manual-cohort.md",
    "scripts/run_day1_scheduler.py",
    "pyproject.toml",
    "uv.lock",
)


def git_provenance(source_commit: str) -> dict[str, object]:
    head = _git("rev-parse", "HEAD")
    if head != source_commit:
        raise RuntimeError("source_commit_not_head")
    runtime_paths = tuple(
        sorted(
            set(
                _git("ls-files", "src/recall").splitlines()
                + list(RUNTIME_ENTRY_PATHS)
            )
        )
    )
    dirty = _git(
        "status",
        "--porcelain",
        "--",
        "src/recall",
        "scripts/run_day1_scheduler.py",
        "docs/evidence/predictions/2026-08-25--day1-manual-cohort.md",
        "pyproject.toml",
        "uv.lock",
    )
    untracked = _git(
        "ls-files",
        "--others",
        "--exclude-standard",
        "--",
        "src",
        "scripts",
        "tests",
        "pyproject.toml",
        "uv.lock",
    )
    validate_source_clean(dirty, untracked)
    paths: dict[str, dict[str, str]] = {}
    for path in runtime_paths:
        blob = subprocess.run(
            ["git", "show", f"{source_commit}:{path}"],
            check=True,
            capture_output=True,
        ).stdout
        blob_oid = _git("rev-parse", f"{source_commit}:{path}")
        if _git("hash-object", path) != blob_oid:
            raise RuntimeError("committed_blob_mismatch")
        paths[path] = {
            "git_blob_oid": blob_oid,
            "committed_blob_sha256": hashlib.sha256(blob).hexdigest(),
        }
    return {
        "source_commit": source_commit,
        "git_tree": _git("rev-parse", f"{source_commit}^{{tree}}"),
        "runtime_blobs": paths,
    }


def validate_source_clean(dirty: str, untracked: str) -> None:
    if dirty:
        raise RuntimeError("source_critical_tree_dirty")
    if untracked:
        raise RuntimeError("source_critical_untracked_file")


def validate_first_evidence(
    value: Mapping[str, Any],
    *,
    source_commit: str,
    before: Mapping[str, Any],
    backend: Mapping[str, str],
    provenance: Mapping[str, object],
) -> None:
    if (
        value.get("source_commit") != source_commit
        or value.get("phase") != "first"
        or value.get("readback") != before
        or value.get("backend") != backend
        or value.get("git_tree") != provenance["git_tree"]
        or value.get("runtime_blobs") != provenance["runtime_blobs"]
    ):
        raise RuntimeError("day1_first_phase_evidence_mismatch")


def readback(ledger: LedgerPort) -> dict[str, object]:
    cases: dict[str, object] = {}
    artifacts: dict[str, object] = {}
    runs: dict[str, object] = {}
    events: dict[str, object] = {}
    for item in COHORT:
        record = ledger.get_watch_case(item.case_id)
        if record is None:
            raise RuntimeError("readback_watch_case_missing")
        case_wire = _jsonable(record.to_wire())
        cases[item.case_id] = {
            "pointer": case_wire,
            "canonical_sha256": _object_hash(case_wire),
            "expected_selected": item.expected_selected,
        }
        watch_artifact = ledger.get_artifact(record.artifact_id)
        if watch_artifact is None:
            raise RuntimeError("readback_watch_artifact_missing")
        parse_artifact(watch_artifact, authorized_producers=PRODUCER_REGISTRY)
        receipt_id = str(watch_artifact["input_artifact_ids"][0])
        receipt = ledger.get_artifact(receipt_id)
        if receipt is None:
            raise RuntimeError("readback_privacy_receipt_missing")
        for wire in (receipt, watch_artifact):
            parsed = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
            artifacts[parsed.artifact_id] = {
                "schema_name": parsed.schema_name,
                "content_hash": parsed.content_hash,
                "canonical_sha256": _object_hash(_jsonable(wire)),
                "wire": _jsonable(wire),
            }
    for item in COHORT:
        record = ledger.get_watch_case(item.case_id)
        assert record is not None
        for run_id in _expected_run_ids(item.case_id, record):
            run = ledger.get_scan_run(run_id)
            if run is None:
                continue
            run_wire = _jsonable(run.to_wire())
            runs[run_id] = {
                "pointer": run_wire,
                "canonical_sha256": _object_hash(run_wire),
            }
            scan_artifact = ledger.get_artifact(str(run.scan_run_artifact_id))
            if scan_artifact is None:
                raise RuntimeError("readback_scan_artifact_missing")
            parsed = parse_artifact(
                scan_artifact, authorized_producers=PRODUCER_REGISTRY
            )
            artifacts[parsed.artifact_id] = {
                "schema_name": parsed.schema_name,
                "content_hash": parsed.content_hash,
                "canonical_sha256": _object_hash(_jsonable(scan_artifact)),
                "wire": _jsonable(scan_artifact),
            }
            for event in ledger.list_scan_run_events(run_id):
                event_wire = _jsonable(event.to_wire())
                events[event.event_id] = {
                    "wire": event_wire,
                    "canonical_sha256": _object_hash(event_wire),
                }
    counts = {
        name: ledger.read_back_count(name)
        for name in (
            "artifacts",
            "watch_cases",
            "scan_runs",
            "scan_run_events",
            "review_tasks",
        )
    }
    return {
        "counts": counts,
        "watch_cases": cases,
        "artifacts": artifacts,
        "scan_runs": runs,
        "scan_run_events": events,
    }


def write_json(path: Path, value: Mapping[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = redact_evidence(_jsonable(value))
    payload = json.dumps(safe, indent=2, sort_keys=True) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8", newline="\n")
    temporary.replace(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def redact_evidence(value: Any, *, field: str = "") -> Any:
    cryptographic = (
        "sha256",
        "hash",
        "commit",
        "oid",
        "signature",
        "artifact_id",
        "run_id",
        "event_id",
        "case_id",
    )
    if any(marker in field.lower() for marker in cryptographic):
        return _jsonable(value)
    if isinstance(value, Mapping):
        return {
            str(key): redact_evidence(item, field=str(key))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_evidence(item, field=field) for item in value]
    return redact_json(value)


def _expected_run_ids(case_id: str, record) -> tuple[str, ...]:
    from recall.controller.hashes import scan_idempotency_key
    from uuid import NAMESPACE_URL, uuid5

    if record.next_scan_at is None:
        return ()
    key = scan_idempotency_key(
        watch_case_id=case_id,
        source_cursors=dict(record.source_cursors),
        schedule_epoch=record.next_scan_at,
        data_mode="SYNTHETIC",
    )
    return (str(uuid5(NAMESPACE_URL, f"recall:scan-run:{key}")),)


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _object_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
