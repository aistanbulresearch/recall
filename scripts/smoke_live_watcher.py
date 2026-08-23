from __future__ import annotations

import asyncio
import json

from recall.agents.config import MODEL_ID, VERTEX_LOCATION
from recall.agents.factory import build_agent_bundle
from recall.agents.runtime import AdkRunnerProvider
from recall.agents.schemas import EvidenceSnapshotOutput
from recall.contracts import AgentRole, ArtifactStatus, DataMode, build_artifact
from recall.ledger.producers import PRODUCER_REGISTRY


CASE_ID = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
RUN_ID = "b1d74cb8-25ac-4a84-ab9d-5a71a366c2da"
ARTIFACT_ID = "f7617fa1-2f75-47f3-b88d-ec72e88e3051"


def evidence_connector(query: str) -> dict[str, object]:
    """Fixed synthetic connector surface; the smoke prompt must not invoke it."""
    return {"query": query, "mode": "SYNTHETIC"}


async def main() -> None:
    bundle = build_agent_bundle(
        AgentRole.EVIDENCE_WATCHER,
        tools={"evidence_connector": evidence_connector},
    )
    # The production bundle keeps its exact connector allowlist. This one-call
    # smoke removes tools from an immutable clone so the ADK loop cannot add a
    # second inference turn after a function call.
    smoke_agent = bundle.agent.model_copy(update={"tools": []})
    provider = AdkRunnerProvider(smoke_agent)
    prompt = """This is a deployability smoke using an already-authorized synthetic
connector result. Do not call a tool. Normalize exactly this input:
effective_at=2026-08-22T06:30:00Z; observation_ids=[];
source_cursors={captured-replay:stage-1}; coverage_status=PASS;
normalized_facts={observation_count:1,scope:BRCA2-exons-15-26}; conflicts=[];
snapshot_hash=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.
Return only the required JSON object."""
    response = await asyncio.wait_for(provider.generate(prompt), timeout=60)
    output = EvidenceSnapshotOutput.model_validate_json(response)
    payload = output.to_contract_payload()
    artifact = build_artifact(
        schema_name="EvidenceSnapshot",
        schema_version="1.0.0",
        artifact_id=ARTIFACT_ID,
        case_id=CASE_ID,
        run_id=RUN_ID,
        producer={
            "component": "evidence-watcher",
            "version": "0.1.0",
            "identity": "evidence-watcher",
        },
        created_at="2026-08-22T06:30:00Z",
        input_artifact_ids=(),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.VALID,
        payload=payload,
        authorized_producers=PRODUCER_REGISTRY,
    )
    print(
        json.dumps(
            {
                "model": MODEL_ID,
                "vertex_location": VERTEX_LOCATION,
                "model_calls": 1,
                "schema_repairs": 0,
                "artifact_schema": artifact["schema_name"],
                "artifact_status": artifact["status"],
                "artifact_content_hash": artifact["content_hash"],
                "recorded_payload": payload,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
