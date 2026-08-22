"""Vertex AI Agent Engine (Agent Runtime) wrapper.

The Vertex SDK is imported lazily so the deterministic core and its unit tests
stay free of a cloud dependency. Callers inject an ``AgentEngineClient``; the
production implementation is ``VertexAgentEngineClient``.

Receipt field mapping, stated explicitly so no value is invented:

- ``runtime.service`` is the constant ``vertex-ai-agent-engine``.
- ``runtime.region`` is the Agent Engine location the resource was read back from.
- ``runtime.resource_name`` is the full ``projects/.../reasoningEngines/...`` name.
- ``runtime.revision`` is the read-back ``update_time``, the only per-deployment
  version an Agent Engine resource exposes.
- ``runtime.read_back_at`` is when this process performed the confirming get.

A deployment that cannot be read back produces no VALID receipt.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from recall.contracts.enums import ArtifactStatus, DataMode

from .config import PlatformConfig
from .errors import PlatformError
from .receipts import deployment_receipt, utc_timestamp

logger = logging.getLogger(__name__)

RUNTIME_SERVICE = "vertex-ai-agent-engine"


@dataclass(frozen=True, slots=True)
class AgentSpec:
    """Immutable description of one agent to place on the managed runtime."""

    display_name: str
    description: str
    requirements: tuple[str, ...]
    env_vars: Mapping[str, str] = field(default_factory=dict)
    service_account: str | None = None


@dataclass(frozen=True, slots=True)
class DeployedEngine:
    """Read-back view of a deployed Agent Engine resource."""

    resource_name: str
    display_name: str
    region: str
    revision: str
    deployed_at: str
    read_back_at: str

    @property
    def engine_id(self) -> str:
        return self.resource_name.rsplit("/", 1)[-1]


class AgentEngineClient(Protocol):
    """Minimal surface of vertexai.agent_engines used by this lane."""

    def create(
        self,
        *,
        agent_engine: Any,
        display_name: str,
        description: str,
        requirements: Sequence[str],
        env_vars: Mapping[str, str],
        service_account: str | None,
    ) -> Any: ...

    def get(self, resource_name: str) -> Any: ...

    def list(self) -> Iterable[Any]: ...

    def delete(self, resource_name: str, *, force: bool = False) -> None: ...


def _resource_attr(resource: Any, name: str) -> Any:
    value = getattr(resource, name, None)
    if value is None:
        api_resource = getattr(resource, "api_resource", None)
        if api_resource is not None:
            value = getattr(api_resource, name, None)
    return value


def _resource_name_of(resource: Any) -> Any:
    name = _resource_attr(resource, "resource_name")
    if name is None:
        name = _resource_attr(resource, "name")
    return name


def _read_back_region(resource_name: str) -> str:
    parts = resource_name.split("/")
    if len(parts) < 4 or parts[0] != "projects" or parts[2] != "locations":
        raise PlatformError("runtime_resource_name_invalid", resource_name)
    return parts[3]


def _format_timestamp(value: Any) -> str:
    """Render an Agent Engine timestamp as the RFC 3339 string the contract needs."""

    if isinstance(value, str):
        return value
    rfc3339 = getattr(value, "rfc3339", None)
    if callable(rfc3339):
        return str(rfc3339())
    if isinstance(value, datetime):
        return utc_timestamp(value)
    raise PlatformError("runtime_timestamp_invalid", type(value).__name__)


class AgentRuntime:
    """Deploy, invoke, read back, and delete managed agents."""

    def __init__(self, client: AgentEngineClient, config: PlatformConfig) -> None:
        self._client = client
        self._config = config

    def deploy(self, spec: AgentSpec, agent_engine: Any) -> DeployedEngine:
        created = self._client.create(
            agent_engine=agent_engine,
            display_name=spec.display_name,
            description=spec.description,
            requirements=list(spec.requirements),
            env_vars=dict(spec.env_vars),
            service_account=spec.service_account,
        )
        resource_name = _resource_name_of(created)
        if not isinstance(resource_name, str) or not resource_name:
            raise PlatformError("runtime_create_resource_name_missing")
        logger.info("agent engine created: %s", resource_name.rsplit("/", 1)[-1])
        return self.read_back(resource_name)

    def read_back(self, resource_name: str) -> DeployedEngine:
        """Confirm a deployment by a separate get, never by the create response."""

        resource = self._client.get(resource_name)
        if resource is None:
            raise PlatformError("runtime_read_back_missing", resource_name)
        confirmed = _resource_name_of(resource)
        if confirmed != resource_name:
            raise PlatformError("runtime_read_back_mismatch", resource_name)
        revision = _resource_attr(resource, "update_time")
        if revision is None:
            raise PlatformError("runtime_revision_missing", resource_name)
        created = _resource_attr(resource, "create_time")
        if created is None:
            raise PlatformError("runtime_create_time_missing", resource_name)
        display_name = _resource_attr(resource, "display_name") or ""
        return DeployedEngine(
            resource_name=resource_name,
            display_name=str(display_name),
            region=_read_back_region(resource_name),
            revision=_format_timestamp(revision),
            deployed_at=_format_timestamp(created),
            read_back_at=utc_timestamp(datetime.now(UTC)),
        )

    def invoke(
        self, resource_name: str, *, message: str, user_id: str
    ) -> list[dict[str, Any]]:
        """Call a deployed agent and return its raw event stream."""

        resource = self._client.get(resource_name)
        stream = getattr(resource, "stream_query", None)
        if stream is None:
            raise PlatformError("runtime_query_unsupported", resource_name)
        events = [dict(event) for event in stream(message=message, user_id=user_id)]
        if not events:
            raise PlatformError("runtime_query_empty", resource_name)
        return events

    def list_resource_names(self) -> list[str]:
        names: list[str] = []
        for resource in self._client.list():
            name = _resource_name_of(resource)
            if isinstance(name, str) and name:
                names.append(name)
        return sorted(names)

    def delete(self, resource_name: str, *, force: bool = False) -> None:
        self._client.delete(resource_name, force=force)
        logger.info("agent engine deleted: %s", resource_name.rsplit("/", 1)[-1])

    def is_absent(self, resource_name: str) -> bool:
        """Prove removal from the catalog listing, not from the delete call."""

        return resource_name not in self.list_resource_names()

    def build_deployment_receipt(
        self,
        engine: DeployedEngine,
        *,
        artifact_id: str,
        producer_version: str,
        source_revision: str,
        deployed_components: Sequence[str],
        deployed_at: str | None = None,
        data_mode: DataMode = DataMode.SYNTHETIC,
        status: ArtifactStatus = ArtifactStatus.VALID,
    ) -> dict[str, Any]:
        return deployment_receipt(
            artifact_id=artifact_id,
            producer_version=producer_version,
            created_at=utc_timestamp(datetime.now(UTC)),
            deployed_at=deployed_at or engine.deployed_at,
            source_revision=source_revision,
            deployed_components=deployed_components,
            service=RUNTIME_SERVICE,
            revision=engine.revision,
            region=engine.region,
            resource_name=engine.resource_name,
            read_back_at=engine.read_back_at,
            data_mode=data_mode,
            status=status,
        )


class VertexAgentEngineClient:
    """Production AgentEngineClient backed by vertexai.agent_engines."""

    def __init__(self, config: PlatformConfig) -> None:
        self._config = config
        self._engines = self._initialise(config)

    @staticmethod
    def _initialise(config: PlatformConfig) -> Any:
        try:
            import vertexai
            from vertexai import agent_engines
        except ImportError as exc:  # pragma: no cover - needs the tooling venv
            raise PlatformError("runtime_sdk_unavailable", str(exc)) from exc
        vertexai.init(
            project=config.project_id,
            location=config.agent_engine_location,
            staging_bucket=config.staging_bucket,
        )
        return agent_engines

    def create(
        self,
        *,
        agent_engine: Any,
        display_name: str,
        description: str,
        requirements: Sequence[str],
        env_vars: Mapping[str, str],
        service_account: str | None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "agent_engine": agent_engine,
            "display_name": display_name,
            "description": description,
            "requirements": list(requirements),
            "env_vars": dict(env_vars),
        }
        if service_account:
            kwargs["service_account"] = service_account
        return self._engines.create(**kwargs)

    def get(self, resource_name: str) -> Any:
        return self._engines.get(resource_name)

    def list(self) -> Iterator[Any]:
        return iter(self._engines.list())

    def delete(self, resource_name: str, *, force: bool = False) -> None:
        self._engines.delete(resource_name, force=force)
