from __future__ import annotations

import hashlib
import subprocess
from datetime import date
from pathlib import Path

from recall.scheduler.cohort import (
    MANAGED_COHORT,
    REPLAY_ANCHORS,
    RUN_PREDICTIONS,
    cases_for_date,
    verify_replay_anchors,
)
from recall.scheduler.config import COHORT as FROZEN_DAY1_COHORT


ROOT = Path(__file__).resolve().parents[2]


def test_cohort_preserves_original_three_and_adds_nine() -> None:
    assert len(MANAGED_COHORT) == 12
    assert tuple(
        (item.case_id, item.next_scan_at, item.cursor)
        for item in MANAGED_COHORT[:3]
    ) == tuple(
        (item.case_id, item.next_scan_at, item.cursor)
        for item in FROZEN_DAY1_COHORT
    )


def test_committed_predictions_match_exact_due_dates() -> None:
    for selected_for_date, predicted in RUN_PREDICTIONS.items():
        assert len(cases_for_date(selected_for_date)) == predicted
    assert [RUN_PREDICTIONS[date(2026, 8, day)] for day in (26, 27, 28)] == [
        3,
        2,
        4,
    ]


def test_replay_cases_have_exactly_one_registered_anchor() -> None:
    anchors = {item.vcv: item for item in REPLAY_ANCHORS}
    replay_cases = [item for item in MANAGED_COHORT if item.vcv is not None]
    assert len(replay_cases) == 5
    assert len({item.vcv for item in replay_cases}) == 5
    assert all(item.vcv in anchors for item in replay_cases)
    assert all(item.data_mode.value == "SYNTHETIC" for item in replay_cases)
    assert all(
        item.declared_composition.value == "SYNTHETIC_WITH_CAPTURED_REPLAY"
        for item in replay_cases
    )
    assert all(
        item.data_mode.value == "SYNTHETIC"
        and item.declared_composition.value == "SYNTHETIC_ONLY"
        for item in MANAGED_COHORT
        if item.vcv is None
    )


def test_replay_capture_hashes_match_worktree_and_git_blobs() -> None:
    verify_replay_anchors(ROOT)
    for anchor in REPLAY_ANCHORS:
        worktree = (ROOT / anchor.capture_path).read_bytes()
        assert hashlib.sha256(worktree).hexdigest() == anchor.sha256
        committed = subprocess.run(
            ["git", "cat-file", "blob", f"HEAD:{anchor.capture_path}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert hashlib.sha256(committed).hexdigest() == anchor.sha256


def test_case_ids_and_cursors_are_unique() -> None:
    assert len({item.case_id for item in MANAGED_COHORT}) == len(MANAGED_COHORT)
    assert len({item.cursor for item in MANAGED_COHORT}) == len(MANAGED_COHORT)
