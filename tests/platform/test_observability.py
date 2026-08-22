from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from recall.contracts.canonical import content_hash
from recall.platform.errors import PlatformError
from recall.platform.observability import (
    MANAGED_PATH_RECEIPT_FIELDS,
    ComponentState,
    ComponentStatus,
    ManagedStatus,
    aggregate_managed_status,
    managed_path_receipt,
    new_span_id,
    new_trace_id,
    parse_traceparent,
    read_back_trace,
    traceparent,
)
from recall.platform.receipts import COMMON_FIELDS

ARTIFACT_ID = "4f1a2b3c-0000-4000-8000-000000000004"
TRACE_ID = "0af7651916cd43dd8448eb211c80319c"


def _observed(component: str) -> ComponentStatus:
    return ComponentStatus(component, ComponentState.OBSERVED, None)


def test_no_component_is_unavailable_not_healthy() -> None:
    status, reasons = aggregate_managed_status([])
    assert status is ManagedStatus.UNAVAILABLE
    assert reasons == ("managed_path_no_component_observed",)


def test_all_observed_is_managed() -> None:
    status, reasons = aggregate_managed_status(
        [_observed("agent-runtime"), _observed("model-armor")]
    )
    assert status is ManagedStatus.MANAGED
    assert reasons == ()


def test_one_degraded_component_degrades_the_path() -> None:
    status, reasons = aggregate_managed_status(
        [
            _observed("agent-runtime"),
            ComponentStatus("model-armor", ComponentState.DEGRADED, "armor_call_failed"),
        ]
    )
    assert status is ManagedStatus.DEGRADED
    assert reasons == ("armor_call_failed", "managed_path_component_degraded")


def test_unavailable_outranks_degraded() -> None:
    status, _ = aggregate_managed_status(
        [
            ComponentStatus("model-armor", ComponentState.DEGRADED, "x"),
            ComponentStatus("agent-runtime", ComponentState.UNAVAILABLE, "y"),
        ]
    )
    assert status is ManagedStatus.UNAVAILABLE


def test_traceparent_round_trip() -> None:
    trace_id, span_id = new_trace_id(), new_span_id()
    header = traceparent(trace_id, span_id)
    assert header.startswith("00-")
    assert parse_traceparent(header) == (trace_id, span_id)


@pytest.mark.parametrize(
    "trace_id, span_id, code",
    [
        ("short", "0123456789abcdef", "trace_id_invalid"),
        (TRACE_ID, "short", "span_id_invalid"),
        ("g" * 32, "0123456789abcdef", "trace_id_invalid"),
    ],
)
def test_malformed_trace_identifiers_are_rejected(
    trace_id: str, span_id: str, code: str
) -> None:
    with pytest.raises(PlatformError) as excinfo:
        traceparent(trace_id, span_id)
    assert excinfo.value.code == code


def test_malformed_traceparent_is_rejected() -> None:
    with pytest.raises(PlatformError) as excinfo:
        parse_traceparent("01-abc-def")
    assert excinfo.value.code == "traceparent_malformed"


class FakeTraceClient:
    def __init__(self, payload: Mapping[str, Any] | None) -> None:
        self._payload = payload

    def get_trace(self, trace_id: str) -> Mapping[str, Any]:
        if self._payload is None:
            raise PlatformError("trace_fetch_failed", f"{trace_id}:404")
        return self._payload


def test_trace_with_spans_is_observed() -> None:
    client = FakeTraceClient(
        {"traceId": TRACE_ID, "spans": [{"name": "controller"}, {"name": "runtime"}]}
    )
    result = read_back_trace(client, TRACE_ID)
    assert result["state"] == ComponentState.OBSERVED.value
    assert result["span_count"] == 2
    assert result["span_names"] == ["controller", "runtime"]


def test_trace_without_spans_is_degraded() -> None:
    result = read_back_trace(FakeTraceClient({"traceId": TRACE_ID}), TRACE_ID)
    assert result["state"] == ComponentState.DEGRADED.value
    assert result["reason_code"] == "trace_has_no_spans"


def test_missing_trace_is_unavailable() -> None:
    result = read_back_trace(FakeTraceClient(None), TRACE_ID)
    assert result["state"] == ComponentState.UNAVAILABLE.value
    assert result["reason_code"] == "trace_fetch_failed"
    assert result["span_count"] == 0


def test_managed_receipt_matches_the_contract_field_set() -> None:
    wire = managed_path_receipt(
        artifact_id=ARTIFACT_ID,
        producer_version="0.1.0",
        created_at="2026-08-22T13:05:00Z",
        statuses=[_observed("agent-runtime"), _observed("model-armor")],
        trace_id=TRACE_ID,
    )
    assert set(wire) == COMMON_FIELDS | MANAGED_PATH_RECEIPT_FIELDS
    assert wire["managed_status"] == "MANAGED"
    assert wire["status"] == "VALID"
    assert wire["trace_id"] == TRACE_ID
    assert wire["content_hash"] == content_hash(wire)
    assert wire["producer"]["identity"] == "health-aggregator"


def test_managed_claim_requires_a_trace() -> None:
    with pytest.raises(PlatformError) as excinfo:
        managed_path_receipt(
            artifact_id=ARTIFACT_ID,
            producer_version="0.1.0",
            created_at="2026-08-22T13:05:00Z",
            statuses=[_observed("agent-runtime")],
            trace_id=None,
        )
    assert excinfo.value.code == "managed_path_trace_missing"


def test_degraded_receipt_is_allowed_without_a_trace() -> None:
    wire = managed_path_receipt(
        artifact_id=ARTIFACT_ID,
        producer_version="0.1.0",
        created_at="2026-08-22T13:05:00Z",
        statuses=[ComponentStatus("model-armor", ComponentState.DEGRADED, "boom")],
        trace_id=None,
    )
    assert wire["managed_status"] == "DEGRADED"
    assert wire["status"] == "DEGRADED"
    assert wire["trace_id"] is None


def test_component_statuses_are_sorted() -> None:
    wire = managed_path_receipt(
        artifact_id=ARTIFACT_ID,
        producer_version="0.1.0",
        created_at="2026-08-22T13:05:00Z",
        statuses=[_observed("model-armor"), _observed("agent-runtime")],
        trace_id=TRACE_ID,
    )
    assert [item["component"] for item in wire["component_statuses"]] == [
        "agent-runtime",
        "model-armor",
    ]
