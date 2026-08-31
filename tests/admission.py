from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid5

from recall.contracts import DataMode
from recall.controller import Controller
from recall.ledger.port import LedgerPort
from recall.privacy.receipt import build_privacy_receipt, verify_privacy_receipt
from recall.privacy.signing import LocalSigner, content_hash


TEST_SIGNER = LocalSigner("test-admission-key", b"test-admission-key-material")


def verify_test_receipt(value) -> bool:
    valid, _reasons = verify_privacy_receipt(dict(value), TEST_SIGNER)
    return valid


def in_memory_ledger():
    from recall.ledger import InMemoryLedger

    return InMemoryLedger(privacy_receipt_verifier=verify_test_receipt)


def cloud_payload(
    case_id: str,
    *,
    tenant_id: str = "synthetic-lab",
    region: str = "us-central1",
    data_mode: DataMode = DataMode.SYNTHETIC,
) -> dict[str, object]:
    return {
        "payload_kind": "recall.privacy.cloud_bound_payload",
        "payload_version": "1.0.0",
        "case_token": case_id,
        "tenant_id": tenant_id,
        "region": region,
        "data_mode": data_mode.value,
        "variant": {
            "gene": "BRCA2",
            "hgvs_c": "c.7522G>C",
            "hgvs_p": "p.Gly2508Arg",
            "assembly": "GRCh38",
        },
    }


def privacy_receipt(
    case_id: str,
    *,
    now: datetime,
    payload: dict[str, object] | None = None,
    decision: str = "ACCEPTED",
    data_mode: DataMode = DataMode.SYNTHETIC,
) -> dict[str, object]:
    outbound = payload or cloud_payload(case_id, data_mode=data_mode)
    return build_privacy_receipt(
        artifact_id=str(uuid5(UUID(case_id), "privacy-receipt")),
        case_id=case_id,
        created_at=now.isoformat().replace("+00:00", "Z"),
        producer_version="test",
        data_mode=data_mode.value,
        decision=decision,
        detector_versions={"deterministic": "test", "gemma": "disabled"},
        identifier_classes_checked=("synthetic",),
        deterministic_detector={"version": "test", "approved_spans": []},
        gemma_detector={
            "version": "test",
            "invoked": False,
            "schema_valid": False,
            "approved_residual_spans": [],
        },
        outbound={
            "scan_status": "CLEAR",
            "allowed_field_paths": sorted([
                "payload_kind",
                "payload_version",
                "case_token",
                "tenant_id",
                "region",
                "data_mode",
                "variant",
            ]),
            "raw_text_field_count": 0,
        },
        payload_hash=content_hash(outbound),
        warnings=(),
        signer=TEST_SIGNER,
    )


def admit_watch_case(
    ledger: LedgerPort,
    controller: Controller,
    *,
    case_id: str,
    now: datetime,
    next_scan_at: str,
    source_cursors: dict[str, str],
    tenant_id: str = "synthetic-lab",
    region: str = "us-central1",
    data_mode: DataMode = DataMode.SYNTHETIC,
):
    payload = cloud_payload(
        case_id,
        tenant_id=tenant_id,
        region=region,
        data_mode=data_mode,
    )
    receipt = privacy_receipt(
        case_id, now=now, payload=payload, data_mode=data_mode
    )
    ledger.append_artifact(receipt)
    created = controller.create_watch_case(
        watch_case_id=case_id,
        tenant_id=tenant_id,
        region=region,
        privacy_receipt_id=str(receipt["artifact_id"]),
        cloud_bound_payload=payload,
        data_mode=data_mode,
        source_cursors=source_cursors,
        pending_observation_hashes=(),
        next_scan_at=next_scan_at,
        now=now,
    )
    return created, receipt, payload
