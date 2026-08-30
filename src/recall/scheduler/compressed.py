from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from recall.agents.full_audit import FullAuditCoordinator
from recall.contracts import DataMode, ExecutionProfile, parse_artifact
from recall.controller import Controller
from recall.controller.hashes import scan_idempotency_key
from recall.connectors.live import LiveSourceRecord
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY

from .compressed_batch import (
    BatchCaseResult,
    WritePhaseDeadlineExceeded,
    execute_verified_batch,
)
from .compressed_batch_receipt import (
    persist_or_reconcile_batch_execution,
    verify_batch_execution_binding,
)
from .compressed_cohort import (
    CompressedCohortCase,
    cases_for_cycle,
    portfolio_cases,
)
from .compressed_ramp_gate import require_ramp_gate_pass
from .compressed_headroom import require_headroom_pass
from .compressed_identity import (
    evidence_legacy_failure_receipt_id,
    manifest_artifact_id,
    mode_receipt_artifact_id,
    tick_run_id,
    trace_id,
)
from .compressed_manifest import (
    build_compressed_manifest,
    build_compressed_mode_receipt,
    require_compressed_mode_receipt_binding,
)
from .compressed_final_only_manifest import verify_final_only_history_rows
from .compressed_plan import (
    CompressedCycle,
    CompressedPlan,
    FinalOnlyOwnerRelease,
    resolve_declared_cycle,
    verify_manifest_against_plan,
)
from .compressed_preparation import (
    CompressedPreparationBundle,
    ensure_final_only_history_receipt,
    verify_prepared_cycle,
)
from .compressed_recovery import (
    install_final_only_recovery,
    recovery_trace_id,
    require_recovery_for_started_final_prefix,
)
from .compressed_supersession import (
    LedgerForPrefix,
    VerifiedFinalOnlySupersession,
    verify_final_only_supersession,
)
from .full_audit_phase import (
    FullAuditCaseFailure,
    FullAuditPhaseResult,
    execute_full_audit_phase,
    persist_cohort_checkpoint,
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
    data_mode_receipt_id: str | None


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
        full_audit_coordinator: FullAuditCoordinator | None = None,
        refetch_fetcher: Callable[[str], LiveSourceRecord] | None = None,
        clock: Callable[[], datetime] | None = None,
        owner_release: FinalOnlyOwnerRelease | None = None,
    ) -> None:
        self._ledger = ledger
        self._plan = plan
        self._cycle = cycle
        self._bundle = bundle
        self._source_commit = source_commit
        self._image_digest = image_digest
        self._full_audit = full_audit_coordinator
        self._refetch_fetcher = refetch_fetcher
        self._clock = clock
        self._owner_release = owner_release
        self.controller = Controller(ledger)

    def trigger(
        self,
        *,
        now: datetime,
        previous_manifest: Mapping[str, object] | None,
        ramp_gate_receipt: Mapping[str, object] | None = None,
        headroom_receipt: Mapping[str, object] | None = None,
        prior_ledgers: Mapping[str, LedgerPort] | None = None,
        historical_ledger_factory: LedgerForPrefix | None = None,
        recovery_previous_ledger: LedgerPort | None = None,
    ) -> CompressedCycleResult:
        resolved = (
            self._plan.by_id(self._owner_release.cycle_id)
            if self._owner_release is not None
            else resolve_declared_cycle(now, self._plan)
        )
        clock = self._clock or (lambda: now)
        if resolved != self._cycle:
            raise RuntimeError("compressed_cycle_resolution_mismatch")
        if self._owner_release is not None and now != self._owner_release.actual_start:
            raise RuntimeError("final_only_owner_release_start_mismatch")
        if self._cycle.write_path == "EXTERNAL_IMMUTABLE":
            raise RuntimeError("compressed_cycle_external_immutable")
        verified_supersession: VerifiedFinalOnlySupersession | None = None
        if self._plan.schema_version == "2.8.0":
            if any(
                item is not None
                for item in (
                    previous_manifest,
                    ramp_gate_receipt,
                    headroom_receipt,
                )
            ):
                raise RuntimeError("final_only_legacy_gate_input_forbidden")
            if historical_ledger_factory is None:
                raise RuntimeError("final_only_history_ledger_factory_missing")
            verified_supersession = verify_final_only_supersession(
                self._plan,
                ledger_for_prefix=historical_ledger_factory,
            )
        recovery_receipt = None
        if (
            self._plan.schema_version == "2.8.0"
            and self._owner_release is not None
            and self._owner_release.recovery is not None
        ):
            if recovery_previous_ledger is None or self._full_audit is None:
                raise RuntimeError("final_recovery_runtime_context_missing")
            ready = install_final_only_recovery(
                previous_ledger=recovery_previous_ledger,
                target_ledger=self._ledger,
                plan=self._plan,
                cycle=self._cycle,
                bundle=self._bundle,
                recovery=self._owner_release.recovery,
                source_commit=self._source_commit,
                image_digest=self._image_digest,
                cost_snapshot=self._full_audit.cost_snapshot(),
                now=now,
            )
            recovery_receipt = self._ledger.get_artifact(
                ready.recovery_receipt_id
            )
            if recovery_receipt is None:
                raise RuntimeError("final_recovery_receipt_missing")
        elif self._plan.schema_version == "2.8.0":
            if self._owner_release is not None:
                require_recovery_for_started_final_prefix(
                    self._ledger,
                    plan=self._plan,
                    cycle=self._cycle,
                )
            ensure_final_only_history_receipt(
                self._ledger, self._bundle, self._plan, self._cycle
            )
        else:
            verify_prepared_cycle(
                self._ledger, self._bundle, self._plan, self._cycle
            )
        if self._cycle.cycle_index >= 3 and verified_supersession is None:
            if ramp_gate_receipt is None:
                raise RuntimeError("compressed_ramp_gate_receipt_missing")
            require_ramp_gate_pass(
                ramp_gate_receipt,
                plan=self._plan,
                target_cycle=self._cycle,
                target_ledger=self._ledger,
            )
        if self._cycle.cycle_id == "c6" and verified_supersession is None:
            if headroom_receipt is None:
                raise RuntimeError("compressed_headroom_receipt_missing")
            require_headroom_pass(
                headroom_receipt,
                plan=self._plan,
                c6_cycle=self._cycle,
                prior_ledgers={} if prior_ledgers is None else prior_ledgers,
                c6_ledger=self._ledger,
            )
        selected = cases_for_cycle(self._cycle)
        population = portfolio_cases(self._plan.cycles)
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
                ramp_gate_receipt=ramp_gate_receipt,
                headroom_receipt=headroom_receipt,
                verified_supersession=verified_supersession,
            )
        batch_execution = None
        write_deadline_at = min(
            now + timedelta(seconds=self._cycle.write_timeout_seconds),
            self._effective_deadline(),
        )
        if self._cycle.write_path == "FIRESTORE_BATCH_V1":
            try:
                batch = execute_verified_batch(
                    selected,
                    create_one=lambda item: self._create_case(item, now=now),
                    ledger=self._ledger,
                    started_at=now,
                    clock=clock,
                    deadline_at=write_deadline_at,
                )
            except WritePhaseDeadlineExceeded as exc:
                if str(exc) == "compressed_write_phase_deadline_exceeded":
                    failures = tuple(
                        FullAuditCaseFailure(
                            item.case_id,
                            self._expected_run_id(item),
                            (
                                "write_phase_deadline_exceeded_after_durable_create"
                                if self._ledger.get_scan_run(
                                    self._expected_run_id(item)
                                ) is not None
                                else "write_phase_deadline_exceeded_before_create"
                            ),
                        )
                        for item in selected
                    )
                    checkpoint = persist_cohort_checkpoint(
                        ledger=self._ledger,
                        plan_sha256=self._plan.sha256,
                        cycle=self._cycle,
                        expected_manifest_id=manifest_id,
                        checkpoint_run_id=tick_run_id(self._plan, self._cycle),
                        total_cases=len(selected),
                        completed=(),
                        failures=failures,
                        detected_at=clock(),
                    )
                    raise RuntimeError(
                        f"compressed_write_phase_deadline_exceeded:{checkpoint['artifact_id']}"
                    ) from exc
                raise
            outcomes = batch.outcomes
            batch_execution = persist_or_reconcile_batch_execution(
                ledger=self._ledger,
                plan=self._plan,
                cycle=self._cycle,
                outcomes=outcomes,
                write_metrics=batch.metrics(),
            )
            write_metrics = batch_execution.write_metrics
        elif (
            self._cycle.write_path == "SERIAL_VERIFIED"
            and self._cycle.cycle_index < 3
        ):
            outcomes = tuple(self._create_case(item, now=now) for item in selected)
            write_metrics = None
        else:
            raise RuntimeError("compressed_write_path_invalid")
        created = [item.run_record.run_id for item in outcomes if item.created]
        reused = [item.run_record.run_id for item in outcomes if not item.created]
        manifest_created = created
        manifest_reused = reused
        if batch_execution is not None:
            # The durable attempt receipt, not the current process invocation,
            # owns manifest parity. A retry after that receipt was committed
            # retains the original fresh-write proof while this invocation's
            # result still truthfully reports that it reused existing runs.
            manifest_created = list(
                batch_execution.receipt["created_run_ids"]
            )
            manifest_reused = list(
                batch_execution.receipt["recovered_current_epoch_run_ids"]
            )
        watch_records = [item.watch_record for item in outcomes]
        run_records = [item.run_record for item in outcomes]
        agent_phase: FullAuditPhaseResult | None = None
        if self._cycle.execution_profile == "FULL_AUDIT_V1":
            if self._full_audit is None:
                raise RuntimeError("full_audit_coordinator_required")
            write_completed_at = datetime.fromisoformat(
                str(write_metrics["completed_at"]).replace("Z", "+00:00")
            )
            agent_deadline_at = min(
                write_completed_at
                + timedelta(seconds=self._cycle.agent_timeout_seconds),
                self._effective_deadline(),
            )
            agent_phase = execute_full_audit_phase(
                tuple(outcomes),
                coordinator=self._full_audit,
                bundle=self._bundle,
                cycle=self._cycle,
                refetch_fetcher=self._refetch_fetcher,
                checkpoint_ledger=self._ledger,
                plan_sha256=self._plan.sha256,
                expected_manifest_id=manifest_artifact_id(
                    self._plan, self._cycle
                ),
                checkpoint_run_id=tick_run_id(self._plan, self._cycle),
                agent_deadline_at=agent_deadline_at,
                clock=clock,
            )
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
                newly_created_run_ids=manifest_created,
                reused_run_ids=manifest_reused,
                bundle=self._bundle,
                previous_manifest=previous_manifest,
                ramp_gate_receipt=ramp_gate_receipt,
                headroom_receipt=headroom_receipt,
                batch_execution_receipt=(
                    None if batch_execution is None else batch_execution.receipt
                ),
                write_measurement_status=(
                    "NOT_APPLICABLE"
                    if batch_execution is None
                    else batch_execution.measurement_status
                ),
                write_metrics=write_metrics,
                agent_phase=agent_phase,
                executed_at=(
                    now
                    if write_metrics is None
                    else datetime.fromisoformat(
                        str(
                            write_metrics["completed_at"]
                            if agent_phase is None
                            else agent_phase.completed_at
                        ).replace("Z", "+00:00")
                    )
                ),
                trigger_started_at=now,
                verified_supersession=verified_supersession,
                owner_release=self._owner_release,
                recovery_receipt=recovery_receipt,
            )
            parsed_candidate = parse_artifact(
                manifest, authorized_producers=PRODUCER_REGISTRY
            )
            if verified_supersession is not None:
                verify_final_only_history_rows(
                    self._plan,
                    verified_supersession,
                    parsed_candidate.payload.execution_history,
                )
            verify_manifest_against_plan(
                parsed_candidate,
                self._plan,
                expected_legacy_failure_receipt_id=evidence_legacy_failure_receipt_id(
                    self._plan
                ),
            )
            self._ledger.append_artifact(manifest)
        else:
            manifest = existing
            parsed = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
            if verified_supersession is not None:
                verify_final_only_history_rows(
                    self._plan,
                    verified_supersession,
                    parsed.payload.execution_history,
                )
            if (
                parsed.schema_version
                != (
                    "3.4.0"
                    if self._plan.schema_version == "2.8.0"
                    else "3.3.0"
                    if self._cycle.execution_profile == "FULL_AUDIT_V1"
                    else ("3.1.0" if self._cycle.cycle_index >= 3 else "3.0.0")
                )
                or parsed.payload.cycle_id != self._cycle.cycle_id
                or tuple(parsed.payload.delta["authoritative_run_ids"])
                != tuple(sorted(item.run_id for item in run_records))
            ):
                raise RuntimeError("compressed_manifest_reconciliation_failed")
        parsed_manifest = parse_artifact(
            manifest, authorized_producers=PRODUCER_REGISTRY
        )
        if parsed_manifest.status.value != "VALID":
            return CompressedCycleResult(
                cycle_id=self._cycle.cycle_id,
                cohort_due_date=self._cycle.cohort_due_date.isoformat(),
                newly_created_run_ids=tuple(sorted(created)),
                reused_run_ids=tuple(sorted(reused)),
                authoritative_run_ids=tuple(
                    sorted(item.run_id for item in run_records)
                ),
                manifest_artifact_id=manifest_id,
                data_mode_receipt_id=None,
            )
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
        require_compressed_mode_receipt_binding(
            persisted,
            manifest_artifact_id=manifest_id,
            recovery_receipt_id=(
                None
                if recovery_receipt is None
                else str(recovery_receipt["artifact_id"])
            ),
        )
        return CompressedCycleResult(
            cycle_id=self._cycle.cycle_id,
            cohort_due_date=self._cycle.cohort_due_date.isoformat(),
            newly_created_run_ids=tuple(sorted(created)),
            reused_run_ids=tuple(sorted(reused)),
            authoritative_run_ids=tuple(sorted(item.run_id for item in run_records)),
            manifest_artifact_id=manifest_id,
            data_mode_receipt_id=receipt_id,
        )

    def _create_case(
        self, item: CompressedCohortCase, *, now: datetime
    ) -> BatchCaseResult:
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
            identity_scope=(
                None
                if self._owner_release is None
                or self._owner_release.recovery is None
                else self._owner_release.recovery.identity_scope
            ),
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
                or existing_artifact.payload.deadline_at != self._deadline(now)
            ):
                raise RuntimeError("compressed_existing_scan_run_mismatch")
            return BatchCaseResult(
                item,
                record,
                existing_run,
                False,
                existing_artifact.content_hash,
                receipt_id,
                self._cycle.schedule_epoch,
                key,
                self._trace_id(item.case_id),
                existing_artifact.payload.deadline_at,
                BUDGET_SNAPSHOT,
                self._cycle.execution_profile,
            )
        result = self.controller.create_run(
            watch_case_id=item.case_id,
            source_cursors=dict(record.source_cursors),
            schedule_epoch=self._cycle.schedule_epoch,
            data_mode=DataMode.SYNTHETIC,
            privacy_receipt_id=receipt_id,
            expected_watch_case_version=record.version,
            triggered_at=now,
            budget_snapshot=BUDGET_SNAPSHOT,
            trace_id=self._trace_id(item.case_id),
            deadline_at=self._deadline(now),
            now=now,
            execution_profile=(
                ExecutionProfile.FULL_AUDIT_V1
                if self._cycle.execution_profile == "FULL_AUDIT_V1"
                else None
            ),
            identity_scope=(
                None
                if self._owner_release is None
                or self._owner_release.recovery is None
                else self._owner_release.recovery.identity_scope
            ),
        )
        created_wire = self._ledger.get_artifact(
            str(result.record.scan_run_artifact_id)
        )
        if created_wire is None:
            raise RuntimeError("compressed_created_scan_run_missing")
        created_artifact = parse_artifact(
            created_wire, authorized_producers=PRODUCER_REGISTRY
        )
        return BatchCaseResult(
            item,
            record,
            result.record,
            result.created,
            created_artifact.content_hash,
            receipt_id,
            self._cycle.schedule_epoch,
            key,
            self._trace_id(item.case_id),
            self._deadline(now),
            BUDGET_SNAPSHOT,
            self._cycle.execution_profile,
        )

    def _expected_run_id(self, item: CompressedCohortCase) -> str:
        record = self._ledger.get_watch_case(item.case_id)
        if record is None:
            raise RuntimeError("compressed_watch_case_not_due")
        key = scan_idempotency_key(
            watch_case_id=item.case_id,
            source_cursors=dict(record.source_cursors),
            schedule_epoch=self._cycle.schedule_epoch,
            data_mode=DataMode.SYNTHETIC.value,
            identity_scope=(
                None
                if self._owner_release is None
                or self._owner_release.recovery is None
                else self._owner_release.recovery.identity_scope
            ),
        )
        return str(uuid5(NAMESPACE_URL, f"recall:scan-run:{key}"))

    def _trace_id(self, case_id: str) -> str:
        if self._owner_release is not None and self._owner_release.recovery is not None:
            return recovery_trace_id(
                self._plan,
                self._cycle,
                case_id,
                self._owner_release.recovery,
            )
        return trace_id(self._plan, self._cycle, case_id)

    def _reconcile_existing_context(
        self,
        manifest: Mapping[str, object],
        *,
        previous_manifest: Mapping[str, object] | None,
        ramp_gate_receipt: Mapping[str, object] | None,
        headroom_receipt: Mapping[str, object] | None,
        verified_supersession: VerifiedFinalOnlySupersession | None,
    ) -> None:
        parsed = parse_artifact(manifest, authorized_producers=PRODUCER_REGISTRY)
        verify_manifest_against_plan(
            parsed,
            self._plan,
            expected_legacy_failure_receipt_id=evidence_legacy_failure_receipt_id(
                self._plan
            ),
        )
        expected_previous = (
            None
            if previous_manifest is None
            else str(previous_manifest["artifact_id"])
        )
        expected_gate = (
            None
            if ramp_gate_receipt is None
            else str(ramp_gate_receipt["artifact_id"])
        )
        expected_headroom = (
            None
            if headroom_receipt is None
            else str(headroom_receipt["artifact_id"])
        )
        if (
            parsed.schema_version
            != (
                "3.4.0"
                if self._plan.schema_version == "2.8.0"
                else "3.3.0"
                if self._cycle.execution_profile == "FULL_AUDIT_V1"
                else ("3.1.0" if self._cycle.cycle_index >= 3 else "3.0.0")
            )
            or parsed.payload.cycle_id != self._cycle.cycle_id
            or parsed.payload.plan_sha256 != self._plan.sha256
            or parsed.payload.source_commit != self._source_commit
            or parsed.payload.image_digest != self._image_digest
            or parsed.payload.previous_manifest_id != expected_previous
            or (
                self._cycle.cycle_index >= 3
                and parsed.payload.ramp_gate_receipt_id != expected_gate
            )
            or parsed.payload.headroom_receipt_id != expected_headroom
            or (
                verified_supersession is not None
                and tuple(
                    parsed.payload.final_only_supersession[
                        "verified_artifact_ids"
                    ]
                )
                != verified_supersession.verified_artifact_ids
            )
        ):
            raise RuntimeError("compressed_existing_manifest_context_mismatch")
        if self._cycle.cycle_index >= 3:
            verify_batch_execution_binding(
                ledger=self._ledger,
                plan=self._plan,
                cycle=self._cycle,
                receipt_id=str(parsed.payload.batch_execution_receipt_id),
                expected_ordered_run_ids=tuple(
                    parsed.payload.delta["authoritative_run_ids"]
                ),
                expected_created_run_ids=tuple(
                    parsed.payload.delta["newly_created_run_ids"]
                ),
                expected_recovered_run_ids=tuple(
                    parsed.payload.delta["reused_run_ids"]
                ),
                expected_measurement_status=str(
                    parsed.payload.write_measurement_status
                ),
                expected_write_metrics=parsed.payload.write_metrics,
            )

    def _deadline(self, now: datetime) -> str:
        del now
        return self._effective_deadline().isoformat().replace(
            "+00:00", "Z"
        )

    def _effective_deadline(self) -> datetime:
        return (
            self._owner_release.execution_deadline
            if self._owner_release is not None
            else self._cycle.end_to_end_deadline
        )
