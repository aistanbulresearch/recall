from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from recall.ledger.firestore import FirestoreLedger
from recall.agents.full_audit import FullAuditCoordinator
from recall.agents.in_process_runtime import InProcessAdkRoleRunner
from recall.agents.provider_pacing import provider_rpm_from_environment
from recall.connectors import PubMedConnector
from recall.contracts import parse_artifact
from recall.controller.tool_gateway_store import FirestoreGatewayInvocationStore
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.platform.redaction import redact_json

from .dayn import DayNScheduler, collection_prefix, preview
from .manifest import day_index, manifest_artifact_id
from .cohort import RUN_PREDICTIONS
from .continuation import (
    MissingCohortDay,
    previous_complete_managed_date,
    validate_persisted_manifest_link,
)
from .preparation import (
    LockedPreparationVerifier,
    load_preparation_bundle,
)
from .compressed import CompressedCycleScheduler
from .compressed_batch import BATCH_MAX_WORKERS
from .compressed_cohort import cases_for_cycle, portfolio_cases
from .compressed_ramp_gate import evaluate_and_persist_ramp_gate
from .compressed_headroom import evaluate_and_persist_headroom
from .compressed_identity import (
    collection_prefix as compressed_collection_prefix,
    evidence_collection_prefix,
    evidence_manifest_artifact_id,
    manifest_artifact_id as compressed_manifest_artifact_id,
)
from .compressed_plan import load_compressed_plan, resolve_declared_cycle
from .compressed_preparation import (
    CompressedPreparationVerifier,
    load_compressed_bundle,
    verify_prepared_cycle,
)
from .compressed_supersession import verify_final_only_supersession
from .model_cost import (
    DEFAULT_MODEL_COST_POLICY,
    FirestoreModelCostLedger,
)
from .smoke import (
    SMOKE_NEGATIVE_PROBE,
    SMOKE_PROVIDER_MAX_429_RETRIES,
    build_smoke_contract,
    execute_isolated_smoke,
)


