from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from recall.contracts import canonical_json_bytes, parse_artifact, parse_cloud_bound_payload
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY

from .compressed_cohort import all_compressed_cases, cases_for_cycle
from .compressed_plan import PLAN9_HISTORICAL_SHA256, CompressedCycle, CompressedPlan
from .history import load_day1_history_receipt


DEFAULT_COMPRESSED_BUNDLE_PATH = Path(
    "artifacts/evidence/cohort-compression/preparation-bundle-v2.json"
)

FULL_AUDIT_MODEL_ID = "gemma4:e4b-it-qat"
FINAL_ONLY_SOURCE_BUNDLE_SHA256 = (
    "56ef5e9f73c0b25c7718652a2624dcff9927906bb8d4ee723fdda9add2f111ee"
)
FINAL_ONLY_SOURCE_BUNDLE_COMMIT = "6d30a125db12ec926445dd1bd816ba10aecf938f"
FINAL_ONLY_SOURCE_MATERIAL_SHA256 = (
    "b346febf7cf834fb46f9a4994f7a1a626405d1a031b1a4c5980efd40a307e1cc"
)
FINAL_ONLY_PRIVACY_SOURCE_LOCK = {
    "algorithm": "HMAC-SHA256",
    "key_fingerprint_sha256": (
        "fa70a3d2d397209ea3fb6f5b09363e3b5cfc2bf6a0742c0f3ca7932031b92b08"
    ),
    "key_id": "full-cohort-receipt-run-v1",
    "source_sha256": (
        "70ccfc251d37dffa8174d82842feedcef1227399a285d13b9ba9e82979fab901"
    ),
}
FINAL_ONLY_LAB_NOTE_SOURCE_LOCK = {
    "notes_version": "portfolio-notes-v2",
    "schema_version": "1.1.0",
    "source_sha256": (
        "ce71a0b7b50601148c49b65457bc603efca929b3569ed37179902424c8d36af6"
    ),
}
FINAL_ONLY_REBOUND_WATCH_FIELDS = frozenset(
    {
        "artifact_id",
        "content_hash",
        "created_at",
        "monitoring_started_at",
        "next_scan_at",
    }
)


@dataclass(frozen=True, slots=True)
class CompressedPreparedCase:
    case_id: str
    cycle_id: str
    cloud_bound_payload: Mapping[str, object]
    privacy_receipt: Mapping[str, object]
    watch_case: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class CompressedPreparationBundle:
    schema_version: str
    prepared_at: str
    source_commit: str | None
    plan_sha256: str
    rights_note: str
    cases: tuple[CompressedPreparedCase, ...]
    replay_observations: tuple[Mapping[str, object], ...]
    history_receipt: Mapping[str, object]
    legacy_failure_receipt: Mapping[str, object] | None
    bundle_sha256: str
    privacy_receipt_source_lock: Mapping[str, str] | None = None
    lab_note_source_lock: Mapping[str, str] | None = None
    source_bundle_sha256: str | None = None
    source_material_sha256: str | None = None
    input_source_commit: str | None = None
    input_plan_sha256: str | None = None

    @property
    def observations_by_vcv(self) -> Mapping[str, Mapping[str, object]]:
        return {
            str(item["structured_fields"]["semantic_anchor"]): item
            for item in self.replay_observations
        }


class CompressedPreparationVerifier:
    def __init__(self, bundle: CompressedPreparationBundle) -> None:
        self._locks = {
            str(item.privacy_receipt["artifact_id"]): _wire_sha256(
                item.privacy_receipt
            )
            for item in bundle.cases
        }

    def __call__(self, value: Mapping[str, Any]) -> bool:
        try:
            parsed = parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
        except Exception:
            return False
        return (
            parsed.schema_name == "PrivacyReceipt"
            and parsed.data_mode.value == "SYNTHETIC"
            and parsed.producer.identity == "privacy-gate"
            and parsed.payload.decision.value == "ACCEPTED"
            and self._locks.get(parsed.artifact_id) == _wire_sha256(value)
        )


