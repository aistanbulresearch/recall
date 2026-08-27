from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from threading import RLock
from typing import Any, Protocol

from google.cloud import firestore
from google.cloud.firestore_v1.base_client import BaseClient

from recall.contracts import canonical_json_bytes


@dataclass(frozen=True, slots=True)
class ModelCostPolicy:
    model_id: str
    location: str
    price_source: str
    price_effective_date: str
    input_usd_micros_per_million_tokens: int
    output_usd_micros_per_million_tokens: int
    max_request_bytes_per_turn: int
    max_output_tokens_per_turn: int
    hard_cap_usd_micros: int
    sha256: str


_POLICY_WIRE = {
    "schema_version": "1.0.0",
    "model_id": "gemini-3.7-flash",
    "location": "global",
    "price_source": "Google Cloud Vertex AI pricing",
    "price_effective_date": "2026-08-27",
    "input_usd_micros_per_million_tokens": 750_000,
    "output_usd_micros_per_million_tokens": 3_750_000,
    "max_request_bytes_per_turn": 16_384,
    "max_output_tokens_per_turn": 2_048,
    "hard_cap_usd_micros": 75_000_000,
}


def _policy() -> ModelCostPolicy:
    from hashlib import sha256

    fields = {key: value for key, value in _POLICY_WIRE.items() if key != "schema_version"}
    return ModelCostPolicy(
        **fields,
        sha256=sha256(canonical_json_bytes(_POLICY_WIRE)).hexdigest(),
    )


DEFAULT_MODEL_COST_POLICY = _policy()


@dataclass(frozen=True, slots=True)
class CostReservation:
    state: str
    reservation_id: str
    reserved_usd_micros: int


@dataclass(frozen=True, slots=True)
class CostSnapshot:
    reserved_usd_micros: int
    reconciled_usd_micros: int


class ModelCostLedger(Protocol):
    def reserve(
        self, reservation_id: str, worst_case_usd_micros: int
    ) -> CostReservation: ...

    def reconcile(
        self, reservation_id: str, *, actual_usd_micros: int
    ) -> None: ...

    def snapshot(self) -> CostSnapshot: ...


def validate_request_budget(payload: bytes, policy: ModelCostPolicy) -> None:
    if len(payload) > policy.max_request_bytes_per_turn:
        raise RuntimeError("model_request_budget_exceeded")


def projected_cost_micros(
    *,
    prompt_tokens: int,
    candidate_tokens: int,
    thoughts_tokens: int,
    policy: ModelCostPolicy,
) -> int:
    if min(prompt_tokens, candidate_tokens, thoughts_tokens) < 0:
        raise ValueError("model_token_count_invalid")
    return ceil(
        prompt_tokens
        * policy.input_usd_micros_per_million_tokens
        / 1_000_000
    ) + ceil(
        (candidate_tokens + thoughts_tokens)
        * policy.output_usd_micros_per_million_tokens
        / 1_000_000
    )


def worst_case_turn_cost_micros(policy: ModelCostPolicy) -> int:
    return projected_cost_micros(
        prompt_tokens=policy.max_request_bytes_per_turn,
        candidate_tokens=policy.max_output_tokens_per_turn,
        thoughts_tokens=0,
        policy=policy,
    )


class InMemoryModelCostLedger:
    def __init__(self, *, hard_cap_usd_micros: int) -> None:
        self._cap = hard_cap_usd_micros
        self._records: dict[str, tuple[int, int | None]] = {}
        self._lock = RLock()

    def reserve(
        self, reservation_id: str, worst_case_usd_micros: int
    ) -> CostReservation:
        _positive(worst_case_usd_micros)
        with self._lock:
            existing = self._records.get(reservation_id)
            if existing is not None:
                if existing[0] != worst_case_usd_micros:
                    raise ValueError("model_cost_reservation_integrity_failed")
                return CostReservation(
                    "RESERVED", reservation_id, existing[0]
                )
            if self._exposure() + worst_case_usd_micros > self._cap:
                return CostReservation("DENIED", reservation_id, 0)
            self._records[reservation_id] = (worst_case_usd_micros, None)
            return CostReservation(
                "RESERVED", reservation_id, worst_case_usd_micros
            )

    def reconcile(
        self, reservation_id: str, *, actual_usd_micros: int
    ) -> None:
        if actual_usd_micros < 0:
            raise ValueError("model_cost_actual_invalid")
        with self._lock:
            existing = self._records.get(reservation_id)
            if existing is None or actual_usd_micros > existing[0]:
                raise ValueError("model_cost_reconciliation_invalid")
            if existing[1] is not None and existing[1] != actual_usd_micros:
                raise ValueError("model_cost_reconciliation_integrity_failed")
            self._records[reservation_id] = (existing[0], actual_usd_micros)

    def snapshot(self) -> CostSnapshot:
        with self._lock:
            return CostSnapshot(
                reserved_usd_micros=self._exposure(),
                reconciled_usd_micros=sum(
                    actual for _reserved, actual in self._records.values()
                    if actual is not None
                ),
            )

    def _exposure(self) -> int:
        return sum(
            reserved if actual is None else actual
            for reserved, actual in self._records.values()
        )


