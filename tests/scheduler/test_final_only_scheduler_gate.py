from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import pytest

import recall.scheduler.compressed as compressed_module
from recall.scheduler.compressed import CompressedCycleScheduler
from recall.scheduler.compressed_manifest import build_compressed_manifest
from recall.scheduler.compressed_identity import evidence_legacy_failure_receipt_id
from recall.scheduler.compressed_plan import (
    parse_compressed_plan,
    verify_manifest_against_plan,
)
from recall.scheduler.compressed_supersession import VerifiedFinalOnlySupersession
from recall.scheduler.full_audit_phase import FullAuditPhaseResult
import recall.scheduler.compressed_final_only_manifest as final_manifest_module
from recall.scheduler.compressed_final_only_manifest import (
    verify_final_only_history_rows,
)
import recall.scheduler.compressed_manifest as manifest_module
from tests.scheduler.test_compressed_plan import _wire_for_final_only


class _TargetLedger:
    def __init__(self) -> None:
        self.write_calls: list[str] = []

    def append_artifact(self, *_args, **_kwargs) -> None:
        self.write_calls.append("append_artifact")

    def create_scan_run(self, *_args, **_kwargs) -> None:
        self.write_calls.append("create_scan_run")


def _history_row(
    sequence: int,
    *,
    cycle_id: str | None,
    status: str,
) -> dict[str, object]:
    return {
        "sequence_index": sequence,
        "source_schema_version": "CohortDayManifest/3.3.0",
        "cycle_id": cycle_id,
        "cycle_index": None if cycle_id is None else int(cycle_id[1:]),
        "cohort_due_date": "2026-08-25",
        "scheduled_for": "2026-08-25T15:00:00Z",
        "window_start": None,
        "window_end": None,
        "trigger_code": "COHORT_COMPRESSED_MACHINE_TRIGGERED",
        "executed_at": "2026-08-25T15:00:03Z",
        "runs_created": 3,
        "runs_predicted": 3,
        "execution_status": status,
        "failure_receipt_id": None,
        "evidence_state": "LIVE_INFRASTRUCTURE_SYNTHETIC_DATA",
        "schedule_mode": (
            None if cycle_id is None else "COMPRESSED_MACHINE_TRIGGERED"
        ),
    }


def test_final_only_history_is_verified_before_preparation_or_target_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = parse_compressed_plan(_wire_for_final_only(), sha256="e" * 64)
    cycle = plan.by_id("c6")
    calls: list[str] = []

    def reject_history(*_args, **_kwargs):
        calls.append("history")
        raise RuntimeError("final_only_history_hash_mismatch")

    monkeypatch.setattr(
        compressed_module, "verify_final_only_supersession", reject_history
    )
    monkeypatch.setattr(
        compressed_module,
        "verify_prepared_cycle",
        lambda *_args, **_kwargs: calls.append("prepared"),
    )
    target = _TargetLedger()
    scheduler = CompressedCycleScheduler(
        target,
        plan=plan,
        cycle=cycle,
        bundle=SimpleNamespace(),
        source_commit="a" * 40,
        image_digest=f"sha256:{'b' * 64}",
    )

    with pytest.raises(RuntimeError, match="final_only_history_hash_mismatch"):
        scheduler.trigger(
            now=cycle.window_start,
            previous_manifest=None,
            historical_ledger_factory=lambda _prefix: SimpleNamespace(),
        )

    assert calls == ["history"]
    assert target.write_calls == []


def test_final_only_rejects_legacy_gate_or_predecessor_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = parse_compressed_plan(_wire_for_final_only(), sha256="e" * 64)
    cycle = plan.by_id("c6")
    monkeypatch.setattr(
        compressed_module,
        "verify_final_only_supersession",
        lambda *_args, **_kwargs: SimpleNamespace(
            plan_sha256=plan.sha256,
            verified_artifact_ids=(),
            manifest_wires=(),
        ),
    )
    scheduler = CompressedCycleScheduler(
        _TargetLedger(),
        plan=plan,
        cycle=cycle,
        bundle=SimpleNamespace(),
        source_commit="a" * 40,
        image_digest=f"sha256:{'b' * 64}",
    )

    with pytest.raises(RuntimeError, match="final_only_legacy_gate_input_forbidden"):
        scheduler.trigger(
            now=cycle.window_start,
            previous_manifest={"artifact_id": "legacy"},
            ramp_gate_receipt={"artifact_id": "fiction"},
            headroom_receipt={"artifact_id": "fiction"},
            historical_ledger_factory=lambda _prefix: SimpleNamespace(),
        )


