from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4

import pytest

from recall.contracts import (
    ArtifactStatus,
    DataMode,
    build_artifact,
    canonical_json_bytes,
    content_hash as artifact_content_hash,
)
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.privacy.signing import (
    LocalSigner,
    content_hash as signing_content_hash,
    signer_fingerprint_sha256,
)
from recall.scheduler.privacy_receipt_source import LockedJsonPrivacyReceiptSource


SIGNER = LocalSigner(key_id="external-lab", key=b"external-lab-test-key")


def _receipt(case_id: str, cloud: dict[str, object]) -> dict[str, object]:
    wire = build_artifact(
        schema_name="PrivacyReceipt",
        schema_version="1.1.0",
        artifact_id=str(uuid4()),
        case_id=case_id,
        run_id=None,
        producer={
            "component": "local-privacy-gate",
            "version": "1.1.0",
            "identity": "privacy-gate",
        },
        created_at="2026-08-27T01:00:00Z",
        input_artifact_ids=(),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID,
        payload={
            "decision": "ACCEPTED",
            "detector_versions": {"deterministic": "1", "gemma": "1"},
            "identifier_classes_checked": [],
            "detectors": {
                "deterministic": {"version": "1", "approved_spans": []},
                "gemma": {
                    "version": "1",
                    "invoked": True,
                    "schema_valid": True,
                    "approved_residual_spans": [],
                },
            },
            "outbound": {
                "scan_status": "CLEAR",
                "allowed_field_paths": [],
                "raw_text_field_count": 0,
            },
            "payload_hash": sha256(canonical_json_bytes(cloud)).hexdigest(),
            "signature_ref": {
                "key_id": "external-lab",
                "algorithm": "HMAC-SHA256",
                "signature": "0" * 64,
            },
            "execution_locus": "LAB_LOCAL",
            "transport_class": "LOCAL_PROCESS",
            "endpoint_class": "OLLAMA_LOCAL",
            "model_id": "gemma4:e4b-it-qat",
            "model_revision": "sha256:" + "b" * 64,
        },
        authorized_producers=PRODUCER_REGISTRY,
    )
    body = {
        key: value
        for key, value in wire.items()
        if key not in {"content_hash", "signature_ref"}
    }
    wire["signature_ref"] = SIGNER.signature_ref(signing_content_hash(body))
    wire["content_hash"] = artifact_content_hash(wire)
    return wire


def _source(path) -> LockedJsonPrivacyReceiptSource:
    return LockedJsonPrivacyReceiptSource(
        path,
        expected_sha256=sha256(path.read_bytes()).hexdigest(),
        signer=SIGNER,
        expected_key_fingerprint_sha256=signer_fingerprint_sha256(SIGNER),
    )


def test_external_receipt_source_is_exact_and_never_synthesizes_missing_rows(
    tmp_path,
) -> None:
    case_id = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
    cloud = {"case_token": case_id, "variant": {"gene": "BRCA2"}}
    path = tmp_path / "receipts.json"
    path.write_text(
        json.dumps(
            {"schema_version": "1.0.0", "receipts": [_receipt(case_id, cloud)]}
        ),
        encoding="utf-8",
    )
    source = _source(path)

    source.assert_exact_case_set({case_id})
    assert source.source_lock == {
        "source_sha256": sha256(path.read_bytes()).hexdigest(),
        "key_id": SIGNER.key_id,
        "algorithm": "HMAC-SHA256",
        "key_fingerprint_sha256": signer_fingerprint_sha256(SIGNER),
    }
    assert source.receipt_for(case_id, cloud)["execution_locus"] == "LAB_LOCAL"
    with pytest.raises(RuntimeError, match="privacy_receipt_source_missing"):
        source.receipt_for(str(uuid4()), cloud)


@pytest.mark.parametrize(
    "endpoint_class", ["OLLAMA_CLOUD_RUN", "OLLAMA_VERTEX_ENDPOINT"]
)
def test_external_receipt_source_accepts_declared_private_gemma_service(
    tmp_path, endpoint_class: str
) -> None:
    case_id = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
    cloud = {"case_token": case_id}
    receipt = deepcopy(_receipt(case_id, cloud))
    receipt.update(
        {
            "transport_class": "PRIVATE_SERVICE",
            "endpoint_class": endpoint_class,
        }
    )
    body = {
        key: item
        for key, item in receipt.items()
        if key not in {"content_hash", "signature_ref"}
    }
    receipt["signature_ref"] = SIGNER.signature_ref(signing_content_hash(body))
    receipt["content_hash"] = artifact_content_hash(receipt)
    path = tmp_path / "receipts.json"
    path.write_text(
        json.dumps({"schema_version": "1.0.0", "receipts": [receipt]}),
        encoding="utf-8",
    )

    assert _source(path).receipt_for(case_id, cloud)["endpoint_class"] == (
        endpoint_class
    )


