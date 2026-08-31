from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from recall.contracts import ContractError, parse_artifact
from recall.ledger.memory import InMemoryLedger
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.scheduler.cohort import MANAGED_COHORT
from recall.scheduler.dayn import DayNScheduler
from recall.scheduler.preparation import (
    LockedPreparationVerifier,
    install_prepared_day,
    load_preparation_bundle,
)


ROOT = Path(__file__).resolve().parents[2]
BUNDLE_SHA = "c460340e75bf186980c8e7a938c5c5e0b4da89599890b2864af7dabdb4ffe841"
IMAGE_DIGEST = "sha256:" + "b" * 64


def _manifest() -> dict[str, object]:
    bundle = load_preparation_bundle(ROOT, expected_sha256=BUNDLE_SHA)
    ledger = InMemoryLedger(privacy_receipt_verifier=LockedPreparationVerifier(bundle))
    now = datetime(2026, 8, 26, 16, 1, tzinfo=timezone.utc)
    install_prepared_day(ledger, bundle, now=now)
    result = DayNScheduler(
        ledger,
        bundle=bundle,
        source_commit=bundle.source_commit,
        image_digest=IMAGE_DIGEST,
    ).trigger(now=now, previous_manifest=None)
    value = ledger.get_artifact(result.manifest_artifact_id)
    assert value is not None
    return value


def _overlap_partition(wire: dict[str, object]) -> None:
    wire["delta"]["excluded_case_ids"] = sorted(
        {
            *wire["delta"]["excluded_case_ids"],
            wire["delta"]["selected_case_ids"][0],
        }
    )


def test_cohort_day_manifest_exact_contract_parses() -> None:
    artifact = parse_artifact(_manifest(), authorized_producers=PRODUCER_REGISTRY)
    assert artifact.schema_name == "CohortDayManifest"
    assert artifact.schema_version == "2.1.0"
    assert artifact.payload.image_digest == IMAGE_DIGEST
    assert artifact.payload.execution_history[-1]["selected_for_date"] == "2026-08-26"


def test_committed_manifest_example_is_v21_and_explicitly_synthetic() -> None:
    wire = json.loads(
        (ROOT / "artifacts/evidence/cohort-manifest-example/day2-manifest.synthetic.json")
        .read_text(encoding="utf-8")
    )
    artifact = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
    expected_digest = "sha256:" + hashlib.sha256(
        b"recall:in-memory-synthetic-manifest-example:v2.1"
    ).hexdigest()
    assert artifact.schema_version == "2.1.0"
    assert artifact.payload.source_commit == _manifest()["source_commit"]
    assert artifact.payload.image_digest == expected_digest


def test_committed_v20_example_reads_without_rewriting_wire() -> None:
    wire = json.loads(
        (ROOT / "artifacts/evidence/cohort-manifest-example/day2-manifest.v2.0.legacy.json")
        .read_text(encoding="utf-8")
    )
    before = copy.deepcopy(wire)
    artifact = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
    assert artifact.schema_version == "2.0.0"
    assert tuple(artifact.payload.execution_history[0]) == (
        "day_index",
        "executed_at",
        "selected_for_date",
        "runs_created",
        "runs_predicted",
    )
    assert wire == before


@pytest.mark.parametrize(
    ("path", "value", "reason"),
    [
        (("execution_history", 1, "selected_for_date"), "2026-08-25", "contract_date_mismatch"),
        (("execution_history", 1, "runs_predicted"), 4, "contract_value_invalid"),
        (("cases", 0, "data_mode"), "CAPTURED_REPLAY", "contract_enum_invalid"),
    ],
)
def test_manifest_rejects_inconsistent_nested_values(path, value, reason) -> None:
    wire = copy.deepcopy(_manifest())
    target = wire
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ContractError, match=reason):
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY, verify_hash=False)


def test_manifest_requires_full_common_envelope() -> None:
    wire = _manifest()
    wire.pop("extensions")
    with pytest.raises(ContractError, match="contract_required_field_missing"):
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY, verify_hash=False)


def test_manifest_rejects_non_digest_image_identity() -> None:
    wire = _manifest()
    wire["image_digest"] = "sha256:not-hex"
    with pytest.raises(ContractError, match="contract_hash_invalid:image_digest"):
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY, verify_hash=False)


