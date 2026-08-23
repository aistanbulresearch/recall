"""Contract-conforming wire dictionaries for platform-level receipts.

`DeploymentReceipt` is declared in `docs/contracts/ARTIFACT_CONTRACTS.md` and
carries an authorised producer in `recall.ledger.producers`, but it is not yet
registered in `recall.contracts.schemas.SCHEMAS`. `recall.contracts.build_artifact`
therefore cannot emit it. This module builds the identical envelope shape and
the same canonical content hash as `build_artifact`, and enforces the documented
field sets locally, so the contracts lane can register an executable parser later
without changing the bytes produced here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from recall.contracts.canonical import content_hash
from recall.contracts.enums import ArtifactStatus, DataMode
from recall.contracts.validation import (
    require_exact_fields,
    tuple_of_strings,
    uuid_value,
)
from recall.ledger.producers import PRODUCER_REGISTRY

from .errors import PlatformError

COMMON_FIELDS = frozenset(
    {
        "schema_name",
        "schema_version",
        "artifact_id",
        "case_id",
        "run_id",
        "producer",
        "created_at",
        "input_artifact_ids",
        "content_hash",
        "data_mode",
        "status",
        "warnings",
        "extensions",
    }
)

RUNTIME_FIELDS = frozenset(
    {"service", "revision", "region", "resource_name", "read_back_at"}
)
DEPLOYMENT_RECEIPT_FIELDS = frozenset(
    {"runtime", "deployed_components", "source_revision", "deployed_at"}
)
DEPLOYMENT_RECEIPT_VERSION = "1.0.0"


def utc_timestamp(moment: datetime) -> str:
    """Render a UTC RFC 3339 timestamp with the trailing `Z` the contract requires."""

    return (
        moment.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def _require_timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise PlatformError("contract_timestamp_invalid", field)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PlatformError("contract_timestamp_invalid", field) from exc
    return value


def _require_producer(schema_name: str, producer: Mapping[str, str]) -> dict[str, str]:
    require_exact_fields(
        producer, frozenset({"component", "version", "identity"}), "producer"
    )
    if not all(isinstance(producer[key], str) and producer[key] for key in producer):
        raise PlatformError("contract_type_invalid", "producer")
    if "@" in producer["identity"]:
        raise PlatformError("contract_identity_not_sanitized")
    allowed = PRODUCER_REGISTRY.get(schema_name)
    if allowed is None:
        raise PlatformError("producer_schema_unregistered", schema_name)
    if producer["identity"] not in allowed:
        raise PlatformError(
            "producer_not_authorized", f"{schema_name}:{producer['identity']}"
        )
    if producer["component"] != PRODUCER_REGISTRY.authority_label(schema_name):
        raise PlatformError("producer_authority_mismatch", schema_name)
    return dict(producer)


def build_platform_receipt(
    *,
    schema_name: str,
    schema_version: str,
    payload_fields: frozenset[str],
    artifact_id: str,
    case_id: str | None,
    run_id: str | None,
    producer: Mapping[str, str],
    created_at: str,
    input_artifact_ids: Sequence[str],
    data_mode: DataMode,
    status: ArtifactStatus,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a strict artifact envelope with the payload flattened at top level."""

    require_exact_fields(payload, payload_fields, schema_name)
    input_ids = tuple_of_strings(list(input_artifact_ids), "input_artifact_ids")
    for input_id in input_ids:
        uuid_value(input_id, "input_artifact_ids")
    wire: dict[str, Any] = {
        "schema_name": schema_name,
        "schema_version": schema_version,
        "artifact_id": str(uuid_value(artifact_id, "artifact_id")),
        "case_id": uuid_value(case_id, "case_id", nullable=True),
        "run_id": uuid_value(run_id, "run_id", nullable=True),
        "producer": _require_producer(schema_name, producer),
        "created_at": _require_timestamp(created_at, "created_at"),
        "input_artifact_ids": list(input_ids),
        "content_hash": "0" * 64,
        "data_mode": DataMode(data_mode).value,
        "status": ArtifactStatus(status).value,
        "warnings": [],
        "extensions": {},
    }
    overlap = set(wire) & set(payload)
    if overlap:
        raise PlatformError("contract_unknown_field", f"{schema_name}:{sorted(overlap)}")
    wire.update(dict(payload))
    wire["content_hash"] = content_hash(wire)
    return wire


def deployment_receipt(
    *,
    artifact_id: str,
    producer_version: str,
    created_at: str,
    deployed_at: str,
    source_revision: str,
    deployed_components: Sequence[str],
    service: str,
    revision: str,
    region: str,
    resource_name: str,
    read_back_at: str,
    data_mode: DataMode = DataMode.SYNTHETIC,
    status: ArtifactStatus = ArtifactStatus.VALID,
) -> dict[str, Any]:
    """Emit a `DeploymentReceipt` wire dict for one read-back managed runtime.

    A `VALID` receipt requires a resource name and a read-back timestamp that
    were observed after the deployment. An unverified deployment must be emitted
    as `INCOMPLETE` or `DEGRADED`; it is never a clean cloud claim.
    """

    status = ArtifactStatus(status)
    if status is ArtifactStatus.VALID and not (resource_name and read_back_at):
        raise PlatformError("deployment_read_back_missing", "runtime")
    components = tuple_of_strings(list(deployed_components), "deployed_components")
    if not components:
        raise PlatformError("deployment_components_missing")
    runtime = {
        "service": service,
        "revision": revision,
        "region": region,
        "resource_name": resource_name,
        "read_back_at": _require_timestamp(read_back_at, "runtime.read_back_at")
        if read_back_at
        else "",
    }
    require_exact_fields(runtime, RUNTIME_FIELDS, "runtime")
    return build_platform_receipt(
        schema_name="DeploymentReceipt",
        schema_version=DEPLOYMENT_RECEIPT_VERSION,
        payload_fields=DEPLOYMENT_RECEIPT_FIELDS,
        artifact_id=artifact_id,
        case_id=None,
        run_id=None,
        producer={
            "component": "Release controller",
            "version": producer_version,
            "identity": "release-controller",
        },
        created_at=created_at,
        input_artifact_ids=(),
        data_mode=data_mode,
        status=status,
        payload={
            "runtime": runtime,
            "deployed_components": list(components),
            "source_revision": source_revision,
            "deployed_at": _require_timestamp(deployed_at, "deployed_at"),
        },
    )
