from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest

from recall.contracts.enums import AgentRole
from recall.platform.config import PlatformConfig
from recall.platform.errors import PlatformError
from recall.platform.fleet import (
    CONTROLLER_SPAN,
    FLEET_MEMBERS,
    FLEET_REQUIREMENTS,
    FLEET_RESOURCE_LIMITS,
    AgentCall,
    FleetDeployment,
    GatewayBinding,
    expected_agent_author,
    verify_fleet_identity,
    fleet_identity_is_distinct,
    observed_authors,
    deploy_fleet,
    deploy_overlap_seconds,
    fleet_env_vars,
    fleet_is_complete,
    fleet_spec,
    fleet_summary,
    fleet_trace_is_complete,
    record_fleet_run,
    verify_fleet_catalogued,
)
from recall.platform.observability import TraceRecorder
from recall.platform.runtime import AgentRuntime, DeployedEngine

REGION = "us-central1"
TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
CONFIG = PlatformConfig(
    project_id="test-project",
    agent_engine_location=REGION,
    model="gemini-3.7-flash",
    model_location="global",
    staging_bucket="gs://recall-agent-engine-staging-test",
)

# The gateway an agent is allowed to know about. Threaded explicitly so the
# tests assert the deployed environment carries it, rather than trusting that
# something further down resolved it.
GATEWAY = GatewayBinding(
    url="https://recall-tool-gateway-test.a.run.app",
    audience="https://recall-tool-gateway-test.a.run.app",
)


def _engine(name: str) -> DeployedEngine:
    return DeployedEngine(
        resource_name=f"projects/test-project/locations/{REGION}/reasoningEngines/{name}",
        display_name=name,
        region=REGION,
        revision="2026-08-24T09:00:00Z",
        deployed_at="2026-08-24T08:59:00Z",
        read_back_at="2026-08-24T09:00:10Z",
    )


def test_fleet_covers_the_three_agent_roles() -> None:
    roles = [member.role for member in FLEET_MEMBERS]
    assert roles == [
        AgentRole.EVIDENCE_WATCHER,
        AgentRole.EVIDENCE_ASSESSOR,
        AgentRole.CITATION_AUDITOR,
    ]
    assert len({member.display_name for member in FLEET_MEMBERS}) == 3


def test_each_member_runs_under_its_own_service_account() -> None:
    accounts = {member.service_account_id for member in FLEET_MEMBERS}
    assert accounts == {"recall-sa-watcher", "recall-sa-assessor", "recall-sa-auditor"}
    for member in FLEET_MEMBERS:
        spec = fleet_spec(CONFIG, member, gateway=GATEWAY)
        assert spec.service_account is not None
        assert spec.service_account.startswith(member.service_account_id + "@")


def test_genai_instrumentation_is_always_deployed() -> None:
    assert "opentelemetry-instrumentation-google-genai" in FLEET_REQUIREMENTS
    for member in FLEET_MEMBERS:
        assert fleet_spec(CONFIG, member, gateway=GATEWAY).requirements == FLEET_REQUIREMENTS


def test_telemetry_is_enabled_by_environment() -> None:
    env = fleet_env_vars(CONFIG, "recall-watcher", gateway=GATEWAY)
    assert env["GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"] == "true"
    assert env["OTEL_SEMCONV_STABILITY_OPT_IN"] == "gen_ai_latest_experimental"
    assert env["OTEL_SERVICE_NAME"] == "recall-watcher"


def test_prompt_content_never_enters_spans() -> None:
    env = fleet_env_vars(CONFIG, "recall-watcher", gateway=GATEWAY)
    assert env["ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS"] == "false"
    assert "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT" not in env


def test_service_name_is_per_role() -> None:
    names = {
        fleet_env_vars(CONFIG, member.display_name, gateway=GATEWAY)["OTEL_SERVICE_NAME"]
        for member in FLEET_MEMBERS
    }
    assert len(names) == 3


def test_blank_service_name_is_refused() -> None:
    with pytest.raises(PlatformError) as excinfo:
        fleet_env_vars(CONFIG, "", gateway=GATEWAY)
    assert excinfo.value.code == "fleet_service_name_missing"