def load_compressed_bundle(
    repo_root: Path,
    *,
    expected_sha256: str,
    plan: CompressedPlan,
    path: Path = DEFAULT_COMPRESSED_BUNDLE_PATH,
) -> CompressedPreparationBundle:
    root = repo_root.resolve()
    full = (root / path).resolve()
    if not full.is_relative_to(root) or not full.is_file():
        raise RuntimeError("compressed_preparation_path_invalid")
    raw = full.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise RuntimeError("compressed_preparation_bundle_hash_mismatch")
    value = json.loads(raw.decode("utf-8"))
    legacy_base_fields = {
        "schema_version",
        "prepared_at",
        "source_commit",
        "plan_sha256",
        "rights_note",
        "cases",
        "replay_observations",
        "legacy_failure_receipt",
    }
    final_only_fields = {
        "schema_version",
        "prepared_at",
        "input_source_commit",
        "input_plan_sha256",
        "plan_sha256",
        "rights_note",
        "cases",
        "replay_observations",
        "privacy_receipt_source_lock",
        "lab_note_source_lock",
        "source_bundle_sha256",
        "source_material_sha256",
    }
    observed_fields = frozenset(value) if isinstance(value, dict) else frozenset()
    schema_version = value.get("schema_version") if isinstance(value, dict) else None
    legacy_shapes = {
        frozenset(legacy_base_fields),
        frozenset({*legacy_base_fields, "privacy_receipt_source_lock"}),
        frozenset(
            {
                *legacy_base_fields,
                "privacy_receipt_source_lock",
                "lab_note_source_lock",
            }
        ),
    }
    if not isinstance(value, dict) or (
        schema_version == "2.3.0"
        and observed_fields != frozenset(final_only_fields)
    ) or (
        schema_version != "2.3.0" and observed_fields not in legacy_shapes
    ):
        raise RuntimeError("compressed_preparation_bundle_shape_invalid")
    has_source_lock = "privacy_receipt_source_lock" in value
    has_note_lock = "lab_note_source_lock" in value
    final_only = schema_version == "2.3.0"
    if final_only:
        if (
            plan.schema_version != "2.8.0"
            or value["plan_sha256"] != plan.sha256
            or value["source_bundle_sha256"]
            != FINAL_ONLY_SOURCE_BUNDLE_SHA256
            or value["input_source_commit"]
            != FINAL_ONLY_SOURCE_BUNDLE_COMMIT
            or value["input_plan_sha256"] != PLAN9_HISTORICAL_SHA256
            or value["source_material_sha256"]
            != FINAL_ONLY_SOURCE_MATERIAL_SHA256
            or value["privacy_receipt_source_lock"]
            != FINAL_ONLY_PRIVACY_SOURCE_LOCK
            or value["lab_note_source_lock"]
            != FINAL_ONLY_LAB_NOTE_SOURCE_LOCK
        ):
            raise RuntimeError("compressed_final_only_preparation_lock_mismatch")
    elif (
        schema_version not in {"2.0.0", "2.1.0", "2.2.0"}
        or has_source_lock is not (schema_version in {"2.1.0", "2.2.0"})
        or has_note_lock is not (schema_version == "2.2.0")
        or value["plan_sha256"] != plan.sha256
    ):
        raise RuntimeError("compressed_preparation_plan_mismatch")
    bundle = CompressedPreparationBundle(
        schema_version=str(schema_version),
        prepared_at=_timestamp(value["prepared_at"]),
        source_commit=(None if final_only else _commit(value["source_commit"])),
        plan_sha256=plan.sha256,
        rights_note=_text(value["rights_note"]),
        cases=tuple(_parse_case(item) for item in value["cases"]),
        replay_observations=tuple(
            _parse_observation(item) for item in value["replay_observations"]
        ),
        history_receipt=load_day1_history_receipt(root),
        legacy_failure_receipt=(
            None
            if final_only
            else _parse_failure(value["legacy_failure_receipt"])
        ),
        bundle_sha256=digest,
        privacy_receipt_source_lock=(
            None
            if not has_source_lock
            else _parse_privacy_source_lock(
                value["privacy_receipt_source_lock"]
            )
        ),
        lab_note_source_lock=(
            None
            if not has_note_lock
            else _parse_lab_note_source_lock(value["lab_note_source_lock"])
        ),
        source_bundle_sha256=(
            str(value["source_bundle_sha256"]) if final_only else None
        ),
        source_material_sha256=(
            str(value["source_material_sha256"]) if final_only else None
        ),
        input_source_commit=(
            _commit(value["input_source_commit"]) if final_only else None
        ),
        input_plan_sha256=(
            str(value["input_plan_sha256"]) if final_only else None
        ),
    )
    _validate_bundle(bundle, plan)
    if final_only and final_only_source_material_sha256(bundle) != (
        FINAL_ONLY_SOURCE_MATERIAL_SHA256
    ):
        raise RuntimeError("compressed_final_only_source_material_mismatch")
    return bundle


