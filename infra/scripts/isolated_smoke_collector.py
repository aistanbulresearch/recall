"""Join exact Cloud Run executions with durable isolated-smoke evidence.

All gcloud reads go through ``gcloud_redacted.py``.  Firestore and Cloud Trace
reads are exact-ID/prefix SDK reads.  The emitted report contains only typed
verdicts, safe reason codes, and aggregate counts; raw resource, artifact, case,
run, trace, principal, project, or secret identifiers are never returned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from isolated_smoke_evidence import FAIL, NOT_VERIFIED, evaluate_evidence
from isolated_smoke_trigger import (
    PROJECT_PLACEHOLDER,
    REGION,
    DeploymentExpectation,
    SmokePair,
    validate_job_snapshot,
)


TERMINAL_STATES = {"NO_ACTION", "ABSTAIN", "REVIEW_REQUIRED", "HALTED"}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _nested(value: Mapping[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        current: Any = value
        for key in path:
            if not isinstance(current, Mapping) or key not in current:
                current = None
                break
            current = current[key]
        if current is not None:
            return current
    return None


def _container(execution: Mapping[str, Any]) -> Mapping[str, Any]:
    candidates = _nested(
        execution,
        ("template", "containers"),
        ("spec", "template", "spec", "containers"),
        ("spec", "template", "spec", "template", "spec", "containers"),
    )
    if isinstance(candidates, list) and len(candidates) == 1:
        return _mapping(candidates[0])
    return {}


def _creator_class(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return "NOT_VERIFIED"
    if value.endswith(".gserviceaccount.com"):
        return "MACHINE_SERVICE_ACCOUNT"
    if "@" in value:
        return "HUMAN"
    return "NOT_VERIFIED"


def _terminal_success(execution: Mapping[str, Any]) -> bool | None:
    conditions = _nested(execution, ("conditions",), ("status", "conditions"))
    if not isinstance(conditions, list):
        return None
    for item in conditions:
        row = _mapping(item)
        if row.get("type") in {"Completed", "Ready"}:
            state = row.get("state", row.get("status"))
            return state in {True, "True", "CONDITION_SUCCEEDED"}
    return None


def _counter(execution: Mapping[str, Any], name: str) -> int | None:
    value = _nested(execution, (name,), ("status", name))
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def normalize_execution(
    raw: Mapping[str, Any],
    *,
    execution_id: str,
    mode: str,
    pair: SmokePair,
    expected_project_sha256: str,
) -> tuple[dict[str, object], set[str], str | None]:
    failures: set[str] = set()
    container = _container(raw)
    env_rows = container.get("env")
    env = {
        str(item.get("name")): item.get("value")
        for item in (env_rows if isinstance(env_rows, list) else [])
        if isinstance(item, Mapping) and isinstance(item.get("name"), str)
    }
    args = container.get("args")
    observed_args = list(args) if isinstance(args, (list, tuple)) else []
    if observed_args != list(pair.entrypoint_args(mode)):
        failures.add("execution_args_invalid")
    expected_env = {
        "RECALL_SOURCE_COMMIT": pair.source_commit,
        "RECALL_SOURCE_TREE": pair.source_tree,
        "RECALL_COMPRESSED_PREPARATION_SHA256": pair.bundle_sha256,
        "RECALL_IMAGE_DIGEST": pair.image_digest,
        "RECALL_SMOKE_EXPECTED_PLAN_SHA256": pair.plan_sha256,
        "RECALL_SMOKE_EXPECTED_IMAGE_DIGEST": pair.image_digest,
        "RECALL_SMOKE_JOB_MAX_RETRIES": "0",
    }
    for name, expected in expected_env.items():
        if env.get(name) != expected:
            failures.add("execution_override_or_provenance_invalid")
    expectation = DeploymentExpectation(
        source_commit=pair.source_commit,
        source_tree=pair.source_tree,
        expected_project_sha256=expected_project_sha256,
        bundle_sha256=pair.bundle_sha256,
        image_digest=pair.image_digest,
        expected_service_account=(
            f"recall-sa-cohort-job@{PROJECT_PLACEHOLDER}."
            "iam.gserviceaccount.com"
        ),
    )
    failures.update(validate_job_snapshot(raw, expectation))
    expected_role_principals = {
        "RECALL_WATCHER_PRINCIPAL": (
            f"recall-sa-watcher@{PROJECT_PLACEHOLDER}.iam.gserviceaccount.com"
        ),
        "RECALL_ASSESSOR_PRINCIPAL": (
            f"recall-sa-assessor@{PROJECT_PLACEHOLDER}.iam.gserviceaccount.com"
        ),
        "RECALL_AUDITOR_PRINCIPAL": (
            f"recall-sa-auditor@{PROJECT_PLACEHOLDER}.iam.gserviceaccount.com"
        ),
    }
    actual_caller_config_verified = all(
        env.get(name) == expected
        for name, expected in expected_role_principals.items()
    )
    if not actual_caller_config_verified:
        failures.add("actual_caller_config_invalid")
    name = _nested(raw, ("name",), ("metadata", "name"))
    if isinstance(name, str):
        name = name.rsplit("/", 1)[-1]
    if name != execution_id:
        failures.add("execution_identity_mismatch")
    creator = _nested(
        raw,
        ("creator",),
        ("metadata", "creator"),
        ("metadata", "annotations", "run.googleapis.com/creator"),
    )
    creator_class = _creator_class(creator)
    if creator_class == "HUMAN":
        failures.add("machine_creator_required")
    image = str(container.get("image", ""))
    if not image.endswith("@" + pair.image_digest):
        failures.add("execution_digest_invalid")
    task_count = _nested(
        raw, ("template", "taskCount"), ("spec", "template", "spec", "taskCount")
    )
    normalized = {
        "mode": mode,
        "terminal": _terminal_success(raw),
        "condition": "SUCCEEDED" if _terminal_success(raw) is True else None,
        "succeeded_count": _counter(raw, "succeededCount"),
        "failed_count": _counter(raw, "failedCount"),
        "retried_count": _counter(raw, "retriedCount"),
        "task_count": task_count,
        "creator_class": creator_class,
        "image_digest": pair.image_digest if image.endswith("@" + pair.image_digest) else None,
        "source_commit": env.get("RECALL_SOURCE_COMMIT"),
        "source_tree": env.get("RECALL_SOURCE_TREE"),
        "plan_sha256": env.get("RECALL_SMOKE_EXPECTED_PLAN_SHA256"),
        "bundle_sha256": env.get("RECALL_COMPRESSED_PREPARATION_SHA256"),
        "actual_caller_config_verified": actual_caller_config_verified,
    }
    principal_fingerprint = (
        hashlib.sha256(str(creator).encode("utf-8")).hexdigest()
        if isinstance(creator, str) and creator
        else None
    )
    return normalized, failures, principal_fingerprint


def _read_receipt(path: Path) -> tuple[SmokePair, dict[str, str], str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ValueError("execution_receipt_invalid") from None
    if (
        not isinstance(value, dict)
        or value.get("schema_name") != "IsolatedSmokeExecutionPair"
        or value.get("schema_version") != "1.0.0"
    ):
        raise ValueError("execution_receipt_invalid")
    pair = SmokePair.create(
        smoke_id=str(value.get("smoke_id", "")),
        source_commit=str(value.get("source_commit", "")),
        source_tree=str(value.get("source_tree", "")),
        plan_sha256=str(value.get("plan_sha256", "")),
        bundle_sha256=str(value.get("bundle_sha256", "")),
        image_digest=str(value.get("image_digest", "")),
    )
    executions = {
        "positive": str(value.get("positive_execution", "")),
        "negative": str(value.get("negative_execution", "")),
    }
    expected_project_sha256 = str(value.get("expected_project_sha256", ""))
    if (
        value.get("positive_prefix") != pair.positive_prefix
        or value.get("negative_prefix") != pair.negative_prefix
        or executions["positive"] == executions["negative"]
        or not re.fullmatch(r"[0-9a-f]{64}", expected_project_sha256)
        or any(not re.fullmatch(r"recall-cohort-daily-[a-z0-9-]+", item) for item in executions.values())
    ):
        raise ValueError("execution_receipt_binding_invalid")
    return pair, executions, expected_project_sha256


def _semantic_result_valid(
    value: Mapping[str, Any], *, mode: str, pair: SmokePair
) -> set[str]:
    prefix = pair.positive_prefix if mode == "positive" else pair.negative_prefix
    failures: set[str] = set()
    expected = {
        "schema_name": "IsolatedSmokeCollectionVerification",
        "schema_version": "1.0.0",
        "verified": True,
        "writes": 0,
        "smoke_id": pair.smoke_id,
        "mode": mode.upper(),
        "collection_prefix": prefix,
        "source_commit": pair.source_commit,
        "plan_sha256": pair.plan_sha256,
        "preparation_bundle_sha256": pair.bundle_sha256,
        "image_digest": pair.image_digest,
        "execution_status": "COMPLETE" if mode == "positive" else "INCOMPLETE",
    }
    if any(value.get(key) != item for key, item in expected.items()):
        failures.add("semantic_collection_binding_invalid")
    cases = value.get("selected_case_ids")
    runs = value.get("run_ids")
    count = 4 if mode == "positive" else 1
    if not isinstance(cases, list) or not isinstance(runs, list) or len(cases) != count or len(runs) != count:
        failures.add("semantic_collection_count_invalid")
    mode_id = value.get("mode_receipt_artifact_id")
    mode_hash = value.get("mode_receipt_content_hash")
    if mode == "positive" and (not mode_id or not mode_hash):
        failures.add("positive_mode_receipt_missing")
    if mode == "negative" and (mode_id is not None or mode_hash is not None):
        failures.add("negative_mode_receipt_forbidden")
    cost = _mapping(value.get("cost"))
    if cost.get("reserved_usd_micros") != cost.get("reconciled_usd_micros"):
        failures.add("semantic_cost_invalid")
    return failures


def _snapshot_mode(
    *, mode: str, execution: Mapping[str, Any], semantic: Mapping[str, Any], telemetry: Mapping[str, Any]
) -> dict[str, object]:
    positive = mode == "positive"
    turns = telemetry.get("total_model_turns")
    return {
        "prefix_valid": True,
        "execution": dict(execution),
        "result": {
            "schema_name": "IsolatedSmokeResult",
            "schema_version": "1.0.0",
            "mode": mode.upper(),
            "case_count": len(semantic.get("selected_case_ids", [])),
            "run_count": len(semantic.get("run_ids", [])),
            "terminal_states": telemetry.get("terminal_states"),
            "policy_decision_count": telemetry.get("policy_decision_count"),
            "failure_receipt_count": telemetry.get("failure_receipt_count"),
            "failure_codes": telemetry.get("failure_codes", []),
            "total_model_turns": turns,
            "budget_limit": 24 if positive else 2,
            "budget_observed": turns,
            "writes_scope_exact": semantic.get("writes") == 0,
        },
        "roles": telemetry.get("roles"),
        "manifest_status": telemetry.get("manifest_status"),
        "mode_receipt_verified": telemetry.get("mode_receipt_verified"),
        "idempotency_verified": telemetry.get("idempotency_verified"),
        "lease_terminal_verified": telemetry.get("lease_terminal_verified"),
    }


def collect_from_receipt(
    receipt_path: Path,
    *,
    run_fn: Any = None,
    semantic_collect_fn: Callable[[str, SmokePair], Mapping[str, Any]] | None = None,
    telemetry_collect_fn: Callable[[str, SmokePair, Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, object]:
    pair, executions, expected_project_sha256 = _read_receipt(receipt_path)
    if run_fn is None:
        from repoint_cohort_job import _run_redacted

        run_fn = _run_redacted
    semantic_collect_fn = semantic_collect_fn or _collect_semantic_default
    telemetry_collect_fn = telemetry_collect_fn or _collect_telemetry_default
    modes: dict[str, dict[str, object]] = {}
    failures: set[str] = set()
    unknown: set[str] = set()
    principals: list[str | None] = []
    for mode in ("positive", "negative"):
        described = run_fn(
            "run",
            "jobs",
            "executions",
            "describe",
            executions[mode],
            f"--region={REGION}",
            "--format=json",
        )
        if described.returncode != 0:
            unknown.add(f"{mode}_execution_describe_not_verified")
            continue
        try:
            raw = json.loads(described.stdout)
        except json.JSONDecodeError:
            unknown.add(f"{mode}_execution_describe_not_verified")
            continue
        execution, execution_failures, principal = normalize_execution(
            raw,
            execution_id=executions[mode],
            mode=mode,
            pair=pair,
            expected_project_sha256=expected_project_sha256,
        )
        failures.update(execution_failures)
        principals.append(principal)
        try:
            semantic = semantic_collect_fn(mode, pair)
            telemetry = telemetry_collect_fn(mode, pair, semantic)
        except RuntimeError:
            # Core contract mismatches are deterministic evidence failures. Do
            # not expose artifact IDs or raw exception text in the report.
            failures.add(f"{mode}_durable_evidence_invalid")
            continue
        except Exception:  # unavailable external reads remain NOT_VERIFIED
            unknown.add(f"{mode}_durable_evidence_not_verified")
            continue
        failures.update(_semantic_result_valid(semantic, mode=mode, pair=pair))
        modes[mode] = _snapshot_mode(
            mode=mode, execution=execution, semantic=semantic, telemetry=telemetry
        )
    if len(principals) == 2 and (None in principals or principals[0] != principals[1]):
        failures.add("cross_execution_creator_mismatch")
    if len(modes) != 2:
        return {
            "verdict": FAIL if failures else NOT_VERIFIED,
            "positive": NOT_VERIFIED,
            "negative": NOT_VERIFIED,
            "aggregate_model_turns": 0,
            "codes": sorted(failures | unknown),
        }
    report = evaluate_evidence(
        modes,
        expected={
            "image_digest": pair.image_digest,
            "source_commit": pair.source_commit,
            "source_tree": pair.source_tree,
            "plan_sha256": pair.plan_sha256,
            "bundle_sha256": pair.bundle_sha256,
        },
    )
    codes = set(report["codes"]) | failures | unknown
    report["codes"] = sorted(codes)
    if failures:
        report["verdict"] = FAIL
    elif unknown and report["verdict"] != FAIL:
        report["verdict"] = NOT_VERIFIED
    return report


def _collect_semantic_default(mode: str, pair: SmokePair) -> Mapping[str, Any]:
    """Run Core's deterministic-ID verifier directly against exact-prefix data."""

    import hashlib as _hashlib

    from gcloud_redacted import resolve_project
    from recall.ledger.firestore import FirestoreLedger
    from recall.scheduler.compressed_plan import load_compressed_plan
    from recall.scheduler.compressed_preparation import (
        CompressedPreparationVerifier,
        load_compressed_bundle,
    )
    from recall.scheduler.model_cost import DEFAULT_MODEL_COST_POLICY, FirestoreModelCostLedger
    from recall.scheduler.smoke import (
        build_smoke_contract,
        smoke_manifest_artifact_id,
        smoke_mode_receipt_artifact_id,
        verify_persisted_smoke_artifacts,
    )

    root = Path(__file__).resolve().parents[2]
    plan = load_compressed_plan(root)
    bundle = load_compressed_bundle(root, expected_sha256=pair.bundle_sha256, plan=plan)
    prefix = pair.positive_prefix if mode == "positive" else pair.negative_prefix
    contract = build_smoke_contract(
        mode=mode,
        smoke_id=pair.smoke_id,
        collection_prefix=prefix,
        source_commit=pair.source_commit,
        plan_sha256=pair.plan_sha256,
        image_digest=pair.image_digest,
        expected_plan_sha256=pair.plan_sha256,
        expected_image_digest=pair.image_digest,
        preparation_bundle_sha256=pair.bundle_sha256,
        job_max_retries="0",
    )
    project = resolve_project()
    ledger = FirestoreLedger.from_default_credentials(
        collection_prefix=prefix,
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle),
        expected_project_sha256=_hashlib.sha256(project.encode("utf-8")).hexdigest(),
        database="(default)",
        require_live=True,
    )
    manifest_id = smoke_manifest_artifact_id(prefix)
    mode_id = smoke_mode_receipt_artifact_id(prefix) if mode == "positive" else None
    cost = FirestoreModelCostLedger(
        ledger.client,
        collection_name=f"{prefix}model_cost",
        hard_cap_usd_micros=DEFAULT_MODEL_COST_POLICY.hard_cap_usd_micros,
    ).snapshot()
    bindings = verify_persisted_smoke_artifacts(
        ledger=ledger,
        contract=contract,
        manifest_artifact_id=manifest_id,
        mode_receipt_artifact_id=mode_id,
        cost_snapshot=cost,
    )
    manifest = ledger.get_artifact(manifest_id)
    if manifest is None:
        raise RuntimeError("smoke_manifest_missing")
    return {
        "schema_name": "IsolatedSmokeCollectionVerification",
        "schema_version": "1.0.0",
        "verified": True,
        "writes": 0,
        "smoke_id": pair.smoke_id,
        "mode": mode.upper(),
        "collection_prefix": prefix,
        "source_commit": pair.source_commit,
        "plan_sha256": pair.plan_sha256,
        "preparation_bundle_sha256": pair.bundle_sha256,
        "image_digest": pair.image_digest,
        **bindings,
        "execution_status": manifest["execution_status"],
        "selected_case_ids": manifest["selected_case_ids"],
        "run_ids": manifest["run_ids"],
        "cost": {
            "reserved_usd_micros": cost.reserved_usd_micros,
            "reconciled_usd_micros": cost.reconciled_usd_micros,
        },
    }


