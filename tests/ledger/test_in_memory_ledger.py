from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest

from recall.contracts import (
    AgentRole,
    ArtifactStatus,
    ContractError,
    DataMode,
    ExecutionProfile,
    build_artifact,
    content_hash,
)
from recall.contracts.tool_causality import tool_request_id
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.controller import Controller, ScanRunEventCode
from recall.ledger import InMemoryLedger, ScanRunRecord

from .helpers import ARTIFACT_ID, RUN_ID, conflicting_receipt, tool_receipt
from tests.admission import admit_watch_case, in_memory_ledger


CASE_ID = "728d6e23-5ee4-4bd4-9319-4304f55628f3"


def _leased_ledger(
    now: datetime, *, lease_seconds: int = 300, full_audit: bool = False
) -> tuple[InMemoryLedger, Controller, ScanRunRecord]:
    ledger = in_memory_ledger()
    controller = Controller(ledger)
    admitted, receipt, _payload = admit_watch_case(
        ledger,
        controller,
        case_id=CASE_ID,
        now=now,
        next_scan_at="2026-08-22T00:00:00Z",
        source_cursors={"clinvar": "42"},
    )
    created = controller.create_run(
        watch_case_id=CASE_ID,
        source_cursors={"clinvar": "42"},
        schedule_epoch="2026-08-22T00:00:00Z",
        data_mode=DataMode.SYNTHETIC,
        privacy_receipt_id=str(receipt["artifact_id"]),
        expected_watch_case_version=admitted.record.version,
        triggered_at=datetime(2026, 8, 22, tzinfo=UTC),
        budget_snapshot={
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
        },
        trace_id="0a651403-8226-4072-9240-344542b0c5fb",
        deadline_at="2026-08-22T00:09:59Z",
        now=now,
        execution_profile=(
            ExecutionProfile.FULL_AUDIT_V1 if full_audit else None
        ),
    ).record
    queued = controller.transition(
        created.run_id,
        expected_version=1,
        lease_epoch=0,
        event_code=ScanRunEventCode.OUTBOX_PUBLISHED,
        now=now,
    )
    routing = controller.acquire_lease(
        queued.run_id,
        expected_version=2,
        new_epoch=1,
        expires_at=now + timedelta(seconds=lease_seconds),
        now=now,
    )
    return ledger, controller, routing


def test_append_is_idempotent_but_rejects_same_id_with_different_hash() -> None:
    ledger = in_memory_ledger()
    wire = tool_receipt()

    first = ledger.append_artifact(wire)
    second = ledger.append_artifact(wire)

    assert first.to_wire() == second.to_wire()
    assert ledger.get_artifact(ARTIFACT_ID) == wire
    assert [item["artifact_id"] for item in ledger.list_by_run(RUN_ID)] == [
        ARTIFACT_ID
    ]

    with pytest.raises(ContractError, match="artifact_integrity_failed"):
        ledger.append_artifact(conflicting_receipt())
    assert ledger.get_artifact(ARTIFACT_ID) == wire


def test_transition_cas_writes_one_event_and_stale_version_changes_nothing() -> None:
    now = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
    ledger, controller, routing = _leased_ledger(now)
    running = controller.transition(
        routing.run_id,
        expected_version=3,
        lease_epoch=1,
        event_code=ScanRunEventCode.ROUTE_VALIDATED,
        now=now + timedelta(seconds=1),
    )

    assert running.version == 4
    assert running.state == "WATCHING"
    assert ledger.read_back_count("scan_run_events", run_id=running.run_id) == 4

    with pytest.raises(ContractError, match="stale_write_rejected"):
        controller.transition(
            running.run_id,
            expected_version=3,
            lease_epoch=1,
            event_code=ScanRunEventCode.CANDIDATE_UNKNOWN,
            now=now + timedelta(seconds=2),
        )
    assert ledger.get_scan_run(running.run_id) == running
    assert ledger.read_back_count("scan_run_events", run_id=running.run_id) == 4