LedgerFactory = Callable[..., Any]
_SOURCE_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def execute(
    argv: Sequence[str],
    *,
    environment: Mapping[str, str],
    now_factory: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ledger_factory: LedgerFactory = FirestoreLedger.from_default_credentials,
    full_audit_factory: Callable[[FirestoreLedger], FullAuditCoordinator] | None = None,
    repo_root: Path | None = None,
) -> dict[str, object]:
    scheduler_mode = _required(environment, "RECALL_SCHEDULER_MODE")
    if scheduler_mode == "LEGACY_DAYN":
        return _execute_legacy(
            argv,
            environment=environment,
            now_factory=now_factory,
            ledger_factory=ledger_factory,
            repo_root=repo_root,
        )
    if scheduler_mode != "COMPRESSED_V3":
        raise RuntimeError("cohort_scheduler_mode_invalid")
    provider_rpm = provider_rpm_from_environment(environment)
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview-date")
    parser.add_argument("--verify-prefix")
    parser.add_argument("--smoke-mode")
    parser.add_argument("--smoke-id")
    parser.add_argument("--smoke-prefix")
    args = parser.parse_args(list(argv))
    smoke_values = (args.smoke_mode, args.smoke_id, args.smoke_prefix)
    if any(item is not None for item in smoke_values) and not all(smoke_values):
        raise RuntimeError("smoke_contract_incomplete")
    root = (repo_root or Path.cwd()).resolve()
    plan = load_compressed_plan(root)
    bundle_sha = _required(environment, "RECALL_COMPRESSED_PREPARATION_SHA256")
    bundle = load_compressed_bundle(
        root, expected_sha256=bundle_sha, plan=plan
    )
    source_commit = _required(environment, "RECALL_SOURCE_COMMIT")
    if not _SOURCE_COMMIT.fullmatch(source_commit):
        raise RuntimeError("cohort_source_commit_invalid")
    _require_compressed_source_binding(bundle, source_commit)
    image_digest = _required(environment, "RECALL_IMAGE_DIGEST")
    if not _IMAGE_DIGEST.fullmatch(image_digest):
        raise RuntimeError("cohort_image_digest_invalid")
    if args.smoke_mode is not None:
        contract = build_smoke_contract(
            mode=args.smoke_mode,
            smoke_id=args.smoke_id,
            collection_prefix=args.smoke_prefix,
            source_commit=source_commit,
            plan_sha256=plan.sha256,
            image_digest=image_digest,
            expected_plan_sha256=_required(
                environment, "RECALL_SMOKE_EXPECTED_PLAN_SHA256"
            ),
            expected_image_digest=_required(
                environment, "RECALL_SMOKE_EXPECTED_IMAGE_DIGEST"
            ),
            preparation_bundle_sha256=bundle.bundle_sha256,
            job_max_retries=_required(
                environment, "RECALL_SMOKE_JOB_MAX_RETRIES"
            ),
        )
        project_sha = _required(environment, "RECALL_EXPECTED_PROJECT_SHA256")
        verifier = CompressedPreparationVerifier(bundle)
        ledger = ledger_factory(
            collection_prefix=contract.collection_prefix,
            privacy_receipt_verifier=verifier,
            expected_project_sha256=project_sha,
            database="(default)",
            require_live=True,
        )
        failure_probe = (
            SMOKE_NEGATIVE_PROBE
            if contract.mode == "negative"
            else None
        )
        full_audit = (
            full_audit_factory(ledger)
            if full_audit_factory is not None
            else _build_full_audit_coordinator(
                ledger,
                plan_sha256=plan.sha256,
                provider_rpm=provider_rpm,
                max_429_retries=SMOKE_PROVIDER_MAX_429_RETRIES,
                failure_probe=failure_probe,
                isolated_cost_collection=True,
            )
        )
        ncbi = PubMedConnector(
            tool=_required(environment, "RECALL_NCBI_TOOL"),
            email=_required(environment, "RECALL_NCBI_EMAIL"),
        )
        return execute_isolated_smoke(
            contract=contract,
            ledger=ledger,
            plan=plan,
            bundle=bundle,
            coordinator=full_audit,
            now=now_factory(),
            refetch_fetcher=ncbi.fetch,
        )
    if args.preview_date:
        selected = date.fromisoformat(args.preview_date)
        cycle = plan.by_due_date(selected)
        selected_cases = cases_for_cycle(cycle)
        selected_ids = {item.case_id for item in selected_cases}
        excluded = sorted(
            item.case_id
            for item in portfolio_cases(plan.cycles)
            if item.case_id not in selected_ids
        )
        return {
            "mode": "DRY_RUN_COMPRESSED_SELECTION_PREVIEW",
            "writes": 0,
            "cycle_id": cycle.cycle_id,
            "cohort_due_date": cycle.cohort_due_date.isoformat(),
            "selected_case_ids": sorted(selected_ids),
            "excluded_case_ids": excluded,
            "runs_predicted": cycle.runs_predicted,
            "collection_prefix": compressed_collection_prefix(plan, cycle),
            "plan_sha256": plan.sha256,
            "preparation_bundle_sha256": bundle.bundle_sha256,
            "source_commit": source_commit,
            "image_digest": image_digest,
            "write_path": cycle.write_path,
            "epoch_label": cycle.epoch_label,
            "evaluation_role": cycle.evaluation_role,
            "execution_timeout_seconds": cycle.execution_timeout_seconds,
            "write_timeout_seconds": cycle.write_timeout_seconds,
            "agent_timeout_seconds": cycle.agent_timeout_seconds,
            "authoritative_end_to_end_deadline": (
                cycle.end_to_end_deadline.isoformat().replace("+00:00", "Z")
            ),
            "activation": cycle.activation,
            "execution_profile": cycle.execution_profile,
            "parity_indicator_fields": [
                "expected_newly_created_runs",
                "actual_newly_created_runs",
                "expected_reused_runs",
                "actual_reused_runs",
                "new_epoch_required",
                "same_write_path_as_ramp",
                "parity_match",
                "epoch_parity_match",
                "fresh_write_parity_match",
            ],
            "batch_max_workers": (
                BATCH_MAX_WORKERS
                if cycle.write_path == "FIRESTORE_BATCH_V1"
                else 1
            ),
        }
    project_sha = _required(environment, "RECALL_EXPECTED_PROJECT_SHA256")
    verifier = CompressedPreparationVerifier(bundle)

    def historical_ledger(prefix: str):
        return ledger_factory(
            collection_prefix=prefix,
            privacy_receipt_verifier=verifier,
            expected_project_sha256=project_sha,
            database="(default)",
            require_live=True,
        )

    if args.verify_prefix:
        try:
            due = datetime.strptime(args.verify_prefix, "%Y%m%d").date()
        except ValueError as exc:
            raise RuntimeError("compressed_verify_prefix_invalid") from exc
        cycle = plan.by_due_date(due)
        ledger = ledger_factory(
            collection_prefix=compressed_collection_prefix(plan, cycle),
            privacy_receipt_verifier=verifier,
            expected_project_sha256=project_sha,
            database="(default)",
            require_live=True,
        )
        before = {
            name: ledger.read_back_count(name) for name in ledger.collection_names
        }
        verified_history = None
        if plan.schema_version == "2.8.0":
            verified_history = verify_final_only_supersession(
                plan,
                ledger_for_prefix=historical_ledger,
            )
        verify_prepared_cycle(ledger, bundle, plan, cycle)
        after = {
            name: ledger.read_back_count(name) for name in ledger.collection_names
        }
        if after != before:
            raise RuntimeError("compressed_verify_prefix_wrote_data")
        return {
            "mode": "LIVE_FIRESTORE_COMPRESSED_PREFIX_VERIFICATION",
            "verified": True,
            "writes": 0,
            "cycle_id": cycle.cycle_id,
            "cohort_due_date": cycle.cohort_due_date.isoformat(),
            "collection_prefix": compressed_collection_prefix(plan, cycle),
            "readback": after,
            "plan_sha256": plan.sha256,
            "preparation_bundle_sha256": bundle.bundle_sha256,
            "verified_historical_artifact_ids": (
                []
                if verified_history is None
                else list(verified_history.verified_artifact_ids)
            ),
        }
    now = now_factory()
    cycle = resolve_declared_cycle(now, plan)
    if cycle.write_path == "EXTERNAL_IMMUTABLE":
        raise RuntimeError("compressed_cycle_external_immutable")
    ledger = ledger_factory(
        collection_prefix=compressed_collection_prefix(plan, cycle),
        privacy_receipt_verifier=verifier,
        expected_project_sha256=project_sha,
        database="(default)",
        require_live=True,
    )
    full_audit = None
    refetch_backend = None
    if cycle.execution_profile == "FULL_AUDIT_V1":
        if not isinstance(ledger, FirestoreLedger):
            if full_audit_factory is None:
                raise RuntimeError("full_audit_factory_required")
        full_audit = (
            full_audit_factory(ledger)
            if full_audit_factory is not None
            else _build_full_audit_coordinator(
                ledger,
                plan_sha256=plan.sha256,
                provider_rpm=provider_rpm,
            )
        )
        ncbi = PubMedConnector(
            tool=_required(environment, "RECALL_NCBI_TOOL"),
            email=_required(environment, "RECALL_NCBI_EMAIL"),
        )
        refetch_backend = ncbi.fetch
    previous = None
    prior_ledgers = {}
    ramp_gate = None
    headroom = None
    if plan.schema_version != "2.8.0":
        for prior_cycle in plan.cycles[: cycle.cycle_index - 1]:
            prior_ledger = ledger_factory(
                collection_prefix=evidence_collection_prefix(plan, prior_cycle),
                privacy_receipt_verifier=verifier,
                expected_project_sha256=project_sha,
                database="(default)",
                require_live=True,
            )
            prior_ledgers[prior_cycle.cycle_id] = prior_ledger
        if cycle.cycle_index > 1:
            predecessor = plan.cycles[cycle.cycle_index - 2]
            previous = prior_ledgers[predecessor.cycle_id].get_artifact(
                evidence_manifest_artifact_id(plan, predecessor)
            )
            if previous is None:
                raise RuntimeError("compressed_previous_manifest_missing")
        predecessor = plan.cycles[cycle.cycle_index - 2]
        ramp_gate = evaluate_and_persist_ramp_gate(
                plan=plan,
                target_cycle=cycle,
                predecessor_ledger=prior_ledgers[predecessor.cycle_id],
                target_ledger=ledger,
                now=now,
        )
        if cycle.cycle_id == "c6":
            headroom = evaluate_and_persist_headroom(
                plan=plan,
                c6_cycle=cycle,
                prior_ledgers=prior_ledgers,
                c6_ledger=ledger,
            )
    result = CompressedCycleScheduler(
        ledger,
        plan=plan,
        cycle=cycle,
        bundle=bundle,
        source_commit=source_commit,
        image_digest=image_digest,
        full_audit_coordinator=full_audit,
        refetch_fetcher=refetch_backend,
        clock=lambda: datetime.now(timezone.utc),
    ).trigger(
        now=now,
        previous_manifest=previous,
        ramp_gate_receipt=ramp_gate,
        headroom_receipt=headroom,
        prior_ledgers=prior_ledgers,
        historical_ledger_factory=(
            historical_ledger if plan.schema_version == "2.8.0" else None
        ),
    )
    return {
        "mode": "LIVE_FIRESTORE_COMPRESSED_MACHINE_TRIGGERED_COHORT_CYCLE",
        "cycle_id": result.cycle_id,
        "cohort_due_date": result.cohort_due_date,
        "newly_created_run_ids": list(result.newly_created_run_ids),
        "reused_run_ids": list(result.reused_run_ids),
        "authoritative_run_ids": list(result.authoritative_run_ids),
        "manifest_artifact_id": result.manifest_artifact_id,
        "data_mode_receipt_id": result.data_mode_receipt_id,
        "ramp_gate_receipt_id": (
            None if ramp_gate is None else str(ramp_gate["artifact_id"])
        ),
        "headroom_receipt_id": (
            None if headroom is None else str(headroom["artifact_id"])
        ),
        "collection_prefix": compressed_collection_prefix(plan, cycle),
        "plan_sha256": plan.sha256,
        "schedule_mode": plan.schedule_mode,
        "write_path": cycle.write_path,
        "epoch_label": cycle.epoch_label,
        "evaluation_role": cycle.evaluation_role,
        "execution_timeout_seconds": cycle.execution_timeout_seconds,
        "write_timeout_seconds": cycle.write_timeout_seconds,
        "agent_timeout_seconds": cycle.agent_timeout_seconds,
        "authoritative_end_to_end_deadline": (
            cycle.end_to_end_deadline.isoformat().replace("+00:00", "Z")
        ),
        "activation": cycle.activation,
        "execution_profile": cycle.execution_profile,
        "batch_max_workers": (
            BATCH_MAX_WORKERS
            if cycle.write_path == "FIRESTORE_BATCH_V1"
            else 1
        ),
        "backend": dict(ledger.backend_metadata()),
        "claim_boundary": {
            "managed_tick": "EXECUTED",
            "managed_admission": "NOT_CLAIMED_LAB_LOCAL_PREPARATION",
            "cross_day_watch_case_continuity": "NOT_CLAIMED_DATE_ISOLATED",
            "terminal_agent_execution": "IN_PROCESS_ADK_CLOUD_RUN",
            "agent_engine_cohort_execution": "NOT_CLAIMED",
        },
    }


