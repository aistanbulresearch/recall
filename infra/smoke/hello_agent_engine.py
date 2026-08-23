"""Day-zero Agent Runtime smoke: deploy, read back, invoke, receipt, delete.

Each stage is a separate subcommand so every step produces its own raw output and
nothing is inferred from an earlier call. Run from the tooling interpreter that
carries the Vertex AI Agent Engine SDK (see infra/README.md).

    $env:RECALL_PLATFORM_PYTHON infra\\smoke\\hello_agent_engine.py deploy --redact
    ... invoke   --resource-name <name> --message "..." --redact
    ... receipt  --resource-name <name> --redact
    ... delete   --resource-name <name> --redact
    ... list --redact

`--redact` replaces the project segment of every resource name with `<project>`
so the output can be pasted into a report without leaking the project id.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from recall.contracts.enums import ArtifactStatus, DataMode  # noqa: E402
from recall.platform.config import PlatformConfig  # noqa: E402
from recall.platform.errors import PlatformError  # noqa: E402
from recall.platform.identity import BY_ACCOUNT_ID  # noqa: E402
from recall.platform.receipts import utc_timestamp  # noqa: E402
from recall.platform.redaction import redact_identifiers  # noqa: E402
from recall.platform.runtime import (  # noqa: E402
    AgentRuntime,
    AgentSpec,
    VertexAgentEngineClient,
)

logger = logging.getLogger("recall.platform.smoke")

DISPLAY_NAME = "recall-hello-smoke"
AGENT_NAME = "recall_hello_smoke"
DESCRIPTION = "Lane L1 day-zero managed runtime smoke. Temporary; deleted same day."
# The runtime logs "telemetry enabled but proceeding without ... instrumentation"
# and emits no spans unless these are installed in the deployed image. The
# google-genai one is the load-bearing package: without it the model call
# produces no GenAI span at all.
REQUIREMENTS = (
    "google-cloud-aiplatform[adk,agent_engines]",
    "opentelemetry-instrumentation-google-genai",
    "opentelemetry-instrumentation-grpc",
    "opentelemetry-instrumentation-httpx",
)
INSTRUCTION = (
    "You are a deployment smoke probe for the Recall platform lane. "
    "Answer in one short sentence. Handle no clinical or personal content."
)
_PROJECT_ID = ""


def _redact(text: str, enabled: bool) -> str:
    return redact_identifiers(text, _PROJECT_ID) if enabled else text


def identity_email(account_id: str, project_id: str) -> str:
    identity = BY_ACCOUNT_ID.get(account_id)
    if identity is None:
        raise PlatformError("identity_account_unknown", account_id)
    return identity.email(project_id)


def _emit(value: Any, redact: bool) -> None:
    rendered = value if isinstance(value, str) else json.dumps(value, indent=2)
    print(_redact(rendered, redact))


def _source_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _runtime(config: PlatformConfig) -> AgentRuntime:
    return AgentRuntime(VertexAgentEngineClient(config), config)


def _hello_app(config: PlatformConfig) -> Any:
    """Build the app without the enable_tracing parameter.

    The runtime logs: "To fix this and control telemetry, please remove the
    'enable_tracing' parameter from your deployment code... The Cloud Console may
    incorrectly show telemetry as On when it is actually Off." Passing the
    parameter at all, even as False, takes telemetry away from the environment
    variables, so it is not passed.
    """

    from google.adk.agents import Agent
    from vertexai import agent_engines

    agent = Agent(model=config.model, name=AGENT_NAME, instruction=INSTRUCTION)
    return agent_engines.AdkApp(agent=agent)


def _spec(config: PlatformConfig, service_account: str | None) -> AgentSpec:
    return AgentSpec(
        display_name=DISPLAY_NAME,
        description=DESCRIPTION,
        requirements=REQUIREMENTS,
        env_vars={
            "GOOGLE_CLOUD_LOCATION": config.model_location,
            "GOOGLE_GENAI_USE_VERTEXAI": "1",
            "RECALL_MODEL": config.model,
            # Telemetry is configured by environment. The enable_tracing flag is
            # overridden by the runtime and produced no spans.
            "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
            "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
            "OTEL_SERVICE_NAME": DISPLAY_NAME,
            # Keep prompt and response text out of spans. Recall's contracts
            # forbid raw sensitive text in cloud artifacts, so both content
            # capture switches stay off: this one is false and
            # OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT is left unset.
            "ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS": "false",
        },
        service_account=service_account,
    )


def cmd_deploy(args: argparse.Namespace, config: PlatformConfig) -> int:
    runtime = _runtime(config)
    started = utc_timestamp(datetime.now(UTC))
    account = None
    if args.service_account_id:
        account = identity_email(args.service_account_id, config.project_id)
    engine = runtime.deploy(_spec(config, account), _hello_app(config))
    _emit(
        {
            "started_at": started,
            "resource_name": engine.resource_name,
            "display_name": engine.display_name,
            "region": engine.region,
            "revision": engine.revision,
            "read_back_at": engine.read_back_at,
        },
        args.redact,
    )
    return 0


def cmd_invoke(args: argparse.Namespace, config: PlatformConfig) -> int:
    runtime = _runtime(config)
    events = runtime.invoke(
        args.resource_name, message=args.message, user_id=args.user_id
    )
    _emit(events, args.redact)
    return 0


def cmd_receipt(args: argparse.Namespace, config: PlatformConfig) -> int:
    runtime = _runtime(config)
    engine = runtime.read_back(args.resource_name)
    receipt = runtime.build_deployment_receipt(
        engine,
        artifact_id=str(uuid.uuid4()),
        producer_version=args.producer_version,
        source_revision=_source_revision(),
        deployed_components=[DISPLAY_NAME],
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID,
    )
    _emit(receipt, args.redact)
    return 0


def cmd_delete(args: argparse.Namespace, config: PlatformConfig) -> int:
    runtime = _runtime(config)
    runtime.delete(args.resource_name, force=True)
    absent = runtime.is_absent(args.resource_name)
    _emit(
        {
            "deleted": args.resource_name,
            "absent_from_list": absent,
            "remaining": runtime.list_resource_names(),
            "checked_at": utc_timestamp(datetime.now(UTC)),
        },
        args.redact,
    )
    return 0 if absent else 1


def cmd_list(args: argparse.Namespace, config: PlatformConfig) -> int:
    runtime = _runtime(config)
    _emit(
        {
            "region": config.agent_engine_location,
            "resource_names": runtime.list_resource_names(),
            "checked_at": utc_timestamp(datetime.now(UTC)),
        },
        args.redact,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    # Shared flags live on a parent parser so they are accepted after the
    # subcommand, which is where an operator naturally types them.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--redact", action="store_true")
    common.add_argument("--producer-version", default="0.1.0")

    parser = argparse.ArgumentParser(description=__doc__, parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    deploy = sub.add_parser("deploy", parents=[common])
    deploy.add_argument(
        "--service-account-id",
        default=None,
        help="account id such as recall-sa-watcher; the project is resolved locally",
    )
    deploy.set_defaults(handler=cmd_deploy)

    invoke = sub.add_parser("invoke", parents=[common])
    invoke.add_argument("--resource-name", required=True)
    invoke.add_argument("--message", default="Reply with the word ready.")
    invoke.add_argument("--user-id", default="l1-smoke")
    invoke.set_defaults(handler=cmd_invoke)

    receipt = sub.add_parser("receipt", parents=[common])
    receipt.add_argument("--resource-name", required=True)
    receipt.set_defaults(handler=cmd_receipt)

    delete = sub.add_parser("delete", parents=[common])
    delete.add_argument("--resource-name", required=True)
    delete.set_defaults(handler=cmd_delete)

    listing = sub.add_parser("list", parents=[common])
    listing.set_defaults(handler=cmd_list)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    config = PlatformConfig.from_env()
    global _PROJECT_ID
    _PROJECT_ID = config.project_id
    return int(args.handler(args, config))


if __name__ == "__main__":
    raise SystemExit(main())
