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
    parser.add_argument("--anchor", required=True)
    parser.add_argument("--web-root", type=Path, required=True)
    args = parser.parse_args()
    result = regenerate_compressed_plan(
        ROOT,
        args.web_root,
        anchor=args.anchor,
    )
    print(json.dumps(result.to_wire(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
