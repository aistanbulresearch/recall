from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import pytest

from recall.platform.config import PlatformConfig
from recall.platform.errors import PlatformError
from recall.platform.receipts import COMMON_FIELDS, DEPLOYMENT_RECEIPT_FIELDS
from recall.platform.runtime import AgentRuntime, AgentSpec

ARTIFACT_ID = "4f1a2b3c-0000-4000-8000-000000000002"
REGION = "us-central1"
CONFIG = PlatformConfig(
    project_id="test-project",
    agent_engine_location=REGION,
    model="gemini-3.7-flash",
    model_location="global",
    staging_bucket="gs://recall-agent-engine-staging-test",
)


class FakeResource:
    def __init__(
        self,
        resource_name: str,
        display_name: str,
        update_time: str | None,
        events: Sequence[Mapping[str, Any]] | None = None,
        create_time: str | None = "2026-08-22T05:43:55Z",
    ) -> None:
        self.resource_name = resource_name
        self.display_name = display_name
        self.update_time = update_time
        self.create_time = create_time
        self._events = list(events or [])

    def stream_query(self, *, message: str, user_id: str) -> Iterator[dict[str, Any]]:
        for event in self._events:
            yield {**event, "echo": message, "user_id": user_id}


class UnqueryableResource:
    def __init__(self, resource_name: str, update_time: str) -> None:
        self.resource_name = resource_name
        self.display_name = "no-query"
        self.update_time = update_time
        self.create_time = "2026-08-22T05:43:55Z"


class FakeClient:
    def __init__(self, *, update_time: str | None = "2026-08-22T08:54:12Z") -> None:
        self.resources: dict[str, Any] = {}
        self.deleted: list[str] = []
        self.create_kwargs: dict[str, Any] = {}
        self._update_time = update_time
        self._next_id = 1

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
        self.create_kwargs = {
            "agent_engine": agent_engine,
            "display_name": display_name,
            "description": description,
            "requirements": list(requirements),
            "env_vars": dict(env_vars),
            "service_account": service_account,
        }
        name = f"projects/test-project/locations/{REGION}/reasoningEngines/{self._next_id}"
        self._next_id += 1
        self.resources[name] = FakeResource(
            name,
            display_name,
            self._update_time,
            events=[{"content": {"parts": [{"text": "hello from recall"}]}}],
        )
        return FakeResource(name, display_name, self._update_time)

    def get(self, resource_name: str) -> Any:
        return self.resources.get(resource_name)

    def list(self) -> Iterator[Any]:
        return iter(list(self.resources.values()))

    def delete(self, resource_name: str, *, force: bool = False) -> None:
        self.resources.pop(resource_name, None)
        self.deleted.append(resource_name)


SPEC = AgentSpec(
    display_name="recall-hello-smoke",
    description="day zero managed runtime smoke",
    requirements=("google-cloud-aiplatform[adk,agent_engines]",),
    env_vars={"GOOGLE_CLOUD_LOCATION": "global"},
)


def _runtime(client: FakeClient) -> AgentRuntime:
    return AgentRuntime(client, CONFIG)


def test_deploy_reads_back_region_and_revision() -> None:
    client = FakeClient()
    engine = _runtime(client).deploy(SPEC, agent_engine=object())
    assert engine.region == REGION
    assert engine.revision == "2026-08-22T08:54:12Z"
    assert engine.deployed_at == "2026-08-22T05:43:55Z"
    assert engine.display_name == "recall-hello-smoke"
    assert engine.read_back_at.endswith("Z")
    assert client.create_kwargs["env_vars"] == {"GOOGLE_CLOUD_LOCATION": "global"}


def test_deploy_without_read_back_is_an_error() -> None:
    client = FakeClient()

    def _empty_get(resource_name: str) -> None:
        return None

    client.get = _empty_get  # type: ignore[method-assign]
    with pytest.raises(PlatformError) as excinfo:
        _runtime(client).deploy(SPEC, agent_engine=object())
    assert excinfo.value.code == "runtime_read_back_missing"


