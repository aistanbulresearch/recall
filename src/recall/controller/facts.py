from __future__ import annotations

from collections.abc import Sequence

from recall.contracts import parse_artifact
from recall.contracts.enums import FactState, PresenceState, ScanRunEventCode, ToolDecision
from recall.contracts.payloads import (
    AssessmentReceiptPayload,
    CandidateDeltaPayload,
    CitationAuditPayload,
    DataModePayload,
    EvidenceSnapshotPayload,
    FailurePayload,
    PrivacyReceiptPayload,
    RegistryResolutionPayload,
    ToolAuthorizationPayload,
)
from recall.controller.projection import project_failure
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY


_FACT_FIELDS = (
    "privacy_accepted",
    "registry_resolution_valid",
    "route_valid",
    "tool_authorization_complete",
    "source_retrieval_complete",
    "source_schema_valid",
    "data_mode_valid",
    "snapshot_integrity_valid",
    "assessment_valid",
    "citation_audit_complete",
    "all_material_claims_verified",
    "counter_evidence_complete",
)


def _latest(payloads: Sequence[object], payload_type: type):
    matches = [payload for payload in payloads if isinstance(payload, payload_type)]
    return None if not matches else matches[-1]


def build_policy_input_facts(
    ledger: LedgerPort, run_id: str
) -> dict[str, str]:
    artifacts = [
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
        for wire in ledger.list_by_run(run_id)
    ]
    artifacts.sort(key=lambda item: (item.created_at, item.artifact_id))
    payloads = [artifact.payload for artifact in artifacts]
    facts = {field: FactState.NOT_EVALUATED.value for field in _FACT_FIELDS}
    facts.update(
        {
            "candidate_delta_state": PresenceState.UNKNOWN.value,
            "unresolved_conflict_state": PresenceState.UNKNOWN.value,
            "budget_or_loop_failure_state": PresenceState.ABSENT.value,
            "existing_open_task_state": (
                PresenceState.PRESENT.value
                if ledger.list_review_tasks(run_id)
                else PresenceState.ABSENT.value
            ),
        }
    )

    privacy = _latest(payloads, PrivacyReceiptPayload)
    if privacy is not None:
        facts["privacy_accepted"] = privacy.decision.value
    registry = _latest(payloads, RegistryResolutionPayload)
    if registry is not None:
        facts["registry_resolution_valid"] = registry.validation_status.value
    if any(
        event.event_code is ScanRunEventCode.ROUTE_VALIDATED
        for event in ledger.list_scan_run_events(run_id)
    ):
        facts["route_valid"] = FactState.PASS.value

    authorizations = [
        payload for payload in payloads if isinstance(payload, ToolAuthorizationPayload)
    ]
    if authorizations:
        facts["tool_authorization_complete"] = (
            FactState.FAIL.value
            if any(item.decision is ToolDecision.DENIED for item in authorizations)
            else FactState.PASS.value
        )

    snapshot = _latest(payloads, EvidenceSnapshotPayload)
    if snapshot is not None:
        facts["source_retrieval_complete"] = snapshot.coverage_status.value
        facts["source_schema_valid"] = snapshot.coverage_status.value
        facts["snapshot_integrity_valid"] = FactState.PASS.value
        facts["unresolved_conflict_state"] = (
            PresenceState.PRESENT.value
            if snapshot.conflicts
            else PresenceState.ABSENT.value
        )
    mode = _latest(payloads, DataModePayload)
    if mode is not None:
        facts["data_mode_valid"] = mode.propagation_status.value
    candidate = _latest(payloads, CandidateDeltaPayload)
    if candidate is not None:
        facts["candidate_delta_state"] = candidate.candidate_delta_state.value
    assessment = _latest(payloads, AssessmentReceiptPayload)
    if assessment is not None:
        facts["assessment_valid"] = assessment.schema_validation_status.value
    audit = _latest(payloads, CitationAuditPayload)
    if audit is not None:
        facts["citation_audit_complete"] = audit.audit_completeness.value
        facts["counter_evidence_complete"] = audit.counter_evidence_coverage.value
        verdicts = tuple(item["verdict"] for item in audit.claim_verdicts)
        facts["all_material_claims_verified"] = (
            FactState.NOT_EVALUATED.value
            if not verdicts
            else (
                FactState.PASS.value
                if not audit.rejected_claim_ids
                and all(verdict == FactState.PASS.value for verdict in verdicts)
                else FactState.FAIL.value
            )
        )

    for artifact in artifacts:
        payload = artifact.payload
        if not isinstance(payload, FailurePayload):
            continue
        related_schema = ""
        if payload.related_artifact_ids:
            related = ledger.get_artifact(payload.related_artifact_ids[0])
            if related is not None:
                related_schema = str(related.get("schema_name", ""))
        projection = project_failure(payload.failure_code, related_schema)
        if projection is not None:
            facts[projection.fact_name] = projection.fact_state.value

    return facts
