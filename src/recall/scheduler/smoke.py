from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from recall.agents.full_audit import FullAuditCoordinator
from recall.contracts import (
    AgentRole,
    ArtifactStatus,
    DataMode,
    build_artifact,
    canonical_json_bytes,
    parse_artifact,
)
from recall.ledger.port import LedgerPort
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.contracts.enums import ScanRunEventCode

from .compressed import CompressedCycleScheduler
from .compressed_batch import execute_verified_batch
from .compressed_cohort import CompressedCohortCase, cases_for_cycle
from .compressed_plan import CompressedCycle, CompressedPlan
from .compressed_preparation import (
    CompressedPreparationBundle,
    CompressedPreparationVerifier,
)
from .full_audit_phase import execute_full_audit_phase


SMOKE_SCHEMA_NAME = "IsolatedSmokeResult"
SMOKE_SCHEMA_VERSION = "1.0.0"
SMOKE_CONCURRENCY = 2
SMOKE_PROVIDER_MAX_429_RETRIES = 0
SMOKE_AGGREGATE_TURN_LIMIT = 26
SMOKE_EXECUTION_TIMEOUT_SECONDS = 28_800
SMOKE_WRITE_TIMEOUT_SECONDS = 1_800
SMOKE_AGENT_TIMEOUT_SECONDS = 27_000
SMOKE_MODE_CASE_COUNTS = {"positive": 4, "negative": 1}
SMOKE_MODE_TURN_LIMITS = {"positive": 24, "negative": 2}
SMOKE_NEGATIVE_PROBE = "WATCHER_SCHEMA_INVALID_AFTER_TOOL_ROUND_TRIP"

_SMOKE_ID = re.compile(r"^[a-z0-9]{8,32}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class IsolatedSmokeContract:
    mode: str
    smoke_id: str
    collection_prefix: str
    source_commit: str
    plan_sha256: str
    image_digest: str
    preparation_bundle_sha256: str
    job_max_retries: int

    @property
    def case_count(self) -> int:
        return SMOKE_MODE_CASE_COUNTS[self.mode]

    @property
    def turn_limit(self) -> int:
        return SMOKE_MODE_TURN_LIMITS[self.mode]


def smoke_tick_run_id(collection_prefix: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"recall:smoke:{collection_prefix}:tick"))


