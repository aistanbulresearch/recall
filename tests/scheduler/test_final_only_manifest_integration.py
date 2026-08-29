from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import pytest

import recall.scheduler.compressed_final_only_manifest as final_manifest_module
from recall.agents.full_audit import FullAuditRunOutcome
from recall.contracts import parse_artifact
from recall.contracts.enums import ScanRunState, WatchCaseState
from recall.ledger.models import ScanRunRecord, WatchCaseRecord
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.scheduler.compressed_cohort import cases_for_cycle, portfolio_cases
from recall.scheduler.compressed_identity import evidence_legacy_failure_receipt_id
from recall.scheduler.compressed_manifest import build_compressed_manifest
from recall.scheduler.compressed_plan import (
    FINAL_ONLY_OWNER_RELEASE_REASON,
    FINAL_ONLY_OWNER_RELEASE_TOKEN,
    authorize_final_only_owner_release,
    parse_compressed_plan,
    verify_manifest_against_plan,
)
from recall.scheduler.compressed_supersession import VerifiedFinalOnlySupersession
from recall.scheduler.full_audit_phase import FullAuditPhaseResult
from tests.scheduler.test_compressed_plan import _wire_for_final_only
from tests.scheduler.test_final_only_scheduler_gate import _history_row


def _id(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"final-only-integration:{label}"))


