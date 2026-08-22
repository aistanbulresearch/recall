"""Managed-path trace evidence: invoke under a known trace id, then read it back.

    python infra/smoke/trace_readback.py invoke --resource-name <name> --redact
    python infra/smoke/trace_readback.py get --trace-id <32 hex> --redact
    python infra/smoke/trace_readback.py receipt --trace-id <32 hex> --redact

There is no search command. Cloud Trace v1 `projects.traces.list` returned zero
results for a trace that `projects.traces.get` returned immediately, so searching
cannot be used to find a trace. The caller mints the trace id and injects it as a
W3C `traceparent`, so the id to fetch is always already known.

`invoke` and `get` exit non-zero unless the trace is fetched with at least one
span, so a missing or empty trace fails rather than reading as a managed path.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from recall.platform.config import PlatformConfig  # noqa: E402
from recall.platform.observability import (  # noqa: E402
    ComponentState,
    ComponentStatus,
    RestTraceClient,
    managed_path_receipt,
    read_back_trace,
)
from recall.platform.receipts import utc_timestamp  # noqa: E402
from recall.platform.redaction import redact_identifiers  # noqa: E402
from recall.platform.runtime import TracedRuntimeInvoker  # noqa: E402

logger = logging.getLogger("recall.platform.trace")


def _emit(value: Any, project_id: str, redact: bool) -> None:
    rendered = value if isinstance(value, str) else json.dumps(value, indent=2)
    print(redact_identifiers(rendered, project_id) if redact else rendered)


def _receipt_for(
    trace: dict[str, Any], component: str, producer_version: str
) -> dict[str, Any]:
    statuses = [
        ComponentStatus(component, ComponentState(trace["state"]), trace["reason_code"])
    ]
    observed = trace["state"] == ComponentState.OBSERVED.value
    return managed_path_receipt(
        artifact_id=str(uuid.uuid4()),
        producer_version=producer_version,
        created_at=utc_timestamp(datetime.now(UTC)),
        statuses=statuses,
        trace_id=trace["trace_id"] if observed else None,
    )


def cmd_invoke(args: argparse.Namespace, config: PlatformConfig) -> int:
    """Mint a trace id, call the agent under it, then fetch that exact trace."""

    call = TracedRuntimeInvoker(config).invoke(
        args.resource_name,
        message=args.message,
        user_id=args.user_id,
        trace_id=args.trace_id,
    )
    trace = read_back_trace(RestTraceClient(config), call.trace_id)
    _emit(
        {
            "traceparent_sent": call.traceparent,
            "trace_id": call.trace_id,
            "event_count": len(call.events),
            "first_event_author": call.events[0].get("author") if call.events else None,
            "trace_read_back": trace,
        },
        config.project_id,
        args.redact,
    )
    return 0 if trace["state"] == ComponentState.OBSERVED.value else 1


def cmd_get(args: argparse.Namespace, config: PlatformConfig) -> int:
    trace = read_back_trace(RestTraceClient(config), args.trace_id)
    _emit(trace, config.project_id, args.redact)
    return 0 if trace["state"] == ComponentState.OBSERVED.value else 1


def cmd_receipt(args: argparse.Namespace, config: PlatformConfig) -> int:
    trace = read_back_trace(RestTraceClient(config), args.trace_id)
    _emit(
        _receipt_for(trace, args.component, args.producer_version),
        config.project_id,
        args.redact,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--redact", action="store_true")
    common.add_argument("--producer-version", default="0.1.0")
    parser = argparse.ArgumentParser(description=__doc__, parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    invoke = sub.add_parser("invoke", parents=[common])
    invoke.add_argument("--resource-name", required=True)
    invoke.add_argument("--message", default="Reply with the word ready.")
    invoke.add_argument("--user-id", default="l1-trace-smoke")
    invoke.add_argument("--trace-id", default=None)
    invoke.set_defaults(handler=cmd_invoke)

    get = sub.add_parser("get", parents=[common])
    get.add_argument("--trace-id", required=True)
    get.set_defaults(handler=cmd_get)

    receipt = sub.add_parser("receipt", parents=[common])
    receipt.add_argument("--trace-id", required=True)
    receipt.add_argument("--component", default="agent-runtime")
    receipt.set_defaults(handler=cmd_receipt)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    return int(args.handler(args, PlatformConfig.from_env()))


if __name__ == "__main__":
    raise SystemExit(main())
