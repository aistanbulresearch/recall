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
    assert_agent_carries_no_tracing_flag,
    assert_fleet_config,
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


def _corrupted(**changes: Any) -> dict[str, Any]:
    expected = copy.deepcopy(dict(EXPECTED_FLEET_CONFIG))
    expected.update(changes)
    return expected


def test_the_locked_configuration_matches_what_the_fleet_builds() -> None:
    assert_fleet_config(CONFIG)


def test_wrong_requirements_stop_the_run() -> None:
    expected = _corrupted(requirements=("google-cloud-aiplatform[adk,agent_engines]",))
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, expected=expected)
    assert excinfo.value.code == "fleet_config_mismatch"
    assert excinfo.value.detail == "requirements"


def test_wrong_resource_limits_stop_the_run() -> None:
    expected = _corrupted(resource_limits={"cpu": "4", "memory": "16Gi"})
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, expected=expected)
    assert excinfo.value.detail == "resource_limits"


def test_a_missing_env_key_stops_the_run() -> None:
    keys = set(EXPECTED_FLEET_CONFIG["env_keys"]) | {"AN_EXTRA_KEY"}
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, expected=_corrupted(env_keys=frozenset(keys)))
    assert excinfo.value.detail == "env_keys"


def test_telemetry_switched_off_stops_the_run() -> None:
    values = dict(EXPECTED_FLEET_CONFIG["env_values"])
    values["GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"] = "false"
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, expected=_corrupted(env_values=values))
    assert excinfo.value.detail == (
        "env_values.GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"
    )


def test_content_capture_switched_on_stops_the_run() -> None:
    values = dict(EXPECTED_FLEET_CONFIG["env_values"])
    values["ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS"] = "true"
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, expected=_corrupted(env_values=values))
    assert excinfo.value.detail == "env_values.ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS"


def test_a_wrong_role_to_account_mapping_stops_the_run() -> None:
    mapping = dict(EXPECTED_FLEET_CONFIG["role_service_accounts"])
    mapping["EVIDENCE_WATCHER"] = "recall-sa-assessor"
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, expected=_corrupted(role_service_accounts=mapping))
    assert excinfo.value.detail == "role_service_accounts.EVIDENCE_WATCHER"


def test_a_missing_role_stops_the_run() -> None:
    mapping = dict(EXPECTED_FLEET_CONFIG["role_service_accounts"])
    mapping.pop("CITATION_AUDITOR")
    with pytest.raises(PlatformError) as excinfo:
        assert_fleet_config(CONFIG, expected=_corrupted(role_service_accounts=mapping))
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
        deploy_fleet(runtime, CONFIG, lambda member: object())
    assert excinfo.value.code == "fleet_config_mismatch"
    assert runtime.specs == [], "an engine was created despite the mismatch"


def test_a_tracing_flagged_agent_is_reported_per_member() -> None:
    class TracingAgent:
        _enable_tracing = True

    results = deploy_fleet(
        RecordingRuntime(), CONFIG, lambda member: TracingAgent(), retries=0
    )
    assert all(not r.deployed for r in results)
    assert all("fleet_config_mismatch" in (r.error or "") for r in results)


def test_a_healthy_configuration_still_deploys() -> None:
    runtime = RecordingRuntime()
    results = deploy_fleet(runtime, CONFIG, lambda member: object())
    assert all(r.deployed for r in results)
    assert len(runtime.specs) == len(FLEET_MEMBERS)
