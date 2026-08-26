from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ..enums import (
    AgentRole,
    DataComposition,
    DataMode,
    FactState,
    FailureTerminal,
    ToolDecision,
)
from ..errors import ContractError
from ..failure_registry import FailureCode
from ..validation import (
    SEMVER,
    SHA256,
    enum_value,
    non_empty_string,
    require_exact_fields,
    tuple_of_strings,
    uuid_value,
)
from .evidence import CandidateDeltaPayload, EvidenceSnapshotPayload
from .lifecycle import (
    ReviewTaskPayload,
    ScanRunEventPayload,
    ScanRunPayload,
    WatchCasePayload,
)
from .policy import PolicyDecisionPayload
from .receipts import (
    AssessmentReceiptPayload,
    CitationAuditPayload,
    PrivacyReceiptPayload,
    RegistryResolutionPayload,
)
from .agentic import (
    DeploymentReceiptPayload,
    EvidenceDeltaPayload,
    EvidenceObservationPayload,
    ManagedPathReceiptPayload,
    RoutingPlanPayload,
)
from .scheduler import CohortDayManifestPayload
from .scheduler_v3 import CohortDayManifestV3Payload
from .scheduler_legacy import CohortDayManifestV20Payload
from .cohort_failure import CohortDayFailureReceiptPayload
from .cohort_history import CohortHistoryReceiptPayload
from .compressed_receipts import (
    CohortHeadroomReceiptPayload,
    CompressedCycleFailureReceiptPayload,
)


@dataclass(frozen=True, slots=True)
class ToolAuthorizationPayload:
    agent_role: AgentRole
    tool_id: str
    requested_action: str
    decision: ToolDecision
    policy_version: str
    reason_codes: tuple[str, ...]
    invocation_id: str

    def to_wire(self) -> dict[str, object]:
        return {
            "agent_role": self.agent_role.value,
            "tool_id": self.tool_id,
            "requested_action": self.requested_action,
            "decision": self.decision.value,
            "policy_version": self.policy_version,
            "reason_codes": list(self.reason_codes),
            "invocation_id": self.invocation_id,
        }