def test_ledger_rejects_mismatched_transition_without_any_write() -> None:
    now = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
    ledger, _controller, routing = _leased_ledger(now)
    pointer_before = ledger.get_scan_run(routing.run_id)
    events_before = ledger.read_back_count(
        "scan_run_events", run_id=routing.run_id
    )
    artifacts_before = ledger.read_back_count("artifacts", run_id=routing.run_id)

    with pytest.raises(ContractError, match="contract_transition_invalid"):
        ledger.transition_with_cas(
            routing.run_id,
            expected_version=routing.version,
            lease_epoch=routing.lease_epoch,
            to_state="ASSESSING",
            event_code=ScanRunEventCode.ROUTE_VALIDATED,
            now=now + timedelta(seconds=1),
        )

    assert ledger.get_scan_run(routing.run_id) == pointer_before
    assert (
        ledger.read_back_count("scan_run_events", run_id=routing.run_id)
        == events_before
    )
    assert ledger.read_back_count("artifacts", run_id=routing.run_id) == artifacts_before


def test_generic_ledger_transition_cannot_apply_full_audit_agent_step() -> None:
    now = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
    ledger, controller, routing = _leased_ledger(now)
    watching = controller.transition(
        routing.run_id,
        expected_version=routing.version,
        lease_epoch=routing.lease_epoch,
        event_code=ScanRunEventCode.ROUTE_VALIDATED,
        now=now + timedelta(seconds=1),
    )
    pointer_before = ledger.get_scan_run(watching.run_id)
    events_before = ledger.read_back_count("scan_run_events", run_id=watching.run_id)
    artifacts_before = ledger.read_back_count("artifacts", run_id=watching.run_id)

    with pytest.raises(ContractError, match="full_audit_specialized_commit_required"):
        ledger.transition_with_cas(
            watching.run_id,
            expected_version=watching.version,
            lease_epoch=watching.lease_epoch,
            to_state="ASSESSING",
            event_code=ScanRunEventCode.FULL_AUDIT_REQUIRED,
            now=now + timedelta(seconds=2),
        )

    assert ledger.get_scan_run(watching.run_id) == pointer_before
    assert ledger.read_back_count("scan_run_events", run_id=watching.run_id) == events_before
    assert ledger.read_back_count("artifacts", run_id=watching.run_id) == artifacts_before


def test_specialized_full_audit_commit_is_atomic_and_profile_bound() -> None:
    now = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
    ledger, controller, routing = _leased_ledger(now, full_audit=True)
    watching = controller.transition(
        routing.run_id,
        expected_version=routing.version,
        lease_epoch=routing.lease_epoch,
        event_code=ScanRunEventCode.ROUTE_VALIDATED,
        now=now + timedelta(seconds=1),
    )
    step_artifacts = _watcher_step_artifacts(
        watching.run_id, now + timedelta(seconds=2)
    )
    ledger.append_artifact(step_artifacts[0])
    ledger.append_artifact(step_artifacts[1])
    artifacts = step_artifacts[2:]
    invalid = [dict(item) for item in artifacts]
    invalid[-1] = {**invalid[-1], "content_hash": "0" * 64}
    pointer_before = ledger.get_scan_run(watching.run_id)
    events_before = ledger.read_back_count("scan_run_events", run_id=watching.run_id)
    artifacts_before = ledger.read_back_count("artifacts", run_id=watching.run_id)

    with pytest.raises(ContractError, match="artifact_integrity_failed"):
        ledger.commit_agent_step(
            watching.run_id,
            expected_version=watching.version,
            lease_epoch=watching.lease_epoch,
            event_code=ScanRunEventCode.FULL_AUDIT_REQUIRED,
            artifacts=invalid,
            now=now + timedelta(seconds=2),
        )

    assert ledger.get_scan_run(watching.run_id) == pointer_before
    assert ledger.read_back_count("scan_run_events", run_id=watching.run_id) == events_before
    assert ledger.read_back_count("artifacts", run_id=watching.run_id) == artifacts_before

    assessing = ledger.commit_agent_step(
        watching.run_id,
        expected_version=watching.version,
        lease_epoch=watching.lease_epoch,
        event_code=ScanRunEventCode.FULL_AUDIT_REQUIRED,
        artifacts=artifacts,
        now=now + timedelta(seconds=2),
    )
    assert assessing.state == "ASSESSING"
    assert ledger.read_back_count("scan_run_events", run_id=watching.run_id) == events_before + 1
    assert ledger.read_back_count("artifacts", run_id=watching.run_id) == artifacts_before + 4


