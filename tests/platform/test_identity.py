from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from recall.contracts.enums import AgentRole
from recall.platform.errors import PlatformError
from recall.platform.identity import (
    SERVICE_IDENTITIES,
    agents_hold_no_ledger_access,
    declared_inventory,
    identity_for_role,
    observe_agent_identity,
    reconcile_bucket_policy,
    reconcile_project_policy,
)

PROJECT = "test-project"


def _member(account_id: str) -> str:
    return f"serviceAccount:{account_id}@{PROJECT}.iam.gserviceaccount.com"


def _matching_project_policy() -> dict[str, list[str]]:
    return {
        _member(identity.account_id): list(identity.project_roles)
        for identity in SERVICE_IDENTITIES
    }


def _matching_bucket_policy() -> dict[str, list[str]]:
    return {
        _member(identity.account_id): list(identity.bucket_roles)
        for identity in SERVICE_IDENTITIES
        if identity.bucket_roles
    }


def test_every_role_has_its_own_account() -> None:
    account_ids = [identity.account_id for identity in SERVICE_IDENTITIES]
    assert len(account_ids) == len(set(account_ids)) == 5
    assert all(account_id.startswith("recall-sa-") for account_id in account_ids)


def test_agents_never_reach_the_ledger() -> None:
    assert agents_hold_no_ledger_access() is True
    for identity in SERVICE_IDENTITIES:
        if identity.agent_role is not None:
            assert "roles/datastore.user" not in identity.project_roles


def test_only_the_controller_writes_the_ledger() -> None:
    controller = next(
        identity for identity in SERVICE_IDENTITIES if identity.agent_role is None
    )
    assert controller.account_id == "recall-sa-controller"
    assert "roles/datastore.user" in controller.project_roles
    assert controller.bucket_roles == ()


@pytest.mark.parametrize("role", list(AgentRole))
def test_each_agent_role_maps_to_an_account(role: AgentRole) -> None:
    assert identity_for_role(role).agent_role is role


def test_declared_inventory_carries_no_project_identifier() -> None:
    rendered = json.dumps(declared_inventory())
    assert PROJECT not in rendered
    assert rendered.count("<project>") == len(SERVICE_IDENTITIES) + 1


def test_email_requires_a_project() -> None:
    identity = SERVICE_IDENTITIES[0]
    assert identity.email(PROJECT).endswith(f"@{PROJECT}.iam.gserviceaccount.com")
    with pytest.raises(PlatformError) as excinfo:
        identity.email("")
    assert excinfo.value.code == "identity_project_missing"


def test_matching_policy_reconciles() -> None:
    assert reconcile_project_policy(_matching_project_policy(), PROJECT) == {
        "scope": "project",
        "status": "MATCHED",
        "checked_accounts": 5,
        "drifts": [],
    }


def test_absent_member_reports_missing_roles_not_success() -> None:
    policy = _matching_project_policy()
    del policy[_member("recall-sa-watcher")]
    result = reconcile_project_policy(policy, PROJECT)
    assert result["status"] == "DRIFTED"
    assert result["drifts"] == [
        {
            "account_id": "recall-sa-watcher",
            "missing_roles": ["roles/aiplatform.user"],
            "unexpected_roles": [],
        }
    ]


def test_extra_grant_is_drift() -> None:
    policy = _matching_project_policy()
    policy[_member("recall-sa-assessor")].append("roles/datastore.user")
    result = reconcile_project_policy(policy, PROJECT)
    assert result["status"] == "DRIFTED"
    assert result["drifts"][0]["unexpected_roles"] == ["roles/datastore.user"]


def test_bucket_reconcile_flags_a_stray_controller_grant() -> None:
    policy = _matching_bucket_policy()
    policy[_member("recall-sa-controller")] = ["roles/storage.objectViewer"]
    result = reconcile_bucket_policy(policy, PROJECT)
    assert result["scope"] == "staging_bucket"
    assert result["status"] == "DRIFTED"
    assert result["drifts"][0]["account_id"] == "recall-sa-controller"


def test_bucket_reconcile_matches_declaration() -> None:
    assert reconcile_bucket_policy(_matching_bucket_policy(), PROJECT)["status"] == (
        "MATCHED"
    )


class FakeIdentityClient:
    def __init__(self, payload: Mapping[str, Any] | None, error: str | None = None):
        self._payload = payload
        self._error = error

    def _answer(self, location: str) -> Mapping[str, Any]:
        if self._error is not None:
            raise PlatformError("identity_listing_unavailable", self._error)
        assert self._payload is not None
        return self._payload

    def list_access_summaries(self, location: str) -> Mapping[str, Any]:
        return self._answer(location)

    def list_auth_providers(self, location: str) -> Mapping[str, Any]:
        return self._answer(location)


def test_empty_listing_is_recorded_as_empty() -> None:
    result = observe_agent_identity(FakeIdentityClient({}), "us-central1")
    assert result["access_summaries"] == {"status": "EMPTY", "count": 0}
    assert result["auth_providers"] == {"status": "EMPTY", "count": 0}


def test_populated_listing_is_observed() -> None:
    payload = {"accessSummaries": [{"name": "a"}, {"name": "b"}]}
    result = observe_agent_identity(FakeIdentityClient(payload), "us-central1")
    assert result["access_summaries"] == {"status": "OBSERVED", "count": 2}


def test_unreachable_listing_is_degraded_never_clean() -> None:
    result = observe_agent_identity(
        FakeIdentityClient(None, error="accessSummaries:403"), "global"
    )
    assert result["access_summaries"]["status"] == "DEGRADED"
    assert result["access_summaries"]["reason_code"] == "identity_listing_unavailable"
    assert result["access_summaries"]["detail"] == "accessSummaries:403"
    assert "count" not in result["access_summaries"]
