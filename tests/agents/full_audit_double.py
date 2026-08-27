from __future__ import annotations

from datetime import UTC, datetime, timedelta

from recall.agents.full_audit_models import RoleRunResult, TurnTelemetry
from recall.agents.schemas import (
    AssessmentAgentOutput,
    CitationAuditOutput,
    EvidenceSnapshotOutput,
)
from recall.contracts import AgentRole


class DeterministicFullAuditRunner:
    def __init__(self, *, now: datetime | None = None) -> None:
        self.now = now or datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
        self.roles: list[AgentRole] = []

    async def execute(self, role, prompt, tools, context):
        del prompt
        self.roles.append(role)
        if role is AgentRole.EVIDENCE_WATCHER:
            result = tools["evidence_connector"](
                stage="prepared",
                tool_context=context.tool_context("watcher-call"),
            )
            output = EvidenceSnapshotOutput.model_validate(
                {
                    "effective_at": self.now.isoformat(),
                    "observation_ids": [],
                    "coverage_status": "PASS" if result["records"] else "FAIL",
                    "source_cursors": {"clinvar": "42"},
                    "normalized_facts": {
                        "observation_count": len(result["records"]),
                        "scope": "synthetic",
                    },
                    "conflicts": [],
                    "snapshot_hash": "a" * 64,
                }
            )
        elif role is AgentRole.EVIDENCE_ASSESSOR:
            candidate_id = context.input_artifact_ids[0]
            tools["ledger_read"](
                artifact_id=candidate_id,
                tool_context=context.tool_context("assessor-call"),
            )
            output = AssessmentAgentOutput.model_validate(
                {
                    "evidence_delta": {
                        "candidate_receipt_id": candidate_id,
                        "previous_snapshot_id": None,
                        "current_snapshot_id": context.input_artifact_ids[1],
                        "added_observation_refs": [],
                        "removed_observation_refs": [],
                        "change_items": [],
                        "comparison": {
                            "classification_changed": "NOT_EVALUATED",
                            "classification_source_refs": [],
                        },
                        "materiality_proposal": "NO_CANDIDATE",
                        "uncertainties": [],
                        "counter_evidence_refs": [],
                    },
                    "assessment_receipt": {
                        "delta_id": "00000000-0000-4000-8000-000000000001",
                        "material_claims": [],
                        "counter_evidence_set": [],
                        "uncertainty_codes": [],
                        "schema_validation_status": "PASS",
                    },
                }
            )
        else:
            assessment_id = context.input_artifact_ids[0]
            tools["ledger_read"](
                artifact_id=assessment_id,
                tool_context=context.tool_context("auditor-call"),
            )
            output = CitationAuditOutput.model_validate(
                {
                    "assessment_id": assessment_id,
                    "audit_status": "COMPLETE",
                    "claim_results": [],
                    "metadata_refetches": [],
                    "counter_evidence_coverage": "PASS",
                    "audit_completeness": "PASS",
                    "rejected_claim_ids": [],
                }
            )
        call_ids = {
            AgentRole.EVIDENCE_WATCHER: ("watcher-call",),
            AgentRole.EVIDENCE_ASSESSOR: ("assessor-call",),
            AgentRole.CITATION_AUDITOR: ("auditor-call",),
        }[role]
        return RoleRunResult(
            output=output,
            turns=(TurnTelemetry(1, 100, 20, 5, 125, "STOP", True, 100),),
            tool_call_ids=call_ids,
            tool_response_ids=call_ids,
            trace_id=context.trace_id,
            invocation_id=context.invocation_id,
            started_at=self.now,
            completed_at=self.now + timedelta(milliseconds=100),
            http_429_count=0,
        )
