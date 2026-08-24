"""Answer one question: can a deployed Agent Engine reach the tool gateway?

IAM and reachability are different questions. The three agent service accounts
hold roles/run.invoker on recall-tool-gateway, which is an authorization fact
and says nothing about whether a packet from inside a managed Agent Engine can
arrive at a Cloud Run service whose ingress is internal-only.

The verdict classifies BY MECHANISM, not by whether the call succeeded, because
a failed call can mean three completely different things and only one of them
is an answer to this question:

    REACHABLE    an HTTP response of any kind came back, including 401, 403 or
                 500, and including a body that was not JSON. A body is proof
                 of a network path. This is the trap case: an HTML 403 page
                 from the Google front end surfaces as
                 tool_gateway_response_invalid, which reads like a failure and
                 is in fact the strongest possible evidence of reachability.
    UNREACHABLE  tool_gateway_unavailable, and only that. The transport raises
                 it solely from (OSError, TimeoutError, URLError), meaning no
                 HTTP was ever received.
    CONFIG       a client-side refusal before a socket opened.
    INCONCLUSIVE the model never invoked the tool. Not a verdict. Reported as
                 a non-answer rather than dressed up as one.

Signatures are taken from UrlLibGatewayTransport in src/recall/agents/tools.py,
which catches HTTPError separately and keeps parsing, so an HTTP error arrives
as a response rather than as a failure.

Usage:
    python infra/scripts/reachability_discriminator.py --resource-name <name>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from recall.platform.config import PlatformConfig  # noqa: E402
from recall.platform.redaction import redact_identifiers  # noqa: E402
from recall.platform.runtime import TracedRuntimeInvoker  # noqa: E402

# Phrased to make the tool the only way to answer. The model still decides, and
# a run where it declines is reported as INCONCLUSIVE rather than as a verdict.
PROBE_MESSAGE = (
    "Use your evidence_connector tool now to fetch evidence for identifier "
    "PMID:12345678. Do not answer from memory and do not explain your "
    "reasoning: call the tool. If the tool call fails, report the exact error "
    "string it raised, verbatim, and nothing else."
)

UNREACHABLE_SIGNATURES = ("tool_gateway_unavailable",)
REACHABLE_SIGNATURES = (
    "tool_gateway_response_invalid",
    "tool_gateway_denied",
    "tool_gateway_request_mismatch",
    "tool_gateway_result_invalid",
)
CONFIG_SIGNATURES = (
    "tool_gateway_https_required",
    "tool_gateway_audience_required",
    "tool_gateway_timeout_invalid",
)


def classify(blob: str, tool_seen: bool) -> tuple[str, str]:
    """Return (verdict, evidence) from the raw response text."""

    for signature in CONFIG_SIGNATURES:
        if signature in blob:
            return "CONFIG", signature
    for signature in UNREACHABLE_SIGNATURES:
        if signature in blob:
            return "UNREACHABLE", signature
    for signature in REACHABLE_SIGNATURES:
        if signature in blob:
            return "REACHABLE", signature
    if tool_seen:
        # The tool ran and raised none of the known failures, so a response was
        # parsed: the path exists.
        return "REACHABLE", "tool completed without a transport failure"
    return "INCONCLUSIVE", "no evidence_connector invocation in the response"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resource-name", required=True)
    parser.add_argument("--user-id", default="recall-discriminator")
    parser.add_argument("--redact", action="store_true")
    args = parser.parse_args()

    config = PlatformConfig.from_env()
    invoker = TracedRuntimeInvoker(config)

    started = time.monotonic()
    error: str | None = None
    events: Any = None
    try:
        events = invoker.invoke(
            args.resource_name, message=PROBE_MESSAGE, user_id=args.user_id
        )
    except Exception as exc:  # noqa: BLE001 - the failure IS the measurement
        error = f"{type(exc).__name__}:{exc}"
    latency = round(time.monotonic() - started, 2)

    blob = json.dumps(events, default=str) if events is not None else (error or "")
    tool_seen = "evidence_connector" in blob
    verdict, evidence = classify(blob, tool_seen)
    if error and verdict == "INCONCLUSIVE":
        verdict, evidence = "INVOCATION_FAILED", error

    result = {
        "probe": "agent_engine_to_tool_gateway",
        "mode": "model_mediated",
        "resource_name": args.resource_name,
        "gateway_url": os.environ.get("RECALL_TOOL_GATEWAY_URL", "<unset>"),
        "latency_seconds": latency,
        "tool_invocation_seen": tool_seen,
        "verdict": verdict,
        "evidence": evidence,
        "invocation_error": error,
        "raw_response": events,
    }
    rendered = json.dumps(result, indent=2, default=str)
    print(redact_identifiers(rendered, config.project_id) if args.redact else rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