def test_final_only_manifest_builder_binds_history_and_retires_ramp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = parse_compressed_plan(_wire_for_final_only(), sha256="e" * 64)
    cycle = plan.by_id("c6")
    assert plan.supersession is not None
    bindings = plan.supersession.historical_evidence
    verified = VerifiedFinalOnlySupersession(
        plan_sha256=plan.sha256,
        verified_artifact_ids=tuple(
            artifact_id
            for item in bindings
            for artifact_id in (
                item.manifest_artifact_id,
                item.mode_receipt_artifact_id,
            )
            if artifact_id is not None
        ),
        manifest_wires=tuple(
            {"artifact_id": item.manifest_artifact_id} for item in bindings
        ),
    )
    legacy = [
        _history_row(1, cycle_id=None, status="COMPLETE"),
        _history_row(2, cycle_id=None, status="INCOMPLETE"),
    ]
    c1 = _history_row(3, cycle_id="c1", status="COMPLETE")
    c2 = _history_row(4, cycle_id="c2", status="COMPLETE")
    c3 = _history_row(5, cycle_id="c3", status="COMPLETE")
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
    monkeypatch.setattr(
        manifest_module,
        "build_artifact",
        lambda **kwargs: kwargs,
    )
    now = cycle.window_start
    batch_id = str(uuid5(NAMESPACE_URL, "final-only-batch"))
    built = build_compressed_manifest(
        plan=plan,
        cycle=cycle,
        source_commit="a" * 40,
        image_digest=f"sha256:{'b' * 64}",
        selected_cases=(),
        excluded_case_ids=(),
        watch_records=(),
        run_records=(),
        newly_created_run_ids=(),
        reused_run_ids=(),
        bundle=SimpleNamespace(
            observations_by_vcv={},
            history_receipt={"artifact_id": str(uuid5(NAMESPACE_URL, "history"))},
            legacy_failure_receipt={
                "artifact_id": str(uuid5(NAMESPACE_URL, "legacy"))
            },
        ),
        previous_manifest=None,
        ramp_gate_receipt=None,
        headroom_receipt=None,
        batch_execution_receipt={"artifact_id": batch_id},
        write_measurement_status="MEASURED",
        write_metrics={
            "completed_at": (now + timedelta(seconds=1)).isoformat().replace(
                "+00:00", "Z"
            ),
            "persistence_surface": "LIVE_FIRESTORE",
            "effective_write_millis_per_case": 1000,
        },
        agent_phase=FullAuditPhaseResult(
            outcomes=(),
            summary={
                "total_runs": 0,
                "complete_runs": 0,
                "incomplete_runs": 0,
                "not_evaluated_runs": 0,
                "halted_runs": 0,
            },
            elapsed_ms=1,
            started_at=now.isoformat().replace("+00:00", "Z"),
            completed_at=(now + timedelta(seconds=2)).isoformat().replace(
                "+00:00", "Z"
            ),
        ),
        executed_at=now + timedelta(seconds=2),
        trigger_started_at=now,
        verified_supersession=verified,
    )

    payload = built["payload"]
    assert built["schema_version"] == "3.4.0"
    assert payload["previous_manifest_id"] is None
    assert payload["ramp_gate_receipt_id"] is None
    assert payload["headroom_receipt_id"] is None
    assert [row["execution_status"] for row in payload["execution_history"][-3:]] == [
        "RETIRED_TIMEBOX",
        "RETIRED_TIMEBOX",
        "INCOMPLETE",
    ]
    assert payload["final_only_supersession"]["verified_artifact_ids"] == list(
        verified.verified_artifact_ids
    )
    assert set(verified.verified_artifact_ids).issubset(
        set(built["input_artifact_ids"])
    )

    verify_final_only_history_rows(
        plan,
        verified,
        built["payload"]["execution_history"],
    )
    built["payload"]["execution_history"][2]["runs_created"] += 1
    with pytest.raises(
        RuntimeError, match="final_only_history_row_binding_invalid"
    ):
        verify_final_only_history_rows(
            plan,
            verified,
            built["payload"]["execution_history"],
        )


