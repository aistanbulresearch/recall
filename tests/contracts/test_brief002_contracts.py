from __future__ import annotations

from copy import deepcopy

import pytest

from recall.contracts import (
    ArtifactStatus,
    ContractError,
    DataMode,
    build_artifact,
)
from recall.ledger.producers import PRODUCER_REGISTRY


COMMON = {
    "artifact_id": "f7617fa1-2f75-47f3-b88d-ec72e88e3051",
    "case_id": "728d6e23-5ee4-4bd4-9319-4304f55628f3",
    "run_id": "b1d74cb8-25ac-4a84-ab9d-5a71a366c2da",
    "created_at": "2026-08-22T06:30:00Z",
}


@pytest.mark.parametrize(
    ("schema_name", "schema_version", "identity", "payload"),
    [
        (
            "RoutingPlan",
            "1.0.0",
            "fleet-coordinator",
            {
                "requested_capabilities": ["evidence-watch"],
                "proposed_bindings": [],
                "route_order": ["evidence-watcher"],
                "validation_status": "PASS",
                "rationale_codes": ["pinned_manifest_selected"],
            },
        ),
        (
            "EvidenceObservation",
            "1.0.0",
            "evidence-connector",
            {
                "source": "pubmed",
                "source_record_id": "PMID:39779848",
                "retrieved_at": "2026-08-16T23:18:30Z",
                "source_version": "captured-1.0.1",
                "source_locator": "https://pubmed.ncbi.nlm.nih.gov/39779848/",
                "source_content_hash": "a" * 64,
                "structured_fields": {"title": "Synthetic metadata fixture"},
                "retrieval_status": "PASS",
            },
        ),
        (
            "EvidenceDelta",
            "2.0.0",
            "evidence-assessor",
            {
                "candidate_receipt_id": COMMON["artifact_id"],
                "previous_snapshot_id": None,
                "current_snapshot_id": COMMON["artifact_id"],
                "added_observation_refs": [COMMON["artifact_id"]],
                "removed_observation_refs": [],
                "change_items": [{"code": "publication_added"}],
                "comparison": {
                    "classification_changed": "NOT_EVALUATED",
                    "classification_source_refs": [],
                },
                "materiality_proposal": "REVIEW",
                "uncertainties": ["non_clinical_research_only"],
                "counter_evidence_refs": [],
            },
        ),
        (
            "DeploymentReceipt",
            "1.0.0",
            "release-controller",
            {
                "runtime": {
                    "service": "agent-engine",
                    "revision": "local-smoke",
                    "region": "global",
                    "resource_name": "not-deployed",
                    "read_back_at": "2026-08-22T06:30:00Z",
                },
                "deployed_components": ["evidence-watcher"],
                "source_revision": "bc855957",
                "deployed_at": "2026-08-22T06:30:00Z",
            },
        ),
        (
            "ManagedPathReceipt",
            "1.0.0",
            "health-aggregator",
            {
                "managed_status": "NOT_EVALUATED",
                "component_statuses": {"model_armor": "NOT_EVALUATED"},
                "reason_codes": ["runtime_not_deployed"],
                "trace_id": COMMON["run_id"],
            },
        ),
    ],
)
def test_new_l2_and_lane_contracts_are_strict(
    schema_name: str,
    schema_version: str,
    identity: str,
    payload: dict[str, object],
) -> None:
    wire = build_artifact(
        schema_name=schema_name,
        schema_version=schema_version,
        artifact_id=COMMON["artifact_id"],
        case_id=COMMON["case_id"],
        run_id=COMMON["run_id"],
        producer={"component": schema_name, "version": "0.1.0", "identity": identity},
        created_at=COMMON["created_at"],
        input_artifact_ids=(),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID,
        payload=payload,
        authorized_producers=PRODUCER_REGISTRY,
    )
    assert wire["schema_name"] == schema_name
    broken = deepcopy(wire)
    broken["unexpected"] = True
    with pytest.raises(ContractError, match="contract_unknown_field"):
        from recall.contracts import parse_artifact

        parse_artifact(broken, authorized_producers=PRODUCER_REGISTRY)


def test_citation_audit_uses_complete_incomplete_and_verdict_enums() -> None:
    wire = build_artifact(
        schema_name="CitationAuditReceipt",
        schema_version="1.0.0",
        artifact_id=COMMON["artifact_id"],
        case_id=COMMON["case_id"],
        run_id=COMMON["run_id"],
        producer={
            "component": "citation-auditor",
            "version": "0.1.0",
            "identity": "citation-auditor",
        },
        created_at=COMMON["created_at"],
        input_artifact_ids=(),
        data_mode=DataMode.CAPTURED_REPLAY,
        status=ArtifactStatus.VALID,
        payload={
            "assessment_id": COMMON["artifact_id"],
            "audit_status": "COMPLETE",
            "claim_verdicts": [
                {
                    "claim_id": "claim-001",
                    "verdict": "VERIFIED",
                    "reason_codes": [],
                    "refetched_source": {
                        "identifier": "PMID:39779848",
                        "title": "Synthetic metadata fixture",
                        "locator": "https://pubmed.ncbi.nlm.nih.gov/39779848/",
                        "content_hash": "d" * 64,
                    },
                }
            ],
            "metadata_refetches": [],
            "counter_evidence_coverage": "PASS",
            "audit_completeness": "PASS",
            "rejected_claim_ids": [],
        },
        authorized_producers=PRODUCER_REGISTRY,
    )
    assert wire["audit_status"] == "COMPLETE"
    assert wire["claim_verdicts"][0]["verdict"] == "VERIFIED"


