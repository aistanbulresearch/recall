from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

from .canonical import content_hash
from .enums import ArtifactStatus, DataMode
from .errors import ContractError
from .payloads import Payload
from .schemas import LEGACY_SCHEMAS, SCHEMAS
from .validation import (
    SEMVER,
    SHA256,
    enum_value,
    require_exact_fields,
    tuple_of_strings,
    uuid_value,
)


_COMMON_FIELDS = frozenset(
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


@dataclass(frozen=True, slots=True)
class Producer:
    component: str
    version: str
    identity: str

    def to_wire(self) -> dict[str, str]:
        return {
            "component": self.component,
            "version": self.version,
            "identity": self.identity,
        }


@dataclass(frozen=True, slots=True)
class WarningItem:
    code: str
    message_key: str
    related_artifact_ids: tuple[str, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message_key": self.message_key,
            "related_artifact_ids": list(self.related_artifact_ids),
        }


@dataclass(frozen=True, slots=True)
class Artifact:
    schema_name: str
    schema_version: str
    artifact_id: str
    case_id: str | None
    run_id: str | None
    producer: Producer
    created_at: str
    input_artifact_ids: tuple[str, ...]
    content_hash: str
    data_mode: DataMode
    status: ArtifactStatus
    warnings: tuple[WarningItem, ...]
    extensions: Mapping[str, object]
    payload: Payload

    def to_wire(self) -> dict[str, object]:
        wire: dict[str, object] = {
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "artifact_id": self.artifact_id,
            "case_id": self.case_id,
            "run_id": self.run_id,
            "producer": self.producer.to_wire(),
            "created_at": self.created_at,
            "input_artifact_ids": list(self.input_artifact_ids),
            "content_hash": self.content_hash,
            "data_mode": self.data_mode.value,
            "status": self.status.value,
            "warnings": [warning.to_wire() for warning in self.warnings],
            "extensions": dict(self.extensions),
        }
        wire.update(self.payload.to_wire())
        return wire


def _parse_producer(value: Any) -> Producer:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "producer")
    require_exact_fields(
        value, frozenset({"component", "version", "identity"}), "producer"
    )
    if not all(isinstance(value[field], str) and value[field] for field in value):
        raise ContractError("contract_type_invalid", "producer")
    if "@" in value["identity"]:
        raise ContractError("contract_identity_not_sanitized")
    return Producer(value["component"], value["version"], value["identity"])


def _parse_warnings(value: Any) -> tuple[WarningItem, ...]:
    if not isinstance(value, list):
        raise ContractError("contract_type_invalid", "warnings")
    parsed: list[WarningItem] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ContractError("contract_type_invalid", f"warnings[{index}]")
        require_exact_fields(
            item,
            frozenset({"code", "message_key", "related_artifact_ids"}),
            f"warnings[{index}]",
        )
        related = tuple_of_strings(
            item["related_artifact_ids"], f"warnings[{index}].related_artifact_ids"
        )
        for artifact_id in related:
            uuid_value(artifact_id, "warning.related_artifact_ids")
        parsed.append(WarningItem(str(item["code"]), str(item["message_key"]), related))
    return tuple(parsed)


def parse_artifact(
    value: Mapping[str, Any],
    *,
    authorized_producers: Mapping[str, Collection[str]],
    verify_hash: bool = True,
) -> Artifact:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "artifact")
    schema_name = value.get("schema_name")
    if not isinstance(schema_name, str) or schema_name not in SCHEMAS:
        raise ContractError("contract_schema_unregistered")
    current_version, current_fields, current_parser, current_run_required = SCHEMAS[
        schema_name
    ]
    declared_version = value.get("schema_version")
    if declared_version == current_version:
        version = current_version
        payload_fields = current_fields
        parser = current_parser
        run_required = current_run_required
    else:
        legacy = LEGACY_SCHEMAS.get((schema_name, str(declared_version)))
        if legacy is None:
            raise ContractError("contract_major_unsupported", schema_name)
        payload_fields, parser, run_required = legacy
        version = str(declared_version)
    require_exact_fields(value, _COMMON_FIELDS | payload_fields, schema_name)
    if not SEMVER.fullmatch(str(value["schema_version"])):
        raise ContractError("contract_semver_invalid", "schema_version")
    artifact_id = str(uuid_value(value["artifact_id"], "artifact_id"))
    case_id = uuid_value(value["case_id"], "case_id", nullable=True)
    run_id = uuid_value(value["run_id"], "run_id", nullable=True)
    if run_required and run_id is None:
        raise ContractError("contract_required_value_missing", "run_id")
    created_at = value["created_at"]
    if not isinstance(created_at, str) or not created_at.endswith("Z"):
        raise ContractError("contract_timestamp_invalid", "created_at")
    try:
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("contract_timestamp_invalid", "created_at") from exc
    input_ids = tuple_of_strings(value["input_artifact_ids"], "input_artifact_ids")
    for input_id in input_ids:
        uuid_value(input_id, "input_artifact_ids")
    extensions = value["extensions"]
    if not isinstance(extensions, Mapping):
        raise ContractError("contract_type_invalid", "extensions")
    if extensions:
        raise ContractError("contract_unknown_field", "extensions")
    declared_hash = value["content_hash"]
    if not isinstance(declared_hash, str) or not SHA256.fullmatch(declared_hash):
        raise ContractError("contract_hash_invalid", "content_hash")
    # Validate every structured field before the integrity comparison so a
    # malformed contract receives its precise fail-closed reason. Integrity
    # remains mandatory once the wire shape is known to be valid.
    producer = _parse_producer(value["producer"])
    allowed_identities = authorized_producers.get(schema_name, ())
    if producer.identity not in allowed_identities:
        raise ContractError(
            "producer_not_authorized", f"{schema_name}:{producer.identity}"
        )
    warnings = _parse_warnings(value["warnings"])
    data_mode = enum_value(DataMode, value["data_mode"], "data_mode")
    status = enum_value(ArtifactStatus, value["status"], "status")
    payload = parser(value)
    if verify_hash and content_hash(value) != declared_hash:
        raise ContractError("artifact_integrity_failed")
    return Artifact(
        schema_name=schema_name,
        schema_version=version,
        artifact_id=artifact_id,
        case_id=case_id,
        run_id=run_id,
        producer=producer,
        created_at=created_at,
        input_artifact_ids=input_ids,
        content_hash=declared_hash,
        data_mode=data_mode,
        status=status,
        warnings=warnings,
        extensions=MappingProxyType({}),
        payload=payload,
    )
