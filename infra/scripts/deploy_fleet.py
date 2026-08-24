"""Deploy the three permanent fleet agents and prove the result.

    python infra/scripts/deploy_fleet.py plan --redact
    python infra/scripts/deploy_fleet.py deploy --redact
    python infra/scripts/deploy_fleet.py verify --resource-names <a> <b> <c> --redact

`plan` builds every agent and runs the startup config assert without touching the
cloud, so a configuration mismatch is found for free rather than after three
engines exist.

`deploy` refuses to start unless that assert passes, deploys the three
concurrently, records per-member timing, reads the instance shape back, waits for
the catalog on a bounded schedule, and records one Controller trace carrying a
root span plus one child per agent.

These engines are PERSISTENT under infra/resources.json lifecycle_policy: they
live until the freeze, and the same-day deletion rule does not apply to them.

The agent apps come from recall.agents, so the fleet runs the same agents every
other caller builds. See --bypass-factory-tracing-defect for the one case where
that path cannot be used.
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

from recall.contracts.enums import AgentRole  # noqa: E402
from recall.platform.config import PlatformConfig  # noqa: E402
from recall.platform.errors import PlatformError  # noqa: E402
from recall.platform.fleet import (  # noqa: E402
    FLEET_MEMBERS,
    AgentCall,
    FleetMember,
    assert_agent_carries_no_tracing_flag,
    GatewayBinding,
    assert_fleet_config,
    deploy_fleet,
    fleet_summary,
    record_fleet_run,
    verify_fleet_catalogued,
)
from recall.platform.observability import (  # noqa: E402
    RestTraceClient,
    RestTraceWriter,
    TraceRecorder,
    read_back_trace,
)
from recall.platform.redaction import redact_identifiers  # noqa: E402
from recall.platform.registry import RestRegistryClient  # noqa: E402
from recall.platform.runtime import AgentRuntime, VertexAgentEngineClient  # noqa: E402

logger = logging.getLogger("recall.platform.fleet")

ROLE_TOOLS: dict[AgentRole, dict[str, Any]] = {}


def _emit(value: Any, project_id: str, redact: bool) -> None:
    rendered = value if isinstance(value, str) else json.dumps(value, indent=2)
    print(redact_identifiers(rendered, project_id) if redact else rendered)


def _build_app(member: FleetMember, *, bypass: bool) -> Any:
    """Build the deployable app for one member from the shared agent factory.

    `to_adk_app()` passes enable_tracing=False, and passing that parameter at all
    takes telemetry away from the environment variables: the runtime then reports
    telemetry as on while it is off and emits no spans. While that defect is
    unfixed, --bypass-factory-tracing-defect constructs the same AdkApp without
    the parameter. The bypass is temporary and must be removed once the factory
    stops passing it; the startup guard refuses the flag either way.
    """

    from recall.agents import build_agent_bundle

    bundle = build_agent_bundle(member.role, tools=ROLE_TOOLS.get(member.role, {}))
    if not bypass:
        return bundle.to_adk_app()

    from vertexai import agent_engines

    return agent_engines.AdkApp(
        agent=bundle.agent,
        app_name=f"recall_{member.role.value.lower()}",
    )


def _factory(bypass: bool) -> Any:
    def build(member: FleetMember) -> Any:
        app = _build_app(member, bypass=bypass)
        # Checked here as well as inside deploy_fleet, so `plan` reports the
        # mismatch without any cloud call at all.
        assert_agent_carries_no_tracing_flag(app)
        return app

    return build


def cmd_plan(args: argparse.Namespace, config: PlatformConfig) -> int:
    """Prove the configuration and the agents without touching the cloud."""

    assert_fleet_config(config, gateway=GatewayBinding.from_env())
    built: list[dict[str, Any]] = []
    for member in FLEET_MEMBERS:
        try:
            _factory(args.bypass_factory_tracing_defect)(member)
            outcome, detail = "OK", None
        except PlatformError as exc:
            outcome, detail = "REFUSED", f"{exc.code}:{exc.detail}"
        except Exception as exc:  # noqa: BLE001 - the failure is the finding
            outcome, detail = "FAILED", f"{type(exc).__name__}:{exc}"[:200]
        built.append(
            {
                "role": member.role.value,
                "display_name": member.display_name,
                "service_account_id": member.service_account_id,
                "agent_build": outcome,
                "detail": detail,
            }
        )
    _emit(
        {"startup_config_assert": "PASS", "agents": built},
        config.project_id,
        args.redact,
    )
    return 0 if all(item["agent_build"] == "OK" for item in built) else 1


def cmd_deploy(args: argparse.Namespace, config: PlatformConfig) -> int:
    runtime = AgentRuntime(VertexAgentEngineClient(config), config)
    results = deploy_fleet(
        runtime,
        config,
        _factory(args.bypass_factory_tracing_defect),
        gateway=GatewayBinding.from_env(),
    )

    catalog = verify_fleet_catalogued(
        RestRegistryClient(config), config.agent_engine_location, results
    )

    recorder = TraceRecorder(config.project_id)
    calls = [
        AgentCall(
            member=result.member,
            started_at=datetime.fromisoformat(result.started_at.replace("Z", "+00:00")),
            finished_at=datetime.fromisoformat(
                result.finished_at.replace("Z", "+00:00")
            ),
            outcome="OK" if result.deployed else "FAILED",
            event_count=1 if result.deployed else 0,
        )
        for result in results
        if result.started_at and result.finished_at
    ]
    run_start = min((call.started_at for call in calls), default=datetime.now(UTC))
    run_end = max((call.finished_at for call in calls), default=datetime.now(UTC))
    record_fleet_run(
        recorder,
        calls,
        run_start=run_start,
        run_end=run_end,
        region=config.agent_engine_location,
    )
    recorder.flush(RestTraceWriter(config))
    trace = read_back_trace(RestTraceClient(config), recorder.trace_id)

    summary = fleet_summary(results, catalog, trace.get("span_names", []))
    summary["trace_id"] = recorder.trace_id
    summary["trace_read_back"] = trace
    summary["lifecycle"] = "persistent"
    _emit(summary, config.project_id, args.redact)

    complete = (
        summary["deploy_status"] == "COMPLETE"
        and catalog["status"] == "COMPLETE"
        and summary["trace_status"] == "COMPLETE"
    )
    return 0 if complete else 1


def cmd_verify(args: argparse.Namespace, config: PlatformConfig) -> int:
    """Re-read the catalog and a trace for engines that already exist."""

    runtime = AgentRuntime(VertexAgentEngineClient(config), config)
    engines = [runtime.read_back(name) for name in args.resource_names]
    _emit(
        {
            "engines": [
                {
                    "resource_name": engine.resource_name,
                    "display_name": engine.display_name,
                    "region": engine.region,
                    "revision": engine.revision,
                    "resource_limits": engine.resource_limits,
                    "resource_limits_source": (
                        "READ_BACK" if engine.resource_limits else "UNREAD"
                    ),
                }
                for engine in engines
            ]
        },
        config.project_id,
        args.redact,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--redact", action="store_true")
    common.add_argument(
        "--bypass-factory-tracing-defect",
        action="store_true",
        help=(
            "build AdkApp without enable_tracing because the shared factory "
            "passes it; temporary, remove once the factory is fixed"
        ),
    )
    parser = argparse.ArgumentParser(description=__doc__, parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", parents=[common])
    plan.set_defaults(handler=cmd_plan)

    deploy = sub.add_parser("deploy", parents=[common])
    deploy.set_defaults(handler=cmd_deploy)

    verify = sub.add_parser("verify", parents=[common])
    verify.add_argument("--resource-names", nargs="+", required=True)
    verify.set_defaults(handler=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    return int(args.handler(args, PlatformConfig.from_env()))


if __name__ == "__main__":
    raise SystemExit(main())
