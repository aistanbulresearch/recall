from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.adk.runners import InMemoryRunner

from recall.agents.config import (
    LIVE_TOOL_ROUND_TIMEOUT_SECONDS,
    MODEL_ID,
    VERTEX_LOCATION,
)
from recall.agents.factory import build_agent_bundle
from recall.agents.schemas import EvidenceSnapshotOutput
from recall.agents.authorization import ToolAuthorizer
from recall.connectors import ReplayConnector
from recall.contracts import AgentRole, ArtifactStatus, DataMode, build_artifact
from recall.ledger import InMemoryLedger
from recall.ledger.producers import PRODUCER_REGISTRY


CASE_ID = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
RUN_ID = "b1d74cb8-25ac-4a84-ab9d-5a71a366c2da"
ARTIFACT_ID = "f7617fa1-2f75-47f3-b88d-ec72e88e3051"
FIXED_NOW = datetime(2026, 8, 22, 6, 30, tzinfo=UTC)


async def main() -> None:
    root = Path(__file__).parents[1]
    connector = ReplayConnector(
        root, root / "docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json"
    )
    ledger = InMemoryLedger()
    authorizer = ToolAuthorizer(
        ledger,
        role=AgentRole.EVIDENCE_WATCHER,
        allowed_tool_ids=frozenset({"evidence_connector"}),
        case_id=CASE_ID,
        run_id=RUN_ID,
        data_mode=DataMode.CAPTURED_REPLAY,
        clock=lambda: FIXED_NOW,
    )

    def evidence_connector(stage: str) -> dict[str, object]:
        """Load one verified RCL-205 replay stage; stage must be stage-0/1/2."""
        authorized = authorizer.invoke(
            "evidence_connector",
            "read_verified_replay_stage",
            connector.tool_result,
            stage,
        )
        if authorized.value is None:
            raise RuntimeError("authorized_tool_returned_no_value")
        return authorized.value

    bundle = build_agent_bundle(
        AgentRole.EVIDENCE_WATCHER,
        tools={"evidence_connector": evidence_connector},
    )
    turn_starts: deque[float] = deque()
    model_turns: list[dict[str, object]] = []

    def before_model(callback_context: Any, llm_request: Any) -> None:
        del callback_context, llm_request
        turn_starts.append(time.perf_counter())

    def after_model(callback_context: Any, llm_response: Any) -> None:
        del callback_context
        started_at = turn_starts.popleft()
        usage = getattr(llm_response, "usage_metadata", None)
        content = getattr(llm_response, "content", None)
        parts = getattr(content, "parts", None) if content else None
        model_turns.append(
            {
                "candidates_token_count": _usage_count(
                    usage, "candidates_token_count"
                ),
                "finish_reason": _enum_value(
                    getattr(llm_response, "finish_reason", None)
                ),
                "function_call_produced": any(
                    getattr(part, "function_call", None) is not None
                    for part in parts or ()
                ),
                "prompt_token_count": _usage_count(usage, "prompt_token_count"),
                "thoughts_token_count": _usage_count(
                    usage, "thoughts_token_count"
                ),
                "total_token_count": _usage_count(usage, "total_token_count"),
                "turn": len(model_turns) + 1,
                "wall_seconds": round(time.perf_counter() - started_at, 3),
            }
        )

    instrumented_agent = bundle.agent.model_copy(
        update={
            "after_model_callback": after_model,
            "before_model_callback": before_model,
        }
    )
    runner = InMemoryRunner(agent=instrumented_agent)
    prompt = (
        "Call evidence_connector exactly once with stage='stage-1'. "
        "The tool returns a verified snapshot_payload derived from frozen bytes. "
        "Return that snapshot_payload exactly as the required JSON object. "
        "Do not add interpretation, classification, or prose."
    )
    run_started_at = time.perf_counter()
    try:
        events = await asyncio.wait_for(
            runner.run_debug(prompt, quiet=True),
            timeout=LIVE_TOOL_ROUND_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error_type": type(exc).__name__,
                    "model": MODEL_ID,
                    "model_turns": model_turns,
                    "run_wall_seconds": round(
                        time.perf_counter() - run_started_at, 3
                    ),
                    "status": "FAIL",
                    "unfinished_model_turns": len(turn_starts),
                    "vertex_location": VERTEX_LOCATION,
                },
                sort_keys=True,
            )
        )
        raise
    run_wall_seconds = round(time.perf_counter() - run_started_at, 3)
    try:
        output_text = _last_text(events)
        output = EvidenceSnapshotOutput.model_validate_json(output_text)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error_type": type(exc).__name__,
                    "model": MODEL_ID,
                    "model_turns": model_turns,
                    "run_wall_seconds": run_wall_seconds,
                    "status": "FAIL",
                    "unfinished_model_turns": len(turn_starts),
                    "vertex_location": VERTEX_LOCATION,
                },
                sort_keys=True,
            )
        )
        raise
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
        data_mode=DataMode.CAPTURED_REPLAY,
        status=ArtifactStatus.VALID,
        payload=payload,
        authorized_producers=PRODUCER_REGISTRY,
    )
    ledger.append_artifact(artifact)
    tool_calls, tool_responses = _tool_event_counts(events)
    print(
        json.dumps(
            {
                "artifact_content_hash": artifact["content_hash"],
                "artifact_schema": artifact["schema_name"],
                "artifact_status": artifact["status"],
                "authorization_receipts": authorizer.counters.allowed,
                "backend_invocations": authorizer.counters.backend_invocations,
                "data_mode": artifact["data_mode"],
                "model": MODEL_ID,
                "model_turn_count": len(model_turns),
                "model_turns": model_turns,
                "recorded_payload": payload,
                "run_wall_seconds": run_wall_seconds,
                "status": "PASS",
                "tool_calls": tool_calls,
                "tool_responses": tool_responses,
                "vertex_location": VERTEX_LOCATION,
            },
            sort_keys=True,
        )
    )


def _usage_count(usage: Any, field: str) -> int:
    return int(getattr(usage, field, 0) or 0)


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _last_text(events: list[object]) -> str:
    for event in reversed(events):
        content = getattr(event, "content", None)
        parts = getattr(content, "parts", None) if content else None
        if parts:
            text = "".join(
                str(part.text) for part in parts if getattr(part, "text", None)
            )
            if text:
                return text
    raise RuntimeError("agent_response_missing")


def _tool_event_counts(events: list[object]) -> tuple[int, int]:
    calls = 0
    responses = 0
    for event in events:
        content = getattr(event, "content", None)
        parts = getattr(content, "parts", None) if content else None
        for part in parts or ():
            calls += int(getattr(part, "function_call", None) is not None)
            responses += int(getattr(part, "function_response", None) is not None)
    return calls, responses


if __name__ == "__main__":
    asyncio.run(main())
