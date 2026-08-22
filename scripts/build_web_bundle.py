"""Build the static artifact bundles that the demo surface renders.

Lane L2 owns the executable contracts and will produce these artifacts from
`run_fixture`. Until that exists, this script emits contract-shaped stand-in
artifacts so the deterministic View Model Builder can be built and tested
against real field paths rather than invented ones.

The `PrivacyReceipt` in every bundle is not a stand-in: it is produced by the
laboratory Privacy Gate in this repository from a synthetic corpus record.

Ownership: lane L3. Related tasks: RCL-406, RCL-307, RCL-208.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from recall.privacy.detectors import DeterministicDetector  # noqa: E402
from recall.privacy.gate import PrivacyGate  # noqa: E402
from recall.privacy.gemma import GemmaResidualDetector  # noqa: E402
from recall.privacy.minimizer import LabNote  # noqa: E402
from recall.privacy.signing import LocalSigner, content_hash  # noqa: E402

BUNDLE_KIND = "recall.web.static_artifact_bundle"
BUNDLE_VERSION = "1.0.0"
OUTPUT_DIRECTORY = REPO_ROOT / "web" / "src" / "bundles"
NAMESPACE = uuid.UUID("6f1b7a52-0f5f-4a3f-9f6d-2f3a1f0a9b11")
CREATED_AT = "2026-08-22T09:00:00Z"

PROVENANCE_NOTE = (
    "Contract-shaped stand-in artifacts for lane L3 user interface development. "
    "Lane L2 owns the executable contracts and the authoritative run output. "
    "Only the PrivacyReceipt is produced by real code in this repository. "
    "Nothing here is evidence that a backend run occurred."
)


def identifier(label: str) -> str:
    return str(uuid.uuid5(NAMESPACE, label))


def envelope(
    schema_name: str,
    schema_version: str,
    label: str,
    *,
    case_id: str | None,
    run_id: str | None,
    component: str,
    identity: str,
    inputs: list[str] | None = None,
    status: str = "VALID",
    data_mode: str = "SYNTHETIC",
    warnings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_name": schema_name,
        "schema_version": schema_version,
        "artifact_id": identifier(label),
        "case_id": case_id,
        "run_id": run_id,
        "producer": {"component": component, "version": "0.1.0", "identity": identity},
        "created_at": CREATED_AT,
        "input_artifact_ids": sorted(inputs or []),
        "data_mode": data_mode,
        "status": status,
        "warnings": warnings or [],
        "extensions": {},
    }


def finalize(artifact: dict[str, Any]) -> dict[str, Any]:
    artifact["content_hash"] = content_hash({k: v for k, v in artifact.items() if k != "content_hash"})
    return artifact


def build_privacy_receipt(scenario: str) -> dict[str, Any]:
    """Run the real Privacy Gate over one synthetic corpus record."""

    split = json.loads((REPO_ROOT / "corpus" / "generated" / "dev.json").read_text(encoding="utf-8"))
    record = split[0 if scenario != "halted" else 1]
    text = record["text"]

    detector = DeterministicDetector()
    detected = {(span.start, span.end) for span in detector.detect(text)}
    residuals = [span for span in record["spans"] if (span["start"], span["end"]) not in detected][:8]

    def transport(note_text: str, timeout_seconds: float) -> str:
        if scenario == "quarantine":
            return "I could not find any identifiers."
        return json.dumps(
            {
                "spans": [
                    {"start": s["start"], "end": s["end"], "identifier_class": s["identifier_class"]}
                    for s in residuals
                ]
            }
        )

    counter = {"value": 0}

    def uuid_factory() -> str:
        counter["value"] += 1
        return identifier(f"privacy-receipt-{scenario}-{counter['value']}")

    from datetime import datetime, timezone

    gate = PrivacyGate(
        signer=LocalSigner(key_id="demo-lab-key", key=b"demo-bundle-key-material"),
        gemma=GemmaResidualDetector(transport, model_id="stub-residual-source", clock=lambda: 0.0),
        clock=lambda: datetime(2026, 8, 22, 9, 0, 0, tzinfo=timezone.utc),
        uuid_factory=uuid_factory,
    )
    result = gate.process(
        LabNote.parse(
            {
                "case_key": record["record_id"],
                "note_text": text,
                "tenant_id": "lab-demo",
                "region": "eu-central",
                "gene": record["structured"]["gene"],
                "hgvs_c": record["structured"]["hgvs_c"],
                "hgvs_p": record["structured"]["hgvs_p"],
                "assembly": record["structured"]["assembly"],
            }
        )
    )
    return result.receipt


def build_bundle(scenario: str) -> dict[str, Any]:
    privacy_receipt = build_privacy_receipt(scenario)
    case_id = privacy_receipt["case_id"]
    run_id = identifier(f"run-{scenario}")
    watch_case_id = identifier(f"watch-case-{scenario}")
    previous_snapshot_id = identifier(f"snapshot-previous-{scenario}")
    current_snapshot_id = identifier(f"snapshot-current-{scenario}")
    candidate_id = identifier(f"candidate-{scenario}")
    audit_id = identifier(f"audit-{scenario}")
    decision_id = identifier(f"policy-decision-{scenario}")
    task_id = identifier(f"review-task-{scenario}")

    run_state = {"golden": "REVIEW_REQUIRED", "fault": "ABSTAIN", "halted": "HALTED"}[scenario]
    outcome = {"golden": "REVIEW_REQUIRED", "fault": "ABSTAIN", "halted": None}[scenario]

    artifacts: list[dict[str, Any]] = [privacy_receipt]

    artifacts.append(
        finalize(
            {
                **envelope("WatchCase", "2.0.0", f"watch-case-{scenario}", case_id=case_id, run_id=None,
                           component="workflow-controller", identity="controller-service"),
                "artifact_id": watch_case_id,
                "tenant_id": "lab-demo",
                "region": "eu-central",
                "state": {"golden": "AWAITING_HUMAN", "fault": "ACTIVE", "halted": "ATTENTION_REQUIRED"}[scenario],
                "monitoring_started_at": "2026-06-15T08:00:00Z",
                "monitoring_policy": "weekly-public-evidence-scan",
                "next_scan_at": None if scenario == "halted" else "2026-08-29T06:00:00Z",
                "source_cursors": {"clinvar": "2026-08-15", "pubmed": "2026-08-18"},
                "last_verified_snapshot_id": previous_snapshot_id,
                "last_verified_scan": {"run_id": identifier("run-previous"), "completed_at": "2026-08-15T06:04:00Z"},
                "pending_observation_hashes": [] if scenario == "golden" else [identifier(f"pending-{scenario}")[:32]],
                "attention_marker": None
                if scenario == "golden"
                else {
                    "reason_codes": ["citation_audit_incomplete"] if scenario == "fault" else ["ledger_integrity_unavailable"],
                    "first_seen_at": CREATED_AT,
                    "last_seen_at": CREATED_AT,
                    "related_run_ids": [run_id],
                    "operator_action_required": scenario == "halted",
                },
                "open_review_task_id": task_id if scenario == "golden" else None,
                "retention_policy": "contest-synthetic-30d",
            }
        )
    )

    artifacts.append(
        finalize(
            {
                **envelope("ScanRun", "1.0.0", f"scan-run-{scenario}", case_id=case_id, run_id=run_id,
                           component="workflow-controller", identity="controller-service",
                           inputs=[privacy_receipt["artifact_id"]]),
                "artifact_id": run_id,
                "watch_case_id": watch_case_id,
                "state": run_state,
                "scheduled_for": "2026-08-22T06:00:00Z",
                "attempt": 1,
                "lease_epoch": 4,
                "deadline_at": "2026-08-22T06:05:00Z",
                "budget_snapshot": {
                    "delegation_depth": 1,
                    "specialist_invocations": 3,
                    "model_calls_per_role": 1,
                    "schema_repairs": 1,
                    "agent_retries": 1,
                    "connector_retries": 3,
                    "repeated_state_limit": 2,
                    "wall_time_seconds": 300,
                    "step_deadlines": {"routing": 20, "watching": 90, "assessing": 60, "auditing": 90},
                    "token_ceilings": {"coordinator": 2000, "watcher": 4000, "assessor": 6000, "auditor": 6000},
                },
                "idempotency_key": f"{watch_case_id}:2026-08-22",
                "trace_id": identifier(f"trace-{scenario}").replace("-", "")[:32],
                "terminal_policy_decision_id": None if scenario == "halted" else decision_id,
                "failure_receipt_ids": [identifier(f"failure-{scenario}")] if scenario != "golden" else [],
            }
        )
    )

    transitions = ["CREATED", "QUEUED", "ROUTING", "WATCHING"]
    if scenario != "halted":
        transitions += ["ASSESSING", "AUDITING", "POLICY_EVALUATION", run_state]
    else:
        transitions += ["HALTED"]
    for index, (from_state, to_state) in enumerate(zip(transitions, transitions[1:]), start=1):
        artifacts.append(
            finalize(
                {
                    **envelope("ScanRunEvent", "1.0.0", f"event-{scenario}-{index}", case_id=case_id, run_id=run_id,
                               component="workflow-controller", identity="controller-service"),
                    "event_id": identifier(f"event-id-{scenario}-{index}"),
                    "sequence": index,
                    "from_state": from_state,
                    "to_state": to_state,
                    "event_code": f"transition_{to_state.lower()}",
                    "agent_id": {
                        "ROUTING": "fleet-coordinator",
                        "WATCHING": "evidence-watcher",
                        "ASSESSING": "evidence-assessor",
                        "AUDITING": "citation-auditor",
                    }.get(to_state, "workflow-controller"),
                    "lease_epoch": 4,
                }
            )
        )

    roles = (
        ("route.propose", "fleet-coordinator", "FLEET_COORDINATOR", "0.3.1"),
        ("evidence.watch", "evidence-watcher", "EVIDENCE_WATCHER", "0.3.4"),
        ("evidence.assess", "evidence-assessor", "EVIDENCE_ASSESSOR", "0.3.2"),
        ("citation.audit", "citation-auditor", "CITATION_AUDITOR", "0.3.5"),
    )
    artifacts.append(
        finalize(
            {
                **envelope("RegistryResolutionReceipt", "1.0.0", f"registry-{scenario}", case_id=case_id, run_id=run_id,
                           component="workflow-controller", identity="controller-service"),
                "requested_capabilities": [capability for capability, *_ in roles],
                "bindings": [
                    {
                        "capability": capability,
                        "agent_id": agent_id,
                        "role": role,
                        "revision": revision,
                        "manifest_digest": f"sha256:{identifier(f'manifest-{agent_id}').replace('-', '')}",
                        "binding_id": identifier(f"binding-{scenario}-{agent_id}"),
                        "region": "eu-central",
                        "validation_status": "VALIDATED",
                    }
                    for capability, agent_id, role, revision in roles
                ],
                "validation_status": "VALIDATED",
                "reason_codes": [],
            }
        )
    )

    artifacts.append(
        finalize(
            {
                **envelope("RoutingPlan", "1.0.0", f"routing-{scenario}", case_id=case_id, run_id=run_id,
                           component="fleet-coordinator", identity="coordinator-agent"),
                "requested_capabilities": [capability for capability, *_ in roles],
                "proposed_bindings": [
                    {"capability": capability, "agent_id": agent_id} for capability, agent_id, *_ in roles
                ],
                "route_order": [agent_id for _, agent_id, *_ in roles],
                "validation_status": "VALIDATED",
                "rationale_codes": ["capability_match", "revision_pinned"],
            }
        )
    )

    if scenario == "fault":
        artifacts.append(
            finalize(
                {
                    **envelope("ToolAuthorizationReceipt", "1.0.0", f"tool-denial-{scenario}", case_id=case_id,
                               run_id=run_id, component="tool-authorizer", identity="gateway-authorizer",
                               status="REJECTED"),
                    "agent_role": "EVIDENCE_ASSESSOR",
                    "tool_id": "review-task-writer",
                    "requested_action": "create_review_task",
                    "decision": "DENIED",
                    "policy_version": "1.0.1",
                    "reason_codes": ["tool_not_allowlisted", "role_cannot_create_terminal_outcome"],
                    "invocation_id": identifier(f"invocation-{scenario}"),
                }
            )
        )

    artifacts.append(
        finalize(
            {
                **envelope("CandidateDeltaReceipt", "1.0.0", f"candidate-{scenario}", case_id=case_id, run_id=run_id,
                           component="evidence-normalizer", identity="normalizer-service",
                           data_mode="CAPTURED_REPLAY"),
                "artifact_id": candidate_id,
                "previous_snapshot_id": previous_snapshot_id,
                "current_snapshot_id": current_snapshot_id,
                "exact_allele_match": True,
                "scope_match": True,
                "snapshot_complete": scenario != "halted",
                "new_observation_hashes": [identifier(f"observation-{scenario}-1").replace("-", "")],
                "candidate_delta_state": "PRESENT" if scenario != "halted" else "UNKNOWN",
                "reason_codes": [] if scenario != "halted" else ["snapshot_incomplete"],
            }
        )
    )

    for label, snapshot_id, effective_at in (
        ("previous", previous_snapshot_id, "2026-06-15T00:00:00Z"),
        ("current", current_snapshot_id, "2026-08-22T00:00:00Z"),
    ):
        artifacts.append(
            finalize(
                {
                    **envelope("EvidenceSnapshot", "1.0.0", f"snapshot-{label}-{scenario}", case_id=case_id,
                               run_id=run_id, component="evidence-watcher", identity="watcher-agent",
                               data_mode="CAPTURED_REPLAY"),
                    "artifact_id": snapshot_id,
                    "effective_at": effective_at,
                    "observation_ids": [identifier(f"observation-{label}-{scenario}-{i}") for i in range(1, 3)],
                    "coverage_status": "COMPLETE" if scenario != "halted" else "INCOMPLETE",
                    "source_cursors": {"clinvar": effective_at[:10], "pubmed": effective_at[:10]},
                    "normalized_facts": {"submission_count": 4 if label == "current" else 3},
                    "conflicts": [],
                    "snapshot_hash": f"sha256:{identifier(f'snapshot-hash-{label}-{scenario}').replace('-', '')}",
                }
            )
        )

    if scenario != "halted":
        artifacts.append(
            finalize(
                {
                    **envelope("EvidenceDelta", "2.0.0", f"delta-{scenario}", case_id=case_id, run_id=run_id,
                               component="evidence-assessor", identity="assessor-agent",
                               data_mode="CAPTURED_REPLAY", inputs=[candidate_id]),
                    "candidate_receipt_id": candidate_id,
                    "previous_snapshot_id": previous_snapshot_id,
                    "current_snapshot_id": current_snapshot_id,
                    "added_observation_refs": [identifier(f"observation-current-{scenario}-1")],
                    "removed_observation_refs": [],
                    "change_items": [
                        {"change_code": "new_functional_study", "observation_ref": identifier(f"observation-current-{scenario}-1")}
                    ],
                    "comparison": {
                        "classification_changed": False,
                        "classification_source_refs": [identifier(f"observation-previous-{scenario}-1")],
                    },
                    "materiality_proposal": "MATERIAL_CANDIDATE",
                    "uncertainties": ["single_source_functional_evidence"],
                    "counter_evidence_refs": [identifier(f"observation-current-{scenario}-2")],
                }
            )
        )

        verdicts = [
            {
                "claim_id": "claim-1",
                "verdict": "VERIFIED",
                "reason_codes": ["metadata_matched"],
                "refetched_source": {
                    "identifier": "PMID39779848",
                    "title": "Saturation genome editing of BRCA2",
                    "locator": "https://pubmed.ncbi.nlm.nih.gov/39779848/",
                    "content_hash": f"sha256:{identifier('source-hash-1').replace('-', '')}",
                },
            },
            {
                "claim_id": "claim-2",
                "verdict": "VERIFIED" if scenario == "golden" else "REJECTED_METADATA_MISMATCH",
                "reason_codes": ["metadata_matched"] if scenario == "golden" else ["refetched_title_mismatch"],
                "refetched_source": {
                    "identifier": "PMID39779857",
                    "title": "Functional characterisation follow-up",
                    "locator": "https://pubmed.ncbi.nlm.nih.gov/39779857/",
                    "content_hash": f"sha256:{identifier('source-hash-2').replace('-', '')}",
                },
            },
        ]
        artifacts.append(
            finalize(
                {
                    **envelope("CitationAuditReceipt", "1.0.0", f"audit-{scenario}", case_id=case_id, run_id=run_id,
                               component="citation-auditor", identity="auditor-agent",
                               data_mode="CAPTURED_REPLAY",
                               status="VALID" if scenario == "golden" else "INCOMPLETE"),
                    "artifact_id": audit_id,
                    "assessment_id": identifier(f"assessment-{scenario}"),
                    "audit_status": "COMPLETE" if scenario == "golden" else "INCOMPLETE",
                    "claim_verdicts": verdicts,
                    "metadata_refetches": 2,
                    "counter_evidence_coverage": "COMPLETE" if scenario == "golden" else "INCOMPLETE",
                    "audit_completeness": scenario == "golden",
                    "rejected_claim_ids": [] if scenario == "golden" else ["claim-2"],
                }
            )
        )

        facts = {
            "privacy_accepted": "PASS",
            "registry_resolution_valid": "PASS",
            "route_valid": "PASS",
            "tool_authorization_complete": "PASS" if scenario == "golden" else "FAIL",
            "source_retrieval_complete": "PASS",
            "source_schema_valid": "PASS",
            "data_mode_valid": "PASS",
            "snapshot_integrity_valid": "PASS",
            "assessment_valid": "PASS",
            "citation_audit_complete": "PASS" if scenario == "golden" else "FAIL",
            "all_material_claims_verified": "PASS" if scenario == "golden" else "FAIL",
            "counter_evidence_complete": "PASS" if scenario == "golden" else "FAIL",
            "candidate_delta_state": "PRESENT",
            "unresolved_conflict_state": "ABSENT",
            "budget_or_loop_failure_state": "ABSENT",
            "existing_open_task_state": "ABSENT",
        }
        artifacts.append(
            finalize(
                {
                    **envelope("PolicyDecision", "2.0.0", f"policy-{scenario}", case_id=case_id, run_id=run_id,
                               component="policy-gate", identity="policy-service",
                               inputs=[audit_id, candidate_id]),
                    "artifact_id": decision_id,
                    "policy_version": "1.0.1",
                    "input_facts": facts,
                    "outcome": outcome,
                    "reason_codes": ["all_prerequisites_verified", "material_change_candidate_present"]
                    if scenario == "golden"
                    else ["citation_audit_incomplete", "material_claim_rejected", "tool_authorization_incomplete"],
                    "missing_prerequisites": []
                    if scenario == "golden"
                    else ["all_material_claims_verified", "citation_audit_complete", "counter_evidence_complete", "tool_authorization_complete"],
                    "review_trigger": scenario == "golden",
                    "existing_task_id": None,
                }
            )
        )

    if scenario == "golden":
        artifacts.append(
            finalize(
                {
                    **envelope("ReviewTask", "1.0.0", f"task-{scenario}", case_id=case_id, run_id=run_id,
                               component="workflow-controller", identity="controller-outbox",
                               inputs=[decision_id]),
                    "artifact_id": task_id,
                    "watch_case_id": watch_case_id,
                    "trigger_decision_id": decision_id,
                    "state": "OPEN",
                    "priority_band": "REVIEW_SOON",
                    "claim_ids": ["claim-1", "claim-2"],
                    "audit_receipt_id": audit_id,
                    "simulation": True,
                    "deduplication_key": f"{watch_case_id}:{decision_id}",
                }
            )
        )

    if scenario != "golden":
        artifacts.append(
            finalize(
                {
                    **envelope("FailureReceipt", "1.0.0", f"failure-{scenario}", case_id=case_id, run_id=run_id,
                               component="workflow-controller", identity="controller-service", status="VALID"),
                    "artifact_id": identifier(f"failure-{scenario}"),
                    "failure_code": "citation_audit_incomplete" if scenario == "fault" else "ledger_integrity_unavailable",
                    "stage": "AUDITING" if scenario == "fault" else "POLICY_EVALUATION",
                    "retryable": scenario == "fault",
                    "attempt": 1,
                    "budget_state": {"connector_retries_used": 0, "agent_retries_used": 0},
                    "details": {"blocked_downstream_action": "review_task_creation"},
                    "related_artifact_ids": [run_id],
                    "safe_terminal": True,
                    "operator_action": "inspect_source_availability" if scenario == "halted" else "none",
                }
            )
        )

    subject_ids = [artifact["artifact_id"] for artifact in artifacts]
    artifacts.append(
        finalize(
            {
                **envelope("DataModeReceipt", "2.0.0", f"data-mode-{scenario}", case_id=case_id, run_id=run_id,
                           component="data-mode-gate", identity="mode-gate-service"),
                "subject_artifact_ids": sorted(subject_ids),
                "mode_set": ["CAPTURED_REPLAY", "SYNTHETIC"],
                "declared_composition": "SYNTHETIC_WITH_CAPTURED_REPLAY",
                "propagation_status": "COMPLETE",
                "reason_codes": [],
            }
        )
    )

    artifacts.append(
        finalize(
            {
                **envelope("DeploymentReceipt", "1.0.0", f"deployment-{scenario}", case_id=None, run_id=None,
                           component="release-controller", identity="release-service"),
                "runtime": {
                    "service": "recall-agent-runtime",
                    "revision": "recall-runtime-00007-abc",
                    "region": "eu-central",
                    "resource_name": "projects/<project>/locations/eu-central/services/recall-agent-runtime",
                    "read_back_at": CREATED_AT,
                },
                "deployed_components": ["intake", "controller", "agent-runtime", "reviewer-web"],
                "source_revision": "0000000",
                "deployed_at": CREATED_AT,
            }
        )
    )

    artifacts.append(
        finalize(
            {
                **envelope("ManagedPathReceipt", "1.0.0", f"managed-{scenario}", case_id=None, run_id=run_id,
                           component="health-aggregator", identity="health-service",
                           status="VALID" if scenario != "halted" else "DEGRADED"),
                "managed_status": "HEALTHY" if scenario != "halted" else "DEGRADED",
                "component_statuses": {
                    "agent_runtime": "HEALTHY",
                    "agent_registry": "HEALTHY",
                    "ledger": "HEALTHY" if scenario != "halted" else "UNAVAILABLE",
                },
                "reason_codes": [] if scenario != "halted" else ["ledger_unavailable"],
                "trace_id": identifier(f"trace-{scenario}").replace("-", "")[:32],
            }
        )
    )

    return {
        "bundle_kind": BUNDLE_KIND,
        "bundle_version": BUNDLE_VERSION,
        "bundle_id": scenario,
        "provenance": {
            "note": PROVENANCE_NOTE,
            "privacy_receipt_source": "produced by src/recall/privacy at bundle build time",
            "other_artifacts_source": "contract-shaped stand-in pending lane L2 run_fixture output",
            "contract_reference": "docs/contracts/ARTIFACT_CONTRACTS.md",
        },
        "artifacts": artifacts,
    }


def main() -> int:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for scenario in ("golden", "fault", "halted"):
        bundle = build_bundle(scenario)
        path = OUTPUT_DIRECTORY / f"{scenario}.json"
        path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"{scenario}: {len(bundle['artifacts'])} artifacts -> {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
