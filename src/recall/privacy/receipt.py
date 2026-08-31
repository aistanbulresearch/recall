"""`PrivacyReceipt` wire construction.

Field names, nested shapes, and the common envelope follow
`docs/contracts/ARTIFACT_CONTRACTS.md`. The executable schema that parses this
dict is owned by lane L2; this module only emits the contract-shaped value.
"""

from __future__ import annotations

from typing import Any, Iterable

from recall.contracts.canonical import content_hash as artifact_content_hash
from recall.privacy.signing import (
    SIGNING_ALGORITHM,
    LocalSigner,
    canonical_json,
    content_hash,
)

SCHEMA_NAME = "PrivacyReceipt"
SCHEMA_VERSION = "1.0.0"
PRODUCER_COMPONENT = "local-privacy-gate"
PRODUCER_IDENTITY = "privacy-gate"

DECISION_ACCEPTED = "ACCEPTED"
DECISION_QUARANTINED = "QUARANTINED"
STATUS_VALID = "VALID"


def build_warning(code: str, message_key: str, related_artifact_ids: Iterable[str] = ()) -> dict[str, Any]:
    """Typed warning: exactly `code`, `message_key`, and `related_artifact_ids`."""

    return {"code": code, "message_key": message_key, "related_artifact_ids": sorted(related_artifact_ids)}


SCHEMA_VERSION_V11 = "1.1.0"

# The five 1.1 locus fields, all-or-nothing: a receipt either declares where
# the model leg ran (1.1) or predates the question (1.0). A partial block is a
# bug, never a wire shape.
LOCUS_FIELDS = (
    "execution_locus",
    "transport_class",
    "endpoint_class",
    "model_id",
    "model_revision",
)


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
    execution_locus_block: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Assemble, hash, and sign one receipt.

    The detached signature covers the unsigned receipt body. The final artifact
    hash then covers that signature reference as well as the body, avoiding a
    circular signature while keeping the complete wire artifact tamper-evident.
    """

    if decision not in (DECISION_ACCEPTED, DECISION_QUARANTINED):
        raise ValueError(f"unregistered privacy decision: {decision}")
    if execution_locus_block is not None:
        missing = [f for f in LOCUS_FIELDS if not execution_locus_block.get(f)]
        extra = [f for f in execution_locus_block if f not in LOCUS_FIELDS]
        if missing or extra:
            raise ValueError(f"locus block malformed: missing={missing} extra={extra}")
        if not str(execution_locus_block["model_revision"]).startswith("sha256:"):
            raise ValueError("model_revision must be sha256-prefixed")

    receipt: dict[str, Any] = {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION
        if execution_locus_block is None
        else SCHEMA_VERSION_V11,
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
    if execution_locus_block is not None:
        # Inserted BEFORE signing, so the declaration is covered by the
        # signature like every other claim in the receipt.
        receipt.update({f: execution_locus_block[f] for f in LOCUS_FIELDS})

    signed_body_hash = content_hash(receipt)
    receipt["signature_ref"] = signer.signature_ref(signed_body_hash)
    receipt["content_hash"] = artifact_content_hash(receipt)
    return receipt


def verify_privacy_receipt(receipt: dict[str, Any], signer: LocalSigner) -> tuple[bool, tuple[str, ...]]:
    """Recompute the content hash and check the signature."""

    reasons: list[str] = []
    if artifact_content_hash(receipt) != receipt.get("content_hash"):
        reasons.append("content_hash_mismatch")
    body = {
        key: value
        for key, value in receipt.items()
        if key not in ("content_hash", "signature_ref")
    }
    signed_body_hash = content_hash(body)
    signature_ref = receipt.get("signature_ref") or {}
    if signature_ref.get("key_id") != signer.key_id:
        reasons.append("signature_key_mismatch")
    if signature_ref.get("algorithm") != SIGNING_ALGORITHM:
        reasons.append("signature_algorithm_mismatch")
    if not signer.verify(signed_body_hash, str(signature_ref.get("signature"))):
        reasons.append("signature_invalid")
    return (not reasons), tuple(reasons)


def receipt_canonical_json(receipt: dict[str, Any]) -> str:
    return canonical_json(receipt)
