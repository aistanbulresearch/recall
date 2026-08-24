from __future__ import annotations

import asyncio
import json
from collections import deque
from pathlib import Path

from recall.agents.factory import build_agent_bundle
from recall.agents.runtime import AdkRunnerProvider, StructuredAgentRuntime
from recall.agents.schemas import EvidenceSnapshotOutput
from recall.contracts import AgentRole, ContractError

from .recorded_llm import RecordedLlm


FIXTURE = Path("tests/fixtures/gemini/watcher_valid.json")
LIVE_METADATA = Path("tests/fixtures/gemini/watcher_live_smoke_metadata.json")


def evidence_connector(query: str) -> dict[str, str]:
    return {"query": query}


class SequenceProvider:
    def __init__(self, responses: list[str]) -> None:
        self.responses = deque(responses)
        self.call_count = 0

    async def generate(self, prompt: str) -> str:
        assert prompt
        self.call_count += 1
        return self.responses.popleft()


def test_recorded_gemini_response_runs_through_real_adk_runner() -> None:
    response = FIXTURE.read_text(encoding="utf-8")
    bundle = build_agent_bundle(
        AgentRole.EVIDENCE_WATCHER,
        tools={"evidence_connector": evidence_connector},
        model=RecordedLlm([response]),
    )
    provider = AdkRunnerProvider(bundle.agent)
    runtime = StructuredAgentRuntime(provider, EvidenceSnapshotOutput)
    result = asyncio.run(runtime.execute("Normalize the supplied connector result."))
    assert result.output.coverage_status == "PASS"
    assert result.model_calls == 1
    assert result.schema_repairs == 0


def test_live_smoke_metadata_is_sanitized_and_pinned() -> None:
    metadata = json.loads(LIVE_METADATA.read_text(encoding="utf-8"))
    assert metadata == {
        "artifact_content_hash": (
            "8f1aad206afd70eee6e959ef4e9cc3e32b16373073db7d1c41d0d97bc85f7ddf"
        ),
        "artifact_schema": "EvidenceSnapshot",
        "artifact_status": "VALID",
        "model": "gemini-3.7-flash",
        "model_calls": 1,
        "schema_repairs": 0,
        "vertex_location": "global",
    }


def test_free_text_gets_one_repair_then_valid_json() -> None:
    valid = FIXTURE.read_text(encoding="utf-8")
    provider = SequenceProvider(["This is not JSON.", valid])
    runtime = StructuredAgentRuntime(provider, EvidenceSnapshotOutput)
    result = asyncio.run(runtime.execute("Return the snapshot payload."))
    assert result.output.snapshot_hash == "b" * 64
    assert result.model_calls == 2
    assert result.schema_repairs == 1


def test_second_invalid_response_fails_typed_and_stops() -> None:
    provider = SequenceProvider(["free text", "still free text"])
    runtime = StructuredAgentRuntime(provider, EvidenceSnapshotOutput)
    try:
        asyncio.run(runtime.execute("Return the snapshot payload."))
    except ContractError as exc:
        assert exc.code == "agent_schema_invalid"
    else:
        raise AssertionError("invalid second response was accepted")
    assert provider.call_count == 2
