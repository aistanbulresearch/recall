from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from recall.contracts import content_hash
from recall.ledger.models import COLLECTION_NAMES
from recall.scheduler.compressed_plan import load_compressed_plan
from recall.scheduler.compressed_preparation import (
    DEFAULT_COMPRESSED_BUNDLE_PATH,
    ensure_final_only_history_receipt,
    install_prepared_cycle,
    load_compressed_bundle,
)
from tests.support.compressed_v33_manifest import make_ledger


ROOT = Path(__file__).resolve().parents[2]


def _prepared_without_history():
    plan = load_compressed_plan(ROOT)
    bundle_path = ROOT / DEFAULT_COMPRESSED_BUNDLE_PATH
    bundle = load_compressed_bundle(
        ROOT,
        expected_sha256=__import__("hashlib").sha256(
            bundle_path.read_bytes()
        ).hexdigest(),
        plan=plan,
    )
    cycle = plan.by_id("c6")
    ledger = make_ledger(bundle, live=True)
    install_prepared_cycle(ledger, bundle, plan, cycle, now=cycle.window_start)
    history_id = str(bundle.history_receipt["artifact_id"])
    ledger._artifacts.pop(history_id)
    return plan, bundle, cycle, ledger, history_id


def _counts(ledger) -> dict[str, int]:
    return {name: ledger.read_back_count(name) for name in COLLECTION_NAMES}


def test_final_only_runtime_installs_only_exact_missing_history_after_read_only_precheck() -> None:
    plan, bundle, cycle, ledger, history_id = _prepared_without_history()
    before = _counts(ledger)

    created = ensure_final_only_history_receipt(ledger, bundle, plan, cycle)

    after = _counts(ledger)
    assert created == 1
    assert ledger.get_artifact(history_id) == bundle.history_receipt
    assert after["artifacts"] == before["artifacts"] + 1
    assert {key: after[key] for key in after if key != "artifacts"} == {
        key: before[key] for key in before if key != "artifacts"
    }


def test_final_only_runtime_refuses_history_install_when_other_preparation_is_missing() -> None:
    plan, bundle, cycle, ledger, history_id = _prepared_without_history()
    missing_case = bundle.cases[0]
    ledger._watch_cases.pop(missing_case.case_id)
    before = _counts(ledger)

    with pytest.raises(RuntimeError, match="compressed_prepared_watch_case_missing"):
        ensure_final_only_history_receipt(ledger, bundle, plan, cycle)

    assert ledger.get_artifact(history_id) is None
    assert _counts(ledger) == before


def test_final_only_runtime_refuses_conflicting_history_without_writes() -> None:
    plan, bundle, cycle, ledger, history_id = _prepared_without_history()
    conflicting = deepcopy(bundle.history_receipt)
    conflicting["warnings"] = [
        {
            "code": "CONFLICT",
            "message_key": "CONFLICT",
            "related_artifact_ids": [],
        }
    ]
    conflicting["content_hash"] = content_hash(conflicting)
    ledger.append_artifact(conflicting)
    before = _counts(ledger)

    with pytest.raises(RuntimeError, match="cohort_history_receipt_missing"):
        ensure_final_only_history_receipt(ledger, bundle, plan, cycle)

    assert ledger.get_artifact(history_id) == conflicting
    assert _counts(ledger) == before