def install_prepared_cycle(
    ledger: LedgerPort,
    bundle: CompressedPreparationBundle,
    plan: CompressedPlan,
    cycle: CompressedCycle,
    *,
    now: datetime,
) -> Mapping[str, int]:
    expected = {(item.case_id, item.cycle_id) for item in cases_for_cycle(cycle)}
    selected = tuple(
        item for item in bundle.cases
        if (item.case_id, item.cycle_id) in expected
    )
    _prevalidate_selected(bundle, cycle, selected)
    history_created = _append_locked(ledger, bundle.history_receipt)
    failure_created = 0
    if cycle.cycle_id == "c1":
        if bundle.legacy_failure_receipt is None:
            raise RuntimeError("compressed_legacy_failure_receipt_missing")
        failure_created = _append_locked(ledger, bundle.legacy_failure_receipt)
    receipts = cases = observations = 0
    verifier = CompressedPreparationVerifier(bundle)
    for item in selected:
        receipts += _append_locked(ledger, item.privacy_receipt)
        if not verifier(item.privacy_receipt):
            raise RuntimeError("compressed_preparation_receipt_lock_failed")
        _record, created = ledger.create_watch_case(
            item.watch_case,
            cloud_bound_payload=item.cloud_bound_payload,
            now=now,
        )
        cases += int(created)
    selected_vcvs = {
        item.vcv for item in cases_for_cycle(cycle) if item.vcv is not None
    }
    for observation in bundle.replay_observations:
        if observation["structured_fields"]["semantic_anchor"] in selected_vcvs:
            observations += _append_locked(ledger, observation)
    verify_prepared_cycle(ledger, bundle, plan, cycle)
    return {
        "history_receipts_created": history_created,
        "legacy_failure_receipts_created": failure_created,
        "privacy_receipts_created": receipts,
        "watch_cases_created": cases,
        "replay_observations_created": observations,
    }


def verify_prepared_cycle(
    ledger: LedgerPort,
    bundle: CompressedPreparationBundle,
    plan: CompressedPlan,
    cycle: CompressedCycle,
) -> None:
    _verify_prepared_cycle(
        ledger, bundle, plan, cycle, require_history_receipt=True
    )


def ensure_final_only_history_receipt(
    ledger: LedgerPort,
    bundle: CompressedPreparationBundle,
    plan: CompressedPlan,
    cycle: CompressedCycle,
) -> int:
    """Install only the exact committed Day-1 receipt after a read-only precheck."""

    if (
        plan.schema_version != "2.8.0"
        or bundle.schema_version != "2.3.0"
        or cycle != plan.by_id("c6")
        or bundle.plan_sha256 != plan.sha256
        or bundle.source_bundle_sha256 != FINAL_ONLY_SOURCE_BUNDLE_SHA256
        or bundle.source_material_sha256 != FINAL_ONLY_SOURCE_MATERIAL_SHA256
        or bundle.input_source_commit != FINAL_ONLY_SOURCE_BUNDLE_COMMIT
        or bundle.input_plan_sha256 != PLAN9_HISTORICAL_SHA256
        or bundle.privacy_receipt_source_lock != FINAL_ONLY_PRIVACY_SOURCE_LOCK
        or bundle.lab_note_source_lock != FINAL_ONLY_LAB_NOTE_SOURCE_LOCK
        or final_only_source_material_sha256(bundle)
        != FINAL_ONLY_SOURCE_MATERIAL_SHA256
    ):
        raise RuntimeError("compressed_final_only_preparation_lock_mismatch")
    _verify_prepared_cycle(
        ledger, bundle, plan, cycle, require_history_receipt=False
    )
    persisted = ledger.get_artifact(str(bundle.history_receipt["artifact_id"]))
    if persisted is not None:
        _verify_locked(
            ledger, bundle.history_receipt, "cohort_history_receipt_missing"
        )
        return 0
    created = _append_locked(ledger, bundle.history_receipt)
    _verify_locked(ledger, bundle.history_receipt, "cohort_history_receipt_missing")
    return created


