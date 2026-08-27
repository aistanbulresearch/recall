from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid5

from recall.agents.schemas import AssessmentAgentOutput, CitationAuditOutput, EvidenceSnapshotOutput
from recall.contracts import AgentRole, ArtifactStatus, DataMode, canonical_json_bytes, build_artifact
from recall.ledger.producers import PRODUCER_REGISTRY

from .full_audit_models import PreparedRunEvidence, RoleRunResult, TurnTelemetry


def prepared_tool_records(
    evidence: PreparedRunEvidence, *, observed_at: datetime
) -> tuple[dict[str, object], ...]:
    synthetic = {
        "source": "Synthetic preparation bundle",
        "source_record_id": next(iter(evidence.source_cursors.values())),
        "retrieved_at": _timestamp(observed_at),
        "source_version": "compressed-preparation-v2",
        "source_locator": f"bundle://{evidence.case_id}",
        "source_content_hash": sha256(
            canonical_json_bytes(evidence.cloud_bound_payload)
        ).hexdigest(),
        "structured_fields": dict(evidence.cloud_bound_payload),
        "retrieval_status": "PASS",
        "data_mode": DataMode.SYNTHETIC.value,
    }
    replay = [
        {
            "source": item["source"],
            "source_record_id": item["source_record_id"],
            "retrieved_at": item["retrieved_at"],
            "source_version": item["source_version"],
            "source_locator": item["source_locator"],
            "source_content_hash": item["source_content_hash"],
            "structured_fields": dict(item["structured_fields"]),
            "retrieval_status": item["retrieval_status"],
            "data_mode": DataMode.CAPTURED_REPLAY.value,
        }
        for item in evidence.replay_observations
    ]
    return (synthetic, *replay)


def build_registry_receipt(
    *, case_id: str, run_id: str, data_mode: DataMode, now: datetime
) -> dict[str, object]:
    return _artifact(
        "RegistryResolutionReceipt",
        "1.1.0",
        _id(run_id, "registry-resolution"),
        case_id,
        run_id,
        "controller",
        data_mode,
        now,
        {
            "requested_capabilities": [
                "citation.audit", "evidence.assess", "evidence.watch"
            ],
            "bindings": [],
            "resolution_mode": "PINNED_FALLBACK",
            "validation_status": "PASS",
            "reason_codes": [],
        },
    )


def build_started_receipt(
    *,
    case_id: str,
    run_id: str,
    role: AgentRole,
    attempt: int,
    trace_id: str,
    invocation_id: str,
    data_mode: DataMode,
    now: datetime,
) -> dict[str, object]:
    return _agent_receipt(
        case_id=case_id,
        run_id=run_id,
        role=role,
        attempt=attempt,
        status="STARTED",
        trace_id=trace_id,
        invocation_id=invocation_id,
        data_mode=data_mode,
        started_at=now,
        completed_at=None,
        result=None,
        failure_code=None,
    )


def build_completed_receipt(
    *,
    case_id: str,
    run_id: str,
    role: AgentRole,
    attempt: int,
    started_receipt_id: str,
    data_mode: DataMode,
    result: RoleRunResult,
) -> dict[str, object]:
    return _agent_receipt(
        case_id=case_id,
        run_id=run_id,
        role=role,
        attempt=attempt,
        status="COMPLETED",
        trace_id=result.trace_id,
        invocation_id=result.invocation_id,
        data_mode=data_mode,
        started_at=result.started_at,
        completed_at=result.completed_at,
        result=result,
        failure_code=None,
        started_receipt_id=started_receipt_id,
    )


def build_failed_receipt(
    *,
    case_id: str,
    run_id: str,
    role: AgentRole,
    attempt: int,
    started_receipt_id: str,
    trace_id: str,
    invocation_id: str,
    data_mode: DataMode,
    started_at: datetime,
    failed_at: datetime,
    failure_code: str,
    turns: tuple[TurnTelemetry, ...] = (),
    http_429_count: int = 0,
    tool_records: tuple[Mapping[str, str], ...] = (),
) -> dict[str, object]:
    return _agent_receipt(
        case_id=case_id,
        run_id=run_id,
        role=role,
        attempt=attempt,
        status="FAILED",
        trace_id=trace_id,
        invocation_id=invocation_id,
        data_mode=data_mode,
        started_at=started_at,
        completed_at=failed_at,
        result=None,
        failure_code=failure_code,
        started_receipt_id=started_receipt_id,
        partial_turns=turns,
        partial_http_429_count=http_429_count,
        partial_tool_records=tool_records,
    )


