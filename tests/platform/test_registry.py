from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from recall.contracts.enums import FactState
from recall.contracts.errors import ContractError
from recall.contracts.models import parse_artifact
from recall.contracts.schemas import SCHEMAS
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
    registered_contract,
    resolution_mode_is_a_field,
    resolve_capabilities,
    runtime_identity,
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
    # A clean resolution reports no problem. Before the contract carried
    # resolution_mode, the mode rode along here as a transitional reason code.
    if resolution_mode_is_a_field():
        assert resolution.reason_codes == ()
    else:
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
def test_resolution_mode_is_never_lost(mode: ResolutionMode) -> None:
    """The mode is recoverable at every contract version.

    From 1.1.0 it is a payload field; before that it travelled as a typed reason
    code. Either way it must be readable from the emitted resolution.
    """

    resolution = resolve_capabilities(
        list(CATALOG), CATALOG, resolution_mode=mode, region=REGION
    )
    payload = resolution.payload()
    if resolution_mode_is_a_field():
        assert payload["resolution_mode"] == mode.value
        assert RESOLUTION_MODE_REASON[mode] not in resolution.reason_codes
    else:
        assert RESOLUTION_MODE_REASON[mode] in resolution.reason_codes
        assert "resolution_mode" not in payload


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


ENGINE_ID = "1111222233334444"  # synthetic stand-in for the observed engine id

# Shape observed live on 2026-08-22: the catalog name is a registry-assigned id
# that never contains the engine id, so the runtime link must come from agentId
# and the RuntimeReference attribute.
LIVE_AGENT_RECORD: dict[str, Any] = {
    "name": "projects/p/locations/us-central1/agents/agentregistry-00000000-0000-0000-9c4a-f3973fb10599",
    "agentId": (
        "urn:agent:projects-000:projects:000:locations:us-central1:aiplatform"
        f":reasoningEngines:{ENGINE_ID}"
    ),
    "location": "us-central1",
    "displayName": "recall-hello-smoke",
    "uid": "agentregistry-00000000-0000-0000-9c4a-f3973fb10599",
    "updateTime": "2026-08-22T14:38:21.116595Z",
    "protocols": [
        {
            "type": "CUSTOM",
            "interfaces": [
                {
                    "url": f"https://us-central1-aiplatform.googleapis.com/v1/projects/p/locations/us-central1/reasoningEngines/{ENGINE_ID}:query",
                    "protocolBinding": "HTTP_JSON",
                },
                {
                    "url": f"https://us-central1-aiplatform.googleapis.com/v1/projects/p/locations/us-central1/reasoningEngines/{ENGINE_ID}:streamQuery",
                    "protocolBinding": "HTTP_JSON",
                },
            ],
        }
    ],
    "attributes": {
        "agentregistry.googleapis.com/system/Framework": {"framework": "google-adk"},
        "agentregistry.googleapis.com/system/RuntimeReference": {
            "uri": f"//aiplatform.googleapis.com/projects/p/locations/us-central1/reasoningEngines/{ENGINE_ID}"
        },
        "agentregistry.googleapis.com/system/RuntimeIdentity": {
            "principal": "sa://recall-sa-watcher@p.iam.gserviceaccount.com"
        },
    },
}
RESOURCE = f"projects/p/locations/us-central1/reasoningEngines/{ENGINE_ID}"


def test_engine_absent_from_catalog_is_not_catalogued() -> None:
    client = FakeRegistryClient([{"name": "projects/p/locations/us-central1/agents/x"}])
    assert engine_is_catalogued(client, REGION, RESOURCE) is False


def test_registry_name_alone_never_proves_cataloguing() -> None:
    # The registry-assigned name must not be mistaken for the runtime link.
    stripped = {k: v for k, v in LIVE_AGENT_RECORD.items() if k not in ("agentId", "attributes")}
    assert engine_is_catalogued(FakeRegistryClient([stripped]), REGION, RESOURCE) is False


def test_live_catalog_record_is_recognised() -> None:
    client = FakeRegistryClient([LIVE_AGENT_RECORD])
    assert engine_is_catalogued(client, REGION, RESOURCE) is True


def test_runtime_reference_alone_is_enough() -> None:
    record = {k: v for k, v in LIVE_AGENT_RECORD.items() if k != "agentId"}
    assert engine_is_catalogued(FakeRegistryClient([record]), REGION, RESOURCE) is True


def test_catalog_reports_the_per_role_service_account() -> None:
    assert (
        runtime_identity(LIVE_AGENT_RECORD)
        == "sa://recall-sa-watcher@p.iam.gserviceaccount.com"
    )
    assert runtime_identity({"attributes": {}}) is None


