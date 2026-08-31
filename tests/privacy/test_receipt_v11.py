"""PrivacyReceipt 1.1 emission: the locus block, all-or-nothing and signed."""

from __future__ import annotations

import secrets

import pytest

from recall.privacy.receipt import build_privacy_receipt, verify_privacy_receipt
from recall.privacy.signing import LocalSigner


def _base_kwargs(signer: LocalSigner) -> dict:
    return {
        "artifact_id": "11111111-1111-5111-8111-111111111111",
        "case_id": "22222222-2222-5222-8222-222222222222",
        "created_at": "2026-08-27T09:00:00Z",
        "producer_version": "0.1.0",
        "data_mode": "SYNTHETIC",
        "decision": "ACCEPTED",
        "detector_versions": {"deterministic": "deterministic-detectors@1.0.0"},
        "identifier_classes_checked": ["PERSON_NAME"],
        "deterministic_detector": {"version": "x", "approved_spans": []},
        "gemma_detector": {"invoked": True, "schema_valid": True, "version": "y", "approved_residual_spans": []},
        "outbound": {"allowed_field_paths": ["$.x"], "raw_text_field_count": 0, "scan_status": "CLEAR"},
        "payload_hash": "a" * 64,
        "warnings": [],
        "signer": signer,
    }


LOCUS = {
    "execution_locus": "LAB_LOCAL",
    "transport_class": "PRIVATE_SERVICE",
    "endpoint_class": "OLLAMA_LOCAL",
    "model_id": "gemma3n:e4b-it-q4_0",
    "model_revision": "sha256:" + "e8" * 32,
}


def test_no_block_emits_1_0_unchanged() -> None:
    signer = LocalSigner(key_id="t", key=secrets.token_bytes(32))
    receipt = build_privacy_receipt(**_base_kwargs(signer))
    assert receipt["schema_version"] == "1.0.0"
    assert "execution_locus" not in receipt
    valid, reasons = verify_privacy_receipt(dict(receipt), signer)
    assert valid, reasons


def test_block_emits_1_1_with_all_five_fields_signed() -> None:
    signer = LocalSigner(key_id="t", key=secrets.token_bytes(32))
    receipt = build_privacy_receipt(**_base_kwargs(signer), execution_locus_block=dict(LOCUS))
    assert receipt["schema_version"] == "1.1.0"
    for field, value in LOCUS.items():
        assert receipt[field] == value
    valid, reasons = verify_privacy_receipt(dict(receipt), signer)
    assert valid, reasons
    # The declaration is covered by the signature: tampering with the locus
    # after signing must break verification.
    tampered = dict(receipt)
    tampered["endpoint_class"] = "VERTEX_AI_GLOBAL"
    valid_t, _ = verify_privacy_receipt(tampered, signer)
    assert not valid_t


@pytest.mark.parametrize("drop", sorted(LOCUS))
def test_partial_block_is_an_error(drop: str) -> None:
    signer = LocalSigner(key_id="t", key=secrets.token_bytes(32))
    partial = {k: v for k, v in LOCUS.items() if k != drop}
    with pytest.raises(ValueError, match="locus block malformed"):
        build_privacy_receipt(**_base_kwargs(signer), execution_locus_block=partial)


def test_unprefixed_model_revision_is_an_error() -> None:
    signer = LocalSigner(key_id="t", key=secrets.token_bytes(32))
    bad = dict(LOCUS, model_revision="e8" * 32)
    with pytest.raises(ValueError, match="sha256-prefixed"):
        build_privacy_receipt(**_base_kwargs(signer), execution_locus_block=bad)
