from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from recall.contracts import DataMode
from recall.contracts.enums import PresenceState, ScanRunEventCode
from recall.controller import Controller
from recall.demo.fixtures import FixtureSpec, append_fixture_artifacts
from recall.demo.admission import (
    synthetic_cloud_payload,
    synthetic_privacy_receipt,
)
from recall.ledger.port import LedgerPort


_BUDGET = {
    "delegation_depth": 1,
    "specialist_invocations": 3,
    "model_calls_per_role": 1,
    "schema_repairs": 1,
    "agent_retries": 1,
    "connector_retries": 3,
    "repeated_state_limit": 1,
    "wall_time_seconds": 599,
    "step_deadlines": {},
    "token_ceilings": {},
}


def _unavailable_policy(_facts: Mapping[str, object], _version: str) -> object:
    raise RuntimeError("policy_gate_unavailable")


def run_fixture(
    ledger: LedgerPort,
    spec: FixtureSpec,
    *,
    execution_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    started = now or datetime.now(UTC)
    case_id = str(uuid5(NAMESPACE_URL, f"recall:{execution_id}:case"))
    trace_id = str(uuid5(NAMESPACE_URL, f"recall:{execution_id}:trace"))
    controller = Controller(
        ledger,
        **({} if spec.policy_available else {"policy_evaluator": _unavailable_policy}),
    )
    privacy_receipt = synthetic_privacy_receipt(
        case_id, now=started, data_mode=DataMode.CAPTURED_REPLAY
    )
    ledger.append_artifact(privacy_receipt)
    admitted = controller.create_watch_case(
        watch_case_id=case_id,
        tenant_id="synthetic-contest-lab",
        region="us-central1",
        privacy_receipt_id=str(privacy_receipt["artifact_id"]),
        cloud_bound_payload=synthetic_cloud_payload(
            case_id, data_mode=DataMode.CAPTURED_REPLAY
        ),
        data_mode=DataMode.CAPTURED_REPLAY,
        source_cursors=spec.source_cursors,
        pending_observation_hashes=("c" * 64,),
        next_scan_at=spec.schedule_epoch,
        now=started,
    )
    created = controller.create_run(
        watch_case_id=case_id,
        source_cursors=spec.source_cursors,
        schedule_epoch=spec.schedule_epoch,
        data_mode=DataMode.CAPTURED_REPLAY,
        privacy_receipt_id=str(privacy_receipt["artifact_id"]),
        expected_watch_case_version=admitted.record.version,
        triggered_at=datetime.fromisoformat(
            spec.schedule_epoch.replace("Z", "+00:00")
        ),
        budget_snapshot=_BUDGET,
        trace_id=trace_id,
        deadline_at=(started + timedelta(minutes=10))
        .isoformat()
        .replace("+00:00", "Z"),
        now=started,
    )
    duplicate_create = controller.create_run(
        watch_case_id=case_id,
        source_cursors=spec.source_cursors,
        schedule_epoch=spec.schedule_epoch,
        data_mode=DataMode.CAPTURED_REPLAY,
        privacy_receipt_id=str(privacy_receipt["artifact_id"]),
        expected_watch_case_version=admitted.record.version,
        triggered_at=datetime.fromisoformat(
            spec.schedule_epoch.replace("Z", "+00:00")
        ),
        budget_snapshot=_BUDGET,
        trace_id=trace_id,
        deadline_at=(started + timedelta(minutes=10))
        .isoformat()
        .replace("+00:00", "Z"),
        now=started + timedelta(milliseconds=1),
    )
    queued = controller.transition(
        created.record.run_id,
        expected_version=created.record.version,
        lease_epoch=created.record.lease_epoch,
        event_code=ScanRunEventCode.OUTBOX_PUBLISHED,
        now=started + timedelta(seconds=1),
    )
    routing = controller.acquire_lease(
        queued.run_id,
        expected_version=queued.version,
        new_epoch=1,
        expires_at=started + timedelta(minutes=5),
        now=started + timedelta(seconds=2),
    )
    watching = controller.transition(
        routing.run_id,
        expected_version=routing.version,
        lease_epoch=routing.lease_epoch,
        event_code=ScanRunEventCode.ROUTE_VALIDATED,
        now=started + timedelta(seconds=3),
    )
    identifiers = append_fixture_artifacts(
        ledger,
        spec=spec,
        run_id=watching.run_id,
        case_id=case_id,
        now=started + timedelta(seconds=4),
    )
    candidate_event = {
        PresenceState.ABSENT: ScanRunEventCode.CANDIDATE_ABSENT,
        PresenceState.PRESENT: ScanRunEventCode.CANDIDATE_PRESENT,
        PresenceState.UNKNOWN: ScanRunEventCode.CANDIDATE_UNKNOWN,
    }[spec.candidate_delta_state]
    current = controller.transition(
        watching.run_id,
        expected_version=watching.version,
        lease_epoch=watching.lease_epoch,
        event_code=candidate_event,
        now=started + timedelta(seconds=5),
    )
    if spec.candidate_delta_state is PresenceState.PRESENT:
        current = controller.transition(
            current.run_id,
            expected_version=current.version,
            lease_epoch=current.lease_epoch,
            event_code=ScanRunEventCode.ASSESSMENT_COMPLETED,
            now=started + timedelta(seconds=6),
        )
        current = controller.transition(
            current.run_id,
            expected_version=current.version,
            lease_epoch=current.lease_epoch,
            event_code=ScanRunEventCode.AUDIT_COMPLETED,
            now=started + timedelta(seconds=7),
        )

    terminal = controller.evaluate_and_commit(
        current.run_id,
        verified_delta_hash="c" * 64,
        audit_receipt_id=identifiers.get("CitationAuditReceipt"),
        claim_ids=("claim-001",) if "CitationAuditReceipt" in identifiers else (),
        verified_snapshot_id=identifiers["EvidenceSnapshot"],
        verified_source_cursors=spec.source_cursors,
        pending_observation_hashes=("c" * 64,),
        now=started + timedelta(seconds=8),
    )
    repeated = controller.evaluate_and_commit(
        current.run_id,
        verified_delta_hash="c" * 64,
        audit_receipt_id=identifiers.get("CitationAuditReceipt"),
        claim_ids=("claim-001",) if "CitationAuditReceipt" in identifiers else (),
        verified_snapshot_id=identifiers["EvidenceSnapshot"],
        verified_source_cursors=spec.source_cursors,
        pending_observation_hashes=("c" * 64,),
        now=started + timedelta(seconds=9),
    )
    tasks = ledger.list_review_tasks(current.run_id)
    if tasks:
        controller.deliver_task_outbox(tasks[0].task_id)
        tasks = ledger.list_review_tasks(current.run_id)
    artifacts = ledger.list_by_run(current.run_id)
    watch_case = ledger.get_watch_case(case_id)
    if watch_case is None:
        raise RuntimeError("fixture_watch_case_missing_after_terminal")
    events = ledger.list_scan_run_events(current.run_id)
    if not events:
        raise RuntimeError("fixture_scan_run_events_missing")
    last_event = events[-1]
    policy_artifacts = [
        item for item in artifacts if item["schema_name"] == "PolicyDecision"
    ]
    failures = [item for item in artifacts if item["schema_name"] == "FailureReceipt"]
    if policy_artifacts:
        reasons = list(policy_artifacts[0]["reason_codes"])
        missing = list(policy_artifacts[0]["missing_prerequisites"])
    else:
        reasons = [str(item["failure_code"]) for item in failures]
        missing = []
    return {
        "fixture_id": spec.fixture_id,
        "data_labels": [mode.value for mode in spec.mode_set],
        "run_id": terminal.record.run_id,
        "terminal_state": terminal.record.state.value,
        "ordered_reason_codes": sorted(reasons),
        "missing_prerequisites": sorted(missing),
        "policy_call_count": controller.policy_call_count,
        "policy_decision_count": len(policy_artifacts),
        "duplicate_create_reused": not duplicate_create.created,
        "duplicate_terminal_reused": repeated.reused,
        "review_task_ids": [task.task_id for task in tasks],
        "review_task_delivery_states": [task.delivery_state for task in tasks],
        "watch_case_read_back": {
            "state": watch_case.state.value,
            "source_cursors": dict(watch_case.source_cursors),
            "last_verified_snapshot_id": watch_case.last_verified_snapshot_id,
            "pending_observation_hashes": list(
                watch_case.pending_observation_hashes
            ),
            "open_review_task_id": watch_case.open_review_task_id,
        },
        "pointer_last_event": {
            "pointer_state": terminal.record.state.value,
            "pointer_version": terminal.record.version,
            "event_to_state": last_event.to_state.value,
            "event_sequence": last_event.sequence,
            "consistent": (
                terminal.record.state is last_event.to_state
                and terminal.record.version == last_event.sequence
            ),
        },
        "firestore_read_back": {
            name: ledger.read_back_count(name)
            if name == "watch_cases"
            else ledger.read_back_count(name, run_id=current.run_id)
            for name in (
                "artifacts",
                "watch_cases",
                "scan_runs",
                "scan_run_events",
                "review_tasks",
            )
        },
    }
