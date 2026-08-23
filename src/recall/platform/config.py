from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from .errors import PlatformError

_REQUIRED_ENV = (
    "RECALL_GCP_PROJECT",
    "RECALL_AGENT_ENGINE_LOCATION",
    "RECALL_MODEL",
    "RECALL_MODEL_LOCATION",
    "RECALL_STAGING_BUCKET",
)

RESOURCE_PREFIX = "recall-"
LANE_LABEL_KEY = "lane"
LANE_LABEL_VALUE = "l1"


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    """Immutable platform binding resolved from the environment.

    Project, bucket, and service-account values are never hardcoded in source
    or in committed inventory files; they are supplied per environment.
    """

    project_id: str
    agent_engine_location: str
    model: str
    model_location: str
    staging_bucket: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> PlatformConfig:
        source = os.environ if env is None else env
        missing = sorted(name for name in _REQUIRED_ENV if not source.get(name))
        if missing:
            raise PlatformError("platform_config_missing", ",".join(missing))
        bucket = source["RECALL_STAGING_BUCKET"]
        if not bucket.startswith("gs://"):
            raise PlatformError("platform_staging_bucket_invalid", "scheme")
        if not bucket[len("gs://") :].startswith(RESOURCE_PREFIX):
            raise PlatformError("platform_staging_bucket_invalid", "prefix")
        return cls(
            project_id=source["RECALL_GCP_PROJECT"],
            agent_engine_location=source["RECALL_AGENT_ENGINE_LOCATION"],
            model=source["RECALL_MODEL"],
            model_location=source["RECALL_MODEL_LOCATION"],
            staging_bucket=bucket,
        )


def resource_labels(component: str) -> dict[str, str]:
    """Return the mandatory lane labels applied to every L1 cloud resource."""

    if not component:
        raise PlatformError("platform_label_component_missing")
    return {LANE_LABEL_KEY: LANE_LABEL_VALUE, "component": component}


def require_resource_prefix(name: str, field: str) -> str:
    if not name.startswith(RESOURCE_PREFIX):
        raise PlatformError("platform_resource_prefix_invalid", field)
    return name
