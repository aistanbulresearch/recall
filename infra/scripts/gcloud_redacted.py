"""Run a gcloud command and redact BOTH streams, unconditionally.

Written because I leaked the project id into a session transcript four times in
two days, and the pattern was identical every time: I piped the command I
expected to print through a redaction, and the command that FAILED printed
unredacted. Error paths are exactly the ones that carry resource names, and
exactly the ones a per-command redaction forgets — four for four.

Per-command redaction is the wrong layer. This is the invocation layer: every
call through here gets stdout and stderr redacted whether it succeeds or not,
so an error path cannot be the one that was overlooked.

    python infra/scripts/gcloud_redacted.py run jobs list --region=us-central1
    python infra/scripts/gcloud_redacted.py scheduler jobs describe <name> ...

The exit code is passed through faithfully. A wrapper that swallowed exit codes
in order to tidy output would be this project's own recurring defect wearing a
helper's clothes: the caller must still be able to tell success from failure,
and `$?` is how they do it.

Nothing here is a fallback. If gcloud cannot be found, or the project cannot be
resolved, it fails loudly rather than running unredacted or guessing — a
redactor that silently redacts nothing is worse than no redactor, because the
caller believes they are protected.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from recall.platform.redaction import redact_identifiers  # noqa: E402

# Read from the gcloud configuration file rather than by running gcloud: the
# `config get-value project` call is the one that hung for hours when
# credentials lapsed, and this helper wraps calls that are already on a
# milestone path. A call that never happens cannot hang.
CONFIG_PROJECT = re.compile(r"^\s*project\s*=\s*(\S+)\s*$", re.MULTILINE)
# The active account is masked too. The owner's constraint names it beside the
# project id ("proje ID, billing ID, hesap e-postasi, token degeri"), and the
# first test of this helper printed it in a gcloud error — the redactor built
# to stop leaks demonstrated a second leak class while proving it worked.
# Only the HUMAN account is masked, not every address: service-account emails
# are resource names whose project half is already redacted, and masking them
# would hide which principal a binding names.
CONFIG_ACCOUNT = re.compile(r"^\s*account\s*=\s*(\S+)\s*$", re.MULTILINE)


def _config_text() -> str:
    import os

    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise SystemExit("gcloud_redacted_no_appdata")
    config = Path(appdata) / "gcloud" / "configurations" / "config_default"
    if not config.exists():
        raise SystemExit(f"gcloud_redacted_no_config:{config}")
    return config.read_text(encoding="utf-8", errors="replace")


def resolve_project() -> str:
    match = CONFIG_PROJECT.search(_config_text())
    if not match:
        raise SystemExit("gcloud_redacted_project_unresolved")
    return match.group(1)


def resolve_account() -> str | None:
    match = CONFIG_ACCOUNT.search(_config_text())
    return match.group(1) if match else None


def scrub(text: str, project: str, number: str | None, account: str | None) -> str:
    """Mask the project id, the project number, and long bare digit runs.

    The project NUMBER is masked explicitly rather than relying on the digit-run
    heuristic, because the heuristic is a net and a net has holes. Both are
    applied: the specific value first, the net second.
    """

    masked = redact_identifiers(text, project)
    if number:
        masked = masked.replace(number, "<project-number>")
    if account:
        masked = masked.replace(account, "<account>")
    return masked


def main() -> int:
    args = sys.argv[1:]
    if not args:
        raise SystemExit("usage: gcloud_redacted.py <gcloud args...>")

    exe = shutil.which("gcloud")
    if not exe:
        raise SystemExit("gcloud_redacted_executable_not_found")

    project = resolve_project()
    account = resolve_account()

    # The number is best-effort: if it cannot be read, the id is still masked and
    # the digit-run net still applies. Its absence is reported on stderr rather
    # than passing silently, so a partial redaction is never mistaken for a full
    # one.
    number = None
    probe = subprocess.run(
        [exe, "projects", "describe", project, "--format=value(projectNumber)"],
        capture_output=True, text=True, timeout=120,
    )
    if probe.returncode == 0:
        number = probe.stdout.strip() or None
    if not number:
        print("gcloud_redacted: project number unresolved; id masked, number by heuristic only",
              file=sys.stderr)

    result = subprocess.run([exe, *args], capture_output=True, text=True)
    if result.stdout:
        sys.stdout.write(scrub(result.stdout, project, number, account))
    if result.stderr:
        sys.stderr.write(scrub(result.stderr, project, number, account))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
