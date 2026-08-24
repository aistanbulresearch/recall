"""Discriminate a harness defect from a helper defect on the hang path.

On 2026-08-24 three tests failed in another process tree with
subprocess.TimeoutExpired at pytest's 120s limit, while passing here. The
tempting reading is "the helper never returned". That is not what
TimeoutExpired says. It says PYTHON'S READ NEVER SAW EOF, which is a different
claim: the hanging stub spawns `ping` as a grandchild, and if that grandchild
inherits PowerShell's stdout handle then the pipe stays open after PowerShell
has already exited. The helper can have returned correctly and on time.

This script separates the two before anyone changes code, by making the helper
report through a channel that does not depend on the pipe at all: a file.

    probe 1  stdout through a PIPE      (how the failing tests read it)
    probe 2  stdout redirected to FILES (no pipe for a grandchild to hold)

Verdict:
    timed out, outcome file complete  -> HARNESS defect: fix the test's reader
    timed out, outcome file empty     -> HELPER defect: fix the kill path
    never timed out                   -> not reproduced in this environment

Run it in the environment where the three tests fail. It creates nothing
outside its own temporary directory and starts no cloud call.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "infra" / "scripts" / "gcloud_token.ps1"

# The stub that never finishes on its own, standing in for the call that hung.
HANGING_STUB = "@echo off\r\nping -n 240 127.0.0.1 >nul\r\nexit /b 0\r\n"

HELPER_TIMEOUT_SECONDS = 5
PYTHON_TIMEOUT_SECONDS = 60


def _script(stub: Path, outcome: Path) -> str:
    """Call the helper and record the result to a file, not to stdout.

    The file write is the whole point: it survives a pipe that never closes.
    """

    return (
        f". '{HELPER}'; "
        "$verdict = ''; "
        "try { "
        f"  $t = Get-RecallAccessToken -TimeoutSeconds {HELPER_TIMEOUT_SECONDS} "
        f"-GcloudPath '{stub}'; "
        '  $verdict = "TOKEN:$t" '
        "} catch { "
        '  $verdict = "ERROR:$($_.Exception.Message)" '
        "} "
        f"Set-Content -LiteralPath '{outcome}' -Value $verdict -Encoding UTF8; "
        "Write-Output $verdict"
    )


def _powershell(script: str) -> list[str]:
    return [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    ]


def _probe(label: str, workdir: Path, use_pipe: bool) -> dict:
    stub = workdir / f"hang_{label}.cmd"
    stub.write_text(HANGING_STUB, encoding="utf-8")
    outcome = workdir / f"outcome_{label}.txt"
    cmd = _powershell(_script(stub, outcome))

    started = time.monotonic()
    timed_out = False
    if use_pipe:
        try:
            subprocess.run(
                cmd, capture_output=True, text=True, timeout=PYTHON_TIMEOUT_SECONDS
            )
        except subprocess.TimeoutExpired:
            timed_out = True
    else:
        out_file = workdir / f"stdout_{label}.txt"
        err_file = workdir / f"stderr_{label}.txt"
        with out_file.open("w") as o, err_file.open("w") as e:
            try:
                subprocess.run(
                    cmd, stdout=o, stderr=e, timeout=PYTHON_TIMEOUT_SECONDS
                )
            except subprocess.TimeoutExpired:
                timed_out = True
    elapsed = time.monotonic() - started

    # Give a completing helper a moment to flush before reading its report.
    if not outcome.exists():
        time.sleep(1.0)
    # utf-8-sig, not utf-8: Set-Content -Encoding UTF8 on PowerShell 5.1 writes a
    # BOM, and a stray ﻿ both corrupts the comparison and crashes printing
    # on a non-UTF-8 console. This is the same BOM that spoiled a secret version
    # earlier in the project; the encoding a writer picks is part of its output.
    recorded = (
        outcome.read_text(encoding="utf-8-sig").strip() if outcome.exists() else ""
    )

    return {
        "probe": label,
        "channel": "pipe" if use_pipe else "file",
        "python_timed_out": timed_out,
        "seconds": round(elapsed, 1),
        "helper_outcome": recorded or "<none>",
        "helper_completed": bool(recorded),
    }


def main() -> int:
    print(f"helper:          {HELPER}")
    print(f"helper timeout:  {HELPER_TIMEOUT_SECONDS}s")
    print(f"python timeout:  {PYTHON_TIMEOUT_SECONDS}s")
    print()

    with tempfile.TemporaryDirectory(prefix="recall_hang_") as tmp:
        workdir = Path(tmp)
        results = [
            _probe("pipe", workdir, use_pipe=True),
            _probe("file", workdir, use_pipe=False),
        ]

    for r in results:
        print(
            f"{r['probe']:<6} channel={r['channel']:<4} "
            f"timed_out={str(r['python_timed_out']):<5} "
            f"{r['seconds']:>6}s  helper_outcome={r['helper_outcome']}"
        )
    print()

    pipe = results[0]
    if not pipe["python_timed_out"]:
        print("VERDICT: NOT REPRODUCED here -- the pipe read returned normally.")
        return 0
    if pipe["helper_completed"]:
        print(
            "VERDICT: HARNESS defect. The helper completed and recorded "
            f"{pipe['helper_outcome']!r}, but Python's pipe read never saw EOF. "
            "A grandchild is holding the stdout handle; fix the test's reader, "
            "not the helper."
        )
        return 0
    print(
        "VERDICT: HELPER defect. Nothing was recorded, so the helper itself "
        "did not reach its own catch block. Investigate the kill path."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