def smoke_manifest_artifact_id(collection_prefix: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{smoke_tick_run_id(collection_prefix)}:manifest"))


def smoke_mode_receipt_artifact_id(collection_prefix: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{smoke_tick_run_id(collection_prefix)}:mode"))


def derive_smoke_prefix(
    *, source_commit: str, plan_sha256: str, mode: str, smoke_id: str
) -> str:
    if not _SOURCE_COMMIT.fullmatch(source_commit):
        raise RuntimeError("smoke_source_commit_invalid")
    if not _SHA256.fullmatch(plan_sha256):
        raise RuntimeError("smoke_plan_sha256_invalid")
    if mode not in SMOKE_MODE_CASE_COUNTS:
        raise RuntimeError("smoke_mode_invalid")
    if not _SMOKE_ID.fullmatch(smoke_id):
        raise RuntimeError("smoke_id_invalid")
    return (
        f"dev_recall_smoke_{source_commit[:12]}_{plan_sha256[:12]}_"
        f"{mode}_{smoke_id}_"
    )


def build_smoke_contract(
    *,
    mode: str,
    smoke_id: str,
    collection_prefix: str,
    source_commit: str,
    plan_sha256: str,
    image_digest: str,
    expected_plan_sha256: str,
    expected_image_digest: str,
    preparation_bundle_sha256: str,
    job_max_retries: str,
) -> IsolatedSmokeContract:
    if expected_plan_sha256 != plan_sha256:
        raise RuntimeError("smoke_plan_sha256_mismatch")
    if (
        not _IMAGE_DIGEST.fullmatch(expected_image_digest)
        or expected_image_digest != image_digest
    ):
        raise RuntimeError("smoke_image_digest_mismatch")
    if job_max_retries != "0":
        raise RuntimeError("smoke_job_max_retries_invalid")
    expected_prefix = derive_smoke_prefix(
        source_commit=source_commit,
        plan_sha256=plan_sha256,
        mode=mode,
        smoke_id=smoke_id,
    )
    if collection_prefix != expected_prefix:
        raise RuntimeError("smoke_collection_prefix_mismatch")
    if not collection_prefix.startswith("dev_recall_smoke_"):
        raise RuntimeError("smoke_collection_prefix_invalid")
    return IsolatedSmokeContract(
        mode=mode,
        smoke_id=smoke_id,
        collection_prefix=collection_prefix,
        source_commit=source_commit,
        plan_sha256=plan_sha256,
        image_digest=image_digest,
        preparation_bundle_sha256=preparation_bundle_sha256,
        job_max_retries=0,
    )


def select_smoke_cases(
    plan: CompressedPlan, bundle: CompressedPreparationBundle, *, mode: str
) -> tuple[CompressedCohortCase, ...]:
    if plan.schema_version != "2.8.0":
        raise RuntimeError("smoke_final_only_plan_required")
    cycle = plan.by_id("c6")
    candidates = tuple(sorted(cases_for_cycle(cycle), key=lambda item: item.case_id))
    prepared = {
        item.case_id
        for item in bundle.cases
        if item.cycle_id == cycle.cycle_id
    }
    if len(candidates) != 456 or prepared != {item.case_id for item in candidates}:
        raise RuntimeError("smoke_c6_case_set_invalid")
    if mode == "positive":
        selected = candidates[:4]
    elif mode == "negative":
        selected = candidates[4:5]
    else:
        raise RuntimeError("smoke_mode_invalid")
    if len(selected) != SMOKE_MODE_CASE_COUNTS[mode]:
        raise RuntimeError("smoke_case_count_invalid")
    return selected


def execute_isolated_smoke(
    *,
    contract: IsolatedSmokeContract,
    ledger: LedgerPort,
    plan: CompressedPlan,
    bundle: CompressedPreparationBundle,
    coordinator: FullAuditCoordinator,
    now: datetime,
    refetch_fetcher: Any = None,
) -> dict[str, object]:
    cycle = plan.by_id("c6")
    if contract.plan_sha256 != plan.sha256:
        raise RuntimeError("smoke_plan_sha256_mismatch")
    execution_deadline_at, agent_deadline_at = _smoke_deadlines(
        contract=contract,
        plan=plan,
        cycle=cycle,
        now=now,
    )
    _require_empty_namespace(ledger)
    selected = select_smoke_cases(plan, bundle, mode=contract.mode)
    _install_smoke_cases(ledger, bundle, cycle, selected, now=now)
    scheduler = CompressedCycleScheduler(
        ledger,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        source_commit=contract.source_commit,
        image_digest=contract.image_digest,
        full_audit_coordinator=coordinator,
        refetch_fetcher=refetch_fetcher,
        clock=lambda: now,
    )
    batch = execute_verified_batch(
        selected,
        create_one=lambda item: scheduler._create_case(
            item,
            now=now,
            smoke_execution_deadline_at=execution_deadline_at,
            smoke_collection_prefix=contract.collection_prefix,
        ),
        ledger=ledger,
        started_at=now,
    )
    outcomes = execute_full_audit_phase(
        batch.outcomes,
        coordinator=coordinator,
        bundle=bundle,
        cycle=cycle,
        concurrency=SMOKE_CONCURRENCY,
        refetch_fetcher=refetch_fetcher,
        checkpoint_ledger=ledger,
        plan_sha256=plan.sha256,
        expected_manifest_id=smoke_manifest_artifact_id(
            contract.collection_prefix
        ),
        checkpoint_run_id=smoke_tick_run_id(contract.collection_prefix),
        agent_deadline_at=agent_deadline_at,
        clock=lambda: now,
    )
    result = collect_isolated_smoke_result(
        contract=contract,
        ledger=ledger,
        selected_case_ids=tuple(item.case_id for item in selected),
        run_ids=tuple(item.run_record.run_id for item in batch.outcomes),
        cost_snapshot=coordinator.cost_snapshot(),
        expected_outcomes=outcomes.outcomes,
    )
    return _persist_smoke_artifacts(
        ledger=ledger,
        contract=contract,
        result=result,
        now=now,
    )


def _smoke_deadlines(
    *,
    contract: IsolatedSmokeContract,
    plan: CompressedPlan,
    cycle: CompressedCycle,
    now: datetime,
) -> tuple[datetime, datetime]:
    if (
        not isinstance(now, datetime)
        or now.tzinfo is None
        or now.utcoffset() != timedelta(0)
        or plan.schema_version != "2.8.0"
        or cycle.cycle_id != "c6"
        or cycle.activation != "ACTIVE"
        or cycle.execution_profile != "FULL_AUDIT_V1"
        or not contract.collection_prefix.startswith("dev_recall_smoke_")
        or contract.plan_sha256 != plan.sha256
        or (
            cycle.execution_timeout_seconds,
            cycle.write_timeout_seconds,
            cycle.agent_timeout_seconds,
        )
        != (
            SMOKE_EXECUTION_TIMEOUT_SECONDS,
            SMOKE_WRITE_TIMEOUT_SECONDS,
            SMOKE_AGENT_TIMEOUT_SECONDS,
        )
    ):
        raise RuntimeError("smoke_deadline_contract_invalid")
    execution_deadline_at = now + timedelta(
        seconds=SMOKE_EXECUTION_TIMEOUT_SECONDS
    )
    agent_deadline_at = now + timedelta(seconds=SMOKE_AGENT_TIMEOUT_SECONDS)
    if agent_deadline_at > execution_deadline_at:
        raise RuntimeError("smoke_deadline_contract_invalid")
    return execution_deadline_at, agent_deadline_at


def collect_isolated_smoke_result(
    *,
    contract: IsolatedSmokeContract,
    ledger: LedgerPort,
    selected_case_ids: Sequence[str],
    run_ids: Sequence[str],
    cost_snapshot: Any,
    expected_outcomes: Sequence[Any] | None = None,
) -> dict[str, object]:
    if len(selected_case_ids) != contract.case_count or len(run_ids) != contract.case_count:
        raise RuntimeError("smoke_case_count_invalid")
    rows = []
    terminal_receipts: list[Mapping[str, object]] = []
    policy_ids: list[str] = []
    failure_ids: list[str] = []
    technical_codes: list[str] = []
    role_counts: Counter[str] = Counter()
    turns = 0
    http_429_count = 0
    audit_statuses: list[str] = []
    terminal_states: list[str] = []
    for case_id, run_id in zip(selected_case_ids, run_ids, strict=True):
        record = ledger.get_scan_run(run_id)
        if record is None:
            raise RuntimeError("smoke_run_missing")
        artifacts = ledger.list_by_run(run_id)
        _verify_run_lifecycle(ledger, run_id)
        terminal = []
        audits = []
        for wire in artifacts:
            parsed = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
            if parsed.case_id != case_id:
                raise RuntimeError("smoke_run_case_binding_invalid")
            if parsed.schema_name == "AgentExecutionReceipt" and wire.get(
                "execution_status"
            ) in {"COMPLETED", "FAILED"}:
                if wire.get("attempt") != 1:
                    raise RuntimeError("smoke_role_retry_forbidden")
                terminal.append(wire)
            elif parsed.schema_name == "PolicyDecision":
                policy_ids.append(parsed.artifact_id)
            elif parsed.schema_name == "FailureReceipt":
                failure_ids.append(parsed.artifact_id)
            elif parsed.schema_name == "CitationAuditReceipt":
                audits.append(wire)
        for receipt in terminal:
            role = str(receipt["agent_role"])
            role_counts[role] += 1
            terminal_receipts.append(receipt)
            turns += len(receipt["turns"])
            http_429_count += int(receipt["http_429_count"])
            if receipt["failure_code"] is not None:
                technical_codes.append(str(receipt["failure_code"]))
        terminal_states.append(record.state.value)
        audit_statuses.append(
            "INCOMPLETE" if not audits else str(audits[0]["audit_status"])
        )
        rows.append(
            {
                "case_id": case_id,
                "run_id": run_id,
                "terminal_state": record.state.value,
                "audit_status": audit_statuses[-1],
            }
        )
    if expected_outcomes is not None:
        observed = {(row["case_id"], row["run_id"]) for row in rows}
        expected = {(item.case_id, item.run_id) for item in expected_outcomes}
        if observed != expected:
            raise RuntimeError("smoke_outcome_readback_mismatch")
    result = {
        "schema_name": SMOKE_SCHEMA_NAME,
        "schema_version": SMOKE_SCHEMA_VERSION,
        "result_id": str(
            uuid5(
                NAMESPACE_URL,
                "recall:isolated-smoke:"
                + sha256(
                    canonical_json_bytes(
                        {
                            "prefix": contract.collection_prefix,
                            "runs": list(run_ids),
                            "states": terminal_states,
                        }
                    )
                ).hexdigest(),
            )
        ),
        "smoke_id": contract.smoke_id,
        "mode": contract.mode.upper(),
        "collection_prefix": contract.collection_prefix,
        "source_commit": contract.source_commit,
        "plan_sha256": contract.plan_sha256,
        "image_digest": contract.image_digest,
        "preparation_bundle_sha256": contract.preparation_bundle_sha256,
        "selected_case_ids": list(selected_case_ids),
        "run_ids": list(run_ids),
        "run_results": rows,
        "terminal_states": terminal_states,
        "audit_statuses": audit_statuses,
        "agent_execution_receipt_ids": sorted(
            str(item["artifact_id"]) for item in terminal_receipts
        ),
        "policy_decision_ids": sorted(policy_ids),
        "policy_decision_count": len(policy_ids),
        "failure_receipt_ids": sorted(failure_ids),
        "technical_failure_codes": sorted(set(technical_codes)),
        "role_receipt_counts": dict(sorted(role_counts.items())),
        "total_model_turns": turns,
        "http_429_count": http_429_count,
        "turn_budget": {"limit": contract.turn_limit, "observed": turns},
        "aggregate_turn_budget": SMOKE_AGGREGATE_TURN_LIMIT,
        "provider_max_429_retries": SMOKE_PROVIDER_MAX_429_RETRIES,
        "job_max_retries": contract.job_max_retries,
        "cost": {
            "reserved_usd_micros": int(cost_snapshot.reserved_usd_micros),
            "reconciled_usd_micros": int(cost_snapshot.reconciled_usd_micros),
        },
        "writes_scope": {
            "collection_prefix": contract.collection_prefix,
            "namespace": "dev_recall_smoke_",
            "final_prefix_access": False,
        },
        "backend": dict(ledger.backend_metadata()),
    }
    _verify_smoke_result(result, contract)
    return result


def verify_persisted_smoke_artifacts(
    *,
    ledger: LedgerPort,
    contract: IsolatedSmokeContract,
    manifest_artifact_id: str,
    mode_receipt_artifact_id: str | None,
    cost_snapshot: Any,
) -> dict[str, object]:
    manifest_wire = ledger.get_artifact(manifest_artifact_id)
    if manifest_wire is None:
        raise RuntimeError("smoke_manifest_missing")
    manifest = parse_artifact(
        manifest_wire, authorized_producers=PRODUCER_REGISTRY
    )
    payload = manifest.payload
    if (
        manifest.schema_name != "IsolatedSmokeManifest"
        or manifest.schema_version != "1.0.0"
        or payload.smoke_id != contract.smoke_id
        or payload.smoke_mode != contract.mode.upper()
        or payload.collection_prefix != contract.collection_prefix
        or payload.source_commit != contract.source_commit
        or payload.plan_sha256 != contract.plan_sha256
        or payload.preparation_bundle_sha256
        != contract.preparation_bundle_sha256
        or payload.image_digest != contract.image_digest
    ):
        raise RuntimeError("smoke_manifest_binding_invalid")
    _verify_manifest_dependencies(ledger, payload)
    _verify_manifest_cost(payload, cost_snapshot)
    for run_id in payload.run_ids:
        _verify_run_lifecycle(ledger, run_id)
    if contract.mode == "negative":
        if mode_receipt_artifact_id is not None:
            raise RuntimeError("smoke_negative_mode_receipt_forbidden")
        return {
            "manifest_artifact_id": manifest.artifact_id,
            "manifest_content_hash": manifest.content_hash,
            "mode_receipt_artifact_id": None,
            "mode_receipt_content_hash": None,
        }
    if mode_receipt_artifact_id is None:
        raise RuntimeError("smoke_mode_receipt_missing")
    mode_wire = ledger.get_artifact(mode_receipt_artifact_id)
    if mode_wire is None:
        raise RuntimeError("smoke_mode_receipt_missing")
    mode = parse_artifact(mode_wire, authorized_producers=PRODUCER_REGISTRY)
    mode_payload = mode.payload
    if (
        mode.schema_name != "IsolatedSmokeModeReceipt"
        or mode.schema_version != "1.0.0"
        or mode_payload.manifest_artifact_id != manifest.artifact_id
        or mode_payload.manifest_content_hash != manifest.content_hash
        or mode_payload.smoke_id != contract.smoke_id
        or mode_payload.collection_prefix != contract.collection_prefix
        or mode_payload.source_commit != contract.source_commit
        or mode_payload.plan_sha256 != contract.plan_sha256
        or mode_payload.preparation_bundle_sha256
        != contract.preparation_bundle_sha256
        or mode_payload.image_digest != contract.image_digest
        or mode_payload.agent_execution_receipt_ids
        != payload.agent_execution_receipt_ids
    ):
        raise RuntimeError("smoke_mode_receipt_binding_invalid")
    return {
        "manifest_artifact_id": manifest.artifact_id,
        "manifest_content_hash": manifest.content_hash,
        "mode_receipt_artifact_id": mode.artifact_id,
        "mode_receipt_content_hash": mode.content_hash,
    }


def _verify_smoke_result(
    result: Mapping[str, object], contract: IsolatedSmokeContract
) -> None:
    turns = int(result["total_model_turns"])
    if turns > contract.turn_limit or int(result["http_429_count"]) != 0:
        raise RuntimeError("smoke_model_budget_failed")
    cost = result["cost"]
    if not isinstance(cost, Mapping) or cost["reserved_usd_micros"] != cost[
        "reconciled_usd_micros"
    ]:
        raise RuntimeError("smoke_cost_reconciliation_failed")
    roles = result["role_receipt_counts"]
    if contract.mode == "positive":
        expected_roles = {
            AgentRole.EVIDENCE_WATCHER.value: 4,
            AgentRole.EVIDENCE_ASSESSOR.value: 4,
            AgentRole.CITATION_AUDITOR.value: 4,
        }
        if (
            roles != expected_roles
            or set(result["audit_statuses"]) != {"COMPLETE"}
            or "HALTED" in result["terminal_states"]
            or int(result["policy_decision_count"]) != 4
        ):
            raise RuntimeError("smoke_positive_outcome_invalid")
        return
    receipts = result["agent_execution_receipt_ids"]
    if (
        result["terminal_states"] != ["HALTED"]
        or result["audit_statuses"] != ["INCOMPLETE"]
        or int(result["policy_decision_count"]) != 0
        or result["technical_failure_codes"] != ["agent_schema_invalid"]
        or roles != {AgentRole.EVIDENCE_WATCHER.value: 1}
        or not isinstance(receipts, list)
        or len(receipts) != 1
    ):
        raise RuntimeError("smoke_negative_outcome_invalid")


def _persist_smoke_artifacts(
    *,
    ledger: LedgerPort,
    contract: IsolatedSmokeContract,
    result: dict[str, object],
    now: datetime,
) -> dict[str, object]:
    tick_run_id = smoke_tick_run_id(contract.collection_prefix)
    manifest_id = smoke_manifest_artifact_id(contract.collection_prefix)
    input_ids = tuple(
        sorted(
            {
                *result["agent_execution_receipt_ids"],
                *result["policy_decision_ids"],
                *result["failure_receipt_ids"],
            }
        )
    )
    cost = result["cost"]
    assert isinstance(cost, Mapping)
    status = "COMPLETE" if contract.mode == "positive" else "INCOMPLETE"
    manifest_wire = build_artifact(
        schema_name="IsolatedSmokeManifest",
        schema_version="1.0.0",
        artifact_id=manifest_id,
        case_id=None,
        run_id=tick_run_id,
        producer={
            "component": "smoke-controller",
            "version": "1.0.0",
            "identity": "smoke-controller",
        },
        created_at=now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        input_artifact_ids=input_ids,
        data_mode=DataMode.SYNTHETIC,
        status=(
            ArtifactStatus.VALID
            if status == "COMPLETE"
            else ArtifactStatus.INCOMPLETE
        ),
        payload={
            "smoke_id": contract.smoke_id,
            "smoke_mode": contract.mode.upper(),
            "collection_prefix": contract.collection_prefix,
            "source_commit": contract.source_commit,
            "plan_sha256": contract.plan_sha256,
            "preparation_bundle_sha256": contract.preparation_bundle_sha256,
            "image_digest": contract.image_digest,
            "selected_case_ids": result["selected_case_ids"],
            "run_ids": result["run_ids"],
            "terminal_states": result["terminal_states"],
            "audit_statuses": result["audit_statuses"],
            "agent_execution_receipt_ids": result[
                "agent_execution_receipt_ids"
            ],
            "policy_decision_ids": result["policy_decision_ids"],
            "failure_receipt_ids": result["failure_receipt_ids"],
            "role_receipt_counts": result["role_receipt_counts"],
            "total_model_turns": result["total_model_turns"],
            "turn_budget_limit": contract.turn_limit,
            "aggregate_turn_budget_limit": SMOKE_AGGREGATE_TURN_LIMIT,
            "provider_max_429_retries": SMOKE_PROVIDER_MAX_429_RETRIES,
            "job_max_retries": contract.job_max_retries,
            "http_429_count": result["http_429_count"],
            "reserved_cost_usd_micros": cost["reserved_usd_micros"],
            "reconciled_cost_usd_micros": cost["reconciled_usd_micros"],
            "execution_status": status,
        },
        authorized_producers=PRODUCER_REGISTRY,
    )
    manifest = ledger.append_artifact(manifest_wire)
    mode_id: str | None = None
    if contract.mode == "positive":
        mode_id = smoke_mode_receipt_artifact_id(contract.collection_prefix)
        mode_wire = build_artifact(
            schema_name="IsolatedSmokeModeReceipt",
            schema_version="1.0.0",
            artifact_id=mode_id,
            case_id=None,
            run_id=tick_run_id,
            producer={
                "component": "smoke-mode-gate",
                "version": "1.0.0",
                "identity": "smoke-mode-gate",
            },
            created_at=now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            input_artifact_ids=tuple(
                sorted(
                    {
                        manifest.artifact_id,
                        *result["agent_execution_receipt_ids"],
                    }
                )
            ),
            data_mode=DataMode.SYNTHETIC,
            status=ArtifactStatus.VALID,
            payload={
                "smoke_id": contract.smoke_id,
                "collection_prefix": contract.collection_prefix,
                "source_commit": contract.source_commit,
                "plan_sha256": contract.plan_sha256,
                "preparation_bundle_sha256": contract.preparation_bundle_sha256,
                "image_digest": contract.image_digest,
                "manifest_artifact_id": manifest.artifact_id,
                "manifest_content_hash": manifest.content_hash,
                "agent_execution_receipt_ids": result[
                    "agent_execution_receipt_ids"
                ],
                "mode_set": ["SYNTHETIC"],
                "declared_composition": "SMOKE_ONLY_SYNTHETIC",
                "validation_status": "PASS",
                "reason_codes": [],
            },
            authorized_producers=PRODUCER_REGISTRY,
        )
        ledger.append_artifact(mode_wire)
    bindings = verify_persisted_smoke_artifacts(
        ledger=ledger,
        contract=contract,
        manifest_artifact_id=manifest.artifact_id,
        mode_receipt_artifact_id=mode_id,
        cost_snapshot=cost,
    )
    result.update({"tick_run_id": tick_run_id, **bindings})
    return result


def _require_empty_namespace(ledger: LedgerPort) -> None:
    if any(ledger.read_back_count(name) for name in ledger.collection_names):
        raise RuntimeError("smoke_id_already_used")
    client = getattr(ledger, "client", None)
    prefix = getattr(ledger, "collection_prefix", None)
    if client is None or not isinstance(prefix, str):
        return
    for suffix in ("model_cost", "tool_gateway_invocations"):
        if next(iter(client.collection(f"{prefix}{suffix}").limit(1).stream()), None):
            raise RuntimeError("smoke_id_already_used")


def _verify_run_lifecycle(ledger: LedgerPort, run_id: str) -> None:
    events = tuple(ledger.list_scan_run_events(run_id))
    if not events or events[0].event_code is not ScanRunEventCode.RUN_CREATED:
        raise RuntimeError("smoke_run_lifecycle_invalid")
    sequences = tuple(item.sequence for item in events)
    if sequences != tuple(sorted(set(sequences))):
        raise RuntimeError("smoke_run_lifecycle_invalid")
    codes = tuple(item.event_code for item in events)
    if (
        codes.count(ScanRunEventCode.LEASE_ACQUIRED) != 1
        or ScanRunEventCode.LEASE_TAKEN_OVER in codes
        or ScanRunEventCode.RETRY_SCHEDULED in codes
    ):
        raise RuntimeError("smoke_run_retry_or_lease_invalid")


def _verify_manifest_dependencies(ledger: LedgerPort, payload: Any) -> None:
    declared_agents = set(payload.agent_execution_receipt_ids)
    declared_policies = set(payload.policy_decision_ids)
    declared_failures = set(payload.failure_receipt_ids)
    actual_agents: set[str] = set()
    actual_policies: set[str] = set()
    actual_failures: set[str] = set()
    observed_roles: Counter[str] = Counter()
    observed_turns = 0
    observed_429 = 0
    for index, (case_id, run_id) in enumerate(
        zip(payload.selected_case_ids, payload.run_ids, strict=True)
    ):
        record = ledger.get_scan_run(run_id)
        if record is None or record.state.value != payload.terminal_states[index]:
            raise RuntimeError("smoke_run_state_binding_invalid")
        per_run_roles: Counter[str] = Counter()
        audit_statuses: list[str] = []
        per_run_policy_ids: set[str] = set()
        per_run_failure_ids: set[str] = set()
        for wire in ledger.list_by_run(run_id):
            parsed = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
            if parsed.run_id != run_id or parsed.case_id != case_id:
                raise RuntimeError("smoke_run_case_binding_invalid")
            if parsed.schema_name == "AgentExecutionReceipt" and wire.get(
                "execution_status"
            ) in {"COMPLETED", "FAILED"}:
                actual_agents.add(parsed.artifact_id)
                if wire.get("attempt") != 1:
                    raise RuntimeError("smoke_role_retry_forbidden")
                role = str(wire["agent_role"])
                per_run_roles[role] += 1
                observed_roles[role] += 1
                observed_turns += len(wire["turns"])
                observed_429 += int(wire["http_429_count"])
                if (
                    payload.smoke_mode == "POSITIVE"
                    and wire["execution_status"] != "COMPLETED"
                ):
                    raise RuntimeError("smoke_agent_receipt_binding_invalid")
                if payload.smoke_mode == "NEGATIVE" and (
                    wire["execution_status"] != "FAILED"
                    or wire["failure_code"] != "agent_schema_invalid"
                    or not wire["tool_call_ids"]
                    or wire["tool_call_ids"] != wire["tool_response_ids"]
                    or not wire["tool_records"]
                ):
                    raise RuntimeError("smoke_negative_telemetry_invalid")
            elif parsed.schema_name == "PolicyDecision":
                actual_policies.add(parsed.artifact_id)
                per_run_policy_ids.add(parsed.artifact_id)
            elif parsed.schema_name == "FailureReceipt":
                actual_failures.add(parsed.artifact_id)
                per_run_failure_ids.add(parsed.artifact_id)
            elif parsed.schema_name == "CitationAuditReceipt":
                audit_statuses.append(str(wire["audit_status"]))
        expected_audit = payload.audit_statuses[index]
        observed_audit = "INCOMPLETE" if not audit_statuses else audit_statuses[0]
        if len(audit_statuses) > 1 or observed_audit != expected_audit:
            raise RuntimeError("smoke_audit_status_binding_invalid")
        if payload.smoke_mode == "POSITIVE":
            if (
                per_run_roles
                != {
                    AgentRole.EVIDENCE_WATCHER.value: 1,
                    AgentRole.EVIDENCE_ASSESSOR.value: 1,
                    AgentRole.CITATION_AUDITOR.value: 1,
                }
                or len(per_run_policy_ids) != 1
                or per_run_failure_ids
            ):
                raise RuntimeError("smoke_per_run_topology_invalid")
            if (
                record.terminal_policy_decision_id
                != next(iter(per_run_policy_ids))
                or record.failure_receipt_ids
            ):
                raise RuntimeError("smoke_run_terminal_pointer_invalid")
        elif (
            per_run_roles != {AgentRole.EVIDENCE_WATCHER.value: 1}
            or per_run_policy_ids
            or not per_run_failure_ids
        ):
            raise RuntimeError("smoke_per_run_topology_invalid")
        elif (
            record.terminal_policy_decision_id is not None
            or set(record.failure_receipt_ids) != per_run_failure_ids
        ):
            raise RuntimeError("smoke_run_terminal_pointer_invalid")
    if (
        actual_agents != declared_agents
        or actual_policies != declared_policies
        or actual_failures != declared_failures
    ):
        raise RuntimeError("smoke_manifest_artifact_set_mismatch")
    if (
        dict(sorted(observed_roles.items())) != dict(payload.role_receipt_counts)
        or observed_turns != payload.total_model_turns
        or observed_429 != payload.http_429_count
    ):
        raise RuntimeError("smoke_agent_receipt_summary_invalid")


def _verify_manifest_cost(payload: Any, snapshot: Any) -> None:
    if isinstance(snapshot, Mapping):
        reserved = snapshot.get("reserved_usd_micros")
        reconciled = snapshot.get("reconciled_usd_micros")
    else:
        reserved = getattr(snapshot, "reserved_usd_micros", None)
        reconciled = getattr(snapshot, "reconciled_usd_micros", None)
    if (
        reserved != payload.reserved_cost_usd_micros
        or reconciled != payload.reconciled_cost_usd_micros
        or reserved != reconciled
    ):
        raise RuntimeError("smoke_cost_snapshot_mismatch")


def _install_smoke_cases(
    ledger: LedgerPort,
    bundle: CompressedPreparationBundle,
    cycle: CompressedCycle,
    selected: Sequence[CompressedCohortCase],
    *,
    now: datetime,
) -> None:
    prepared = {
        (item.case_id, item.cycle_id): item for item in bundle.cases
    }
    verifier = CompressedPreparationVerifier(bundle)
    selected_vcvs = set()
    for case in selected:
        item = prepared.get((case.case_id, cycle.cycle_id))
        if item is None or not verifier(item.privacy_receipt):
            raise RuntimeError("smoke_preparation_case_invalid")
        ledger.append_artifact(item.privacy_receipt)
        receipt = ledger.get_artifact(str(item.privacy_receipt["artifact_id"]))
        if receipt is None or not verifier(receipt):
            raise RuntimeError("smoke_preparation_receipt_lock_failed")
        record, created = ledger.create_watch_case(
            item.watch_case,
            cloud_bound_payload=item.cloud_bound_payload,
            now=now,
        )
        if not created or record.next_scan_at != cycle.schedule_epoch:
            raise RuntimeError("smoke_preparation_watch_case_invalid")
        if case.vcv is not None:
            selected_vcvs.add(case.vcv)
    for vcv in sorted(selected_vcvs):
        observation = bundle.observations_by_vcv.get(vcv)
        if observation is None:
            raise RuntimeError("smoke_preparation_anchor_missing")
        ledger.append_artifact(observation)
