from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Sequence

from recall.contracts import (
    canonical_json_bytes,
    content_hash,
    parse_artifact,
    parse_cloud_bound_payload,
)
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.scheduler.compressed_cohort import cases_for_cycle
from recall.scheduler.compressed_identity import prepared_watch_artifact_id
from recall.scheduler.compressed_plan import (
    FINAL_ONLY_PLAN_SHA256,
    PLAN10_C6_PHASE_TIMEOUTS,
    PLAN10_C6_WINDOW_DURATION,
    PLAN9_HISTORICAL_SHA256,
    parse_compressed_plan,
)
from recall.scheduler.compressed_preparation import (
    FINAL_ONLY_LAB_NOTE_SOURCE_LOCK,
    FINAL_ONLY_PRIVACY_SOURCE_LOCK,
    FINAL_ONLY_SOURCE_BUNDLE_COMMIT,
    FINAL_ONLY_SOURCE_BUNDLE_SHA256,
    FINAL_ONLY_SOURCE_MATERIAL_SHA256,
    _require_full_audit_privacy_receipt,
    final_only_watch_case_source_projection,
)


@dataclass(frozen=True, slots=True)
class FinalOnlyHistoricalInput:
    cycle_id: str
    evidence_role: str
    execution_status: str
    plan_sha256: str
    collection_prefix: str
    manifest_artifact_id: str
    manifest_content_hash: str
    mode_receipt_artifact_id: str | None
    mode_receipt_content_hash: str | None

    def to_wire(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FinalOnlyCandidate:
    plan_bytes: bytes
    plan_sha256: str


@dataclass(frozen=True, slots=True)
class FinalOnlyPreparationCandidate:
    bundle_bytes: bytes
    bundle_sha256: str
    source_material_sha256: str


def render_final_only_candidate(
    source_plan_bytes: bytes,
    *,
    historical_evidence: Sequence[FinalOnlyHistoricalInput],
    c6_window_start: str,
    c6_window_end: str,
) -> FinalOnlyCandidate:
    evidence = tuple(historical_evidence)
    _validate_evidence_topology(evidence)
    start = _timestamp(c6_window_start)
    end = _timestamp(c6_window_end)
    if end - start != PLAN10_C6_WINDOW_DURATION:
        raise RuntimeError("final_only_c6_window_duration_invalid")

    source_sha = hashlib.sha256(source_plan_bytes).hexdigest()
    if source_sha == FINAL_ONLY_PLAN_SHA256:
        source = json.loads(source_plan_bytes)
        parsed = parse_compressed_plan(source, sha256=source_sha)
        supersession = source.get("supersession")
        if (
            parsed.schema_version != "2.8.0"
            or parsed.by_id("c6").window_start != start
            or parsed.by_id("c6").window_end != end
            or not isinstance(supersession, dict)
            or supersession.get("historical_evidence")
            != [item.to_wire() for item in evidence]
        ):
            raise RuntimeError("final_only_applied_plan_mismatch")
        return FinalOnlyCandidate(source_plan_bytes, source_sha)
    if source_sha != PLAN9_HISTORICAL_SHA256:
        raise RuntimeError("final_only_source_plan_sha_invalid")

    source = json.loads(source_plan_bytes)
    candidate = deepcopy(source)
    candidate["schema_version"] = "2.8.0"
    candidate["supersession"] = {
        "mode": "FINAL_ONLY_TIMEBOX",
        "superseded_plan_sha256": PLAN9_HISTORICAL_SHA256,
        "owner_decision": "RETIRE_RAMP_DUE_TIMEBOX_AND_AUTHORIZE_FINAL_456",
        "reason_code": "RAMP_TIMEBOX_EXHAUSTED",
        "historical_evidence": [item.to_wire() for item in evidence],
        "retired_cycles": [
            {
                "cycle_id": cycle_id,
                "state": "RETIRED_TIMEBOX",
                "execution_status": "NOT_EXECUTED",
                "runs_created": 0,
            }
            for cycle_id in ("c4", "c5")
        ],
    }
    cycles = {item["cycle_id"]: item for item in candidate["cycles"]}
    for cycle_id, activation in (
        ("c1", "IMMUTABLE_EXECUTED"),
        ("c2", "IMMUTABLE_EXECUTED"),
        ("c3", "HISTORICAL_ATTEMPTS_PRESERVED"),
        ("c4", "RETIRED_TIMEBOX"),
        ("c5", "RETIRED_TIMEBOX"),
        ("c6", "ACTIVE"),
    ):
        cycles[cycle_id]["activation"] = activation
    for cycle_id in ("c4", "c5", "c6"):
        cycles[cycle_id]["predecessor"] = None
    c6 = cycles["c6"]
    c6["window_start"] = c6_window_start
    c6["window_end"] = c6_window_end
    c6["epoch_label"] = "PLAN6_FINAL_456_REASSESSMENT_ACTIVE"
    (
        c6["execution_timeout_seconds"],
        c6["write_timeout_seconds"],
        c6["agent_timeout_seconds"],
    ) = PLAN10_C6_PHASE_TIMEOUTS
    rendered = (
        json.dumps(candidate, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    digest = hashlib.sha256(rendered).hexdigest()
    parsed = parse_compressed_plan(candidate, sha256=digest)
    if parsed.by_id("c6").window_start != start or parsed.supersession is None:
        raise RuntimeError("final_only_candidate_verification_failed")
    return FinalOnlyCandidate(rendered, digest)


def render_final_only_preparation_candidate(
    source_bundle_bytes: bytes,
    *,
    plan_candidate: FinalOnlyCandidate,
    prepared_at: str,
    expected_source_bundle_sha256: str = FINAL_ONLY_SOURCE_BUNDLE_SHA256,
    expected_source_material_sha256: str = FINAL_ONLY_SOURCE_MATERIAL_SHA256,
) -> FinalOnlyPreparationCandidate:
    source_digest = hashlib.sha256(source_bundle_bytes).hexdigest()
    if source_digest != expected_source_bundle_sha256:
        raise RuntimeError("final_only_source_bundle_sha_invalid")
    prepared = _timestamp_text(prepared_at)
    plan = parse_compressed_plan(
        json.loads(plan_candidate.plan_bytes),
        sha256=plan_candidate.plan_sha256,
    )
    c6 = plan.by_id("c6")
    if plan.schema_version != "2.8.0" or c6.activation != "ACTIVE":
        raise RuntimeError("final_only_preparation_plan_invalid")

    source = json.loads(source_bundle_bytes)
    required_source_fields = {
        "schema_version",
        "prepared_at",
        "source_commit",
        "plan_sha256",
        "rights_note",
        "cases",
        "replay_observations",
        "legacy_failure_receipt",
        "privacy_receipt_source_lock",
        "lab_note_source_lock",
    }
    if (
        not isinstance(source, dict)
        or set(source) != required_source_fields
        or source["schema_version"] != "2.2.0"
        or source["source_commit"] != FINAL_ONLY_SOURCE_BUNDLE_COMMIT
        or source["plan_sha256"] != PLAN9_HISTORICAL_SHA256
        or source["privacy_receipt_source_lock"]
        != FINAL_ONLY_PRIVACY_SOURCE_LOCK
        or source["lab_note_source_lock"]
        != FINAL_ONLY_LAB_NOTE_SOURCE_LOCK
    ):
        raise RuntimeError("final_only_source_bundle_contract_invalid")

    expected_cases = cases_for_cycle(c6)
    expected_by_case = {item.case_id: item for item in expected_cases}
    source_cases = sorted(
        (
            item
            for item in source["cases"]
            if isinstance(item, Mapping) and item.get("cycle_id") == "c6"
        ),
        key=lambda item: str(item["case_id"]),
    )
    if tuple(item["case_id"] for item in source_cases) != tuple(
        item.case_id for item in expected_cases
    ):
        raise RuntimeError("final_only_source_case_set_invalid")

    cases: list[dict[str, object]] = []
    for item in source_cases:
        case_id = str(item["case_id"])
        expected = expected_by_case[case_id]
        cloud = parse_cloud_bound_payload(item["cloud_bound_payload"])
        receipt = parse_artifact(
            item["privacy_receipt"], authorized_producers=PRODUCER_REGISTRY
        )
        source_watch = parse_artifact(
            item["watch_case"], authorized_producers=PRODUCER_REGISTRY
        )
        _require_full_audit_privacy_receipt(receipt.to_wire())
        if (
            cloud.case_token != case_id
            or receipt.case_id != case_id
            or source_watch.case_id != case_id
            or source_watch.input_artifact_ids != (receipt.artifact_id,)
        ):
            raise RuntimeError("final_only_source_case_binding_invalid")
        watch = deepcopy(source_watch.to_wire())
        watch.update(
            {
                "artifact_id": prepared_watch_artifact_id(case_id, c6),
                "created_at": prepared,
                "monitoring_started_at": prepared,
                "next_scan_at": c6.schedule_epoch,
                "source_cursors": {"synthetic-source": expected.cursor},
            }
        )
        watch["content_hash"] = content_hash(watch)
        parsed_watch = parse_artifact(
            watch, authorized_producers=PRODUCER_REGISTRY
        )
        if (
            parsed_watch.artifact_id
            != prepared_watch_artifact_id(case_id, c6)
            or final_only_watch_case_source_projection(parsed_watch.to_wire())
            != final_only_watch_case_source_projection(source_watch.to_wire())
        ):
            raise RuntimeError("final_only_watch_case_rebuild_invalid")
        cases.append(
            {
                "case_id": case_id,
                "cycle_id": "c6",
                "cloud_bound_payload": cloud.to_wire(),
                "privacy_receipt": receipt.to_wire(),
                "watch_case": parsed_watch.to_wire(),
            }
        )

    expected_anchors = {
        item.vcv for item in expected_cases if item.vcv is not None
    }
    observations = sorted(
        (
            parse_artifact(item, authorized_producers=PRODUCER_REGISTRY).to_wire()
            for item in source["replay_observations"]
            if isinstance(item, Mapping)
            and item.get("structured_fields", {}).get("semantic_anchor")
            in expected_anchors
        ),
        key=lambda item: str(item["structured_fields"]["semantic_anchor"]),
    )
    if {
        item["structured_fields"]["semantic_anchor"] for item in observations
    } != expected_anchors:
        raise RuntimeError("final_only_source_anchor_set_invalid")

    material = {
        "cases": [
            {
                "case_id": item["case_id"],
                "cloud_bound_payload": item["cloud_bound_payload"],
                "privacy_receipt": item["privacy_receipt"],
                "watch_case": final_only_watch_case_source_projection(
                    item["watch_case"]
                ),
            }
            for item in cases
        ],
        "replay_observations": observations,
        "privacy_receipt_source_lock": source["privacy_receipt_source_lock"],
        "lab_note_source_lock": source["lab_note_source_lock"],
        "rights_note": source["rights_note"],
    }
    material_digest = hashlib.sha256(canonical_json_bytes(material)).hexdigest()
    if material_digest != expected_source_material_sha256:
        raise RuntimeError("final_only_source_material_sha_invalid")
    bundle = {
        "schema_version": "2.3.0",
        "prepared_at": prepared,
        "input_source_commit": source["source_commit"],
        "input_plan_sha256": source["plan_sha256"],
        "plan_sha256": plan.sha256,
        "source_bundle_sha256": source_digest,
        "source_material_sha256": material_digest,
        "rights_note": source["rights_note"],
        "cases": cases,
        "replay_observations": observations,
        "privacy_receipt_source_lock": source["privacy_receipt_source_lock"],
        "lab_note_source_lock": source["lab_note_source_lock"],
    }
    rendered = (
        json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    return FinalOnlyPreparationCandidate(
        bundle_bytes=rendered,
        bundle_sha256=hashlib.sha256(rendered).hexdigest(),
        source_material_sha256=material_digest,
    )


def _validate_evidence_topology(
    values: tuple[FinalOnlyHistoricalInput, ...],
) -> None:
    observed = tuple(
        (item.cycle_id, item.evidence_role, item.execution_status)
        for item in values
    )
    if (
        len(values) < 3
        or observed[:2]
        != (
            ("c1", "IMMUTABLE_EXECUTED", "COMPLETE"),
            ("c2", "IMMUTABLE_EXECUTED", "COMPLETE"),
        )
        or any(
            item != ("c3", "HISTORICAL_ATTEMPT", "INCOMPLETE")
            for item in observed[2:]
        )
    ):
        raise RuntimeError("final_only_evidence_topology_invalid")


def _timestamp(value: str) -> datetime:
    if not value.endswith("Z"):
        raise RuntimeError("final_only_window_timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError("final_only_window_timestamp_invalid") from exc
    if parsed.microsecond:
        raise RuntimeError("final_only_window_timestamp_invalid")
    return parsed


def _timestamp_text(value: str) -> str:
    return _timestamp(value).isoformat().replace("+00:00", "Z")
