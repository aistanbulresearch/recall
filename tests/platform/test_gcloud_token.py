"""Tests for the bounded access-token helper in infra/scripts/gcloud_token.ps1.

The helper is PowerShell because the scripts that need it are. It is exercised
here through real PowerShell runs against stub executables, so the timeout path
is measured rather than asserted: a stub that never returns stands in for the
gcloud call that was still running after 49 hours on 2026-08-23.

No real credential is involved. The stubs are batch files created per test.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "infra" / "scripts" / "gcloud_token.ps1"

# Execution policy on this machine is Restricted, so a .ps1 cannot be dot-sourced
# without an explicit bypass. This mirrors how the infra scripts are actually
# invoked; without it the dot-source fails and every function looks undefined.
POWERSHELL = (
    "powershell",
    "-NoProfile",
    "-NonInteractive",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
)

# A stub that never finishes on its own, standing in for the call that hung.
HANGING_STUB = "@echo off\r\nping -n 240 127.0.0.1 >nul\r\nexit /b 0\r\n"

pytestmark = pytest.mark.skipif(
    shutil.which("powershell") is None, reason="powershell is not available"
)


def _run_helper(
    stub: Path, timeout_seconds: int, wait: int = 120
) -> subprocess.CompletedProcess[str]:
    """Call Get-RecallAccessToken against a stub and report what it did."""

    script = (
        f". '{HELPER}'; "
        "try { "
        f"  $t = Get-RecallAccessToken -TimeoutSeconds {timeout_seconds} "
        f"-GcloudPath '{stub}'; "
        '  Write-Output "TOKEN:$t" '
        "} catch { "
        '  Write-Output "ERROR:$($_.Exception.Message)" '
        "}"
    )
    return subprocess.run(
        [*POWERSHELL, script],
        capture_output=True,
        text=True,
        timeout=wait,
        check=False,
    )


def _stub(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="ascii")
    return path


def _ping_count() -> int:
    """Count PING.EXE by process name.

    Counting by command line does not work here: the query string itself
    contains the pattern, so the querying process matches its own filter and the
    check reports survivors that are only itself.
    """

    result = subprocess.run(
        [*POWERSHELL, "@(Get-Process -Name PING -ErrorAction SilentlyContinue).Count"],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    return int(result.stdout.strip() or 0)


def test_a_prompt_token_is_returned(tmp_path: Path) -> None:
    stub = _stub(
        tmp_path, "fast.cmd", "@echo off\r\necho ya29.stub-token\r\nexit /b 0\r\n"
    )
    result = _run_helper(stub, timeout_seconds=15)
    assert "TOKEN:ya29.stub-token" in result.stdout, result.stdout + result.stderr


def test_a_hanging_call_is_cut_off_at_the_limit(tmp_path: Path) -> None:
    """The measured defect: a call that never returns must not wait forever."""

    stub = _stub(tmp_path, "hang.cmd", HANGING_STUB)
    started = time.monotonic()
    result = _run_helper(stub, timeout_seconds=3)
    elapsed = time.monotonic() - started

    assert "ERROR:recall_token_timeout:3" in result.stdout, (
        result.stdout + result.stderr
    )
    assert "TOKEN:" not in result.stdout, "a timed-out call must not yield a token"
    # Generous upper bound: the claim is that the call is bounded, not that
    # PowerShell startup is fast.
    assert elapsed < 45, f"helper took {elapsed:.1f}s for a 3s limit"


def test_a_hanging_call_leaves_no_grandchild_behind(tmp_path: Path) -> None:
    """Stopping only the launched process would leave the real child running.

    The stub's long-running work is a ping one level below the .cmd, the same
    shape as gcloud.cmd spawning python. That python child is what survived for
    49 hours when the parent was abandoned.
    """

    before = _ping_count()
    stub = _stub(tmp_path, "hangprobe.cmd", HANGING_STUB)
    result = _run_helper(stub, timeout_seconds=3)
    assert "recall_token_timeout" in result.stdout, result.stdout

    time.sleep(3)
    after = _ping_count()
    assert after <= before, (
        f"ping processes went from {before} to {after}: the timed-out call left "
        "a grandchild running"
    )


def test_a_refusing_gcloud_is_an_auth_failure_not_a_timeout(tmp_path: Path) -> None:
    stub = _stub(
        tmp_path, "refuse.cmd", "@echo off\r\necho no credentials 1>&2\r\nexit /b 1\r\n"
    )
    result = _run_helper(stub, timeout_seconds=15)
    assert "ERROR:recall_token_auth_failed:1" in result.stdout, result.stdout


def test_the_two_failure_paths_report_different_codes(tmp_path: Path) -> None:
    refusing = _stub(tmp_path, "r2.cmd", "@echo off\r\nexit /b 1\r\n")
    hanging = _stub(tmp_path, "h2.cmd", HANGING_STUB)
    auth = _run_helper(refusing, timeout_seconds=15).stdout
    timed_out = _run_helper(hanging, timeout_seconds=3).stdout
    assert "recall_token_auth_failed" in auth
    assert "recall_token_timeout" in timed_out
    assert "recall_token_timeout" not in auth
    assert "recall_token_auth_failed" not in timed_out


def test_an_empty_token_is_not_a_clean_token(tmp_path: Path) -> None:
    stub = _stub(tmp_path, "blank.cmd", "@echo off\r\nexit /b 0\r\n")
    result = _run_helper(stub, timeout_seconds=15)
    assert "ERROR:recall_token_empty" in result.stdout, result.stdout
    assert "TOKEN:" not in result.stdout


def test_a_nonpositive_limit_is_refused(tmp_path: Path) -> None:
    stub = _stub(tmp_path, "any.cmd", "@echo off\r\necho tok\r\nexit /b 0\r\n")
    result = _run_helper(stub, timeout_seconds=0)
    assert "ERROR:recall_token_timeout_invalid:0" in result.stdout, result.stdout


def test_the_tree_stopper_refuses_system_process_ids() -> None:
    """The near-miss this guard exists for: a null id walked pid 0's children."""

    script = (
        f". '{HELPER}'; "
        'Write-Output "null:$(Stop-RecallProcessTree -RootId $null)"; '
        'Write-Output "zero:$(Stop-RecallProcessTree -RootId 0)"; '
        'Write-Output "four:$(Stop-RecallProcessTree -RootId 4)"'
    )
    result = subprocess.run(
        [*POWERSHELL, script],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert "null:0" in result.stdout, result.stdout + result.stderr
    assert "zero:0" in result.stdout, result.stdout
    assert "four:0" in result.stdout, result.stdout
