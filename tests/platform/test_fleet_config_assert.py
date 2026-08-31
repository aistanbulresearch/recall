"""The fleet must not start on a configuration that is not the locked one.

Today a generation parameter lived only in a CLI flag, so nothing checked it.
Three engines rising on the wrong environment on 08-24 would be the same defect
class, and it would not be visible until the traces were already wrong. These
tests corrupt the locked constant and prove no engine is created.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from recall.platform.config import PlatformConfig
from recall.platform.errors import PlatformError
from recall.platform.fleet import (
    EXPECTED_FLEET_CONFIG,
    FLEET_MEMBERS,
    RECALL_WHEEL,
    assert_agent_carries_no_tracing_flag,
    assert_fleet_config,
    fleet_env_vars,
    fleet_spec,
    GatewayBinding,
    deploy_fleet,
)
from recall.platform.runtime import AgentRuntime, DeployedEngine

REGION = "us-central1"


class RecordingRuntime(AgentRuntime):
    """Runtime stub that records every spec it was asked to deploy.

    Defined here rather than imported: tests/platform is not an importable
    package, because naming it `platform` would shadow the standard library.
    """

    def __init__(self) -> None:
        self.specs: list[Any] = []

    def deploy(self, spec: Any, agent_engine: Any) -> DeployedEngine:  # type: ignore[override]
        self.specs.append(spec)
        return DeployedEngine(
            resource_name=(
                f"projects/test-project/locations/{REGION}"
                f"/reasoningEngines/{spec.display_name}"
            ),
            display_name=spec.display_name,
            region=REGION,
            revision="2026-08-24T09:00:00Z",
            deployed_at="2026-08-24T08:59:00Z",
            read_back_at="2026-08-24T09:00:10Z",
            resource_limits=dict(spec.resource_limits or {}),
        )
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


def _corrupted(**changes: Any) -> dict[str, Any]:
    expected = copy.deepcopy(dict(EXPECTED_FLEET_CONFIG))
    expected.update(changes)
    return expected


def test_the_locked_configuration_matches_what_the_fleet_builds() -> None:
    assert_fleet_config(CONFIG, gateway=GATEWAY)


def test_wrong_requirements_stop_the_run() -> None:
    expected = _corrupted(requirements=("google-cloud-aiplatform[adk,agent_engines]",))
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, gateway=GATEWAY, expected=expected)
    assert excinfo.value.code == "fleet_config_mismatch"
    assert excinfo.value.detail == "requirements"


def test_wrong_resource_limits_stop_the_run() -> None:
    expected = _corrupted(resource_limits={"cpu": "4", "memory": "16Gi"})
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, gateway=GATEWAY, expected=expected)
    assert excinfo.value.detail == "resource_limits"


def test_a_missing_env_key_stops_the_run() -> None:
    keys = set(EXPECTED_FLEET_CONFIG["env_keys"]) | {"AN_EXTRA_KEY"}
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, gateway=GATEWAY, expected=_corrupted(env_keys=frozenset(keys)))
    assert excinfo.value.detail == "env_keys"


def test_telemetry_switched_off_stops_the_run() -> None:
    values = dict(EXPECTED_FLEET_CONFIG["env_values"])
    values["GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"] = "false"
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, gateway=GATEWAY, expected=_corrupted(env_values=values))
    assert excinfo.value.detail == (
        "env_values.GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"
    )


def test_content_capture_switched_on_stops_the_run() -> None:
    values = dict(EXPECTED_FLEET_CONFIG["env_values"])
    values["ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS"] = "true"
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, gateway=GATEWAY, expected=_corrupted(env_values=values))
    assert excinfo.value.detail == "env_values.ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS"


def test_a_wrong_role_to_account_mapping_stops_the_run() -> None:
    mapping = dict(EXPECTED_FLEET_CONFIG["role_service_accounts"])
    mapping["EVIDENCE_WATCHER"] = "recall-sa-assessor"
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, gateway=GATEWAY, expected=_corrupted(role_service_accounts=mapping))
    assert excinfo.value.detail == "role_service_accounts.EVIDENCE_WATCHER"


def test_a_missing_role_stops_the_run() -> None:
    mapping = dict(EXPECTED_FLEET_CONFIG["role_service_accounts"])
    mapping.pop("CITATION_AUDITOR")
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, gateway=GATEWAY, expected=_corrupted(role_service_accounts=mapping))
    assert excinfo.value.detail == "role_service_accounts"


def test_an_agent_built_with_the_tracing_flag_is_refused() -> None:
    class TracingAgent:
        enable_tracing = True

    with pytest.raises(PlatformError) as excinfo:
        assert_agent_carries_no_tracing_flag(TracingAgent())
    assert excinfo.value.detail == "enable_tracing"


def test_an_agent_without_the_tracing_flag_is_accepted() -> None:
    assert assert_agent_carries_no_tracing_flag(object()) is None


def test_an_omitted_parameter_looks_like_none_and_is_accepted() -> None:
    class OmittedApp:
        _tmpl_attrs = {"enable_tracing": None}

    assert assert_agent_carries_no_tracing_flag(OmittedApp()) is None


def test_enable_tracing_false_is_refused_because_false_is_the_harmful_value() -> None:
    """AdkApp(enable_tracing=False) silently disables telemetry.

    Observed on 2026-08-24: passing the parameter leaves False in _tmpl_attrs,
    omitting it leaves None. A truthiness check would accept the False and the
    fleet would emit no spans.
    """

    class FalseFlagApp:
        _tmpl_attrs = {"enable_tracing": False}

    with pytest.raises(PlatformError) as excinfo:
        assert_agent_carries_no_tracing_flag(FalseFlagApp())
    assert excinfo.value.detail == "enable_tracing"


def test_enable_tracing_true_is_also_refused() -> None:
    class TrueFlagApp:
        _tmpl_attrs = {"enable_tracing": True}

    with pytest.raises(PlatformError) as excinfo:
        assert_agent_carries_no_tracing_flag(TrueFlagApp())
    assert excinfo.value.detail == "enable_tracing"


def test_a_corrupted_constant_creates_no_engine(monkeypatch: Any) -> None:
    """The claim that matters: mismatch stops before anything is deployed."""

    broken = _corrupted(resource_limits={"cpu": "99", "memory": "1Ti"})
    monkeypatch.setattr(
        "recall.platform.fleet.EXPECTED_FLEET_CONFIG", broken, raising=True
    )
    runtime = RecordingRuntime()
    with pytest.raises(PlatformError) as excinfo:
        deploy_fleet(runtime, CONFIG, lambda member: object(), gateway=GATEWAY)
    assert excinfo.value.code == "fleet_config_mismatch"
    assert runtime.specs == [], "an engine was created despite the mismatch"


def test_a_tracing_flagged_agent_is_reported_per_member() -> None:
    class TracingAgent:
        _enable_tracing = True

    results = deploy_fleet(
        RecordingRuntime(), CONFIG, lambda member: TracingAgent(), retries=0, gateway=GATEWAY
    )
    assert all(not r.deployed for r in results)
    assert all("fleet_config_mismatch" in (r.error or "") for r in results)


def test_a_healthy_configuration_still_deploys() -> None:
    runtime = RecordingRuntime()
    results = deploy_fleet(runtime, CONFIG, lambda member: object(), gateway=GATEWAY)
    assert all(r.deployed for r in results)
    assert len(runtime.specs) == len(FLEET_MEMBERS)


# --- the gateway binding is part of the declared fleet shape ------------------
#
# Until 2026-08-25 fleet_env_vars set no gateway variables at all, so a deployed
# agent would have raised tool_gateway_https_required before opening a socket.
# In a reachability test that failure is indistinguishable from an unreachable
# network unless someone reads the error string, and the conclusion would have
# been "agent engines cannot reach internal ingress" -- possibly flipping a
# security posture on a missing environment variable.
#
# assert_gateway_config already existed and was already tested. Nothing called
# it on the deploy path, which is the difference between a check and a check
# that runs.


def test_the_deployed_environment_carries_the_gateway_binding() -> None:
    for member in FLEET_MEMBERS:
        env = fleet_env_vars(CONFIG, member.display_name, gateway=GATEWAY)
        assert env["RECALL_TOOL_GATEWAY_URL"] == GATEWAY.url
        assert env["RECALL_TOOL_GATEWAY_AUDIENCE"] == GATEWAY.audience


def test_the_agent_environment_never_carries_the_signing_key() -> None:
    """The whole reason the gateway exists is that agents do not hold it."""

    for member in FLEET_MEMBERS:
        env = fleet_env_vars(CONFIG, member.display_name, gateway=GATEWAY)
        assert "RECALL_TOOL_CAPABILITY_SECRET_B64" not in env
        assert "RECALL_NCBI_EMAIL" not in env
        assert "RECALL_NCBI_TOOL" not in env


def test_a_mismatched_audience_is_refused_on_the_deploy_path() -> None:
    """Proves assert_gateway_config is reached from assert_fleet_config.

    A token minted for the wrong audience is rejected by Cloud Run at the door,
    so this would have been every agent call failing, discovered at the smoke
    rather than at the gate.
    """

    wrong = GatewayBinding(
        url="https://recall-tool-gateway-test.a.run.app",
        audience="https://some-other-service.a.run.app",
    )
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, gateway=wrong)
    assert excinfo.value.code == "fleet_config_mismatch"
    assert "audience" in str(excinfo.value.detail)


def test_an_unset_gateway_url_is_refused_rather_than_defaulted() -> None:
    with pytest.raises(PlatformError) as excinfo:
        GatewayBinding.from_env({})
    assert excinfo.value.code == "fleet_gateway_url_missing"


def test_the_audience_defaults_to_the_url_rather_than_drifting() -> None:
    binding = GatewayBinding.from_env(
        {"RECALL_TOOL_GATEWAY_URL": "https://recall-tool-gateway-test.a.run.app"}
    )
    assert binding.audience == binding.url


# --- the agent is pickled by reference, so the payload has to travel ----------
#
# The three engines were CREATED in the right project and region on 2026-08-25
# and then failed to start:
#     ModuleNotFoundError: No module named 'recall'
# Agent Engine pickles the agent by reference, so the container must import
# recall.agents.* and recall.contracts.* just to unpickle it. requirements
# listed only PyPI packages; our own code was never shipped. That reads like a
# platform fault and is in fact a missing payload.
#
# The 08-22 hello engine deployed fine because it imported nothing of ours,
# which is why this could only surface with the real fleet.


def test_the_recall_wheel_travels_with_every_member() -> None:
    for member in FLEET_MEMBERS:
        spec = fleet_spec(CONFIG, member, gateway=GATEWAY)
        assert RECALL_WHEEL in spec.extra_packages, (
            "the container cannot unpickle the agent without recall on its path"
        )
        assert RECALL_WHEEL in spec.requirements, (
            "extra_packages uploads the wheel; requirements is what installs it"
        )


def test_a_fleet_missing_its_own_package_is_refused() -> None:
    expected = dict(EXPECTED_FLEET_CONFIG)
    expected["extra_packages"] = ()
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, gateway=GATEWAY, expected=expected)
    assert excinfo.value.code == "fleet_config_mismatch"
    assert excinfo.value.detail == "extra_packages"
