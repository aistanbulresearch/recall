from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from recall.contracts.enums import FactState
from recall.contracts.errors import ContractError
from recall.contracts.models import parse_artifact
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.platform.errors import PlatformError
from recall.platform.registry import (
    BINDING_FIELDS,
    RESOLUTION_MODE_REASON,
    UNRESOLVED_REASON,
    ResolutionMode,
    agent_engine_service_body,
    build_registry_resolution_receipt,
    catalog_digest,
    catalog_from_agents,
    engine_is_catalogued,
    observe_catalog,
    resolve_capabilities,
)

REGION = "us-central1"
ARTIFACT_ID = "4f1a2b3c-0000-4000-8000-000000000003"
RUN_ID = "4f1a2b3c-0000-4000-8000-0000000000ff"

CATALOG: dict[str, dict[str, Any]] = {
    "evidence.watch": {
        "agent_id": "recall-watcher",
        "role": "EVIDENCE_WATCHER",
        "revision": "2026-08-22T05:49:16Z",
        "binding_id": "binding-watcher-1",
        "region": REGION,
    },
    "evidence.assess": {
        "agent_id": "recall-assessor",
        "role": "EVIDENCE_ASSESSOR",
        "revision": "2026-08-22T05:49:20Z",
        "binding_id": "binding-assessor-1",
        "region": REGION,
    },
}


def _resolution(requested: list[str] | None = None):
    return resolve_capabilities(
        requested or list(CATALOG),
        CATALOG,
        resolution_mode=ResolutionMode.REGISTRY,
        region=REGION,
    )


def test_full_resolution_passes() -> None:
    resolution = _resolution()
    assert resolution.validation_status is FactState.PASS
    assert len(resolution.bindings) == 2
    assert resolution.unresolved == ()
    assert resolution.reason_codes == (
        RESOLUTION_MODE_REASON[ResolutionMode.REGISTRY],
    )


def test_binding_wire_matches_the_contract_field_set() -> None:
    binding = _resolution().bindings[0].to_wire()
    assert set(binding) == BINDING_FIELDS
    assert all(value for value in binding.values())


def test_unresolved_capability_fails_and_is_not_dropped() -> None:
    resolution = _resolution([*CATALOG, "evidence.audit"])
    assert resolution.validation_status is FactState.FAIL
    assert resolution.unresolved == ("evidence.audit",)
    assert "evidence.audit" in resolution.requested_capabilities
    assert UNRESOLVED_REASON in resolution.reason_codes


def test_incomplete_catalog_record_is_an_error() -> None:
    broken = {"evidence.watch": dict(CATALOG["evidence.watch"], revision="")}
    with pytest.raises(PlatformError) as excinfo:
        resolve_capabilities(
            ["evidence.watch"],
            broken,
            resolution_mode=ResolutionMode.REGISTRY,
            region=REGION,
        )
    assert excinfo.value.code == "registry_catalog_record_incomplete"


def test_empty_request_is_rejected() -> None:
    with pytest.raises(PlatformError) as excinfo:
        resolve_capabilities(
            [], CATALOG, resolution_mode=ResolutionMode.REGISTRY, region=REGION
        )
    assert excinfo.value.code == "registry_no_capability_requested"


def test_manifest_digest_tracks_the_catalog_record() -> None:
    first = catalog_digest(CATALOG["evidence.watch"])
    changed = catalog_digest(dict(CATALOG["evidence.watch"], revision="other"))
    assert len(first) == 64
    assert first != changed
    with pytest.raises(PlatformError):
        catalog_digest({})


@pytest.mark.parametrize("mode", list(ResolutionMode))
def test_resolution_mode_survives_as_a_typed_reason_code(mode: ResolutionMode) -> None:
    resolution = resolve_capabilities(
        list(CATALOG), CATALOG, resolution_mode=mode, region=REGION
    )
    assert RESOLUTION_MODE_REASON[mode] in resolution.reason_codes


def test_receipt_is_accepted_by_the_registered_parser() -> None:
    wire = build_registry_resolution_receipt(
        _resolution(),
        artifact_id=ARTIFACT_ID,
        run_id=RUN_ID,
        case_id=None,
        producer_version="0.1.0",
        created_at="2026-08-22T06:20:00Z",
    )
    artifact = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
    assert artifact.schema_name == "RegistryResolutionReceipt"
    assert artifact.status.value == "VALID"
    assert wire["validation_status"] == "PASS"


