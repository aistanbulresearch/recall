from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class SourceCursorsOutput(StrictOutput):
    captured_replay: str | None = Field(default=None, alias="captured-replay")
    pubmed: str | None = None
    geo: str | None = None
    clinvar: str | None = None

    @model_validator(mode="after")
    def require_visible_source(self) -> SourceCursorsOutput:
        if not any((self.captured_replay, self.pubmed, self.geo, self.clinvar)):
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


class EvidenceDeltaOutput(StrictOutput):
    candidate_receipt_id: str
    previous_snapshot_id: str | None
    current_snapshot_id: str
    added_observation_refs: list[str]
    removed_observation_refs: list[str]
    change_items: list[dict[str, Any]]
    comparison: dict[str, Any]
    materiality_proposal: str
    uncertainties: list[str]
    counter_evidence_refs: list[str]


class AssessmentReceiptOutput(StrictOutput):
    delta_id: str
    material_claims: list[str]
    counter_evidence_set: list[str]
    uncertainty_codes: list[str]
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
    refetched_source: RefetchedSourceOutput


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
