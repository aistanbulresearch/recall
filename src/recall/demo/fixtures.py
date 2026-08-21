from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from recall.contracts import ArtifactStatus, ContractError, DataMode, build_artifact
from recall.contracts.fault_fixture import authorize_tool_request, parse_fault_fixture
from recall.contracts.enums import PresenceState, ToolDecision
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY


_FIELDS = frozenset(
    {
        "fixture_id",
        "mode_set",
        "candidate_delta_state",
        "tool_decision",
        "citation_verdict",
        "policy_available",
        "source_cursors",
        "schedule_epoch",
    }
)


@dataclass(frozen=True, slots=True)
class FixtureSpec:
    fixture_id: str
    mode_set: tuple[DataMode, ...]
    candidate_delta_state: PresenceState
    tool_decision: ToolDecision
    citation_verdict: str | None
    policy_available: bool
    source_cursors: Mapping[str, str]
    schedule_epoch: str


def parse_fixture_spec(value: Mapping[str, Any]) -> FixtureSpec:
    if "fixture_version" in value:
        fault = parse_fault_fixture(value)
        authorization = authorize_tool_request(fault.tool_request, ())
        return FixtureSpec(
            fixture_id=f"fault-run-{fault.citation_probe.claim_id}",
            mode_set=tuple(
                sorted(
                    {fault.institutional_mode, fault.evidence_mode},
                    key=lambda item: item.value,
                )
            ),
            candidate_delta_state=PresenceState.PRESENT,
            tool_decision=authorization.decision,
            citation_verdict="FAIL" if fault.citation_mismatch else "PASS",
            policy_available=True,
            source_cursors={
                "captured-replay": fault.citation_probe.cited_identifier
            },
            schedule_epoch="2026-08-22T06:02:00Z",
        )
    if set(value) != _FIELDS:
        unknown = sorted(set(value) - _FIELDS)
        missing = sorted(_FIELDS - set(value))
        code = "fixture_unknown_field" if unknown else "fixture_required_field_missing"
        raise ContractError(code, f"unknown={unknown};missing={missing}")
    raw_modes = value["mode_set"]
    if not isinstance(raw_modes, list):
        raise ContractError("contract_type_invalid", "mode_set")
    modes = tuple(DataMode(item) for item in raw_modes)
    if modes != tuple(sorted(set(modes), key=lambda item: item.value)):
        raise ContractError("contract_order_or_uniqueness_invalid", "mode_set")
    cursors = value["source_cursors"]
    if not isinstance(cursors, Mapping) or any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in cursors.items()
    ):
        raise ContractError("contract_type_invalid", "source_cursors")
    fixture_id = value["fixture_id"]
    schedule_epoch = value["schedule_epoch"]
    policy_available = value["policy_available"]
    citation = value["citation_verdict"]
    if not isinstance(fixture_id, str) or not fixture_id:
        raise ContractError("contract_type_invalid", "fixture_id")
    if not isinstance(schedule_epoch, str) or not schedule_epoch.endswith("Z"):
        raise ContractError("contract_timestamp_invalid", "schedule_epoch")
    if not isinstance(policy_available, bool):
        raise ContractError("contract_type_invalid", "policy_available")
    if citation not in {None, "PASS", "FAIL"}:
        raise ContractError("contract_enum_invalid", "citation_verdict")
    candidate = PresenceState(value["candidate_delta_state"])
    if (candidate is PresenceState.PRESENT) is not (citation is not None):
        raise ContractError("contract_value_invalid", "citation_verdict")
    return FixtureSpec(
        fixture_id=fixture_id,
        mode_set=modes,
        candidate_delta_state=candidate,
        tool_decision=ToolDecision(value["tool_decision"]),
        citation_verdict=citation,
        policy_available=policy_available,
        source_cursors=dict(sorted(cursors.items())),
        schedule_epoch=schedule_epoch,
    )


