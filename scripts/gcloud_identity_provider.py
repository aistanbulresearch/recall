"""Per-request bearer-token provider for the managed Gemma endpoint.

L1's decision (2026-08-27, Vertex pivot): the Vertex endpoint admits by IAM
with an ACCESS token (not an ID token), Ollama itself has no auth, so the
bearer is the single gate. The runner is a local human ADC account, therefore
the token is minted by `gcloud auth print-access-token` as a SUBPROCESS PER
REQUEST: no caching, no expiry arithmetic, no refresh state. A fresh token per
call is a couple of seconds against model calls measured in minutes, and it
removes the entire class of stale-credential mid-run failures.

This module is run-side: it owns identity so the transport does not. It is
injected into `OllamaChatTransport(auth_header_provider=...)`, whose manifest
reports auth as a boolean only. Errors carry gcloud's stderr, never a token.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Mapping

_TIMEOUT_SECONDS = 30.0


def _gcloud_executable() -> str:
    # On Windows the entrypoint is gcloud.cmd; shutil.which resolves whichever
    # form this machine has rather than hardcoding one platform's name.
    for candidate in ("gcloud", "gcloud.cmd"):
        found = shutil.which(candidate)
        if found:
            return found
    raise RuntimeError("gcloud_not_found_on_path")


def access_token_header() -> Mapping[str, str]:
    """Mint a fresh access token and shape it as the Authorization header.

    Called once per model request by the transport. Raises rather than
    returning an empty header: an unauthenticated call to an IAM-only service
    is a guaranteed 401/403, and failing loudly here names the actual problem.
    """

    executable = _gcloud_executable()
    try:
        completed = subprocess.run(
            [executable, "auth", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("gcloud_access_token_timeout") from error
    if completed.returncode != 0:
        # stderr may say "Reauthentication required" etc. It never contains a
        # token, so it is safe to surface; the token itself never reaches an
        # error message or a log.
        detail = (completed.stderr or "").strip()[:200]
        raise RuntimeError(f"gcloud_access_token_failed: {detail}")
    token = completed.stdout.strip()
    if not token:
        raise RuntimeError("gcloud_access_token_empty")
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    """Self-test: mint one token and report shape only, never content."""

    header = access_token_header()
    value = header["Authorization"]
    print(f"minted: Bearer <{len(value) - 7} chars>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
