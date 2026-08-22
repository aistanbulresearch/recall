from __future__ import annotations

from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from recall.contracts import ArtifactStatus, DataMode, build_artifact
from recall.ledger import InMemoryLedger
from recall.ledger.producers import PRODUCER_REGISTRY


def append_policy_artifacts(
    ledger: InMemoryLedger,
    *,
    run_id: str,
    case_id: str,
    now: datetime,
    candidate: str,
    tool_decision: str = "ALLOWED",
    citation_pass: bool = True,
) -> dict[str, str]:
    created_at = now.isoformat().replace("+00:00", "Z")
    ids: dict[str, str] = {}

    def append(schema: str, identity: str, payload: dict[str, object]) -> str:
        artifact_id = str(uuid5(NAMESPACE_URL, f"{run_id}:{schema}"))
        wire = build_artifact(
            schema_name=schema,
            schema_version={
                "DataModeReceipt": "2.0.0",
                "RegistryResolutionReceipt": "1.1.0",
            }.get(schema, "1.0.0"),
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
            data_mode=DataMode.SYNTHETIC,
            status=ArtifactStatus.VALID,
            payload=payload,
            authorized_producers=PRODUCER_REGISTRY,
        )
        ledger.append_artifact(wire)
        ids[schema] = artifact_id
        return artifact_id

    append(
        "PrivacyReceipt",
        "privacy-gate",
        {
            "decision": "ACCEPTED",
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
            "signature_ref": {
                "key_id": "fixture-key",
                "algorithm": "HMAC-SHA256",
                "signature": "f" * 64,
            },
        },
    )
    append(
        "RegistryResolutionReceipt",
        "controller",
        {
            "requested_capabilities": ["evidence-watch"],
            "bindings": [],
            "resolution_mode": "PINNED_FALLBACK",
            "validation_status": "PASS",
            "reason_codes": [],
        },
    )
    append(
        "ToolAuthorizationReceipt",
        "controller-authorizer",
        {
            "agent_role": "EVIDENCE_ASSESSOR",
            "tool_id": "synthetic-replay-reader",
            "requested_action": "read_fixture",
            "decision": tool_decision,
            "policy_version": "1.0.1",
            "reason_codes": (
                [] if tool_decision == "ALLOWED" else ["tool_not_allowlisted"]
            ),
            "invocation_id": str(uuid5(NAMESPACE_URL, f"{run_id}:invocation")),
        },
    )
    snapshot_id = append(
        "EvidenceSnapshot",
        "evidence-watcher",
        {
            "effective_at": created_at,
            "observation_ids": [],
            "coverage_status": "PASS",
            "source_cursors": {"synthetic": "cursor-1"},
            "normalized_facts": {"record_count": 1},
            "conflicts": [],
            "snapshot_hash": "b" * 64,
        },
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
            "new_observation_hashes": [] if candidate == "ABSENT" else ["c" * 64],
            "candidate_delta_state": candidate,
            "reason_codes": [],
        },
    )
    append(
        "DataModeReceipt",
        "controller-mode-gate",
        {
            "subject_artifact_ids": [candidate_id],
            "mode_set": ["SYNTHETIC"],
            "declared_composition": "SYNTHETIC_ONLY",
            "propagation_status": "PASS",
            "reason_codes": [],
        },
    )
    if candidate == "PRESENT":
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
        )
        append(
            "CitationAuditReceipt",
            "citation-auditor",
            {
                "assessment_id": assessment_id,
                "audit_status": "COMPLETE",
                "claim_verdicts": [
                    {
                        "claim_id": "claim-001",
                        "verdict": "VERIFIED" if citation_pass else "MISMATCH",
                        "reason_codes": [] if citation_pass else ["citation_mismatch"],
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
                "rejected_claim_ids": [] if citation_pass else ["claim-001"],
            },
        )
    return ids
