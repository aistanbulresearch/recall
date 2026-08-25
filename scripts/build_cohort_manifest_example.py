from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from recall.ledger.memory import InMemoryLedger
from recall.scheduler.dayn import DayNScheduler
from recall.scheduler.preparation import (
    DEFAULT_BUNDLE_PATH,
    LockedPreparationVerifier,
    install_prepared_day,
    load_preparation_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("artifacts/evidence/cohort-manifest-example")


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
        source_commit=_git("rev-parse", "HEAD"),
    ).trigger(now=now, previous_manifest=None)
    manifest = ledger.get_artifact(result.manifest_artifact_id)
    receipt = ledger.get_artifact(result.data_mode_receipt_id)
    if manifest is None or receipt is None:
        raise RuntimeError("cohort_manifest_example_missing")
    target = ROOT / OUTPUT
    target.mkdir(parents=True, exist_ok=True)
    outputs = {
        "day2-manifest.synthetic.json": manifest,
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


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
