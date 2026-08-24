from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import re
from threading import RLock
from typing import Any, Protocol

from google.cloud import firestore
from google.cloud.firestore_v1.base_client import BaseClient


_COLLECTION = re.compile(r"^[a-z][a-z0-9_]{2,79}$")


@dataclass(frozen=True, slots=True)
class GatewayResponse:
    status_code: int
    body: dict[str, object]


@dataclass(frozen=True, slots=True)
class GatewayReservation:
    state: str
    created_at: datetime
    response: GatewayResponse | None = None


class GatewayInvocationStore(Protocol):
    def reserve(
        self,
        request_id: str,
        request_hash: str,
        *,
        now: datetime,
    ) -> GatewayReservation: ...

    def complete(
        self,
        request_id: str,
        request_hash: str,
        response: GatewayResponse,
    ) -> None: ...


class InMemoryGatewayInvocationStore:
    def __init__(self) -> None:
        self._records: dict[str, dict[str, object]] = {}
        self._lock = RLock()

    def reserve(
        self,
        request_id: str,
        request_hash: str,
        *,
        now: datetime,
    ) -> GatewayReservation:
        with self._lock:
            existing = self._records.get(request_id)
            if existing is None:
                self._records[request_id] = {
                    "request_hash": request_hash,
                    "created_at": now,
                    "response": None,
                }
                return GatewayReservation("NEW", now)
            if existing["request_hash"] != request_hash:
                raise ValueError("gateway_request_id_reused")
            response = existing["response"]
            if response is None:
                return GatewayReservation(
                    "PENDING", existing["created_at"]  # type: ignore[arg-type]
                )
            return GatewayReservation(
                "COMPLETE",
                existing["created_at"],  # type: ignore[arg-type]
                deepcopy(response),  # type: ignore[arg-type]
            )

    def complete(
        self,
        request_id: str,
        request_hash: str,
        response: GatewayResponse,
    ) -> None:
        with self._lock:
            existing = self._records.get(request_id)
            if existing is None or existing["request_hash"] != request_hash:
                raise ValueError("gateway_reservation_missing")
            current = existing["response"]
            if current is not None and current != response:
                raise ValueError("gateway_response_integrity_failed")
            existing["response"] = deepcopy(response)


class FirestoreGatewayInvocationStore:
    """Transactional cache that prevents normal HTTP retries re-running tools."""

    def __init__(
        self,
        client: BaseClient,
        *,
        collection_name: str = "tool_gateway_invocations",
    ) -> None:
        if not _COLLECTION.fullmatch(collection_name):
            raise ValueError("gateway_store_collection_invalid")
        self._client = client
        self._collection = client.collection(collection_name)

    def reserve(
        self,
        request_id: str,
        request_hash: str,
        *,
        now: datetime,
    ) -> GatewayReservation:
        reference = self._collection.document(request_id)
        transaction = self._client.transaction()

        @firestore.transactional
        def reserve_once(txn: Any) -> GatewayReservation:
            snapshot = reference.get(transaction=txn)
            if not snapshot.exists:
                txn.create(
                    reference,
                    {
                        "request_hash": request_hash,
                        "created_at": now,
                        "state": "PENDING",
                        "status_code": None,
                        "response_body": None,
                    },
                )
                return GatewayReservation("NEW", now)
            value = snapshot.to_dict()
            if value.get("request_hash") != request_hash:
                raise ValueError("gateway_request_id_reused")
            created_at = value.get("created_at")
            if not isinstance(created_at, datetime):
                raise ValueError("gateway_store_record_invalid")
            state = value.get("state")
            if state == "PENDING":
                return GatewayReservation("PENDING", created_at)
            if state != "COMPLETE":
                raise ValueError("gateway_store_record_invalid")
            status = value.get("status_code")
            body = value.get("response_body")
            if not isinstance(status, int) or not isinstance(body, dict):
                raise ValueError("gateway_store_record_invalid")
            return GatewayReservation(
                "COMPLETE", created_at, GatewayResponse(status, body)
            )

        return reserve_once(transaction)

    def complete(
        self,
        request_id: str,
        request_hash: str,
        response: GatewayResponse,
    ) -> None:
        reference = self._collection.document(request_id)
        transaction = self._client.transaction()

        @firestore.transactional
        def complete_once(txn: Any) -> None:
            snapshot = reference.get(transaction=txn)
            if not snapshot.exists:
                raise ValueError("gateway_reservation_missing")
            value = snapshot.to_dict()
            if value.get("request_hash") != request_hash:
                raise ValueError("gateway_reservation_missing")
            state = value.get("state")
            if state == "COMPLETE":
                if (
                    value.get("status_code") != response.status_code
                    or value.get("response_body") != response.body
                ):
                    raise ValueError("gateway_response_integrity_failed")
                return
            if state != "PENDING":
                raise ValueError("gateway_store_record_invalid")
            txn.update(
                reference,
                {
                    "state": "COMPLETE",
                    "status_code": response.status_code,
                    "response_body": response.body,
                },
            )

        complete_once(transaction)