def _validate_receipt_topology(
    terminal: Any,
    artifacts_by_id: Mapping[str, Any],
    *,
    started_validator: Callable[[Any, Any], None] | None = None,
    authorization_validator: Callable[[Any, Sequence[Any]], None] | None = None,
) -> None:
    """Bind one terminal receipt to its exact STARTED and auth receipts."""

    from recall.contracts import ContractError
    from recall.ledger.agent_step import (
        validate_started_receipt_binding,
        validate_tool_authorization_bindings,
    )

    started_validator = started_validator or validate_started_receipt_binding
    authorization_validator = (
        authorization_validator or validate_tool_authorization_bindings
    )
    started_id = terminal.payload.started_receipt_id
    started = artifacts_by_id.get(str(started_id))
    if started is None:
        raise RuntimeError("smoke_started_receipt_missing")
    authorization_ids = tuple(
        str(record["authorization_receipt_id"])
        for record in terminal.payload.tool_records
    )
    authorization_receipts = tuple(
        artifacts_by_id[item]
        for item in authorization_ids
        if item in artifacts_by_id
    )
    if len(authorization_receipts) != len(authorization_ids):
        raise RuntimeError("smoke_authorization_receipt_missing")
    try:
        started_validator(terminal, started)
        authorization_validator(terminal, authorization_receipts)
    except ContractError as exc:
        raise RuntimeError("smoke_receipt_topology_invalid") from exc


