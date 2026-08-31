from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from recall.connectors import PubMedConnector, RefetchAdapter, ReplayConnector
from recall.connectors.live import canonical_pubmed_metadata_hash
from recall.contracts import (
    AgentRole,
    ArtifactStatus,
    DataMode,
    build_artifact,
)
from recall.controller.tool_capability import (
    RefetchGrant,
    RunToolCapability,
    ToolCapabilityCodec,
)
from recall.controller.tool_capability_issuer import ToolCapabilityIssuer
from recall.controller.tool_gateway import (
    InMemoryGatewayInvocationStore,
    ToolGateway,
)
from recall.controller.tool_gateway_runtime import load_frozen_replay_connector
from recall.ledger import InMemoryLedger
from recall.ledger.producers import PRODUCER_REGISTRY


NOW = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)
CASE_ID = str(uuid4())
RUN_ID = str(uuid4())
SOURCE_ID = str(uuid4())
AUDIENCE = "https://recall-controller.internal"
WATCHER = "recall-watcher@example.iam.gserviceaccount.com"
ASSESSOR = "recall-assessor@example.iam.gserviceaccount.com"
AUDITOR = "recall-auditor@example.iam.gserviceaccount.com"
ROOT = Path(__file__).parents[2]
MANIFEST = ROOT / "docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json"
METADATA_HASH = canonical_pubmed_metadata_hash(
    "39779848",
    "A multiplexed assay of BRCA2 variant function",
    "https://pubmed.ncbi.nlm.nih.gov/39779848/",
)


class StaticIdentityVerifier:
    def __init__(self, claims: dict[str, object]) -> None:
        self.claims = claims
        self.calls = 0

    def verify(self, token: str, audience: str) -> dict[str, object]:
        self.calls += 1
        assert token == "oidc-token"
        assert audience == AUDIENCE
        return dict(self.claims)


class CountingReplay:
    def __init__(self) -> None:
        self.calls = 0

    def tool_result(self, stage: str) -> dict[str, object]:
        self.calls += 1
        return {"protocol_id": "RCL-205", "replay_stage": stage}


class HugeReplay(CountingReplay):
    def tool_result(self, stage: str) -> dict[str, object]:
        self.calls += 1
        return {"replay_stage": stage, "payload": "x" * 70_000}


class CountingPubMed:
    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, _identifier: str) -> object:
        self.calls += 1
        raise AssertionError("unexpected refetch")


class RecordingLedger(InMemoryLedger):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[str, str]] = []

    def append_artifact(self, value: dict[str, object]):  # type: ignore[override]
        self.events.append(("append", str(value["schema_name"])))
        return super().append_artifact(value)

    def get_artifact(self, artifact_id: str) -> dict[str, object] | None:
        self.events.append(("get", artifact_id))
        return super().get_artifact(artifact_id)


class FailingReceiptLedger(InMemoryLedger):
    def append_artifact(self, value: dict[str, object]):  # type: ignore[override]
        if value["schema_name"] == "ToolAuthorizationReceipt":
            raise RuntimeError("ledger unavailable")
        return super().append_artifact(value)


def _claims(principal: str, **overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "aud": AUDIENCE,
        "iss": "https://accounts.google.com",
        "email": principal,
        "email_verified": True,
        "exp": int((NOW + timedelta(minutes=10)).timestamp()),
    }
    value.update(overrides)
    return value


def _source_artifact() -> dict[str, object]:
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
            "source_content_hash": "a" * 64,
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


def _grant(source_hash: str) -> RefetchGrant:
    return RefetchGrant(
        claim_id="claim-001",
        source_artifact_id=SOURCE_ID,
        source_artifact_content_hash=source_hash,
        identifier="39779848",
        title="A multiplexed assay of BRCA2 variant function",
        locator="https://pubmed.ncbi.nlm.nih.gov/39779848/",
        content_hash=METADATA_HASH,
        data_mode=DataMode.CAPTURED_REPLAY,
    )


def _ledger_and_codec() -> tuple[InMemoryLedger, ToolCapabilityIssuer, ToolCapabilityCodec]:
    ledger = InMemoryLedger()
    ledger.append_artifact(_source_artifact())
    codec = ToolCapabilityCodec(b"s" * 32, clock=lambda: NOW)
    return ledger, ToolCapabilityIssuer(ledger, codec), codec