def test_partial_resolution_receipt_is_incomplete_not_valid() -> None:
    wire = build_registry_resolution_receipt(
        _resolution([*CATALOG, "evidence.audit"]),
        artifact_id=ARTIFACT_ID,
        run_id=RUN_ID,
        case_id=None,
        producer_version="0.1.0",
        created_at="2026-08-22T06:20:00Z",
    )
    assert wire["status"] == "INCOMPLETE"
    assert wire["validation_status"] == "FAIL"
    parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)


def test_receipt_requires_a_run_id() -> None:
    with pytest.raises(ContractError) as excinfo:
        build_registry_resolution_receipt(
            _resolution(),
            artifact_id=ARTIFACT_ID,
            run_id=None,  # type: ignore[arg-type]
            case_id=None,
            producer_version="0.1.0",
            created_at="2026-08-22T06:20:00Z",
        )
    assert excinfo.value.code == "contract_required_value_missing"


class FakeRegistryClient:
    def __init__(self, agents: list[dict[str, Any]], fail: str | None = None) -> None:
        self._agents = agents
        self._fail = fail

    def list_agents(self, location: str) -> Mapping[str, Any]:
        if self._fail == "agents":
            raise PlatformError("registry_call_failed", "agents:403")
        return {"agents": self._agents}

    def list_services(self, location: str) -> Mapping[str, Any]:
        return {}

    def list_bindings(self, location: str) -> Mapping[str, Any]:
        return {}

    def create_service(
        self, location: str, service_id: str, body: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return {"name": f"services/{service_id}"}

    def fetch_available_bindings(
        self, location: str, source_identifier: str
    ) -> Mapping[str, Any]:
        return {}


def test_catalog_observation_separates_empty_from_unreachable() -> None:
    populated = observe_catalog(FakeRegistryClient([{"name": "a"}]), REGION)
    assert populated["agents"] == {"status": "OBSERVED", "count": 1}
    assert populated["services"] == {"status": "EMPTY", "count": 0}

    degraded = observe_catalog(FakeRegistryClient([], fail="agents"), REGION)
    assert degraded["agents"]["status"] == "DEGRADED"
    assert degraded["agents"]["detail"] == "agents:403"


def test_engine_absent_from_catalog_is_not_catalogued() -> None:
    client = FakeRegistryClient([{"name": "projects/p/locations/us-central1/agents/x"}])
    resource = "projects/p/locations/us-central1/reasoningEngines/3891525143687593984"
    assert engine_is_catalogued(client, REGION, resource) is False


def test_engine_present_in_catalog_is_catalogued() -> None:
    engine_id = "3891525143687593984"
    client = FakeRegistryClient(
        [{"name": f"projects/p/locations/us-central1/agents/{engine_id}"}]
    )
    resource = f"projects/p/locations/us-central1/reasoningEngines/{engine_id}"
    assert engine_is_catalogued(client, REGION, resource) is True


def test_catalog_projection_keeps_only_mapped_agents() -> None:
    payload = {
        "agents": [
            {
                "agentId": "urn:agent:recall:watcher",
                "version": "1",
                "uid": "uid-1",
                "location": REGION,
            },
            {"agentId": "urn:agent:googleapis.com:workspaceagent", "version": "1"},
        ]
    }
    catalog = catalog_from_agents(
        payload, {"urn:agent:recall:watcher": "evidence.watch"}
    )
    assert list(catalog) == ["evidence.watch"]
    assert catalog["evidence.watch"]["binding_id"] == "uid-1"


def test_service_body_refuses_an_insecure_endpoint() -> None:
    with pytest.raises(PlatformError) as excinfo:
        agent_engine_service_body(
            display_name="recall-watcher",
            description="d",
            url="http://example.invalid",
        )
    assert excinfo.value.code == "registry_service_url_insecure"


def test_service_body_shape() -> None:
    body = agent_engine_service_body(
        display_name="recall-watcher",
        description="Recall evidence watcher endpoint",
        url="https://us-central1-aiplatform.googleapis.com/v1/x:streamQuery",
    )
    assert body["agentSpec"] == {"type": "NO_SPEC"}
    assert body["interfaces"][0]["protocolBinding"] == "HTTP_JSON"
