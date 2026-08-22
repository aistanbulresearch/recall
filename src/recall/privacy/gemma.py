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
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable

from recall.privacy.spans import IDENTIFIER_CLASSES

GEMMA_ADAPTER_VERSION = "gemma-span-adapter@1.1.0"

STATUS_OK = "OK"
STATUS_INVALID_JSON = "INVALID_JSON"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_DISABLED = "DISABLED"

# Denial-of-service bound, not a recall bound. It has to sit well above the
# number of identifiers a real note can carry, or a complete answer becomes
# impossible to accept: the development split holds 10 to 15 seeded spans per
# note, so the previous cap of 8 rejected every full response and measured the
# cap instead of the model. The prompt states no number at all; this constant
# only stops an unbounded list from being processed.
MAX_PROPOSALS = 24
SURFACE_NOT_FOUND = "model_response_surface_not_found"
JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

SYSTEM_INSTRUCTION = (
    "You locate residual identifier substrings in a clinical note. "
    "Return only JSON of the form "
    "{\"spans\": [{\"surface\": str, \"start\": int, \"end\": int, \"identifier_class\": str}]}. "
    "surface is the identifier exactly as it appears in the note, copied character for character. "
    "start and end are character offsets into the note, counting from zero, where "
    "note[start:end] is exactly that identifier and nothing else. "
    "identifier_class must be one of: " + ", ".join(IDENTIFIER_CLASSES) + ". "
    "Any other class name makes the whole response invalid. "
    "Return every identifier that appears in the note, not a selection. "
    "Return {\"spans\": []} when you find nothing. "
    "Never return explanations, reasoning, or any key other than these four."
)



@dataclass(frozen=True)
class GemmaProposal:
    """One model proposal, carrying both ways of locating the identifier.

    `surface` never reaches a receipt or a cloud-bound payload. It exists so
    the deterministic side can place the identifier itself instead of trusting
    the model's character arithmetic, and it stays laboratory-local.
    """

    start: int
    end: int
    identifier_class: str
    surface: str = ""


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
            # Sent even when a server ignores it: an OpenAI-compatible server
            # that hosts more than one model rejects the request without it.
            "model": self.model_id,
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


OLLAMA_DEFAULT_OPTIONS: dict[str, Any] = {
    # A note is roughly 200 tokens and the instruction roughly 600, so 2048 is
    # ample. A larger window is expensive on CPU for no benefit here.
    "num_ctx": 2048,
    "num_thread": 14,
    "num_predict": 512,
    "temperature": 0.0,
}
OLLAMA_DEFAULT_KEEP_ALIVE = "30m"


@dataclass
class OllamaChatTransport:
    """Client for a laboratory-local Ollama server.

    Ollama's OpenAI-compatible route accepts neither generation options nor
    `keep_alive`, and reloading a multi-gigabyte model on every call dominates
    the measured latency. This native-route client carries both, and every
    value it sends is recorded in the evidence manifest, because generation
    settings change what a measurement means.

    No retry, matching `LlamaServerTransport`.
    """

    base_url: str = "http://127.0.0.1:11434"
    model_id: str = "unconfigured"
    options: dict[str, Any] = field(default_factory=lambda: dict(OLLAMA_DEFAULT_OPTIONS))
    keep_alive: str = OLLAMA_DEFAULT_KEEP_ALIVE
    think: bool = False

    def request_settings(self) -> dict[str, Any]:
        """Exactly what this transport sends, for the manifest."""

        return {
            "server_kind": "ollama",
            "endpoint": "/api/chat",
            "options": dict(self.options),
            "keep_alive": self.keep_alive,
            "think": self.think,
        }

    def __call__(self, note_text: str, timeout_seconds: float) -> str:
        body = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": note_text},
            ],
            "think": self.think,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": dict(self.options),
        }
        request = urllib.request.Request(
            url=f"{self.base_url.rstrip('/')}/api/chat",
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
            return str(payload["message"]["content"])
        except (KeyError, TypeError) as error:
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
        if not isinstance(item, dict) or set(item) != {"surface", "start", "end", "identifier_class"}:
            return (), ("model_response_unknown_field",)
        start, end = item["start"], item["end"]
        identifier_class, surface = item["identifier_class"], item["surface"]
        if isinstance(start, bool) or isinstance(end, bool):
            return (), ("model_response_type_error",)
        if not isinstance(start, int) or not isinstance(end, int) or not isinstance(identifier_class, str):
            return (), ("model_response_type_error",)
        if not isinstance(surface, str) or not surface:
            return (), ("model_response_type_error",)
        if identifier_class not in IDENTIFIER_CLASSES:
            return (), ("model_response_unknown_identifier_class",)
        proposals.append(
            GemmaProposal(start=start, end=end, identifier_class=identifier_class, surface=surface)
        )
    return tuple(proposals), ()


def all_occurrences(note_text: str, surface: str) -> tuple[int, ...]:
    """Every start offset at which `surface` occurs, overlaps included."""

    if not surface:
        return ()
    offsets: list[int] = []
    index = note_text.find(surface)
    while index != -1:
        offsets.append(index)
        index = note_text.find(surface, index + 1)
    return tuple(offsets)


def locate_surfaces(
    note_text: str, proposals: Iterable[GemmaProposal]
) -> tuple[tuple[GemmaProposal, ...], tuple[str, ...]]:
    """Place each proposal by exact search on its surface string.

    The ambiguity rule is fixed before the measurement runs, so it cannot be
    chosen afterwards to suit a result:

    * the surface occurs exactly once: that position;
    * it occurs more than once: every occurrence becomes its own proposal;
    * it does not occur: the proposal is refused with
      `model_response_surface_not_found`.

    A refusal drops one proposal. It never invalidates the response, unlike a
    schema violation, because a model that miscopied one identifier still
    located the others.
    """

    located: list[GemmaProposal] = []
    refused = 0
    for proposal in proposals:
        offsets = all_occurrences(note_text, proposal.surface)
        if not offsets:
            refused += 1
            continue
        for start in offsets:
            located.append(
                replace(proposal, start=start, end=start + len(proposal.surface))
            )
    reason_codes = (SURFACE_NOT_FOUND,) if refused else ()
    return tuple(located), reason_codes