def _validate_terminal_pointers(record: Any, artifacts: Sequence[Any]) -> None:
    failures = {
        item.artifact_id
        for item in artifacts
        if item.schema_name == "FailureReceipt"
    }
    policies = {
        item.artifact_id
        for item in artifacts
        if item.schema_name == "PolicyDecision"
    }
    expected_policy = (
        set()
        if record.terminal_policy_decision_id is None
        else {record.terminal_policy_decision_id}
    )
    if failures != set(record.failure_receipt_ids) or policies != expected_policy:
        raise RuntimeError("smoke_terminal_pointer_mismatch")


def _trace_has_required_spans(trace: Mapping[str, Any], *, mode: str) -> bool | None:
    state = trace.get("state")
    if state in {"UNAVAILABLE", "DEGRADED"}:
        return None
    if state != "OBSERVED":
        return False
    span_names = trace.get("span_names")
    if not isinstance(span_names, list) or any(
        not isinstance(item, str) for item in span_names
    ):
        return False
    from recall.contracts.enums import AgentRole
    from recall.platform.fleet import (
        CONTROLLER_SPAN,
        FLEET_MEMBERS,
        fleet_trace_is_complete,
    )

    if mode == "positive":
        return fleet_trace_is_complete(span_names)
    watcher = next(
        item.span_name
        for item in FLEET_MEMBERS
        if item.role is AgentRole.EVIDENCE_WATCHER
    )
    return {CONTROLLER_SPAN, watcher}.issubset(set(span_names))


