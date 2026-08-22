"""`PrivacyReceipt` wire construction.

Field names, nested shapes, and the common envelope follow
`docs/contracts/ARTIFACT_CONTRACTS.md`. The executable schema that parses this
dict is owned by lane L2; this module only emits the contract-shaped value.
"""

from __future__ import annotations

from typing import Any, Iterable

from recall.privacy.signing import LocalSigner, canonical_json, content_hash

SCHEMA_NAME = "PrivacyReceipt"
SCHEMA_VERSION = "1.0.0"
PRODUCER_COMPONENT = "local-privacy-gate"
PRODUCER_IDENTITY = "lab-privacy-gate"

DECISION_ACCEPTED = "ACCEPTED"
DECISION_QUARANTINED = "QUARANTINED"
STATUS_VALID = "VALID"


def build_warning(code: str, message_key: str, related_artifact_ids: Iterable[str] = ()) -> dict[str, Any]:
    """Typed warning: exactly `code`, `message_key`, and `related_artifact_ids`."""

    return {"code": code, "message_key": message_key, "related_artifact_ids": sorted(related_artifact_ids)}


def build_privacy_receipt(
    *,
    artifact_id: str,
    case_id: str,
    created_at: str,
    producer_version: str,
    data_mode: str,
    decision: str,
    detector_versions: dict[str, str],
    identifier_classes_checked: Iterable[str],
    deterministic_detector: dict[str, Any],
    gemma_detector: dict[str, Any],
    outbound: dict[str, Any],
    payload_hash: str,
    warnings: Iterable[dict[str, Any]],
    signer: LocalSigner,
) -> dict[str, Any]:
    """Assemble, hash, and sign one receipt.

    `content_hash` covers the canonical receipt with `content_hash` and
    `signature_ref` omitted. The signature then covers that hash, so both the
    body and the hash are verifiable without a circular definition.
    """

    if decision not in (DECISION_ACCEPTED, DECISION_QUARANTINED):
        raise ValueError(f"unregistered privacy decision: {decision}")

    receipt: dict[str, Any] = {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "artifact_id": artifact_id,
        "case_id": case_id,
        "run_id": None,
        "producer": {
            "component": PRODUCER_COMPONENT,
            "version": producer_version,
            "identity": PRODUCER_IDENTITY,
        },
        "created_at": created_at,
        "input_artifact_ids": [],
        "data_mode": data_mode,
        "status": STATUS_VALID,
        "warnings": list(warnings),
        "extensions": {},
        "decision": decision,
        "detector_versions": dict(sorted(detector_versions.items())),
        "identifier_classes_checked": sorted(identifier_classes_checked),
        "detectors": {
            "deterministic": deterministic_detector,
            "gemma": gemma_detector,
        },
        "outbound": outbound,
        "payload_hash": payload_hash,
    }

    receipt["content_hash"] = content_hash(receipt)
    receipt["signature_ref"] = signer.signature_ref(receipt["content_hash"])
    return receipt


def verify_privacy_receipt(receipt: dict[str, Any], signer: LocalSigner) -> tuple[bool, tuple[str, ...]]:
    """Recompute the content hash and check the signature."""

    reasons: list[str] = []
    body = {key: value for key, value in receipt.items() if key not in ("content_hash", "signature_ref")}
    if content_hash(body) != receipt.get("content_hash"):
        reasons.append("content_hash_mismatch")
    signature_ref = receipt.get("signature_ref") or {}
    if signature_ref.get("key_id") != signer.key_id:
        reasons.append("signature_key_mismatch")
    if not signer.verify(str(receipt.get("content_hash")), str(signature_ref.get("signature"))):
        reasons.append("signature_invalid")
    return (not reasons), tuple(reasons)


def receipt_canonical_json(receipt: dict[str, Any]) -> str:
    return canonical_json(receipt)
