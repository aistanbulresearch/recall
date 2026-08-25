from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

from recall.ledger.firestore import FirestoreLedger
from recall.platform.redaction import redact_json
from recall.scheduler.dayn import collection_prefix
from recall.scheduler.cohort import RUN_PREDICTIONS
from recall.scheduler.preparation import (
    LockedPreparationVerifier,
    install_prepared_day,
    load_preparation_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    selected_date = date.fromisoformat(args.date)
    if selected_date <= date(2026, 8, 25) or selected_date not in RUN_PREDICTIONS:
        raise RuntimeError("cohort_preparation_date_not_registered")
    expected_bundle_sha = os.environ.get("RECALL_COHORT_PREPARATION_SHA256")
    project_sha = os.environ.get("RECALL_EXPECTED_PROJECT_SHA256")
    if not expected_bundle_sha or not project_sha:
        raise RuntimeError("cohort_preparation_environment_missing")
    bundle = load_preparation_bundle(
        Path.cwd(), expected_sha256=expected_bundle_sha
    )
    verifier = LockedPreparationVerifier(bundle)
    ledger = FirestoreLedger.from_default_credentials(
        collection_prefix=collection_prefix(selected_date),
        privacy_receipt_verifier=verifier,
        expected_project_sha256=project_sha,
        database="(default)",
        require_live=True,
    )
    result = install_prepared_day(
        ledger,
        bundle,
        now=datetime.now(timezone.utc),
    )
    payload = {
        "mode": "LAB_LOCAL_PREPARATION_LIVE_FIRESTORE_SYNTHETIC_DATA",
        "selected_for_date": selected_date.isoformat(),
        "collection_prefix": collection_prefix(selected_date),
        "writes": dict(result),
        "readback": {
            name: ledger.read_back_count(name)
            for name in ledger.collection_names
        },
        "preparation_bundle_sha256": bundle.bundle_sha256,
        "claim_boundary": {
            "privacy_admission": "LAB_LOCAL_PREPARED_COMMITTED_WIRES",
            "managed_schedule": "NOT_EXECUTED_BY_THIS_COMMAND",
        },
    }
    print(json.dumps(redact_json(payload), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
