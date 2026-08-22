from __future__ import annotations

import os
from pathlib import Path

from recall.agents.config import MODEL_ID, REQUIREMENTS, VERTEX_LOCATION
from recall.agents.factory import build_agent_bundle
from recall.agents.schemas import (
    AssessmentAgentOutput,
    CitationAuditOutput,
    EvidenceSnapshotOutput,
    RoutingPlanOutput,
)
from recall.contracts import AgentRole


def evidence_connector(query: str) -> dict[str, str]:
    return {"query": query}


def ledger_read(artifact_id: str) -> dict[str, str]:
    return {"artifact_id": artifact_id}


def refetch_metadata(identifier: str) -> dict[str, str]:
    return {"identifier": identifier}


def registry_search(capability: str) -> dict[str, str]:
    return {"capability": capability}


def test_four_roles_have_exact_model_schema_tools_and_versioned_prompts() -> None:
    cases = {
        AgentRole.EVIDENCE_WATCHER: (
            {"evidence_connector": evidence_connector},
            EvidenceSnapshotOutput,
            {"evidence_connector"},
        ),
        AgentRole.EVIDENCE_ASSESSOR: (
            {"ledger_read": ledger_read},
            AssessmentAgentOutput,
            {"ledger_read"},
        ),
        AgentRole.CITATION_AUDITOR: (
            {
                "ledger_read": ledger_read,
                "refetch_metadata": refetch_metadata,
            },
            CitationAuditOutput,
            {"ledger_read", "refetch_metadata"},
        ),
        AgentRole.FLEET_COORDINATOR: (
            {"registry_search": registry_search},
            RoutingPlanOutput,
            {"registry_search"},
        ),
    }
    for role, (tools, output_schema, expected_tools) in cases.items():
        bundle = build_agent_bundle(role, tools=tools)
        assert bundle.agent.model == MODEL_ID
        assert bundle.agent.output_schema is output_schema
        assert {tool.__name__ for tool in bundle.agent.tools} == expected_tools
        assert bundle.agent.disallow_transfer_to_parent is True
        assert bundle.agent.disallow_transfer_to_peers is True
        assert bundle.agent.include_contents == "none"
        assert bundle.requirements == REQUIREMENTS
        assert bundle.prompt_path.name.endswith("-v1.txt")
        assert Path(bundle.prompt_path).is_file()
        assert os.environ["GOOGLE_GENAI_USE_VERTEXAI"] == "1"
        assert os.environ["GOOGLE_CLOUD_LOCATION"] == "global"


def test_watcher_is_adk_app_compatible_without_cloud_call() -> None:
    bundle = build_agent_bundle(
        AgentRole.EVIDENCE_WATCHER,
        tools={"evidence_connector": evidence_connector},
    )
    app = bundle.to_adk_app()
    assert app.agent_framework == "google-adk"
    assert app._tmpl_attrs["agent"] is bundle.agent
    assert MODEL_ID == "gemini-3.7-flash"
    assert VERTEX_LOCATION == "global"
    assert "google-adk==2.7.1" in REQUIREMENTS
    assert "google-cloud-aiplatform[agent_engines]==1.165.1" in REQUIREMENTS


def test_tool_set_must_be_exact_not_merely_subset() -> None:
    try:
        build_agent_bundle(
            AgentRole.EVIDENCE_WATCHER,
            tools={
                "evidence_connector": evidence_connector,
                "ledger_read": ledger_read,
            },
        )
    except ValueError as exc:
        assert str(exc) == "agent_tool_set_invalid:EVIDENCE_WATCHER"
    else:
        raise AssertionError("unexpected tool expansion was accepted")
