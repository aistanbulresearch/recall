from __future__ import annotations

from typing import Any

from .payloads import (
    parse_deployment_receipt_payload,
    parse_evidence_delta_payload,
    parse_evidence_observation_payload,
    parse_managed_path_receipt_payload,
    parse_routing_plan_payload,
    parse_assessment_receipt_payload,
    parse_candidate_delta_payload,
    parse_citation_audit_payload,
    parse_data_mode_payload,
    parse_evidence_snapshot_payload,
    parse_failure_payload,
    parse_policy_decision_payload,
    parse_privacy_receipt_payload,
    parse_privacy_receipt_v11_payload,
    parse_registry_resolution_payload,
    parse_review_task_payload,
    parse_scan_run_event_payload,
    parse_scan_run_payload,
    parse_scan_run_v11_payload,
    parse_tool_authorization_payload,
    parse_watch_case_payload,
    parse_cohort_day_manifest_payload,
    parse_cohort_day_manifest_v3_payload,
    parse_cohort_day_manifest_v31_payload,
    parse_cohort_day_manifest_v32_payload,
    parse_cohort_day_manifest_v20_payload,
    parse_cohort_day_failure_receipt_payload,
    parse_cohort_history_receipt_payload,
    parse_cohort_headroom_receipt_payload,
    parse_compressed_cycle_failure_receipt_payload,
    parse_cohort_ramp_gate_receipt_payload,
    parse_agent_execution_receipt_payload,
)


_COHORT_MANIFEST_FIELDS = frozenset(
    {
        "day_index",
        "selected_for_date",
        "scheduled_for",
        "source_commit",
        "image_digest",
        "trigger_code",
        "previous_manifest_id",
        "managed_history_starts_at_day_index",
        "delta",
        "cumulative",
        "cases",
        "vcv_anchors",
        "execution_history",
    }
)

_COHORT_MANIFEST_V3_FIELDS = _COHORT_MANIFEST_FIELDS | frozenset(
    {
        "cycle_id",
        "cycle_index",
        "plan_version",
        "plan_sha256",
        "cohort_due_date",
        "window_start",
        "window_end",
        "schedule_mode",
        "headroom_receipt_id",
    }
)
_COHORT_MANIFEST_V31_FIELDS = _COHORT_MANIFEST_V3_FIELDS | frozenset(
    {"epoch_label", "evaluation_role", "ramp_gate_receipt_id", "write_metrics", "parity"}
)
_COHORT_MANIFEST_V32_FIELDS = _COHORT_MANIFEST_V31_FIELDS | frozenset(
    {"agent_execution_summary", "run_outcomes"}
)


LEGACY_SCHEMAS: dict[tuple[str, str], tuple[frozenset[str], Any, bool]] = {
    ("ScanRun", "1.0.0"): (
        frozenset(
            {
                "watch_case_id", "state", "scheduled_for", "attempt",
                "lease_epoch", "deadline_at", "budget_snapshot",
                "idempotency_key", "trace_id", "terminal_policy_decision_id",
                "failure_receipt_ids",
            }
        ),
        parse_scan_run_payload,
        True,
    ),
    ("PrivacyReceipt", "1.0.0"): (
        frozenset(
            {
                "decision", "detector_versions", "identifier_classes_checked",
                "detectors", "outbound", "payload_hash", "signature_ref",
            }
        ),
        parse_privacy_receipt_payload,
        False,
    ),
    ("CohortDayManifest", "2.0.0"): (
        _COHORT_MANIFEST_FIELDS,
        parse_cohort_day_manifest_v20_payload,
        True,
    ),
    ("CohortDayManifest", "2.1.0"): (
        _COHORT_MANIFEST_FIELDS,
        parse_cohort_day_manifest_payload,
        True,
    ),
    ("CohortDayManifest", "3.0.0"): (
        _COHORT_MANIFEST_V3_FIELDS,
        parse_cohort_day_manifest_v3_payload,
        True,
    ),
    ("CohortDayManifest", "3.1.0"): (
        _COHORT_MANIFEST_V31_FIELDS,
        parse_cohort_day_manifest_v31_payload,
        True,
    ),
}


