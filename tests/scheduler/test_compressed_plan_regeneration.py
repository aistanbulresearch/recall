from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest
import recall.testing.compressed_plan_regeneration as regeneration_module

from recall.scheduler.compressed_plan import PLAN_PATH
from recall.testing.compressed_plan_regeneration import (
    CORE_PIN_COUNTS,
    STALE_PREPARATION_BUNDLE,
    WEB_PIN_PATH,
    regenerate_compressed_plan,
)
from recall.testing.deadline_policy_vectors import VECTOR_PATH


ROOT = Path(__file__).resolve().parents[2]


def test_regeneration_shifts_only_runnable_windows_and_refreshes_all_pins(
    tmp_path: Path,
) -> None:
    core = tmp_path / "core"
    web = tmp_path / "web"
    before = json.loads((ROOT / PLAN_PATH).read_text(encoding="utf-8"))
    old_sha = _seed_repositories(core, web)

    result = regenerate_compressed_plan(
        core,
        web,
        anchor="2026-08-29T09:00:00+03:00",
    )

    after = json.loads((core / PLAN_PATH).read_text(encoding="utf-8"))
    assert result.anchor_utc == "2026-08-29T06:00:00Z"
    assert after["cycles"][:2] == before["cycles"][:2]
    assert after["cycles"][2]["window_start"] == "2026-08-29T06:00:00Z"
    assert after["cycles"][3]["window_start"] == "2026-08-30T03:00:00Z"
    assert after["cycles"][4]["window_start"] == "2026-08-31T03:00:00Z"
    assert after["cycles"][5]["window_start"] == "2026-09-01T03:00:00Z"
    assert _without_windows(after) == _without_windows(before)
    assert result.old_plan_sha256 == old_sha
    assert result.new_plan_sha256 == hashlib.sha256(
        (core / PLAN_PATH).read_bytes()
    ).hexdigest()
    assert result.stale_old_sha_paths == (
        STALE_PREPARATION_BUNDLE.as_posix(),
    )
    for path, count in CORE_PIN_COUNTS.items():
        assert (core / path).read_text(encoding="utf-8").count(
            result.new_plan_sha256
        ) == count
    assert (web / WEB_PIN_PATH).read_text(encoding="utf-8").count(
        result.new_plan_sha256
    ) == 1
    assert (core / VECTOR_PATH).read_bytes() == (web / VECTOR_PATH).read_bytes()


def test_regeneration_refuses_unexpected_old_sha_before_writes(
    tmp_path: Path,
) -> None:
    core = tmp_path / "core"
    web = tmp_path / "web"
    old_sha = _seed_repositories(core, web)
    unexpected = core / "unexpected.txt"
    unexpected.write_text(old_sha, encoding="utf-8")
    _git(core, "add", "unexpected.txt")
    before = (core / PLAN_PATH).read_bytes()

    with pytest.raises(RuntimeError, match="unexpected_old_sha"):
        regenerate_compressed_plan(
            core,
            web,
            anchor="2026-08-28T09:00:00+03:00",
        )

    assert (core / PLAN_PATH).read_bytes() == before


def test_regeneration_rolls_back_both_roots_after_mid_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core = tmp_path / "core"
    web = tmp_path / "web"
    _seed_repositories(core, web)
    before = _all_bytes(core, web)
    writes = 0
    original = regeneration_module._write_output

    def injected(target: Path, output: bytes) -> None:
        nonlocal writes
        writes += 1
        if writes == 4:
            raise OSError("injected_mid_write_failure")
        original(target, output)

    monkeypatch.setattr(regeneration_module, "_write_output", injected)
    with pytest.raises(OSError, match="injected_mid_write_failure"):
        regenerate_compressed_plan(
            core,
            web,
            anchor="2026-08-29T09:00:00+03:00",
        )
    assert _all_bytes(core, web) == before


def test_regeneration_rolls_back_both_roots_after_keyboard_interrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core = tmp_path / "core"
    web = tmp_path / "web"
    _seed_repositories(core, web)
    before = _all_bytes(core, web)
    writes = 0
    original = regeneration_module._write_output

    def interrupted(target: Path, output: bytes) -> None:
        nonlocal writes
        writes += 1
        if writes == 4:
            raise KeyboardInterrupt
        original(target, output)

    monkeypatch.setattr(regeneration_module, "_write_output", interrupted)
    with pytest.raises(KeyboardInterrupt):
        regenerate_compressed_plan(
            core,
            web,
            anchor="2026-08-29T09:00:00+03:00",
        )
    assert _all_bytes(core, web) == before


def test_regeneration_rolls_back_both_roots_after_post_validation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core = tmp_path / "core"
    web = tmp_path / "web"
    _seed_repositories(core, web)
    before = _all_bytes(core, web)
    scans = 0
    original = regeneration_module._sha_occurrences

    def injected(root: Path, sha256: str) -> set[str]:
        nonlocal scans
        scans += 1
        observed = original(root, sha256)
        if scans == 3:
            observed.add("post-validation-injected.txt")
        return observed

    monkeypatch.setattr(regeneration_module, "_sha_occurrences", injected)
    with pytest.raises(RuntimeError, match="old_sha_remains"):
        regenerate_compressed_plan(
            core,
            web,
            anchor="2026-08-29T09:00:00+03:00",
        )
    assert _all_bytes(core, web) == before


@pytest.mark.parametrize("anchor", ["2026-08-28T09:00:00", "not-a-time"])
def test_regeneration_requires_explicit_timezone(anchor: str, tmp_path: Path) -> None:
    core = tmp_path / "core"
    web = tmp_path / "web"
    _seed_repositories(core, web)
    with pytest.raises(RuntimeError, match="compressed_plan_anchor_invalid"):
        regenerate_compressed_plan(core, web, anchor=anchor)


def _seed_repositories(core: Path, web: Path) -> str:
    plan = (ROOT / PLAN_PATH).read_bytes()
    old_sha = hashlib.sha256(plan).hexdigest()
    _write(core / PLAN_PATH, plan)
    for path, count in CORE_PIN_COUNTS.items():
        _write(core / path, ((old_sha + "\n") * count).encode())
    _write(core / VECTOR_PATH, (old_sha + "\n").encode())
    _write(
        core / STALE_PREPARATION_BUNDLE,
        (json.dumps({"plan_sha256": old_sha}) + "\n").encode(),
    )
    _write(web / WEB_PIN_PATH, (old_sha + "\n").encode())
    _write(web / VECTOR_PATH, (old_sha + "\n").encode())
    for root in (core, web):
        _git(root, "init")
        _git(root, "add", ".")
    return old_sha


def _write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


def _git(root: Path, *args: str) -> None:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def _without_windows(value: dict[str, object]) -> dict[str, object]:
    clone = deepcopy(value)
    for cycle in clone["cycles"]:
        cycle.pop("window_start")
        cycle.pop("window_end")
    return clone


def _all_bytes(core: Path, web: Path) -> dict[str, bytes]:
    paths = [
        core / PLAN_PATH,
        *(core / path for path in CORE_PIN_COUNTS),
        core / VECTOR_PATH,
        web / WEB_PIN_PATH,
        web / VECTOR_PATH,
    ]
    return {str(path): path.read_bytes() for path in paths}