def build_watcher_artifacts(
    *,
    run_id: str,
    evidence: PreparedRunEvidence,
    result: RoleRunResult,
    completed_receipt: Mapping[str, object],
) -> tuple[dict[str, object], ...]:
    if not isinstance(result.output, EvidenceSnapshotOutput):
        raise TypeError("watcher_output_invalid")
    created_at = result.completed_at
    records = prepared_tool_records(evidence, observed_at=created_at)
    observations = tuple(
        _artifact(
            "EvidenceObservation",
            "1.0.0",
            _id(run_id, f"observation:{index}"),
            evidence.case_id,
            run_id,
            "evidence-connector",
            DataMode(record["data_mode"]),
            created_at,
            {key: value for key, value in record.items() if key != "data_mode"},
        )
        for index, record in enumerate(records, start=1)
    )
    observation_ids = tuple(str(item["artifact_id"]) for item in observations)
    mixed_mode = (
        DataMode.CAPTURED_REPLAY
        if any(item["data_mode"] == DataMode.CAPTURED_REPLAY.value for item in observations)
        else DataMode.SYNTHETIC
    )
    coverage_status = (
        "PASS"
        if records and all(item["retrieval_status"] == "PASS" for item in records)
        else "FAIL"
    )
    facts = {
        "observation_count": len(records),
        "scope": (
            "synthetic_with_captured_replay"
            if any(
                item["data_mode"] == DataMode.CAPTURED_REPLAY.value
                for item in records
            )
            else "synthetic"
        ),
        "source_classifications": sorted(
            str(item["structured_fields"]["aggregate_classification"])
            for item in records
            if "aggregate_classification" in item["structured_fields"]
        ),
    }
    conflicts: list[dict[str, object]] = []
    snapshot_id = _id(run_id, "evidence-snapshot")
    snapshot = _artifact(
        "EvidenceSnapshot",
        "1.0.0",
        snapshot_id,
        evidence.case_id,
        run_id,
        "evidence-watcher",
        mixed_mode,
        created_at,
        {
            "effective_at": _timestamp(created_at),
            "observation_ids": sorted(observation_ids),
            "coverage_status": coverage_status,
            "source_cursors": dict(sorted(evidence.source_cursors.items())),
            "normalized_facts": facts,
            "conflicts": conflicts,
            "snapshot_hash": sha256(
                canonical_json_bytes(
                    {
                        "observation_ids": sorted(observation_ids),
                        "facts": facts,
                        "conflicts": conflicts,
                    }
                )
            ).hexdigest(),
        },
        observation_ids,
    )
    replay_records = tuple(
        item
        for item in records
        if item["data_mode"] == DataMode.CAPTURED_REPLAY.value
    )
    replay_projections = tuple(
        item["structured_fields"] for item in replay_records
    )
    projected = tuple(
        item
        for item in replay_projections
        if "gene" in item and "transcript_hgvs" in item
    )
    exact = tuple(
        item
        for item in projected
        if _exact_variant_projection(
            evidence.cloud_bound_payload.get("variant"), item
        )
    )
    matching_hashes = sorted(
        str(item["source_content_hash"])
        for item in replay_records
        if item["structured_fields"] in exact
    )
    if exact and coverage_status == "PASS":
        candidate_state = "PRESENT"
        candidate_reasons = ["exact_allele_new_observation"]
    elif replay_records and not projected:
        candidate_state = "UNKNOWN"
        candidate_reasons = ["captured_replay_projection_unavailable"]
    else:
        candidate_state = "ABSENT"
        candidate_reasons = ["exact_allele_absent"]
    candidate = _artifact(
        "CandidateDeltaReceipt",
        "1.0.0",
        _id(run_id, "candidate-delta"),
        evidence.case_id,
        run_id,
        "evidence-normalizer",
        mixed_mode,
        created_at,
        {
            "previous_snapshot_id": None,
            "current_snapshot_id": snapshot_id,
            "exact_allele_match": bool(exact),
            "scope_match": bool(projected),
            "snapshot_complete": coverage_status == "PASS",
            "new_observation_hashes": matching_hashes,
            "candidate_delta_state": candidate_state,
            "reason_codes": candidate_reasons,
        },
        (snapshot_id,),
    )
    return (*observations, snapshot, candidate, dict(completed_receipt))


def _exact_variant_projection(
    raw_variant: object, projection: Mapping[str, object]
) -> bool:
    if not isinstance(raw_variant, Mapping):
        return False
    gene = raw_variant.get("gene")
    hgvs_c = raw_variant.get("hgvs_c")
    if not isinstance(gene, str) or not isinstance(hgvs_c, str):
        return False
    transcript = str(projection.get("transcript_hgvs", ""))
    return projection.get("gene") == gene and transcript.endswith(hgvs_c)