def _verify_prepared_cycle(
    ledger: LedgerPort,
    bundle: CompressedPreparationBundle,
    plan: CompressedPlan,
    cycle: CompressedCycle,
    *,
    require_history_receipt: bool,
) -> None:
    if require_history_receipt:
        _verify_locked(
            ledger, bundle.history_receipt, "cohort_history_receipt_missing"
        )
    if cycle.cycle_id == "c1":
        if bundle.legacy_failure_receipt is None:
            raise RuntimeError("compressed_legacy_failure_receipt_missing")
        _verify_locked(
            ledger,
            bundle.legacy_failure_receipt,
            "compressed_legacy_failure_receipt_missing",
        )
    expected = {(item.case_id, item.cycle_id) for item in cases_for_cycle(cycle)}
    selected = tuple(
        item for item in bundle.cases
        if (item.case_id, item.cycle_id) in expected
    )
    _prevalidate_selected(bundle, cycle, selected)
    verifier = CompressedPreparationVerifier(bundle)
    for item in selected:
        record = ledger.get_watch_case(item.case_id)
        if (
            record is None
            or record.next_scan_at != cycle.schedule_epoch
            or record.artifact_id != item.watch_case["artifact_id"]
        ):
            raise RuntimeError("compressed_prepared_watch_case_missing")
        _verify_locked(
            ledger, item.watch_case, "compressed_prepared_watch_case_lock_failed"
        )
        receipt = ledger.get_artifact(str(item.privacy_receipt["artifact_id"]))
        if receipt is None or not verifier(receipt):
            raise RuntimeError("compressed_prepared_receipt_missing")
        if cycle.execution_profile == "FULL_AUDIT_V1":
            _require_full_audit_privacy_receipt(receipt)
            if bundle.privacy_receipt_source_lock is None:
                raise RuntimeError("full_audit_privacy_source_lock_required")
            if bundle.lab_note_source_lock is None:
                raise RuntimeError("full_audit_lab_note_source_lock_required")
    for item in cases_for_cycle(cycle):
        if item.vcv is not None:
            observation = bundle.observations_by_vcv[item.vcv]
            _verify_locked(
                ledger, observation, "compressed_prepared_anchor_missing"
            )


def _prevalidate_selected(
    bundle: CompressedPreparationBundle,
    cycle: CompressedCycle,
    selected: tuple[CompressedPreparedCase, ...],
) -> None:
    """Reject an invalid FULL_AUDIT bundle before the first ledger write."""

    if len(selected) != cycle.runs_predicted:
        raise RuntimeError("compressed_preparation_case_set_mismatch")
    verifier = CompressedPreparationVerifier(bundle)
    for item in selected:
        if not verifier(item.privacy_receipt):
            raise RuntimeError("compressed_preparation_receipt_lock_failed")
        if cycle.execution_profile == "FULL_AUDIT_V1":
            _require_full_audit_privacy_receipt(item.privacy_receipt)
    if (
        cycle.execution_profile == "FULL_AUDIT_V1"
        and (
            bundle.privacy_receipt_source_lock is None
            or bundle.lab_note_source_lock is None
        )
    ):
        raise RuntimeError("full_audit_input_source_locks_required")


def _append_locked(ledger: LedgerPort, value: Mapping[str, object]) -> int:
    artifact_id = str(value["artifact_id"])
    before = ledger.get_artifact(artifact_id)
    ledger.append_artifact(value)
    _verify_locked(ledger, value, "compressed_preparation_readback_failed")
    return int(before is None)


def _verify_locked(
    ledger: LedgerPort, value: Mapping[str, object], reason: str
) -> None:
    persisted = ledger.get_artifact(str(value["artifact_id"]))
    if persisted is None or _wire_sha256(persisted) != _wire_sha256(value):
        raise RuntimeError(reason)