def _gateway(
    ledger: InMemoryLedger,
    codec: ToolCapabilityCodec,
    verifier: StaticIdentityVerifier,
    replay: Any,
    *,
    pubmed: PubMedConnector | None = None,
) -> ToolGateway:
    return ToolGateway(
        ledger=ledger,
        replay_connector=replay,
        pubmed_connector=pubmed
        or PubMedConnector(
            tool="recall_test",
            email="research@example.org",
            transport=lambda _url, _timeout: (_ for _ in ()).throw(OSError("down")),
            sleeper=lambda _seconds: None,
        ),
        refetch_adapter=RefetchAdapter(),
        capability_codec=codec,
        identity_verifier=verifier,
        expected_audience=AUDIENCE,
        role_principals={
            AgentRole.EVIDENCE_WATCHER: WATCHER,
            AgentRole.EVIDENCE_ASSESSOR: ASSESSOR,
            AgentRole.CITATION_AUDITOR: AUDITOR,
        },
        invocation_store=InMemoryGatewayInvocationStore(),
        clock=lambda: NOW,
    )


def _body(token: str, arguments: dict[str, object], request_id: str | None = None) -> dict[str, object]:
    return {
        "protocol_version": "1.0",
        "request_id": request_id or str(uuid4()),
        "capability": token,
        "arguments": arguments,
    }


def test_identical_retry_returns_cached_response_and_one_receipt() -> None:
    ledger, issuer, codec = _ledger_and_codec()
    replay = CountingReplay()
    token = issuer.issue(
        role=AgentRole.EVIDENCE_WATCHER,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_replay_stages=("stage-1",),
        expires_at=NOW + timedelta(minutes=5),
    )
    gateway = _gateway(ledger, codec, StaticIdentityVerifier(_claims(WATCHER)), replay)
    body = _body(token, {"stage": "stage-1"})
    first = gateway.handle("evidence_connector", "oidc-token", body)
    second = gateway.handle("evidence_connector", "oidc-token", body)
    assert first.status_code == second.status_code == 200
    assert first.body == second.body
    assert replay.calls == 1
    receipts = [
        item
        for item in ledger.list_by_run(RUN_ID)
        if item["schema_name"] == "ToolAuthorizationReceipt"
    ]
    assert len(receipts) == 1


def test_receipt_persistence_failure_denies_without_backend_execution() -> None:
    ledger = FailingReceiptLedger()
    codec = ToolCapabilityCodec(b"s" * 32, clock=lambda: NOW)
    replay = CountingReplay()
    capability = RunToolCapability(
        capability_id=str(uuid4()),
        role=AgentRole.EVIDENCE_WATCHER,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_tool_ids=("evidence_connector",),
        allowed_artifact_ids=(),
        allowed_artifact_schema_names=(),
        allowed_replay_stages=("stage-1",),
        refetch_grants=(),
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )

    response = _gateway(
        ledger, codec, StaticIdentityVerifier(_claims(WATCHER)), replay
    ).handle(
        "evidence_connector",
        "oidc-token",
        _body(codec.issue(capability), {"stage": "stage-1"}),
    )

    assert response.status_code == 503
    assert response.body["decision"] == "DENIED"
    assert response.body["authorization_receipt"] is None
    assert response.body["error"] == "authorization_receipt_persistence_failed"
    assert replay.calls == 0


def test_oversized_allowed_result_preserves_receipt_and_cached_retry() -> None:
    ledger, issuer, codec = _ledger_and_codec()
    replay = HugeReplay()
    token = issuer.issue(
        role=AgentRole.EVIDENCE_WATCHER,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_replay_stages=("stage-1",),
        expires_at=NOW + timedelta(minutes=5),
    )
    gateway = _gateway(
        ledger, codec, StaticIdentityVerifier(_claims(WATCHER)), replay
    )
    body = _body(token, {"stage": "stage-1"})

    first = gateway.handle("evidence_connector", "oidc-token", body)
    second = gateway.handle("evidence_connector", "oidc-token", body)

    assert first.status_code == second.status_code == 502
    assert first.body == second.body
    assert first.body["decision"] == "ALLOWED"
    assert first.body["authorization_receipt"]["decision"] == "ALLOWED"
    assert first.body["result"] is None
    assert first.body["error"] == "gateway_response_too_large"
    assert replay.calls == 1
    receipts = [
        item
        for item in ledger.list_by_run(RUN_ID)
        if item["schema_name"] == "ToolAuthorizationReceipt"
    ]
    assert len(receipts) == 1


