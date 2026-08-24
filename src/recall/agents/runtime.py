from __future__ import annotations

import json
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from google.adk.agents import BaseAgent
from google.adk.runners import InMemoryRunner
from pydantic import BaseModel, ValidationError

from recall.contracts import ContractError


OutputT = TypeVar("OutputT", bound=BaseModel)


class ModelProvider(Protocol):
    def generate(self, prompt: str) -> Awaitable[str]: ...


@dataclass(frozen=True, slots=True)
class StructuredRunResult:
    output: BaseModel
    model_calls: int
    schema_repairs: int


class AdkRunnerProvider:
    def __init__(self, agent: BaseAgent) -> None:
        self._runner = InMemoryRunner(agent=agent)

    async def generate(self, prompt: str) -> str:
        events = await self._runner.run_debug(prompt, quiet=True)
        for event in reversed(events):
            content = getattr(event, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if parts:
                text = "".join(
                    str(part.text) for part in parts if getattr(part, "text", None)
                )
                if text:
                    return text
        raise ContractError("agent_response_missing")


class StructuredAgentRuntime:
    def __init__(
        self, provider: ModelProvider, output_schema: type[OutputT]
    ) -> None:
        self._provider = provider
        self._output_schema = output_schema

    async def execute(self, prompt: str) -> StructuredRunResult:
        response = await self._provider.generate(prompt)
        try:
            output = self._parse(response)
            return StructuredRunResult(output, model_calls=1, schema_repairs=0)
        except (json.JSONDecodeError, ValidationError):
            repair_prompt = (
                "The prior response was not valid strict JSON for the required "
                "response schema. Return only one corrected JSON object.\n"
                f"Prior response:\n{response}"
            )
            repaired = await self._provider.generate(repair_prompt)
            try:
                output = self._parse(repaired)
            except (json.JSONDecodeError, ValidationError) as exc:
                raise ContractError("agent_schema_invalid") from exc
            return StructuredRunResult(output, model_calls=2, schema_repairs=1)

    def _parse(self, response: str) -> OutputT:
        data = json.loads(response)
        return self._output_schema.model_validate(data)
