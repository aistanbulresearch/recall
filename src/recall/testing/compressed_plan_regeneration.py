from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from recall.scheduler.compressed_plan import PLAN_PATH
from recall.testing.deadline_policy_vectors import (
    VECTOR_PATH,
    render_deadline_policy_vectors,
)


RUNNABLE_CYCLE_IDS = ("c3", "c4", "c5", "c6")
STALE_PREPARATION_BUNDLE = Path(
    "artifacts/evidence/cohort-compression/preparation-bundle-v2.json"
)
CORE_PIN_COUNTS = {
    Path("src/recall/scheduler/compressed_plan.py"): 1,
    Path("src/recall/contracts/payloads/scheduler_v3.py"): 1,
    Path("src/recall/contracts/payloads/scheduler_v33.py"): 4,
}
WEB_PIN_PATH = Path("web/src/viewmodel/deadline_policy.ts")


@dataclass(frozen=True, slots=True)
class PlanRegenerationResult:
    old_plan_sha256: str
    new_plan_sha256: str
    anchor_utc: str
    shifted_cycle_ids: tuple[str, ...]
    core_pin_paths: tuple[str, ...]
    web_pin_path: str
    core_vector_path: str
    web_vector_path: str
    stale_old_sha_paths: tuple[str, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "old_plan_sha256": self.old_plan_sha256,
            "new_plan_sha256": self.new_plan_sha256,
            "anchor_utc": self.anchor_utc,
            "shifted_cycle_ids": list(self.shifted_cycle_ids),
            "core_pin_paths": list(self.core_pin_paths),
            "web_pin_path": self.web_pin_path,
            "core_vector_path": self.core_vector_path,
            "web_vector_path": self.web_vector_path,
            "stale_preparation_status": (
                "STALE_REQUIRES_REGEN"
                if self.stale_old_sha_paths
                else "NOT_PRESENT"
            ),
            "stale_old_sha_paths": list(self.stale_old_sha_paths),
        }


