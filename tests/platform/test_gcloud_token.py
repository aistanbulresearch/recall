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


# --- Get-RecallProject: the milestone-path call that must never launch gcloud ---

CONFIG_WITH_PROJECT = "[core]\nproject = recall-example-0000\n"
CONFIG_WITHOUT_PROJECT = "[core]\naccount = someone\n"


def _run_project(
    expression: str, project_env: str = ""
) -> subprocess.CompletedProcess[str]:
    """Evaluate a Get-RecallProject expression and report what it did."""

    script = (
        f". '{HELPER}'; "
        f"$env:RECALL_GCP_PROJECT = '{project_env}'; "
        "try { "
        f'  Write-Output "OK:$({expression})" '
        "} catch { "
        '  Write-Output "ERROR:$($_.Exception.Message)" '
        "}"
    )
    return subprocess.run(
        [*POWERSHELL, script], capture_output=True, text=True, timeout=120
    )


def test_project_is_read_from_the_config_file(tmp_path: Path) -> None:
    config = tmp_path / "config_default"
    config.write_text(CONFIG_WITH_PROJECT, encoding="utf-8")
    out = _run_project(f"Get-RecallProject -ConfigPath '{config}'")
    assert "OK:recall-example-0000" in out.stdout


def test_the_environment_variable_wins(tmp_path: Path) -> None:
    config = tmp_path / "config_default"
    config.write_text("[core]\nproject = from-file\n", encoding="utf-8")
    out = _run_project(
        f"Get-RecallProject -ConfigPath '{config}'", project_env="from-env"
    )
    assert "OK:from-env" in out.stdout