def _plan_bound_manifest(plan):
    assert plan.supersession is not None
    cycle = plan.by_id("c6")
    start = cycle.window_start
    write_completed = start + timedelta(seconds=1)
    agent_completed = start + timedelta(seconds=2)
    historical = [
        {
            "cycle_id": item.cycle_id,
            "evidence_role": item.evidence_role,
            "execution_status": item.execution_status,
            "plan_sha256": item.plan_sha256,
            "collection_prefix": item.collection_prefix,
            "manifest_artifact_id": item.manifest_artifact_id,
            "manifest_content_hash": item.manifest_content_hash,
            "mode_receipt_artifact_id": item.mode_receipt_artifact_id,
            "mode_receipt_content_hash": item.mode_receipt_content_hash,
        }
        for item in plan.supersession.historical_evidence
    ]
    verified_ids = tuple(
        artifact_id
        for item in plan.supersession.historical_evidence
        for artifact_id in (
            item.manifest_artifact_id,
            item.mode_receipt_artifact_id,
        )
        if artifact_id is not None
    )
    rows = [
        _history_row(1, cycle_id=None, status="COMPLETE"),
        _history_row(2, cycle_id=None, status="INCOMPLETE"),
    ]
    rows[1]["failure_receipt_id"] = evidence_legacy_failure_receipt_id(plan)
    for sequence, cycle_id, status in (
        (3, "c1", "COMPLETE"),
        (4, "c2", "COMPLETE"),
        (5, "c3", "HISTORICAL_ATTEMPTS_PRESERVED"),
        (6, "c4", "RETIRED_TIMEBOX"),
        (7, "c5", "RETIRED_TIMEBOX"),
        (8, "c6", "COMPLETE"),
    ):
        row = _history_row(sequence, cycle_id=cycle_id, status=status)
        if status == "RETIRED_TIMEBOX":
            row.update({"runs_created": 0, "runs_predicted": 0, "executed_at": None})
        rows.append(row)
    for index, cycle_id in ((5, "c4"), (6, "c5"), (7, "c6")):
        bound_cycle = plan.by_id(cycle_id)
        rows[index].update(
            {
                "cycle_index": bound_cycle.cycle_index,
                "cohort_due_date": bound_cycle.cohort_due_date.isoformat(),
                "scheduled_for": bound_cycle.schedule_epoch,
                "window_start": bound_cycle.schedule_epoch,
                "window_end": bound_cycle.window_end.isoformat().replace(
                    "+00:00", "Z"
                ),
                "trigger_code": "COHORT_COMPRESSED_MACHINE_TRIGGERED",
                "schedule_mode": plan.schedule_mode,
            }
        )
    for index in (5, 6):
        rows[index].update(
            {
                "source_schema_version": "OwnerSupersession/1.0.0",
                "evidence_state": "OWNER_DECISION",
                "failure_receipt_id": None,
            }
        )
    rows[7].update(
        {
            "source_schema_version": "CohortDayManifest/3.4.0",
            "runs_created": 456,
            "runs_predicted": 456,
            "executed_at": agent_completed.isoformat().replace("+00:00", "Z"),
            "evidence_state": "LIVE_INFRASTRUCTURE_SYNTHETIC_DATA",
            "failure_receipt_id": None,
        }
    )
    payload = SimpleNamespace(
        cycle_id="c6",
        cycle_index=6,
        cohort_due_date=cycle.cohort_due_date.isoformat(),
        delta={
            "runs_predicted": 456,
            "authoritative_run_ids": tuple(f"run-{index}" for index in range(456)),
        },
        window_start=cycle.schedule_epoch,
        window_end=cycle.window_end.isoformat().replace("+00:00", "Z"),
        scheduled_for=cycle.schedule_epoch,
        plan_version=plan.version,
        plan_sha256=plan.sha256,
        schedule_mode=plan.schedule_mode,
        execution_history=tuple(rows),
        deadline_policy={
            "trigger_started_at": cycle.schedule_epoch,
            "trigger_window_end": cycle.window_end.isoformat().replace(
                "+00:00", "Z"
            ),
            "write_timeout_seconds": cycle.write_timeout_seconds,
            "write_deadline": (start + timedelta(seconds=1800)).isoformat().replace(
                "+00:00", "Z"
            ),
            "write_completed_at": write_completed.isoformat().replace(
                "+00:00", "Z"
            ),
            "agent_timeout_seconds": cycle.agent_timeout_seconds,
            "agent_deadline": (
                write_completed + timedelta(seconds=cycle.agent_timeout_seconds)
            ).isoformat().replace("+00:00", "Z"),
            "agent_completed_at": agent_completed.isoformat().replace(
                "+00:00", "Z"
            ),
            "execution_timeout_seconds": cycle.execution_timeout_seconds,
            "authoritative_end_to_end_deadline": cycle.end_to_end_deadline.isoformat().replace(
                "+00:00", "Z"
            ),
        },
        final_only_supersession={
            "mode": plan.supersession.mode,
            "superseded_plan_sha256": plan.supersession.superseded_plan_sha256,
            "owner_decision": plan.supersession.owner_decision,
            "reason_code": plan.supersession.reason_code,
            "historical_evidence": historical,
            "retired_cycles": [
                {
                    "cycle_id": item.cycle_id,
                    "state": item.state,
                    "execution_status": item.execution_status,
                    "runs_created": item.runs_created,
                }
                for item in plan.supersession.retired_cycles
            ],
            "verified_artifact_ids": verified_ids,
        },
        previous_manifest_id=None,
        ramp_gate_receipt_id=None,
        headroom_receipt_id=None,
    )
    return SimpleNamespace(
        schema_name="CohortDayManifest",
        schema_version="3.4.0",
        payload=payload,
        created_at=agent_completed.isoformat().replace("+00:00", "Z"),
        status=SimpleNamespace(value="VALID"),
        input_artifact_ids=verified_ids,
    )


