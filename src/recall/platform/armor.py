"""Model Armor template management and sanitization decisions.

The decision is read from what Model Armor actually returned. There are exactly
three outcomes and none of them defaults to safe:

- `NO_MATCH_FOUND` with a successful invocation is `PASS`.
- `MATCH_FOUND` is `BLOCK`.
- An unreachable service, a partial or failed invocation, or an unspecified match
  state is `DEGRADED`. Unscreened content is never reported as clean.

Templates are created with prompt-injection and jailbreak detection, sensitive
data inspection, and malicious URI detection enabled, and carry the lane labels.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from .config import PlatformConfig, resource_labels
from .errors import PlatformError

logger = logging.getLogger(__name__)

TEMPLATE_ID = "recall-armor-default"
ARMOR_COMPONENT = "model-armor"

MATCH_FOUND = "MATCH_FOUND"
NO_MATCH_FOUND = "NO_MATCH_FOUND"
INVOCATION_SUCCESS = "SUCCESS"

FILTER_RESULT_KEYS = (
    "piAndJailbreakFilterResult",
    "sdpFilterResult",
    "raiFilterResult",
    "maliciousUriFilterResult",
    "csamFilterFilterResult",
    "virusScanFilterResult",
)


class ArmorDecision(StrEnum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    DEGRADED = "DEGRADED"


def armor_template_body(
    *, confidence_level: str = "LOW_AND_ABOVE"
) -> dict[str, Any]:
    """Build the template body: injection, jailbreak, sensitive data, malicious URI."""

    return {
        "labels": resource_labels(ARMOR_COMPONENT),
        "filterConfig": {
            "piAndJailbreakFilterSettings": {
                "filterEnforcement": "ENABLED",
                "confidenceLevel": confidence_level,
            },
            "sdpSettings": {"basicConfig": {"filterEnforcement": "ENABLED"}},
            "maliciousUriFilterSettings": {"filterEnforcement": "ENABLED"},
            "raiSettings": {
                "raiFilters": [
                    {"filterType": "DANGEROUS", "confidenceLevel": confidence_level},
                    {"filterType": "HARASSMENT", "confidenceLevel": confidence_level},
                    {"filterType": "HATE_SPEECH", "confidenceLevel": confidence_level},
                    {
                        "filterType": "SEXUALLY_EXPLICIT",
                        "confidenceLevel": confidence_level,
                    },
                ]
            },
        },
        "templateMetadata": {
            "enforcementType": "INSPECT_AND_BLOCK",
            "logSanitizeOperations": True,
            "ignorePartialInvocationFailures": False,
        },
    }


@dataclass(frozen=True, slots=True)
class ArmorFinding:
    """One filter's verdict, carried without the screened text."""

    filter_name: str
    match_state: str
    execution_state: str
    confidence_level: str | None

    def to_wire(self) -> dict[str, Any]:
        return {
            "filter_name": self.filter_name,
            "match_state": self.match_state,
            "execution_state": self.execution_state,
            "confidence_level": self.confidence_level,
        }


def _findings(filter_results: Mapping[str, Any]) -> list[ArmorFinding]:
    findings: list[ArmorFinding] = []
    for name, body in sorted(filter_results.items()):
        if not isinstance(body, Mapping):
            continue
        inner: Mapping[str, Any] = body
        for key in FILTER_RESULT_KEYS:
            nested = body.get(key)
            if isinstance(nested, Mapping):
                inner = nested
                break
        findings.append(
            ArmorFinding(
                filter_name=name,
                match_state=str(inner.get("matchState", "FILTER_MATCH_STATE_UNSPECIFIED")),
                execution_state=str(
                    inner.get("executionState", "FILTER_EXECUTION_STATE_UNSPECIFIED")
                ),
                confidence_level=(
                    str(inner["confidenceLevel"])
                    if inner.get("confidenceLevel")
                    else None
                ),
            )
        )
    return findings


def evaluate_sanitization(payload: Mapping[str, Any]) -> tuple[ArmorDecision, list[ArmorFinding], list[str]]:
    """Turn a sanitize response into a decision, findings, and reason codes."""

    result = payload.get("sanitizationResult")
    if not isinstance(result, Mapping):
        return ArmorDecision.DEGRADED, [], ["armor_response_malformed"]
    match_state = str(result.get("filterMatchState", ""))
    invocation = str(result.get("invocationResult", ""))
    filter_results = result.get("filterResults")
    findings = _findings(filter_results if isinstance(filter_results, Mapping) else {})

    if match_state == MATCH_FOUND:
        return ArmorDecision.BLOCK, findings, ["armor_match_found"]
    if match_state == NO_MATCH_FOUND and invocation == INVOCATION_SUCCESS:
        return ArmorDecision.PASS, findings, []
    reasons = ["armor_inconclusive"]
    if invocation and invocation != INVOCATION_SUCCESS:
        reasons.append(f"armor_invocation_{invocation.lower()}")
    return ArmorDecision.DEGRADED, findings, sorted(set(reasons))