def _build_full_audit_coordinator(
    ledger: FirestoreLedger,
    *,
    plan_sha256: str,
    provider_rpm: int,
    max_429_retries: int = 3,
    failure_probe: str | None = None,
    isolated_cost_collection: bool = False,
) -> FullAuditCoordinator:
    prefix = ledger.collection_prefix
    return FullAuditCoordinator(
        ledger,
        role_runner=InProcessAdkRoleRunner(
            max_request_bytes=(
                DEFAULT_MODEL_COST_POLICY.max_request_bytes_per_turn
            ),
            provider_rpm=provider_rpm,
            max_429_retries=max_429_retries,
            failure_probe=failure_probe,
        ),
        invocation_store=FirestoreGatewayInvocationStore(
            ledger.client,
            collection_name=f"{prefix}tool_gateway_invocations",
        ),
        cost_ledger=FirestoreModelCostLedger(
            ledger.client,
            collection_name=(
                f"{prefix}model_cost"
                if isolated_cost_collection
                else f"recall_plan6_cost_{plan_sha256[:16]}"
            ),
            hard_cap_usd_micros=DEFAULT_MODEL_COST_POLICY.hard_cap_usd_micros,
        ),
        cost_policy=DEFAULT_MODEL_COST_POLICY,
        clock=lambda: datetime.now(UTC),
    )


