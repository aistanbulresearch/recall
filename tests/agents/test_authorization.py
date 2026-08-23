from __future__ import annotations

from datetime import UTC, datetime

import pytest

from recall.agents.authorization import ToolAuthorizer
from recall.contracts import AgentRole, DataMode, ToolDecision
from recall.ledger import InMemoryLedger


CASE_ID = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
RUN_ID = "b1d74cb8-25ac-4a84-ab9d-5a71a366c2da"


def test_assessor_create_review_task_is_denied_without_backend_invocation() -> None:
    ledger = InMemoryLedger()
    calls = 0

    def create_review_task() -> str:
        nonlocal calls
        calls += 1
        return "forbidden"

    authorizer = ToolAuthorizer(
        ledger,
        role=AgentRole.EVIDENCE_ASSESSOR,
        allowed_tool_ids=frozenset({"ledger_read"}),
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.SYNTHETIC,
        clock=lambda: datetime(2026, 8, 22, 6, 30, tzinfo=UTC),
    )
    result = authorizer.invoke(
        "create_review_task",
        "create_review_task",
        create_review_task,
    )
    assert result.receipt.payload.decision is ToolDecision.DENIED
    assert result.value is None
    assert calls == 0
    assert authorizer.counters.denied == 1
    assert authorizer.counters.backend_invocations == 0
    assert ledger.read_back_count("artifacts", run_id=RUN_ID) == 1


def test_allowlisted_tool_writes_receipt_then_invokes_once() -> None:
    ledger = InMemoryLedger()
    calls = 0

    def ledger_read() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    authorizer = ToolAuthorizer(
        ledger,
        role=AgentRole.EVIDENCE_ASSESSOR,
        allowed_tool_ids=frozenset({"ledger_read"}),
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.SYNTHETIC,
        clock=lambda: datetime(2026, 8, 22, 6, 30, tzinfo=UTC),
    )
    result = authorizer.invoke("ledger_read", "read_artifact", ledger_read)
    assert result.receipt.payload.decision is ToolDecision.ALLOWED
    assert result.value == "ok"
    assert calls == 1
    assert authorizer.counters.backend_invocations == 1


def test_watcher_arbitrary_url_tool_is_denied() -> None:
    ledger = InMemoryLedger()
    calls = 0

    def fetch_arbitrary_url() -> str:
        nonlocal calls
        calls += 1
        return "forbidden"

    authorizer = ToolAuthorizer(
        ledger,
        role=AgentRole.EVIDENCE_WATCHER,
        allowed_tool_ids=frozenset({"evidence_connector"}),
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        clock=lambda: datetime(2026, 8, 22, 6, 30, tzinfo=UTC),
    )
    result = authorizer.invoke(
        "fetch_arbitrary_url", "https://example.invalid", fetch_arbitrary_url
    )
    assert result.receipt.payload.decision is ToolDecision.DENIED
    assert result.receipt.payload.reason_codes == ("tool_not_allowlisted",)
    assert authorizer.counters.backend_invocations == 0
    assert calls == 0


def test_authorizer_rejects_caller_supplied_tool_expansion() -> None:
    with pytest.raises(
        ValueError, match="agent_tool_set_invalid:EVIDENCE_ASSESSOR"
    ):
        ToolAuthorizer(
            InMemoryLedger(),
            role=AgentRole.EVIDENCE_ASSESSOR,
            allowed_tool_ids=frozenset({"ledger_read", "create_review_task"}),
            case_id=CASE_ID,
            run_id=RUN_ID,
            data_mode=DataMode.SYNTHETIC,
            clock=lambda: datetime(2026, 8, 22, 6, 30, tzinfo=UTC),
        )
