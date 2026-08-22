from __future__ import annotations

from types import MappingProxyType

from recall.contracts import AgentRole


MODEL_ID = "gemini-3.7-flash"
VERTEX_LOCATION = "global"
MODEL_MAX_OUTPUT_TOKENS = 2048
MODEL_THINKING_BUDGET = 512
LIVE_TOOL_ROUND_TIMEOUT_SECONDS = 120
REQUIREMENTS = (
    "google-adk==2.7.1",
    "google-cloud-aiplatform[agent_engines]==1.165.1",
)
POLICY_VERSION = "1.0.0"

ROLE_NAMES = MappingProxyType(
    {
        AgentRole.EVIDENCE_WATCHER: "evidence_watcher",
        AgentRole.EVIDENCE_ASSESSOR: "evidence_assessor",
        AgentRole.CITATION_AUDITOR: "citation_auditor",
        AgentRole.FLEET_COORDINATOR: "fleet_coordinator",
    }
)

ROLE_TOOL_IDS = MappingProxyType(
    {
        AgentRole.EVIDENCE_WATCHER: frozenset({"evidence_connector"}),
        AgentRole.EVIDENCE_ASSESSOR: frozenset({"ledger_read"}),
        AgentRole.CITATION_AUDITOR: frozenset(
            {"ledger_read", "refetch_metadata"}
        ),
        AgentRole.FLEET_COORDINATOR: frozenset({"registry_search"}),
    }
)