def _parse_case(value: Any) -> CompressedPreparedCase:
    if not isinstance(value, Mapping) or set(value) != {
        "case_id",
        "cycle_id",
        "cloud_bound_payload",
        "privacy_receipt",
        "watch_case",
    }:
        raise RuntimeError("compressed_prepared_case_shape_invalid")
    cloud = parse_cloud_bound_payload(value["cloud_bound_payload"])
    receipt = parse_artifact(value["privacy_receipt"], authorized_producers=PRODUCER_REGISTRY)
    watch = parse_artifact(value["watch_case"], authorized_producers=PRODUCER_REGISTRY)
    if (
        receipt.schema_name != "PrivacyReceipt"
        or watch.schema_name != "WatchCase"
        or cloud.case_token != value["case_id"]
        or receipt.case_id != value["case_id"]
        or watch.case_id != value["case_id"]
        or watch.input_artifact_ids != (receipt.artifact_id,)
    ):
        raise RuntimeError("compressed_prepared_case_binding_invalid")
    return CompressedPreparedCase(
        case_id=str(value["case_id"]),
        cycle_id=_text(value["cycle_id"]),
        cloud_bound_payload=cloud.to_wire(),
        privacy_receipt=receipt.to_wire(),
        watch_case=watch.to_wire(),
    )


def _require_full_audit_privacy_receipt(
    value: Mapping[str, object],
) -> None:
    parsed = parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
    if (
        parsed.schema_name != "PrivacyReceipt"
        or parsed.schema_version != "1.1.0"
    ):
        raise RuntimeError("full_audit_privacy_receipt_required")
    gemma = parsed.payload.detectors["gemma"]
    declared_path = (
        parsed.payload.execution_locus.value,
        parsed.payload.transport_class.value,
        parsed.payload.endpoint_class.value,
    )
    accepted_paths = {
        ("LAB_LOCAL", "LOCAL_PROCESS", "OLLAMA_LOCAL"),
        ("LAB_LOCAL", "PRIVATE_SERVICE", "OLLAMA_CLOUD_RUN"),
        ("LAB_LOCAL", "PRIVATE_SERVICE", "OLLAMA_VERTEX_ENDPOINT"),
    }
    if (
        parsed.payload.decision.value != "ACCEPTED"
        or declared_path not in accepted_paths
        or parsed.payload.model_id != FULL_AUDIT_MODEL_ID
        or not str(parsed.payload.model_revision).startswith("sha256:")
        or gemma.get("invoked") is not True
        or gemma.get("schema_valid") is not True
    ):
        raise RuntimeError("full_audit_privacy_receipt_required")


def _parse_observation(value: Any) -> Mapping[str, object]:
    artifact = parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
    if artifact.schema_name != "EvidenceObservation" or artifact.data_mode.value != "CAPTURED_REPLAY":
        raise RuntimeError("compressed_replay_observation_invalid")
    return artifact.to_wire()


def _parse_failure(value: Any) -> Mapping[str, object]:
    artifact = parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
    if artifact.schema_name != "CompressedCycleFailureReceipt":
        raise RuntimeError("compressed_failure_receipt_invalid")
    return artifact.to_wire()