def append_fixture_artifacts(
    ledger: LedgerPort,
    *,
    spec: FixtureSpec,
    run_id: str,
    case_id: str,
    now: datetime,
) -> dict[str, str]:
    created_at = now.isoformat().replace("+00:00", "Z")
    identifiers: dict[str, str] = {}

    def append(
        schema: str,
        identity: str,
        payload: Mapping[str, object],
        data_mode: DataMode,
    ) -> str:
        artifact_id = str(uuid5(NAMESPACE_URL, f"{run_id}:{schema}"))
        wire = build_artifact(
            schema_name=schema,
            schema_version="2.0.0" if schema == "DataModeReceipt" else "1.0.0",
            artifact_id=artifact_id,
            case_id=case_id,
            run_id=run_id,
            producer={
                "component": f"fixture-{schema.lower()}",
                "version": "0.1.0",
                "identity": identity,
            },
            created_at=created_at,
            input_artifact_ids=(),
            data_mode=data_mode,
            status=ArtifactStatus.VALID,
            payload=payload,
            authorized_producers=PRODUCER_REGISTRY,
        )
        ledger.append_artifact(wire)
        identifiers[schema] = artifact_id
        return artifact_id

    append(
        "PrivacyReceipt",
        "privacy-gate",
        {
            "decision": "PASS",
            "detector_versions": {"deterministic": "1.0.0", "gemma": "not-invoked"},
            "identifier_classes_checked": ["synthetic-fixture"],
            "detectors": {
                "deterministic": {"version": "1.0.0", "approved_spans": []},
                "gemma": {
                    "version": "not-invoked",
                    "invoked": False,
                    "schema_valid": True,
                    "approved_residual_spans": [],
                },
            },
            "outbound": {
                "scan_status": "PASS",
                "allowed_field_paths": ["$.synthetic_record"],
                "raw_text_field_count": 0,
            },
            "payload_hash": "a" * 64,
            "signature_ref": "fixture-signature",
        },
        DataMode.SYNTHETIC,
    )
    append(
        "RegistryResolutionReceipt",
        "controller",
        {
            "requested_capabilities": ["evidence-watch"],
            "bindings": [],
            "validation_status": "PASS",
            "reason_codes": [],
        },
        DataMode.SYNTHETIC,
    )
    append(
        "ToolAuthorizationReceipt",
        "controller-authorizer",
        {
            "agent_role": "EVIDENCE_ASSESSOR",
            "tool_id": "captured-replay-reader",
            "requested_action": "read_fixture",
            "decision": spec.tool_decision.value,
            "policy_version": "1.0.1",
            "reason_codes": (
                []
                if spec.tool_decision is ToolDecision.ALLOWED
                else ["tool_not_allowlisted"]
            ),
            "invocation_id": str(uuid5(NAMESPACE_URL, f"{run_id}:invocation")),
        },
        DataMode.SYNTHETIC,
    )
    snapshot_id = append(
        "EvidenceSnapshot",
        "evidence-watcher",
        {
            "effective_at": created_at,
            "observation_ids": [],
            "coverage_status": "PASS",
            "source_cursors": dict(spec.source_cursors),
            "normalized_facts": {"record_count": 1},
            "conflicts": [],
            "snapshot_hash": "b" * 64,
        },
        DataMode.CAPTURED_REPLAY,
    )
    candidate_id = append(
        "CandidateDeltaReceipt",
        "evidence-normalizer",
        {
            "previous_snapshot_id": None,
            "current_snapshot_id": snapshot_id,
            "exact_allele_match": True,
            "scope_match": True,
            "snapshot_complete": True,
            "new_observation_hashes": (
                []
                if spec.candidate_delta_state is PresenceState.ABSENT
                else ["c" * 64]
            ),
            "candidate_delta_state": spec.candidate_delta_state.value,
            "reason_codes": [],
        },
        DataMode.CAPTURED_REPLAY,
    )
    append(
        "DataModeReceipt",
        "controller-mode-gate",
        {
            "subject_artifact_ids": [candidate_id],
            "mode_set": [mode.value for mode in spec.mode_set],
            "declared_composition": "SYNTHETIC_WITH_CAPTURED_REPLAY",
            "propagation_status": "PASS",
            "reason_codes": [],
        },
        DataMode.SYNTHETIC,
    )
    if spec.candidate_delta_state is PresenceState.PRESENT:
        assessment_id = append(
            "AssessmentReceipt",
            "evidence-assessor",
            {
                "delta_id": candidate_id,
                "material_claims": ["claim-001"],
                "counter_evidence_set": ["counter-001"],
                "uncertainty_codes": [],
                "schema_validation_status": "PASS",
            },
            DataMode.CAPTURED_REPLAY,
        )
        append(
            "CitationAuditReceipt",
            "citation-auditor",
            {
                "assessment_id": assessment_id,
                "audit_status": "PASS",
                "claim_verdicts": [
                    {
                        "claim_id": "claim-001",
                        "verdict": spec.citation_verdict,
                        "reason_codes": (
                            [] if spec.citation_verdict == "PASS" else ["citation_mismatch"]
                        ),
                        "refetched_source": {
                            "identifier": "PMID:12345678",
                            "title": "Refetched synthetic evidence",
                            "locator": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
                            "content_hash": "d" * 64,
                        },
                    }
                ],
                "metadata_refetches": [],
                "counter_evidence_coverage": "PASS",
                "audit_completeness": "PASS",
                "rejected_claim_ids": (
                    [] if spec.citation_verdict == "PASS" else ["claim-001"]
                ),
            },
            DataMode.CAPTURED_REPLAY,
        )
    return identifiers