@dataclass(frozen=True, slots=True)
class DataModePayload:
    subject_artifact_ids: tuple[str, ...]
    mode_set: tuple[DataMode, ...]
    declared_composition: DataComposition
    propagation_status: FactState
    reason_codes: tuple[str, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "subject_artifact_ids": list(self.subject_artifact_ids),
            "mode_set": [mode.value for mode in self.mode_set],
            "declared_composition": self.declared_composition.value,
            "propagation_status": self.propagation_status.value,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class FailurePayload:
    failure_code: FailureCode
    stage: str
    retryable: bool
    attempt: int
    budget_state: str
    details: Mapping[str, object]
    related_artifact_ids: tuple[str, ...]
    safe_terminal: FailureTerminal
    operator_action: str

    def to_wire(self) -> dict[str, object]:
        return {
            "failure_code": self.failure_code.value,
            "stage": self.stage,
            "retryable": self.retryable,
            "attempt": self.attempt,
            "budget_state": self.budget_state,
            "details": dict(self.details),
            "related_artifact_ids": list(self.related_artifact_ids),
            "safe_terminal": self.safe_terminal.value,
            "operator_action": self.operator_action,
        }


Payload = (
    ToolAuthorizationPayload
    | DataModePayload
    | FailurePayload
    | ScanRunPayload
    | ReviewTaskPayload
    | PolicyDecisionPayload
    | ScanRunEventPayload
    | WatchCasePayload
    | EvidenceSnapshotPayload
    | CandidateDeltaPayload
    | PrivacyReceiptPayload
    | RegistryResolutionPayload
    | AssessmentReceiptPayload
    | CitationAuditPayload
    | RoutingPlanPayload
    | EvidenceObservationPayload
    | EvidenceDeltaPayload
    | DeploymentReceiptPayload
    | ManagedPathReceiptPayload
    | CohortDayManifestPayload
    | CohortDayManifestV3Payload
    | CohortDayManifestV20Payload
    | CohortDayFailureReceiptPayload
    | CohortHistoryReceiptPayload
    | CohortHeadroomReceiptPayload
    | CompressedCycleFailureReceiptPayload
)


def parse_tool_authorization_payload(
    value: Mapping[str, Any],
) -> ToolAuthorizationPayload:
    reason_codes = tuple_of_strings(value["reason_codes"], "reason_codes")
    decision = enum_value(ToolDecision, value["decision"], "decision")
    if decision is ToolDecision.DENIED and not reason_codes:
        raise ContractError("contract_required_value_missing", "reason_codes")
    policy_version = non_empty_string(value["policy_version"], "policy_version")
    if not SEMVER.fullmatch(policy_version):
        raise ContractError("contract_semver_invalid", "policy_version")
    return ToolAuthorizationPayload(
        agent_role=enum_value(AgentRole, value["agent_role"], "agent_role"),
        tool_id=non_empty_string(value["tool_id"], "tool_id"),
        requested_action=non_empty_string(
            value["requested_action"], "requested_action"
        ),
        decision=decision,
        policy_version=policy_version,
        reason_codes=reason_codes,
        invocation_id=str(uuid_value(value["invocation_id"], "invocation_id")),
    )


def _expected_composition(modes: tuple[DataMode, ...]) -> DataComposition:
    projections = {
        (DataMode.SYNTHETIC,): DataComposition.SYNTHETIC_ONLY,
        (DataMode.CAPTURED_REPLAY,): DataComposition.CAPTURED_REPLAY_ONLY,
        (DataMode.LIVE_PUBLIC,): DataComposition.LIVE_PUBLIC_ONLY,
        (DataMode.MOCK,): DataComposition.MOCK_ONLY,
        (
            DataMode.CAPTURED_REPLAY,
            DataMode.SYNTHETIC,
        ): DataComposition.SYNTHETIC_WITH_CAPTURED_REPLAY,
    }
    try:
        return projections[modes]
    except KeyError as exc:
        raise ContractError("data_mode_conflict") from exc


def parse_data_mode_payload(value: Mapping[str, Any]) -> DataModePayload:
    subjects = tuple_of_strings(value["subject_artifact_ids"], "subject_artifact_ids")
    if not subjects:
        raise ContractError("contract_required_value_missing", "subject_artifact_ids")
    for artifact_id in subjects:
        uuid_value(artifact_id, "subject_artifact_ids")
    raw_modes = value["mode_set"]
    if not isinstance(raw_modes, list):
        raise ContractError("contract_type_invalid", "mode_set")
    modes = tuple(enum_value(DataMode, mode, "mode_set") for mode in raw_modes)
    if not modes or modes != tuple(sorted(set(modes), key=lambda mode: mode.value)):
        raise ContractError("contract_order_or_uniqueness_invalid", "mode_set")
    expected = _expected_composition(modes)
    declared = enum_value(
        DataComposition, value["declared_composition"], "declared_composition"
    )
    if declared is not expected:
        raise ContractError("data_mode_conflict", "declared_composition")
    return DataModePayload(
        subject_artifact_ids=subjects,
        mode_set=modes,
        declared_composition=declared,
        propagation_status=enum_value(
            FactState, value["propagation_status"], "propagation_status"
        ),
        reason_codes=tuple_of_strings(value["reason_codes"], "reason_codes"),
    )


_HALTED_CODES = frozenset(
    {
        FailureCode.POLICY_UNAVAILABLE,
        FailureCode.LEDGER_INTEGRITY_FAILED,
        FailureCode.CONTROLLER_FAILED,
    }
)


def _parse_failure_details(
    code: FailureCode, raw: Any
) -> Mapping[str, object]:
    if not isinstance(raw, Mapping):
        raise ContractError("contract_type_invalid", "details")
    if code is FailureCode.LOOP_DETECTED:
        require_exact_fields(
            raw, frozenset({"hop_count", "repeated_state_hash"}), "details"
        )
        hop_count = raw["hop_count"]
        state_hash = raw["repeated_state_hash"]
        if isinstance(hop_count, bool) or not isinstance(hop_count, int) or hop_count < 1:
            raise ContractError("contract_type_invalid", "details.hop_count")
        if not isinstance(state_hash, str) or not SHA256.fullmatch(state_hash):
            raise ContractError(
                "contract_hash_invalid", "details.repeated_state_hash"
            )
    elif code is FailureCode.SOURCE_UNAVAILABLE:
        require_exact_fields(raw, frozenset({"source", "attempts"}), "details")
        non_empty_string(raw["source"], "details.source")
        attempts = raw["attempts"]
        if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
            raise ContractError("contract_type_invalid", "details.attempts")
    elif raw:
        raise ContractError("contract_unknown_field", f"details:{sorted(raw)}")
    return MappingProxyType(dict(raw))


def parse_failure_payload(value: Mapping[str, Any]) -> FailurePayload:
    code = enum_value(FailureCode, value["failure_code"], "failure_code")
    terminal = enum_value(FailureTerminal, value["safe_terminal"], "safe_terminal")
    if (code in _HALTED_CODES) is not (terminal is FailureTerminal.HALTED):
        raise ContractError("contract_value_invalid", "safe_terminal")
    related = tuple_of_strings(value["related_artifact_ids"], "related_artifact_ids")
    for artifact_id in related:
        uuid_value(artifact_id, "related_artifact_ids")
    retryable = value["retryable"]
    attempt = value["attempt"]
    if not isinstance(retryable, bool):
        raise ContractError("contract_type_invalid", "retryable")
    if retryable is not (terminal is FailureTerminal.RETRY):
        raise ContractError("contract_value_invalid", "retryable")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ContractError("contract_type_invalid", "attempt")
    return FailurePayload(
        failure_code=code,
        stage=non_empty_string(value["stage"], "stage"),
        retryable=retryable,
        attempt=attempt,
        budget_state=non_empty_string(value["budget_state"], "budget_state"),
        details=_parse_failure_details(code, value["details"]),
        related_artifact_ids=related,
        safe_terminal=terminal,
        operator_action=non_empty_string(value["operator_action"], "operator_action"),
    )
