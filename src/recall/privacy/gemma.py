"""Local Gemma adapter: span proposals only.

The adapter talks to a laboratory-local `llama.cpp` server. It returns typed
outcomes for every failure mode. It never redacts, never approves, and never
decides whether a payload may leave the laboratory. A missing, slow, or
malformed model response is an explicit failure state, never a clean result.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

from recall.privacy.spans import IDENTIFIER_CLASSES

GEMMA_ADAPTER_VERSION = "gemma-span-adapter@1.0.0"

STATUS_OK = "OK"
STATUS_INVALID_JSON = "INVALID_JSON"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_DISABLED = "DISABLED"

MAX_PROPOSALS = 8
JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

SYSTEM_INSTRUCTION = (
    "You locate residual identifier substrings in a clinical note. "
    "Return only JSON of the form {\"spans\": [{\"start\": int, \"end\": int, \"identifier_class\": str}]}. "
    "start and end are character offsets into the note. "
    "Return {\"spans\": []} when you find nothing. "
    "Never return explanations, reasoning, the substring itself, or any other key."
)


@dataclass(frozen=True)
class GemmaProposal:
    start: int
    end: int
    identifier_class: str


@dataclass(frozen=True)
class GemmaOutcome:
    """Typed result of one local model invocation."""

    invoked: bool
    status: str
    schema_valid: bool
    proposals: tuple[GemmaProposal, ...] = ()
    latency_ms: int | None = None
    reason_codes: tuple[str, ...] = ()
    model_id: str = "unconfigured"
    adapter_version: str = GEMMA_ADAPTER_VERSION

    @property
    def usable(self) -> bool:
        return self.invoked and self.status == STATUS_OK and self.schema_valid


class TransportTimeout(Exception):
    """Raised by a transport when the local model exceeds its deadline."""


class TransportUnavailable(Exception):
    """Raised by a transport when the local model cannot be reached."""


Transport = Callable[[str, float], str]


@dataclass
class LlamaServerTransport:
    """Minimal client for a laboratory-local `llama.cpp` server.

    No retry: the brief fixes retry at zero so a slow or broken local model can
    never delay or silently repeat an egress decision.
    """

    base_url: str = "http://127.0.0.1:8080"
    model_id: str = "unconfigured"
    max_tokens: int = 512
    extra_body: dict[str, Any] = field(default_factory=dict)

    def __call__(self, note_text: str, timeout_seconds: float) -> str:
        body = {
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": note_text},
            ],
            "temperature": 0.0,
            "max_tokens": self.max_tokens,
            "stream": False,
            **self.extra_body,
        }
        request = urllib.request.Request(
            url=f"{self.base_url.rstrip('/')}/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except TimeoutError as error:  # pragma: no cover - environment dependent
            raise TransportTimeout(str(error)) from error
        except urllib.error.URLError as error:  # pragma: no cover - environment dependent
            if isinstance(getattr(error, "reason", None), TimeoutError):
                raise TransportTimeout(str(error)) from error
            raise TransportUnavailable(str(error)) from error
        except OSError as error:  # pragma: no cover - environment dependent
            raise TransportUnavailable(str(error)) from error
        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as error:
            raise TransportUnavailable(f"unexpected local model response shape: {error}") from error


class GemmaResidualDetector:
    """Invokes the local model and validates its output against a strict schema."""

    def __init__(
        self,
        transport: Transport | None = None,
        *,
        model_id: str = "unconfigured",
        timeout_seconds: float = 8.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport
        self._model_id = model_id
        self._timeout_seconds = timeout_seconds
        self._clock = clock

    def propose(self, note_text: str) -> GemmaOutcome:
        if self._transport is None:
            return GemmaOutcome(
                invoked=False,
                status=STATUS_DISABLED,
                schema_valid=False,
                reason_codes=("local_model_not_configured",),
                model_id=self._model_id,
            )

        started = self._clock()
        try:
            raw = self._transport(note_text, self._timeout_seconds)
        except TransportTimeout:
            return GemmaOutcome(
                invoked=True,
                status=STATUS_TIMEOUT,
                schema_valid=False,
                latency_ms=self._elapsed_ms(started),
                reason_codes=("local_model_timeout",),
                model_id=self._model_id,
            )
        except TransportUnavailable:
            return GemmaOutcome(
                invoked=True,
                status=STATUS_UNAVAILABLE,
                schema_valid=False,
                latency_ms=self._elapsed_ms(started),
                reason_codes=("local_model_unavailable",),
                model_id=self._model_id,
            )

        latency_ms = self._elapsed_ms(started)
        proposals, reason_codes = parse_span_response(raw)
        if reason_codes:
            return GemmaOutcome(
                invoked=True,
                status=STATUS_INVALID_JSON,
                schema_valid=False,
                latency_ms=latency_ms,
                reason_codes=reason_codes,
                model_id=self._model_id,
            )
        return GemmaOutcome(
            invoked=True,
            status=STATUS_OK,
            schema_valid=True,
            proposals=proposals,
            latency_ms=latency_ms,
            model_id=self._model_id,
        )

    def _elapsed_ms(self, started: float) -> int:
        return int(round((self._clock() - started) * 1000))


def parse_span_response(raw: str) -> tuple[tuple[GemmaProposal, ...], tuple[str, ...]]:
    """Strict schema check for the local model response.

    Any unknown key, wrong type, or non-JSON body is a schema failure. The
    caller must treat a schema failure as an unusable outcome, not as an empty
    result.
    """

    if not isinstance(raw, str) or not raw.strip():
        return (), ("empty_model_response",)
    candidate = raw.strip()
    if not candidate.startswith("{"):
        match = JSON_OBJECT_PATTERN.search(candidate)
        if match is None:
            return (), ("model_response_not_json",)
        candidate = match.group(0)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return (), ("model_response_not_json",)
    if not isinstance(payload, dict):
        return (), ("model_response_not_object",)
    if set(payload) != {"spans"}:
        return (), ("model_response_unknown_field",)
    spans = payload["spans"]
    if not isinstance(spans, list):
        return (), ("model_response_spans_not_array",)
    if len(spans) > MAX_PROPOSALS:
        return (), ("model_response_too_many_spans",)

    proposals: list[GemmaProposal] = []
    for item in spans:
        if not isinstance(item, dict) or set(item) != {"start", "end", "identifier_class"}:
            return (), ("model_response_unknown_field",)
        start, end, identifier_class = item["start"], item["end"], item["identifier_class"]
        if isinstance(start, bool) or isinstance(end, bool):
            return (), ("model_response_type_error",)
        if not isinstance(start, int) or not isinstance(end, int) or not isinstance(identifier_class, str):
            return (), ("model_response_type_error",)
        if identifier_class not in IDENTIFIER_CLASSES:
            return (), ("model_response_unknown_identifier_class",)
        proposals.append(GemmaProposal(start=start, end=end, identifier_class=identifier_class))
    return tuple(proposals), ()
