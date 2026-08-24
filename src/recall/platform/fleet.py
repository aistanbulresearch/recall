"""One deploy path for the three fleet agents.

Everything that had to be discovered the hard way on 2026-08-22 is encoded here
once, so the three engines cannot be deployed with a different configuration from
each other or from the one that was proven to work:

- Telemetry is configured by environment variable. The `enable_tracing` parameter
  is never passed to `AdkApp`; passing it at all, even as False, takes telemetry
  away from the environment and the runtime then reports telemetry as on while it
  is off.
- `opentelemetry-instrumentation-google-genai` must be installed in the deployed
  image or the model call produces no span at all.
- Prompt and response text stays out of spans.
- Each role runs under its own service account.

The three deployments run concurrently. Sequentially they took about six minutes
each, which is not an acceptable milestone path.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from recall.contracts.enums import AgentRole

from .config import PlatformConfig
from .errors import PlatformError
from .identity import identity_for_role
from .observability import SpanRecord, TraceRecorder
from .registry import RegistryClient, engine_is_catalogued
from .runtime import AgentRuntime, AgentSpec, DeployedEngine

logger = logging.getLogger(__name__)

FLEET_REQUIREMENTS: tuple[str, ...] = (
    "google-cloud-aiplatform[adk,agent_engines]",
    # Load bearing: without this the model call emits no GenAI span.
    "opentelemetry-instrumentation-google-genai",
    "opentelemetry-instrumentation-grpc",
    "opentelemetry-instrumentation-httpx",
)


@dataclass(frozen=True, slots=True)
class FleetMember:
    """One agent role and the catalog capability it answers."""

    role: AgentRole
    capability: str
    display_name: str

    @property
    def service_account_id(self) -> str:
        return identity_for_role(self.role).account_id

    @property
    def span_name(self) -> str:
        return f"recall.agent.{self.role.value.lower()}"


FLEET_MEMBERS: tuple[FleetMember, ...] = (
    FleetMember(AgentRole.EVIDENCE_WATCHER, "evidence.watch", "recall-watcher"),
    FleetMember(AgentRole.EVIDENCE_ASSESSOR, "evidence.assess", "recall-assessor"),
    FleetMember(AgentRole.CITATION_AUDITOR, "evidence.audit", "recall-auditor"),
)

CONTROLLER_SPAN = "recall.controller.scan_run"

# Pinned so the deployed shape is known when the run is costed, rather than being
# whatever default the runtime happens to apply.
FLEET_RESOURCE_LIMITS: Mapping[str, str] = {"cpu": "1", "memory": "4Gi"}

# Catalog registration is not instant. The one observation on 2026-08-22 happened
# to be immediate, but that was a single engine; three concurrent deploys may
# propagate differently, and a premature read would report a healthy fleet as
# INCOMPLETE.
CATALOG_ATTEMPTS = 6
CATALOG_INTERVAL_SECONDS = 10


def fleet_env_vars(config: PlatformConfig, service_name: str) -> dict[str, str]:
    """The proven telemetry and model environment for a deployed agent."""

    if not service_name:
        raise PlatformError("fleet_service_name_missing")
    return {
        # gemini-3.7-flash is served at global only; the engine itself runs in region.
        "GOOGLE_CLOUD_LOCATION": config.model_location,
        "GOOGLE_GENAI_USE_VERTEXAI": "1",
        "RECALL_MODEL": config.model,
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
        "OTEL_SERVICE_NAME": service_name,
        # Content capture stays off. OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT
        # is deliberately absent for the same reason.
        "ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS": "false",
    }


def fleet_spec(config: PlatformConfig, member: FleetMember) -> AgentSpec:
    """Build the deploy spec for one member, including its own service account."""

    identity = identity_for_role(member.role)
    return AgentSpec(
        display_name=member.display_name,
        description=f"Recall {member.role.value} agent",
        requirements=FLEET_REQUIREMENTS,
        env_vars=fleet_env_vars(config, member.display_name),
        service_account=identity.email(config.project_id),
        resource_limits=dict(FLEET_RESOURCE_LIMITS),
    )


@dataclass(frozen=True, slots=True)
class FleetDeployment:
    """Result of deploying one member: an engine, or the error that stopped it."""

    member: FleetMember
    engine: DeployedEngine | None
    error: str | None
    started_at: str = ""
    finished_at: str = ""
    attempts: int = 1

    @property
    def deployed(self) -> bool:
        return self.engine is not None

    def to_wire(self) -> dict[str, Any]:
        limits = self.engine.resource_limits if self.engine else None
        return {
            "role": self.member.role.value,
            "display_name": self.member.display_name,
            "service_account_id": self.member.service_account_id,
            "deployed": self.deployed,
            "resource_name": self.engine.resource_name if self.engine else None,
            "revision": self.engine.revision if self.engine else None,
            "requested_resource_limits": dict(FLEET_RESOURCE_LIMITS),
            "read_back_resource_limits": dict(limits) if limits else None,
            "resource_limits_source": "READ_BACK" if limits else "UNREAD",
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "attempts": self.attempts,
            "error": self.error,
        }


# The one place the fleet's startup configuration is declared. deploy_fleet
# refuses to start unless the effective configuration matches this exactly.
# Rationale: a parameter that lives only at a call site is a parameter nobody
# checks. Three engines rising on the wrong environment would not be visible
# until the traces were already wrong.
EXPECTED_FLEET_CONFIG: Mapping[str, Any] = {
    "requirements": FLEET_REQUIREMENTS,
    "resource_limits": dict(FLEET_RESOURCE_LIMITS),
    "env_keys": frozenset(
        {
            "GOOGLE_CLOUD_LOCATION",
            "GOOGLE_GENAI_USE_VERTEXAI",
            "RECALL_MODEL",
            "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY",
            "OTEL_SEMCONV_STABILITY_OPT_IN",
            "OTEL_SERVICE_NAME",
            "ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS",
        }
    ),
    "env_values": {
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
        "ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS": "false",
        "GOOGLE_GENAI_USE_VERTEXAI": "1",
    },
    "forbidden_env_keys": frozenset(
        {"enable_tracing", "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"}
    ),
    "role_service_accounts": {
        AgentRole.EVIDENCE_WATCHER.value: "recall-sa-watcher",
        AgentRole.EVIDENCE_ASSESSOR.value: "recall-sa-assessor",
        AgentRole.CITATION_AUDITOR.value: "recall-sa-auditor",
    },
}

TRACING_ATTRIBUTES = ("enable_tracing", "_enable_tracing")


def _mismatch(field: str) -> PlatformError:
    return PlatformError("fleet_config_mismatch", field)


def assert_fleet_config(
    config: PlatformConfig,
    members: Sequence[FleetMember] = FLEET_MEMBERS,
    *,
    expected: Mapping[str, Any] | None = None,
) -> None:
    """Refuse to start unless the effective configuration is the locked one.

    Raises `fleet_config_mismatch:<field>` naming the first field that differs,
    before any engine is created. Recording the actual value in a manifest after
    the fact is not the same protection: by then the engines exist.
    """

    # Resolved here, not bound as a default: a default argument captures the
    # constant once at import, so a later change to it would not be seen and the
    # check would be reading a snapshot of itself.
    if expected is None:
        expected = EXPECTED_FLEET_CONFIG
    if not members:
        raise _mismatch("members")
    declared_roles = {member.role.value for member in members}
    if declared_roles != set(expected["role_service_accounts"]):
        raise _mismatch("role_service_accounts")

    for member in members:
        expected_account = expected["role_service_accounts"][member.role.value]
        if member.service_account_id != expected_account:
            raise _mismatch(f"role_service_accounts.{member.role.value}")

        spec = fleet_spec(config, member)
        if tuple(spec.requirements) != tuple(expected["requirements"]):
            raise _mismatch("requirements")
        if dict(spec.resource_limits or {}) != dict(expected["resource_limits"]):
            raise _mismatch("resource_limits")

        env = dict(spec.env_vars)
        if set(env) != set(expected["env_keys"]):
            raise _mismatch("env_keys")
        for key, value in expected["env_values"].items():
            if env.get(key) != value:
                raise _mismatch(f"env_values.{key}")
        for forbidden in expected["forbidden_env_keys"]:
            if forbidden in env:
                raise _mismatch(f"forbidden_env_keys.{forbidden}")
        if env.get("OTEL_SERVICE_NAME") != member.display_name:
            raise _mismatch("env_values.OTEL_SERVICE_NAME")

        if not spec.service_account or not spec.service_account.startswith(
            expected_account + "@"
        ):
            raise _mismatch(f"service_account.{member.role.value}")


def assert_agent_carries_no_tracing_flag(agent_engine: Any) -> None:
    """Refuse an agent object built with the enable_tracing parameter.

    Passing the parameter at all takes telemetry away from the environment
    variables, and the runtime then reports telemetry as on while it is off.
    False is the dangerous value, not True: it silently disables telemetry while
    looking like a careful setting, which is how a fleet reaches production
    emitting no spans.

    AdkApp records the argument in `_tmpl_attrs`, where an omitted parameter
    leaves None and a passed one leaves the value. Checking truthiness would wave
    through exactly the False that causes the harm, so presence is what is
    checked.
    """

    template = getattr(agent_engine, "_tmpl_attrs", None)
    if isinstance(template, Mapping) and template.get("enable_tracing") is not None:
        raise _mismatch("enable_tracing")
    for attribute in TRACING_ATTRIBUTES:
        if getattr(agent_engine, attribute, None) is not None:
            raise _mismatch("enable_tracing")


AgentFactory = Callable[[FleetMember], Any]


def deploy_fleet(
    runtime: AgentRuntime,
    config: PlatformConfig,
    agent_factory: AgentFactory,
    members: Sequence[FleetMember] = FLEET_MEMBERS,
    *,
    max_workers: int = 3,
    retries: int = 1,
) -> list[FleetDeployment]:
    """Deploy every member concurrently and report each outcome separately.

    A member that fails does not cancel the others, and its failure is returned
    rather than raised, so a partial fleet is visible as a partial fleet instead
    of collapsing into one exception.
    """

    if not members:
        raise PlatformError("fleet_no_members")
    # Checked before anything is created. A mismatch stops the run with zero
    # engines in flight.
    assert_fleet_config(config, members)

    def _deploy(member: FleetMember) -> FleetDeployment:
        # Timestamps are recorded per member so 08-24 can measure whether the
        # three creates actually ran concurrently rather than assuming they did.
        started = datetime.now(UTC)
        error: str | None = None
        for attempt in range(1, retries + 2):
            try:
                agent = agent_factory(member)
                assert_agent_carries_no_tracing_flag(agent)
                engine = runtime.deploy(fleet_spec(config, member), agent)
            except Exception as exc:  # noqa: BLE001 - the failure is the result
                error = f"{type(exc).__name__}:{exc}"[:300]
                logger.error(
                    "fleet member failed on attempt %s: %s", attempt, member.display_name
                )
                continue
            return FleetDeployment(
                member,
                engine,
                None,
                started_at=_stamp(started),
                finished_at=_stamp(datetime.now(UTC)),
                attempts=attempt,
            )
        return FleetDeployment(
            member,
            None,
            error,
            started_at=_stamp(started),
            finished_at=_stamp(datetime.now(UTC)),
            attempts=retries + 1,
        )

    with ThreadPoolExecutor(max_workers=min(max_workers, len(members))) as pool:
        return list(pool.map(_deploy, members))


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def deploy_overlap_seconds(results: Sequence[FleetDeployment]) -> float:
    """How long at least two members were deploying at once.

    Zero means the creates were serialised, whatever the intent was.
    """

    spans = [
        (
            datetime.fromisoformat(r.started_at.replace("Z", "+00:00")),
            datetime.fromisoformat(r.finished_at.replace("Z", "+00:00")),
        )
        for r in results
        if r.started_at and r.finished_at
    ]
    if len(spans) < 2:
        return 0.0
    overlap = 0.0
    for index, (start_a, end_a) in enumerate(spans):
        for start_b, end_b in spans[index + 1 :]:
            latest_start = max(start_a, start_b)
            earliest_end = min(end_a, end_b)
            overlap = max(overlap, (earliest_end - latest_start).total_seconds())
    return max(overlap, 0.0)


def fleet_is_complete(results: Sequence[FleetDeployment]) -> bool:
    return bool(results) and all(result.deployed for result in results)


def verify_fleet_catalogued(
    client: RegistryClient,
    location: str,
    results: Sequence[FleetDeployment],
    *,
    attempts: int = CATALOG_ATTEMPTS,
    interval_seconds: int = CATALOG_INTERVAL_SECONDS,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Read the catalog back until every deployed member appears, or give up.

    Registration is not instant, so a single read taken straight after deploy can
    report a healthy fleet as INCOMPLETE. This retries on a bounded schedule and
    records the elapsed seconds at which each member first appeared. Running out
    of attempts still returns INCOMPLETE: waiting longer is allowed, concluding
    success without evidence is not.

    A member that did not deploy is never catalogued and is not waited for.
    """

    if attempts < 1:
        raise PlatformError("fleet_catalog_attempts_invalid", str(attempts))
    pending = {
        result.member.role.value: result
        for result in results
        if result.engine is not None
    }
    first_seen: dict[str, int] = {}
    elapsed = 0
    for attempt in range(attempts):
        if not pending:
            break
        if attempt:
            sleeper(interval_seconds)
            elapsed += interval_seconds
        for role, result in list(pending.items()):
            assert result.engine is not None
            if engine_is_catalogued(client, location, result.engine.resource_name):
                first_seen[role] = elapsed
                del pending[role]

    entries: list[dict[str, Any]] = []
    for result in results:
        role = result.member.role.value
        catalogued = role in first_seen
        entries.append(
            {
                "role": role,
                "display_name": result.member.display_name,
                "deployed": result.deployed,
                "catalogued": catalogued,
                "catalogued_after_seconds": first_seen.get(role),
            }
        )
    complete = bool(entries) and all(entry["catalogued"] for entry in entries)
    return {
        "location": location,
        "members": entries,
        "catalogued_count": sum(1 for entry in entries if entry["catalogued"]),
        "expected": len(entries),
        "waited_seconds": elapsed,
        "status": "COMPLETE" if complete else "INCOMPLETE",
    }


