from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from recall.controller import tool_gateway_store
from recall.controller.tool_gateway_store import (
    FirestoreGatewayInvocationStore,
    GatewayResponse,
)


NOW = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)


class FakeSnapshot:
    def __init__(self, value: dict[str, object] | None) -> None:
        self.exists = value is not None
        self._value = value

    def to_dict(self) -> dict[str, object]:
        assert self._value is not None
        return dict(self._value)


class FakeReference:
    def __init__(self, records: dict[str, dict[str, object]], key: str) -> None:
        self.records = records
        self.key = key

    def get(self, *, transaction: object) -> FakeSnapshot:
        return FakeSnapshot(self.records.get(self.key))


class FakeTransaction:
    def create(self, reference: FakeReference, value: dict[str, object]) -> None:
        if reference.key in reference.records:
            raise AssertionError("duplicate create")
        reference.records[reference.key] = dict(value)

    def update(self, reference: FakeReference, value: dict[str, object]) -> None:
        reference.records[reference.key].update(value)


class FakeCollection:
    def __init__(self, records: dict[str, dict[str, object]]) -> None:
        self.records = records

    def document(self, key: str) -> FakeReference:
        return FakeReference(self.records, key)


class FakeClient:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, object]] = {}

    def collection(self, _name: str) -> FakeCollection:
        return FakeCollection(self.records)

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()


@pytest.fixture(autouse=True)
def direct_transactions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tool_gateway_store.firestore,
        "transactional",
        lambda function: lambda transaction: function(transaction),
    )


def test_firestore_store_reserve_complete_and_cached_retry() -> None:
    client = FakeClient()
    store = FirestoreGatewayInvocationStore(client)  # type: ignore[arg-type]
    first = store.reserve("request-1", "a" * 64, now=NOW)
    assert first.state == "NEW"
    pending = store.reserve("request-1", "a" * 64, now=NOW)
    assert pending.state == "PENDING"
    response = GatewayResponse(200, {"result": {"ok": True}})
    store.complete("request-1", "a" * 64, response)
    cached = store.reserve("request-1", "a" * 64, now=NOW)
    assert cached.state == "COMPLETE"
    assert cached.response == response
    store.complete("request-1", "a" * 64, response)


def test_firestore_store_rejects_hash_collision_and_response_change() -> None:
    client = FakeClient()
    store = FirestoreGatewayInvocationStore(client)  # type: ignore[arg-type]
    store.reserve("request-1", "a" * 64, now=NOW)
    with pytest.raises(ValueError, match="gateway_request_id_reused"):
        store.reserve("request-1", "b" * 64, now=NOW)
    store.complete("request-1", "a" * 64, GatewayResponse(200, {"ok": True}))
    with pytest.raises(ValueError, match="gateway_response_integrity_failed"):
        store.complete("request-1", "a" * 64, GatewayResponse(500, {"ok": False}))


def test_firestore_store_rejects_corrupt_state() -> None:
    client = FakeClient()
    store = FirestoreGatewayInvocationStore(client)  # type: ignore[arg-type]
    store.reserve("request-1", "a" * 64, now=NOW)
    client.records["request-1"]["state"] = "CORRUPT"
    with pytest.raises(ValueError, match="gateway_store_record_invalid"):
        store.reserve("request-1", "a" * 64, now=NOW)
    with pytest.raises(ValueError, match="gateway_store_record_invalid"):
        store.complete("request-1", "a" * 64, GatewayResponse(200, {}))
