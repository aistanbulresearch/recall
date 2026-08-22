"""Agent Registry resolution: catalog lookup, bindings, and a validated receipt.

Agent Registry v1 exposes `agents` as list/get/search only; there is no
`agents.create`. An agent therefore reaches the catalog either because the
platform publishes it (`REGISTRY`) or because this lane registers its endpoint as
a `service` (`MANUAL_SERVICE`). A pinned, non-catalog endpoint is
`PINNED_FALLBACK` and is never presented as catalogued.

`RegistryResolutionReceipt` is registered in `recall.contracts.schemas`, so this
module builds it through `recall.contracts.build_artifact` and the result is
parse-validated rather than merely shaped. The Controller is the authoritative
producer; this module supplies the resolution it records.

The contract's payload field set is closed and `extensions` must stay empty, so
`resolution_mode` cannot yet be a first-class field. It is carried losslessly as
a typed reason code until the contracts lane adds the field.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from recall.contracts.builder import build_artifact
from recall.contracts.canonical import canonical_json_bytes, content_hash
from recall.contracts.enums import ArtifactStatus, DataMode, FactState
from recall.ledger.producers import PRODUCER_REGISTRY

from .config import PlatformConfig
from .errors import PlatformError

logger = logging.getLogger(__name__)

REGISTRY_RESOLUTION_VERSION = "1.0.0"
BINDING_FIELDS = frozenset(
    {
        "capability",
        "agent_id",
        "role",
        "revision",
        "manifest_digest",
        "binding_id",
        "region",
        "validation_status",
    }
)


class ResolutionMode(StrEnum):
    """How a capability reached an executable endpoint."""

    REGISTRY = "REGISTRY"
    MANUAL_SERVICE = "MANUAL_SERVICE"
    PINNED_FALLBACK = "PINNED_FALLBACK"


RESOLUTION_MODE_REASON: Mapping[ResolutionMode, str] = {
    ResolutionMode.REGISTRY: "registry_resolution_mode_registry",
    ResolutionMode.MANUAL_SERVICE: "registry_resolution_mode_manual_service",
    ResolutionMode.PINNED_FALLBACK: "registry_resolution_mode_pinned_fallback",
}
UNRESOLVED_REASON = "registry_capability_unresolved"


@dataclass(frozen=True, slots=True)
class CapabilityBinding:
    """One resolved capability. Every field is a non-empty string by contract."""

    capability: str
    agent_id: str
    role: str
    revision: str
    manifest_digest: str
    binding_id: str
    region: str
    validation_status: FactState

    def to_wire(self) -> dict[str, str]:
        wire = {
            "capability": self.capability,
            "agent_id": self.agent_id,
            "role": self.role,
            "revision": self.revision,
            "manifest_digest": self.manifest_digest,
            "binding_id": self.binding_id,
            "region": self.region,
            "validation_status": self.validation_status.value,
        }
        empty = sorted(field for field, value in wire.items() if not value)
        if empty:
            raise PlatformError("registry_binding_field_empty", ",".join(empty))
        if set(wire) != BINDING_FIELDS:
            raise PlatformError("registry_binding_field_set_invalid")
        return wire


def catalog_digest(record: Mapping[str, Any]) -> str:
    """Digest the catalog record a binding was resolved from.

    The digest is over the canonical JSON of the record, so a changed catalog
    entry changes the manifest digest and an operator can recompute it.
    """

    if not record:
        raise PlatformError("registry_catalog_record_empty")
    return content_hash({"record": dict(record), "content_hash": ""})


@dataclass(frozen=True, slots=True)
class RegistryResolution:
    """Outcome of resolving a capability set against the catalog."""

    requested_capabilities: tuple[str, ...]
    bindings: tuple[CapabilityBinding, ...]
    resolution_mode: ResolutionMode
    unresolved: tuple[str, ...]

    @property
    def validation_status(self) -> FactState:
        """A partially resolved fleet is FAIL, never a shorter success."""

        if self.unresolved:
            return FactState.FAIL
        if not self.bindings:
            return FactState.NOT_EVALUATED
        return FactState.PASS

    @property
    def reason_codes(self) -> tuple[str, ...]:
        codes = {RESOLUTION_MODE_REASON[self.resolution_mode]}
        if self.unresolved:
            codes.add(UNRESOLVED_REASON)
        return tuple(sorted(codes))

    def payload(self) -> dict[str, Any]:
        return {
            "requested_capabilities": list(self.requested_capabilities),
            "bindings": [binding.to_wire() for binding in self.bindings],
            "validation_status": self.validation_status.value,
            "reason_codes": list(self.reason_codes),
        }


def resolve_capabilities(
    requested: Sequence[str],
    catalog: Mapping[str, Mapping[str, Any]],
    *,
    resolution_mode: ResolutionMode,
    region: str,
) -> RegistryResolution:
    """Resolve each requested capability against a catalog snapshot.

    A capability with no catalog entry is recorded in `unresolved`; it is never
    dropped from the request, and it never becomes a successful shorter binding
    list.
    """

    ordered = tuple(sorted(set(requested)))
    if not ordered:
        raise PlatformError("registry_no_capability_requested")
    bindings: list[CapabilityBinding] = []
    unresolved: list[str] = []
    for capability in ordered:
        record = catalog.get(capability)
        if not record:
            unresolved.append(capability)
            continue
        missing = sorted(
            field
            for field in ("agent_id", "role", "revision", "binding_id")
            if not record.get(field)
        )
        if missing:
            raise PlatformError(
                "registry_catalog_record_incomplete", f"{capability}:{missing}"
            )
        bindings.append(
            CapabilityBinding(
                capability=capability,
                agent_id=str(record["agent_id"]),
                role=str(record["role"]),
                revision=str(record["revision"]),
                manifest_digest=catalog_digest(record),
                binding_id=str(record["binding_id"]),
                region=str(record.get("region") or region),
                validation_status=FactState.PASS,
            )
        )
    return RegistryResolution(
        requested_capabilities=ordered,
        bindings=tuple(bindings),
        resolution_mode=resolution_mode,
        unresolved=tuple(unresolved),
    )


def build_registry_resolution_receipt(
    resolution: RegistryResolution,
    *,
    artifact_id: str,
    run_id: str,
    case_id: str | None,
    producer_version: str,
    created_at: str,
    data_mode: DataMode = DataMode.SYNTHETIC,
) -> dict[str, Any]:
    """Build the receipt through the registered parser so it is validated, not assumed.

    The Controller is the authoritative producer of this contract; this helper
    exists so the platform lane and the Controller emit identical bytes.
    """

    status = (
        ArtifactStatus.VALID
        if resolution.validation_status is FactState.PASS
        else ArtifactStatus.INCOMPLETE
    )
    return build_artifact(
        schema_name="RegistryResolutionReceipt",
        schema_version=REGISTRY_RESOLUTION_VERSION,
        artifact_id=artifact_id,
        case_id=case_id,
        run_id=run_id,
        producer={
            "component": PRODUCER_REGISTRY.authority_label(
                "RegistryResolutionReceipt"
            ),
            "version": producer_version,
            "identity": "controller",
        },
        created_at=created_at,
        input_artifact_ids=(),
        data_mode=data_mode,
        status=status,
        payload=resolution.payload(),
        authorized_producers=PRODUCER_REGISTRY,
    )


class RegistryClient(Protocol):
    """Agent Registry surface used by this lane."""

    def list_agents(self, location: str) -> Mapping[str, Any]: ...

    def list_services(self, location: str) -> Mapping[str, Any]: ...

    def list_bindings(self, location: str) -> Mapping[str, Any]: ...

    def create_service(
        self, location: str, service_id: str, body: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...

    def fetch_available_bindings(
        self, location: str, source_identifier: str
    ) -> Mapping[str, Any]: ...


def observe_catalog(client: RegistryClient, location: str) -> dict[str, Any]:
    """Record catalog contents, distinguishing empty from unreachable."""

    observation: dict[str, Any] = {"location": location}
    for key, call, item_key in (
        ("agents", client.list_agents, "agents"),
        ("services", client.list_services, "services"),
        ("bindings", client.list_bindings, "bindings"),
    ):
        try:
            payload = call(location)
        except PlatformError as exc:
            observation[key] = {
                "status": "DEGRADED",
                "reason_code": exc.code,
                "detail": exc.detail,
            }
            continue
        items = payload.get(item_key)
        listed = items if isinstance(items, list) else []
        observation[key] = {
            "status": "EMPTY" if not listed else "OBSERVED",
            "count": len(listed),
        }
    return observation


def engine_is_catalogued(
    client: RegistryClient, location: str, resource_name: str
) -> bool:
    """Answer whether a deployed engine actually appears in the catalog.

    A deployment that cannot be found here is not catalogued, whatever the
    deployment call returned.
    """

    engine_id = resource_name.rsplit("/", 1)[-1]
    payload = client.list_agents(location)
    agents = payload.get("agents")
    if not isinstance(agents, list):
        return False
    return any(engine_id in str(agent.get("name", "")) for agent in agents)


def agent_engine_service_body(
    *,
    display_name: str,
    description: str,
    url: str,
    protocol_binding: str = "HTTP_JSON",
) -> dict[str, Any]:
    """Build a `services.create` body registering an endpoint in the catalog."""

    if not url.startswith("https://"):
        raise PlatformError("registry_service_url_insecure", url)
    return {
        "displayName": display_name,
        "description": description,
        "agentSpec": {"type": "NO_SPEC"},
        "interfaces": [{"url": url, "protocolBinding": protocol_binding}],
    }


class RestRegistryClient:
    """Agent Registry client over REST with application default credentials."""

    BASE = "https://agentregistry.googleapis.com/v1"

    def __init__(self, config: PlatformConfig) -> None:
        self._project = config.project_id
        self._session = self._authorised_session()

    @staticmethod
    def _authorised_session() -> Any:
        try:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise PlatformError("registry_sdk_unavailable", str(exc)) from exc
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return AuthorizedSession(credentials)

    def _parent(self, location: str) -> str:
        return f"projects/{self._project}/locations/{location}"

    def _request(
        self,
        method: str,
        location: str,
        resource: str,
        *,
        params: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        url = f"{self.BASE}/{self._parent(location)}/{resource}"
        response = self._session.request(
            method, url, params=dict(params or {}), json=body, timeout=30
        )
        if response.status_code != 200:
            raise PlatformError(
                "registry_call_failed", f"{resource}:{response.status_code}"
            )
        return response.json()

    def list_agents(self, location: str) -> Mapping[str, Any]:
        return self._request("GET", location, "agents", params={"pageSize": "100"})

    def list_services(self, location: str) -> Mapping[str, Any]:
        return self._request("GET", location, "services")

    def list_bindings(self, location: str) -> Mapping[str, Any]:
        return self._request("GET", location, "bindings")

    def create_service(
        self, location: str, service_id: str, body: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return self._request(
            "POST", location, "services", params={"serviceId": service_id}, body=body
        )

    def fetch_available_bindings(
        self, location: str, source_identifier: str
    ) -> Mapping[str, Any]:
        return self._request(
            "GET",
            location,
            "bindings:fetchAvailable",
            params={"sourceIdentifier": source_identifier},
        )


def catalog_from_agents(
    payload: Mapping[str, Any], capability_by_agent: Mapping[str, str]
) -> dict[str, dict[str, Any]]:
    """Project a live `agents.list` response into a resolution catalog."""

    agents = payload.get("agents")
    if not isinstance(agents, list):
        raise PlatformError("registry_agents_payload_invalid")
    catalog: dict[str, dict[str, Any]] = {}
    for agent in agents:
        agent_id = str(agent.get("agentId") or agent.get("name") or "")
        capability = capability_by_agent.get(agent_id)
        if not capability:
            continue
        catalog[capability] = {
            "agent_id": agent_id,
            "role": capability,
            "revision": str(agent.get("version") or agent.get("updateTime") or ""),
            "binding_id": str(agent.get("uid") or agent.get("name") or ""),
            "region": str(agent.get("location") or ""),
            "card": agent.get("card") or {},
        }
    return catalog


def canonical_catalog_bytes(catalog: Mapping[str, Mapping[str, Any]]) -> bytes:
    """Expose the canonical encoding so an auditor can recompute a digest."""

    return canonical_json_bytes(dict(catalog))


def iter_binding_wires(
    bindings: Iterable[CapabilityBinding],
) -> list[dict[str, str]]:
    return [binding.to_wire() for binding in bindings]
