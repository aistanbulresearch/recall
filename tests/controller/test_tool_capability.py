from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from recall.connectors.live import canonical_pubmed_metadata_hash
from recall.contracts import (
    AgentRole,
    ArtifactStatus,
    DataMode,
    build_artifact,
)
from recall.controller.tool_capability import (
    RunToolCapability,
    ToolCapabilityCodec,
)
from recall.controller.tool_capability_issuer import ToolCapabilityIssuer
from recall.ledger import InMemoryLedger
from recall.ledger.producers import PRODUCER_REGISTRY


NOW = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)
CASE_ID = str(uuid4())
RUN_ID = str(uuid4())
SOURCE_ID = str(uuid4())
METADATA_HASH = canonical_pubmed_metadata_hash(
    "39779848",
    "A multiplexed assay of BRCA2 variant function",
    "https://pubmed.ncbi.nlm.nih.gov/39779848/",
)


def _source_artifact(*, content_hash: str | None = None) -> dict[str, object]:
    return build_artifact(
        schema_name="EvidenceObservation",
        schema_version="1.0.0",
        artifact_id=SOURCE_ID,
        case_id=CASE_ID,
        run_id=RUN_ID,
        producer={
            "component": "rcl-205-replay-connector",
            "version": "1.0.1",
            "identity": "evidence-connector",
        },
        created_at="2026-08-24T09:58:00Z",
        input_artifact_ids=(),
        data_mode=DataMode.CAPTURED_REPLAY,
        status=ArtifactStatus.VALID,
        payload={
            "source": "pubmed",
            "source_record_id": "39779848",
            "retrieved_at": "2026-08-16T23:18:30Z",
            "source_version": "rcl-205:STAGE_1:1.0.1",
            "source_locator": "https://pubmed.ncbi.nlm.nih.gov/39779848/",
            "source_content_hash": content_hash or "a" * 64,
            "structured_fields": {
                "semantic_anchor": "PMID:39779848",
                "citation_metadata": {
                    "identifier": "39779848",
                    "title": "A multiplexed assay of BRCA2 variant function",
                    "locator": "https://pubmed.ncbi.nlm.nih.gov/39779848/",
                    "content_hash": METADATA_HASH,
                },
            },
            "retrieval_status": "PASS",
        },
        authorized_producers=PRODUCER_REGISTRY,
    )


def _issuer() -> tuple[InMemoryLedger, ToolCapabilityIssuer, ToolCapabilityCodec]:
    ledger = InMemoryLedger()
    source = _source_artifact()
    ledger.append_artifact(source)
    codec = ToolCapabilityCodec(b"x" * 32, clock=lambda: NOW)
    return ledger, ToolCapabilityIssuer(ledger, codec), codec


def test_capability_round_trip_binds_source_artifact_hash_separately() -> None:
    ledger, issuer, codec = _issuer()
    source = ledger.get_artifact(SOURCE_ID)
    assert source is not None
    token = issuer.issue(
        role=AgentRole.CITATION_AUDITOR,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_artifact_ids=(SOURCE_ID,),
        allowed_artifact_schema_names=("EvidenceObservation",),
        refetch_claims={"claim-001": SOURCE_ID},
        expires_at=NOW + timedelta(minutes=5),
    )
    decoded = codec.verify(token)
    grant = decoded.refetch_grants[0]
    assert grant.source_artifact_content_hash == source["content_hash"]
    assert grant.content_hash == METADATA_HASH
    assert grant.source_artifact_content_hash != grant.content_hash


def test_capability_issuer_derives_refetch_metadata_from_ledger() -> None:
    _ledger, issuer, codec = _issuer()
    token = issuer.issue(
        role=AgentRole.CITATION_AUDITOR,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_artifact_ids=(SOURCE_ID,),
        allowed_artifact_schema_names=("EvidenceObservation",),
        refetch_claims={"claim-001": SOURCE_ID},
        expires_at=NOW + timedelta(minutes=5),
    )
    grant = codec.verify(token).refetch_grants[0]
    assert grant.identifier == "39779848"
    assert grant.title == "A multiplexed assay of BRCA2 variant function"
    assert grant.locator == "https://pubmed.ncbi.nlm.nih.gov/39779848/"
    assert grant.data_mode is DataMode.CAPTURED_REPLAY


def test_role_schema_and_data_mode_are_closed_at_issuance() -> None:
    _ledger, issuer, _codec = _issuer()
    with pytest.raises(ValueError, match="tool_capability_schema_not_role_allowed"):
        issuer.issue(
            role=AgentRole.EVIDENCE_ASSESSOR,
            case_id=CASE_ID,
            run_id=RUN_ID,
            data_mode=DataMode.CAPTURED_REPLAY,
            allowed_artifact_ids=(SOURCE_ID,),
            allowed_artifact_schema_names=("AssessmentReceipt",),
            expires_at=NOW + timedelta(minutes=5),
        )
    with pytest.raises(ValueError, match="capability_artifact_data_mode_mismatch"):
        issuer.issue(
            role=AgentRole.EVIDENCE_ASSESSOR,
            case_id=CASE_ID,
            run_id=RUN_ID,
            data_mode=DataMode.LIVE_PUBLIC,
            allowed_artifact_ids=(SOURCE_ID,),
            allowed_artifact_schema_names=("EvidenceObservation",),
            expires_at=NOW + timedelta(minutes=5),
        )


def test_tampered_or_expired_capability_is_rejected() -> None:
    _ledger, issuer, codec = _issuer()
    token = issuer.issue(
        role=AgentRole.EVIDENCE_WATCHER,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_replay_stages=("stage-1",),
        expires_at=NOW + timedelta(minutes=5),
    )
    version, payload, signature = token.split(".")
    tampered_payload = ("A" if payload[0] != "A" else "B") + payload[1:]
    with pytest.raises(ValueError, match="tool_capability_signature_invalid"):
        codec.verify(".".join((version, tampered_payload, signature)))
    expired_codec = ToolCapabilityCodec(
        b"x" * 32, clock=lambda: NOW + timedelta(minutes=6)
    )
    with pytest.raises(ValueError, match="tool_capability_expired"):
        expired_codec.verify(token)


def test_capability_schema_is_closed() -> None:
    fields = set(RunToolCapability.__dataclass_fields__)
    assert fields == {
        "capability_id",
        "role",
        "case_id",
        "run_id",
        "data_mode",
        "allowed_tool_ids",
        "allowed_artifact_ids",
        "allowed_artifact_schema_names",
        "allowed_replay_stages",
        "refetch_grants",
        "issued_at",
        "expires_at",
    }