def test_zero_predicted_and_zero_created_is_a_valid_silent_day() -> None:
    wire = _manifest()
    wire["cases"] = []
    wire["vcv_anchors"] = []
    wire["delta"]["selected_case_ids"] = []
    wire["delta"]["excluded_case_ids"] = sorted(
        item.case_id for item in MANAGED_COHORT
    )
    wire["delta"]["newly_created_run_ids"] = []
    wire["delta"]["reused_run_ids"] = []
    wire["delta"]["authoritative_run_ids"] = []
    wire["delta"]["runs_predicted"] = 0
    wire["delta"]["prediction_match"] = True
    wire["execution_history"][-1]["runs_created"] = 0
    wire["execution_history"][-1]["runs_predicted"] = 0
    wire["cumulative"] = {
        "daily_cycles": 2,
        "successful_daily_cycles": 2,
        "runs_predicted": 1,
        "runs_created": 1,
        "distinct_execution_dates": 2,
    }
    parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY, verify_hash=False)


def test_predicted_work_with_zero_authoritative_runs_is_a_failed_day() -> None:
    wire = _manifest()
    wire["delta"]["newly_created_run_ids"] = []
    wire["delta"]["reused_run_ids"] = []
    wire["delta"]["authoritative_run_ids"] = []
    wire["delta"]["prediction_match"] = False
    wire["execution_history"][-1]["runs_created"] = 0
    wire["cumulative"] = {
        "daily_cycles": 2,
        "successful_daily_cycles": 1,
        "runs_predicted": 4,
        "runs_created": 1,
        "distinct_execution_dates": 2,
    }
    wire["status"] = "INCOMPLETE"
    artifact = parse_artifact(
        wire, authorized_producers=PRODUCER_REGISTRY, verify_hash=False
    )
    assert artifact.payload.delta["prediction_match"] is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda wire: wire["cumulative"].__setitem__("runs_created", 99),
        lambda wire: wire.__setitem__("trigger_code", "DAY1_MANUAL"),
        lambda wire: wire.__setitem__("managed_history_starts_at_day_index", 1),
        _overlap_partition,
        lambda wire: wire["vcv_anchors"][0].__setitem__(
            "artifact_id", "00000000-0000-4000-8000-000000000001"
        ),
    ],
)
def test_manifest_rejects_semantically_contradictory_claims(mutate) -> None:
    wire = copy.deepcopy(_manifest())
    mutate(wire)
    with pytest.raises(ContractError, match="contract_value_invalid"):
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY, verify_hash=False)


def test_manifest_rejects_case_unrelated_to_selected_partition() -> None:
    wire = copy.deepcopy(_manifest())
    wire["cases"][0]["case_id"] = wire["delta"]["excluded_case_ids"][0]
    wire["cases"] = sorted(wire["cases"], key=lambda item: item["case_id"])
    with pytest.raises(ContractError, match="contract_value_invalid:cases"):
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY, verify_hash=False)


def test_manifest_rejects_reverse_chronological_history() -> None:
    wire = copy.deepcopy(_manifest())
    wire["execution_history"][0]["executed_at"] = "2026-08-27T15:01:00Z"
    wire["execution_history"][0]["selected_for_date"] = "2026-08-27"
    with pytest.raises(
        ContractError,
        match="contract_order_or_uniqueness_invalid:selected_for_date",
    ):
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY, verify_hash=False)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda wire: wire["execution_history"][1].__setitem__(
            "failure_receipt_id", "00000000-0000-4000-8000-000000000001"
        ),
        lambda wire: wire["execution_history"][1].__setitem__(
            "execution_status", "UNKNOWN"
        ),
        lambda wire: wire["execution_history"][1].__setitem__("executed_at", None),
    ],
)
def test_v21_history_rejects_status_receipt_timestamp_contradictions(mutate) -> None:
    wire = copy.deepcopy(_manifest())
    mutate(wire)
    with pytest.raises(ContractError):
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY, verify_hash=False)


def test_v21_incomplete_history_requires_receipt_in_manifest_inputs() -> None:
    wire = copy.deepcopy(_manifest())
    row = wire["execution_history"][0]
    row["execution_status"] = "INCOMPLETE"
    row["executed_at"] = None
    row["runs_created"] = 0
    row["failure_receipt_id"] = "00000000-0000-4000-8000-000000000001"
    wire["cumulative"] = {
        "daily_cycles": 1,
        "successful_daily_cycles": 1,
        "runs_predicted": 4,
        "runs_created": 3,
        "distinct_execution_dates": 1,
    }
    wire["status"] = "INCOMPLETE"
    with pytest.raises(
        ContractError,
        match="contract_value_invalid:execution_history.failure_receipt_id",
    ):
        parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY, verify_hash=False)
