from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID, uuid5

from recall.contracts import ArtifactStatus, DataMode, build_artifact
from recall.ledger.models import ScanRunRecord
from recall.ledger.producers import PRODUCER_REGISTRY


def build_technical_halt_failure(
    *,
    current: ScanRunRecord,
    scan_artifact: Mapping[str, object],
    failure_code: str,
    now: datetime,
) -> dict[str, object]:
    artifact_id = str(uuid5(UUID(current.run_id), failure_code))
    return build_artifact(
        schema_name="FailureReceipt",
        schema_version="1.0.0",
        artifact_id=artifact_id,
        case_id=str(scan_artifact["case_id"]),
        run_id=current.run_id,
        producer={
            "component": "workflow-controller",
            "version": "0.1.0",
            "identity": "controller-failure-recorder",
        },
        created_at=now.isoformat().replace("+00:00", "Z"),
        input_artifact_ids=(str(current.scan_run_artifact_id),),
        data_mode=DataMode(scan_artifact["data_mode"]),
        status=ArtifactStatus.REJECTED,
        payload={
            "failure_code": failure_code,
            "stage": "POLICY_EVALUATION",
            "retryable": False,
            "attempt": 1,
            "budget_state": "WITHIN_LIMIT",
            "details": {},
            "related_artifact_ids": [str(current.scan_run_artifact_id)],
            "safe_terminal": "HALTED",
            "operator_action": (
                f"restore_{failure_code}_and_start_authorized_recovery"
            ),
        },
        authorized_producers=PRODUCER_REGISTRY,
    )