class RecordingRuntime(AgentRuntime):
    """Runtime stub that records concurrency and can fail a chosen member."""

    def __init__(self, fail_display_name: str | None = None) -> None:
        self.active = 0
        self.peak = 0
        self._lock = threading.Lock()
        self.specs: list[Any] = []
        self._fail = fail_display_name

    def deploy(self, spec: Any, agent_engine: Any) -> DeployedEngine:  # type: ignore[override]
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.specs.append(spec)
        try:
            threading.Event().wait(0.05)
            if spec.display_name == self._fail:
                raise RuntimeError("boom")
            return _engine(spec.display_name)
        finally:
            with self._lock:
                self.active -= 1


def test_members_deploy_concurrently_not_one_after_another() -> None:
    runtime = RecordingRuntime()
    results = deploy_fleet(runtime, CONFIG, lambda member: object(), gateway=GATEWAY)
    assert len(results) == 3
    assert runtime.peak > 1, "sequential deploys would take three times as long"
    assert fleet_is_complete(results) is True


def test_one_failed_member_does_not_hide_the_others() -> None:
    runtime = RecordingRuntime(fail_display_name="recall-assessor")
    results = deploy_fleet(runtime, CONFIG, lambda member: object(), gateway=GATEWAY)
    by_name = {r.member.display_name: r for r in results}
    assert by_name["recall-assessor"].deployed is False
    assert "RuntimeError" in (by_name["recall-assessor"].error or "")
    assert by_name["recall-watcher"].deployed is True
    assert fleet_is_complete(results) is False


def test_empty_member_list_is_refused() -> None:
    with pytest.raises(PlatformError) as excinfo:
        deploy_fleet(RecordingRuntime(), CONFIG, lambda member: object(), members=[], gateway=GATEWAY)
    assert excinfo.value.code == "fleet_no_members"


