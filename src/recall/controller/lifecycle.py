from __future__ import annotations

from types import MappingProxyType

from recall.contracts.enums import ScanRunEventCode, ScanRunState
from recall.contracts.errors import ContractError


_TRANSITIONS: dict[
    tuple[ScanRunState | None, ScanRunEventCode], ScanRunState
] = {
    (None, ScanRunEventCode.RUN_CREATED): ScanRunState.CREATED,
    (ScanRunState.CREATED, ScanRunEventCode.OUTBOX_PUBLISHED): ScanRunState.QUEUED,
    (ScanRunState.QUEUED, ScanRunEventCode.LEASE_ACQUIRED): ScanRunState.ROUTING,
    (ScanRunState.ROUTING, ScanRunEventCode.ROUTE_VALIDATED): ScanRunState.WATCHING,
    (
        ScanRunState.ROUTING,
        ScanRunEventCode.PREREQUISITE_FAILED,
    ): ScanRunState.POLICY_EVALUATION,
    (
        ScanRunState.WATCHING,
        ScanRunEventCode.CANDIDATE_ABSENT,
    ): ScanRunState.POLICY_EVALUATION,
    (
        ScanRunState.WATCHING,
        ScanRunEventCode.CANDIDATE_UNKNOWN,
    ): ScanRunState.POLICY_EVALUATION,
    (
        ScanRunState.WATCHING,
        ScanRunEventCode.CANDIDATE_PRESENT,
    ): ScanRunState.ASSESSING,
    (
        ScanRunState.WATCHING,
        ScanRunEventCode.FULL_AUDIT_REQUIRED,
    ): ScanRunState.ASSESSING,
    (
        ScanRunState.WATCHING,
        ScanRunEventCode.PREREQUISITE_FAILED,
    ): ScanRunState.POLICY_EVALUATION,
    (
        ScanRunState.ASSESSING,
        ScanRunEventCode.ASSESSMENT_COMPLETED,
    ): ScanRunState.AUDITING,
    (
        ScanRunState.ASSESSING,
        ScanRunEventCode.PREREQUISITE_FAILED,
    ): ScanRunState.POLICY_EVALUATION,
    (
        ScanRunState.AUDITING,
        ScanRunEventCode.AUDIT_COMPLETED,
    ): ScanRunState.POLICY_EVALUATION,
    (
        ScanRunState.AUDITING,
        ScanRunEventCode.PREREQUISITE_FAILED,
    ): ScanRunState.POLICY_EVALUATION,
    (
        ScanRunState.POLICY_EVALUATION,
        ScanRunEventCode.POLICY_NO_ACTION,
    ): ScanRunState.NO_ACTION,
    (
        ScanRunState.POLICY_EVALUATION,
        ScanRunEventCode.POLICY_ABSTAIN,
    ): ScanRunState.ABSTAIN,
    (
        ScanRunState.POLICY_EVALUATION,
        ScanRunEventCode.POLICY_REVIEW_REQUIRED,
    ): ScanRunState.REVIEW_REQUIRED,
}

_NONTERMINAL = frozenset(
    {
        ScanRunState.CREATED,
        ScanRunState.QUEUED,
        ScanRunState.ROUTING,
        ScanRunState.WATCHING,
        ScanRunState.ASSESSING,
        ScanRunState.AUDITING,
        ScanRunState.POLICY_EVALUATION,
    }
)
for state in _NONTERMINAL:
    _TRANSITIONS[(state, ScanRunEventCode.RETRY_SCHEDULED)] = state
    _TRANSITIONS[(state, ScanRunEventCode.STATE_HASH_OBSERVED)] = state
    _TRANSITIONS[(state, ScanRunEventCode.TECHNICAL_HALTED)] = ScanRunState.HALTED
    _TRANSITIONS[(state, ScanRunEventCode.LOOP_DETECTED)] = (
        ScanRunState.POLICY_EVALUATION
    )
for state in _NONTERMINAL - {ScanRunState.CREATED}:
    _TRANSITIONS[(state, ScanRunEventCode.LEASE_TAKEN_OVER)] = state

SCAN_RUN_TRANSITIONS = MappingProxyType(_TRANSITIONS)


def transition_target(
    from_state: ScanRunState | None, event_code: ScanRunEventCode
) -> ScanRunState:
    try:
        return SCAN_RUN_TRANSITIONS[(from_state, event_code)]
    except KeyError as exc:
        raise ContractError(
            "contract_transition_invalid",
            f"{'none' if from_state is None else from_state.value}:{event_code.value}",
        ) from exc


def require_transition(
    from_state: ScanRunState | None,
    event_code: ScanRunEventCode,
    target_state: ScanRunState,
) -> None:
    if transition_target(from_state, event_code) is not target_state:
        source = "none" if from_state is None else from_state.value
        raise ContractError(
            "contract_transition_invalid",
            f"{source}:{event_code.value}:{target_state.value}",
        )