def armor_receipt(
    *,
    decision: ArmorDecision,
    findings: Sequence[ArmorFinding],
    template_version: str | None,
    reason_codes: Sequence[str] = (),
) -> dict[str, Any]:
    """Lane-local receipt: decision, findings, template version.

    This shape is not yet a registered artifact contract. A `PASS` requires a
    known template version, so a decision cannot claim to come from a template
    that was never read back.
    """

    decision = ArmorDecision(decision)
    if decision is ArmorDecision.PASS and not template_version:
        raise PlatformError("armor_template_version_missing")
    return {
        "decision": decision.value,
        "findings": [finding.to_wire() for finding in findings],
        "template_version": template_version,
        "reason_codes": sorted(set(reason_codes)),
    }


class ModelArmorClient(Protocol):
    """Model Armor surface used by this lane."""

    def create_template(
        self, location: str, template_id: str, body: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...

    def get_template(self, location: str, template_id: str) -> Mapping[str, Any]: ...

    def delete_template(self, location: str, template_id: str) -> None: ...

    def sanitize_user_prompt(
        self, location: str, template_id: str, text: str
    ) -> Mapping[str, Any]: ...

    def sanitize_model_response(
        self, location: str, template_id: str, text: str, user_prompt: str
    ) -> Mapping[str, Any]: ...


class ArmorScreen:
    """Screen prompts and responses, degrading loudly when Model Armor is unreachable."""

    def __init__(
        self, client: ModelArmorClient, location: str, template_id: str = TEMPLATE_ID
    ) -> None:
        self._client = client
        self._location = location
        self._template_id = template_id

    def template_version(self) -> str | None:
        try:
            template = self._client.get_template(self._location, self._template_id)
        except PlatformError:
            return None
        version = template.get("updateTime")
        return str(version) if version else None

    def screen_prompt(self, text: str) -> dict[str, Any]:
        return self._screen(
            lambda: self._client.sanitize_user_prompt(
                self._location, self._template_id, text
            )
        )

    def screen_response(self, text: str, *, user_prompt: str) -> dict[str, Any]:
        return self._screen(
            lambda: self._client.sanitize_model_response(
                self._location, self._template_id, text, user_prompt
            )
        )

    def _screen(self, call: Any) -> dict[str, Any]:
        version = self.template_version()
        try:
            payload = call()
        except PlatformError as exc:
            return armor_receipt(
                decision=ArmorDecision.DEGRADED,
                findings=[],
                template_version=version,
                reason_codes=[exc.code],
            )
        decision, findings, reasons = evaluate_sanitization(payload)
        if decision is ArmorDecision.PASS and not version:
            # The screen answered clean, but the policy it screened against cannot
            # be identified. An unattributable pass is degraded, not clean.
            decision = ArmorDecision.DEGRADED
            reasons = [*reasons, "armor_template_version_unknown"]
        return armor_receipt(
            decision=decision,
            findings=findings,
            template_version=version,
            reason_codes=reasons,
        )


class RestModelArmorClient:
    """Model Armor client over REST with application default credentials."""

    def __init__(self, config: PlatformConfig) -> None:
        self._project = config.project_id
        self._session = self._authorised_session()

    @staticmethod
    def _authorised_session() -> Any:
        try:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise PlatformError("armor_sdk_unavailable", str(exc)) from exc
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return AuthorizedSession(credentials)

    def _base(self, location: str) -> str:
        return (
            f"https://modelarmor.{location}.rep.googleapis.com/v1"
            f"/projects/{self._project}/locations/{location}"
        )

    def _request(
        self,
        method: str,
        location: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        url = f"{self._base(location)}/{path}"
        response = self._session.request(
            method, url, params=dict(params or {}), json=body, timeout=30
        )
        if response.status_code != 200:
            raise PlatformError("armor_call_failed", f"{path}:{response.status_code}")
        return response.json() if response.content else {}

    def create_template(
        self, location: str, template_id: str, body: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return self._request(
            "POST",
            location,
            "templates",
            params={"templateId": template_id},
            body=body,
        )

    def get_template(self, location: str, template_id: str) -> Mapping[str, Any]:
        return self._request("GET", location, f"templates/{template_id}")

    def delete_template(self, location: str, template_id: str) -> None:
        self._request("DELETE", location, f"templates/{template_id}")

    def sanitize_user_prompt(
        self, location: str, template_id: str, text: str
    ) -> Mapping[str, Any]:
        return self._request(
            "POST",
            location,
            f"templates/{template_id}:sanitizeUserPrompt",
            body={"userPromptData": {"text": text}},
        )

    def sanitize_model_response(
        self, location: str, template_id: str, text: str, user_prompt: str
    ) -> Mapping[str, Any]:
        return self._request(
            "POST",
            location,
            f"templates/{template_id}:sanitizeModelResponse",
            body={"modelResponseData": {"text": text}, "userPrompt": user_prompt},
        )