def test_external_receipt_source_rejects_payload_or_case_set_drift(tmp_path) -> None:
    case_id = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
    cloud = {"case_token": case_id}
    path = tmp_path / "receipts.json"
    path.write_text(
        json.dumps(
            {"schema_version": "1.0.0", "receipts": [_receipt(case_id, cloud)]}
        ),
        encoding="utf-8",
    )
    source = _source(path)

    with pytest.raises(RuntimeError, match="privacy_receipt_source_payload_mismatch"):
        source.receipt_for(case_id, {"case_token": "different"})
    with pytest.raises(RuntimeError, match="privacy_receipt_source_case_set_mismatch"):
        source.assert_exact_case_set({case_id, str(uuid4())})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("execution_locus", "CLOUD_ISOLATED"),
        ("model_id", "gemma-alias"),
    ],
)
def test_external_receipt_source_rejects_nonlocal_or_unlocked_model_rows(
    tmp_path, field: str, value: str
) -> None:
    case_id = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
    cloud = {"case_token": case_id}
    receipt = deepcopy(_receipt(case_id, cloud))
    receipt[field] = value
    body = {
        key: item
        for key, item in receipt.items()
        if key not in {"content_hash", "signature_ref"}
    }
    receipt["signature_ref"] = SIGNER.signature_ref(
        signing_content_hash(body)
    )
    receipt["content_hash"] = artifact_content_hash(receipt)
    path = tmp_path / "receipts.json"
    path.write_text(
        json.dumps({"schema_version": "1.0.0", "receipts": [receipt]}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="privacy_receipt_source_receipt_invalid"):
        _source(path)


@pytest.mark.parametrize(
    ("transport_class", "endpoint_class"),
    [
        ("LOCAL_PROCESS", "OLLAMA_CLOUD_RUN"),
        ("LOCAL_PROCESS", "OLLAMA_VERTEX_ENDPOINT"),
        ("PRIVATE_SERVICE", "OLLAMA_LOCAL"),
    ],
)
def test_external_receipt_source_rejects_mixed_locus_claims(
    tmp_path, transport_class: str, endpoint_class: str
) -> None:
    case_id = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
    cloud = {"case_token": case_id}
    receipt = deepcopy(_receipt(case_id, cloud))
    receipt.update(
        {
            "transport_class": transport_class,
            "endpoint_class": endpoint_class,
        }
    )
    body = {
        key: item
        for key, item in receipt.items()
        if key not in {"content_hash", "signature_ref"}
    }
    receipt["signature_ref"] = SIGNER.signature_ref(signing_content_hash(body))
    receipt["content_hash"] = artifact_content_hash(receipt)
    path = tmp_path / "receipts.json"
    path.write_text(
        json.dumps({"schema_version": "1.0.0", "receipts": [receipt]}),
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError, match="privacy_receipt_source_receipt_invalid"
    ):
        _source(path)


def test_external_receipt_source_rejects_invalid_signature_and_source_lock(
    tmp_path,
) -> None:
    case_id = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
    cloud = {"case_token": case_id}
    receipt = deepcopy(_receipt(case_id, cloud))
    receipt["signature_ref"]["signature"] = "f" * 64
    receipt["content_hash"] = artifact_content_hash(receipt)
    path = tmp_path / "receipts.json"
    path.write_text(
        json.dumps({"schema_version": "1.0.0", "receipts": [receipt]}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="privacy_receipt_source_signature_invalid"):
        _source(path)
    with pytest.raises(RuntimeError, match="privacy_receipt_source_hash_mismatch"):
        LockedJsonPrivacyReceiptSource(
            path,
            expected_sha256="0" * 64,
            signer=SIGNER,
            expected_key_fingerprint_sha256=signer_fingerprint_sha256(SIGNER),
        )
    with pytest.raises(RuntimeError, match="privacy_receipt_verifier_lock_mismatch"):
        LockedJsonPrivacyReceiptSource(
            path,
            expected_sha256=sha256(path.read_bytes()).hexdigest(),
            signer=SIGNER,
            expected_key_fingerprint_sha256="0" * 64,
        )