def test_a_missing_config_file_throws_rather_than_returning_empty(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "not_here"
    out = _run_project(f"Get-RecallProject -ConfigPath '{missing}'")
    assert "ERROR:recall_project_config_missing" in out.stdout


def test_a_config_without_a_project_throws(tmp_path: Path) -> None:
    config = tmp_path / "config_default"
    config.write_text(CONFIG_WITHOUT_PROJECT, encoding="utf-8")
    out = _run_project(f"Get-RecallProject -ConfigPath '{config}'")
    assert "ERROR:recall_project_unresolved" in out.stdout


def test_resolving_the_project_launches_no_gcloud(tmp_path: Path) -> None:
    """The whole point: this path starts no gcloud, so it cannot hang.

    Tested by putting a marker-writing stub first on PATH. If the resolver ever
    shells out to gcloud, the marker appears.

    An earlier version compared @(Get-Process).Count before and after, which is
    racy: any unrelated process starting on the machine during the window flips
    it. That test passed on one checkout and failed on another for reasons that
    had nothing to do with the code, which is precisely the failure mode this
    file is being corrected for.
    """

    config = tmp_path / "config_default"
    config.write_text(CONFIG_WITH_PROJECT, encoding="utf-8")
    marker = tmp_path / "gcloud-was-called.txt"
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    (stub_dir / "gcloud.cmd").write_text(
        "@echo off\r\n" + f'echo called > "{marker}"\r\n' + "exit /b 0\r\n",
        encoding="utf-8",
    )
    script = (
        f". '{HELPER}'; "
        "$env:RECALL_GCP_PROJECT = ''; "
        f"$env:PATH = '{stub_dir}' + [IO.Path]::PathSeparator + $env:PATH; "
        f"Write-Output \"OK:$(Get-RecallProject -ConfigPath '{config}')\""
    )
    out = subprocess.run(
        [*POWERSHELL, script], capture_output=True, text=True, timeout=120
    )
    assert "OK:recall-example-0000" in out.stdout
    assert not marker.exists(), "resolving the project invoked gcloud"


# --- degenerate inputs: the shapes an expired or half-written config produces ---
#
# These failed cross-environment on 2026-08-24 with "Cannot index into a null
# array". The failure did not reproduce on the authoring machine, which is the
# point: a test whose result depends on machine state is not evidence. Every
# input below is written by the test itself, so the outcome cannot vary with
# whose gcloud configuration happens to be on disk.


def test_an_empty_config_file_reports_unresolved(tmp_path: Path) -> None:
    config = tmp_path / "config_default"
    config.write_text("", encoding="utf-8")
    out = _run_project(f"Get-RecallProject -ConfigPath '{config}'")
    assert "ERROR:recall_project_unresolved" in out.stdout


def test_a_whitespace_only_config_reports_unresolved(tmp_path: Path) -> None:
    config = tmp_path / "config_default"
    config.write_text("\n\n   \n", encoding="utf-8")
    out = _run_project(f"Get-RecallProject -ConfigPath '{config}'")
    assert "ERROR:recall_project_unresolved" in out.stdout


def test_a_single_line_config_resolves(tmp_path: Path) -> None:
    """One line makes Get-Content return a string, not an array.

    The scalar and array shapes take different paths through PowerShell's
    matching, so both are covered rather than whichever the author happened
    to write first.
    """

    config = tmp_path / "config_default"
    config.write_text("project = solo-value\n", encoding="utf-8")
    out = _run_project(f"Get-RecallProject -ConfigPath '{config}'")
    assert "OK:solo-value" in out.stdout


def test_a_multi_line_config_resolves(tmp_path: Path) -> None:
    config = tmp_path / "config_default"
    config.write_text(
        "[core]\naccount = someone\nproject = multi-value\n", encoding="utf-8"
    )
    out = _run_project(f"Get-RecallProject -ConfigPath '{config}'")
    assert "OK:multi-value" in out.stdout


def test_crlf_line_endings_resolve(tmp_path: Path) -> None:
    config = tmp_path / "config_default"
    config.write_bytes(b"[core]\r\nproject = crlf-value\r\n")
    out = _run_project(f"Get-RecallProject -ConfigPath '{config}'")
    assert "OK:crlf-value" in out.stdout


def test_a_commented_project_line_is_not_matched(tmp_path: Path) -> None:
    config = tmp_path / "config_default"
    config.write_text("# project = commented-out\n", encoding="utf-8")
    out = _run_project(f"Get-RecallProject -ConfigPath '{config}'")
    assert "ERROR:recall_project_unresolved" in out.stdout


def test_the_first_project_line_wins(tmp_path: Path) -> None:
    config = tmp_path / "config_default"
    config.write_text("project = first\nproject = second\n", encoding="utf-8")
    out = _run_project(f"Get-RecallProject -ConfigPath '{config}'")
    assert "OK:first" in out.stdout


# --- empty command output: what an expired credential actually produces -------


def test_empty_stdout_is_refused_rather_than_returned(tmp_path: Path) -> None:
    """A credential that has lapsed can exit zero and print nothing.

    An empty token is not a token. Returning it would send an Authorization
    header of "Bearer " and turn a credential failure into a puzzling 401 much
    further away from the cause.
    """

    stub = tmp_path / "gcloud.cmd"
    stub.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
    result = _run_helper(stub, timeout_seconds=15)
    assert "ERROR:recall_token_empty" in result.stdout


def test_whitespace_only_stdout_is_refused(tmp_path: Path) -> None:
    stub = tmp_path / "gcloud.cmd"
    stub.write_text("@echo off\r\necho.\r\nexit /b 0\r\n", encoding="utf-8")
    result = _run_helper(stub, timeout_seconds=15)
    assert "ERROR:recall_token_empty" in result.stdout


def test_nonzero_exit_with_no_output_maps_to_auth_failed(tmp_path: Path) -> None:
    """Exit code decides, not the emptiness of the output."""

    stub = tmp_path / "gcloud.cmd"
    stub.write_text("@echo off\r\nexit /b 1\r\n", encoding="utf-8")
    result = _run_helper(stub, timeout_seconds=15)
    assert "ERROR:recall_token_auth_failed:1" in result.stdout
