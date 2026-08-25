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

from .cohort import MANAGED_COHORT, REPLAY_ANCHORS


BUNDLE_VERSION = "1.0.0"
DEFAULT_BUNDLE_PATH = Path(
    "artifacts/evidence/cohort-preparation-v1/preparation-bundle.json"
)


@dataclass(frozen=True, slots=True)
class PreparedCase:
    case_id: str
    cloud_bound_payload: Mapping[str, object]
    privacy_receipt: Mapping[str, object]
    watch_case: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class CohortPreparationBundle:
    prepared_at: str
    source_commit: str
    rights_note: str
    cases: tuple[PreparedCase, ...]
    replay_observations: tuple[Mapping[str, object], ...]
    bundle_sha256: str

    @property
    def receipt_locks(self) -> Mapping[str, tuple[str, str]]:
        return {
            str(item.privacy_receipt["artifact_id"]): (
                str(item.privacy_receipt["content_hash"]),
                _wire_sha256(item.privacy_receipt),
            )
            for item in self.cases
        }

    @property
    def watch_locks(self) -> Mapping[str, tuple[str, str]]:
        return {
            str(item.watch_case["artifact_id"]): (
                str(item.watch_case["content_hash"]),
                _wire_sha256(item.watch_case),
            )
            for item in self.cases
        }

    @property
    def observations_by_vcv(self) -> Mapping[str, Mapping[str, object]]:
        return {
            str(item["structured_fields"]["semantic_anchor"]): item
            for item in self.replay_observations
        }


class LockedPreparationVerifier:
    """Verify only exact, owner-committed lab-prepared PrivacyReceipts."""

    def __init__(self, bundle: CohortPreparationBundle) -> None:
        self._locks = bundle.receipt_locks

    def __call__(self, value: Mapping[str, Any]) -> bool:
        try:
            parsed = parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
        except Exception:
            return False
        expected = self._locks.get(parsed.artifact_id)
        return (
            parsed.schema_name == "PrivacyReceipt"
            and parsed.data_mode.value == "SYNTHETIC"
            and parsed.producer.identity == "privacy-gate"
            and parsed.payload.decision.value == "ACCEPTED"
            and expected
            == (parsed.content_hash, _wire_sha256(value))
        )


def load_preparation_bundle(
    repo_root: Path,
    *,
    expected_sha256: str,
    path: Path = DEFAULT_BUNDLE_PATH,
) -> CohortPreparationBundle:
    full_path = (repo_root / path).resolve()
    if not full_path.is_relative_to(repo_root.resolve()):
        raise RuntimeError("cohort_preparation_path_escape")
    raw = full_path.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != expected_sha256:
        raise RuntimeError("cohort_preparation_bundle_hash_mismatch")
    value = json.loads(raw.decode("utf-8"))
    if set(value) != {
        "schema_version",
        "prepared_at",
        "source_commit",
        "rights_note",
        "cases",
        "replay_observations",
    } or value["schema_version"] != BUNDLE_VERSION:
        raise RuntimeError("cohort_preparation_bundle_shape_invalid")
    cases = tuple(_parse_prepared_case(item) for item in value["cases"])
    observations = tuple(
        _parse_replay_observation(item) for item in value["replay_observations"]
    )
    bundle = CohortPreparationBundle(
        prepared_at=_timestamp(value["prepared_at"]),
        source_commit=_commit(value["source_commit"]),
        rights_note=_text(value["rights_note"], "rights_note"),
        cases=cases,
        replay_observations=observations,
        bundle_sha256=actual_sha256,
    )
    _validate_complete_bundle(bundle)
    return bundle


def install_prepared_day(
    ledger: LedgerPort,
    bundle: CohortPreparationBundle,
    *,
    now: datetime,
) -> Mapping[str, int]:
    verifier = LockedPreparationVerifier(bundle)
    receipts_created = 0
    cases_created = 0
    anchors_created = 0
    for item in bundle.cases:
        before = ledger.get_artifact(str(item.privacy_receipt["artifact_id"]))
        ledger.append_artifact(item.privacy_receipt)
        receipts_created += int(before is None)
        if not verifier(item.privacy_receipt):
            raise RuntimeError("cohort_preparation_receipt_lock_failed")
        _record, created = ledger.create_watch_case(
            item.watch_case,
            cloud_bound_payload=item.cloud_bound_payload,
            now=now,
        )
        cases_created += int(created)
    for observation in bundle.replay_observations:
        before = ledger.get_artifact(str(observation["artifact_id"]))
        ledger.append_artifact(observation)
        anchors_created += int(before is None)
    verify_prepared_day(ledger, bundle)
    return {
        "privacy_receipts_created": receipts_created,
        "watch_cases_created": cases_created,
        "replay_observations_created": anchors_created,
    }


