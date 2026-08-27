from __future__ import annotations

import pytest

from recall.contracts import ContractError
from recall.controller.lifecycle import (
    SCAN_RUN_TRANSITIONS,
    ScanRunEventCode,
    ScanRunState,
    transition_target,
)


def test_every_declared_transition_is_accepted() -> None:
    for (from_state, event_code), expected in SCAN_RUN_TRANSITIONS.items():
        assert transition_target(from_state, event_code) is expected


def test_event_enum_and_transition_table_are_bidirectionally_complete() -> None:
    table_codes = {event_code for _, event_code in SCAN_RUN_TRANSITIONS}

    assert table_codes == set(ScanRunEventCode)
    assert (
        transition_target(None, ScanRunEventCode.RUN_CREATED)
        is ScanRunState.CREATED
    )


@pytest.mark.parametrize(
    ("state", "event"),
    [
        (ScanRunState.CREATED, ScanRunEventCode.POLICY_NO_ACTION),
        (ScanRunState.WATCHING, ScanRunEventCode.AUDIT_COMPLETED),
        (ScanRunState.NO_ACTION, ScanRunEventCode.RETRY_SCHEDULED),
        (ScanRunState.ABSTAIN, ScanRunEventCode.TECHNICAL_HALTED),
        (ScanRunState.REVIEW_REQUIRED, ScanRunEventCode.LEASE_TAKEN_OVER),
        (ScanRunState.HALTED, ScanRunEventCode.OUTBOX_PUBLISHED),
    ],
)
def test_unlisted_and_terminal_transitions_are_rejected(
    state: ScanRunState, event: ScanRunEventCode
) -> None:
    with pytest.raises(ContractError, match="contract_transition_invalid"):
        transition_target(state, event)


def test_event_codes_are_closed_enum_values() -> None:
    with pytest.raises(ValueError):
        ScanRunEventCode("free_form_event")


def test_full_audit_transition_is_closed_and_always_enters_assessment() -> None:
    assert (
        transition_target(
            ScanRunState.WATCHING, ScanRunEventCode.FULL_AUDIT_REQUIRED
        )
        is ScanRunState.ASSESSING
    )
