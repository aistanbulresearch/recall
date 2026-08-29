from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from recall.scheduler.compressed_plan import PLAN_PATH
from recall.scheduler.compressed_preparation import DEFAULT_COMPRESSED_BUNDLE_PATH
from recall.testing.compressed_final_only_regeneration import (
    FinalOnlyHistoricalInput,
    render_final_only_candidate,
    render_final_only_preparation_candidate,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--historical-evidence", type=Path, required=True)
    parser.add_argument("--c6-window-start", required=True)
    parser.add_argument("--c6-window-end", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-bundle", type=Path)
    parser.add_argument("--prepared-at")
    parser.add_argument("--bundle-output", type=Path)
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    evidence = json.loads(args.historical_evidence.resolve().read_bytes())
    if not isinstance(evidence, list):
        raise RuntimeError("final_only_evidence_file_invalid")
    result = render_final_only_candidate(
        (root / PLAN_PATH).read_bytes(),
        historical_evidence=tuple(
            FinalOnlyHistoricalInput(**item) for item in evidence
        ),
        c6_window_start=args.c6_window_start,
        c6_window_end=args.c6_window_end,
    )
    preparation_args = (
        args.source_bundle,
        args.prepared_at,
        args.bundle_output,
    )
    if any(item is not None for item in preparation_args) and any(
        item is None for item in preparation_args
    ):
        raise RuntimeError("final_only_preparation_arguments_incomplete")
    preparation = None
    if args.source_bundle is not None:
        preparation = render_final_only_preparation_candidate(
            args.source_bundle.resolve().read_bytes(),
            plan_candidate=result,
            prepared_at=args.prepared_at,
        )
    if args.output is not None:
        output = args.output.resolve()
        if output == (root / PLAN_PATH).resolve():
            raise RuntimeError("final_only_production_apply_forbidden")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(result.plan_bytes)
    if preparation is not None:
        bundle_output = args.bundle_output.resolve()
        if bundle_output == (root / DEFAULT_COMPRESSED_BUNDLE_PATH).resolve():
            raise RuntimeError("final_only_production_apply_forbidden")
        bundle_output.parent.mkdir(parents=True, exist_ok=True)
        bundle_output.write_bytes(preparation.bundle_bytes)
    print(
        json.dumps(
            {
                "mode": "FINAL_ONLY_CANDIDATE_ONLY",
                "plan_sha256": result.plan_sha256,
                "output": None if args.output is None else str(args.output.resolve()),
                "preparation_bundle_sha256": (
                    None if preparation is None else preparation.bundle_sha256
                ),
                "preparation_output": (
                    None
                    if preparation is None
                    else str(args.bundle_output.resolve())
                ),
                "source_material_sha256": (
                    None
                    if preparation is None
                    else preparation.source_material_sha256
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
