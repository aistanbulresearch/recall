from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any

from google.adk import Agent
from google.genai.types import GenerateContentConfig, ThinkingConfig
from vertexai.agent_engines import AdkApp
import vertexai

from recall.contracts import AgentRole

from .config import (
    MODEL_ID,
    MODEL_MAX_OUTPUT_TOKENS,
    MODEL_THINKING_BUDGET,
    REQUIREMENTS,
    ROLE_NAMES,
    ROLE_TOOL_IDS,
)
from .schemas import (
    AssessmentAgentOutput,
    CitationAuditOutput,
    EvidenceSnapshotOutput,
    RoutingPlanOutput,
    StrictOutput,
)


PROMPT_DIR = Path(__file__).with_name("prompts")
OUTPUT_SCHEMAS: Mapping[AgentRole, type[StrictOutput]] = {
    AgentRole.EVIDENCE_WATCHER: EvidenceSnapshotOutput,
    AgentRole.EVIDENCE_ASSESSOR: AssessmentAgentOutput,
    AgentRole.CITATION_AUDITOR: CitationAuditOutput,
    AgentRole.FLEET_COORDINATOR: RoutingPlanOutput,
}


@dataclass(frozen=True, slots=True)
class AgentBundle:
    role: AgentRole
    agent: Agent
    prompt_path: Path
    requirements: tuple[str, ...]

    def to_adk_app(self) -> AdkApp:
        vertexai.init(
            project=os.environ.get("GOOGLE_CLOUD_PROJECT", "recall-local-smoke"),
            location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
        )
        return AdkApp(
            agent=self.agent,
            app_name=f"recall_{ROLE_NAMES[self.role]}",
        )


def build_agent_bundle(
    role: AgentRole,
    *,
    tools: Mapping[str, Callable[..., Any]],
    model: str | Any = MODEL_ID,
) -> AgentBundle:
    os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "1"
    os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
    expected = ROLE_TOOL_IDS[role]
    if frozenset(tools) != expected:
        raise ValueError(f"agent_tool_set_invalid:{role.value}")
    prompt_path = PROMPT_DIR / f"{ROLE_NAMES[role].replace('_', '-')}-v1.txt"
    instruction = prompt_path.read_text(encoding="utf-8")
    agent = Agent(
        name=ROLE_NAMES[role],
        model=model,
        instruction=instruction,
        tools=[tools[tool_id] for tool_id in sorted(expected)],
        output_schema=OUTPUT_SCHEMAS[role],
        generate_content_config=GenerateContentConfig(
            max_output_tokens=MODEL_MAX_OUTPUT_TOKENS,
            thinking_config=ThinkingConfig(
                thinking_budget=MODEL_THINKING_BUDGET
            ),
        ),
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
        include_contents="none",
    )
    return AgentBundle(role, agent, prompt_path, REQUIREMENTS)
