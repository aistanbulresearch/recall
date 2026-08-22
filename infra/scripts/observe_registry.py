"""Read-only Agent Registry observation.

Answers two questions with evidence rather than assumption: what the catalog
actually holds, and whether a given deployed Agent Engine appears in it.

    python infra/scripts/observe_registry.py catalog --redact
    python infra/scripts/observe_registry.py catalogued --resource-name <name> --redact

Creates nothing. Registering a service or binding is a separate, approved step.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from recall.platform.config import PlatformConfig  # noqa: E402
from recall.platform.redaction import redact_identifiers  # noqa: E402
from recall.platform.registry import (  # noqa: E402
    RestRegistryClient,
    engine_is_catalogued,
    observe_catalog,
)

logger = logging.getLogger("recall.platform.registry")


def _emit(value: Any, project_id: str, redact: bool) -> None:
    rendered = value if isinstance(value, str) else json.dumps(value, indent=2)
    print(redact_identifiers(rendered, project_id) if redact else rendered)


def cmd_catalog(args: argparse.Namespace, config: PlatformConfig) -> int:
    client = RestRegistryClient(config)
    _emit(
        observe_catalog(client, config.agent_engine_location),
        config.project_id,
        args.redact,
    )
    return 0


def cmd_catalogued(args: argparse.Namespace, config: PlatformConfig) -> int:
    client = RestRegistryClient(config)
    catalogued = engine_is_catalogued(
        client, config.agent_engine_location, args.resource_name
    )
    _emit(
        {
            "resource_name": args.resource_name,
            "catalogued": catalogued,
            "location": config.agent_engine_location,
        },
        config.project_id,
        args.redact,
    )
    return 0 if catalogued else 1


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--redact", action="store_true")
    parser = argparse.ArgumentParser(description=__doc__, parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    catalog = sub.add_parser("catalog", parents=[common])
    catalog.set_defaults(handler=cmd_catalog)

    catalogued = sub.add_parser("catalogued", parents=[common])
    catalogued.add_argument("--resource-name", required=True)
    catalogued.set_defaults(handler=cmd_catalogued)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    return int(args.handler(args, PlatformConfig.from_env()))


if __name__ == "__main__":
    raise SystemExit(main())
