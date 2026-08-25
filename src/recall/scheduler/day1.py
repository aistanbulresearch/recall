from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from recall.contracts import DataMode, parse_artifact
from recall.controller import Controller
from recall.ledger.port import LedgerPort
from recall.ledger.models import WatchCaseRecord
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.privacy.gate import PrivacyGate
from recall.privacy.minimizer import LabNote
from recall.privacy.receipt import verify_privacy_receipt
from recall.privacy.signing import LocalSigner

from .config import BUDGET_SNAPSHOT, COHORT, DEADLINE_AT, TRIGGER_AT


@dataclass(frozen=True, slots=True)
class Day1TriggerResult:
    selected_case_ids: tuple[str, ...]
    excluded_case_ids: tuple[str, ...]
    created_run_ids: tuple[str, ...]
    reused_run_ids: tuple[str, ...]


class Day1Scheduler:
    """One-shot deterministic scheduler for the synthetic Day-1 cohort."""

    def __init__(
        self,
        ledger: LedgerPort,
        *,
        source_commit: str,
        signer: LocalSigner,
    ) -> None:
        self._ledger = ledger
        self._source_commit = source_commit
        self._signer = signer
        self.controller = Controller(ledger)

    def verify_receipt(self, value) -> bool:
        valid, _reasons = verify_privacy_receipt(dict(value), self._signer)
        return valid

    def seed(self, *, now: datetime) -> tuple[str, ...]:
        created: list[str] = []
        for item in COHORT:
            gate = PrivacyGate(
                signer=self._signer,
                vault=_IdentitySyntheticVault(),
                clock=lambda: now,
                uuid_factory=lambda item=item: str(
                    uuid5(uuid5(NAMESPACE_URL, item.case_id), "day1-privacy")
                ),
            )
            gate_result = gate.process(_lab_note(item.case_id))
            if not gate_result.accepted or gate_result.cloud_bound_payload is None:
                raise RuntimeError("day1_privacy_gate_rejected_synthetic_input")
            payload = gate_result.cloud_bound_payload
            receipt = gate_result.receipt
            self._ledger.append_artifact(receipt)
            result = self.controller.create_watch_case(
                watch_case_id=item.case_id,
                tenant_id="synthetic-contest-lab",
                region="us-central1",
                privacy_receipt_id=str(receipt["artifact_id"]),
                cloud_bound_payload=payload,
                data_mode=DataMode.SYNTHETIC,
                source_cursors={"synthetic-source": item.cursor},
                pending_observation_hashes=(),
                next_scan_at=item.next_scan_at,
                now=now,
            )
            if result.created:
                created.append(item.case_id)
        return tuple(created)

    def trigger(self, *, now: datetime) -> Day1TriggerResult:
        trigger_at = _timestamp(TRIGGER_AT)
        due: list[tuple[WatchCaseRecord, str]] = []
        excluded: list[str] = []

        # Complete admission preflight precedes every ScanRun write.
        for item in COHORT:
            record = self._ledger.get_watch_case(item.case_id)
            if record is None:
                raise RuntimeError("day1_watch_case_missing")
            artifact_wire = self._ledger.get_artifact(record.artifact_id)
            if artifact_wire is None:
                raise RuntimeError("day1_watch_case_artifact_missing")
            parse_artifact(artifact_wire, authorized_producers=PRODUCER_REGISTRY)
            if record.state.value != "ACTIVE":
                raise RuntimeError("day1_watch_case_not_active")
            if record.next_scan_at is None:
                raise RuntimeError("day1_next_scan_at_missing")
            if _timestamp(record.next_scan_at) <= trigger_at:
                due.append((record, str(artifact_wire["input_artifact_ids"][0])))
            else:
                excluded.append(item.case_id)

        expected_due = tuple(
            item.case_id for item in COHORT if item.expected_selected
        )
        expected_excluded = tuple(
            item.case_id for item in COHORT if not item.expected_selected
        )
        actual_due = tuple(record.watch_case_id for record, _ in due)
        if actual_due != expected_due or tuple(excluded) != expected_excluded:
            raise RuntimeError("day1_frozen_cohort_selection_mismatch")

        created: list[str] = []
        reused: list[str] = []
        for record, receipt_id in due:
            result = self.controller.create_run(
                watch_case_id=record.watch_case_id,
                source_cursors=dict(record.source_cursors),
                schedule_epoch=str(record.next_scan_at),
                data_mode=DataMode.SYNTHETIC,
                privacy_receipt_id=receipt_id,
                expected_watch_case_version=record.version,
                triggered_at=trigger_at,
                budget_snapshot=BUDGET_SNAPSHOT,
                trace_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"recall:{self._source_commit}:{record.watch_case_id}:day1-trace",
                    )
                ),
                deadline_at=DEADLINE_AT,
                now=now,
            )
            target = created if result.created else reused
            target.append(result.record.run_id)
        return Day1TriggerResult(
            selected_case_ids=tuple(record.watch_case_id for record, _ in due),
            excluded_case_ids=tuple(excluded),
            created_run_ids=tuple(created),
            reused_run_ids=tuple(reused),
        )


def receipt_verifier(signer: LocalSigner):
    def verify(value) -> bool:
        valid, _reasons = verify_privacy_receipt(dict(value), signer)
        return valid

    return verify


class _IdentitySyntheticVault:
    def case_token(self, case_key: str) -> str:
        return case_key


def _lab_note(case_id: str) -> LabNote:
    return LabNote(
        case_key=case_id,
        note_text="Synthetic research record. No person identifiers.",
        tenant_id="synthetic-contest-lab",
        region="us-central1",
        gene="BRCA2",
        hgvs_c="c.7522G>C",
        hgvs_p="p.Gly2508Arg",
        assembly="GRCh38",
        data_mode="SYNTHETIC",
    )


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