def test_live_record_projects_into_a_resolvable_catalog() -> None:
    catalog = catalog_from_agents(
        {"agents": [LIVE_AGENT_RECORD]}, {"recall-hello-smoke": "evidence.watch"}
    )
    entry = catalog["evidence.watch"]
    assert entry["runtime_identity"].endswith("recall-sa-watcher@p.iam.gserviceaccount.com")
    assert len(entry["endpoints"]) == 2
    assert all(url.startswith("https://") for url in entry["endpoints"])


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


# --- contract version alignment (RegistryResolutionReceipt 1.1.0) -------------


def test_emitted_version_matches_the_registered_contract() -> None:
    """The receipt must never declare a version the Ledger does not validate."""

    version, _fields = registered_contract()
    wire = build_registry_resolution_receipt(
        _resolution(),
        artifact_id=ARTIFACT_ID,
        run_id=RUN_ID,
        case_id=None,
        producer_version="0.1.0",
        created_at="2026-08-23T10:00:00Z",
    )
    assert wire["schema_version"] == version
    parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)


def test_payload_field_set_matches_the_registered_contract() -> None:
    _version, fields = registered_contract()
    payload_keys = set(_resolution().payload())
    assert payload_keys == set(fields)


def _simulate_registry(monkeypatch: Any, version: str, fields: set[str]) -> None:
    """Point the emitter at a registry entry with the given version and fields."""

    class _StubPayload:
        """Stands in for the contracts-lane payload object at that version."""

        def __init__(self, value: Mapping[str, Any]) -> None:
            self._fields = {key: value[key] for key in fields if key in value}

        def to_wire(self) -> dict[str, Any]:
            return dict(self._fields)

    def _permissive_parser(value: Mapping[str, Any]) -> Any:
        return _StubPayload(value)

    monkeypatch.setitem(
        SCHEMAS,
        "RegistryResolutionReceipt",
        (version, frozenset(fields), _permissive_parser, True),
    )


CORE_110_FIELDS = {
    "requested_capabilities",
    "bindings",
    "resolution_mode",
    "validation_status",
    "reason_codes",
}


def test_against_the_core_1_1_0_contract_the_mode_is_a_payload_field(
    monkeypatch: Any,
) -> None:
    _simulate_registry(monkeypatch, "1.1.0", CORE_110_FIELDS)
    resolution = resolve_capabilities(
        list(CATALOG),
        CATALOG,
        resolution_mode=ResolutionMode.MANUAL_SERVICE,
        region=REGION,
    )
    payload = resolution.payload()
    assert payload["resolution_mode"] == "MANUAL_SERVICE"
    assert set(payload) == CORE_110_FIELDS


def test_against_1_1_0_the_transitional_reason_code_is_dropped(
    monkeypatch: Any,
) -> None:
    _simulate_registry(monkeypatch, "1.1.0", CORE_110_FIELDS)
    resolution = _resolution()
    assert resolution.reason_codes == ()
    assert not any(
        code.startswith("registry_resolution_mode_") for code in resolution.reason_codes
    )


def test_against_1_1_0_unresolved_reason_still_reported(monkeypatch: Any) -> None:
    _simulate_registry(monkeypatch, "1.1.0", CORE_110_FIELDS)
    resolution = _resolution([*CATALOG, "evidence.audit"])
    assert resolution.reason_codes == (UNRESOLVED_REASON,)
    assert resolution.payload()["resolution_mode"] == "REGISTRY"


def test_against_1_1_0_the_receipt_declares_1_1_0(monkeypatch: Any) -> None:
    _simulate_registry(monkeypatch, "1.1.0", CORE_110_FIELDS)
    wire = build_registry_resolution_receipt(
        _resolution(),
        artifact_id=ARTIFACT_ID,
        run_id=RUN_ID,
        case_id=None,
        producer_version="0.1.0",
        created_at="2026-08-23T10:00:00Z",
    )
    assert wire["schema_version"] == "1.1.0"
    assert wire["resolution_mode"] == "REGISTRY"


@pytest.mark.parametrize("mode", list(ResolutionMode))
def test_every_mode_round_trips_as_a_field(monkeypatch: Any, mode: Any) -> None:
    _simulate_registry(monkeypatch, "1.1.0", CORE_110_FIELDS)
    resolution = resolve_capabilities(
        list(CATALOG), CATALOG, resolution_mode=mode, region=REGION
    )
    assert resolution.payload()["resolution_mode"] == mode.value


def test_mode_values_match_the_closed_contract_enum() -> None:
    assert {mode.value for mode in ResolutionMode} == {
        "REGISTRY",
        "MANUAL_SERVICE",
        "PINNED_FALLBACK",
    }


def test_unregistered_schema_fails_loudly(monkeypatch: Any) -> None:
    monkeypatch.delitem(SCHEMAS, "RegistryResolutionReceipt")
    with pytest.raises(PlatformError) as excinfo:
        registered_contract()
    assert excinfo.value.code == "registry_schema_unregistered"