def test_real_final_only_producer_parser_plan_verifier_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = parse_compressed_plan(_wire_for_final_only(), sha256="e" * 64)
    cycle = plan.by_id("c6")
    assert plan.supersession is not None
    bindings = plan.supersession.historical_evidence
    legacy = [
        _history_row(1, cycle_id=None, status="COMPLETE"),
        _history_row(2, cycle_id=None, status="INCOMPLETE"),
    ]
    legacy[1]["failure_receipt_id"] = evidence_legacy_failure_receipt_id(plan)
    c1 = _history_row(3, cycle_id="c1", status="COMPLETE")
    c2 = _history_row(4, cycle_id="c2", status="COMPLETE")
    c3 = _history_row(5, cycle_id="c3", status="INCOMPLETE")
    histories = {
        bindings[0].manifest_artifact_id: (*legacy, c1),
        bindings[1].manifest_artifact_id: (*legacy, c1, c2),
        bindings[2].manifest_artifact_id: (*legacy, c1, c2, c3),
        bindings[3].manifest_artifact_id: (*legacy, c1, c2, c3),
    }
    monkeypatch.setattr(
        final_manifest_module,
        "parse_artifact",
        lambda wire, **_kwargs: SimpleNamespace(
            payload=SimpleNamespace(
                execution_history=histories[str(wire["artifact_id"])]
            )
        ),
    )
    verified = VerifiedFinalOnlySupersession(
        plan_sha256=plan.sha256,
        verified_artifact_ids=tuple(
            artifact_id
            for binding in bindings
            for artifact_id in (
                binding.manifest_artifact_id,
                binding.mode_receipt_artifact_id,
            )
            if artifact_id is not None
        ),
        manifest_wires=tuple(
            {"artifact_id": binding.manifest_artifact_id}
            for binding in bindings
        ),
    )

    selected = cases_for_cycle(cycle)
    selected_ids = {item.case_id for item in selected}
    excluded = tuple(
        item.case_id
        for item in portfolio_cases(plan.cycles)
        if item.case_id not in selected_ids
    )
    now = cycle.window_end + timedelta(seconds=1)
    owner_release = authorize_final_only_owner_release(
        plan,
        token=FINAL_ONLY_OWNER_RELEASE_TOKEN,
        reason=FINAL_ONLY_OWNER_RELEASE_REASON,
        actual_start=now,
        max_retries=0,
    )
    run_ids = {item.case_id: _id(f"run:{item.case_id}") for item in selected}
    policy_ids = {
        item.case_id: _id(f"policy:{item.case_id}") for item in selected
    }
    watch_records = tuple(
        WatchCaseRecord(
            watch_case_id=item.case_id,
            artifact_id=_id(f"watch:{item.case_id}"),
            state=WatchCaseState.ACTIVE,
            version=1,
            source_cursors=(("replay", item.cursor),),
            last_verified_snapshot_id=None,
            pending_observation_hashes=(),
            open_review_task_id=None,
            attention_reason_codes=(),
            next_scan_at=item.next_scan_at,
            updated_at=now,
        )
        for item in selected
    )
    run_records = tuple(
        ScanRunRecord(
            run_id=run_ids[item.case_id],
            state=ScanRunState.NO_ACTION,
            version=1,
            lease_epoch=1,
            lease_expires_at=None,
            updated_at=now,
            scan_run_artifact_id=_id(f"scan:{item.case_id}"),
            terminal_policy_decision_id=policy_ids[item.case_id],
            failure_receipt_ids=(),
            last_repeated_state_hash=None,
            repeated_state_count=0,
        )
        for item in selected
    )
    outcomes = tuple(
        FullAuditRunOutcome(
            case_id=item.case_id,
            run_id=run_ids[item.case_id],
            terminal_state="NO_ACTION",
            audit_status="COMPLETE",
            citation_audit_receipt_id=_id(f"citation:{item.case_id}"),
            policy_decision_id=policy_ids[item.case_id],
            policy_outcome="NO_ACTION",
            policy_reason_codes=("no_verified_delta",),
            technical_failure_codes=(),
            failure_receipt_ids=(),
            agent_execution_receipt_ids=tuple(
                sorted(
                    _id(f"agent:{item.case_id}:{index}")
                    for index in range(6)
                )
            ),
            elapsed_ms=1,
            turns=(),
            http_429_count=0,
        )
        for item in selected
    )
    completed_at = now + timedelta(seconds=500)
    phase = FullAuditPhaseResult(
        outcomes=outcomes,
        summary={
            "execution_profile": "FULL_AUDIT_V1",
            "runtime_class": "IN_PROCESS_ADK_CLOUD_RUN",
            "concurrency": 2,
            "model_id": "gemini-3.7-flash",
            "endpoint_class": "VERTEX_AI_GLOBAL",
            "total_runs": 456,
            "complete_runs": 456,
            "incomplete_runs": 0,
            "not_evaluated_runs": 0,
            "halted_runs": 0,
            "total_agent_invocations": 1_368,
            "total_prompt_tokens": 0,
            "total_candidate_tokens": 0,
            "total_thoughts_tokens": 0,
            "total_tokens": 0,
            "p50_latency_ms": 1,
            "p95_latency_ms": 1,
            "http_429_count": 0,
            "projected_cost_usd_micros": 0,
            "reserved_cost_usd_micros": 0,
            "pricing_policy_sha256": "f" * 64,
            "actual_billed_cost_state": "NOT_VERIFIED",
        },
        elapsed_ms=500_000,
        started_at=now.isoformat().replace("+00:00", "Z"),
        completed_at=completed_at.isoformat().replace("+00:00", "Z"),
    )
    observations = {
        item.vcv: {
            "artifact_id": _id(f"observation:{item.vcv}"),
            "source_content_hash": "a" * 64,
            "structured_fields": {
                "capture_path": f"capture/{item.vcv}.json",
                "semantic_anchor": item.vcv,
            },
        }
        for item in selected
        if item.vcv is not None
    }
    batch_id = _id("batch")
    wire = build_compressed_manifest(
        plan=plan,
        cycle=cycle,
        source_commit="a" * 40,
        image_digest=f"sha256:{'b' * 64}",
        selected_cases=selected,
        excluded_case_ids=excluded,
        watch_records=watch_records,
        run_records=run_records,
        newly_created_run_ids=tuple(run_ids.values()),
        reused_run_ids=(),
        bundle=SimpleNamespace(
            observations_by_vcv=observations,
            history_receipt={"artifact_id": _id("history")},
            legacy_failure_receipt={"artifact_id": _id("legacy")},
        ),
        previous_manifest=None,
        ramp_gate_receipt=None,
        headroom_receipt=None,
        batch_execution_receipt={"artifact_id": batch_id},
        write_measurement_status="MEASURED",
        write_metrics={
            "scope": "CASE_WRITE_AND_EXACT_READBACK",
            "measurement_semantics": (
                "LEDGER_METHOD_INVOCATIONS_AND_COMMITTED_CASE_DOCUMENTS"
            ),
            "persistence_surface": "LIVE_FIRESTORE",
            "batch_max_workers": 2,
            "selected_case_count": 456,
            "ledger_operation_counts": {
                "watch_case_reads": 456,
                "watch_artifact_reads": 456,
                "idempotency_run_reads": 456,
                "create_run_transaction_calls": 456,
                "post_create_or_reuse_artifact_reads": 456,
                "exact_run_pointer_reads": 456,
                "exact_run_artifact_reads": 456,
                "exact_run_event_queries": 456,
                "aggregate_count_reads": 2,
            },
            "committed_case_documents": 1_368,
            "started_at": now.isoformat().replace("+00:00", "Z"),
            "completed_at": (now + timedelta(seconds=456)).isoformat().replace(
                "+00:00", "Z"
            ),
            "worker_elapsed_ms": 455_000,
            "readback_elapsed_ms": 1_000,
            "total_elapsed_ms": 456_000,
            "effective_write_millis_per_case": 1_000,
        },
        agent_phase=phase,
        executed_at=completed_at,
        trigger_started_at=now,
        verified_supersession=verified,
        owner_release=owner_release,
    )

    parsed = parse_artifact(
        wire, authorized_producers=PRODUCER_REGISTRY, verify_hash=True
    )
    verify_manifest_against_plan(
        parsed,
        plan,
        expected_legacy_failure_receipt_id=evidence_legacy_failure_receipt_id(
            plan
        ),
    )
    assert parsed.status.value == "VALID"
    assert len(parsed.payload.run_outcomes) == 456
    assert parsed.payload.window_start == cycle.schedule_epoch
    assert parsed.payload.window_end == cycle.window_end.isoformat().replace(
        "+00:00", "Z"
    )
    assert parsed.payload.deadline_policy["trigger_started_at"] == now.isoformat().replace(
        "+00:00", "Z"
    )
    assert parsed.payload.deadline_policy["trigger_window_end"] == now.isoformat().replace(
        "+00:00", "Z"
    )
    assert parsed.payload.deadline_policy["authoritative_end_to_end_deadline"] == (
        now + timedelta(seconds=28_800)
    ).isoformat().replace("+00:00", "Z")
    assert [(item.code, item.message_key) for item in parsed.warnings] == [
        (FINAL_ONLY_OWNER_RELEASE_TOKEN, FINAL_ONLY_OWNER_RELEASE_REASON),
        ("CLOUD_RUN_MAX_RETRIES_0", "OWNER_RELEASE_EXTERNAL_ACTIVATION_FACT"),
    ]