def build_assessor_artifacts(
    *,
    run_id: str,
    evidence: PreparedRunEvidence,
    candidate: Mapping[str, object],
    snapshot: Mapping[str, object],
    result: RoleRunResult,
    completed_receipt: Mapping[str, object],
) -> tuple[dict[str, object], ...]:
    if not isinstance(result.output, AssessmentAgentOutput):
        raise TypeError("assessor_output_invalid")
    output = result.output
    delta_id = _id(run_id, "evidence-delta")
    no_candidate = candidate["candidate_delta_state"] != "PRESENT"
    delta = _artifact(
        "EvidenceDelta", "2.0.0", delta_id, evidence.case_id, run_id,
        "evidence-assessor", evidence.data_mode, result.completed_at,
        {
            "candidate_receipt_id": candidate["artifact_id"],
            "previous_snapshot_id": candidate["previous_snapshot_id"],
            "current_snapshot_id": snapshot["artifact_id"],
            "added_observation_refs": [] if no_candidate else output.evidence_delta.added_observation_refs,
            "removed_observation_refs": [],
            "change_items": [] if no_candidate else output.evidence_delta.change_items,
            "comparison": {
                "classification_changed": "NOT_EVALUATED",
                "classification_source_refs": [],
            },
            "materiality_proposal": "NO_CANDIDATE" if no_candidate else output.evidence_delta.materiality_proposal,
            "uncertainties": output.evidence_delta.uncertainties,
            "counter_evidence_refs": [],
        },
        (str(candidate["artifact_id"]), str(snapshot["artifact_id"])),
    )
    assessment = _artifact(
        "AssessmentReceipt", "1.0.0", _id(run_id, "assessment"),
        evidence.case_id, run_id, "evidence-assessor", evidence.data_mode,
        result.completed_at,
        {
            "delta_id": delta_id,
            "material_claims": [] if no_candidate else output.assessment_receipt.material_claims,
            "counter_evidence_set": [] if no_candidate else output.assessment_receipt.counter_evidence_set,
            "uncertainty_codes": output.assessment_receipt.uncertainty_codes,
            "schema_validation_status": output.assessment_receipt.schema_validation_status,
        },
        (delta_id,),
    )
    return delta, assessment, dict(completed_receipt)


def build_auditor_artifacts(
    *,
    run_id: str,
    evidence: PreparedRunEvidence,
    assessment: Mapping[str, object],
    result: RoleRunResult,
    completed_receipt: Mapping[str, object],
) -> tuple[dict[str, object], ...]:
    if not isinstance(result.output, CitationAuditOutput):
        raise TypeError("auditor_output_invalid")
    output = result.output
    expected_claim_ids = tuple(sorted(str(item) for item in assessment["material_claims"]))
    model_claim_ids = tuple(sorted(item.claim_id for item in output.claim_results))
    tool_claim_ids = tuple(
        sorted(
            key.removeprefix("refetch:")
            for key in result.tool_results
            if key.startswith("refetch:")
        )
    )
    claims = [
        _deterministic_claim_verdict(
            claim_id,
            result.tool_results.get(f"refetch:{claim_id}"),
        )
        for claim_id in expected_claim_ids
    ]
    complete = (
        len(set(model_claim_ids)) == len(model_claim_ids)
        and model_claim_ids == expected_claim_ids
        and tool_claim_ids == expected_claim_ids
        and output.audit_status == "COMPLETE"
    )
    audit_status = "COMPLETE" if complete else "INCOMPLETE"
    refetched_sources = [
        dict(item["refetched_source"])
        for item in claims
        if item["refetched_source"] is not None
    ]
    rejected = sorted(
        item["claim_id"] for item in claims if item["verdict"] != "VERIFIED"
    )
    audit = _artifact(
        "CitationAuditReceipt", "1.0.0", _id(run_id, "citation-audit"),
        evidence.case_id, run_id, "citation-auditor", evidence.data_mode,
        result.completed_at,
        {
            "assessment_id": assessment["artifact_id"],
            "audit_status": audit_status,
            "claim_verdicts": claims,
            "metadata_refetches": refetched_sources,
            "counter_evidence_coverage": (
                output.counter_evidence_coverage if complete else "FAIL"
            ),
            "audit_completeness": "PASS" if complete else "FAIL",
            "rejected_claim_ids": rejected,
        },
        (str(assessment["artifact_id"]),),
        status=(
            ArtifactStatus.VALID
            if audit_status == "COMPLETE"
            else ArtifactStatus.INCOMPLETE
        ),
    )
    return audit, dict(completed_receipt)


