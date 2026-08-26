from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

from recall.ledger.firestore import FirestoreLedger
from recall.platform.redaction import redact_json
from recall.scheduler.compressed_identity import collection_prefix
from recall.scheduler.compressed_plan import load_compressed_plan
from recall.scheduler.compressed_preparation import (
    CompressedPreparationVerifier,
    install_prepared_cycle,
    load_compressed_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    selected_date = date.fromisoformat(args.date)
    root = Path.cwd()
    plan = load_compressed_plan(root)
    cycle = plan.by_due_date(selected_date)
    expected_bundle_sha = os.environ.get("RECALL_COMPRESSED_PREPARATION_SHA256")
    project_sha = os.environ.get("RECALL_EXPECTED_PROJECT_SHA256")
    if not expected_bundle_sha or not project_sha:
        raise RuntimeError("cohort_preparation_environment_missing")
    bundle = load_compressed_bundle(
        root, expected_sha256=expected_bundle_sha, plan=plan
    )
    verifier = CompressedPreparationVerifier(bundle)
    ledger = FirestoreLedger.from_default_credentials(
        collection_prefix=collection_prefix(cycle),
        privacy_receipt_verifier=verifier,
        expected_project_sha256=project_sha,
        database="(default)",
        require_live=True,
    )
    result = install_prepared_cycle(
        ledger,
        bundle,
        plan,
        cycle,
        now=datetime.now(timezone.utc),
    )
    payload = {
        "mode": "LAB_LOCAL_PREPARATION_LIVE_FIRESTORE_SYNTHETIC_DATA",
        "cycle_id": cycle.cycle_id,
        "cohort_due_date": selected_date.isoformat(),
        "collection_prefix": collection_prefix(cycle),
        "plan_sha256": plan.sha256,
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
