from __future__ import annotations

import hashlib
import json
import copy
from datetime import datetime, timezone
from pathlib import Path

from recall.ledger.memory import InMemoryLedger
from recall.contracts import content_hash
from recall.scheduler.dayn import DayNScheduler
from recall.scheduler.preparation import (
    DEFAULT_BUNDLE_PATH,
    LockedPreparationVerifier,
    install_prepared_day,
    load_preparation_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("artifacts/evidence/cohort-manifest-example")
EXAMPLE_IMAGE_DIGEST = "sha256:" + hashlib.sha256(
    b"recall:in-memory-synthetic-manifest-example:v2.1"
).hexdigest()


def main() -> int:
    bundle_path = ROOT / DEFAULT_BUNDLE_PATH
    bundle_sha = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    bundle = load_preparation_bundle(ROOT, expected_sha256=bundle_sha)
    ledger = InMemoryLedger(
        privacy_receipt_verifier=LockedPreparationVerifier(bundle)
    )
    now = datetime(2026, 8, 26, 16, 1, tzinfo=timezone.utc)
    install_prepared_day(ledger, bundle, now=now)
    result = DayNScheduler(
        ledger,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=EXAMPLE_IMAGE_DIGEST,
    ).trigger(now=now, previous_manifest=None)
    manifest = ledger.get_artifact(result.manifest_artifact_id)
    receipt = ledger.get_artifact(result.data_mode_receipt_id)
    if manifest is None or receipt is None:
        raise RuntimeError("cohort_manifest_example_missing")
    legacy_manifest = copy.deepcopy(manifest)
    legacy_manifest["schema_version"] = "2.0.0"
    for row in legacy_manifest["execution_history"]:
        row.pop("execution_status")
        row.pop("failure_receipt_id")
    legacy_manifest["content_hash"] = "0" * 64
    legacy_manifest["content_hash"] = content_hash(legacy_manifest)
    target = ROOT / OUTPUT
    target.mkdir(parents=True, exist_ok=True)
    outputs = {
        "day1-history-receipt.live-synthetic.json": bundle.history_receipt,
        "day2-manifest.synthetic.json": manifest,
        "day2-manifest.v2.0.legacy.json": legacy_manifest,
        "day2-data-mode-receipt.synthetic.json": receipt,
    }
    hashes = {}
    for name, value in outputs.items():
        path = target / name
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    print(json.dumps({"files": hashes, "live_execution": False}, sort_keys=True))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