def regenerate_compressed_plan(
    core_root: Path,
    web_root: Path,
    *,
    anchor: str,
) -> PlanRegenerationResult:
    """Shift c3-c6, refresh every executable SHA pin, and rebuild vectors."""

    core_root = core_root.resolve()
    web_root = web_root.resolve()
    anchor_utc = _parse_anchor(anchor)
    plan_path = core_root / PLAN_PATH
    old_plan_bytes = plan_path.read_bytes()
    old_plan_sha = hashlib.sha256(old_plan_bytes).hexdigest()
    old_plan = json.loads(old_plan_bytes.decode("utf-8"))
    new_plan_bytes, new_plan = _shift_plan(old_plan_bytes, anchor_utc)
    new_plan_sha = hashlib.sha256(new_plan_bytes).hexdigest()

    expected_old_paths = {
        *(path.as_posix() for path in CORE_PIN_COUNTS),
        VECTOR_PATH.as_posix(),
        STALE_PREPARATION_BUNDLE.as_posix(),
    }
    core_old_paths = _sha_occurrences(core_root, old_plan_sha)
    unexpected_core = core_old_paths - expected_old_paths
    if unexpected_core:
        raise RuntimeError(
            "compressed_plan_unexpected_old_sha:" + ",".join(sorted(unexpected_core))
        )
    web_expected = {WEB_PIN_PATH.as_posix(), VECTOR_PATH.as_posix()}
    unexpected_web = _sha_occurrences(web_root, old_plan_sha) - web_expected
    if unexpected_web:
        raise RuntimeError(
            "compressed_plan_unexpected_web_old_sha:"
            + ",".join(sorted(unexpected_web))
        )

    pin_outputs: dict[Path, bytes] = {}
    for relative, count in CORE_PIN_COUNTS.items():
        target = core_root / relative
        pin_outputs[target] = _replace_pin(
            target.read_bytes(), old_plan_sha, new_plan_sha, count=count
        )
    web_pin = web_root / WEB_PIN_PATH
    web_pin_output = _replace_pin(
        web_pin.read_bytes(), old_plan_sha, new_plan_sha, count=1
    )

    _assert_values_only(old_plan, new_plan)
    with TemporaryDirectory(prefix="recall-plan-vectors-") as raw_temp:
        vector_root = Path(raw_temp)
        vector_plan = vector_root / PLAN_PATH
        vector_plan.parent.mkdir(parents=True)
        vector_plan.write_bytes(new_plan_bytes)
        vectors = render_deadline_policy_vectors(vector_root)
    core_vector = core_root / VECTOR_PATH
    web_vector = web_root / VECTOR_PATH
    outputs = {
        plan_path: new_plan_bytes,
        **pin_outputs,
        web_pin: web_pin_output,
        core_vector: vectors,
        web_vector: vectors,
    }
    originals = {
        target: target.read_bytes() if target.is_file() else None
        for target in outputs
    }
    try:
        for target, output in outputs.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            _write_output(target, output)

        stale_old_sha_paths: set[str] = set()
        if old_plan_sha != new_plan_sha:
            allowed_stale = {STALE_PREPARATION_BUNDLE.as_posix()}
            stale_old_sha_paths = _sha_occurrences(core_root, old_plan_sha)
            stale_web = _sha_occurrences(web_root, old_plan_sha)
            if stale_old_sha_paths - allowed_stale or stale_web:
                raise RuntimeError(
                    "compressed_plan_old_sha_remains_outside_stale_bundle"
                )
        preparation_path = core_root / STALE_PREPARATION_BUNDLE
        if preparation_path.is_file():
            preparation = json.loads(
                preparation_path.read_text(encoding="utf-8")
            )
            if preparation.get("plan_sha256") != new_plan_sha:
                stale_old_sha_paths.add(STALE_PREPARATION_BUNDLE.as_posix())
        if core_vector.read_bytes() != web_vector.read_bytes():
            raise RuntimeError("deadline_vector_cross_branch_mismatch")
    except BaseException:
        for target, original in originals.items():
            if original is None:
                target.unlink(missing_ok=True)
            else:
                _atomic_write(target, original)
        raise

    return PlanRegenerationResult(
        old_plan_sha256=old_plan_sha,
        new_plan_sha256=new_plan_sha,
        anchor_utc=_wire_timestamp(anchor_utc),
        shifted_cycle_ids=RUNNABLE_CYCLE_IDS,
        core_pin_paths=tuple(path.as_posix() for path in CORE_PIN_COUNTS),
        web_pin_path=WEB_PIN_PATH.as_posix(),
        core_vector_path=VECTOR_PATH.as_posix(),
        web_vector_path=VECTOR_PATH.as_posix(),
        stale_old_sha_paths=tuple(sorted(stale_old_sha_paths)),
    )


def _shift_plan(raw: bytes, anchor: datetime) -> tuple[bytes, dict[str, object]]:
    before = json.loads(raw.decode("utf-8"))
    cycles = _cycle_map(before)
    old_anchor = _timestamp(cycles["c3"]["window_start"])
    delta = anchor - old_anchor
    text = raw.decode("utf-8")
    replacements: list[tuple[str, str]] = []
    for cycle_id in RUNNABLE_CYCLE_IDS:
        cycle = cycles[cycle_id]
        for field in ("window_start", "window_end"):
            old_value = cycle[field]
            new_value = _wire_timestamp(_timestamp(old_value) + delta)
            needle = f'"{field}": "{old_value}"'
            replacement = f'"{field}": "{new_value}"'
            if text.count(needle) != 1:
                raise RuntimeError(
                    f"compressed_plan_window_occurrence_invalid:{cycle_id}:{field}"
                )
            placeholder = f'"{field}": "__RECALL_{cycle_id}_{field}__"'
            text = text.replace(needle, placeholder, 1)
            replacements.append((placeholder, replacement))
    for placeholder, replacement in replacements:
        text = text.replace(placeholder, replacement, 1)
    after = json.loads(text)
    _assert_values_only(before, after)
    return text.encode("utf-8"), after


