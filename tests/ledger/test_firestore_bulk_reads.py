from __future__ import annotations

from datetime import UTC, datetime

import pytest

from recall.contracts import ContractError
from recall.contracts.enums import ScanRunState, WatchCaseState
from recall.ledger.firestore import FirestoreLedger
from recall.ledger.models import ReviewTaskRecord, ScanRunRecord, WatchCaseRecord


class _Snapshot:
    def __init__(self, document_id: str, value: dict[str, object], *, exists=True):
        self.id = document_id
        self.exists = exists
        self._value = value

    def to_dict(self) -> dict[str, object]:
        return dict(self._value)


class _Reference:
    def __init__(self, document_id: str):
        self.id = document_id


class _Collection:
    def __init__(self, snapshots: tuple[_Snapshot, ...]):
        self._snapshots = snapshots
        self.stream_calls = 0

    def stream(self):
        self.stream_calls += 1
        return iter(self._snapshots)

    def where(self, *, filter):
        return self

    def document(self, document_id: str) -> _Reference:
        return _Reference(document_id)


class _Client:
    def __init__(
        self,
        *,
        watch: tuple[_Snapshot, ...] = (),
        runs: tuple[_Snapshot, ...] = (),
        review_tasks: tuple[_Snapshot, ...] = (),
        artifacts: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self.collections = {
            "watch_cases": _Collection(watch),
            "scan_runs": _Collection(runs),
            "artifacts": _Collection(()),
            "review_tasks": _Collection(review_tasks),
        }
        self.artifacts = artifacts or {}
        self.get_all_calls: list[tuple[str, ...]] = []

    def collection(self, name: str) -> _Collection:
        return self.collections[name]

    def get_all(self, references):
        ids = tuple(reference.id for reference in references)
        self.get_all_calls.append(ids)
        return iter(
            _Snapshot(
                document_id,
                self.artifacts.get(document_id, {}),
                exists=document_id in self.artifacts,
            )
            for document_id in ids
        )


def _watch_record(case_id: str) -> WatchCaseRecord:
    return WatchCaseRecord(
        watch_case_id=case_id,
        artifact_id=f"watch-artifact-{case_id}",
        state=WatchCaseState.ACTIVE,
        version=1,
        source_cursors=(("synthetic-source", "cursor"),),
        last_verified_snapshot_id=None,
        pending_observation_hashes=(),
        open_review_task_id=None,
        attention_reason_codes=(),
        next_scan_at="2026-08-31T00:00:00Z",
        updated_at=datetime(2026, 8, 31, tzinfo=UTC),
    )


def _run_record(run_id: str) -> ScanRunRecord:
    return ScanRunRecord(
        run_id=run_id,
        state=ScanRunState.CREATED,
        version=1,
        lease_epoch=0,
        lease_expires_at=None,
        updated_at=datetime(2026, 8, 31, tzinfo=UTC),
        scan_run_artifact_id=f"scan-artifact-{run_id}",
        terminal_policy_decision_id=None,
        failure_receipt_ids=(),
        last_repeated_state_hash=None,
        repeated_state_count=0,
    )


def _review_task(task_id: str) -> ReviewTaskRecord:
    return ReviewTaskRecord(
        task_id=task_id,
        run_id="run-a",
        watch_case_id="case-a",
        policy_decision_id="policy-a",
        deduplication_key="d" * 64,
        artifact_id=task_id,
        state="OPEN",
        delivery_state="PENDING",
        created_at=datetime(2026, 8, 31, tzinfo=UTC),
    )


def test_firestore_bulk_pointer_enumeration_is_one_stream_per_collection() -> None:
    watch = _watch_record("case-b")
    run = _run_record("run-b")
    client = _Client(
        watch=(_Snapshot(watch.watch_case_id, watch.to_wire()),),
        runs=(_Snapshot(run.run_id, run.to_wire()),),
    )
    ledger = FirestoreLedger(client)

    assert ledger.list_watch_cases() == (watch,)
    assert ledger.list_scan_runs() == (run,)
    assert client.collections["watch_cases"].stream_calls == 1
    assert client.collections["scan_runs"].stream_calls == 1


def test_firestore_bulk_review_task_enumeration_is_one_stream() -> None:
    task = _review_task("task-a")
    client = _Client(
        review_tasks=(_Snapshot(task.task_id, task.to_wire()),),
    )
    ledger = FirestoreLedger(client)

    assert ledger.list_review_tasks_all() == (task,)
    assert client.collections["review_tasks"].stream_calls == 1


def test_firestore_run_scoped_review_task_enumeration_remains_available() -> None:
    task = _review_task("task-a")
    client = _Client(
        review_tasks=(_Snapshot(task.task_id, task.to_wire()),),
    )
    ledger = FirestoreLedger(client)

    assert ledger.list_review_tasks("run-a") == (task,)
    assert client.collections["review_tasks"].stream_calls == 1


def test_firestore_bulk_review_task_rejects_document_identity_drift() -> None:
    task = _review_task("task-a")
    client = _Client(
        review_tasks=(_Snapshot("wrong-task", task.to_wire()),),
    )
    ledger = FirestoreLedger(client)

    with pytest.raises(ContractError, match="review_task_document_id"):
        ledger.list_review_tasks_all()


def test_firestore_bulk_artifact_reads_are_chunked_not_per_document() -> None:
    artifact_ids = tuple(f"artifact-{index:04d}" for index in range(1_371))
    client = _Client(
        artifacts={
            artifact_id: {"artifact_id": artifact_id}
            for artifact_id in artifact_ids
        }
    )
    ledger = FirestoreLedger(client)

    values = ledger.get_artifacts(tuple(reversed(artifact_ids)))

    assert set(values) == set(artifact_ids)
    assert tuple(len(call) for call in client.get_all_calls) == (
        250,
        250,
        250,
        250,
        250,
        121,
    )
    assert tuple(item for call in client.get_all_calls for item in call) == artifact_ids


def test_firestore_bulk_artifact_read_rejects_document_identity_drift() -> None:
    client = _Client(artifacts={"artifact-a": {"artifact_id": "artifact-b"}})
    ledger = FirestoreLedger(client)

    with pytest.raises(ContractError, match="bulk_artifact_document_id"):
        ledger.get_artifacts(("artifact-a",))


@pytest.mark.parametrize("collection", ["watch_cases", "scan_runs"])
def test_firestore_bulk_pointer_read_rejects_document_identity_drift(
    collection: str,
) -> None:
    watch = _watch_record("case-a")
    run = _run_record("run-a")
    client = _Client(
        watch=(_Snapshot("wrong-case", watch.to_wire()),),
        runs=(_Snapshot("wrong-run", run.to_wire()),),
    )
    ledger = FirestoreLedger(client)

    with pytest.raises(ContractError, match=f"{collection[:-1]}_document_id"):
        if collection == "watch_cases":
            ledger.list_watch_cases()
        else:
            ledger.list_scan_runs()