def _parse_privacy_source_lock(value: Any) -> Mapping[str, str]:
    fields = {
        "source_sha256",
        "key_id",
        "algorithm",
        "key_fingerprint_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise RuntimeError("privacy_receipt_source_lock_invalid")
    if value["algorithm"] != "HMAC-SHA256":
        raise RuntimeError("privacy_receipt_source_lock_invalid")
    for field in ("source_sha256", "key_fingerprint_sha256"):
        text = value[field]
        if (
            not isinstance(text, str)
            or len(text) != 64
            or any(item not in "0123456789abcdef" for item in text)
        ):
            raise RuntimeError("privacy_receipt_source_lock_invalid")
    if not isinstance(value["key_id"], str) or not value["key_id"]:
        raise RuntimeError("privacy_receipt_source_lock_invalid")
    return {field: str(value[field]) for field in sorted(fields)}


def _parse_lab_note_source_lock(value: Any) -> Mapping[str, str]:
    fields = {"source_sha256", "schema_version", "notes_version"}
    if not isinstance(value, Mapping) or set(value) != fields:
        raise RuntimeError("lab_note_source_lock_invalid")
    if value["schema_version"] != "1.1.0":
        raise RuntimeError("lab_note_source_lock_invalid")
    source_sha = value["source_sha256"]
    if (
        not isinstance(source_sha, str)
        or len(source_sha) != 64
        or any(item not in "0123456789abcdef" for item in source_sha)
        or not isinstance(value["notes_version"], str)
        or not value["notes_version"]
    ):
        raise RuntimeError("lab_note_source_lock_invalid")
    return {field: str(value[field]) for field in sorted(fields)}


def _validate_bundle(bundle: CompressedPreparationBundle, plan: CompressedPlan) -> None:
    if plan.schema_version == "2.8.0":
        if bundle.schema_version != "2.3.0":
            raise RuntimeError("compressed_final_only_preparation_required")
        cycle = plan.by_id("c6")
        expected = cases_for_cycle(cycle)
    else:
        if bundle.schema_version == "2.3.0":
            raise RuntimeError("compressed_final_only_preparation_plan_mismatch")
        cycle = None
        expected = all_compressed_cases(plan.cycles)
    if tuple((item.case_id, item.cycle_id) for item in bundle.cases) != tuple(
        sorted((item.case_id, item.cycle_id) for item in expected)
    ):
        raise RuntimeError("compressed_preparation_case_set_mismatch")
    if cycle is not None:
        expected_by_case = {item.case_id: item for item in expected}
        for item in bundle.cases:
            expected_case = expected_by_case[item.case_id]
            watch = item.watch_case
            _require_full_audit_privacy_receipt(item.privacy_receipt)
            if (
                item.cycle_id != "c6"
                or watch["artifact_id"]
                != _prepared_watch_artifact_id(item.case_id, cycle)
                or watch["next_scan_at"] != cycle.schedule_epoch
                or watch["source_cursors"]
                != {"synthetic-source": expected_case.cursor}
                or watch["data_mode"] != expected_case.data_mode.value
                or item.cloud_bound_payload["data_mode"]
                != expected_case.data_mode.value
            ):
                raise RuntimeError("compressed_final_only_watch_case_binding_invalid")
    expected_vcvs = {item.vcv for item in expected if item.vcv is not None}
    if set(bundle.observations_by_vcv) != expected_vcvs:
        raise RuntimeError("compressed_preparation_anchor_set_mismatch")


def final_only_source_material_sha256(
    bundle: CompressedPreparationBundle,
) -> str:
    material = {
        "cases": [
            {
                "case_id": item.case_id,
                "cloud_bound_payload": item.cloud_bound_payload,
                "privacy_receipt": item.privacy_receipt,
                "watch_case": final_only_watch_case_source_projection(
                    item.watch_case
                ),
            }
            for item in sorted(bundle.cases, key=lambda value: value.case_id)
        ],
        "replay_observations": sorted(
            bundle.replay_observations,
            key=lambda value: str(value["structured_fields"]["semantic_anchor"]),
        ),
        "privacy_receipt_source_lock": bundle.privacy_receipt_source_lock,
        "lab_note_source_lock": bundle.lab_note_source_lock,
        "rights_note": bundle.rights_note,
    }
    return hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def final_only_watch_case_source_projection(
    value: Mapping[str, object],
) -> Mapping[str, object]:
    """Bind every WatchCase field except the target-plan rebound fields."""

    observed = frozenset(value)
    if not FINAL_ONLY_REBOUND_WATCH_FIELDS.issubset(observed):
        raise RuntimeError("compressed_final_only_watch_case_projection_invalid")
    return {
        field: value[field]
        for field in sorted(observed - FINAL_ONLY_REBOUND_WATCH_FIELDS)
    }


def _prepared_watch_artifact_id(case_id: str, cycle: CompressedCycle) -> str:
    from .compressed_identity import prepared_watch_artifact_id

    return prepared_watch_artifact_id(case_id, cycle)


def _wire_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _timestamp(value: Any) -> str:
    text = _text(value)
    if not text.endswith("Z"):
        raise RuntimeError("compressed_preparation_timestamp_invalid")
    datetime.fromisoformat(text.replace("Z", "+00:00"))
    return text


def _commit(value: Any) -> str:
    text = _text(value)
    if len(text) != 40 or any(item not in "0123456789abcdef" for item in text):
        raise RuntimeError("compressed_preparation_commit_invalid")
    return text


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError("compressed_preparation_text_invalid")
    return value