def _execute_legacy(
    argv: Sequence[str],
    *,
    environment: Mapping[str, str],
    now_factory: Callable[[], datetime],
    ledger_factory: LedgerFactory,
    repo_root: Path | None,
) -> dict[str, object]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview-date")
    args = parser.parse_args(list(argv))
    root = (repo_root or Path.cwd()).resolve()
    bundle_sha = _required(environment, "RECALL_COHORT_PREPARATION_SHA256")
    bundle = load_preparation_bundle(root, expected_sha256=bundle_sha)
    source_commit = _required(environment, "RECALL_SOURCE_COMMIT")
    if not _SOURCE_COMMIT.fullmatch(source_commit):
        raise RuntimeError("cohort_source_commit_invalid")
    if source_commit != bundle.source_commit:
        raise RuntimeError("source_commit_mismatch")
    image_digest = _required(environment, "RECALL_IMAGE_DIGEST")
    if not _IMAGE_DIGEST.fullmatch(image_digest):
        raise RuntimeError("cohort_image_digest_invalid")
    if args.preview_date:
        selected = date.fromisoformat(args.preview_date)
        result = preview(selected, repo_root=root)
        return {
            "mode": "DRY_RUN_SELECTION_PREVIEW",
            "writes": 0,
            "selected_for_date": result.selected_for_date,
            "selected_case_ids": list(result.selected_case_ids),
            "excluded_case_ids": list(result.excluded_case_ids),
            "runs_predicted": result.runs_predicted,
            "collection_prefix": result.collection_prefix,
            "preparation_bundle_sha256": bundle.bundle_sha256,
            "source_commit": source_commit,
            "image_digest": image_digest,
        }
    project_sha = _required(environment, "RECALL_EXPECTED_PROJECT_SHA256")
    now = now_factory()
    selected_date = now.astimezone(timezone.utc).date()
    if selected_date not in RUN_PREDICTIONS:
        raise RuntimeError("cohort_prediction_missing")
    verifier = LockedPreparationVerifier(bundle)
    ledger = ledger_factory(
        collection_prefix=collection_prefix(selected_date),
        privacy_receipt_verifier=verifier,
        expected_project_sha256=project_sha,
        database="(default)",
        require_live=True,
    )
    previous, missing_days = _load_prior_context(
        selected_date,
        ledger_factory=ledger_factory,
        verifier=verifier,
        project_sha=project_sha,
    )
    result = DayNScheduler(
        ledger,
        bundle=bundle,
        source_commit=source_commit,
        image_digest=image_digest,
    ).trigger(
        now=now,
        previous_manifest=previous,
        missing_days=missing_days,
    )
    return {
        "mode": "LIVE_FIRESTORE_SYNTHETIC_COHORT_TICK",
        "selected_for_date": result.selected_for_date,
        "newly_created_run_ids": list(result.newly_created_run_ids),
        "reused_run_ids": list(result.reused_run_ids),
        "authoritative_run_ids": list(result.authoritative_run_ids),
        "manifest_artifact_id": result.manifest_artifact_id,
        "data_mode_receipt_id": result.data_mode_receipt_id,
        "failure_receipt_ids": list(result.failure_receipt_ids),
        "collection_prefix": collection_prefix(selected_date),
        "backend": dict(ledger.backend_metadata()),
        "claim_boundary": {
            "managed_tick": "EXECUTED",
            "managed_admission": "NOT_CLAIMED_LAB_LOCAL_PREPARATION",
            "cross_day_watch_case_continuity": "NOT_CLAIMED_DATE_ISOLATED",
            "terminal_agent_execution": "NOT_RUN_NOT_CLAIMED",
        },
    }


