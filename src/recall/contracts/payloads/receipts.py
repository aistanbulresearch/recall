from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ..enums import (
    AuditStatus,
    CitationVerdict,
    EndpointClass,
    ExecutionLocus,
    FactState,
    PrivacyDecision,
    ResolutionMode,
    TransportClass,
)
from ..errors import ContractError
from ..validation import (
    SHA256,
    enum_value,
    non_empty_string,
    require_exact_fields,
    tuple_of_strings,
    uuid_value,
)


def _mapping(value: Any, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", field)
    return MappingProxyType(dict(value))


def _privacy_detectors(value: Any) -> Mapping[str, object]:
    detectors = _mapping(value, "detectors")
    require_exact_fields(detectors, frozenset({"deterministic", "gemma"}), "detectors")
    deterministic = _mapping(detectors["deterministic"], "detectors.deterministic")
    gemma = _mapping(detectors["gemma"], "detectors.gemma")
    require_exact_fields(
        deterministic,
        frozenset({"version", "approved_spans"}),
        "detectors.deterministic",
    )
    require_exact_fields(
        gemma,
        frozenset({"version", "invoked", "schema_valid", "approved_residual_spans"}),
        "detectors.gemma",
    )
    for field, raw in (
        ("approved_spans", deterministic["approved_spans"]),
        ("approved_residual_spans", gemma["approved_residual_spans"]),
    ):
        tuple_of_strings(raw, f"detectors.{field}")
    if not isinstance(gemma["invoked"], bool) or not isinstance(
        gemma["schema_valid"], bool
    ):
        raise ContractError("contract_type_invalid", "detectors.gemma.flags")
    non_empty_string(deterministic["version"], "detectors.deterministic.version")
    non_empty_string(gemma["version"], "detectors.gemma.version")
    return MappingProxyType(
        {"deterministic": dict(deterministic), "gemma": dict(gemma)}
    )


@dataclass(frozen=True, slots=True)
class PrivacyReceiptPayload:
    decision: PrivacyDecision
    detector_versions: Mapping[str, object]
    identifier_classes_checked: tuple[str, ...]
    detectors: Mapping[str, object]
    outbound: Mapping[str, object]
    payload_hash: str
    signature_ref: Mapping[str, str]
    execution_locus: ExecutionLocus | None = None
    transport_class: TransportClass | None = None
    endpoint_class: EndpointClass | None = None
    model_id: str | None = None
    model_revision: str | None = None

    def to_wire(self) -> dict[str, object]:
        value: dict[str, object] = {
            "decision": self.decision.value,
            "detector_versions": dict(self.detector_versions),
            "identifier_classes_checked": list(self.identifier_classes_checked),
            "detectors": dict(self.detectors),
            "outbound": dict(self.outbound),
            "payload_hash": self.payload_hash,
            "signature_ref": dict(self.signature_ref),
        }
        if self.execution_locus is not None:
            value.update(
                {
                    "execution_locus": self.execution_locus.value,
                    "transport_class": self.transport_class.value,
                    "endpoint_class": self.endpoint_class.value,
                    "model_id": self.model_id,
                    "model_revision": self.model_revision,
                }
            )
        return value


def parse_privacy_receipt_payload(
    value: Mapping[str, Any],
) -> PrivacyReceiptPayload:
    payload_hash = value["payload_hash"]
    if not isinstance(payload_hash, str) or not SHA256.fullmatch(payload_hash):
        raise ContractError("contract_hash_invalid", "payload_hash")
    signature_ref = _mapping(value["signature_ref"], "signature_ref")
    require_exact_fields(
        signature_ref,
        frozenset({"key_id", "algorithm", "signature"}),
        "signature_ref",
    )
    for field in signature_ref:
        non_empty_string(signature_ref[field], f"signature_ref.{field}")
    versions = _mapping(value["detector_versions"], "detector_versions")
    for key, item in versions.items():
        non_empty_string(key, "detector_versions.key")
        non_empty_string(item, f"detector_versions.{key}")
    outbound = _mapping(value["outbound"], "outbound")
    require_exact_fields(
        outbound,
        frozenset({"scan_status", "allowed_field_paths", "raw_text_field_count"}),
        "outbound",
    )
    tuple_of_strings(outbound["allowed_field_paths"], "outbound.allowed_field_paths")
    if isinstance(outbound["raw_text_field_count"], bool) or not isinstance(
        outbound["raw_text_field_count"], int
    ):
        raise ContractError("contract_type_invalid", "outbound.raw_text_field_count")
    return PrivacyReceiptPayload(
        decision=enum_value(PrivacyDecision, value["decision"], "decision"),
        detector_versions=versions,
        identifier_classes_checked=tuple_of_strings(
            value["identifier_classes_checked"], "identifier_classes_checked"
        ),
        detectors=_privacy_detectors(value["detectors"]),
        outbound=outbound,
        payload_hash=payload_hash,
        signature_ref=signature_ref,
    )


def parse_privacy_receipt_v11_payload(
    value: Mapping[str, Any],
) -> PrivacyReceiptPayload:
    parsed = parse_privacy_receipt_payload(value)
    model_revision = non_empty_string(value["model_revision"], "model_revision")
    if not model_revision.startswith("sha256:") or not SHA256.fullmatch(
        model_revision.removeprefix("sha256:")
    ):
        raise ContractError("contract_hash_invalid", "model_revision")
    return PrivacyReceiptPayload(
        decision=parsed.decision,
        detector_versions=parsed.detector_versions,
        identifier_classes_checked=parsed.identifier_classes_checked,
        detectors=parsed.detectors,
        outbound=parsed.outbound,
        payload_hash=parsed.payload_hash,
        signature_ref=parsed.signature_ref,
        execution_locus=enum_value(
            ExecutionLocus, value["execution_locus"], "execution_locus"
        ),
        transport_class=enum_value(
            TransportClass, value["transport_class"], "transport_class"
        ),
        endpoint_class=enum_value(
            EndpointClass, value["endpoint_class"], "endpoint_class"
        ),
        model_id=non_empty_string(value["model_id"], "model_id"),
        model_revision=model_revision,
    )


@dataclass(frozen=True, slots=True)
class RegistryResolutionPayload:
    requested_capabilities: tuple[str, ...]
    bindings: tuple[Mapping[str, object], ...]
    resolution_mode: ResolutionMode
    validation_status: FactState
    reason_codes: tuple[str, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "requested_capabilities": list(self.requested_capabilities),
            "bindings": [dict(item) for item in self.bindings],
            "resolution_mode": self.resolution_mode.value,
            "validation_status": self.validation_status.value,
            "reason_codes": list(self.reason_codes),
        }


def parse_registry_resolution_payload(
    value: Mapping[str, Any],
) -> RegistryResolutionPayload:
    bindings = value["bindings"]
    if not isinstance(bindings, list) or any(
        not isinstance(item, Mapping) for item in bindings
    ):
        raise ContractError("contract_type_invalid", "bindings")
    parsed_bindings: list[Mapping[str, object]] = []
    fields = frozenset(
        {
            "capability",
            "agent_id",
            "role",
            "revision",
            "manifest_digest",
            "binding_id",
            "region",
            "validation_status",
        }
    )
    for item in bindings:
        require_exact_fields(item, fields, "bindings")
        for field in fields:
            non_empty_string(item[field], f"bindings.{field}")
        parsed_bindings.append(MappingProxyType(dict(item)))
    return RegistryResolutionPayload(
        requested_capabilities=tuple_of_strings(
            value["requested_capabilities"], "requested_capabilities"
        ),
        bindings=tuple(parsed_bindings),
        resolution_mode=enum_value(
            ResolutionMode, value["resolution_mode"], "resolution_mode"
        ),
        validation_status=enum_value(
            FactState, value["validation_status"], "validation_status"
        ),
        reason_codes=tuple_of_strings(value["reason_codes"], "reason_codes"),
    )


@dataclass(frozen=True, slots=True)
class AssessmentReceiptPayload:
    delta_id: str
    material_claims: tuple[str, ...]
    counter_evidence_set: tuple[str, ...]
    uncertainty_codes: tuple[str, ...]
    schema_validation_status: FactState

    def to_wire(self) -> dict[str, object]:
        return {
            "delta_id": self.delta_id,
            "material_claims": list(self.material_claims),
            "counter_evidence_set": list(self.counter_evidence_set),
            "uncertainty_codes": list(self.uncertainty_codes),
            "schema_validation_status": self.schema_validation_status.value,
        }


def parse_assessment_receipt_payload(
    value: Mapping[str, Any],
) -> AssessmentReceiptPayload:
    return AssessmentReceiptPayload(
        delta_id=str(uuid_value(value["delta_id"], "delta_id")),
        material_claims=tuple_of_strings(value["material_claims"], "material_claims"),
        counter_evidence_set=tuple_of_strings(
            value["counter_evidence_set"], "counter_evidence_set"
        ),
        uncertainty_codes=tuple_of_strings(
            value["uncertainty_codes"], "uncertainty_codes"
        ),
        schema_validation_status=enum_value(
            FactState,
            value["schema_validation_status"],
            "schema_validation_status",
        ),
    )


@dataclass(frozen=True, slots=True)
class CitationAuditPayload:
    assessment_id: str
    audit_status: AuditStatus
    claim_verdicts: tuple[Mapping[str, object], ...]
    metadata_refetches: tuple[Mapping[str, object], ...]
    counter_evidence_coverage: FactState
    audit_completeness: FactState
    rejected_claim_ids: tuple[str, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "assessment_id": self.assessment_id,
            "audit_status": self.audit_status.value,
            "claim_verdicts": [dict(item) for item in self.claim_verdicts],
            "metadata_refetches": [dict(item) for item in self.metadata_refetches],
            "counter_evidence_coverage": self.counter_evidence_coverage.value,
            "audit_completeness": self.audit_completeness.value,
            "rejected_claim_ids": list(self.rejected_claim_ids),
        }


def parse_citation_audit_payload(value: Mapping[str, Any]) -> CitationAuditPayload:
    claims = value["claim_verdicts"]
    refetches = value["metadata_refetches"]
    if not isinstance(claims, list) or any(
        not isinstance(item, Mapping) for item in claims
    ):
        raise ContractError("contract_type_invalid", "claim_verdicts")
    if not isinstance(refetches, list) or any(
        not isinstance(item, Mapping) for item in refetches
    ):
        raise ContractError("contract_type_invalid", "metadata_refetches")
    parsed_claims: list[Mapping[str, object]] = []
    source_fields = frozenset({"identifier", "title", "locator", "content_hash"})
    for item in claims:
        require_exact_fields(
            item,
            frozenset({"claim_id", "verdict", "reason_codes", "refetched_source"}),
            "claim_verdicts",
        )
        verdict = enum_value(
            CitationVerdict, item["verdict"], "claim_verdicts.verdict"
        )
        claim_id = non_empty_string(item["claim_id"], "claim_verdicts.claim_id")
        raw_source = item["refetched_source"]
        if (verdict is CitationVerdict.UNAVAILABLE) is not (raw_source is None):
            raise ContractError(
                "contract_value_invalid", "claim_verdicts.refetched_source"
            )
        source: Mapping[str, object] | None = None
        if raw_source is not None:
            source = _mapping(raw_source, "claim_verdicts.refetched_source")
            require_exact_fields(
                source, source_fields, "claim_verdicts.refetched_source"
            )
            for field in source_fields - {"content_hash"}:
                non_empty_string(
                    source[field], f"claim_verdicts.refetched_source.{field}"
                )
            if not isinstance(source["content_hash"], str) or not SHA256.fullmatch(
                source["content_hash"]
            ):
                raise ContractError(
                    "contract_hash_invalid", "refetched_source.content_hash"
                )
        parsed_claims.append(
            MappingProxyType(
                {
                    "claim_id": claim_id,
                    "verdict": verdict.value,
                    "reason_codes": list(
                        tuple_of_strings(item["reason_codes"], "claim_verdicts.reason_codes")
                    ),
                    "refetched_source": (
                        None if source is None else dict(source)
                    ),
                }
            )
        )
    parsed_refetches: list[Mapping[str, object]] = []
    for item in refetches:
        require_exact_fields(item, source_fields, "metadata_refetches")
        for field in source_fields - {"content_hash"}:
            non_empty_string(item[field], f"metadata_refetches.{field}")
        if not isinstance(item["content_hash"], str) or not SHA256.fullmatch(
            item["content_hash"]
        ):
            raise ContractError("contract_hash_invalid", "metadata_refetches.content_hash")
        parsed_refetches.append(MappingProxyType(dict(item)))
    return CitationAuditPayload(
        assessment_id=str(uuid_value(value["assessment_id"], "assessment_id")),
        audit_status=enum_value(AuditStatus, value["audit_status"], "audit_status"),
        claim_verdicts=tuple(parsed_claims),
        metadata_refetches=tuple(parsed_refetches),
        counter_evidence_coverage=enum_value(
            FactState,
            value["counter_evidence_coverage"],
            "counter_evidence_coverage",
        ),
        audit_completeness=enum_value(
            FactState, value["audit_completeness"], "audit_completeness"
        ),
        rejected_claim_ids=tuple_of_strings(
            value["rejected_claim_ids"], "rejected_claim_ids"
        ),
    )