def verify_prepared_day(
    ledger: LedgerPort, bundle: CohortPreparationBundle
) -> None:
    for item in bundle.cases:
        record = ledger.get_watch_case(item.case_id)
        if record is None or record.artifact_id != item.watch_case["artifact_id"]:
            raise RuntimeError("cohort_prepared_watch_case_missing")
        wire = ledger.get_artifact(record.artifact_id)
        expected = bundle.watch_locks[record.artifact_id]
        if wire is None or (
            str(wire["content_hash"]), _wire_sha256(wire)
        ) != expected:
            raise RuntimeError("cohort_prepared_watch_case_lock_failed")
        receipt_id = str(item.privacy_receipt["artifact_id"])
        receipt = ledger.get_artifact(receipt_id)
        if receipt is None or not LockedPreparationVerifier(bundle)(receipt):
            raise RuntimeError("cohort_prepared_receipt_missing")
    for observation in bundle.replay_observations:
        wire = ledger.get_artifact(str(observation["artifact_id"]))
        if wire is None or _wire_sha256(wire) != _wire_sha256(observation):
            raise RuntimeError("cohort_prepared_anchor_missing")


def _parse_prepared_case(value: Any) -> PreparedCase:
    if not isinstance(value, Mapping) or set(value) != {
        "case_id",
        "cloud_bound_payload",
        "privacy_receipt",
        "watch_case",
    }:
        raise RuntimeError("cohort_prepared_case_shape_invalid")
    receipt = parse_artifact(
        value["privacy_receipt"], authorized_producers=PRODUCER_REGISTRY
    )
    watch = parse_artifact(value["watch_case"], authorized_producers=PRODUCER_REGISTRY)
    cloud = parse_cloud_bound_payload(value["cloud_bound_payload"])
    if (
        receipt.schema_name != "PrivacyReceipt"
        or watch.schema_name != "WatchCase"
        or value["case_id"] != receipt.case_id
        or value["case_id"] != watch.case_id
        or cloud.case_token != value["case_id"]
        or watch.input_artifact_ids != (receipt.artifact_id,)
    ):
        raise RuntimeError("cohort_prepared_case_binding_invalid")
    return PreparedCase(
        case_id=str(value["case_id"]),
        cloud_bound_payload=cloud.to_wire(),
        privacy_receipt=receipt.to_wire(),
        watch_case=watch.to_wire(),
    )


def _parse_replay_observation(value: Any) -> Mapping[str, object]:
    artifact = parse_artifact(value, authorized_producers=PRODUCER_REGISTRY)
    if (
        artifact.schema_name != "EvidenceObservation"
        or artifact.data_mode.value != "CAPTURED_REPLAY"
        or artifact.producer.identity != "evidence-connector"
    ):
        raise RuntimeError("cohort_replay_observation_invalid")
    return artifact.to_wire()


def _validate_complete_bundle(bundle: CohortPreparationBundle) -> None:
    if tuple(item.case_id for item in bundle.cases) != tuple(
        sorted(item.case_id for item in MANAGED_COHORT)
    ):
        raise RuntimeError("cohort_preparation_case_set_mismatch")
    expected_anchors = {item.vcv: item for item in REPLAY_ANCHORS}
    if set(bundle.observations_by_vcv) != set(expected_anchors):
        raise RuntimeError("cohort_preparation_anchor_set_mismatch")
    for vcv, wire in bundle.observations_by_vcv.items():
        anchor = expected_anchors[vcv]
        if (
            wire["source_content_hash"] != anchor.sha256
            or wire["structured_fields"]["capture_path"] != anchor.capture_path
        ):
            raise RuntimeError("cohort_preparation_anchor_lock_mismatch")


def _wire_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RuntimeError("cohort_preparation_timestamp_invalid")
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _commit(value: Any) -> str:
    text = _text(value, "source_commit")
    if len(text) != 40 or any(character not in "0123456789abcdef" for character in text):
        raise RuntimeError("cohort_preparation_commit_invalid")
    return text


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"cohort_preparation_text_invalid:{field}")
    return value
