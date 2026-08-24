from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ..enums import FactState
from ..errors import ContractError
from ..validation import (
    SHA256,
    enum_value,
    non_empty_string,
    require_exact_fields,
    tuple_of_strings,
    uuid_value,
)
from .lifecycle import _timestamp


def _mapping(value: Any, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", field)
    return MappingProxyType(dict(value))


def _mapping_list(value: Any, field: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, Mapping) for item in value
    ):
        raise ContractError("contract_type_invalid", field)
    return tuple(MappingProxyType(dict(item)) for item in value)


def _artifact_ids(value: Any, field: str) -> tuple[str, ...]:
    ids = tuple_of_strings(value, field)
    for artifact_id in ids:
        uuid_value(artifact_id, field)
    return ids


def _ordered_unique_strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ContractError("contract_type_invalid", field)
    result = tuple(value)
    if len(result) != len(set(result)):
        raise ContractError("contract_order_or_uniqueness_invalid", field)
    return result


@dataclass(frozen=True, slots=True)
class RoutingPlanPayload:
    requested_capabilities: tuple[str, ...]
    proposed_bindings: tuple[Mapping[str, object], ...]
    route_order: tuple[str, ...]
    validation_status: FactState
    rationale_codes: tuple[str, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "requested_capabilities": list(self.requested_capabilities),
            "proposed_bindings": [dict(item) for item in self.proposed_bindings],
            "route_order": list(self.route_order),
            "validation_status": self.validation_status.value,
            "rationale_codes": list(self.rationale_codes),
        }


def parse_routing_plan_payload(value: Mapping[str, Any]) -> RoutingPlanPayload:
    bindings = _mapping_list(value["proposed_bindings"], "proposed_bindings")
    binding_fields = frozenset(
        {
            "capability",
            "agent_id",
            "role",
            "revision",
            "manifest_digest",
            "binding_id",
            "region",
        }
    )
    for binding in bindings:
        require_exact_fields(binding, binding_fields, "proposed_bindings")
        for field in binding_fields:
            non_empty_string(binding[field], f"proposed_bindings.{field}")
    return RoutingPlanPayload(
        requested_capabilities=tuple_of_strings(
            value["requested_capabilities"], "requested_capabilities"
        ),
        proposed_bindings=bindings,
        route_order=_ordered_unique_strings(value["route_order"], "route_order"),
        validation_status=enum_value(
            FactState, value["validation_status"], "validation_status"
        ),
        rationale_codes=tuple_of_strings(
            value["rationale_codes"], "rationale_codes"
        ),
    )


@dataclass(frozen=True, slots=True)
class EvidenceObservationPayload:
    source: str
    source_record_id: str
    retrieved_at: str
    source_version: str
    source_locator: str
    source_content_hash: str
    structured_fields: Mapping[str, object]
    retrieval_status: FactState

    def to_wire(self) -> dict[str, object]:
        return {
            "source": self.source,
            "source_record_id": self.source_record_id,
            "retrieved_at": self.retrieved_at,
            "source_version": self.source_version,
            "source_locator": self.source_locator,
            "source_content_hash": self.source_content_hash,
            "structured_fields": dict(self.structured_fields),
            "retrieval_status": self.retrieval_status.value,
        }


def parse_evidence_observation_payload(
    value: Mapping[str, Any],
) -> EvidenceObservationPayload:
    source_hash = value["source_content_hash"]
    if not isinstance(source_hash, str) or not SHA256.fullmatch(source_hash):
        raise ContractError("contract_hash_invalid", "source_content_hash")
    return EvidenceObservationPayload(
        source=non_empty_string(value["source"], "source"),
        source_record_id=non_empty_string(
            value["source_record_id"], "source_record_id"
        ),
        retrieved_at=_timestamp(value["retrieved_at"], "retrieved_at"),
        source_version=non_empty_string(value["source_version"], "source_version"),
        source_locator=non_empty_string(value["source_locator"], "source_locator"),
        source_content_hash=source_hash,
        structured_fields=_mapping(value["structured_fields"], "structured_fields"),
        retrieval_status=enum_value(
            FactState, value["retrieval_status"], "retrieval_status"
        ),
    )


