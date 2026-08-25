from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping
from uuid import NAMESPACE_URL, uuid5

from recall.contracts import DataMode, parse_artifact
from recall.controller import Controller
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY

from .cohort import MANAGED_COHORT, RUN_PREDICTIONS, cases_for_date, verify_replay_anchors
from .manifest import (
    build_manifest,
    build_mode_receipt,
    logical_tick_at,
    manifest_artifact_id,
    mode_receipt_artifact_id,
)
from .preparation import CohortPreparationBundle, verify_prepared_day
from .config import BUDGET_SNAPSHOT


@dataclass(frozen=True, slots=True)
class DayNPreview:
    selected_for_date: str
    selected_case_ids: tuple[str, ...]
    excluded_case_ids: tuple[str, ...]
    runs_predicted: int
    collection_prefix: str


@dataclass(frozen=True, slots=True)
class DayNResult:
    selected_for_date: str
    newly_created_run_ids: tuple[str, ...]
    reused_run_ids: tuple[str, ...]
    authoritative_run_ids: tuple[str, ...]
    manifest_artifact_id: str
    data_mode_receipt_id: str


def collection_prefix(selected_for_date: date) -> str:
    return f"dev_recall_m2_cohort_{selected_for_date:%Y%m%d}_"


def preview(selected_for_date: date, *, repo_root: Path) -> DayNPreview:
    verify_replay_anchors(repo_root)
    selected = cases_for_date(selected_for_date)
    if selected_for_date not in RUN_PREDICTIONS:
        raise RuntimeError("cohort_prediction_missing")
    if len(selected) != RUN_PREDICTIONS[selected_for_date]:
        raise RuntimeError("cohort_prediction_mismatch")
    selected_ids = {item.case_id for item in selected}
    return DayNPreview(
        selected_for_date=selected_for_date.isoformat(),
        selected_case_ids=tuple(sorted(selected_ids)),
        excluded_case_ids=tuple(
            sorted(item.case_id for item in MANAGED_COHORT if item.case_id not in selected_ids)
        ),
        runs_predicted=RUN_PREDICTIONS[selected_for_date],
        collection_prefix=collection_prefix(selected_for_date),
    )


class DayNScheduler:
    """One date-isolated managed cohort tick; admission remains lab-local."""

    def __init__(
        self,
        ledger: LedgerPort,
        *,
        bundle: CohortPreparationBundle,
        source_commit: str,
        image_digest: str,
        fault_after_run_writes: int | None = None,
    ) -> None:
        self._ledger = ledger
        self._bundle = bundle
        self._source_commit = source_commit
        self._image_digest = image_digest
        self._fault_after_run_writes = fault_after_run_writes
        self.controller = Controller(ledger)

    def trigger(
        self,
        *,
        now: datetime,
        previous_manifest: Mapping[str, object] | None,
    ) -> DayNResult:
        selected_for_date = _real_selected_date(now)
        verify_prepared_day(self._ledger, self._bundle)
        selected = cases_for_date(selected_for_date)
        if len(selected) != RUN_PREDICTIONS[selected_for_date]:
            raise RuntimeError("cohort_prediction_mismatch")
        selected_ids = {item.case_id for item in selected}
        excluded = sorted(
            item.case_id for item in MANAGED_COHORT if item.case_id not in selected_ids
        )
        created: list[str] = []
        reused: list[str] = []
        watch_records = []
        run_records = []
        logical_tick = logical_tick_at(selected_for_date)
        deadline = logical_tick + timedelta(minutes=9, seconds=59)
        for item in selected:
            record = self._ledger.get_watch_case(item.case_id)
            if record is None or record.next_scan_at is None:
                raise RuntimeError("cohort_watch_case_not_prepared")
            watch_wire = self._ledger.get_artifact(record.artifact_id)
            if watch_wire is None:
                raise RuntimeError("cohort_watch_case_artifact_missing")
            watch = parse_artifact(watch_wire, authorized_producers=PRODUCER_REGISTRY)
            receipt_id = str(watch.input_artifact_ids[0])
            result = self.controller.create_run(
                watch_case_id=item.case_id,
                source_cursors=dict(record.source_cursors),
                schedule_epoch=record.next_scan_at,
                data_mode=DataMode.SYNTHETIC,
                privacy_receipt_id=receipt_id,
                expected_watch_case_version=record.version,
                triggered_at=logical_tick,
                budget_snapshot=BUDGET_SNAPSHOT,
                trace_id=str(
                    uuid5(NAMESPACE_URL, f"recall:cohort:{selected_for_date}:{item.case_id}:trace")
                ),
                deadline_at=deadline.isoformat().replace("+00:00", "Z"),
                now=now,
            )
            (created if result.created else reused).append(result.record.run_id)
            watch_records.append(record)
            run_records.append(result.record)
            if (
                self._fault_after_run_writes is not None
                and len(created) == self._fault_after_run_writes
            ):
                raise RuntimeError("synthetic_fault_after_run_write")
        manifest_id = manifest_artifact_id(selected_for_date)
        existing = self._ledger.get_artifact(manifest_id)
        if existing is None:
            manifest = build_manifest(
                selected_for_date=selected_for_date,
                source_commit=self._source_commit,
                image_digest=self._image_digest,
                selected_cases=selected,
                excluded_case_ids=excluded,
                watch_records=watch_records,
                run_records=run_records,
                newly_created_run_ids=created,
                reused_run_ids=reused,
                bundle=self._bundle,
                previous_manifest=previous_manifest,
                executed_at=now,
            )
            self._ledger.append_artifact(manifest)
        else:
            manifest = existing
            parsed = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
            if tuple(parsed.payload.delta["authoritative_run_ids"]) != tuple(
                sorted(record.run_id for record in run_records)
            ):
                raise RuntimeError("cohort_manifest_reconciliation_failed")
        receipt_id = mode_receipt_artifact_id(selected_for_date)
        receipt = self._ledger.get_artifact(receipt_id)
        if receipt is None:
            receipt = build_mode_receipt(manifest, selected_for_date=selected_for_date)
            self._ledger.append_artifact(receipt)
        persisted_receipt = self._ledger.get_artifact(receipt_id)
        if persisted_receipt is None:
            raise RuntimeError("cohort_data_mode_receipt_missing")
        parsed_receipt = parse_artifact(
            persisted_receipt, authorized_producers=PRODUCER_REGISTRY
        )
        if manifest_id not in parsed_receipt.payload.subject_artifact_ids:
            raise RuntimeError("cohort_data_mode_receipt_missing")
        return DayNResult(
            selected_for_date=selected_for_date.isoformat(),
            newly_created_run_ids=tuple(sorted(created)),
            reused_run_ids=tuple(sorted(reused)),
            authoritative_run_ids=tuple(sorted(record.run_id for record in run_records)),
            manifest_artifact_id=manifest_id,
            data_mode_receipt_id=receipt_id,
        )


def _real_selected_date(now: datetime) -> date:
    if now.tzinfo is None or now.utcoffset() is None:
        raise RuntimeError("cohort_now_not_timezone_aware")
    utc = now.astimezone(timezone.utc)
    start = logical_tick_at(utc.date())
    end = start + timedelta(minutes=9, seconds=59)
    if not start <= utc <= end:
        raise RuntimeError("cohort_execution_outside_daily_window")
    if utc.date() == date(2026, 8, 25):
        raise RuntimeError("frozen_day1_recurring_execution_forbidden")
    if utc.date() not in RUN_PREDICTIONS:
        raise RuntimeError("cohort_prediction_missing")
    return utc.date()
