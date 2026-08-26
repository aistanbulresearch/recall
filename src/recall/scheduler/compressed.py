from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from recall.contracts import DataMode, parse_artifact
from recall.controller import Controller
from recall.controller.hashes import scan_idempotency_key
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY

from .compressed_cohort import all_compressed_cases, cases_for_cycle
from .compressed_headroom import require_headroom_pass
from .compressed_identity import (
    legacy_failure_receipt_id,
    manifest_artifact_id,
    mode_receipt_artifact_id,
    trace_id,
)
from .compressed_manifest import (
    build_compressed_manifest,
    build_compressed_mode_receipt,
)
from .compressed_plan import (
    CompressedCycle,
    CompressedPlan,
    resolve_declared_cycle,
    verify_manifest_against_plan,
)
from .compressed_preparation import (
    CompressedPreparationBundle,
    verify_prepared_cycle,
)
from .config import BUDGET_SNAPSHOT


@dataclass(frozen=True, slots=True)
class CompressedCycleResult:
    cycle_id: str
    cohort_due_date: str
    newly_created_run_ids: tuple[str, ...]
    reused_run_ids: tuple[str, ...]
    authoritative_run_ids: tuple[str, ...]
    manifest_artifact_id: str
    data_mode_receipt_id: str


class CompressedCycleScheduler:
    def __init__(
        self,
        ledger: LedgerPort,
        *,
        plan: CompressedPlan,
        cycle: CompressedCycle,
        bundle: CompressedPreparationBundle,
        source_commit: str,
        image_digest: str,
    ) -> None:
        self._ledger = ledger
        self._plan = plan
        self._cycle = cycle
        self._bundle = bundle
        self._source_commit = source_commit
        self._image_digest = image_digest
        self.controller = Controller(ledger)

    def trigger(
        self,
        *,
        now: datetime,
        previous_manifest: Mapping[str, object] | None,
        headroom_receipt: Mapping[str, object] | None = None,
        headroom_prior_ledgers: Mapping[str, LedgerPort] | None = None,
    ) -> CompressedCycleResult:
        resolved = resolve_declared_cycle(now, self._plan)
        if resolved != self._cycle:
            raise RuntimeError("compressed_cycle_resolution_mismatch")
        verify_prepared_cycle(
            self._ledger, self._bundle, self._plan, self._cycle
        )
        if self._cycle.cycle_id == "c6":
            if headroom_receipt is None or headroom_prior_ledgers is None:
                raise RuntimeError("compressed_headroom_receipt_missing")
            require_headroom_pass(
                headroom_receipt,
                plan=self._plan,
                c6_cycle=self._cycle,
                prior_ledgers=headroom_prior_ledgers,
                c6_ledger=self._ledger,
            )
        selected = cases_for_cycle(self._cycle)
        population = all_compressed_cases(self._plan.cycles)
        selected_ids = {item.case_id for item in selected}
        excluded = sorted(
            item.case_id for item in population if item.case_id not in selected_ids
        )
        manifest_id = manifest_artifact_id(self._plan, self._cycle)
        existing = self._ledger.get_artifact(manifest_id)
        if existing is not None:
            self._reconcile_existing_context(
                existing,
                previous_manifest=previous_manifest,
                headroom_receipt=headroom_receipt,
            )
        created = []
        reused = []
        watch_records = []
        run_records = []
        for item in selected:
            record = self._ledger.get_watch_case(item.case_id)
            if record is None or record.next_scan_at != self._cycle.schedule_epoch:
                raise RuntimeError("compressed_watch_case_not_due")
            wire = self._ledger.get_artifact(record.artifact_id)
            if wire is None:
                raise RuntimeError("compressed_watch_case_artifact_missing")
            watch = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
            receipt_id = str(watch.input_artifact_ids[0])
            key = scan_idempotency_key(
                watch_case_id=item.case_id,
                source_cursors=dict(record.source_cursors),
                schedule_epoch=self._cycle.schedule_epoch,
                data_mode=DataMode.SYNTHETIC.value,
            )
            expected_run_id = str(uuid5(NAMESPACE_URL, f"recall:scan-run:{key}"))
            existing_run = self._ledger.get_scan_run(expected_run_id)
            if existing_run is not None:
                existing_wire = self._ledger.get_artifact(
                    str(existing_run.scan_run_artifact_id)
                )
                if existing_wire is None:
                    raise RuntimeError("compressed_existing_scan_run_missing")
                existing_artifact = parse_artifact(
                    existing_wire, authorized_producers=PRODUCER_REGISTRY
                )
                if (
                    existing_artifact.schema_name != "ScanRun"
                    or existing_artifact.run_id != expected_run_id
                    or existing_artifact.payload.scheduled_for
                    != self._cycle.schedule_epoch
                    or existing_artifact.payload.watch_case_id != item.case_id
                ):
                    raise RuntimeError("compressed_existing_scan_run_mismatch")
                reused.append(existing_run.run_id)
                watch_records.append(record)
                run_records.append(existing_run)
                continue
            result = self.controller.create_run(
                watch_case_id=item.case_id,
                source_cursors=dict(record.source_cursors),
                schedule_epoch=self._cycle.schedule_epoch,
                data_mode=DataMode.SYNTHETIC,
                privacy_receipt_id=receipt_id,
                expected_watch_case_version=record.version,
                triggered_at=now,
                budget_snapshot=BUDGET_SNAPSHOT,
                trace_id=trace_id(self._plan, self._cycle, item.case_id),
                deadline_at=self._cycle.window_end.isoformat().replace("+00:00", "Z"),
                now=now,
            )
            (created if result.created else reused).append(result.record.run_id)
            watch_records.append(record)
            run_records.append(result.record)
        if existing is None:
            manifest = build_compressed_manifest(
                plan=self._plan,
                cycle=self._cycle,
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
                headroom_receipt=headroom_receipt,
                executed_at=now,
            )
            verify_manifest_against_plan(
                parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY),
                self._plan,
                expected_legacy_failure_receipt_id=legacy_failure_receipt_id(
                    self._plan, self._plan.by_id("c1")
                ),
            )
            self._ledger.append_artifact(manifest)
        else:
            manifest = existing
            parsed = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
            if (
                parsed.schema_version != "3.0.0"
                or parsed.payload.cycle_id != self._cycle.cycle_id
                or tuple(parsed.payload.delta["authoritative_run_ids"])
                != tuple(sorted(item.run_id for item in run_records))
            ):
                raise RuntimeError("compressed_manifest_reconciliation_failed")
        receipt_id = mode_receipt_artifact_id(self._plan, self._cycle)
        receipt = self._ledger.get_artifact(receipt_id)
        if receipt is None:
            receipt = build_compressed_mode_receipt(
                manifest, self._plan, self._cycle
            )
            self._ledger.append_artifact(receipt)
        persisted = self._ledger.get_artifact(receipt_id)
        if persisted is None:
            raise RuntimeError("compressed_data_mode_receipt_missing")
        parsed_receipt = parse_artifact(
            persisted, authorized_producers=PRODUCER_REGISTRY
        )
        if manifest_id not in parsed_receipt.payload.subject_artifact_ids:
            raise RuntimeError("compressed_data_mode_receipt_unbound")
        return CompressedCycleResult(
            cycle_id=self._cycle.cycle_id,
            cohort_due_date=self._cycle.cohort_due_date.isoformat(),
            newly_created_run_ids=tuple(sorted(created)),
            reused_run_ids=tuple(sorted(reused)),
            authoritative_run_ids=tuple(sorted(item.run_id for item in run_records)),
            manifest_artifact_id=manifest_id,
            data_mode_receipt_id=receipt_id,
        )

    def _reconcile_existing_context(
        self,
        manifest: Mapping[str, object],
        *,
        previous_manifest: Mapping[str, object] | None,
        headroom_receipt: Mapping[str, object] | None,
    ) -> None:
        parsed = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
        verify_manifest_against_plan(
            parsed,
            self._plan,
            expected_legacy_failure_receipt_id=legacy_failure_receipt_id(
                self._plan, self._plan.by_id("c1")
            ),
        )
        expected_previous = (
            None
            if previous_manifest is None
            else str(previous_manifest["artifact_id"])
        )
        expected_headroom = (
            None
            if headroom_receipt is None
            else str(headroom_receipt["artifact_id"])
        )
        if (
            parsed.schema_version != "3.0.0"
            or parsed.payload.cycle_id != self._cycle.cycle_id
            or parsed.payload.plan_sha256 != self._plan.sha256
            or parsed.payload.source_commit != self._source_commit
            or parsed.payload.image_digest != self._image_digest
            or parsed.payload.previous_manifest_id != expected_previous
            or parsed.payload.headroom_receipt_id != expected_headroom
        ):
            raise RuntimeError("compressed_existing_manifest_context_mismatch")
