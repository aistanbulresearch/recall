from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from types import SimpleNamespace
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
        resource_limits: Mapping[str, str] | None = None,
    ) -> None:
        self.resource_name = resource_name
        self.display_name = display_name
        self.update_time = update_time
        self.create_time = create_time
        self.resource_limits = resource_limits
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
        resource_limits: Mapping[str, str] | None = None,
        extra_packages: Sequence[str] = (),
    ) -> Any:
        self.create_kwargs = {
            "agent_engine": agent_engine,
            "display_name": display_name,
            "description": description,
            "requirements": list(requirements),
            "env_vars": dict(env_vars),
            "service_account": service_account,
            "extra_packages": tuple(extra_packages),
            "resource_limits": dict(resource_limits) if resource_limits else None,
        }
        name = f"projects/test-project/locations/{REGION}/reasoningEngines/{self._next_id}"
        self._next_id += 1
        # The runtime reports back the shape it was asked for.
        self.resources[name] = FakeResource(
            name,
            display_name,
            self._update_time,
            events=[{"content": {"parts": [{"text": "hello from recall"}]}}],
            resource_limits=dict(resource_limits) if resource_limits else None,
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


class FakeHttpSession:
    """Records the request so header injection can be asserted, not assumed."""

    def __init__(self, status: int = 200, body: str = "") -> None:
        self.status = status
        self.body = body
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        self.calls.append({"method": method, "url": url, **kwargs})

        class _Response:
            status_code = self.status
            text = self.body

        return _Response()


SSE_BODY = (
    'data: {"content": {"parts": [{"text": "ready"}]}, "author": "watcher"}\n'
    "\n"
    'data: {"content": {"parts": [{"text": "done"}]}, "author": "watcher"}\n'
    "data: [DONE]\n"
)
TRACED_RESOURCE = "projects/p/locations/us-central1/reasoningEngines/42"


def _invoker(session: FakeHttpSession) -> Any:
    from recall.platform.runtime import TracedRuntimeInvoker

    return TracedRuntimeInvoker(CONFIG, session=session)


def test_traced_invoke_injects_a_w3c_traceparent() -> None:
    session = FakeHttpSession(body=SSE_BODY)
    result = _invoker(session).invoke(
        TRACED_RESOURCE, message="ping", user_id="smoke"
    )
    header = session.calls[0]["headers"]["traceparent"]
    assert header == f"00-{result.trace_id}-{result.span_id}-01"
    assert len(result.trace_id) == 32
    assert len(result.span_id) == 16


def test_caller_supplied_trace_id_is_used_unchanged() -> None:
    session = FakeHttpSession(body=SSE_BODY)
    trace = "0af7651916cd43dd8448eb211c80319c"
    result = _invoker(session).invoke(
        TRACED_RESOURCE, message="ping", user_id="smoke", trace_id=trace
    )
    assert result.trace_id == trace
    assert trace in session.calls[0]["headers"]["traceparent"]


def test_traced_invoke_targets_the_published_stream_query_endpoint() -> None:
    session = FakeHttpSession(body=SSE_BODY)
    _invoker(session).invoke(TRACED_RESOURCE, message="ping", user_id="smoke")
    url = session.calls[0]["url"]
    assert url.startswith("https://us-central1-aiplatform.googleapis.com/v1/")
    assert url.endswith(f"{TRACED_RESOURCE}:streamQuery?alt=sse")
    assert session.calls[0]["json"]["class_method"] == "stream_query"


def test_sse_events_are_parsed_and_done_marker_dropped() -> None:
    session = FakeHttpSession(body=SSE_BODY)
    result = _invoker(session).invoke(
        TRACED_RESOURCE, message="ping", user_id="smoke"
    )
    assert len(result.events) == 2
    assert result.events[0]["author"] == "watcher"


def test_non_200_response_fails_loudly() -> None:
    session = FakeHttpSession(status=503, body="")
    with pytest.raises(PlatformError) as excinfo:
        _invoker(session).invoke(TRACED_RESOURCE, message="ping", user_id="smoke")
    assert excinfo.value.code == "runtime_query_failed"


def test_empty_stream_is_not_a_successful_call() -> None:
    session = FakeHttpSession(body="data: [DONE]\n")
    with pytest.raises(PlatformError) as excinfo:
        _invoker(session).invoke(TRACED_RESOURCE, message="ping", user_id="smoke")
    assert excinfo.value.code == "runtime_query_empty"


def test_malformed_trace_id_is_refused_before_the_call() -> None:
    session = FakeHttpSession(body=SSE_BODY)
    with pytest.raises(PlatformError) as excinfo:
        _invoker(session).invoke(
            TRACED_RESOURCE, message="ping", user_id="smoke", trace_id="nope"
        )
    assert excinfo.value.code == "trace_id_invalid"
    assert session.calls == []


PINNED_SPEC = AgentSpec(
    display_name="recall-watcher",
    description="pinned shape",
    requirements=("google-cloud-aiplatform[adk,agent_engines]",),
    env_vars={"GOOGLE_CLOUD_LOCATION": "global"},
    resource_limits={"cpu": "1", "memory": "4Gi"},
)


def test_pinned_instance_shape_reaches_the_create_call() -> None:
    client = FakeClient()
    _runtime(client).deploy(PINNED_SPEC, agent_engine=object())
    assert client.create_kwargs["resource_limits"] == {"cpu": "1", "memory": "4Gi"}


def test_instance_shape_is_read_back_from_the_engine() -> None:
    client = FakeClient()
    engine = _runtime(client).deploy(PINNED_SPEC, agent_engine=object())
    assert engine.resource_limits == {"cpu": "1", "memory": "4Gi"}


def test_unpinned_spec_sends_no_shape_and_reads_back_none() -> None:
    client = FakeClient()
    engine = _runtime(client).deploy(SPEC, agent_engine=object())
    assert client.create_kwargs["resource_limits"] is None
    assert engine.resource_limits is None


# --- the SDK binding is global, and this process does not own it alone --------
#
# On 2026-08-25 every fleet engine create failed 403 CONSUMER_INVALID against
# project recall-local-smoke at locations/global. Our client had called
# vertexai.init() with the right project, region and staging bucket at
# construction. Between that and the create, AgentBundle.to_adk_app() called
# vertexai.init() again -- project from GOOGLE_CLOUD_PROJECT with a hardcoded
# smoke fallback, location from GOOGLE_CLOUD_LOCATION, which build_agent_bundle
# had just set to "global" for the model -- silently repointing the SDK and
# dropping the staging bucket.
#
# Binding once at construction is an assumption about other people's code.
# Binding at the point of use is an invariant we hold ourselves.


def test_the_sdk_binding_is_reasserted_before_every_create() -> None:
    from recall.platform.runtime import VertexAgentEngineClient

    bindings: list[Any] = []

    class FakeEngines:
        created: list[dict[str, Any]] = []

        @staticmethod
        def create(**kwargs: Any) -> Any:
            FakeEngines.created.append(kwargs)
            return SimpleNamespace(
                resource_name="projects/p/locations/us-central1/reasoningEngines/1"
            )

    def fake_initialise(config: Any) -> Any:
        bindings.append(config)
        return FakeEngines

    original = VertexAgentEngineClient._initialise
    VertexAgentEngineClient._initialise = staticmethod(fake_initialise)  # type: ignore[method-assign]
    try:
        client = VertexAgentEngineClient(CONFIG)
        assert len(bindings) == 1, "constructing the client binds once"

        client.create(
            agent_engine=object(),
            display_name="recall-watcher",
            description="d",
            requirements=[],
            env_vars={},
            service_account=None,
        )
        assert len(bindings) == 2, (
            "the binding must be re-asserted at the point of use, or a third "
            "party's vertexai.init() between construction and create silently "
            "redirects the deploy"
        )
        assert bindings[-1] is CONFIG
    finally:
        VertexAgentEngineClient._initialise = original  # type: ignore[method-assign]