def test_specialized_agent_commit_rejects_wrong_started_receipt_binding_atomically() -> None:
    now = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
    ledger, controller, routing = _leased_ledger(now, full_audit=True)
    watching = controller.transition(
        routing.run_id,
        expected_version=routing.version,
        lease_epoch=routing.lease_epoch,
        event_code=ScanRunEventCode.ROUTE_VALIDATED,
        now=now + timedelta(seconds=1),
    )
    values = _watcher_step_artifacts(
        watching.run_id, now + timedelta(seconds=2)
    )
    wrong_started = deepcopy(values[0])
    wrong_started["agent_role"] = "EVIDENCE_ASSESSOR"
    wrong_started["content_hash"] = content_hash(wrong_started)
    ledger.append_artifact(wrong_started)
    pointer_before = ledger.get_scan_run(watching.run_id)
    events_before = ledger.read_back_count(
        "scan_run_events", run_id=watching.run_id
    )

    with pytest.raises(ContractError, match="started_receipt_binding"):
        ledger.commit_agent_step(
            watching.run_id,
            expected_version=watching.version,
            lease_epoch=watching.lease_epoch,
            event_code=ScanRunEventCode.FULL_AUDIT_REQUIRED,
            artifacts=values[2:],
            now=now + timedelta(seconds=2),
        )

    assert ledger.get_scan_run(watching.run_id) == pointer_before
    assert ledger.read_back_count(
        "scan_run_events", run_id=watching.run_id
    ) == events_before
    assert ledger.read_back_count("artifacts", run_id=watching.run_id) == 2


def test_specialized_agent_commit_rejects_fabricated_tool_authorization_atomically() -> None:
    now = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
    ledger, controller, routing = _leased_ledger(now, full_audit=True)
    watching = controller.transition(
        routing.run_id,
        expected_version=routing.version,
        lease_epoch=routing.lease_epoch,
        event_code=ScanRunEventCode.ROUTE_VALIDATED,
        now=now + timedelta(seconds=1),
    )
    values = _watcher_step_artifacts(
        watching.run_id, now + timedelta(seconds=2)
    )
    ledger.append_artifact(values[0])
    denied = deepcopy(values[1])
    denied["decision"] = "DENIED"
    denied["reason_codes"] = ["tool_not_allowlisted"]
    denied["content_hash"] = content_hash(denied)
    ledger.append_artifact(denied)
    pointer_before = ledger.get_scan_run(watching.run_id)
    events_before = ledger.read_back_count(
        "scan_run_events", run_id=watching.run_id
    )

    with pytest.raises(ContractError, match="tool_authorization_binding"):
        ledger.commit_agent_step(
            watching.run_id,
            expected_version=watching.version,
            lease_epoch=watching.lease_epoch,
            event_code=ScanRunEventCode.FULL_AUDIT_REQUIRED,
            artifacts=values[2:],
            now=now + timedelta(seconds=2),
        )

    assert ledger.get_scan_run(watching.run_id) == pointer_before
    assert ledger.read_back_count(
        "scan_run_events", run_id=watching.run_id
    ) == events_before


def test_specialized_agent_commit_rejects_authorization_from_another_call_atomically() -> None:
    now = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
    ledger, controller, routing = _leased_ledger(now, full_audit=True)
    watching = controller.transition(
        routing.run_id,
        expected_version=routing.version,
        lease_epoch=routing.lease_epoch,
        event_code=ScanRunEventCode.ROUTE_VALIDATED,
        now=now + timedelta(seconds=1),
    )
    values = _watcher_step_artifacts(
        watching.run_id, now + timedelta(seconds=2)
    )
    ledger.append_artifact(values[0])
    other_call = deepcopy(values[1])
    other_call["invocation_id"] = str(
        __import__("uuid").uuid5(
            __import__("uuid").UUID(watching.run_id), "other-tool-call"
        )
    )
    other_call["content_hash"] = content_hash(other_call)
    ledger.append_artifact(other_call)
    pointer_before = ledger.get_scan_run(watching.run_id)
    events_before = ledger.read_back_count(
        "scan_run_events", run_id=watching.run_id
    )
    artifacts_before = ledger.read_back_count(
        "artifacts", run_id=watching.run_id
    )

    with pytest.raises(ContractError, match="tool_authorization_binding"):
        ledger.commit_agent_step(
            watching.run_id,
            expected_version=watching.version,
            lease_epoch=watching.lease_epoch,
            event_code=ScanRunEventCode.FULL_AUDIT_REQUIRED,
            artifacts=values[2:],
            now=now + timedelta(seconds=2),
        )

    assert ledger.get_scan_run(watching.run_id) == pointer_before
    assert ledger.read_back_count(
        "scan_run_events", run_id=watching.run_id
    ) == events_before
    assert ledger.read_back_count(
        "artifacts", run_id=watching.run_id
    ) == artifacts_before