@dataclass(frozen=True, slots=True)
class EvidenceDeltaPayload:
    candidate_receipt_id: str
    previous_snapshot_id: str | None
    current_snapshot_id: str
    added_observation_refs: tuple[str, ...]
    removed_observation_refs: tuple[str, ...]
    change_items: tuple[Mapping[str, object], ...]
    comparison: Mapping[str, object]
    materiality_proposal: str
    uncertainties: tuple[str, ...]
    counter_evidence_refs: tuple[str, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "candidate_receipt_id": self.candidate_receipt_id,
            "previous_snapshot_id": self.previous_snapshot_id,
            "current_snapshot_id": self.current_snapshot_id,
            "added_observation_refs": list(self.added_observation_refs),
            "removed_observation_refs": list(self.removed_observation_refs),
            "change_items": [dict(item) for item in self.change_items],
            "comparison": dict(self.comparison),
            "materiality_proposal": self.materiality_proposal,
            "uncertainties": list(self.uncertainties),
            "counter_evidence_refs": list(self.counter_evidence_refs),
        }


def parse_evidence_delta_payload(value: Mapping[str, Any]) -> EvidenceDeltaPayload:
    comparison = _mapping(value["comparison"], "comparison")
    require_exact_fields(
        comparison,
        frozenset({"classification_changed", "classification_source_refs"}),
        "comparison",
    )
    enum_value(
        FactState, comparison["classification_changed"], "classification_changed"
    )
    _artifact_ids(
        comparison["classification_source_refs"], "classification_source_refs"
    )
    return EvidenceDeltaPayload(
        candidate_receipt_id=str(
            uuid_value(value["candidate_receipt_id"], "candidate_receipt_id")
        ),
        previous_snapshot_id=uuid_value(
            value["previous_snapshot_id"], "previous_snapshot_id", nullable=True
        ),
        current_snapshot_id=str(
            uuid_value(value["current_snapshot_id"], "current_snapshot_id")
        ),
        added_observation_refs=_artifact_ids(
            value["added_observation_refs"], "added_observation_refs"
        ),
        removed_observation_refs=_artifact_ids(
            value["removed_observation_refs"], "removed_observation_refs"
        ),
        change_items=_mapping_list(value["change_items"], "change_items"),
        comparison=comparison,
        materiality_proposal=non_empty_string(
            value["materiality_proposal"], "materiality_proposal"
        ),
        uncertainties=tuple_of_strings(value["uncertainties"], "uncertainties"),
        counter_evidence_refs=_artifact_ids(
            value["counter_evidence_refs"], "counter_evidence_refs"
        ),
    )


@dataclass(frozen=True, slots=True)
class DeploymentReceiptPayload:
    runtime: Mapping[str, object]
    deployed_components: tuple[str, ...]
    source_revision: str
    deployed_at: str

    def to_wire(self) -> dict[str, object]:
        return {
            "runtime": dict(self.runtime),
            "deployed_components": list(self.deployed_components),
            "source_revision": self.source_revision,
            "deployed_at": self.deployed_at,
        }


def parse_deployment_receipt_payload(
    value: Mapping[str, Any],
) -> DeploymentReceiptPayload:
    runtime = _mapping(value["runtime"], "runtime")
    require_exact_fields(
        runtime,
        frozenset(
            {"service", "revision", "region", "resource_name", "read_back_at"}
        ),
        "runtime",
    )
    for field in ("service", "revision", "region", "resource_name"):
        non_empty_string(runtime[field], f"runtime.{field}")
    _timestamp(runtime["read_back_at"], "runtime.read_back_at")
    return DeploymentReceiptPayload(
        runtime=runtime,
        deployed_components=tuple_of_strings(
            value["deployed_components"], "deployed_components"
        ),
        source_revision=non_empty_string(value["source_revision"], "source_revision"),
        deployed_at=_timestamp(value["deployed_at"], "deployed_at"),
    )


@dataclass(frozen=True, slots=True)
class ManagedPathReceiptPayload:
    managed_status: FactState
    component_statuses: Mapping[str, object]
    reason_codes: tuple[str, ...]
    trace_id: str

    def to_wire(self) -> dict[str, object]:
        return {
            "managed_status": self.managed_status.value,
            "component_statuses": dict(self.component_statuses),
            "reason_codes": list(self.reason_codes),
            "trace_id": self.trace_id,
        }


def parse_managed_path_receipt_payload(
    value: Mapping[str, Any],
) -> ManagedPathReceiptPayload:
    statuses = _mapping(value["component_statuses"], "component_statuses")
    for component, status in statuses.items():
        non_empty_string(component, "component_statuses.key")
        enum_value(FactState, status, f"component_statuses.{component}")
    return ManagedPathReceiptPayload(
        managed_status=enum_value(
            FactState, value["managed_status"], "managed_status"
        ),
        component_statuses=statuses,
        reason_codes=tuple_of_strings(value["reason_codes"], "reason_codes"),
        trace_id=str(uuid_value(value["trace_id"], "trace_id")),
    )