@dataclass(frozen=True, slots=True)
class AgentCall:
    """One agent invocation the Controller made, as it will appear in the trace."""

    member: FleetMember
    started_at: datetime
    finished_at: datetime
    outcome: str
    event_count: int


def record_fleet_run(
    recorder: TraceRecorder,
    calls: Sequence[AgentCall],
    *,
    region: str,
    run_start: datetime,
    run_end: datetime,
) -> tuple[SpanRecord, ...]:
    """Record the Controller root span and one child span per agent call.

    Only calls that were actually made produce a span. A span for an agent that
    never ran would be a decorative claim about the fleet.
    """

    if not calls:
        raise PlatformError("fleet_no_calls_recorded")
    root = recorder.record(CONTROLLER_SPAN, start=run_start, end=run_end)
    for call in calls:
        recorder.record(
            call.member.span_name,
            start=call.started_at,
            end=call.finished_at,
            parent_span_id=root.span_id,
            attributes={
                "recall.role": call.member.role.value,
                "recall.capability": call.member.capability,
                "recall.region": region,
                "recall.outcome": call.outcome,
                "recall.event_count": str(call.event_count),
            },
        )
    return recorder.spans


def expected_span_names(members: Sequence[FleetMember] = FLEET_MEMBERS) -> list[str]:
    """The span names a complete fleet run should produce, sorted as read back."""

    return sorted([CONTROLLER_SPAN, *(member.span_name for member in members)])


def fleet_trace_is_complete(
    span_names: Sequence[str], members: Sequence[FleetMember] = FLEET_MEMBERS
) -> bool:
    """A complete run shows the Controller span plus every member's span."""

    return set(expected_span_names(members)).issubset(set(span_names))


def fleet_summary(
    results: Sequence[FleetDeployment],
    catalog: Mapping[str, Any],
    span_names: Sequence[str],
) -> dict[str, Any]:
    """One object an operator can read to see whether the fleet is really up."""

    overlap = deploy_overlap_seconds(results)
    return {
        "deployments": [result.to_wire() for result in results],
        "deploy_status": "COMPLETE" if fleet_is_complete(results) else "INCOMPLETE",
        "deploy_overlap_seconds": overlap,
        # Measured rather than assumed: zero overlap means Vertex serialised the
        # creates, whatever the thread pool intended.
        "deploy_concurrency": "CONCURRENT" if overlap > 0 else "SERIALISED",
        "retried_members": [
            result.member.role.value for result in results if result.attempts > 1
        ],
        "catalog": dict(catalog),
        "trace_span_names": sorted(span_names),
        "trace_status": (
            "COMPLETE" if fleet_trace_is_complete(span_names) else "INCOMPLETE"
        ),
    }