def test_role_forbidden_tool_persists_denied_receipt_without_backend() -> None:
    ledger, issuer, codec = _ledger_and_codec()
    replay = CountingReplay()
    token = issuer.issue(
        role=AgentRole.EVIDENCE_WATCHER,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_replay_stages=("stage-1",),
        expires_at=NOW + timedelta(minutes=5),
    )
    response = _gateway(
        ledger, codec, StaticIdentityVerifier(_claims(WATCHER)), replay
    ).handle("ledger_read", "oidc-token", _body(token, {"artifact_id": SOURCE_ID}))
    assert response.status_code == 403
    assert response.body["decision"] == "DENIED"
    assert replay.calls == 0
    receipt = [
        item
        for item in ledger.list_by_run(RUN_ID)
        if item["schema_name"] == "ToolAuthorizationReceipt"
    ][0]
    assert receipt["decision"] == "DENIED"
    assert receipt["reason_codes"] == ["tool_not_allowlisted"]


def test_no_auth_is_rejected_before_receipt_or_backend() -> None:
    ledger, issuer, codec = _ledger_and_codec()
    replay = CountingReplay()
    token = issuer.issue(
        role=AgentRole.EVIDENCE_WATCHER,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_replay_stages=("stage-1",),
        expires_at=NOW + timedelta(minutes=5),
    )
    response = _gateway(
        ledger, codec, StaticIdentityVerifier(_claims(WATCHER)), replay
    ).handle("evidence_connector", "", _body(token, {"stage": "stage-1"}))
    assert response.status_code == 401
    assert response.body["error"] == "endpoint_auth_missing"
    assert replay.calls == 0
    assert not any(
        item["schema_name"] == "ToolAuthorizationReceipt"
        for item in ledger.list_by_run(RUN_ID)
    )


def test_http_endpoint_rejects_missing_bearer_header() -> None:
    ledger, issuer, codec = _ledger_and_codec()
    token = issuer.issue(
        role=AgentRole.EVIDENCE_WATCHER,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_replay_stages=("stage-1",),
        expires_at=NOW + timedelta(minutes=5),
    )
    response = _gateway(
        ledger, codec, StaticIdentityVerifier(_claims(WATCHER)), CountingReplay()
    ).handle_http(
        "POST",
        "/v1/tools/evidence_connector:invoke",
        {},
        _body(token, {"stage": "stage-1"}),
    )
    assert response.status_code == 401
    assert response.body["error"] == "endpoint_auth_missing"


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"aud": "wrong"}, "endpoint_audience_invalid"),
        ({"iss": "https://evil.invalid"}, "endpoint_issuer_invalid"),
        ({"email": ASSESSOR}, "endpoint_principal_role_mismatch"),
        ({"exp": int((NOW - timedelta(seconds=1)).timestamp())}, "endpoint_token_expired"),
    ],
)
def test_bad_identity_claims_reject_before_dispatch(
    overrides: dict[str, object], error: str
) -> None:
    ledger, issuer, codec = _ledger_and_codec()
    replay = CountingReplay()
    token = issuer.issue(
        role=AgentRole.EVIDENCE_WATCHER,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_replay_stages=("stage-1",),
        expires_at=NOW + timedelta(minutes=5),
    )
    response = _gateway(
        ledger,
        codec,
        StaticIdentityVerifier(_claims(WATCHER, **overrides)),
        replay,
    ).handle("evidence_connector", "oidc-token", _body(token, {"stage": "stage-1"}))
    assert response.status_code == 401
    assert response.body["error"] == error
    assert replay.calls == 0