class FakeCatalogClient:
    def __init__(self, catalogued_ids: set[str]) -> None:
        self._ids = catalogued_ids

    def list_agents(self, location: str) -> Mapping[str, Any]:
        return {
            "agents": [
                {
                    "agentId": f"urn:agent:x:reasoningEngines:{engine_id}",
                    "attributes": {},
                }
                for engine_id in self._ids
            ]
        }

    def list_services(self, location: str) -> Mapping[str, Any]:
        return {}

    def list_bindings(self, location: str) -> Mapping[str, Any]:
        return {}

    def create_service(
        self, location: str, service_id: str, body: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return {}

    def fetch_available_bindings(
        self, location: str, source_identifier: str
    ) -> Mapping[str, Any]:
        return {}


def _no_sleep(_seconds: float) -> None:
    """Tests never wait for real; the schedule is asserted, not endured."""


def _verify(client: Any, results: Any, **kwargs: Any) -> Any:
    kwargs.setdefault("sleeper", _no_sleep)
    return verify_fleet_catalogued(client, REGION, results, **kwargs)


def _all_deployed() -> list[FleetDeployment]:
    return [FleetDeployment(m, _engine(m.display_name), None) for m in FLEET_MEMBERS]


def test_catalog_read_back_reports_complete_only_when_all_appear() -> None:
    names = {m.display_name for m in FLEET_MEMBERS}
    report = _verify(FakeCatalogClient(names), _all_deployed())
    assert report["status"] == "COMPLETE"
    assert report["catalogued_count"] == 3


def test_missing_catalog_entry_is_incomplete() -> None:
    report = _verify(FakeCatalogClient({"recall-watcher"}), _all_deployed())
    assert report["status"] == "INCOMPLETE"
    assert report["catalogued_count"] == 1


def test_undeployed_member_is_never_catalogued() -> None:
    results = [
        FleetDeployment(FLEET_MEMBERS[0], _engine("recall-watcher"), None),
        FleetDeployment(FLEET_MEMBERS[1], None, "RuntimeError:boom"),
        FleetDeployment(FLEET_MEMBERS[2], _engine("recall-auditor"), None),
    ]
    report = _verify(FakeCatalogClient({"recall-watcher", "recall-auditor"}), results)
    assert report["status"] == "INCOMPLETE"
    assessor = next(m for m in report["members"] if m["role"] == "EVIDENCE_ASSESSOR")
    assert assessor["catalogued"] is False


def _moment(second: int) -> datetime:
    return datetime(2026, 8, 24, 9, 0, second, tzinfo=UTC)


def _calls() -> list[AgentCall]:
    return [
        AgentCall(member, _moment(i), _moment(i + 2), "OK", 1)
        for i, member in enumerate(FLEET_MEMBERS)
    ]


def test_a_complete_run_records_four_spans_under_one_trace() -> None:
    recorder = TraceRecorder("test-project", TRACE_ID)
    spans = record_fleet_run(
        recorder, _calls(), region=REGION, run_start=_moment(0), run_end=_moment(9)
    )
    assert len(spans) == 4
    names = [span.display_name for span in spans]
    assert CONTROLLER_SPAN in names
    assert fleet_trace_is_complete(names) is True
    root = next(s for s in spans if s.display_name == CONTROLLER_SPAN)
    assert all(
        s.parent_span_id == root.span_id for s in spans if s is not root
    )


def test_a_partial_run_is_not_a_complete_trace() -> None:
    recorder = TraceRecorder("test-project", TRACE_ID)
    spans = record_fleet_run(
        recorder, _calls()[:2], region=REGION, run_start=_moment(0), run_end=_moment(9)
    )
    assert len(spans) == 3
    assert fleet_trace_is_complete([s.display_name for s in spans]) is False


def test_span_attributes_carry_role_and_outcome_not_content() -> None:
    recorder = TraceRecorder("test-project", TRACE_ID)
    record_fleet_run(
        recorder, _calls()[:1], region=REGION, run_start=_moment(0), run_end=_moment(9)
    )
    child = recorder.spans[1]
    assert child.attributes["recall.role"] == "EVIDENCE_WATCHER"
    assert child.attributes["recall.outcome"] == "OK"
    assert child.attributes["recall.region"] == REGION
    assert not any("message" in key or "prompt" in key for key in child.attributes)


def test_recording_no_calls_is_an_error() -> None:
    with pytest.raises(PlatformError) as excinfo:
        record_fleet_run(
            TraceRecorder("test-project", TRACE_ID),
            [],
            region=REGION,
            run_start=_moment(0),
            run_end=_moment(9),
        )
    assert excinfo.value.code == "fleet_no_calls_recorded"


def test_summary_reports_both_gates() -> None:
    results = _all_deployed()
    catalog = _verify(
        FakeCatalogClient({m.display_name for m in FLEET_MEMBERS}), results
    )
    recorder = TraceRecorder("test-project", TRACE_ID)
    spans = record_fleet_run(
        recorder, _calls(), region=REGION, run_start=_moment(0), run_end=_moment(9)
    )
    summary = fleet_summary(results, catalog, [s.display_name for s in spans])
    assert summary["deploy_status"] == "COMPLETE"
    assert summary["catalog"]["status"] == "COMPLETE"
    assert summary["trace_status"] == "COMPLETE"


def test_summary_shows_incomplete_when_trace_is_short() -> None:
    results = _all_deployed()
    catalog = _verify(
        FakeCatalogClient({m.display_name for m in FLEET_MEMBERS}), results
    )
    summary = fleet_summary(results, catalog, [CONTROLLER_SPAN])
    assert summary["trace_status"] == "INCOMPLETE"


def test_deployment_wire_has_no_secret_fields() -> None:
    wire = _all_deployed()[0].to_wire()
    assert set(wire) == {
        "role",
        "display_name",
        "service_account_id",
        "deployed",
        "resource_name",
        "revision",
        "requested_resource_limits",
        "read_back_resource_limits",
        "resource_limits_source",
        "started_at",
        "finished_at",
        "attempts",
        "error",
    }


class LateCatalogClient(FakeCatalogClient):
    """Registers its members only from the given attempt onwards."""

    def __init__(self, ids: set[str], appears_on_attempt: int) -> None:
        super().__init__(ids)
        self._appears = appears_on_attempt
        self.calls = 0

    def list_agents(self, location: str) -> Mapping[str, Any]:
        # One call per pending member per attempt.
        self.calls += 1
        attempt = (self.calls - 1) // max(len(FLEET_MEMBERS), 1) + 1
        if attempt < self._appears:
            return {"agents": []}
        return super().list_agents(location)


def test_late_registration_is_waited_for_not_failed() -> None:
    client = LateCatalogClient({m.display_name for m in FLEET_MEMBERS}, 2)
    report = _verify(client, _all_deployed())
    assert report["status"] == "COMPLETE"
    assert report["catalogued_count"] == 3
    # The first attempt happens at zero seconds, so appearing on the second
    # attempt means exactly one interval was waited.
    assert [m["catalogued_after_seconds"] for m in report["members"]] == [10, 10, 10]
    assert report["waited_seconds"] == 10


def test_immediate_registration_records_zero_seconds() -> None:
    report = _verify(
        FakeCatalogClient({m.display_name for m in FLEET_MEMBERS}), _all_deployed()
    )
    assert report["status"] == "COMPLETE"
    assert all(m["catalogued_after_seconds"] == 0 for m in report["members"])
    assert report["waited_seconds"] == 0


def test_never_registering_stays_incomplete_after_the_bound() -> None:
    slept: list[float] = []
    report = _verify(FakeCatalogClient(set()), _all_deployed(), sleeper=slept.append)
    assert report["status"] == "INCOMPLETE"
    assert report["catalogued_count"] == 0
    assert all(m["catalogued_after_seconds"] is None for m in report["members"])
    assert len(slept) == 5, "six attempts means five waits"
    assert report["waited_seconds"] == 50


def test_catalog_attempts_must_be_positive() -> None:
    with pytest.raises(PlatformError) as excinfo:
        _verify(FakeCatalogClient(set()), _all_deployed(), attempts=0)
    assert excinfo.value.code == "fleet_catalog_attempts_invalid"


def test_instance_shape_is_pinned_on_every_member() -> None:
    for member in FLEET_MEMBERS:
        assert fleet_spec(CONFIG, member, gateway=GATEWAY).resource_limits == dict(FLEET_RESOURCE_LIMITS)


def test_unread_shape_is_reported_as_unread_not_as_requested() -> None:
    wire = _all_deployed()[0].to_wire()
    assert wire["requested_resource_limits"] == dict(FLEET_RESOURCE_LIMITS)
    assert wire["read_back_resource_limits"] is None
    assert wire["resource_limits_source"] == "UNREAD"


def test_read_back_shape_is_reported_as_read_back() -> None:
    base = _engine("recall-watcher")
    engine = DeployedEngine(
        resource_name=base.resource_name,
        display_name=base.display_name,
        region=base.region,
        revision=base.revision,
        deployed_at=base.deployed_at,
        read_back_at=base.read_back_at,
        resource_limits={"cpu": "1", "memory": "4Gi"},
    )
    wire = FleetDeployment(FLEET_MEMBERS[0], engine, None).to_wire()
    assert wire["resource_limits_source"] == "READ_BACK"
    assert wire["read_back_resource_limits"] == {"cpu": "1", "memory": "4Gi"}


class FlakyRuntime(RecordingRuntime):
    """Fails one member once, then succeeds, to exercise the single retry."""

    def __init__(self, flaky_display_name: str) -> None:
        super().__init__()
        self._flaky = flaky_display_name
        self._seen = 0

    def deploy(self, spec: Any, agent_engine: Any) -> DeployedEngine:  # type: ignore[override]
        if spec.display_name == self._flaky:
            self._seen += 1
            if self._seen == 1:
                raise RuntimeError("transient")
        return super().deploy(spec, agent_engine)


def test_a_transient_failure_is_retried_once_and_recovers() -> None:
    results = deploy_fleet(
        FlakyRuntime("recall-assessor"), CONFIG, lambda member: object(), gateway=GATEWAY
    )
    by_name = {r.member.display_name: r for r in results}
    assert by_name["recall-assessor"].deployed is True
    assert by_name["recall-assessor"].attempts == 2
    assert fleet_is_complete(results) is True


def test_a_permanent_failure_stops_at_the_retry_bound() -> None:
    results = deploy_fleet(
        RecordingRuntime(fail_display_name="recall-assessor"),
        CONFIG,
        lambda member: object(),
        gateway=GATEWAY,
    )
    failed = next(r for r in results if r.member.display_name == "recall-assessor")
    assert failed.deployed is False
    assert failed.attempts == 2, "one attempt plus one retry, then stop"
    assert fleet_is_complete(results) is False


def test_surviving_members_are_kept_when_one_fails() -> None:
    results = deploy_fleet(
        RecordingRuntime(fail_display_name="recall-assessor"),
        CONFIG,
        lambda member: object(),
        gateway=GATEWAY,
    )
    kept = [r for r in results if r.deployed]
    assert len(kept) == 2, "a partial fleet keeps what deployed; redeploying is cheap"
    assert all(r.engine is not None for r in kept)


def test_deploy_timing_is_recorded_for_every_member() -> None:
    results = deploy_fleet(RecordingRuntime(), CONFIG, lambda member: object(), gateway=GATEWAY)
    for result in results:
        assert result.started_at.endswith("Z")
        assert result.finished_at.endswith("Z")


def test_overlap_is_measured_not_assumed() -> None:
    results = deploy_fleet(RecordingRuntime(), CONFIG, lambda member: object(), gateway=GATEWAY)
    assert deploy_overlap_seconds(results) > 0, "concurrent deploys overlap in time"


def test_serialised_deploys_report_no_overlap() -> None:
    serial = [
        FleetDeployment(
            FLEET_MEMBERS[0],
            _engine("a"),
            None,
            started_at="2026-08-24T09:00:00Z",
            finished_at="2026-08-24T09:06:00Z",
        ),
        FleetDeployment(
            FLEET_MEMBERS[1],
            _engine("b"),
            None,
            started_at="2026-08-24T09:06:00Z",
            finished_at="2026-08-24T09:12:00Z",
        ),
    ]
    assert deploy_overlap_seconds(serial) == 0.0


# --- rule 14: identity is proven by interrogation, not by metadata -----------
#
# The real failure this encodes: on 2026-08-25 the fleet deployed COMPLETE with
# three engines, three display names, three service accounts, three resource ids
# and three catalog rows -- and ONE agent, because concurrent creates raced on a
# fixed staging path. Every signal checked was metadata ABOUT the engine; none
# was testimony FROM it.


class _Invocation:
    def __init__(self, author: str | None) -> None:
        self.events = ({"author": author, "content": {}},) if author else ()


class _RecordingInvoker:
    """Answers with whatever author each resource name is mapped to."""

    def __init__(self, authors_by_resource: dict[str, str | None]) -> None:
        self._authors = authors_by_resource
        self.calls: list[str] = []

    def invoke(self, resource_name: str, *, message: str, user_id: str) -> Any:
        self.calls.append(resource_name)
        return _Invocation(self._authors.get(resource_name))


def _deployments_for(authors: list[str | None]) -> tuple[list[Any], _RecordingInvoker]:
    results = []
    mapping: dict[str, str | None] = {}
    for member, author in zip(FLEET_MEMBERS, authors, strict=True):
        engine = _engine(member.display_name)
        mapping[engine.resource_name] = author
        results.append(
            FleetDeployment(
                member,
                engine,
                None,
                started_at="2026-08-25T00:00:00Z",
                finished_at="2026-08-25T00:00:01Z",
                attempts=1,
            )
        )
    return results, _RecordingInvoker(mapping)


def test_a_correct_fleet_is_confirmed_by_interrogation() -> None:
    authors = [expected_agent_author(m) for m in FLEET_MEMBERS]
    deployments, invoker = _deployments_for(list(authors))
    checks = verify_fleet_identity(invoker, deployments)
    assert len(invoker.calls) == 3, "every engine must actually be asked"
    assert all(c.matches for c in checks)
    assert fleet_identity_is_distinct(checks) is True


def test_a_fleet_of_clones_is_refused() -> None:
    """The exact defect: three engines, correct metadata, one agent."""

    clone = expected_agent_author(FLEET_MEMBERS[1])
    deployments, invoker = _deployments_for([clone, clone, clone])
    checks = verify_fleet_identity(invoker, deployments)
    assert fleet_identity_is_distinct(checks) is False
    wrong = [c.display_name for c in checks if not c.matches]
    assert len(wrong) == 2, "the two impostors are named, not just counted"


def test_three_different_wrong_agents_are_also_refused() -> None:
    """Distinctness alone is not identity."""

    deployments, invoker = _deployments_for(["wrong_a", "wrong_b", "wrong_c"])
    checks = verify_fleet_identity(invoker, deployments)
    assert fleet_identity_is_distinct(checks) is False


def test_an_engine_that_says_nothing_is_not_assumed_correct() -> None:
    authors = [expected_agent_author(m) for m in FLEET_MEMBERS]
    authors[0] = None
    deployments, invoker = _deployments_for(authors)
    checks = verify_fleet_identity(invoker, deployments)
    assert checks[0].matches is False
    assert fleet_identity_is_distinct(checks) is False


def test_a_repr_blob_cannot_be_used_to_read_authors() -> None:
    """Why observed_authors reads events, not a serialised dump.

    json.dumps(invocation, default=str) yields a repr whose single quotes make a
    '"author"' search find nothing -- reporting a clean absence instead of
    failing. That is how this check could have been written to never fire.
    """

    import json

    invocation = _Invocation("evidence_watcher")
    blob = json.dumps(invocation, default=str)
    assert '"author":' not in blob
    assert observed_authors(invocation) == ("evidence_watcher",)