def _assert_values_only(
    before: dict[str, object], after: dict[str, object]
) -> None:
    before_cycles = _cycle_map(before)
    after_cycles = _cycle_map(after)
    if before_cycles["c1"] != after_cycles["c1"]:
        raise RuntimeError("compressed_plan_executed_cycle_changed:c1")
    if before_cycles["c2"] != after_cycles["c2"]:
        raise RuntimeError("compressed_plan_executed_cycle_changed:c2")

    deltas = set()
    for cycle_id in RUNNABLE_CYCLE_IDS:
        old_cycle = before_cycles[cycle_id]
        new_cycle = after_cycles[cycle_id]
        for field in set(old_cycle) - {"window_start", "window_end"}:
            if old_cycle[field] != new_cycle[field]:
                raise RuntimeError(
                    f"compressed_plan_non_window_changed:{cycle_id}:{field}"
                )
        start_delta = (
            _timestamp(new_cycle["window_start"])
            - _timestamp(old_cycle["window_start"])
        )
        end_delta = (
            _timestamp(new_cycle["window_end"])
            - _timestamp(old_cycle["window_end"])
        )
        if start_delta != end_delta:
            raise RuntimeError(f"compressed_plan_duration_changed:{cycle_id}")
        deltas.add(start_delta)
    if len(deltas) != 1:
        raise RuntimeError("compressed_plan_relative_windows_changed")

    before_without_cycles = {key: value for key, value in before.items() if key != "cycles"}
    after_without_cycles = {key: value for key, value in after.items() if key != "cycles"}
    if before_without_cycles != after_without_cycles:
        raise RuntimeError("compressed_plan_non_cycle_field_changed")


def _cycle_map(value: dict[str, object]) -> dict[str, dict[str, object]]:
    cycles = value.get("cycles")
    if not isinstance(cycles, list):
        raise RuntimeError("compressed_plan_cycles_invalid")
    result = {
        str(item.get("cycle_id")): item
        for item in cycles
        if isinstance(item, dict)
    }
    if set(result) != {"c1", "c2", *RUNNABLE_CYCLE_IDS}:
        raise RuntimeError("compressed_plan_cycle_set_invalid")
    return result


def _replace_pin(raw: bytes, old: str, new: str, *, count: int) -> bytes:
    text = raw.decode("utf-8")
    if old == new:
        if text.count(new) != count:
            raise RuntimeError("compressed_plan_current_pin_count_invalid")
        return raw
    if text.count(old) != count:
        raise RuntimeError("compressed_plan_old_pin_count_invalid")
    return text.replace(old, new).encode("utf-8")


def _write_output(target: Path, output: bytes) -> None:
    _atomic_write(target, output)


def _atomic_write(target: Path, output: bytes) -> None:
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            dir=target.parent,
            prefix=f".{target.name}.recall-plan-",
            delete=False,
        ) as handle:
            handle.write(output)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _sha_occurrences(root: Path, sha256: str) -> set[str]:
    command = [
        "git",
        "-C",
        str(root),
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("compressed_plan_git_scan_failed")
    result: set[str] = set()
    needle = sha256.encode("ascii")
    for raw_path in completed.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = raw_path.decode("utf-8")
        if Path(relative).parts[0].startswith(".pytest-"):
            continue
        candidate = root / relative
        if candidate.is_file() and needle in candidate.read_bytes():
            result.add(Path(relative).as_posix())
    return result


def _parse_anchor(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError("compressed_plan_anchor_invalid") from exc
    if parsed.tzinfo is None or parsed.microsecond:
        raise RuntimeError("compressed_plan_anchor_invalid")
    return parsed.astimezone(timezone.utc)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RuntimeError("compressed_plan_timestamp_invalid")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    return parsed.astimezone(timezone.utc)


def _wire_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