def test_plan_verifier_accepts_exact_final_only_binding() -> None:
    plan = parse_compressed_plan(_wire_for_final_only(), sha256="e" * 64)

    verify_manifest_against_plan(
        _plan_bound_manifest(plan),
        plan,
        expected_legacy_failure_receipt_id=evidence_legacy_failure_receipt_id(plan),
    )


def test_plan_verifier_rejects_unbound_historical_hash() -> None:
    plan = parse_compressed_plan(_wire_for_final_only(), sha256="e" * 64)
    manifest = _plan_bound_manifest(plan)
    manifest.payload.final_only_supersession["historical_evidence"][2][
        "manifest_content_hash"
    ] = "0" * 64

    with pytest.raises(
        RuntimeError, match="compressed_final_only_manifest_plan_mismatch"
    ):
        verify_manifest_against_plan(
            manifest,
            plan,
            expected_legacy_failure_receipt_id=evidence_legacy_failure_receipt_id(
                plan
            ),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("window_start", "2099-01-01T00:00:00Z"),
        ("cohort_due_date", "2099-01-01"),
        ("runs_predicted", 1),
        ("evidence_state", "UNVERIFIED"),
        ("failure_receipt_id", str(uuid5(NAMESPACE_URL, "fake-failure"))),
        ("source_schema_version", "OwnerSupersession/9.9.9"),
    ],
)
def test_plan_verifier_rejects_mutated_retired_history_claim(
    field: str,
    value: object,
) -> None:
    plan = parse_compressed_plan(_wire_for_final_only(), sha256="e" * 64)
    manifest = _plan_bound_manifest(plan)
    manifest.payload.execution_history[5][field] = value

    with pytest.raises(
        RuntimeError, match="compressed_final_only_manifest_plan_mismatch"
    ):
        verify_manifest_against_plan(
            manifest,
            plan,
            expected_legacy_failure_receipt_id=evidence_legacy_failure_receipt_id(
                plan
            ),
        )
