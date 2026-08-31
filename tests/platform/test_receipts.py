from __future__ import annotations

import pytest

from recall.contracts.canonical import content_hash
from recall.contracts.enums import ArtifactStatus, DataMode
from recall.contracts.errors import ContractError
from recall.platform.errors import PlatformError
from recall.platform.receipts import (
    COMMON_FIELDS,
    DEPLOYMENT_RECEIPT_FIELDS,
    RUNTIME_FIELDS,
    build_platform_receipt,
    deployment_receipt,
    utc_timestamp,
)

ARTIFACT_ID = "4f1a2b3c-0000-4000-8000-000000000001"


def _receipt(**overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "artifact_id": ARTIFACT_ID,
        "producer_version": "0.1.0",
        "created_at": "2026-08-22T09:00:00Z",
        "deployed_at": "2026-08-22T08:55:00Z",
        "source_revision": "bc855957",
        "deployed_components": ["recall-hello-smoke"],
        "service": "vertex-ai-agent-engine",
        "revision": "2026-08-22T08:54:12Z",
        "region": "us-central1",
        "resource_name": "projects/p/locations/us-central1/reasoningEngines/123",
        "read_back_at": "2026-08-22T08:56:00Z",
    }
    kwargs.update(overrides)
    return deployment_receipt(**kwargs)  # type: ignore[arg-type]


def test_deployment_receipt_field_set_matches_contract() -> None:
    wire = _receipt()
    assert set(wire) == COMMON_FIELDS | DEPLOYMENT_RECEIPT_FIELDS
    assert set(wire["runtime"]) == RUNTIME_FIELDS  # type: ignore[arg-type]


def test_deployment_receipt_uses_authorised_producer() -> None:
    wire = _receipt()
    assert wire["producer"] == {
        "component": "Release controller",
        "version": "0.1.0",
        "identity": "release-controller",
    }
    assert wire["schema_name"] == "DeploymentReceipt"
    assert wire["schema_version"] == "1.0.0"


def test_deployment_receipt_is_deployment_level_and_hash_stable() -> None:
    wire = _receipt()
    assert wire["case_id"] is None
    assert wire["run_id"] is None
    assert wire["warnings"] == []
    assert wire["extensions"] == {}
    assert wire["content_hash"] == content_hash(wire)


def test_deployment_receipt_rejects_unauthorised_identity() -> None:
    with pytest.raises(PlatformError) as excinfo:
        _build_with_identity("evidence-watcher")
    assert excinfo.value.code == "producer_not_authorized"


def _build_with_identity(identity: str) -> None:
    build_platform_receipt(
        schema_name="DeploymentReceipt",
        schema_version="1.0.0",
        payload_fields=DEPLOYMENT_RECEIPT_FIELDS,
        artifact_id=ARTIFACT_ID,
        case_id=None,
        run_id=None,
        producer={
            "component": "Release controller",
            "version": "0.1.0",
            "identity": identity,
        },
        created_at="2026-08-22T09:00:00Z",
        input_artifact_ids=(),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID,
        payload={
            "runtime": {
                "service": "vertex-ai-agent-engine",
                "revision": "r1",
                "region": "us-central1",
                "resource_name": "projects/p/locations/us-central1/reasoningEngines/1",
                "read_back_at": "2026-08-22T08:56:00Z",
            },
            "deployed_components": ["recall-hello-smoke"],
            "source_revision": "bc855957",
            "deployed_at": "2026-08-22T08:55:00Z",
        },
    )


def test_valid_receipt_requires_read_back() -> None:
    with pytest.raises(PlatformError) as excinfo:
        _receipt(resource_name="", read_back_at="")
    assert excinfo.value.code == "deployment_read_back_missing"


def test_degraded_receipt_is_allowed_without_read_back() -> None:
    wire = _receipt(
        resource_name="",
        read_back_at="",
        status=ArtifactStatus.DEGRADED,
    )
    assert wire["status"] == "DEGRADED"
    assert wire["runtime"]["read_back_at"] == ""  # type: ignore[index]


def test_empty_component_list_is_an_error_not_a_clean_result() -> None:
    with pytest.raises(PlatformError) as excinfo:
        _receipt(deployed_components=[])
    assert excinfo.value.code == "deployment_components_missing"


def test_components_must_be_sorted_and_unique() -> None:
    with pytest.raises(ContractError) as excinfo:
        _receipt(deployed_components=["b", "a"])
    assert excinfo.value.code == "contract_order_or_uniqueness_invalid"


def test_non_utc_timestamp_is_rejected() -> None:
    with pytest.raises(PlatformError) as excinfo:
        _receipt(deployed_at="2026-08-22T08:55:00+03:00")
    assert excinfo.value.code == "contract_timestamp_invalid"


def test_utc_timestamp_renders_contract_shape() -> None:
    from datetime import UTC, datetime

    rendered = utc_timestamp(datetime(2026, 8, 22, 8, 55, 0, 123456, tzinfo=UTC))
    assert rendered == "2026-08-22T08:55:00Z"
