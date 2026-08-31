from __future__ import annotations

import copy
from typing import Any

import pytest

from recall.platform.errors import PlatformError
from recall.platform.identity import (
    assert_additive_policy_write,
    parse_policy_document,
)

LIVE_POLICY: dict[str, Any] = {
    "version": 1,
    "etag": "BwYm3Q9zK1s=",
    "bindings": [
        {"role": "roles/owner", "members": ["user:owner@example.invalid"]},
        {
            "role": "roles/aiplatform.user",
            "members": ["serviceAccount:recall-sa-watcher@p.iam.gserviceaccount.com"],
        },
    ],
}

# The exact shape Cloud Resource Manager returned when the API was disabled.
ERROR_BODY: dict[str, Any] = {
    "error": {
        "code": 403,
        "message": "Cloud Resource Manager API has not been used in project before",
        "status": "PERMISSION_DENIED",
    }
}


def _with_added_member(role: str, member: str) -> dict[str, Any]:
    updated = copy.deepcopy(LIVE_POLICY)
    for binding in updated["bindings"]:
        if binding["role"] == role:
            binding["members"].append(member)
            return updated
    updated["bindings"].append({"role": role, "members": [member]})
    return updated


def test_error_body_is_never_treated_as_a_policy() -> None:
    # This is the failure that would have wiped project IAM.
    with pytest.raises(PlatformError) as excinfo:
        parse_policy_document(ERROR_BODY)
    assert excinfo.value.code == "iam_policy_fetch_failed"
    assert excinfo.value.detail == "403"


def test_empty_policy_is_rejected() -> None:
    with pytest.raises(PlatformError) as excinfo:
        parse_policy_document({"etag": "x", "bindings": []})
    assert excinfo.value.code == "iam_policy_empty"


def test_missing_etag_is_rejected() -> None:
    with pytest.raises(PlatformError) as excinfo:
        parse_policy_document({"bindings": LIVE_POLICY["bindings"]})
    assert excinfo.value.code == "iam_policy_etag_missing"


def test_non_mapping_is_rejected() -> None:
    with pytest.raises(PlatformError) as excinfo:
        parse_policy_document("not a policy")
    assert excinfo.value.code == "iam_policy_malformed"


def test_valid_policy_is_accepted() -> None:
    assert parse_policy_document(LIVE_POLICY) is LIVE_POLICY


def test_pure_addition_is_allowed_and_reported() -> None:
    updated = _with_added_member(
        "roles/cloudtrace.agent",
        "serviceAccount:recall-sa-controller@p.iam.gserviceaccount.com",
    )
    added = assert_additive_policy_write(LIVE_POLICY, updated)
    assert added == (
        "roles/cloudtrace.agent:serviceAccount:recall-sa-controller@p.iam.gserviceaccount.com",
    )


def test_dropping_an_unrelated_grant_is_refused() -> None:
    updated = copy.deepcopy(LIVE_POLICY)
    updated["bindings"] = [
        b for b in updated["bindings"] if b["role"] != "roles/owner"
    ]
    with pytest.raises(PlatformError) as excinfo:
        assert_additive_policy_write(LIVE_POLICY, updated)
    assert excinfo.value.code == "iam_policy_would_remove_grant"
    assert "roles/owner" in (excinfo.value.detail or "")


def test_wiping_every_binding_is_refused() -> None:
    updated = copy.deepcopy(LIVE_POLICY)
    updated["bindings"] = []
    with pytest.raises(PlatformError) as excinfo:
        assert_additive_policy_write(LIVE_POLICY, updated)
    assert excinfo.value.code == "iam_policy_would_remove_grant"


def test_stale_etag_is_refused() -> None:
    updated = _with_added_member("roles/aiplatform.user", "serviceAccount:x@p.iam")
    updated["etag"] = "different"
    with pytest.raises(PlatformError) as excinfo:
        assert_additive_policy_write(LIVE_POLICY, updated)
    assert excinfo.value.code == "iam_policy_etag_changed"


def test_write_from_an_error_body_is_refused_at_the_guard() -> None:
    with pytest.raises(PlatformError) as excinfo:
        assert_additive_policy_write(ERROR_BODY, {"etag": None, "bindings": []})
    assert excinfo.value.code == "iam_policy_fetch_failed"


def test_no_change_reports_nothing_added() -> None:
    assert assert_additive_policy_write(LIVE_POLICY, copy.deepcopy(LIVE_POLICY)) == ()