def _deterministic_claim_verdict(
    claim_id: str,
    raw: Mapping[str, object] | None,
) -> dict[str, object]:
    if raw is None or raw.get("claim_id") != claim_id:
        return {
            "claim_id": claim_id,
            "verdict": "UNAVAILABLE",
            "reason_codes": ["citation_refetch_result_missing"],
            "refetched_source": None,
        }
    verdict = str(raw.get("verdict", ""))
    source = raw.get("refetched_source")
    reasons = raw.get("reason_codes")
    if (
        verdict not in {"VERIFIED", "MISMATCH", "UNAVAILABLE"}
        or not isinstance(reasons, list)
        or not reasons
        or any(not isinstance(item, str) or not item for item in reasons)
        or (verdict == "UNAVAILABLE") is not (source is None)
        or (source is not None and not isinstance(source, Mapping))
    ):
        return {
            "claim_id": claim_id,
            "verdict": "UNAVAILABLE",
            "reason_codes": ["citation_refetch_result_invalid"],
            "refetched_source": None,
        }
    return {
        "claim_id": claim_id,
        "verdict": verdict,
        "reason_codes": list(reasons),
        "refetched_source": None if source is None else dict(source),
    }


def _agent_receipt(
    *, case_id: str, run_id: str, role: AgentRole, attempt: int, status: str,
    trace_id: str, invocation_id: str, data_mode: DataMode,
    started_at: datetime, completed_at: datetime | None,
    result: RoleRunResult | None, failure_code: str | None,
    started_receipt_id: str | None = None,
    partial_turns: tuple[TurnTelemetry, ...] = (),
    partial_http_429_count: int = 0,
    partial_tool_records: tuple[Mapping[str, str], ...] = (),
) -> dict[str, object]:
    artifact_id = _id(run_id, f"agent:{role.value}:{attempt}:{status}")
    latency = None if completed_at is None else round((completed_at - started_at).total_seconds() * 1000)
    turns = partial_turns if result is None else result.turns
    http_429_count = (
        partial_http_429_count if result is None else result.http_429_count
    )
    tool_records = tuple(
        sorted(
            partial_tool_records if result is None else result.tool_records,
            key=lambda item: (item["call_id"], item["tool_id"]),
        )
    )
    call_ids = () if result is None else tuple(sorted(result.tool_call_ids))
    response_ids = () if result is None else tuple(sorted(result.tool_response_ids))
    dependency_ids = () if started_receipt_id is None else tuple(
        sorted(
            {
                started_receipt_id,
                *(item["authorization_receipt_id"] for item in tool_records),
            }
        )
    )
    return _artifact(
        "AgentExecutionReceipt", "1.0.0", artifact_id, case_id, run_id,
        "controller-agent-executor", data_mode, completed_at or started_at,
        {
            "execution_profile": "FULL_AUDIT_V1", "agent_role": role.value,
            "attempt": attempt, "execution_status": status,
            "runtime_class": "IN_PROCESS_ADK_CLOUD_RUN",
            "model_id": "gemini-3.7-flash",
            "model_revision": "NOT_VERIFIED_MUTABLE_ALIAS:gemini-3.7-flash",
            "endpoint_class": "VERTEX_AI_GLOBAL", "location": "global",
            "trace_id": trace_id, "invocation_id": invocation_id,
            "started_at": _timestamp(started_at),
            "completed_at": None if completed_at is None else _timestamp(completed_at),
            "latency_ms": latency,
            "turns": [item.to_wire() for item in turns],
            "http_429_count": http_429_count,
            "tool_call_ids": list(call_ids),
            "tool_response_ids": list(response_ids),
            "tool_records": [dict(item) for item in tool_records],
            "started_receipt_id": started_receipt_id,
            "failure_code": failure_code,
        },
        dependency_ids,
        status=ArtifactStatus.VALID if status != "FAILED" else ArtifactStatus.INCOMPLETE,
    )


def _artifact(
    schema: str, version: str, artifact_id: str, case_id: str, run_id: str,
    identity: str, data_mode: DataMode, now: datetime,
    payload: Mapping[str, object], inputs: Sequence[str] = (),
    *, status: ArtifactStatus = ArtifactStatus.VALID,
) -> dict[str, object]:
    return build_artifact(
        schema_name=schema, schema_version=version, artifact_id=artifact_id,
        case_id=case_id, run_id=run_id,
        producer={"component": identity, "version": version, "identity": identity},
        created_at=_timestamp(now), input_artifact_ids=tuple(sorted(inputs)),
        data_mode=data_mode, status=status, payload=payload,
        authorized_producers=PRODUCER_REGISTRY,
    )


def _id(run_id: str, label: str) -> str:
    return str(uuid5(UUID(run_id), label))


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