def test_ledger_read_enforces_exact_grant_case_run_and_schema() -> None:
    ledger, issuer, codec = _ledger_and_codec()
    token = issuer.issue(
        role=AgentRole.EVIDENCE_ASSESSOR,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_artifact_ids=(SOURCE_ID,),
        allowed_artifact_schema_names=("EvidenceObservation",),
        expires_at=NOW + timedelta(minutes=5),
    )
    response = _gateway(
        ledger, codec, StaticIdentityVerifier(_claims(ASSESSOR)), CountingReplay()
    ).handle("ledger_read", "oidc-token", _body(token, {"artifact_id": SOURCE_ID}))
    assert response.status_code == 200
    assert response.body["result"]["artifact"]["artifact_id"] == SOURCE_ID


def test_unknown_artifact_grant_is_denied_without_ledger_result() -> None:
    ledger, issuer, codec = _ledger_and_codec()
    token = issuer.issue(
        role=AgentRole.EVIDENCE_ASSESSOR,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_artifact_ids=(SOURCE_ID,),
        allowed_artifact_schema_names=("EvidenceObservation",),
        expires_at=NOW + timedelta(minutes=5),
    )
    response = _gateway(
        ledger, codec, StaticIdentityVerifier(_claims(ASSESSOR)), CountingReplay()
    ).handle(
        "ledger_read",
        "oidc-token",
        _body(token, {"artifact_id": str(uuid4())}),
    )
    assert response.status_code == 403
    assert "artifact_not_granted" in response.body["authorization_receipt"]["reason_codes"]
    assert response.body["result"] is None


@pytest.mark.parametrize("tool_id", ["ledger_read", "refetch_metadata"])
def test_authorization_receipt_is_appended_before_real_ledger_read(tool_id: str) -> None:
    ledger = RecordingLedger()
    ledger.append_artifact(_source_artifact())
    codec = ToolCapabilityCodec(b"s" * 32, clock=lambda: NOW)
    issuer = ToolCapabilityIssuer(ledger, codec)
    if tool_id == "ledger_read":
        role = AgentRole.EVIDENCE_ASSESSOR
        principal = ASSESSOR
        arguments = {"artifact_id": SOURCE_ID}
        refetch_claims = None
    else:
        role = AgentRole.CITATION_AUDITOR
        principal = AUDITOR
        arguments = {"claim_id": "claim-001"}
        refetch_claims = {"claim-001": SOURCE_ID}
    token = issuer.issue(
        role=role,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_artifact_ids=(SOURCE_ID,),
        allowed_artifact_schema_names=("EvidenceObservation",),
        refetch_claims=refetch_claims,
        expires_at=NOW + timedelta(minutes=5),
    )
    ledger.events.clear()
    response = _gateway(
        ledger, codec, StaticIdentityVerifier(_claims(principal)), CountingReplay()
    ).handle(tool_id, "oidc-token", _body(token, arguments))
    assert response.status_code == 200
    assert ledger.events[:2] == [
        ("append", "ToolAuthorizationReceipt"),
        ("get", SOURCE_ID),
    ]


def test_refetch_is_derived_from_signed_grant_and_unavailable_is_null() -> None:
    ledger, issuer, codec = _ledger_and_codec()
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
    response = _gateway(
        ledger, codec, StaticIdentityVerifier(_claims(AUDITOR)), CountingReplay()
    ).handle("refetch_metadata", "oidc-token", _body(token, {"claim_id": "claim-001"}))
    assert response.status_code == 200
    assert response.body["result"] == {
        "claim_id": "claim-001",
        "verdict": "UNAVAILABLE",
        "reason_codes": ["refetch_source_unavailable"],
        "refetched_source": None,
    }


@pytest.mark.parametrize("extra_field", ["title", "locator", "content_hash", "data_mode"])
def test_refetch_rejects_extra_client_metadata_before_fetch(extra_field: str) -> None:
    ledger, issuer, codec = _ledger_and_codec()
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
    response = _gateway(
        ledger, codec, StaticIdentityVerifier(_claims(AUDITOR)), CountingReplay()
    ).handle(
        "refetch_metadata",
        "oidc-token",
        _body(token, {"claim_id": "claim-001", extra_field: "forged"}),
    )
    assert response.status_code == 400
    assert response.body["error"] == "gateway_request_fields_invalid"