def _watcher_step_artifacts(run_id: str, now: datetime) -> list[dict[str, object]]:
    created_at = now.isoformat().replace("+00:00", "Z")
    ids = {
        name: str(__import__("uuid").uuid5(__import__("uuid").UUID(run_id), name))
        for name in (
            "EvidenceObservation",
            "EvidenceSnapshot",
            "CandidateDeltaReceipt",
            "AgentExecutionReceipt-started",
            "AgentExecutionReceipt-completed",
            "ToolAuthorizationReceipt",
        )
    }
    role_execution_invocation_id = "c9a19973-602f-46b2-953e-62c4cb33f595"
    request_id = tool_request_id(
        run_id=run_id,
        role=AgentRole.EVIDENCE_WATCHER,
        attempt=1,
        role_execution_invocation_id=role_execution_invocation_id,
        adk_invocation_id=role_execution_invocation_id,
        function_call_id="call-1",
        tool_id="evidence_connector",
    )

    def artifact(
        schema: str,
        identity: str,
        artifact_id: str,
        payload: dict[str, object],
        inputs: tuple[str, ...] = (),
    ) -> dict[str, object]:
        return build_artifact(
            schema_name=schema,
            schema_version="1.0.0",
            artifact_id=artifact_id,
            case_id=CASE_ID,
            run_id=run_id,
            producer={"component": identity, "version": "0.1.0", "identity": identity},
            created_at=created_at,
            input_artifact_ids=inputs,
            data_mode=DataMode.SYNTHETIC,
            status=ArtifactStatus.VALID,
            payload=payload,
            authorized_producers=PRODUCER_REGISTRY,
        )

    observation = artifact(
        "EvidenceObservation",
        "evidence-connector",
        ids["EvidenceObservation"],
        {
            "source": "synthetic-preparation-bundle",
            "source_record_id": "synthetic-record-1",
            "retrieved_at": created_at,
            "source_version": "1.0.0",
            "source_locator": "bundle://synthetic-record-1",
            "source_content_hash": "a" * 64,
            "structured_fields": {"record_count": 1},
            "retrieval_status": "PASS",
        },
    )
    snapshot = artifact(
        "EvidenceSnapshot",
        "evidence-watcher",
        ids["EvidenceSnapshot"],
        {
            "effective_at": created_at,
            "observation_ids": [ids["EvidenceObservation"]],
            "coverage_status": "PASS",
            "source_cursors": {"synthetic": "cursor-1"},
            "normalized_facts": {"record_count": 1},
            "conflicts": [],
            "snapshot_hash": "b" * 64,
        },
        (ids["EvidenceObservation"],),
    )
    candidate = artifact(
        "CandidateDeltaReceipt",
        "evidence-normalizer",
        ids["CandidateDeltaReceipt"],
        {
            "previous_snapshot_id": None,
            "current_snapshot_id": ids["EvidenceSnapshot"],
            "exact_allele_match": False,
            "scope_match": False,
            "snapshot_complete": True,
            "new_observation_hashes": [],
            "candidate_delta_state": "ABSENT",
            "reason_codes": ["exact_allele_absent"],
        },
        (ids["EvidenceSnapshot"],),
    )
    started = artifact(
        "AgentExecutionReceipt",
        "controller-agent-executor",
        ids["AgentExecutionReceipt-started"],
        {
            "execution_profile": "FULL_AUDIT_V1",
            "agent_role": "EVIDENCE_WATCHER",
            "attempt": 1,
            "execution_status": "STARTED",
            "runtime_class": "IN_PROCESS_ADK_CLOUD_RUN",
            "model_id": "gemini-3.7-flash",
            "model_revision": "gemini-3.7-flash",
            "endpoint_class": "VERTEX_AI_GLOBAL",
            "location": "global",
            "trace_id": "e190f6ac-b726-42ae-ac2b-e4b80638e91c",
            "invocation_id": role_execution_invocation_id,
            "started_at": created_at,
            "completed_at": None,
            "latency_ms": None,
            "turns": [],
            "http_429_count": 0,
            "tool_call_ids": [],
            "tool_response_ids": [],
            "tool_records": [],
            "started_receipt_id": None,
            "failure_code": None,
        },
    )
    authorization = artifact(
        "ToolAuthorizationReceipt",
        "controller-authorizer",
        ids["ToolAuthorizationReceipt"],
        {
            "agent_role": "EVIDENCE_WATCHER",
            "tool_id": "evidence_connector",
            "requested_action": "{}",
            "decision": "ALLOWED",
            "policy_version": "1.0.0",
            "reason_codes": [],
            "invocation_id": request_id,
        },
    )
    completed = artifact(
        "AgentExecutionReceipt",
        "controller-agent-executor",
        ids["AgentExecutionReceipt-completed"],
        {
            "execution_profile": "FULL_AUDIT_V1",
            "agent_role": "EVIDENCE_WATCHER",
            "attempt": 1,
            "execution_status": "COMPLETED",
            "runtime_class": "IN_PROCESS_ADK_CLOUD_RUN",
            "model_id": "gemini-3.7-flash",
            "model_revision": "gemini-3.7-flash",
            "endpoint_class": "VERTEX_AI_GLOBAL",
            "location": "global",
            "trace_id": "e190f6ac-b726-42ae-ac2b-e4b80638e91c",
            "invocation_id": role_execution_invocation_id,
            "started_at": created_at,
            "completed_at": created_at,
            "latency_ms": 0,
            "turns": [{
                "turn_index": 1,
                "prompt_tokens": 1,
                "candidate_tokens": 1,
                "thoughts_tokens": 0,
                "total_tokens": 2,
                "finish_reason": "STOP",
                "function_call_emitted": True,
                "latency_ms": 0,
            }],
            "http_429_count": 0,
            "tool_call_ids": ["call-1"],
            "tool_response_ids": ["call-1"],
            "tool_records": [
                {
                    "tool_id": "evidence_connector",
                    "call_id": "call-1",
                    "response_id": "call-1",
                    "adk_invocation_id": role_execution_invocation_id,
                    "request_id": request_id,
                    "authorization_receipt_id": ids["ToolAuthorizationReceipt"],
                }
            ],
            "started_receipt_id": ids["AgentExecutionReceipt-started"],
            "failure_code": None,
        },
        (
            ids["AgentExecutionReceipt-started"],
            ids["ToolAuthorizationReceipt"],
        ),
    )
    return [started, authorization, observation, snapshot, candidate, completed]

