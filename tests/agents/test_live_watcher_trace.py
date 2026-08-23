from __future__ import annotations

import json
from pathlib import Path


TRACE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "gemini"
    / "live_watcher_tool_trace.json"
)


def test_live_watcher_trace_is_complete_and_sanitized() -> None:
    trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))

    assert trace["runtime_mode"] == "LIVE_VERTEX"
    assert trace["data_mode"] == "CAPTURED_REPLAY"
    assert trace["model"] == "gemini-3.7-flash"
    assert trace["vertex_location"] == "global"
    assert trace["status"] == "PASS"
    assert trace["tool_calls"] == trace["tool_responses"] == 1
    assert trace["authorization_receipts"] == 1
    assert trace["backend_invocations"] == 1
    assert trace["artifact_status"] == "VALID"
    assert trace["credentials_recorded"] is False
    assert trace["identifiers_recorded"] is False

    turns = trace["model_turns"]
    assert [turn["turn"] for turn in turns] == [1, 2]
    assert [turn["finish_reason"] for turn in turns] == ["STOP", "STOP"]
    assert [turn["function_call_produced"] for turn in turns] == [True, False]
    assert all(turn["wall_seconds"] > 0 for turn in turns)
    assert all(turn["total_token_count"] > 0 for turn in turns)

    serialized = json.dumps(trace, sort_keys=True).lower()
    for forbidden in ("access_token", "api_key", "client_email", "project_id"):
        assert forbidden not in serialized
