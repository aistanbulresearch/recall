from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from typing import Any

from .canonical import content_hash
from .enums import ArtifactStatus, DataMode
from .models import parse_artifact


def build_artifact(
    *,
    schema_name: str,
    schema_version: str,
    artifact_id: str,
    case_id: str | None,
    run_id: str | None,
    producer: Mapping[str, str],
    created_at: str,
    input_artifact_ids: Sequence[str],
    data_mode: DataMode,
    status: ArtifactStatus,
    payload: Mapping[str, Any],
    authorized_producers: Mapping[str, Collection[str]],
    warnings: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    wire: dict[str, object] = {
        "schema_name": schema_name,
        "schema_version": schema_version,
        "artifact_id": artifact_id,
        "case_id": case_id,
        "run_id": run_id,
        "producer": dict(producer),
        "created_at": created_at,
        "input_artifact_ids": list(input_artifact_ids),
        "content_hash": "0" * 64,
        "data_mode": data_mode.value,
        "status": status.value,
        "warnings": [dict(item) for item in warnings],
        "extensions": {},
    }
    wire.update(payload)
    wire["content_hash"] = content_hash(wire)
    return parse_artifact(
        wire, authorized_producers=authorized_producers
    ).to_wire()
