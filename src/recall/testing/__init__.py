"""Checks a lane runs against its own output before integration.

Contract conformance is part of the product, not a lane's private test detail:
an artifact that the Ledger's parser rejects is a defect wherever it is built.
These helpers live in the package so every lane imports them the same way, with
no path configuration and no dependence on test collection order.
"""

from .cross_contract import (
    ContractExpectation,
    CrossContractResult,
    check_against_versions,
    check_producer_against_contract,
    local_contract,
    payload_fields_of,
    registered_as,
)

__all__ = [
    "ContractExpectation",
    "CrossContractResult",
    "check_against_versions",
    "check_producer_against_contract",
    "local_contract",
    "payload_fields_of",
    "registered_as",
]
