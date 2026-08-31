from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from recall.contracts import ArtifactStatus, DataMode, build_artifact
from recall.ledger.producers import PRODUCER_REGISTRY

from .cohort import COHORT_ID


DAY1_EVIDENCE_PATH = Path(
    "artifacts/evidence/day1-manual-20260825-a7f31c9d/first.json"
)
DAY1_EVIDENCE_SHA256 = (
    "fa588a3eee9d8ac66c6629f8668a1e878cdda7586b256c99299eb0ce56283825"
)
DAY1_EVIDENCE_BLOB_OID = "7d82b5158865284c00d89a20445c24db4bca518a"
DAY1_SOURCE_COMMIT = "14587ac5ab9fa854b4d9b0a2138dad81761bb756"
DAY1_SOURCE_TREE = "30ec151f61850356bd42bf30c7e70af48083b3d6"
DAY1_EXECUTED_AT = "2026-08-25T15:00:03.280432Z"
DAY1_RUN_ID = "37ec818b-719b-5dc2-8995-e85f1b67cfdf"
HISTORY_RECEIPT_CREATED_AT = "2026-08-25T20:21:19.422539Z"
EXPECTED_ATOMIC_CHECK_IDS = tuple(f"{index:02d}_{name}" for index, name in (
    (1, "live_firestore"),
    (2, "project_bound"),
    (3, "default_database"),
    (4, "three_watch_cases"),
    (5, "one_due_selected"),
    (6, "two_future_excluded"),
    (7, "one_created_total"),
    (8, "run_created_event"),
    (9, "no_review_task"),
    (10, "exact_counts"),
    (11, "first_trigger_created_one"),
))


def history_receipt_artifact_id() -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            f"recall:cohort-history-receipt:{DAY1_EVIDENCE_SHA256}",
        )
    )


def load_day1_history_receipt(repo_root: Path) -> dict[str, object]:
    root = repo_root.resolve()
    path = (root / DAY1_EVIDENCE_PATH).resolve()
    if not path.is_relative_to(root):
        raise RuntimeError("cohort_history_evidence_path_escape")
    if not path.is_file():
        raise RuntimeError("cohort_history_evidence_missing")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DAY1_EVIDENCE_SHA256:
        raise RuntimeError("cohort_history_evidence_hash_mismatch")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("cohort_history_evidence_json_invalid") from exc
    facts = _validated_facts(value)
    return build_artifact(
        schema_name="CohortHistoryReceipt",
        schema_version="1.0.0",
        artifact_id=history_receipt_artifact_id(),
        case_id=COHORT_ID,
        run_id=DAY1_RUN_ID,
        producer={
            "component": "cohort-history-loader",
            "version": "1.0.0",
            "identity": "cohort-history-loader",
        },
        created_at=HISTORY_RECEIPT_CREATED_AT,
        input_artifact_ids=(),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID,
        payload=facts,
        authorized_producers=PRODUCER_REGISTRY,
    )


def _validated_facts(value: Any) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise RuntimeError("cohort_history_evidence_shape_invalid")
    checks = value.get("atomic_checks")
    if (
        not isinstance(checks, Mapping)
        or tuple(sorted(checks)) != EXPECTED_ATOMIC_CHECK_IDS
        or any(checks[item] is not True for item in EXPECTED_ATOMIC_CHECK_IDS)
    ):
        raise RuntimeError("cohort_history_atomic_checks_invalid")
    result = _mapping(value.get("trigger_result"), "trigger_result")
    readback = _mapping(value.get("readback"), "readback")
    counts = _mapping(readback.get("counts"), "readback.counts")
    created = _uuid_values(result.get("created_run_ids"), "created_run_ids")
    selected = _uuid_values(result.get("selected_case_ids"), "selected_case_ids")
    excluded = _uuid_values(result.get("excluded_case_ids"), "excluded_case_ids")
    expected_counts = {
        "artifacts": 7,
        "watch_cases": 3,
        "scan_runs": 1,
        "scan_run_events": 1,
        "review_tasks": 0,
    }
    if {field: counts.get(field) for field in expected_counts} != expected_counts:
        raise RuntimeError("cohort_history_readback_counts_invalid")
    fixed = {
        "source_commit": DAY1_SOURCE_COMMIT,
        "git_tree": DAY1_SOURCE_TREE,
        "phase": "first",
        "trigger_code": "DAY1_MANUAL",
        "executed_at": DAY1_EXECUTED_AT,
        "logical_trigger_at": "2026-08-25T15:00:00Z",
        "successful_process_exit_contract": 0,
    }
    if any(value.get(field) != expected for field, expected in fixed.items()):
        raise RuntimeError("cohort_history_evidence_semantics_invalid")
    if created != (DAY1_RUN_ID,) or len(selected) != 1 or len(excluded) != 2:
        raise RuntimeError("cohort_history_trigger_result_invalid")
    return {
        "evidence_path": DAY1_EVIDENCE_PATH.as_posix(),
        "evidence_sha256": DAY1_EVIDENCE_SHA256,
        "evidence_git_blob_oid": DAY1_EVIDENCE_BLOB_OID,
        "source_commit": DAY1_SOURCE_COMMIT,
        "source_tree": DAY1_SOURCE_TREE,
        "phase": "first",
        "trigger_code": "DAY1_MANUAL",
        "day_index": 1,
        "executed_at": DAY1_EXECUTED_AT,
        "selected_for_date": "2026-08-25",
        "created_run_ids": list(created),
        "selected_case_ids": list(selected),
        "excluded_case_ids": list(excluded),
        "runs_created": len(created),
        "runs_predicted": 1,
        "readback_counts": expected_counts,
        "direct_exit_code": 0,
        "evidence_classification": "LIVE_INFRASTRUCTURE_SYNTHETIC_DATA",
        "atomic_check_ids": list(EXPECTED_ATOMIC_CHECK_IDS),
    }


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"cohort_history_evidence_shape_invalid:{field}")
    return value


def _uuid_values(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError(f"cohort_history_evidence_shape_invalid:{field}")
    return tuple(sorted(value))
