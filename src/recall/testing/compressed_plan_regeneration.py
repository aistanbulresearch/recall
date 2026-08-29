from __future__ import annotations

import hashlib
import json
import os
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Sequence

from recall.scheduler.compressed_plan import (
    PLAN_PATH,
    PLAN9_C4_EPOCH_LABEL,
    PLAN9_RETRY_EPOCH_LABEL,
    parse_compressed_plan,
)
from recall.testing.deadline_policy_vectors import (
    VECTOR_PATH,
    render_deadline_policy_vectors,
)


RUNNABLE_CYCLE_IDS = ("c3", "c4", "c5", "c6")
STALE_PREPARATION_BUNDLE = Path(
    "artifacts/evidence/cohort-compression/preparation-bundle-v2.json"
)
IMMUTABLE_HISTORICAL_SHA_PATHS = frozenset(
    {
        Path(
            "artifacts/evidence/cohort-compression/"
            "PLAN8_C3_LIVE_PARSE_RECEIPT.json"
        )
    }
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
    mode: str
    anchor_utc: str | None
    applied_windows: tuple[tuple[str, str, str], ...]
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
            "mode": self.mode,
            "anchor_utc": self.anchor_utc,
            "applied_windows": [
                {
                    "cycle_id": cycle_id,
                    "window_start": window_start,
                    "window_end": window_end,
                }
                for cycle_id, window_start, window_end in self.applied_windows
            ],
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
    anchor: str | None = None,
    windows: Sequence[tuple[str, str, str]] | None = None,
    plan9_r1_retry: bool = False,
) -> PlanRegenerationResult:
    """Shift c3-c6, refresh every executable SHA pin, and rebuild vectors."""

    core_root = core_root.resolve()
    web_root = web_root.resolve()
    if (anchor is None) == (windows is None):
        raise RuntimeError("compressed_plan_regeneration_mode_invalid")
    if plan9_r1_retry and windows is None:
        raise RuntimeError("compressed_plan9_requires_explicit_windows")
    plan_path = core_root / PLAN_PATH
    old_plan_bytes = plan_path.read_bytes()
    old_plan_sha = hashlib.sha256(old_plan_bytes).hexdigest()
    old_plan = json.loads(old_plan_bytes.decode("utf-8"))
    if anchor is not None:
        anchor_utc = _parse_anchor(anchor)
        mode = "ANCHOR_SHIFT"
        new_plan_bytes, new_plan = _shift_plan(old_plan_bytes, anchor_utc)
    else:
        anchor_utc = None
        mode = "EXPLICIT_WINDOWS"
        explicit_windows = _parse_explicit_windows(windows or ())
        new_plan_bytes, new_plan = _replace_plan_windows(
            old_plan_bytes,
            explicit_windows,
            require_common_delta=False,
        )
    if plan9_r1_retry:
        new_plan_bytes, new_plan = _bind_plan9_r1_retry(new_plan_bytes)
        mode = "PLAN9_R1_RETRY"
    new_plan_sha = hashlib.sha256(new_plan_bytes).hexdigest()
    # Validate the complete candidate with the same production invariants used
    # by the runtime before either checkout receives a write.
    parse_compressed_plan(new_plan, sha256=new_plan_sha)

    expected_old_paths = {
        *(path.as_posix() for path in CORE_PIN_COUNTS),
        VECTOR_PATH.as_posix(),
        STALE_PREPARATION_BUNDLE.as_posix(),
        *(path.as_posix() for path in IMMUTABLE_HISTORICAL_SHA_PATHS),
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

    if plan9_r1_retry and not _is_plan9_retry(old_plan):
        _assert_plan9_delta(old_plan, new_plan)
    else:
        _assert_values_only(
            old_plan,
            new_plan,
            require_common_delta=mode == "ANCHOR_SHIFT",
        )
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
            allowed_historical = {
                path.as_posix() for path in IMMUTABLE_HISTORICAL_SHA_PATHS
            }
            old_sha_paths = _sha_occurrences(core_root, old_plan_sha)
            stale_web = _sha_occurrences(web_root, old_plan_sha)
            unexpected_old_paths = old_sha_paths - allowed_historical - {
                STALE_PREPARATION_BUNDLE.as_posix()
            }
            if unexpected_old_paths or stale_web:
                raise RuntimeError(
                    "compressed_plan_old_sha_remains_outside_stale_bundle"
                )
            stale_old_sha_paths = old_sha_paths & {
                STALE_PREPARATION_BUNDLE.as_posix()
            }
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
        mode=mode,
        anchor_utc=(
            _wire_timestamp(anchor_utc) if anchor_utc is not None else None
        ),
        applied_windows=tuple(
            (
                cycle_id,
                str(_cycle_map(new_plan)[cycle_id]["window_start"]),
                str(_cycle_map(new_plan)[cycle_id]["window_end"]),
            )
            for cycle_id in RUNNABLE_CYCLE_IDS
        ),
        shifted_cycle_ids=tuple(
            cycle_id
            for cycle_id in RUNNABLE_CYCLE_IDS
            if any(
                _cycle_map(old_plan)[cycle_id][field]
                != _cycle_map(new_plan)[cycle_id][field]
                for field in ("window_start", "window_end")
            )
        ),
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
    windows = {
        cycle_id: (
            _wire_timestamp(
                _timestamp(cycles[cycle_id]["window_start"]) + delta
            ),
            _wire_timestamp(
                _timestamp(cycles[cycle_id]["window_end"]) + delta
            ),
        )
        for cycle_id in RUNNABLE_CYCLE_IDS
    }
    return _replace_plan_windows(raw, windows, require_common_delta=True)


def _replace_plan_windows(
    raw: bytes,
    windows: dict[str, tuple[str, str]],
    *,
    require_common_delta: bool,
) -> tuple[bytes, dict[str, object]]:
    before = json.loads(raw.decode("utf-8"))
    cycles = _cycle_map(before)
    text = raw.decode("utf-8")
    replacements: list[tuple[str, str]] = []
    for cycle_id in RUNNABLE_CYCLE_IDS:
        cycle = cycles[cycle_id]
        for field, new_value in zip(
            ("window_start", "window_end"), windows[cycle_id], strict=True
        ):
            old_value = cycle[field]
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
    _assert_values_only(
        before,
        after,
        require_common_delta=require_common_delta,
    )
    return text.encode("utf-8"), after


def _bind_plan9_r1_retry(
    raw: bytes,
) -> tuple[bytes, dict[str, object]]:
    before = json.loads(raw.decode("utf-8"))
    if _is_plan9_retry(before):
        return raw, before
    if before.get("schema_version") != "2.4.0":
        raise RuntimeError("compressed_plan9_source_schema_invalid")
    cycles = _cycle_map(before)
    if cycles["c3"].get("epoch_label") != "PLAN6_R1_20":
        raise RuntimeError("compressed_plan9_source_epoch_invalid")
    if cycles["c4"].get("activation") != "PROVISIONAL_R1_GATED":
        raise RuntimeError("compressed_plan9_source_activation_invalid")
    text = raw.decode("utf-8")
    schema_needle = '"schema_version": "2.4.0"'
    epoch_needle = '"epoch_label": "PLAN6_R1_20"'
    c4_epoch_needle = '"epoch_label": "PLAN6_R2_80_PROVISIONAL"'
    activation_needle = '"activation": "PROVISIONAL_R1_GATED"'
    if (
        text.count(schema_needle) != 1
        or text.count(epoch_needle) != 1
        or text.count(c4_epoch_needle) != 1
        or text.count(activation_needle) != 3
    ):
        raise RuntimeError("compressed_plan9_source_occurrence_invalid")
    text = text.replace(schema_needle, '"schema_version": "2.6.0"', 1)
    text = text.replace(
        epoch_needle,
        f'"epoch_label": "{PLAN9_RETRY_EPOCH_LABEL}"',
        1,
    )
    text = text.replace(
        c4_epoch_needle,
        f'"epoch_label": "{PLAN9_C4_EPOCH_LABEL}"',
        1,
    )
    text = text.replace(activation_needle, '"activation": "ACTIVE"', 1)
    after = json.loads(text)
    _assert_plan9_delta(before, after)
    return text.encode("utf-8"), after


def _is_plan9_retry(value: dict[str, object]) -> bool:
    try:
        return (
            value.get("schema_version") == "2.6.0"
            and _cycle_map(value)["c3"].get("epoch_label")
            == PLAN9_RETRY_EPOCH_LABEL
            and _cycle_map(value)["c4"].get("activation") == "ACTIVE"
            and _cycle_map(value)["c4"].get("epoch_label")
            == PLAN9_C4_EPOCH_LABEL
        )
    except RuntimeError:
        return False


def _assert_plan9_delta(
    before: dict[str, object], after: dict[str, object]
) -> None:
    if before.get("schema_version") != "2.4.0":
        raise RuntimeError("compressed_plan9_source_schema_invalid")
    if not _is_plan9_retry(after):
        raise RuntimeError("compressed_plan9_retry_invalid")
    normalized = deepcopy(after)
    normalized["schema_version"] = before["schema_version"]
    normalized_cycles = _cycle_map(normalized)
    before_cycles = _cycle_map(before)
    normalized_cycles["c3"]["epoch_label"] = before_cycles["c3"][
        "epoch_label"
    ]
    normalized_cycles["c4"]["activation"] = before_cycles["c4"][
        "activation"
    ]
    normalized_cycles["c4"]["epoch_label"] = before_cycles["c4"][
        "epoch_label"
    ]
    _assert_values_only(before, normalized, require_common_delta=False)


def _assert_values_only(
    before: dict[str, object],
    after: dict[str, object],
    *,
    require_common_delta: bool,
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
    if require_common_delta and len(deltas) != 1:
        raise RuntimeError("compressed_plan_relative_windows_changed")

    before_without_cycles = {key: value for key, value in before.items() if key != "cycles"}
    after_without_cycles = {key: value for key, value in after.items() if key != "cycles"}
    if before_without_cycles != after_without_cycles:
        raise RuntimeError("compressed_plan_non_cycle_field_changed")


def _parse_explicit_windows(
    values: Sequence[tuple[str, str, str]],
) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for cycle_id, raw_start, raw_end in values:
        if cycle_id not in RUNNABLE_CYCLE_IDS or cycle_id in result:
            raise RuntimeError(
                f"compressed_plan_explicit_cycle_invalid:{cycle_id}"
            )
        start = _parse_canonical_utc(raw_start)
        end = _parse_canonical_utc(raw_end)
        result[cycle_id] = (
            _wire_timestamp(start),
            _wire_timestamp(end),
        )
    if set(result) != set(RUNNABLE_CYCLE_IDS):
        raise RuntimeError("compressed_plan_explicit_cycle_set_invalid")
    return result


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


def _parse_canonical_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise RuntimeError("compressed_plan_explicit_timestamp_invalid") from exc
    if (
        not value.endswith("Z")
        or parsed.tzinfo is None
        or parsed.microsecond
        or _wire_timestamp(parsed) != value
    ):
        raise RuntimeError("compressed_plan_explicit_timestamp_invalid")
    return parsed.astimezone(timezone.utc)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RuntimeError("compressed_plan_timestamp_invalid")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    return parsed.astimezone(timezone.utc)


def _wire_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
