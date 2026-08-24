"""The agent side of the gateway trust boundary, checked before deploy.

The gateway exists because agent identities must not hold data-store access or
connector credentials. An agent image that carries the capability signing key
defeats that boundary while every other gate still reports green, so the check
that matters most here is the forbidden-key one.

Field names and the closed tool set come from
docs/platform/CONTROLLER_TOOL_GATEWAY_CONTRACT.md.
"""

from __future__ import annotations

import pytest

from recall.platform.errors import PlatformError
from recall.platform.fleet import (
    EXPECTED_GATEWAY_CONFIG,
    GATEWAY_TOOL_IDS,
    assert_gateway_config,
    gateway_tool_routes,
)

URL = "https://recall-tool-gateway-abc123-uc.a.run.app"
HEALTHY_ENV = {
    "RECALL_TOOL_GATEWAY_URL": URL,
    "RECALL_TOOL_GATEWAY_AUDIENCE": URL,
}


def test_healthy_wiring_is_accepted() -> None:
    assert assert_gateway_config(URL, URL, HEALTHY_ENV) is None


def test_the_closed_tool_set_is_the_contract_set() -> None:
    assert GATEWAY_TOOL_IDS == {
        "evidence_connector",
        "ledger_read",
        "refetch_metadata",
    }


@pytest.mark.parametrize(
    "leaked",
    sorted(EXPECTED_GATEWAY_CONFIG["agent_forbidden_env_keys"]),
)
def test_a_credential_reaching_an_agent_stops_the_deploy(leaked: str) -> None:
    """Every forbidden variable is refused, not just the signing key."""

    env = dict(HEALTHY_ENV, **{leaked: "value"})
    with pytest.raises(PlatformError) as excinfo:
        assert_gateway_config(URL, URL, env)
    assert excinfo.value.code == "fleet_config_mismatch"
    assert excinfo.value.detail == f"agent_forbidden_env_keys.{leaked}"


def test_a_missing_gateway_variable_stops_the_deploy() -> None:
    env = {"RECALL_TOOL_GATEWAY_URL": URL}
    with pytest.raises(PlatformError) as excinfo:
        assert_gateway_config(URL, URL, env)
    assert excinfo.value.detail == "agent_env_keys.RECALL_TOOL_GATEWAY_AUDIENCE"


def test_plain_http_is_refused() -> None:
    insecure = "http://recall-tool-gateway.internal"
    with pytest.raises(PlatformError) as excinfo:
        assert_gateway_config(insecure, insecure, HEALTHY_ENV)
    assert excinfo.value.detail == "gateway_url_scheme"


def test_an_audience_that_is_not_the_service_url_is_refused() -> None:
    """The contract pins the audience to the exact service URL.

    A token minted for a different audience would be accepted by whatever
    service that audience names, which is the confused-deputy case.
    """

    with pytest.raises(PlatformError) as excinfo:
        assert_gateway_config(URL, "https://some-other-service.a.run.app", HEALTHY_ENV)
    assert excinfo.value.detail == "gateway_audience_mismatch"


def test_an_empty_audience_is_refused() -> None:
    with pytest.raises(PlatformError) as excinfo:
        assert_gateway_config(URL, "", HEALTHY_ENV)
    assert excinfo.value.detail == "gateway_audience_missing"


def test_a_trailing_slash_is_not_a_mismatch() -> None:
    assert assert_gateway_config(URL, URL + "/", HEALTHY_ENV) is None


def test_routes_cover_every_tool_and_use_the_contract_path() -> None:
    routes = gateway_tool_routes(URL)
    assert set(routes) == GATEWAY_TOOL_IDS
    assert routes["ledger_read"] == f"{URL}/v1/tools/ledger_read:invoke"
    assert all(route.startswith("https://") for route in routes.values())
