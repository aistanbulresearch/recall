from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from recall.contracts import canonical_json_bytes, parse_artifact
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.privacy.receipt import verify_privacy_receipt
from recall.privacy.signing import (
    SIGNING_ALGORITHM,
    LocalSigner,
    signer_fingerprint_sha256,
)

from .compressed_preparation import _require_full_audit_privacy_receipt


class PrivacyReceiptSource(Protocol):
    def receipt_for(
        self, case_id: str, cloud_bound_payload: Mapping[str, object]
    ) -> Mapping[str, object]: ...


class LockedJsonPrivacyReceiptSource:
    """Exact external Gemma receipts; missing rows never fall back to synthesis."""

    def __init__(
        self,
        path: Path,
        *,
        expected_sha256: str,
        signer: LocalSigner,
        expected_key_fingerprint_sha256: str,
    ) -> None:
        try:
            raw = path.read_bytes()
            value = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("privacy_receipt_source_unavailable") from exc
        actual_source_sha256 = sha256(raw).hexdigest()
        actual_key_fingerprint = signer_fingerprint_sha256(signer)
        if (
            not _sha256(expected_sha256)
            or actual_source_sha256 != expected_sha256
        ):
            raise RuntimeError("privacy_receipt_source_hash_mismatch")
        if (
            not _sha256(expected_key_fingerprint_sha256)
            or actual_key_fingerprint != expected_key_fingerprint_sha256
        ):
            raise RuntimeError("privacy_receipt_verifier_lock_mismatch")
        if (
            not isinstance(value, dict)
            or set(value) != {"schema_version", "receipts"}
            or value["schema_version"] != "1.0.0"
            or not isinstance(value["receipts"], list)
        ):
            raise RuntimeError("privacy_receipt_source_shape_invalid")
        self._receipts: dict[str, Mapping[str, object]] = {}
        for wire in value["receipts"]:
            parsed = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
            if (
                parsed.schema_name != "PrivacyReceipt"
                or parsed.schema_version != "1.1.0"
                or parsed.run_id is not None
                or parsed.producer.identity != "privacy-gate"
                or parsed.payload.decision.value != "ACCEPTED"
                or parsed.case_id in self._receipts
            ):
                raise RuntimeError("privacy_receipt_source_receipt_invalid")
            valid_signature, _reasons = verify_privacy_receipt(
                dict(wire), signer
            )
            if (
                not valid_signature
                or parsed.payload.signature_ref["key_id"] != signer.key_id
                or parsed.payload.signature_ref["algorithm"]
                != SIGNING_ALGORITHM
            ):
                raise RuntimeError("privacy_receipt_source_signature_invalid")
            try:
                _require_full_audit_privacy_receipt(parsed.to_wire())
            except RuntimeError as exc:
                raise RuntimeError(
                    "privacy_receipt_source_receipt_invalid"
                ) from exc
            self._receipts[parsed.case_id] = parsed.to_wire()
        self._source_lock = {
            "source_sha256": actual_source_sha256,
            "key_id": signer.key_id,
            "algorithm": SIGNING_ALGORITHM,
            "key_fingerprint_sha256": actual_key_fingerprint,
        }

    @property
    def source_lock(self) -> Mapping[str, str]:
        return dict(self._source_lock)

    def receipt_for(
        self, case_id: str, cloud_bound_payload: Mapping[str, object]
    ) -> Mapping[str, object]:
        value = self._receipts.get(case_id)
        if value is None:
            raise RuntimeError(f"privacy_receipt_source_missing:{case_id}")
        from hashlib import sha256

        if value["payload_hash"] != sha256(
            canonical_json_bytes(cloud_bound_payload)
        ).hexdigest():
            raise RuntimeError("privacy_receipt_source_payload_mismatch")
        return dict(value)

    def assert_exact_case_set(self, case_ids: set[str]) -> None:
        if set(self._receipts) != case_ids:
            raise RuntimeError("privacy_receipt_source_case_set_mismatch")


def _sha256(value: str) -> bool:
    return len(value) == 64 and all(item in "0123456789abcdef" for item in value)