@pytest.mark.parametrize(
    ("source_cursors", "normalized_facts", "expected_code"),
    [
        ({}, {"observation_count": 1}, "source_cursor_required"),
        (
            {"captured-replay": "stage-1"},
            {},
            "normalized_facts_required",
        ),
    ],
)
def test_pass_snapshot_rejects_each_empty_content_path(
    source_cursors: dict[str, str],
    normalized_facts: dict[str, object],
    expected_code: str,
) -> None:
    with pytest.raises(
        ContractError,
        match=expected_code,
    ):
        build_artifact(
            schema_name="EvidenceSnapshot",
            schema_version="1.0.0",
            artifact_id=COMMON["artifact_id"],
            case_id=COMMON["case_id"],
            run_id=COMMON["run_id"],
            producer={
                "component": "evidence-watcher",
                "version": "0.1.0",
                "identity": "evidence-watcher",
            },
            created_at=COMMON["created_at"],
            input_artifact_ids=(),
            data_mode=DataMode.SYNTHETIC,
            status=ArtifactStatus.VALID,
            payload={
                "effective_at": COMMON["created_at"],
                "observation_ids": [],
                "coverage_status": "PASS",
                "source_cursors": source_cursors,
                "normalized_facts": normalized_facts,
                "conflicts": [],
                "snapshot_hash": "b" * 64,
            },
            authorized_producers=PRODUCER_REGISTRY,
        )


@pytest.mark.parametrize(
    "resolution_mode", ["REGISTRY", "MANUAL_SERVICE", "PINNED_FALLBACK"]
)
def test_registry_resolution_1_1_accepts_only_closed_resolution_modes(
    resolution_mode: str,
) -> None:
    wire = build_artifact(
        schema_name="RegistryResolutionReceipt",
        schema_version="1.1.0",
        artifact_id=COMMON["artifact_id"],
        case_id=COMMON["case_id"],
        run_id=COMMON["run_id"],
        producer={
            "component": "controller",
            "version": "0.1.0",
            "identity": "controller",
        },
        created_at=COMMON["created_at"],
        input_artifact_ids=(),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID,
        payload={
            "requested_capabilities": ["evidence-watch"],
            "bindings": [],
            "resolution_mode": resolution_mode,
            "validation_status": "PASS",
            "reason_codes": [],
        },
        authorized_producers=PRODUCER_REGISTRY,
    )
    assert wire["resolution_mode"] == resolution_mode


def test_registry_resolution_rejects_unknown_mode() -> None:
    with pytest.raises(ContractError, match="contract_enum_invalid:resolution_mode"):
        build_artifact(
            schema_name="RegistryResolutionReceipt",
            schema_version="1.1.0",
            artifact_id=COMMON["artifact_id"],
            case_id=COMMON["case_id"],
            run_id=COMMON["run_id"],
            producer={
                "component": "controller",
                "version": "0.1.0",
                "identity": "controller",
            },
            created_at=COMMON["created_at"],
            input_artifact_ids=(),
            data_mode=DataMode.SYNTHETIC,
            status=ArtifactStatus.VALID,
            payload={
                "requested_capabilities": ["evidence-watch"],
                "bindings": [],
                "resolution_mode": "UNBOUNDED_DISCOVERY",
                "validation_status": "PASS",
                "reason_codes": [],
            },
            authorized_producers=PRODUCER_REGISTRY,
        )


def test_privacy_signature_ref_is_strict_nested_object() -> None:
    wire = build_artifact(
        schema_name="PrivacyReceipt",
        schema_version="1.0.0",
        artifact_id=COMMON["artifact_id"],
        case_id=COMMON["case_id"],
        run_id=COMMON["run_id"],
        producer={
            "component": "privacy-gate",
            "version": "0.1.0",
            "identity": "privacy-gate",
        },
        created_at=COMMON["created_at"],
        input_artifact_ids=(),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID,
        payload={
            "decision": "ACCEPTED",
            "detector_versions": {"deterministic": "1.0.0", "gemma": "1.0.0"},
            "identifier_classes_checked": ["synthetic-fixture"],
            "detectors": {
                "deterministic": {"version": "1.0.0", "approved_spans": []},
                "gemma": {
                    "version": "1.0.0",
                    "invoked": True,
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
                "key_id": "local-test-key",
                "algorithm": "HMAC-SHA256",
                "signature": "b" * 64,
            },
        },
        authorized_producers=PRODUCER_REGISTRY,
    )
    assert wire["signature_ref"]["algorithm"] == "HMAC-SHA256"

    broken = deepcopy(wire)
    broken["signature_ref"]["unexpected"] = True
    with pytest.raises(ContractError, match="contract_unknown_field:signature_ref"):
        from recall.contracts import parse_artifact

        parse_artifact(
            broken,
            authorized_producers=PRODUCER_REGISTRY,
            verify_hash=False,
        )
