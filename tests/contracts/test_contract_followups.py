from __future__ import annotations

import pytest

from recall.contracts import (
    ArtifactStatus,
    ContractError,
    DataMode,
    build_artifact,
    parse_cloud_bound_payload,
)
from recall.ledger.producers import PRODUCER_REGISTRY


COMMON = {
    "artifact_id": "f7617fa1-2f75-47f3-b88d-ec72e88e3051",
    "case_id": "728d6e23-5ee4-4bd4-9319-4304f55628f3",
    "run_id": "b1d74cb8-25ac-4a84-ab9d-5a71a366c2da",
    "created_at": "2026-08-22T06:30:00Z",
}


def _privacy_payload(
    *, decision: str = "ACCEPTED", spans: list[object] | None = None
) -> dict[str, object]:
    approved = ["span-ref-deterministic"] if spans is None else spans
    return {
        "decision": decision,
        "detector_versions": {
            "deterministic": "1.0.0",
            "gemma": "gemma4:e4b-it-qat",
            "outbound_scanner": "1.1.0",
        },
        "identifier_classes_checked": ["PERSON_NAME"],
        "detectors": {
            "deterministic": {
                "version": "1.0.0",
                "approved_spans": approved,
            },
            "gemma": {
                "version": "gemma4:e4b-it-qat",
                "invoked": True,
                "schema_valid": True,
                "approved_residual_spans": ["span-ref-gemma"],
            },
        },
        "outbound": {
            "scan_status": "CLEAR",
            "allowed_field_paths": ["$.variant.gene"],
            "raw_text_field_count": 0,
        },
        "payload_hash": "a" * 64,
        "signature_ref": {
            "key_id": "local-key",
            "algorithm": "HMAC-SHA256",
            "signature": "b" * 64,
        },
    }


def _build_privacy(payload: dict[str, object]) -> dict[str, object]:
    return build_artifact(
        schema_name="PrivacyReceipt",
        schema_version="1.0.0",
        artifact_id=COMMON["artifact_id"],
        case_id=COMMON["case_id"],
        run_id=None,
        producer={
            "component": "privacy-gate",
            "version": "0.1.0",
            "identity": "privacy-gate",
        },
        created_at=COMMON["created_at"],
        input_artifact_ids=(),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID,
        payload=payload,
        authorized_producers=PRODUCER_REGISTRY,
    )


@pytest.mark.parametrize("decision", ["ACCEPTED", "QUARANTINED"])
def test_privacy_receipt_accepts_closed_decisions_and_extensible_versions(
    decision: str,
) -> None:
    wire = _build_privacy(_privacy_payload(decision=decision))

    assert wire["decision"] == decision
    assert wire["run_id"] is None
    assert wire["detector_versions"]["outbound_scanner"] == "1.1.0"
    assert wire["detectors"]["deterministic"]["approved_spans"]
    assert wire["detectors"]["gemma"]["approved_residual_spans"]


def test_privacy_receipt_accepts_empty_span_lists() -> None:
    payload = _privacy_payload(spans=[])
    payload["detectors"]["gemma"]["approved_residual_spans"] = []

    wire = _build_privacy(payload)

    assert wire["detectors"]["deterministic"]["approved_spans"] == []
    assert wire["detectors"]["gemma"]["approved_residual_spans"] == []


def test_privacy_receipt_rejects_non_string_span_item() -> None:
    with pytest.raises(ContractError, match="contract_type_invalid"):
        _build_privacy(_privacy_payload(spans=[{"span_hash": "a" * 64}]))


def test_privacy_receipt_rejects_legacy_pass_decision() -> None:
    with pytest.raises(ContractError, match="contract_enum_invalid:decision"):
        _build_privacy(_privacy_payload(decision="PASS"))


@pytest.mark.parametrize(
    ("verdict", "refetched_source", "accepted"),
    [
        ("UNAVAILABLE", None, True),
        ("VERIFIED", None, False),
        (
            "UNAVAILABLE",
            {
                "identifier": "PMID:39779848",
                "title": "Synthetic metadata fixture",
                "locator": "https://pubmed.ncbi.nlm.nih.gov/39779848/",
                "content_hash": "d" * 64,
            },
            False,
        ),
    ],
)
def test_unavailable_citation_has_no_fabricated_refetched_source(
    verdict: str, refetched_source: dict[str, str] | None, accepted: bool
) -> None:
    kwargs = {
        "schema_name": "CitationAuditReceipt",
        "schema_version": "1.0.0",
        "artifact_id": COMMON["artifact_id"],
        "case_id": COMMON["case_id"],
        "run_id": COMMON["run_id"],
        "producer": {
            "component": "citation-auditor",
            "version": "0.1.0",
            "identity": "citation-auditor",
        },
        "created_at": COMMON["created_at"],
        "input_artifact_ids": (),
        "data_mode": DataMode.CAPTURED_REPLAY,
        "status": ArtifactStatus.INCOMPLETE,
        "payload": {
            "assessment_id": COMMON["artifact_id"],
            "audit_status": "INCOMPLETE",
            "claim_verdicts": [
                {
                    "claim_id": "claim-001",
                    "verdict": verdict,
                    "reason_codes": ["refetch_unavailable"],
                    "refetched_source": refetched_source,
                }
            ],
            "metadata_refetches": [],
            "counter_evidence_coverage": "NOT_EVALUATED",
            "audit_completeness": "FAIL",
            "rejected_claim_ids": ["claim-001"],
        },
        "authorized_producers": PRODUCER_REGISTRY,
    }
    if accepted:
        wire = build_artifact(**kwargs)
        assert wire["claim_verdicts"][0]["refetched_source"] is None
    else:
        with pytest.raises(ContractError, match="contract_value_invalid"):
            build_artifact(**kwargs)


def _cloud_payload() -> dict[str, object]:
    return {
        "payload_kind": "recall.privacy.cloud_bound_payload",
        "payload_version": "1.0.0",
        "case_token": COMMON["case_id"],
        "tenant_id": "synthetic-lab",
        "region": "us-central1",
        "data_mode": "SYNTHETIC",
        "variant": {
            "gene": "BRCA2",
            "hgvs_c": "c.7522G>C",
            "hgvs_p": "p.Gly2508Arg",
            "assembly": "GRCh38",
        },
    }


def test_structured_only_cloud_bound_payload_parses_strictly() -> None:
    parsed = parse_cloud_bound_payload(_cloud_payload())

    assert parsed.to_wire() == _cloud_payload()


def test_cloud_bound_payload_v11_omits_unavailable_protein_consequence() -> None:
    payload = _cloud_payload()
    payload["payload_version"] = "1.1.0"
    payload["variant"].pop("hgvs_p")

    parsed = parse_cloud_bound_payload(payload)

    assert parsed.to_wire() == payload


def test_cloud_bound_payload_v10_still_requires_protein_consequence() -> None:
    payload = _cloud_payload()
    payload["variant"].pop("hgvs_p")

    with pytest.raises(ContractError, match="contract_required_field_missing"):
        parse_cloud_bound_payload(payload)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ({"raw_note": "forbidden"}, "contract_unknown_field"),
        ({"payload_version": "2.0.0"}, "contract_major_unsupported"),
        ({"case_token": "laboratory-case-key"}, "contract_uuid_invalid"),
    ],
)
def test_cloud_bound_payload_rejects_unregistered_or_invalid_values(
    mutation: dict[str, object], expected: str
) -> None:
    payload = _cloud_payload()
    payload.update(mutation)

    with pytest.raises(ContractError, match=expected):
        parse_cloud_bound_payload(payload)