SCHEMAS: dict[str, tuple[str, frozenset[str], Any, bool]] = {
    "CohortHistoryReceipt": (
        "1.0.0",
        frozenset(
            {
                "evidence_path",
                "evidence_sha256",
                "evidence_git_blob_oid",
                "source_commit",
                "source_tree",
                "phase",
                "trigger_code",
                "day_index",
                "executed_at",
                "selected_for_date",
                "created_run_ids",
                "selected_case_ids",
                "excluded_case_ids",
                "runs_created",
                "runs_predicted",
                "readback_counts",
                "direct_exit_code",
                "evidence_classification",
                "atomic_check_ids",
            }
        ),
        parse_cohort_history_receipt_payload,
        True,
    ),
    "CohortDayManifest": (
        "3.2.0",
        _COHORT_MANIFEST_V32_FIELDS,
        parse_cohort_day_manifest_v32_payload,
        True,
    ),
    "CompressedCycleFailureReceipt": (
        "1.0.0",
        frozenset(
            {
                "cohort_due_date",
                "scheduled_for",
                "failure_code",
                "runs_predicted",
                "runs_created",
                "evidence_state",
                "decision_reference",
                "continuation_policy",
            }
        ),
        parse_compressed_cycle_failure_receipt_payload,
        True,
    ),
    "CohortHeadroomReceipt": (
        "1.0.0",
        frozenset(
            {
                "plan_sha256",
                "input_snapshot_sha256",
                "gate_version",
                "required_cycle_ids",
                "observed_cycles",
                "aggregate_runs_predicted",
                "aggregate_runs_created",
                "aggregate_run_events",
                "decision",
                "reason_codes",
                "evidence_watermark",
            }
        ),
        parse_cohort_headroom_receipt_payload,
        True,
    ),
    "CohortRampGateReceipt": (
        "1.0.0",
        frozenset(
            {
                "target_plan_sha256", "target_cycle_id", "input_snapshot_sha256",
                "gate_version", "metric_policy", "predecessor_binding",
                "observed_metrics", "decision", "reason_codes",
                "evidence_watermark",
            }
        ),
        parse_cohort_ramp_gate_receipt_payload,
        True,
    ),
    "CohortDayFailureReceipt": (
        "1.0.0",
        frozenset(
            {
                "day_index",
                "selected_for_date",
                "detected_at",
                "failure_code",
                "expected_manifest_id",
                "runs_predicted",
                "runs_created",
                "source_commit",
                "image_digest",
                "continuation_policy",
            }
        ),
        parse_cohort_day_failure_receipt_payload,
        True,
    ),
    "RoutingPlan": (
        "1.0.0",
        frozenset(
            {
                "requested_capabilities",
                "proposed_bindings",
                "route_order",
                "validation_status",
                "rationale_codes",
            }
        ),
        parse_routing_plan_payload,
        True,
    ),
    "EvidenceObservation": (
        "1.0.0",
        frozenset(
            {
                "source",
                "source_record_id",
                "retrieved_at",
                "source_version",
                "source_locator",
                "source_content_hash",
                "structured_fields",
                "retrieval_status",
            }
        ),
        parse_evidence_observation_payload,
        True,
    ),
    "EvidenceDelta": (
        "2.0.0",
        frozenset(
            {
                "candidate_receipt_id",
                "previous_snapshot_id",
                "current_snapshot_id",
                "added_observation_refs",
                "removed_observation_refs",
                "change_items",
                "comparison",
                "materiality_proposal",
                "uncertainties",
                "counter_evidence_refs",
            }
        ),
        parse_evidence_delta_payload,
        True,
    ),
    "DeploymentReceipt": (
        "1.0.0",
        frozenset(
            {"runtime", "deployed_components", "source_revision", "deployed_at"}
        ),
        parse_deployment_receipt_payload,
        True,
    ),
    "ManagedPathReceipt": (
        "1.0.0",
        frozenset(
            {"managed_status", "component_statuses", "reason_codes", "trace_id"}
        ),
        parse_managed_path_receipt_payload,
        True,
    ),
    "PrivacyReceipt": (
        "1.1.0",
        frozenset(
            {
                "decision",
                "detector_versions",
                "identifier_classes_checked",
                "detectors",
                "outbound",
                "payload_hash",
                "signature_ref",
                "execution_locus",
                "transport_class",
                "endpoint_class",
                "model_id",
                "model_revision",
            }
        ),
        parse_privacy_receipt_v11_payload,
        False,
    ),
    "RegistryResolutionReceipt": (
        "1.1.0",
        frozenset(
            {
                "requested_capabilities",
                "bindings",
                "resolution_mode",
                "validation_status",
                "reason_codes",
            }
        ),
        parse_registry_resolution_payload,
        True,
    ),
    "ToolAuthorizationReceipt": (
        "1.0.0",
        frozenset(
            {
                "agent_role",
                "tool_id",
                "requested_action",
                "decision",
                "policy_version",
                "reason_codes",
                "invocation_id",
            }
        ),
        parse_tool_authorization_payload,
        True,
    ),
    "DataModeReceipt": (
        "2.0.0",
        frozenset(
            {
                "subject_artifact_ids",
                "mode_set",
                "declared_composition",
                "propagation_status",
                "reason_codes",
            }
        ),
        parse_data_mode_payload,
        False,
    ),
    "FailureReceipt": (
        "1.0.0",
        frozenset(
            {
                "failure_code",
                "stage",
                "retryable",
                "attempt",
                "budget_state",
                "details",
                "related_artifact_ids",
                "safe_terminal",
                "operator_action",
            }
        ),
        parse_failure_payload,
        True,
    ),
    "PolicyDecision": (
        "2.0.0",
        frozenset(
            {
                "policy_version",
                "input_facts",
                "outcome",
                "reason_codes",
                "missing_prerequisites",
                "review_trigger",
                "existing_task_id",
            }
        ),
        parse_policy_decision_payload,
        True,
    ),
    "ScanRun": (
        "1.1.0",
        frozenset(
            {
                "watch_case_id",
                "state",
                "scheduled_for",
                "attempt",
                "lease_epoch",
                "deadline_at",
                "budget_snapshot",
                "idempotency_key",
                "trace_id",
                "terminal_policy_decision_id",
                "failure_receipt_ids",
                "execution_profile",
            }
        ),
        parse_scan_run_v11_payload,
        True,
    ),
    "AgentExecutionReceipt": (
        "1.0.0",
        frozenset(
            {
                "execution_profile", "agent_role", "attempt",
                "execution_status", "runtime_class", "model_id",
                "model_revision", "endpoint_class", "location", "trace_id",
                "invocation_id", "started_at", "completed_at", "latency_ms",
                "turns", "http_429_count", "tool_call_ids", "tool_response_ids",
                "tool_records",
                "started_receipt_id", "failure_code",
            }
        ),
        parse_agent_execution_receipt_payload,
        True,
    ),
    "ReviewTask": (
        "1.0.0",
        frozenset(
            {
                "watch_case_id",
                "trigger_decision_id",
                "state",
                "priority_band",
                "claim_ids",
                "audit_receipt_id",
                "simulation",
                "deduplication_key",
            }
        ),
        parse_review_task_payload,
        True,
    ),
    "ScanRunEvent": (
        "1.0.0",
        frozenset(
            {
                "event_id",
                "sequence",
                "from_state",
                "to_state",
                "event_code",
                "agent_id",
                "lease_epoch",
            }
        ),
        parse_scan_run_event_payload,
        True,
    ),
    "WatchCase": (
        "2.0.0",
        frozenset(
            {
                "tenant_id",
                "region",
                "state",
                "monitoring_started_at",
                "monitoring_policy",
                "next_scan_at",
                "source_cursors",
                "last_verified_snapshot_id",
                "last_verified_scan",
                "pending_observation_hashes",
                "attention_marker",
                "open_review_task_id",
                "retention_policy",
            }
        ),
        parse_watch_case_payload,
        False,
    ),
    "EvidenceSnapshot": (
        "1.0.0",
        frozenset(
            {
                "effective_at",
                "observation_ids",
                "coverage_status",
                "source_cursors",
                "normalized_facts",
                "conflicts",
                "snapshot_hash",
            }
        ),
        parse_evidence_snapshot_payload,
        True,
    ),
    "CandidateDeltaReceipt": (
        "1.0.0",
        frozenset(
            {
                "previous_snapshot_id",
                "current_snapshot_id",
                "exact_allele_match",
                "scope_match",
                "snapshot_complete",
                "new_observation_hashes",
                "candidate_delta_state",
                "reason_codes",
            }
        ),
        parse_candidate_delta_payload,
        True,
    ),
    "AssessmentReceipt": (
        "1.0.0",
        frozenset(
            {
                "delta_id",
                "material_claims",
                "counter_evidence_set",
                "uncertainty_codes",
                "schema_validation_status",
            }
        ),
        parse_assessment_receipt_payload,
        True,
    ),
    "CitationAuditReceipt": (
        "1.0.0",
        frozenset(
            {
                "assessment_id",
                "audit_status",
                "claim_verdicts",
                "metadata_refetches",
                "counter_evidence_coverage",
                "audit_completeness",
                "rejected_claim_ids",
            }
        ),
        parse_citation_audit_payload,
        True,
    ),
}
