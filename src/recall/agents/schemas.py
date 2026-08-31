from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)


class StrictOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


ArtifactId = Annotated[
    str,
    Field(
        pattern=(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        )
    ),
]
NonEmptyString = Annotated[str, Field(min_length=1)]


class SourceCursorsOutput(StrictOutput):
    synthetic_source: str | None = Field(default=None, alias="synthetic-source")
    captured_replay: str | None = Field(default=None, alias="captured-replay")
    pubmed: str | None = None
    geo: str | None = None
    clinvar: str | None = None

    @model_validator(mode="after")
    def require_visible_source(self) -> SourceCursorsOutput:
        if not any(
            (
                self.synthetic_source,
                self.captured_replay,
                self.pubmed,
                self.geo,
                self.clinvar,
            )
        ):
            raise ValueError("source_cursor_required")
        return self


class NormalizedFactsOutput(StrictOutput):
    observation_count: int = Field(ge=0)
    scope: str = Field(min_length=1)


class EvidenceSnapshotOutput(StrictOutput):
    effective_at: datetime
    observation_ids: list[str]
    coverage_status: Literal["PASS", "FAIL", "NOT_EVALUATED"]
    source_cursors: SourceCursorsOutput
    normalized_facts: NormalizedFactsOutput
    conflicts: list[dict[str, Any]]
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    def to_contract_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class ComparisonOutput(StrictOutput):
    classification_changed: Literal["PASS", "FAIL", "NOT_EVALUATED"]
    classification_source_refs: list[ArtifactId]


class EvidenceDeltaOutput(StrictOutput):
    candidate_receipt_id: ArtifactId
    previous_snapshot_id: ArtifactId | None
    current_snapshot_id: ArtifactId
    added_observation_refs: list[ArtifactId]
    removed_observation_refs: list[ArtifactId]
    change_items: list[dict[str, Any]]
    comparison: ComparisonOutput
    materiality_proposal: NonEmptyString
    uncertainties: list[NonEmptyString]
    counter_evidence_refs: list[ArtifactId]


class AssessmentReceiptOutput(StrictOutput):
    delta_id: ArtifactId
    material_claims: list[NonEmptyString]
    counter_evidence_set: list[NonEmptyString]
    uncertainty_codes: list[NonEmptyString]
    schema_validation_status: Literal["PASS", "FAIL", "NOT_EVALUATED"]


class AssessmentAgentOutput(StrictOutput):
    evidence_delta: EvidenceDeltaOutput
    assessment_receipt: AssessmentReceiptOutput


class RefetchedSourceOutput(StrictOutput):
    identifier: str
    title: str
    locator: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ClaimAuditProposal(StrictOutput):
    claim_id: str
    cited_identifier: str
    reason_codes: list[str]
    refetched_source: RefetchedSourceOutput | None


class CitationAuditOutput(StrictOutput):
    assessment_id: str
    audit_status: Literal["COMPLETE", "INCOMPLETE"]
    claim_results: list[ClaimAuditProposal]
    metadata_refetches: list[RefetchedSourceOutput]
    counter_evidence_coverage: Literal["PASS", "FAIL", "NOT_EVALUATED"]
    audit_completeness: Literal["PASS", "FAIL", "NOT_EVALUATED"]
    rejected_claim_ids: list[str]


class RoutingPlanOutput(StrictOutput):
    requested_capabilities: list[str]
    proposed_bindings: list[dict[str, Any]]
    route_order: list[str]
    validation_status: Literal["PASS", "FAIL", "NOT_EVALUATED"]
    rationale_codes: list[str]


_SAFE_VALIDATION_LOCATIONS = frozenset(
    {
        "effective_at",
        "observation_ids",
        "coverage_status",
        "source_cursors",
        "synthetic-source",
        "captured-replay",
        "pubmed",
        "geo",
        "clinvar",
        "normalized_facts",
        "observation_count",
        "scope",
        "conflicts",
        "snapshot_hash",
        "evidence_delta",
        "candidate_receipt_id",
        "previous_snapshot_id",
        "current_snapshot_id",
        "added_observation_refs",
        "removed_observation_refs",
        "change_items",
        "comparison",
        "classification_changed",
        "classification_source_refs",
        "materiality_proposal",
        "uncertainties",
        "counter_evidence_refs",
        "assessment_receipt",
        "delta_id",
        "material_claims",
        "counter_evidence_set",
        "uncertainty_codes",
        "schema_validation_status",
        "assessment_id",
        "audit_status",
        "claim_results",
        "claim_id",
        "cited_identifier",
        "reason_codes",
        "refetched_source",
        "identifier",
        "title",
        "locator",
        "content_hash",
        "metadata_refetches",
        "counter_evidence_coverage",
        "audit_completeness",
        "rejected_claim_ids",
        "requested_capabilities",
        "proposed_bindings",
        "route_order",
        "validation_status",
        "rationale_codes",
    }
)
_SAFE_VALIDATION_TYPES = frozenset(
    {
        "datetime_from_date_parsing",
        "dict_type",
        "extra_forbidden",
        "greater_than_equal",
        "int_parsing",
        "json_invalid",
        "list_type",
        "literal_error",
        "missing",
        "model_type",
        "string_pattern_mismatch",
        "string_too_short",
        "string_type",
        "value_error",
    }
)


def schema_validation_error_code(error: ValidationError) -> str:
    failures = error.errors(
        include_url=False,
        include_context=False,
        include_input=False,
    )
    if not failures:
        return "agent_schema_invalid:pydantic_invalid:root:validation_error"
    failure = failures[0]
    failure_type = str(failure.get("type", "validation_error"))
    if failure_type == "json_invalid":
        return "agent_schema_invalid:json_invalid"
    if failure_type not in _SAFE_VALIDATION_TYPES:
        failure_type = "validation_error"
    location = ".".join(
        (
            str(item)
            if isinstance(item, int)
            else item
            if isinstance(item, str) and item in _SAFE_VALIDATION_LOCATIONS
            else "field"
        )
        for item in failure.get("loc", ())
    ) or "root"
    return f"agent_schema_invalid:pydantic_invalid:{location}:{failure_type}"


def safe_contract_code(code: str) -> str:
    if code and len(code) <= 80 and all(
        character.islower() or character.isdigit() or character == "_"
        for character in code
    ):
        return code
    return "contract_error"


def safe_schema_failure_detail(code: str) -> str | None:
    if code == "agent_response_missing:response_missing":
        return "response_missing"
    prefix = "agent_schema_invalid:"
    if not code.startswith(prefix):
        return None
    detail = code.removeprefix(prefix)
    if detail == "json_invalid":
        return detail
    if detail.startswith("pydantic_invalid:"):
        parts = detail.split(":")
        if len(parts) != 3 or parts[2] not in (
            _SAFE_VALIDATION_TYPES | {"validation_error"}
        ):
            return "pydantic_invalid:field:validation_error"
        location = parts[1]
        if not location or any(
            token not in _SAFE_VALIDATION_LOCATIONS
            and token != "root"
            and not token.isdigit()
            for token in location.split(".")
        ):
            location = "field"
        return f"pydantic_invalid:{location}:{parts[2]}"
    artifact_prefix = "artifact_contract:"
    if detail.startswith(artifact_prefix):
        return artifact_prefix + safe_contract_code(
            detail.removeprefix(artifact_prefix)
        )
    return None
