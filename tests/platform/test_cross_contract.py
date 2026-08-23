from __future__ import annotations

import uuid
from typing import Any

import pytest

from cross_contract import (
    ContractExpectation,
    check_against_versions,
    check_producer_against_contract,
    local_contract,
    payload_fields_of,
    registered_as,
)
from recall.contracts.enums import FactState
from recall.contracts.schemas import SCHEMAS
from recall.platform.registry import (
    REGISTRY_RESOLUTION,
    ResolutionMode,
    build_registry_resolution_receipt,
    resolve_capabilities,
)

REGION = "us-central1"
CATALOG: dict[str, dict[str, Any]] = {
    "evidence.watch": {
        "agent_id": "recall-watcher",
        "role": "EVIDENCE_WATCHER",
        "revision": "2026-08-23T09:00:00Z",
        "binding_id": "binding-watcher-1",
        "region": REGION,
    }
}

# Read from feature/rcl-3xx-core:src/recall/contracts/schemas.py on 2026-08-23.
CORE_1_1_0 = ContractExpectation(
    "1.1.0",
    {
        "requested_capabilities",
        "bindings",
        "resolution_mode",
        "validation_status",
        "reason_codes",
    },
)
# The version this lane carried before the contract moved.
LANE_1_0_0 = ContractExpectation(
    "1.0.0",
    {"requested_capabilities", "bindings", "validation_status", "reason_codes"},
)


def _produce() -> dict[str, Any]:
    resolution = resolve_capabilities(
        list(CATALOG),
        CATALOG,
        resolution_mode=ResolutionMode.REGISTRY,
        region=REGION,
    )
    return build_registry_resolution_receipt(
        resolution,
        artifact_id=str(uuid.uuid4()),
        run_id=str(uuid.uuid4()),
        case_id=None,
        producer_version="0.1.0",
        created_at="2026-08-23T11:00:00Z",
    )


def test_the_registry_producer_satisfies_the_core_contract() -> None:
    result = check_producer_against_contract(_produce, REGISTRY_RESOLUTION, CORE_1_1_0)
    assert result.ok, result.summary()
    assert result.emitted_version == "1.1.0"
    assert result.missing_fields == ()
    assert result.unexpected_fields == ()


def test_the_registry_producer_also_satisfies_the_older_contract() -> None:
    result = check_producer_against_contract(_produce, REGISTRY_RESOLUTION, LANE_1_0_0)
    assert result.ok, result.summary()
    assert result.emitted_version == "1.0.0"


def test_one_producer_checked_against_both_versions_at_once() -> None:
    results = check_against_versions(
        _produce, REGISTRY_RESOLUTION, [LANE_1_0_0, CORE_1_1_0]
    )
    assert [r.expected_version for r in results] == ["1.0.0", "1.1.0"]
    assert all(r.ok for r in results), [r.summary() for r in results]


def test_a_hardcoded_producer_is_caught_against_the_newer_contract() -> None:
    """The failure that was reverted: a producer pinned to the old version."""

    def _stale_producer() -> dict[str, Any]:
        wire = _produce()
        return {**wire, "schema_version": "1.0.0"}

    result = check_producer_against_contract(
        _stale_producer, REGISTRY_RESOLUTION, CORE_1_1_0
    )
    assert result.ok is False
    assert result.emitted_version == "1.0.0"
    assert result.error_code == "contract_major_unsupported"
    assert "emitted version 1.0.0" in result.summary()


def test_a_missing_payload_field_is_named() -> None:
    def _without_mode() -> dict[str, Any]:
        wire = _produce()
        wire.pop("resolution_mode", None)
        return wire

    result = check_producer_against_contract(
        _without_mode, REGISTRY_RESOLUTION, CORE_1_1_0
    )
    assert result.ok is False
    assert result.missing_fields == ("resolution_mode",)
    assert "missing ['resolution_mode']" in result.summary()


def test_an_extra_payload_field_is_named() -> None:
    def _with_extra() -> dict[str, Any]:
        return {**_produce(), "invented_field": "x"}

    result = check_producer_against_contract(
        _with_extra, REGISTRY_RESOLUTION, CORE_1_1_0
    )
    assert result.ok is False
    assert result.unexpected_fields == ("invented_field",)


def test_a_raising_producer_is_reported_not_swallowed() -> None:
    def _boom() -> dict[str, Any]:
        raise RuntimeError("producer exploded")

    result = check_producer_against_contract(_boom, REGISTRY_RESOLUTION, CORE_1_1_0)
    assert result.ok is False
    assert result.error_code == "RuntimeError"
    assert result.emitted_version is None


def test_the_registry_is_restored_after_a_check() -> None:
    before = SCHEMAS[REGISTRY_RESOLUTION]
    check_producer_against_contract(_produce, REGISTRY_RESOLUTION, CORE_1_1_0)
    assert SCHEMAS[REGISTRY_RESOLUTION] == before


def test_the_registry_is_restored_even_when_the_producer_raises() -> None:
    before = SCHEMAS[REGISTRY_RESOLUTION]

    def _boom() -> dict[str, Any]:
        raise RuntimeError("boom")

    check_producer_against_contract(_boom, REGISTRY_RESOLUTION, CORE_1_1_0)
    assert SCHEMAS[REGISTRY_RESOLUTION] == before


def test_registered_as_removes_a_schema_it_invented() -> None:
    name = "NotARegisteredContract"
    assert name not in SCHEMAS
    with registered_as(name, CORE_1_1_0):
        assert SCHEMAS[name][0] == "1.1.0"
    assert name not in SCHEMAS


def test_local_contract_reads_what_this_checkout_registers() -> None:
    expectation = local_contract(REGISTRY_RESOLUTION)
    version, fields, _parser, run_required = SCHEMAS[REGISTRY_RESOLUTION]
    assert expectation.version == version
    assert expectation.payload_fields == frozenset(fields)
    assert expectation.run_required == run_required


def test_payload_fields_exclude_the_common_envelope() -> None:
    fields = payload_fields_of(_produce())
    assert "schema_name" not in fields
    assert "content_hash" not in fields
    assert "bindings" in fields


@pytest.mark.parametrize("mode", list(ResolutionMode))
def test_every_resolution_mode_satisfies_the_core_contract(mode: Any) -> None:
    def _with_mode() -> dict[str, Any]:
        resolution = resolve_capabilities(
            list(CATALOG), CATALOG, resolution_mode=mode, region=REGION
        )
        assert resolution.validation_status is FactState.PASS
        return build_registry_resolution_receipt(
            resolution,
            artifact_id=str(uuid.uuid4()),
            run_id=str(uuid.uuid4()),
            case_id=None,
            producer_version="0.1.0",
            created_at="2026-08-23T11:00:00Z",
        )

    result = check_producer_against_contract(
        _with_mode, REGISTRY_RESOLUTION, CORE_1_1_0
    )
    assert result.ok, result.summary()
