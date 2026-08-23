from __future__ import annotations

import pytest

from recall.platform.config import (
    LANE_LABEL_KEY,
    LANE_LABEL_VALUE,
    PlatformConfig,
    require_resource_prefix,
    resource_labels,
)
from recall.platform.errors import PlatformError

ENV = {
    "RECALL_GCP_PROJECT": "test-project",
    "RECALL_AGENT_ENGINE_LOCATION": "us-central1",
    "RECALL_MODEL": "gemini-3.7-flash",
    "RECALL_MODEL_LOCATION": "global",
    "RECALL_STAGING_BUCKET": "gs://recall-agent-engine-staging-test",
}


def test_config_is_resolved_from_the_environment() -> None:
    config = PlatformConfig.from_env(ENV)
    assert config.project_id == "test-project"
    assert config.model_location == "global"
    assert config.staging_bucket == "gs://recall-agent-engine-staging-test"


def test_missing_variables_are_named_not_defaulted() -> None:
    partial = dict(ENV)
    del partial["RECALL_MODEL"]
    del partial["RECALL_GCP_PROJECT"]
    with pytest.raises(PlatformError) as excinfo:
        PlatformConfig.from_env(partial)
    assert excinfo.value.code == "platform_config_missing"
    assert excinfo.value.detail == "RECALL_GCP_PROJECT,RECALL_MODEL"


def test_blank_variable_is_missing_not_empty() -> None:
    blank = dict(ENV, RECALL_MODEL="")
    with pytest.raises(PlatformError) as excinfo:
        PlatformConfig.from_env(blank)
    assert excinfo.value.detail == "RECALL_MODEL"


@pytest.mark.parametrize(
    "bucket, detail",
    [
        ("recall-agent-engine-staging-test", "scheme"),
        ("gs://other-staging-bucket", "prefix"),
    ],
)
def test_staging_bucket_must_carry_the_lane_prefix(bucket: str, detail: str) -> None:
    with pytest.raises(PlatformError) as excinfo:
        PlatformConfig.from_env(dict(ENV, RECALL_STAGING_BUCKET=bucket))
    assert excinfo.value.code == "platform_staging_bucket_invalid"
    assert excinfo.value.detail == detail


def test_every_resource_carries_the_lane_label() -> None:
    labels = resource_labels("agent-engine-staging")
    assert labels[LANE_LABEL_KEY] == LANE_LABEL_VALUE
    assert labels["component"] == "agent-engine-staging"


def test_unlabelled_component_is_rejected() -> None:
    with pytest.raises(PlatformError) as excinfo:
        resource_labels("")
    assert excinfo.value.code == "platform_label_component_missing"


def test_resource_prefix_is_enforced() -> None:
    assert require_resource_prefix("recall-sa-coordinator", "sa") == "recall-sa-coordinator"
    with pytest.raises(PlatformError) as excinfo:
        require_resource_prefix("sa-coordinator", "sa")
    assert excinfo.value.code == "platform_resource_prefix_invalid"
