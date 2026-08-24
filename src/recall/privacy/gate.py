"""Laboratory-local Privacy Gate.

Order of authority for every record:

1. strict local schema, minimisation, and the registered egress profile;
2. deterministic detectors;
3. optional local model proposals;
4. deterministic adjudication of those proposals;
5. deterministic redaction;
6. deterministic outbound scan of every declared free-text field and every
   structured leaf;
7. signed `PrivacyReceipt` and, only on acceptance, a minimised payload.

Step 3 is the only step a model participates in, and it can only add
candidates. Every other step is fixed code. An unavailable, slow, or malformed
model produces a typed warning and a conservative decision; it never produces a
clean result.

Under the default `STRUCTURED_ONLY` egress profile the acceptance decision does
not depend on the model at all: the payload declares no free-text field, so
laboratory prose has no field to travel in. The model can still contribute
proposals, and protocol P1 still measures that contribution on the
`SUMMARY_TEXT` comparator, but no privacy claim in the demonstration rests on
it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from recall.privacy.adjudicator import AdjudicationResult, SpanAdjudicator
from recall.privacy.detectors import DeterministicDetector
from recall.privacy.egress import (
    EGRESS_STRUCTURED_ONLY,
    REASON_FREE_TEXT_PRESENT,
    REASON_MODEL_FAILURE_BLOCKS_TEXT,
    EgressProfile,
    free_text_fields_present,
    resolve_profile,
)
from recall.privacy.gemma import GEMMA_ADAPTER_VERSION, GemmaOutcome, GemmaResidualDetector
from recall.privacy.minimizer import LabNote, build_cloud_bound_payload
from recall.privacy.outbound import SCAN_STATUS_CLEAR, OutboundScanResult, OutboundScanner
from recall.privacy.receipt import (
    DECISION_ACCEPTED,
    DECISION_QUARANTINED,
    build_privacy_receipt,
    build_warning,
)
from recall.privacy.redactor import REDACTOR_VERSION, redact
from recall.privacy.signing import LocalSigner, content_hash
from recall.privacy.spans import DetectedSpan
from recall.privacy.vault import DerivedTokenVault, TokenVault

PRIVACY_GATE_VERSION = "0.1.0"


@dataclass(frozen=True)
class LocalOnlyEvidence:
    """Laboratory-only detail. Never serialised into a receipt or payload."""

    redacted_summary: str
    deterministic_spans: tuple[DetectedSpan, ...]
    approved_residual_spans: tuple[DetectedSpan, ...]
    blocked_field_paths: tuple[str, ...]
    egress_profile: str = EGRESS_STRUCTURED_ONLY


@dataclass(frozen=True)
class GateResult:
    decision: str
    receipt: dict[str, Any]
    cloud_bound_payload: dict[str, Any] | None
    outbound: OutboundScanResult
    gemma: GemmaOutcome
    adjudication: AdjudicationResult
    local_only: LocalOnlyEvidence = field(repr=False, default=None)  # type: ignore[assignment]

    @property
    def accepted(self) -> bool:
        return self.decision == DECISION_ACCEPTED


class PrivacyGate:
    """Deterministic owner of the laboratory egress decision."""

    version = PRIVACY_GATE_VERSION

    def __init__(
        self,
        *,
        signer: LocalSigner,
        detector: DeterministicDetector | None = None,
        gemma: GemmaResidualDetector | None = None,
        scanner: OutboundScanner | None = None,
        adjudicator: SpanAdjudicator | None = None,
        egress_profile: EgressProfile | str = EGRESS_STRUCTURED_ONLY,
        vault: TokenVault | None = None,
        clock: Callable[[], datetime] | None = None,
        uuid_factory: Callable[[], str] | None = None,
    ) -> None:
        self._signer = signer
        self._detector = detector or DeterministicDetector()
        self._gemma = gemma or GemmaResidualDetector()
        self._scanner = scanner or OutboundScanner()
        self._adjudicator = adjudicator or SpanAdjudicator(safe_words=self._scanner.words)
        self._egress = resolve_profile(egress_profile)
        self._vault = vault or DerivedTokenVault(signer.key)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._uuid_factory = uuid_factory or (lambda: str(uuid.uuid4()))

    def detector_versions(self) -> dict[str, str]:
        return {
            "deterministic": self._detector.version,
            "gemma_adapter": GEMMA_ADAPTER_VERSION,
            "adjudicator": self._adjudicator.version,
            "redactor": REDACTOR_VERSION,
            "outbound_scanner": self._scanner.version,
            "lab_directory": self._detector.directory.version,
            "outbound_lexicon": self._scanner.lexicon_version,
            "egress_profile": self._egress.identifier,
            "privacy_gate": self.version,
        }

    def process(self, note: LabNote) -> GateResult:
        deterministic_spans = tuple(self._detector.detect(note.note_text))

        gemma_outcome = self._gemma.propose(note.note_text)
        adjudication = self._adjudicator.adjudicate(gemma_outcome, note.note_text, deterministic_spans)

        all_spans = deterministic_spans + adjudication.approved
        redaction = redact(note.note_text, all_spans)

        case_token = self._vault.case_token(note.case_key)
        summary = redaction.text if self._egress.releases_free_text else None
        candidate_payload = build_cloud_bound_payload(note, case_token, summary)
        scan = self._scanner.scan_payload(candidate_payload, self._egress.text_field_paths)

        # Released-payload invariant. A later change to the minimiser cannot
        # reintroduce prose egress without failing here first.
        undeclared_text = free_text_fields_present(candidate_payload, self._egress)

        # An invoked model that failed its schema, timed out, or was
        # unreachable leaves the residual question unanswered. That only
        # matters where prose is released, so it blocks the free-text profile
        # and is recorded, but not treated as a fault, under structured-only
        # egress where no prose field exists.
        model_blocks_text = (
            self._egress.releases_free_text and gemma_outcome.invoked and not gemma_outcome.schema_valid
        )

        decision = (
            DECISION_ACCEPTED
            if scan.scan_status == SCAN_STATUS_CLEAR and not undeclared_text and not model_blocks_text
            else DECISION_QUARANTINED
        )
        released_payload = candidate_payload if decision == DECISION_ACCEPTED else None
        payload_hash = content_hash(candidate_payload)

        span_key = self._signer.span_key()
        receipt = build_privacy_receipt(
            artifact_id=self._uuid_factory(),
            case_id=case_token,
            created_at=self._clock().strftime("%Y-%m-%dT%H:%M:%SZ"),
            producer_version=self.version,
            data_mode=note.data_mode,
            decision=decision,
            detector_versions=self.detector_versions(),
            identifier_classes_checked=self._detector.identifier_classes_checked(),
            deterministic_detector={
                "version": self._detector.version,
                "approved_spans": sorted(
                    {
                        span.to_receipt_ref(note.note_text, span_key)
                        for span in deterministic_spans
                    }
                ),
            },
            gemma_detector={
                "version": gemma_outcome.adapter_version,
                "invoked": gemma_outcome.invoked,
                "schema_valid": gemma_outcome.schema_valid,
                "approved_residual_spans": sorted(
                    {
                        span.to_receipt_ref(note.note_text, span_key)
                        for span in adjudication.approved
                    }
                ),
            },
            outbound={
                "scan_status": scan.scan_status,
                "allowed_field_paths": list(scan.allowed_field_paths) if decision == DECISION_ACCEPTED else [],
                "raw_text_field_count": scan.raw_text_field_count,
            },
            payload_hash=payload_hash,
            warnings=self._warnings(
                gemma_outcome, adjudication, scan, decision, undeclared_text, model_blocks_text
            ),
            signer=self._signer,
        )

        return GateResult(
            decision=decision,
            receipt=receipt,
            cloud_bound_payload=released_payload,
            outbound=scan,
            gemma=gemma_outcome,
            adjudication=adjudication,
            local_only=LocalOnlyEvidence(
                redacted_summary=redaction.text,
                deterministic_spans=deterministic_spans,
                approved_residual_spans=adjudication.approved,
                blocked_field_paths=scan.blocked_field_paths,
                egress_profile=self._egress.name,
            ),
        )

    @staticmethod
    def _warnings(
        gemma_outcome: GemmaOutcome,
        adjudication: AdjudicationResult,
        scan: OutboundScanResult,
        decision: str,
        undeclared_text: tuple[str, ...] = (),
        model_blocks_text: bool = False,
    ) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        for code in gemma_outcome.reason_codes:
            warnings.append(build_warning(code, f"privacy.gemma.{code}"))
        for code in adjudication.rejected_reason_codes:
            warnings.append(build_warning(code, f"privacy.adjudication.{code}"))
        for code in scan.reason_codes:
            warnings.append(build_warning(code, f"privacy.outbound.{code}"))
        for field_path in undeclared_text:
            warnings.append(build_warning(REASON_FREE_TEXT_PRESENT, f"privacy.egress.{field_path}"))
        if model_blocks_text:
            warnings.append(
                build_warning(REASON_MODEL_FAILURE_BLOCKS_TEXT, "privacy.egress.local_model_failure")
            )
        if decision == DECISION_QUARANTINED:
            warnings.append(build_warning("payload_quarantined", "privacy.decision.payload_quarantined"))
        return warnings
