from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from recall.ledger.firestore import FirestoreLedger
from recall.platform.redaction import redact_json

from .dayn import DayNScheduler, collection_prefix, preview
from .manifest import day_index, manifest_artifact_id
from .preparation import (
    LockedPreparationVerifier,
    load_preparation_bundle,
)


LedgerFactory = Callable[..., Any]
_SOURCE_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def execute(
    argv: Sequence[str],
    *,
    environment: Mapping[str, str],
    now_factory: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ledger_factory: LedgerFactory = FirestoreLedger.from_default_credentials,
    repo_root: Path | None = None,
) -> dict[str, object]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview-date")
    args = parser.parse_args(list(argv))
    root = (repo_root or Path.cwd()).resolve()
    bundle_sha = _required(environment, "RECALL_COHORT_PREPARATION_SHA256")
    bundle = load_preparation_bundle(root, expected_sha256=bundle_sha)
    source_commit = _required(environment, "RECALL_SOURCE_COMMIT")
    if not _SOURCE_COMMIT.fullmatch(source_commit):
        raise RuntimeError("cohort_source_commit_invalid")
    if source_commit != bundle.source_commit:
        raise RuntimeError("source_commit_mismatch")
    image_digest = _required(environment, "RECALL_IMAGE_DIGEST")
    if not _IMAGE_DIGEST.fullmatch(image_digest):
        raise RuntimeError("cohort_image_digest_invalid")
    if args.preview_date:
        selected = date.fromisoformat(args.preview_date)
        result = preview(selected, repo_root=root)
        return {
            "mode": "DRY_RUN_SELECTION_PREVIEW",
            "writes": 0,
            "selected_for_date": result.selected_for_date,
            "selected_case_ids": list(result.selected_case_ids),
            "excluded_case_ids": list(result.excluded_case_ids),
            "runs_predicted": result.runs_predicted,
            "collection_prefix": result.collection_prefix,
            "preparation_bundle_sha256": bundle.bundle_sha256,
            "source_commit": source_commit,
            "image_digest": image_digest,
        }
    project_sha = _required(environment, "RECALL_EXPECTED_PROJECT_SHA256")
    now = now_factory()
    selected_date = now.astimezone(timezone.utc).date()
    verifier = LockedPreparationVerifier(bundle)
    ledger = ledger_factory(
        collection_prefix=collection_prefix(selected_date),
        privacy_receipt_verifier=verifier,
        expected_project_sha256=project_sha,
        database="(default)",
        require_live=True,
    )
    previous = None
    if day_index(selected_date) > 2:
        prior_date = selected_date - timedelta(days=1)
        prior = ledger_factory(
            collection_prefix=collection_prefix(prior_date),
            privacy_receipt_verifier=verifier,
            expected_project_sha256=project_sha,
            database="(default)",
            require_live=True,
        )
        previous = prior.get_artifact(manifest_artifact_id(prior_date))
        if previous is None:
            raise RuntimeError("previous_cohort_manifest_missing")
    result = DayNScheduler(
        ledger,
        bundle=bundle,
        source_commit=source_commit,
        image_digest=image_digest,
    ).trigger(now=now, previous_manifest=previous)
    return {
        "mode": "LIVE_FIRESTORE_SYNTHETIC_COHORT_TICK",
        "selected_for_date": result.selected_for_date,
        "newly_created_run_ids": list(result.newly_created_run_ids),
        "reused_run_ids": list(result.reused_run_ids),
        "authoritative_run_ids": list(result.authoritative_run_ids),
        "manifest_artifact_id": result.manifest_artifact_id,
        "data_mode_receipt_id": result.data_mode_receipt_id,
        "collection_prefix": collection_prefix(selected_date),
        "backend": dict(ledger.backend_metadata()),
        "claim_boundary": {
            "managed_tick": "EXECUTED",
            "managed_admission": "NOT_CLAIMED_LAB_LOCAL_PREPARATION",
            "cross_day_watch_case_continuity": "NOT_CLAIMED_DATE_ISOLATED",
            "terminal_agent_execution": "NOT_RUN_NOT_CLAIMED",
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    import sys

    result = execute(sys.argv[1:] if argv is None else argv, environment=os.environ)
    print(json.dumps(redact_json(result), sort_keys=True))
    return 0


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if not value:
        raise RuntimeError(f"cohort_required_environment_missing:{name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