def test_expired_lease_rejects_transition_without_state_or_event_change() -> None:
    now = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
    ledger, controller, routing = _leased_ledger(now, lease_seconds=1)

    with pytest.raises(ContractError, match="lease_expired"):
        controller.transition(
            routing.run_id,
            expected_version=3,
            lease_epoch=1,
            event_code=ScanRunEventCode.ROUTE_VALIDATED,
            now=now + timedelta(seconds=2),
        )

    assert ledger.get_scan_run(routing.run_id) == routing
    assert ledger.read_back_count("scan_run_events", run_id=routing.run_id) == 3


def test_concurrent_compare_and_set_allows_exactly_one_writer() -> None:
    now = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
    ledger, controller, routing = _leased_ledger(now)
    barrier = Barrier(2)

    def compete(event_code: ScanRunEventCode) -> str:
        barrier.wait()
        try:
            controller.transition(
                routing.run_id,
                expected_version=3,
                lease_epoch=1,
                event_code=event_code,
                now=now + timedelta(seconds=1),
            )
            return "committed"
        except ContractError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                compete,
                [
                    ScanRunEventCode.ROUTE_VALIDATED,
                    ScanRunEventCode.PREREQUISITE_FAILED,
                ],
            )
        )

    assert sorted(results) == ["committed", "stale_write_rejected"]
    assert ledger.read_back_count("scan_run_events", run_id=routing.run_id) == 4
