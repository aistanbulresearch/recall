from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from recall.agents.full_audit_models import RoleExecutionContext
from recall.agents.full_audit_models import PreparedRunEvidence, RoleRunResult
from recall.agents.full_audit_artifacts import build_auditor_artifacts
from recall.agents.local_tools import (
    LocalToolCallContext,
    LocalToolInputs,
    build_local_tools,
)
from recall.agents.schemas import CitationAuditOutput
from recall.contracts import AgentRole, DataMode, parse_artifact
from recall.connectors.live import LiveSourceRecord
from recall.controller.tool_gateway_store import InMemoryGatewayInvocationStore
from recall.ledger import InMemoryLedger
from recall.ledger.producers import PRODUCER_REGISTRY


CASE_ID = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
RUN_ID = "b1d74cb8-25ac-4a84-ab9d-5a71a366c2da"
NOW = datetime(2026, 8, 27, 8, 0, tzinfo=UTC)
SOURCE_HASH = "a" * 64


def _tools(*, with_binding: bool):
    cited = (
        {
            "claim-001": {
                "identifier": "39779848",
                "title": "Synthetic public evidence title",
                "locator": "https://pubmed.ncbi.nlm.nih.gov/39779848/",
                "content_hash": SOURCE_HASH,
                "data_mode": "CAPTURED_REPLAY",
            }
        }
        if with_binding
        else {}
    )

    def fetch(_identifier: str) -> LiveSourceRecord:
        return LiveSourceRecord(
            identifier="39779848",
            title="Synthetic public evidence title",
            locator="https://pubmed.ncbi.nlm.nih.gov/39779848/",
            content_hash=SOURCE_HASH,
        )

    return build_local_tools(
        InMemoryLedger(),
        InMemoryGatewayInvocationStore(),
        LocalToolInputs(
            case_id=CASE_ID,
            run_id=RUN_ID,
            role=AgentRole.CITATION_AUDITOR,
            attempt=1,
            role_execution_invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
            data_mode=DataMode.CAPTURED_REPLAY,
            evidence_records=(),
            source_cursors={},
            clock=lambda: NOW,
            citation_sources=cited,
            refetch_fetcher=fetch,
        ),
    )


def test_refetch_tool_uses_deterministic_adapter_for_bound_cited_source() -> None:
    context = RoleExecutionContext(
        CASE_ID,
        RUN_ID,
        1,
        "34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
        (),
        "e190f6ac-b726-42ae-ac2b-e4b80638e91c",
    )
    value = _tools(with_binding=True)["refetch_metadata"](
        claim_id="claim-001",
        tool_context=context.tool_context("refetch-call"),
    )

    assert value["verdict"] == "VERIFIED"
    assert value["reason_codes"] == ["refetch_metadata_verified"]
    assert value["refetched_source"]["identifier"] == "39779848"


def test_refetch_tool_fails_closed_without_cited_source_binding() -> None:
    context = RoleExecutionContext(
        CASE_ID,
        RUN_ID,
        1,
        "34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
        (),
        "e190f6ac-b726-42ae-ac2b-e4b80638e91c",
    )
    value = _tools(with_binding=False)["refetch_metadata"](
        claim_id="claim-001",
        tool_context=context.tool_context("refetch-call"),
    )

    assert value == {
        "claim_id": "claim-001",
        "verdict": "UNAVAILABLE",
        "reason_codes": ["citation_source_binding_missing"],
        "refetched_source": None,
    }


