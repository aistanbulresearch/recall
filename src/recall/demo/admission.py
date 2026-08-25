from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid5

from recall.contracts import DataMode
from recall.privacy.receipt import build_privacy_receipt, verify_privacy_receipt
from recall.privacy.signing import LocalSigner, content_hash


_SYNTHETIC_FIXTURE_SIGNER = LocalSigner(
    "synthetic-fixture-key-not-for-production",
    b"recall-synthetic-fixture-key-not-for-production",
)


def synthetic_cloud_payload(
    case_id: str, *, data_mode: DataMode = DataMode.SYNTHETIC
) -> dict[str, object]:
    return {
        "payload_kind": "recall.privacy.cloud_bound_payload",
        "payload_version": "1.0.0",
        "case_token": case_id,
        "tenant_id": "synthetic-contest-lab",
        "region": "us-central1",
        "data_mode": data_mode.value,
        "variant": {
            "gene": "BRCA2",
            "hgvs_c": "c.7522G>C",
            "hgvs_p": "p.Gly2508Arg",
            "assembly": "GRCh38",
        },
    }


def synthetic_privacy_receipt(
    case_id: str,
    *,
    now: datetime,
    data_mode: DataMode = DataMode.SYNTHETIC,
) -> dict[str, object]:
    payload = synthetic_cloud_payload(case_id, data_mode=data_mode)
    return build_privacy_receipt(
        artifact_id=str(uuid5(UUID(case_id), "privacy-admission-receipt")),
        case_id=case_id,
        created_at=now.isoformat().replace("+00:00", "Z"),
        producer_version="synthetic-fixture-1",
        data_mode=data_mode.value,
        decision="ACCEPTED",
        detector_versions={"deterministic": "fixture", "gemma": "disabled"},
        identifier_classes_checked=("synthetic",),
        deterministic_detector={"version": "fixture", "approved_spans": []},
        gemma_detector={
            "version": "disabled",
            "invoked": False,
            "schema_valid": False,
            "approved_residual_spans": [],
        },
        outbound={
            "scan_status": "CLEAR",
            "allowed_field_paths": sorted(payload),
            "raw_text_field_count": 0,
        },
        payload_hash=content_hash(payload),
        warnings=(),
        signer=_SYNTHETIC_FIXTURE_SIGNER,
    )


def verify_synthetic_privacy_receipt(value) -> bool:
    valid, _reasons = verify_privacy_receipt(
        dict(value), _SYNTHETIC_FIXTURE_SIGNER
    )
    return valid
