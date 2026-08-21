from __future__ import annotations

from copy import deepcopy
from typing import Any

from recall.contracts import ArtifactStatus, DataMode, build_artifact
from recall.contracts.canonical import content_hash
from recall.ledger.producers import PRODUCER_REGISTRY


RUN_ID = "b1d74cb8-25ac-4a84-ab9d-5a71a366c2da"
ARTIFACT_ID = "f7617fa1-2f75-47f3-b88d-ec72e88e3051"


def tool_receipt() -> dict[str, object]:
    return build_artifact(
        schema_name="ToolAuthorizationReceipt",
        schema_version="1.0.0",
        artifact_id=ARTIFACT_ID,
        case_id="728d6e23-5ee4-4bd4-9319-4304f55628f3",
        run_id=RUN_ID,
        producer={
            "component": "tool-authorizer",
            "version": "0.1.0",
            "identity": "controller-authorizer",
        },
        created_at="2026-08-21T21:00:00Z",
        input_artifact_ids=(),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.REJECTED,
        payload={
            "agent_role": "EVIDENCE_ASSESSOR",
            "tool_id": "review-task-writer",
            "requested_action": "create_review_task",
            "decision": "DENIED",
            "policy_version": "1.0.1",
            "reason_codes": ["tool_not_allowlisted"],
            "invocation_id": "5fd80274-e5a4-4fd9-82c2-63cac6169e9d",
        },
        authorized_producers=PRODUCER_REGISTRY,
    )


def conflicting_receipt() -> dict[str, Any]:
    value = deepcopy(tool_receipt())
    value["requested_action"] = "different_action"
    value["content_hash"] = content_hash(value)
    return value
