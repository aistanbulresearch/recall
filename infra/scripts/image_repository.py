"""Create, verify, and remove the lane's Docker image repository.

    python infra/scripts/image_repository.py create --redact
    python infra/scripts/image_repository.py verify --redact
    python infra/scripts/image_repository.py destroy --redact

Owner-approved on 2026-08-24 as a persistent resource: one Docker format
repository named recall-images in us-central1, holding the internal Tool Gateway
image.

`verify` reads the repository back rather than trusting the create call, and
fails if the format is not DOCKER or the lane labels are absent, so a repository
that exists under the wrong shape is a finding rather than a pass.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from recall.platform.config import PlatformConfig, resource_labels  # noqa: E402
from recall.platform.errors import PlatformError  # noqa: E402
from recall.platform.redaction import redact_identifiers  # noqa: E402

logger = logging.getLogger("recall.platform.registry")

REPOSITORY_ID = "recall-images"
REPOSITORY_COMPONENT = "image-registry"
REQUIRED_FORMAT = "DOCKER"
BASE = "https://artifactregistry.googleapis.com/v1"
# Create is asynchronous; these bound the wait for it to become readable.
CREATE_ATTEMPTS = 10
CREATE_INTERVAL_SECONDS = 6


def _session() -> Any:
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise PlatformError("registry_sdk_unavailable", str(exc)) from exc
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return AuthorizedSession(credentials)


def _parent(config: PlatformConfig) -> str:
    return (
        f"projects/{config.project_id}/locations/"
        f"{config.agent_engine_location}/repositories"
    )


def _emit(value: Any, project_id: str, redact: bool) -> None:
    rendered = value if isinstance(value, str) else json.dumps(value, indent=2)
    print(redact_identifiers(rendered, project_id) if redact else rendered)


def cmd_create(args: argparse.Namespace, config: PlatformConfig) -> int:
    session = _session()
    response = session.post(
        f"{BASE}/{_parent(config)}",
        params={"repositoryId": REPOSITORY_ID},
        json={
            "format": REQUIRED_FORMAT,
            "description": "Recall internal service images",
            "labels": resource_labels(REPOSITORY_COMPONENT),
        },
        timeout=120,
    )
    if response.status_code not in (200, 201):
        raise PlatformError("registry_create_failed", str(response.status_code))
    # Create returns a long-running operation, not the finished repository, so a
    # read-back issued immediately answers 404 and would report a healthy create
    # as a failure. Wait for it to materialise on a bounded schedule.
    waited = _await_repository(session, config)
    _emit(
        {"created": REPOSITORY_ID, "visible_after_seconds": waited},
        config.project_id,
        args.redact,
    )
    return cmd_verify(args, config)


def _await_repository(
    session: Any,
    config: PlatformConfig,
    *,
    attempts: int = CREATE_ATTEMPTS,
    interval_seconds: int = CREATE_INTERVAL_SECONDS,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    """Wait for the repository to become readable, or fail loudly.

    Running out of attempts raises rather than returning: a repository that is
    not readable is not a repository this lane will build into.
    """

    elapsed = 0
    for attempt in range(attempts):
        if attempt:
            sleeper(interval_seconds)
            elapsed += interval_seconds
        probe = session.get(f"{BASE}/{_parent(config)}/{REPOSITORY_ID}", timeout=60)
        if probe.status_code == 200:
            return elapsed
    raise PlatformError("registry_not_visible_after_create", f"{elapsed}s")


def cmd_verify(args: argparse.Namespace, config: PlatformConfig) -> int:
    session = _session()
    response = session.get(
        f"{BASE}/{_parent(config)}/{REPOSITORY_ID}", timeout=60
    )
    if response.status_code != 200:
        raise PlatformError("registry_read_back_failed", str(response.status_code))
    repository = response.json()
    labels = repository.get("labels") or {}
    findings: list[str] = []
    if repository.get("format") != REQUIRED_FORMAT:
        findings.append(f"format:{repository.get('format')}")
    if labels.get("lane") != "l1":
        findings.append(f"lane_label:{labels.get('lane')}")
    _emit(
        {
            "repository": repository.get("name", "").rsplit("/", 1)[-1],
            "format": repository.get("format"),
            "labels": labels,
            "create_time": repository.get("createTime"),
            "status": "PASS" if not findings else "FAIL",
            "findings": findings,
        },
        config.project_id,
        args.redact,
    )
    return 0 if not findings else 1


def cmd_destroy(args: argparse.Namespace, config: PlatformConfig) -> int:
    session = _session()
    response = session.delete(
        f"{BASE}/{_parent(config)}/{REPOSITORY_ID}", timeout=120
    )
    if response.status_code not in (200, 202, 404):
        raise PlatformError("registry_delete_failed", str(response.status_code))
    check = session.get(f"{BASE}/{_parent(config)}/{REPOSITORY_ID}", timeout=60)
    _emit(
        {"deleted": REPOSITORY_ID, "read_back_status": check.status_code},
        config.project_id,
        args.redact,
    )
    return 0 if check.status_code == 404 else 1


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--redact", action="store_true")
    parser = argparse.ArgumentParser(description=__doc__, parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (
        ("create", cmd_create),
        ("verify", cmd_verify),
        ("destroy", cmd_destroy),
    ):
        command = sub.add_parser(name, parents=[common])
        command.set_defaults(handler=handler)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    return int(args.handler(args, PlatformConfig.from_env()))


if __name__ == "__main__":
    raise SystemExit(main())
