from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from recall.contracts import parse_artifact
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY

from .compressed_plan import CompressedPlan, HistoricalEvidenceBinding


LedgerForPrefix = Callable[[str], LedgerPort]


@dataclass(frozen=True, slots=True)
class VerifiedFinalOnlySupersession:
    plan_sha256: str
    verified_artifact_ids: tuple[str, ...]
    manifest_wires: tuple[Mapping[str, object], ...]


def verify_final_only_supersession(
    plan: CompressedPlan,
    *,
    ledger_for_prefix: LedgerForPrefix,
) -> VerifiedFinalOnlySupersession:
    supersession = plan.supersession
    if (
        plan.schema_version != "2.8.0"
        or supersession is None
        or supersession.mode != "FINAL_ONLY_TIMEBOX"
    ):
        raise RuntimeError("final_only_supersession_required")
    verified_ids: list[str] = []
    manifests: list[Mapping[str, object]] = []
    for binding in supersession.historical_evidence:
        ledger = ledger_for_prefix(binding.collection_prefix)
        manifest_wire = _required_artifact(
            ledger,
            binding.manifest_artifact_id,
            binding.manifest_content_hash,
        )
        manifest = parse_artifact(
            manifest_wire,
            authorized_producers=PRODUCER_REGISTRY,
            verify_hash=True,
        )
        _verify_manifest(binding, manifest)
        verified_ids.append(binding.manifest_artifact_id)
        manifests.append(manifest_wire)
        if binding.mode_receipt_artifact_id is not None:
            assert binding.mode_receipt_content_hash is not None
            mode_wire = _required_artifact(
                ledger,
                binding.mode_receipt_artifact_id,
                binding.mode_receipt_content_hash,
            )
            mode = parse_artifact(
                mode_wire,
                authorized_producers=PRODUCER_REGISTRY,
                verify_hash=True,
            )
            if (
                mode.schema_name != "DataModeReceipt"
                or mode.artifact_id != binding.mode_receipt_artifact_id
                or mode.content_hash != binding.mode_receipt_content_hash
                or getattr(mode.status, "value", None) != "VALID"
                or getattr(mode.payload.propagation_status, "value", None)
                != "PASS"
                or binding.manifest_artifact_id
                not in mode.payload.subject_artifact_ids
            ):
                raise RuntimeError("final_only_history_mode_binding_invalid")
            verified_ids.append(binding.mode_receipt_artifact_id)
    return VerifiedFinalOnlySupersession(
        plan_sha256=plan.sha256,
        verified_artifact_ids=tuple(verified_ids),
        manifest_wires=tuple(manifests),
    )


def _required_artifact(
    ledger: LedgerPort,
    artifact_id: str,
    expected_hash: str,
) -> Mapping[str, object]:
    wire = ledger.get_artifact(artifact_id)
    if wire is None:
        raise RuntimeError("final_only_history_artifact_missing")
    if wire.get("content_hash") != expected_hash:
        raise RuntimeError("final_only_history_hash_mismatch")
    return wire


def _verify_manifest(binding: HistoricalEvidenceBinding, manifest: object) -> None:
    if (
        getattr(manifest, "schema_name", None) != "CohortDayManifest"
        or getattr(manifest, "artifact_id", None) != binding.manifest_artifact_id
        or getattr(manifest, "content_hash", None) != binding.manifest_content_hash
        or getattr(manifest.payload, "cycle_id", None) != binding.cycle_id
        or getattr(manifest.payload, "plan_sha256", None) != binding.plan_sha256
    ):
        raise RuntimeError("final_only_history_manifest_binding_invalid")
    history = getattr(manifest.payload, "execution_history", ())
    if (
        not history
        or history[-1].get("cycle_id") != binding.cycle_id
        or history[-1].get("source_schema_version")
        != f"CohortDayManifest/{manifest.schema_version}"
    ):
        raise RuntimeError("final_only_history_manifest_binding_invalid")
    status = getattr(manifest.status, "value", None)
    if binding.execution_status == "COMPLETE":
        if status != "VALID":
            raise RuntimeError("final_only_history_status_mismatch")
        if not history or history[-1]["execution_status"] != "COMPLETE":
            raise RuntimeError("final_only_history_status_mismatch")
        return
    if status != "INCOMPLETE":
        raise RuntimeError("final_only_history_status_mismatch")
