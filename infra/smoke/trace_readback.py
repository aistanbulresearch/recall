"""Cloud Trace read-back for a managed-path invocation.

    python infra/smoke/trace_readback.py recent --redact
    python infra/smoke/trace_readback.py get --trace-id <32 hex> --redact
    python infra/smoke/trace_readback.py receipt --trace-id <32 hex> --redact

`get` exits non-zero unless the trace exists and carries spans, so an absent or
empty trace fails rather than reading as a working managed path.
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

logger = logging.getLogger("recall.platform.trace")


def _emit(value: Any, project_id: str, redact: bool) -> None:
    rendered = value if isinstance(value, str) else json.dumps(value, indent=2)
    print(redact_identifiers(rendered, project_id) if redact else rendered)


def cmd_recent(args: argparse.Namespace, config: PlatformConfig) -> int:
    payload = RestTraceClient(config).list_traces(page_size=args.page_size)
    traces = payload.get("traces") or []
    _emit(
        {
            "count": len(traces),
            "traces": [
                {
                    "traceId": trace.get("traceId"),
                    "span_names": sorted(
                        str(span.get("name", "")) for span in trace.get("spans", [])
                    ),
                }
                for trace in traces
            ],
        },
        config.project_id,
        args.redact,
    )
    return 0 if traces else 1


def cmd_get(args: argparse.Namespace, config: PlatformConfig) -> int:
    result = read_back_trace(RestTraceClient(config), args.trace_id)
    _emit(result, config.project_id, args.redact)
    return 0 if result["state"] == ComponentState.OBSERVED.value else 1


def cmd_receipt(args: argparse.Namespace, config: PlatformConfig) -> int:
    result = read_back_trace(RestTraceClient(config), args.trace_id)
    statuses = [
        ComponentStatus(
            "agent-runtime",
            ComponentState(result["state"]),
            result["reason_code"],
        )
    ]
    receipt = managed_path_receipt(
        artifact_id=str(uuid.uuid4()),
        producer_version=args.producer_version,
        created_at=utc_timestamp(datetime.now(UTC)),
        statuses=statuses,
        trace_id=args.trace_id if result["state"] == ComponentState.OBSERVED.value else None,
    )
    _emit(receipt, config.project_id, args.redact)
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--redact", action="store_true")
    common.add_argument("--producer-version", default="0.1.0")
    parser = argparse.ArgumentParser(description=__doc__, parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    recent = sub.add_parser("recent", parents=[common])
    recent.add_argument("--page-size", type=int, default=20)
    recent.set_defaults(handler=cmd_recent)

    for name, handler in (("get", cmd_get), ("receipt", cmd_receipt)):
        command = sub.add_parser(name, parents=[common])
        command.add_argument("--trace-id", required=True)
        command.set_defaults(handler=handler)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    return int(args.handler(args, PlatformConfig.from_env()))


if __name__ == "__main__":
    raise SystemExit(main())
