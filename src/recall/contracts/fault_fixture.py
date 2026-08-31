from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import re
from typing import Any
from uuid import UUID

from .enums import AgentRole, DataMode, ToolDecision
from .errors import ContractError


def _exact_fields(
    value: Mapping[str, Any], required: frozenset[str], context: str
) -> None:
    unknown = set(value) - required
    missing = required - set(value)
    if unknown:
        raise ContractError("contract_unknown_field", f"{context}:{sorted(unknown)}")
    if missing:
        raise ContractError(
            "contract_required_field_missing", f"{context}:{sorted(missing)}"
        )


@dataclass(frozen=True, slots=True)
class ToolAuthorizationRequest:
    agent_role: AgentRole
    tool_id: str
    requested_action: str
    invocation_id: str


@dataclass(frozen=True, slots=True)
class ToolAuthorizationResult:
    decision: ToolDecision
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CitationMismatchProbe:
    claim_id: str
    cited_identifier: str
    cited_title: str
    refetched_identifier: str
    refetched_title: str

    @property
    def is_mismatch(self) -> bool:
        return (
            self.cited_identifier != self.refetched_identifier
            or self.cited_title != self.refetched_title
        )


@dataclass(frozen=True, slots=True)
class FaultFixture:
    fixture_version: str
    institutional_mode: DataMode
    evidence_mode: DataMode
    citation_probe: CitationMismatchProbe
    tool_request: ToolAuthorizationRequest
    expected_safety_invariants: tuple[str, ...]
    expected_outcome: None

    @property
    def citation_mismatch(self) -> bool:
        return self.citation_probe.is_mismatch


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError("contract_type_invalid", field)
    return value


def _uuid(value: Any, field: str) -> str:
    text = _non_empty_string(value, field)
    try:
        return str(UUID(text))
    except ValueError as exc:
        raise ContractError("contract_uuid_invalid", field) from exc


def parse_fault_fixture(value: Mapping[str, Any]) -> FaultFixture:
    required = frozenset(
        {
            "fixture_version",
            "institutional_mode",
            "evidence_mode",
            "citation_probe",
            "tool_request",
            "expected_safety_invariants",
            "expected_outcome",
        }
    )
    _exact_fields(value, required, "fault_fixture")
    request_raw = value["tool_request"]
    if not isinstance(request_raw, Mapping):
        raise ContractError("contract_type_invalid", "tool_request")
    _exact_fields(
        request_raw,
        frozenset({"agent_role", "tool_id", "requested_action", "invocation_id"}),
        "tool_request",
    )
    citation_raw = value["citation_probe"]
    if not isinstance(citation_raw, Mapping):
        raise ContractError("contract_type_invalid", "citation_probe")
    _exact_fields(
        citation_raw,
        frozenset(
            {
                "claim_id",
                "cited_identifier",
                "cited_title",
                "refetched_identifier",
                "refetched_title",
            }
        ),
        "citation_probe",
    )
    try:
        institutional_mode = DataMode(value["institutional_mode"])
        evidence_mode = DataMode(value["evidence_mode"])
        agent_role = AgentRole(request_raw["agent_role"])
    except (TypeError, ValueError) as exc:
        raise ContractError("contract_enum_invalid") from exc
    if institutional_mode is not DataMode.SYNTHETIC:
        raise ContractError("fault_fixture_institutional_mode")
    if evidence_mode is not DataMode.CAPTURED_REPLAY:
        raise ContractError("fault_fixture_evidence_mode")
    fixture_version = _non_empty_string(value["fixture_version"], "fixture_version")
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", fixture_version) is None:
        raise ContractError("contract_semver_invalid", "fixture_version")
    citation_probe = CitationMismatchProbe(
        claim_id=_uuid(citation_raw["claim_id"], "citation_probe.claim_id"),
        cited_identifier=_non_empty_string(
            citation_raw["cited_identifier"], "citation_probe.cited_identifier"
        ),
        cited_title=_non_empty_string(
            citation_raw["cited_title"], "citation_probe.cited_title"
        ),
        refetched_identifier=_non_empty_string(
            citation_raw["refetched_identifier"],
            "citation_probe.refetched_identifier",
        ),
        refetched_title=_non_empty_string(
            citation_raw["refetched_title"], "citation_probe.refetched_title"
        ),
    )
    if not citation_probe.is_mismatch:
        raise ContractError("fault_fixture_citation_mismatch_required")
    if value["expected_outcome"] is not None:
        raise ContractError("fault_fixture_outcome_preset")
    invariants = value["expected_safety_invariants"]
    if (
        not isinstance(invariants, list)
        or not invariants
        or any(not isinstance(item, str) or not item for item in invariants)
        or invariants != sorted(set(invariants))
    ):
        raise ContractError("contract_type_invalid", "expected_safety_invariants")
    return FaultFixture(
        fixture_version=fixture_version,
        institutional_mode=institutional_mode,
        evidence_mode=evidence_mode,
        citation_probe=citation_probe,
        tool_request=ToolAuthorizationRequest(
            agent_role=agent_role,
            tool_id=_non_empty_string(request_raw["tool_id"], "tool_request.tool_id"),
            requested_action=_non_empty_string(
                request_raw["requested_action"], "tool_request.requested_action"
            ),
            invocation_id=_uuid(
                request_raw["invocation_id"], "tool_request.invocation_id"
            ),
        ),
        expected_safety_invariants=tuple(invariants),
        expected_outcome=None,
    )


def authorize_tool_request(
    request: ToolAuthorizationRequest,
    allowed_actions: Iterable[tuple[AgentRole, str, str]],
) -> ToolAuthorizationResult:
    allowed = frozenset(allowed_actions)
    key = (request.agent_role, request.tool_id, request.requested_action)
    if key in allowed:
        return ToolAuthorizationResult(ToolDecision.ALLOWED, ())
    return ToolAuthorizationResult(
        ToolDecision.DENIED, ("tool_not_allowlisted",)
    )