class FirestoreModelCostLedger:
    def __init__(
        self,
        client: BaseClient,
        *,
        collection_name: str,
        hard_cap_usd_micros: int,
    ) -> None:
        self._client = client
        self._collection = client.collection(collection_name)
        self._cap = hard_cap_usd_micros

    def reserve(
        self, reservation_id: str, worst_case_usd_micros: int
    ) -> CostReservation:
        _positive(worst_case_usd_micros)
        reference = self._collection.document(reservation_id)
        summary_reference = self._collection.document("_summary")
        transaction = self._client.transaction()

        @firestore.transactional
        def reserve_once(txn: Any) -> CostReservation:
            record = reference.get(transaction=txn)
            summary = summary_reference.get(transaction=txn)
            total = 0 if not summary.exists else int(summary.to_dict()["reserved_usd_micros"])
            if record.exists:
                value = record.to_dict()
                if int(value["worst_case_usd_micros"]) != worst_case_usd_micros:
                    raise ValueError("model_cost_reservation_integrity_failed")
                return CostReservation("RESERVED", reservation_id, worst_case_usd_micros)
            if total + worst_case_usd_micros > self._cap:
                return CostReservation("DENIED", reservation_id, 0)
            txn.create(reference, {
                "worst_case_usd_micros": worst_case_usd_micros,
                "actual_usd_micros": None,
            })
            txn.set(summary_reference, {
                "reserved_usd_micros": total + worst_case_usd_micros,
                "reconciled_usd_micros": 0 if not summary.exists else int(summary.to_dict()["reconciled_usd_micros"]),
            })
            return CostReservation("RESERVED", reservation_id, worst_case_usd_micros)

        return reserve_once(transaction)

    def reconcile(self, reservation_id: str, *, actual_usd_micros: int) -> None:
        if actual_usd_micros < 0:
            raise ValueError("model_cost_actual_invalid")
        reference = self._collection.document(reservation_id)
        summary_reference = self._collection.document("_summary")
        transaction = self._client.transaction()

        @firestore.transactional
        def reconcile_once(txn: Any) -> None:
            record = reference.get(transaction=txn)
            summary = summary_reference.get(transaction=txn)
            if not record.exists or not summary.exists:
                raise ValueError("model_cost_reconciliation_invalid")
            value = record.to_dict()
            reserved = int(value["worst_case_usd_micros"])
            observed = value.get("actual_usd_micros")
            if actual_usd_micros > reserved:
                raise ValueError("model_cost_reconciliation_invalid")
            if observed is not None:
                if int(observed) != actual_usd_micros:
                    raise ValueError("model_cost_reconciliation_integrity_failed")
                return
            totals = summary.to_dict()
            txn.update(reference, {"actual_usd_micros": actual_usd_micros})
            txn.set(summary_reference, {
                "reserved_usd_micros": int(totals["reserved_usd_micros"]) - reserved + actual_usd_micros,
                "reconciled_usd_micros": int(totals["reconciled_usd_micros"]) + actual_usd_micros,
            })

        reconcile_once(transaction)

    def snapshot(self) -> CostSnapshot:
        summary = self._collection.document("_summary").get()
        if not summary.exists:
            return CostSnapshot(0, 0)
        value = summary.to_dict()
        return CostSnapshot(
            int(value["reserved_usd_micros"]),
            int(value["reconciled_usd_micros"]),
        )


def _positive(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("model_cost_reservation_invalid")
