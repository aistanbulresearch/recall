from __future__ import annotations

from collections import deque
from collections.abc import AsyncGenerator, Sequence

from google.adk.models import BaseLlm
from google.adk.models._capabilities import LlmCapabilities
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import PrivateAttr


class RecordedLlm(BaseLlm):
    """ADK model double backed only by sanitized recorded responses."""

    _responses: deque[str] = PrivateAttr()

    def __init__(self, responses: Sequence[str]) -> None:
        super().__init__(model="gemini-3.7-flash")
        self._responses = deque(responses)

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del llm_request, stream
        text = self._responses.popleft()
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=text)]),
            partial=False,
        )