def _lease_is_inactive(record: Any, *, now: datetime) -> bool:
    expires_at = record.lease_expires_at
    if expires_at is None:
        return True
    if not isinstance(expires_at, datetime) or expires_at.tzinfo is None:
        return False
    return expires_at <= now


def _collect_telemetry_default(
    mode: str, pair: SmokePair, semantic: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Independently recount receipt, gateway, lifecycle, and trace surfaces."""

    import hashlib as _hashlib

    from gcloud_redacted import resolve_project
    from recall.contracts import ContractError, parse_artifact
    from recall.ledger.firestore import FirestoreLedger
    from recall.ledger.producers import PRODUCER_REGISTRY
    from recall.platform.config import PlatformConfig
    from recall.platform.observability import RestTraceClient, read_back_trace

    prefix = pair.positive_prefix if mode == "positive" else pair.negative_prefix
    project = resolve_project()
    ledger = FirestoreLedger.from_default_credentials(
        collection_prefix=prefix,
        expected_project_sha256=_hashlib.sha256(project.encode("utf-8")).hexdigest(),
        database="(default)",
        require_live=True,
    )
    trace_client = RestTraceClient(
        PlatformConfig(project, REGION, "collector", "global", "gs://recall-collector")
    )

    def parse_wire(wire: Mapping[str, Any]) -> Any:
        try:
            return parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
        except ContractError as exc:
            raise RuntimeError("smoke_artifact_contract_invalid") from exc

    manifest_wire = ledger.get_artifact(str(semantic["manifest_artifact_id"]))
    if manifest_wire is None:
        raise RuntimeError("smoke_manifest_missing")
    manifest = parse_wire(manifest_wire)
    payload = manifest.payload
    roles: list[dict[str, object]] = []
    failures: list[str] = []
    policies = 0
    terminal_states: list[str] = []
    idempotency_keys: set[str] = set()
    lifecycle_verified = True
    request_ids: set[str] = set()
    cost = _mapping(semantic.get("cost"))
    cost_reconciled = cost.get("reserved_usd_micros") == cost.get("reconciled_usd_micros")
    collected_at = datetime.now(UTC)
    for run_id in payload.run_ids:
        record = ledger.get_scan_run(run_id)
        if record is None:
            raise RuntimeError("smoke_run_missing")
        if record.scan_run_artifact_id is None:
            raise RuntimeError("smoke_scan_run_pointer_missing")
        scan_wire = ledger.get_artifact(record.scan_run_artifact_id)
        if scan_wire is None:
            raise RuntimeError("smoke_scan_run_artifact_missing")
        scan = parse_wire(scan_wire)
        if scan.schema_name != "ScanRun":
            raise RuntimeError("smoke_scan_run_pointer_invalid")
        terminal_states.append(record.state.value)
        if (
            record.state.value not in TERMINAL_STATES
            or record.lease_epoch != 1
            or scan.payload.attempt != 0
            or scan.payload.lease_epoch != 0
            or not _lease_is_inactive(record, now=collected_at)
        ):
            lifecycle_verified = False
        if scan.payload.idempotency_key in idempotency_keys:
            lifecycle_verified = False
        idempotency_keys.add(scan.payload.idempotency_key)
        events = ledger.list_scan_run_events(run_id)
        if [item.sequence for item in events] != list(range(1, len(events) + 1)):
            lifecycle_verified = False
        if any(
            item.lease_epoch != 1
            or item.event_code.value in {"lease_taken_over", "retry_scheduled"}
            for item in events
        ):
            lifecycle_verified = False
        artifacts = [parse_wire(wire) for wire in ledger.list_by_run(run_id)]
        artifacts_by_id = {item.artifact_id: item for item in artifacts}
        if len(artifacts_by_id) != len(artifacts):
            raise RuntimeError("smoke_artifact_id_duplicate")
        _validate_terminal_pointers(record, artifacts)
        for parsed in artifacts:
            if (
                parsed.schema_name == "AgentExecutionReceipt"
                and parsed.payload.execution_status.value in {"COMPLETED", "FAILED"}
            ):
                _validate_receipt_topology(parsed, artifacts_by_id)
                records = parsed.payload.tool_records
                calls = parsed.payload.tool_call_ids
                responses = parsed.payload.tool_response_ids
                linked = bool(records) and calls == responses
                request_ids.update(
                    str(item["request_id"])
                    for item in records
                )
                if parsed.payload.attempt != 1:
                    lifecycle_verified = False
                trace_id = parsed.payload.trace_id
                correlation = trace_id == scan.payload.trace_id
                trace = read_back_trace(trace_client, str(trace_id)) if correlation else {"state": "INVALID"}
                trace_observed = _trace_has_required_spans(trace, mode=mode)
                roles.append(
                    {
                        "role": parsed.payload.agent_role.value,
                        "status": parsed.payload.execution_status.value,
                        "turn_count": len(parsed.payload.turns),
                        "http_429_count": parsed.payload.http_429_count,
                        "tool_call_count": len(calls),
                        "tool_response_count": len(responses),
                        "authorization_linked": linked,
                        "actual_caller_verified": linked,
                        "trace_observed": trace_observed,
                        "cost_reconciled": cost_reconciled,
                    }
                )
                if parsed.payload.failure_code:
                    failures.append(parsed.payload.failure_code)
            elif parsed.schema_name == "PolicyDecision":
                policies += 1
    gateway_rows = list(ledger.client.collection(f"{prefix}tool_gateway_invocations").stream())
    gateway_ids: set[str] = set()
    for row in gateway_rows:
        value = row.to_dict()
        if value.get("state") != "COMPLETE" or value.get("status_code") != 200:
            lifecycle_verified = False
        gateway_ids.add(row.id)
    gateway_linked = gateway_ids == request_ids
    for role in roles:
        role["authorization_linked"] = bool(role["authorization_linked"] and gateway_linked)
        role["actual_caller_verified"] = bool(
            role["actual_caller_verified"] and gateway_linked
        )
    return {
        "roles": roles,
        "terminal_states": terminal_states,
        "policy_decision_count": policies,
        "failure_receipt_count": len(payload.failure_receipt_ids),
        "failure_codes": sorted(set(failures)),
        "total_model_turns": sum(int(item["turn_count"]) for item in roles),
        "manifest_status": payload.execution_status,
        "mode_receipt_verified": semantic.get("mode_receipt_artifact_id") is not None,
        "idempotency_verified": lifecycle_verified,
        "lease_terminal_verified": lifecycle_verified,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    report = collect_from_receipt(args.execution_receipt)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
