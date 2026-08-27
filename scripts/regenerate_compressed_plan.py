from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from recall.testing.compressed_plan_regeneration import (  # noqa: E402
    regenerate_compressed_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--anchor")
    mode.add_argument(
        "--window",
        action="append",
        metavar="CYCLE=START/END",
        help="Repeat exactly once for each of c3, c4, c5, and c6.",
    )
    parser.add_argument("--web-root", type=Path, required=True)
    args = parser.parse_args()
    windows = None
    if args.window is not None:
        try:
            windows = tuple(_parse_window(value) for value in args.window)
        except ValueError as exc:
            parser.error(str(exc))
    result = regenerate_compressed_plan(
        ROOT,
        args.web_root,
        anchor=args.anchor,
        windows=windows,
    )
    print(json.dumps(result.to_wire(), indent=2, sort_keys=True))
    return 0


def _parse_window(value: str) -> tuple[str, str, str]:
    try:
        cycle_id, interval = value.split("=", 1)
        start, end = interval.split("/", 1)
    except ValueError as exc:
        raise ValueError("window must use CYCLE=START/END") from exc
    if not cycle_id or not start or not end:
        raise ValueError("window must use CYCLE=START/END")
    return cycle_id, start, end


if __name__ == "__main__":
    raise SystemExit(main())