def test_role_rejects_changed_adk_invocation_before_second_tool_reservation() -> None:
    records: list[dict[str, str]] = []
    tools = build_local_tools(
        InMemoryLedger(),
        InMemoryGatewayInvocationStore(),
        LocalToolInputs(
            case_id=CASE_ID,
            run_id=RUN_ID,
            role=AgentRole.EVIDENCE_WATCHER,
            attempt=1,
            role_execution_invocation_id=(
                "34a66eed-6fa4-5b22-a146-f8e8d2e6070e"
            ),
            data_mode=DataMode.SYNTHETIC,
            evidence_records=({"source": "synthetic"},),
            source_cursors={"synthetic-source": "cursor-001"},
            clock=lambda: NOW,
            citation_sources={},
            tool_record_sink=records.append,
        ),
    )
    first_adk_invocation = str(uuid4())
    result = tools["evidence_connector"](
        stage="prepared",
        tool_context=LocalToolCallContext(first_adk_invocation, "call-1"),
    )

    assert result["source_cursors"] == {"synthetic-source": "cursor-001"}

    with pytest.raises(RuntimeError, match="adk_invocation_identity_mismatch"):
        tools["evidence_connector"](
            stage="prepared",
            tool_context=LocalToolCallContext(str(uuid4()), "call-2"),
        )

    assert len(records) == 1
    assert records[0]["adk_invocation_id"] == first_adk_invocation


def _audit_result(*, tool_result: dict[str, object] | None) -> RoleRunResult:
    output = CitationAuditOutput.model_validate(
        {
            "assessment_id": "f7617fa1-2f75-47f3-b88d-ec72e88e3051",
            "audit_status": "COMPLETE",
            "claim_results": [
                {
                    "claim_id": "claim-001",
                    "cited_identifier": "39779848",
                    "reason_codes": [],
                    "refetched_source": None,
                }
            ],
            "metadata_refetches": [],
            "counter_evidence_coverage": "PASS",
            "audit_completeness": "PASS",
            "rejected_claim_ids": [],
        }
    )
    return RoleRunResult(
        output=output,
        turns=(),
        tool_call_ids=(),
        tool_response_ids=(),
        trace_id="e190f6ac-b726-42ae-ac2b-e4b80638e91c",
        invocation_id="34a66eed-6fa4-5b22-a146-f8e8d2e6070e",
        started_at=NOW,
        completed_at=NOW,
        http_429_count=0,
        tool_results=(
            {} if tool_result is None else {"refetch:claim-001": tool_result}
        ),
    )


def _audit_wire(*, tool_result: dict[str, object] | None):
    evidence = PreparedRunEvidence(
        case_id=CASE_ID,
        cloud_bound_payload={"case_token": CASE_ID},
        source_cursors={"pubmed": "39779848"},
        data_mode=DataMode.CAPTURED_REPLAY,
        replay_observations=(),
    )
    audit, _receipt = build_auditor_artifacts(
        run_id=RUN_ID,
        evidence=evidence,
        assessment={
            "artifact_id": "f7617fa1-2f75-47f3-b88d-ec72e88e3051",
            "material_claims": ["claim-001"],
        },
        result=_audit_result(tool_result=tool_result),
        completed_receipt={"artifact_id": "unused"},
    )
    return parse_artifact(audit, authorized_producers=PRODUCER_REGISTRY)


def test_audit_receipt_uses_tool_result_not_model_proposed_metadata() -> None:
    parsed = _audit_wire(
        tool_result={
            "claim_id": "claim-001",
            "verdict": "VERIFIED",
            "reason_codes": ["refetch_metadata_verified"],
            "refetched_source": {
                "identifier": "39779848",
                "title": "Synthetic public evidence title",
                "locator": "https://pubmed.ncbi.nlm.nih.gov/39779848/",
                "content_hash": SOURCE_HASH,
            },
        }
    )

    assert parsed.payload.audit_status.value == "COMPLETE"
    assert parsed.payload.claim_verdicts[0]["verdict"] == "VERIFIED"
    assert parsed.payload.rejected_claim_ids == ()


def test_audit_receipt_is_incomplete_when_refetch_result_is_missing() -> None:
    parsed = _audit_wire(tool_result=None)

    assert parsed.payload.audit_status.value == "INCOMPLETE"
    assert parsed.payload.audit_completeness.value == "FAIL"
    assert parsed.payload.claim_verdicts[0]["verdict"] == "UNAVAILABLE"
    assert parsed.payload.rejected_claim_ids == ("claim-001",)
