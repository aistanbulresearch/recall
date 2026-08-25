"""Measure whether a lane branch actually lands on the integration target.

A merge that exits 0 is not evidence that the merge brought the work. When a
branch has been merged and then REVERTED on the target, git treats those commits
as already applied: re-merging restores nothing, reports success, and the tests
that would have caught the absence were deleted along with the source they test.
That is a check that cannot fire reporting success, and on 2026-08-25 it would
have produced an M1 branch documenting a running gateway whose Dockerfile,
build config and server entrypoint were not in the repository.

So this asks three questions where the obvious check asks one:

    1. does the merge complete cleanly?
    2. is every file from the lane branch actually PRESENT afterwards?
    3. do the RESTORED files match the lane byte for byte?

Question 2 is the one that matters most, and it is the one a green merge hides.
Question 3 closes the smaller version of the same gap: a file restored with the
wrong bytes is as much a fiction as an absent one.

Everything happens in a throwaway worktree on a throwaway branch. Neither the
lane branch nor the integration target is modified, and the worktree is removed
whether the run succeeds or fails.

    python infra/scripts/verify_integration_merge.py \
        --lane feature/l1-platform --target feature/rcl-3xx-core
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
SCRATCH_BRANCH = "integration-merge-probe"

# Paths this lane is responsible for. A file outside these is another lane's to
# check; claiming otherwise would report a coverage we do not have.
LANE_PREFIXES = (
    "infra/",
    "tests/platform/",
    "src/recall/platform/",
    "artifacts/evidence/gateway",
    "artifacts/evidence/fleet",
)


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    exe = shutil.which("git")
    if not exe:
        raise SystemExit("executable_not_found:git")
    return subprocess.run(
        [exe, *args], cwd=str(cwd or REPO), capture_output=True, text=True, timeout=300
    )


def lane_files(lane: str) -> list[str]:
    listing = git("ls-tree", "-r", "--name-only", lane).stdout.splitlines()
    return [f for f in listing if f.startswith(LANE_PREFIXES)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", default="feature/l1-platform")
    parser.add_argument("--target", default="feature/rcl-3xx-core")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    expected = lane_files(args.lane)
    base = git("merge-base", args.lane, args.target).stdout.strip()
    workdir = Path(tempfile.mkdtemp(prefix="recall_mergeprobe_"))
    result: dict[str, Any] = {
        "probe": "integration_merge",
        "lane": args.lane,
        "lane_head": git("rev-parse", "--short", args.lane).stdout.strip(),
        "target": args.target,
        "target_head": git("rev-parse", "--short", args.target).stdout.strip(),
        "merge_base": base[:12],
        "lane_files_expected": len(expected),
    }

    try:
        git("branch", "-f", SCRATCH_BRANCH, args.target)
        git("worktree", "add", str(workdir), SCRATCH_BRANCH)

        merged = git(
            "-c", "user.name=probe", "-c", "user.email=probe@invalid",
            "merge", "--no-edit", args.lane, cwd=workdir,
        )
        result["merge_exit"] = merged.returncode
        result["merge_clean"] = merged.returncode == 0
        conflicts = [
            line for line in merged.stdout.splitlines() if line.startswith("CONFLICT")
        ]
        result["conflicts"] = conflicts

        # Present-after-merge is checked even when the merge conflicted, because
        # the interesting failure is a file that is missing REGARDLESS.
        missing = [f for f in expected if not (workdir / f).exists()]
        result["files_present_after_merge"] = len(expected) - len(missing)
        result["files_missing_after_merge"] = missing

        # Of the missing, which ones a plain merge can never restore: their last
        # change is at or before the merge base, so git considers them applied.
        unrecoverable = []
        for path in missing:
            last = git("log", "--format=%H", "-1", args.lane, "--", path).stdout.strip()
            if last and git("merge-base", "--is-ancestor", last, base).returncode == 0:
                unrecoverable.append(path)
        result["unrecoverable_without_revert_of_revert"] = unrecoverable

        # Content, not just presence. A file restored with the wrong bytes is as
        # much a fiction as an absent one -- the same failure wearing a smaller
        # coat. Compared only for the RESTORED set: files the target did not
        # have before the merge, so the lane is the only source and the blob
        # must match exactly. Files the target ALSO modified are excluded on
        # purpose -- there a merged result differing from the lane is correct,
        # and flagging it would be a false alarm that trains people to ignore
        # the check.
        restored = [
            f
            for f in expected
            if f not in missing
            and git("cat-file", "-e", f"{args.target}:{f}").returncode != 0
        ]
        mismatched = []
        hash_checked = 0
        if result["merge_clean"]:
            # A clean merge leaves a commit, so tree blobs can be compared
            # directly. That sidesteps working-tree line-ending filters, which
            # would otherwise make every CRLF file look modified.
            for f in restored:
                lane_blob = git("rev-parse", f"{args.lane}:{f}").stdout.strip()
                merged_blob = git("rev-parse", f"HEAD:{f}", cwd=workdir).stdout.strip()
                hash_checked += 1
                if not lane_blob or lane_blob != merged_blob:
                    mismatched.append({"path": f, "lane": lane_blob[:12], "merged": merged_blob[:12]})
        result["restored_files"] = len(restored)
        result["blobs_checked"] = hash_checked
        result["blobs_matching_lane"] = hash_checked - len(mismatched)
        result["blob_mismatches"] = mismatched
        result["blob_check_skipped_reason"] = (
            None if result["merge_clean"] else "merge conflicted; no merge commit to compare"
        )

        result["verdict"] = (
            "GREEN"
            if result["merge_clean"] and not missing and not mismatched
            else "RED"
        )
        result["why"] = (
            "merge completed and every lane file is present"
            if result["verdict"] == "GREEN"
            else "; ".join(
                filter(None, [
                    f"{len(conflicts)} conflict(s)" if conflicts else "",
                    f"{len(missing)} lane file(s) absent after merge" if missing else "",
                    (
                        f"{len(unrecoverable)} of them cannot be restored by any "
                        "re-merge until the revert is reverted on the target"
                    ) if unrecoverable else "",
                    (
                        f"{len(mismatched)} restored file(s) do not match the lane byte for byte"
                    ) if mismatched else "",
                ])
            )
        )
    finally:
        git("merge", "--abort", cwd=workdir)
        git("worktree", "remove", "--force", str(workdir))
        git("branch", "-D", SCRATCH_BRANCH)
        result["cleanup"] = {
            "worktree_removed": not workdir.exists(),
            "scratch_branch_removed": SCRATCH_BRANCH
            not in git("branch", "--list", SCRATCH_BRANCH).stdout,
        }

    rendered = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0 if result["verdict"] == "GREEN" else 1


if __name__ == "__main__":
    sys.exit(main())