def test_missing_revision_blocks_the_receipt() -> None:
    client = FakeClient(update_time=None)
    with pytest.raises(PlatformError) as excinfo:
        _runtime(client).deploy(SPEC, agent_engine=object())
    assert excinfo.value.code == "runtime_revision_missing"


def test_missing_create_time_blocks_the_receipt() -> None:
    client = FakeClient()
    name = "projects/test-project/locations/us-central1/reasoningEngines/9"
    client.resources[name] = FakeResource(
        name, "no-create-time", "2026-08-22T08:54:12Z", create_time=None
    )
    with pytest.raises(PlatformError) as excinfo:
        _runtime(client).read_back(name)
    assert excinfo.value.code == "runtime_create_time_missing"


def test_invoke_returns_raw_events() -> None:
    client = FakeClient()
    runtime = _runtime(client)
    engine = runtime.deploy(SPEC, agent_engine=object())
    events = runtime.invoke(engine.resource_name, message="ping", user_id="smoke")
    assert events[0]["echo"] == "ping"
    assert events[0]["user_id"] == "smoke"


def test_empty_response_is_not_a_successful_call() -> None:
    client = FakeClient()
    runtime = _runtime(client)
    engine = runtime.deploy(SPEC, agent_engine=object())
    client.resources[engine.resource_name] = FakeResource(
        engine.resource_name, "empty", "2026-08-22T08:54:12Z", events=[]
    )
    with pytest.raises(PlatformError) as excinfo:
        runtime.invoke(engine.resource_name, message="ping", user_id="smoke")
    assert excinfo.value.code == "runtime_query_empty"


def test_unqueryable_resource_is_reported_not_assumed_healthy() -> None:
    client = FakeClient()
    runtime = _runtime(client)
    engine = runtime.deploy(SPEC, agent_engine=object())
    client.resources[engine.resource_name] = UnqueryableResource(
        engine.resource_name, "2026-08-22T08:54:12Z"
    )
    with pytest.raises(PlatformError) as excinfo:
        runtime.invoke(engine.resource_name, message="ping", user_id="smoke")
    assert excinfo.value.code == "runtime_query_unsupported"


def test_absence_is_proven_by_listing() -> None:
    client = FakeClient()
    runtime = _runtime(client)
    engine = runtime.deploy(SPEC, agent_engine=object())
    assert runtime.list_resource_names() == [engine.resource_name]
    assert runtime.is_absent(engine.resource_name) is False
    runtime.delete(engine.resource_name)
    assert runtime.list_resource_names() == []
    assert runtime.is_absent(engine.resource_name) is True


def test_receipt_carries_the_read_back_values() -> None:
    client = FakeClient()
    runtime = _runtime(client)
    engine = runtime.deploy(SPEC, agent_engine=object())
    wire = runtime.build_deployment_receipt(
        engine,
        artifact_id=ARTIFACT_ID,
        producer_version="0.1.0",
        source_revision="bc855957",
        deployed_components=["recall-hello-smoke"],
    )
    assert set(wire) == COMMON_FIELDS | DEPLOYMENT_RECEIPT_FIELDS
    runtime_block = wire["runtime"]
    assert runtime_block["service"] == "vertex-ai-agent-engine"  # type: ignore[index]
    assert runtime_block["resource_name"] == engine.resource_name  # type: ignore[index]
    assert runtime_block["revision"] == engine.revision  # type: ignore[index]
    assert runtime_block["region"] == REGION  # type: ignore[index]
    assert wire["status"] == "VALID"


def test_bad_resource_name_is_rejected() -> None:
    client = FakeClient()
    client.resources["bad-name"] = FakeResource(
        "bad-name", "bad", "2026-08-22T08:54:12Z"
    )
    with pytest.raises(PlatformError) as excinfo:
        _runtime(client).read_back("bad-name")
    assert excinfo.value.code == "runtime_resource_name_invalid"
