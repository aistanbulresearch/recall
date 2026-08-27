from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from recall.contracts import content_hash
from recall.scheduler.compressed_identity import prepared_watch_artifact_id
from recall.scheduler.compressed_plan import PLAN_PATH, CompressedPlan
from recall.scheduler.compressed_preparation import (
    DEFAULT_COMPRESSED_BUNDLE_PATH,
    CompressedPreparationBundle,
    load_compressed_bundle,
)
from recall.scheduler.history import DAY1_EVIDENCE_PATH


def rebound_bundle_wire(root: Path, plan: CompressedPlan) -> dict[str, object]:
    """Rebind the legacy committed bundle for unit tests without altering evidence."""

    value = json.loads(
        (root / DEFAULT_COMPRESSED_BUNDLE_PATH).read_text(encoding="utf-8")
    )
    rebound = deepcopy(value)
    rebound["plan_sha256"] = plan.sha256
    for item in rebound["cases"]:
        cycle_id = item["cycle_id"]
        if cycle_id == "historical-day1":
            continue
        cycle = plan.by_id(cycle_id)
        watch = item["watch_case"]
        watch["artifact_id"] = prepared_watch_artifact_id(item["case_id"], cycle)
        watch["next_scan_at"] = cycle.schedule_epoch
        watch["content_hash"] = content_hash(watch)
    return rebound


def load_rebound_test_bundle(
    root: Path, plan: CompressedPlan
) -> tuple[CompressedPreparationBundle, str]:
    with TemporaryDirectory(prefix="recall-rebound-bundle-") as raw_temp:
        bundle, digest = write_rebound_test_repo(root, plan, Path(raw_temp))
    return bundle, digest


def write_rebound_test_repo(
    root: Path,
    plan: CompressedPlan,
    target_root: Path,
) -> tuple[CompressedPreparationBundle, str]:
    value = rebound_bundle_wire(root, plan)
    history = target_root / DAY1_EVIDENCE_PATH
    history.parent.mkdir(parents=True, exist_ok=True)
    history.write_bytes((root / DAY1_EVIDENCE_PATH).read_bytes())
    plan_target = target_root / PLAN_PATH
    plan_target.parent.mkdir(parents=True, exist_ok=True)
    plan_target.write_bytes((root / PLAN_PATH).read_bytes())
    target = target_root / DEFAULT_COMPRESSED_BUNDLE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    bundle = load_compressed_bundle(
        target_root,
        expected_sha256=digest,
        plan=plan,
    )
    return bundle, digest