@pytest.mark.parametrize(
    ("case_id", "run_id", "reason"),
    [
        (str(uuid4()), RUN_ID, "artifact_case_mismatch"),
        (CASE_ID, str(uuid4()), "artifact_run_mismatch"),
    ],
)
def test_forged_capability_scope_is_denied(
    case_id: str, run_id: str, reason: str
) -> None:
    ledger, _issuer, codec = _ledger_and_codec()
    capability = RunToolCapability(
        capability_id=str(uuid4()),
        role=AgentRole.EVIDENCE_ASSESSOR,
        case_id=case_id,
        run_id=run_id,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_tool_ids=("ledger_read",),
        allowed_artifact_ids=(SOURCE_ID,),
        allowed_artifact_schema_names=("EvidenceObservation",),
        allowed_replay_stages=(),
        refetch_grants=(),
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    response = _gateway(
        ledger, codec, StaticIdentityVerifier(_claims(ASSESSOR)), CountingReplay()
    ).handle(
        "ledger_read", "oidc-token", _body(codec.issue(capability), {"artifact_id": SOURCE_ID})
    )
    assert response.status_code == 502
    assert response.body["authorization_receipt"]["decision"] == "ALLOWED"
    assert reason in response.body["error"]
    assert response.body["result"] is None


def test_forged_schema_scope_fails_after_receipt_and_before_result() -> None:
    ledger, _issuer, codec = _ledger_and_codec()
    capability = RunToolCapability(
        capability_id=str(uuid4()),
        role=AgentRole.CITATION_AUDITOR,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_tool_ids=("ledger_read", "refetch_metadata"),
        allowed_artifact_ids=(SOURCE_ID,),
        allowed_artifact_schema_names=("EvidenceDelta",),
        allowed_replay_stages=(),
        refetch_grants=(),
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    response = _gateway(
        ledger, codec, StaticIdentityVerifier(_claims(AUDITOR)), CountingReplay()
    ).handle(
        "ledger_read", "oidc-token", _body(codec.issue(capability), {"artifact_id": SOURCE_ID})
    )
    assert response.status_code == 502
    assert "artifact_schema_not_granted" in response.body["error"]


def test_refetch_rejects_reloaded_source_artifact_hash_mismatch_without_fetch() -> None:
    ledger, _issuer, codec = _ledger_and_codec()
    capability = RunToolCapability(
        capability_id=str(uuid4()),
        role=AgentRole.CITATION_AUDITOR,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_tool_ids=("ledger_read", "refetch_metadata"),
        allowed_artifact_ids=(SOURCE_ID,),
        allowed_artifact_schema_names=("EvidenceObservation",),
        allowed_replay_stages=(),
        refetch_grants=(_grant("f" * 64),),
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    token = codec.issue(capability)
    pubmed = CountingPubMed()
    response = _gateway(
        ledger,
        codec,
        StaticIdentityVerifier(_claims(AUDITOR)),
        CountingReplay(),
        pubmed=pubmed,  # type: ignore[arg-type]
    ).handle("refetch_metadata", "oidc-token", _body(token, {"claim_id": "claim-001"}))
    assert response.status_code == 502
    assert response.body["authorization_receipt"]["decision"] == "ALLOWED"
    assert "source_artifact_hash_mismatch" in response.body["error"]
    assert response.body["result"] is None
    assert pubmed.calls == 0


def test_real_replay_connector_verifies_frozen_assets_and_returns_bounded_result() -> None:
    ledger, issuer, codec = _ledger_and_codec()
    token = issuer.issue(
        role=AgentRole.EVIDENCE_WATCHER,
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        allowed_replay_stages=("stage-1",),
        expires_at=NOW + timedelta(minutes=5),
    )
    gateway = _gateway(
        ledger,
        codec,
        StaticIdentityVerifier(_claims(WATCHER)),
        ReplayConnector(ROOT, MANIFEST),
    )
    response = gateway.handle(
        "evidence_connector", "oidc-token", _body(token, {"stage": "stage-1"})
    )
    assert response.status_code == 200
    assert response.body["result"]["protocol_id"] == "RCL-205"
    assert len(response.body["result"]["observations"]) == 3


def test_frozen_manifest_hash_is_checked_before_connector_startup() -> None:
    with pytest.raises(RuntimeError, match="replay_manifest_hash_mismatch"):
        load_frozen_replay_connector(
            ROOT, MANIFEST, expected_manifest_sha256="0" * 64
        )