def _require_compressed_source_binding(bundle, source_commit: str) -> None:
    """Keep legacy equality; final-only input provenance is loader-verified."""

    if bundle.schema_version != "2.3.0" and source_commit != bundle.source_commit:
        raise RuntimeError("source_commit_mismatch")


def main(argv: Sequence[str] | None = None) -> int:
    import sys

    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        result = execute(arguments, environment=os.environ)
    except Exception as exc:
        if "--verify-prefix" not in arguments:
            raise
        print(
            json.dumps(
                redact_json(
                    {
                        "mode": "LIVE_FIRESTORE_COMPRESSED_PREFIX_VERIFICATION",
                        "verified": False,
                        "writes": 0,
                        "error": type(exc).__name__,
                        "reason": str(exc),
                    }
                ),
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(redact_json(result), sort_keys=True))
    return 0


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if not value:
        raise RuntimeError(f"cohort_required_environment_missing:{name}")
    return value


def _load_prior_context(
    selected_date: date,
    *,
    ledger_factory: LedgerFactory,
    verifier: LockedPreparationVerifier,
    project_sha: str,
) -> tuple[Mapping[str, object] | None, tuple[MissingCohortDay, ...]]:
    if day_index(selected_date) == 2:
        return None, ()
    missing = []
    cursor = selected_date - timedelta(days=1)
    first_managed_date = date(2026, 8, 26)
    while cursor >= first_managed_date:
        if cursor not in RUN_PREDICTIONS:
            raise RuntimeError("cohort_prediction_gap")
        prior = ledger_factory(
            collection_prefix=collection_prefix(cursor),
            privacy_receipt_verifier=verifier,
            expected_project_sha256=project_sha,
            database="(default)",
            require_live=True,
        )
        manifest = prior.get_artifact(manifest_artifact_id(cursor))
        if manifest is not None:
            parsed = parse_artifact(
                manifest, authorized_producers=PRODUCER_REGISTRY
            )
            if (
                parsed.schema_name != "CohortDayManifest"
                or parsed.payload.day_index != day_index(cursor)
                or parsed.payload.selected_for_date != cursor.isoformat()
            ):
                raise RuntimeError("previous_cohort_manifest_invalid")
            _validate_prior_manifest_chain(
                manifest_date=cursor,
                manifest=manifest,
                ledger=prior,
                ledger_factory=ledger_factory,
                verifier=verifier,
                project_sha=project_sha,
            )
            return manifest, tuple(
                MissingCohortDay(item) for item in sorted(missing)
            )
        if (
            prior.read_back_count("scan_runs") != 0
            or prior.read_back_count("scan_run_events") != 0
        ):
            raise RuntimeError("previous_cohort_day_partial_state")
        missing.append(cursor)
        cursor -= timedelta(days=1)
    return None, tuple(MissingCohortDay(item) for item in sorted(missing))


def _validate_prior_manifest_chain(
    *,
    manifest_date: date,
    manifest: Mapping[str, object],
    ledger: Any,
    ledger_factory: LedgerFactory,
    verifier: LockedPreparationVerifier,
    project_sha: str,
) -> None:
    current_date = manifest_date
    current_manifest = manifest
    current_ledger = ledger
    for _ in range(len(RUN_PREDICTIONS)):
        previous_date = previous_complete_managed_date(current_manifest)
        if previous_date is None:
            validate_persisted_manifest_link(
                current_ledger,
                current_manifest,
                manifest_date=current_date,
                previous_manifest=None,
            )
            return
        if previous_date not in RUN_PREDICTIONS or previous_date >= current_date:
            raise RuntimeError("cohort_manifest_predecessor_invalid")
        previous_ledger = ledger_factory(
            collection_prefix=collection_prefix(previous_date),
            privacy_receipt_verifier=verifier,
            expected_project_sha256=project_sha,
            database="(default)",
            require_live=True,
        )
        previous_manifest = previous_ledger.get_artifact(
            manifest_artifact_id(previous_date)
        )
        validate_persisted_manifest_link(
            current_ledger,
            current_manifest,
            manifest_date=current_date,
            previous_manifest=previous_manifest,
        )
        if previous_manifest is None:
            raise RuntimeError("cohort_manifest_predecessor_invalid")
        current_date = previous_date
        current_manifest = previous_manifest
        current_ledger = previous_ledger
    raise RuntimeError("cohort_manifest_predecessor_chain_unbounded")


if __name__ == "__main__":
    raise SystemExit(main())
