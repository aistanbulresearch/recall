from __future__ import annotations

from datetime import UTC, datetime, timedelta
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Callable
from uuid import NAMESPACE_URL, uuid5

import pytest

from recall.agents.full_audit import FullAuditCoordinator
from recall.agents.full_audit_models import RoleExecutionError
from recall.controller.tool_gateway_store import InMemoryGatewayInvocationStore
from recall.contracts import AgentRole
from recall.contracts import content_hash
from recall.contracts import parse_artifact
from recall.contracts.enums import ScanRunEventCode
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.ledger.memory import InMemoryLedger
from recall.scheduler.entrypoint import execute
from recall.scheduler.model_cost import (
    DEFAULT_MODEL_COST_POLICY,
    InMemoryModelCostLedger,
)
from recall.scheduler.smoke import (
    build_smoke_contract,
    derive_smoke_prefix,
    execute_isolated_smoke,
    smoke_manifest_artifact_id,
    smoke_mode_receipt_artifact_id,
    verify_persisted_smoke_artifacts,
    _require_empty_namespace,
)
from tests.agents.full_audit_double import DeterministicFullAuditRunner


ROOT = Path(__file__).parents[2]
SOURCE_COMMIT = "a" * 40
IMAGE_DIGEST = f"sha256:{'b' * 64}"
SMOKE_ID = "smoke0001"


class FailingWatcherRunner(DeterministicFullAuditRunner):
    async def execute(self, role, prompt, tools, context):
        result = await super().execute(role, prompt, tools, context)
        if role is AgentRole.EVIDENCE_WATCHER:
            raise RoleExecutionError(
                "agent_schema_invalid",
                turns=result.turns,
                tool_call_ids=result.tool_call_ids,
                tool_response_ids=result.tool_response_ids,
            )
        return result


class LedgerArtifactView:
    def __init__(
        self,
        ledger,
        transform: Callable = lambda _run_id, rows: rows,
        record_transform: Callable = lambda record: record,
    ):
        self._ledger = ledger
        self._transform = transform
        self._record_transform = record_transform

    def __getattr__(self, name):
        return getattr(self._ledger, name)

    def list_by_run(self, run_id):
        return self._transform(run_id, list(self._ledger.list_by_run(run_id)))

    def get_scan_run(self, run_id):
        return self._record_transform(self._ledger.get_scan_run(run_id))


def _bundle_sha() -> str:
    return sha256(
        (ROOT / "artifacts/evidence/cohort-compression/preparation-bundle-v2.json")
        .read_bytes()
    ).hexdigest()


def _environment(plan_sha: str) -> dict[str, str]:
    return {
        "RECALL_SCHEDULER_MODE": "COMPRESSED_V3",
        "RECALL_COMPRESSED_PREPARATION_SHA256": _bundle_sha(),
        "RECALL_SOURCE_COMMIT": SOURCE_COMMIT,
        "RECALL_IMAGE_DIGEST": IMAGE_DIGEST,
        "RECALL_EXPECTED_PROJECT_SHA256": "c" * 64,
        "RECALL_PROVIDER_RPM": "8",
        "RECALL_SMOKE_JOB_MAX_RETRIES": "0",
        "RECALL_SMOKE_EXPECTED_PLAN_SHA256": plan_sha,
        "RECALL_SMOKE_EXPECTED_IMAGE_DIGEST": IMAGE_DIGEST,
        "RECALL_NCBI_TOOL": "recall-smoke-test",
        "RECALL_NCBI_EMAIL": "smoke@example.invalid",
    }


def _factory(runner, *, now: datetime | None = None):
    coordinators: list[FullAuditCoordinator] = []
    effective_now = now or datetime(2026, 8, 29, 16, 0, tzinfo=UTC)

    def build(ledger):
        coordinator = FullAuditCoordinator(
            ledger,
            role_runner=runner,
            invocation_store=InMemoryGatewayInvocationStore(),
            cost_ledger=InMemoryModelCostLedger(
                hard_cap_usd_micros=75_000_000
            ),
            cost_policy=DEFAULT_MODEL_COST_POLICY,
            clock=lambda: effective_now,
        )
        coordinators.append(coordinator)
        return coordinator

    return build, coordinators


def _invoke(mode: str, runner, *, now: datetime | None = None):
    from recall.scheduler.compressed_plan import load_compressed_plan

    plan = load_compressed_plan(ROOT)
    prefix = derive_smoke_prefix(
        source_commit=SOURCE_COMMIT,
        plan_sha256=plan.sha256,
        mode=mode,
        smoke_id=SMOKE_ID,
    )
    ledger_calls: list[str] = []
    ledgers: dict[str, InMemoryLedger] = {}

    def ledger_factory(*, collection_prefix, privacy_receipt_verifier, **_kwargs):
        ledger_calls.append(collection_prefix)
        ledger = InMemoryLedger(
            privacy_receipt_verifier=privacy_receipt_verifier
        )
        ledgers[collection_prefix] = ledger
        return ledger

    effective_now = now or plan.by_id("c6").window_start
    full_audit_factory, coordinators = _factory(runner, now=effective_now)
    result = execute(
        [
            "--smoke-mode",
            mode,
            "--smoke-id",
            SMOKE_ID,
            "--smoke-prefix",
            prefix,
        ],
        environment=_environment(plan.sha256),
        now_factory=lambda: effective_now,
        ledger_factory=ledger_factory,
        full_audit_factory=full_audit_factory,
        repo_root=ROOT,
    )
    return result, prefix, ledger_calls, ledgers[prefix], coordinators[0]


def test_positive_smoke_uses_actual_start_deadlines_after_historical_window(
    monkeypatch,
) -> None:
    from recall.scheduler.compressed_plan import load_compressed_plan
    import recall.scheduler.smoke as smoke_module

    plan = load_compressed_plan(ROOT)
    cycle = plan.by_id("c6")
    actual_start = cycle.end_to_end_deadline + timedelta(days=1)
    observed: dict[str, datetime] = {}
    real_phase = smoke_module.execute_full_audit_phase

    def observe_phase(*args, **kwargs):
        observed["agent_deadline_at"] = kwargs["agent_deadline_at"]
        return real_phase(*args, **kwargs)

    monkeypatch.setattr(smoke_module, "execute_full_audit_phase", observe_phase)

    result, _prefix, _calls, ledger, _coordinator = _invoke(
        "positive",
        DeterministicFullAuditRunner(),
        now=actual_start,
    )

    assert set(result["terminal_states"]) == {"NO_ACTION"}
    assert observed["agent_deadline_at"] == actual_start + timedelta(
        seconds=cycle.agent_timeout_seconds
    )
    expected_deadline = (
        actual_start + timedelta(seconds=cycle.execution_timeout_seconds)
    ).isoformat().replace("+00:00", "Z")
    for run_id in result["run_ids"]:
        record = ledger.get_scan_run(run_id)
        assert record is not None
        wire = ledger.get_artifact(record.scan_run_artifact_id)
        assert wire is not None
        assert wire["scheduled_for"] == cycle.schedule_epoch
        assert wire["deadline_at"] == expected_deadline


def test_negative_smoke_preserves_typed_failure_after_historical_window() -> None:
    from recall.scheduler.compressed_plan import load_compressed_plan

    cycle = load_compressed_plan(ROOT).by_id("c6")
    actual_start = cycle.end_to_end_deadline + timedelta(seconds=1)
    result, *_ = _invoke(
        "negative",
        FailingWatcherRunner(),
        now=actual_start,
    )

    assert result["terminal_states"] == ["HALTED"]
    assert result["technical_failure_codes"] == ["agent_schema_invalid"]
    assert result["policy_decision_count"] == 0


@pytest.mark.parametrize("invalid_start", [None, datetime(2026, 8, 31, 0, 0)])
def test_smoke_missing_or_malformed_actual_start_fails_before_writes(
    invalid_start,
) -> None:
    from recall.scheduler.compressed_plan import load_compressed_plan

    plan = load_compressed_plan(ROOT)
    prefix = derive_smoke_prefix(
        source_commit=SOURCE_COMMIT,
        plan_sha256=plan.sha256,
        mode="positive",
        smoke_id=SMOKE_ID,
    )
    contract = build_smoke_contract(
        mode="positive",
        smoke_id=SMOKE_ID,
        collection_prefix=prefix,
        source_commit=SOURCE_COMMIT,
        plan_sha256=plan.sha256,
        image_digest=IMAGE_DIGEST,
        expected_plan_sha256=plan.sha256,
        expected_image_digest=IMAGE_DIGEST,
        preparation_bundle_sha256=_bundle_sha(),
        job_max_retries="0",
    )
    ledger = InMemoryLedger()

    with pytest.raises(RuntimeError, match="smoke_deadline_contract_invalid"):
        execute_isolated_smoke(
            contract=contract,
            ledger=ledger,
            plan=plan,
            bundle=None,  # type: ignore[arg-type]
            coordinator=None,  # type: ignore[arg-type]
            now=invalid_start,  # type: ignore[arg-type]
        )

    assert all(
        ledger.read_back_count(name) == 0 for name in ledger.collection_names
    )


def test_smoke_over_budget_deadline_contract_fails_before_writes() -> None:
    from recall.scheduler.compressed_plan import load_compressed_plan

    plan = load_compressed_plan(ROOT)
    c6 = plan.by_id("c6")
    mutated = replace(
        plan,
        cycles=tuple(
            replace(item, execution_timeout_seconds=28_801)
            if item.cycle_id == "c6"
            else item
            for item in plan.cycles
        ),
    )
    prefix = derive_smoke_prefix(
        source_commit=SOURCE_COMMIT,
        plan_sha256=plan.sha256,
        mode="positive",
        smoke_id=SMOKE_ID,
    )
    contract = build_smoke_contract(
        mode="positive",
        smoke_id=SMOKE_ID,
        collection_prefix=prefix,
        source_commit=SOURCE_COMMIT,
        plan_sha256=plan.sha256,
        image_digest=IMAGE_DIGEST,
        expected_plan_sha256=plan.sha256,
        expected_image_digest=IMAGE_DIGEST,
        preparation_bundle_sha256=_bundle_sha(),
        job_max_retries="0",
    )
    ledger = InMemoryLedger()

    with pytest.raises(RuntimeError, match="smoke_deadline_contract_invalid"):
        execute_isolated_smoke(
            contract=contract,
            ledger=ledger,
            plan=mutated,
            bundle=None,  # type: ignore[arg-type]
            coordinator=None,  # type: ignore[arg-type]
            now=c6.end_to_end_deadline + timedelta(seconds=1),
        )

    assert all(
        ledger.read_back_count(name) == 0 for name in ledger.collection_names
    )


def test_positive_smoke_runs_four_cases_through_all_three_roles() -> None:
    runner = DeterministicFullAuditRunner()
    result, prefix, ledger_calls, ledger, coordinator = _invoke(
        "positive", runner
    )

    assert result["schema_name"] == "IsolatedSmokeResult"
    assert result["schema_version"] == "1.0.0"
    assert result["mode"] == "POSITIVE"
    assert result["collection_prefix"] == prefix
    assert ledger_calls == [prefix]
    assert len(result["selected_case_ids"]) == 4
    assert len(set(result["selected_case_ids"])) == 4
    assert len(result["run_ids"]) == 4
    assert set(result["terminal_states"]) == {"NO_ACTION"}
    assert set(result["audit_statuses"]) == {"COMPLETE"}
    assert result["role_receipt_counts"] == {
        "EVIDENCE_WATCHER": 4,
        "EVIDENCE_ASSESSOR": 4,
        "CITATION_AUDITOR": 4,
    }
    assert result["policy_decision_count"] == 4
    assert result["failure_receipt_ids"] == []
    assert result["total_model_turns"] <= 24
    assert result["turn_budget"] == {"limit": 24, "observed": 12}
    assert result["provider_max_429_retries"] == 0
    assert result["job_max_retries"] == 0
    assert coordinator.cost_snapshot().reserved_usd_micros == (
        coordinator.cost_snapshot().reconciled_usd_micros
    )
    assert ledger.read_back_count("scan_runs") == 4
    manifest = ledger.get_artifact(result["manifest_artifact_id"])
    mode_receipt = ledger.get_artifact(result["mode_receipt_artifact_id"])
    assert manifest is not None
    assert mode_receipt is not None
    assert parse_artifact(
        manifest, authorized_producers=PRODUCER_REGISTRY
    ).schema_name == "IsolatedSmokeManifest"
    assert manifest["execution_status"] == "COMPLETE"
    assert manifest["selected_case_ids"] == result["selected_case_ids"]
    assert manifest["agent_execution_receipt_ids"] == result[
        "agent_execution_receipt_ids"
    ]
    assert manifest["turn_budget_limit"] == 24
    assert manifest["aggregate_turn_budget_limit"] == 26
    assert manifest["provider_max_429_retries"] == 0
    assert manifest["job_max_retries"] == 0
    assert set(manifest["input_artifact_ids"]) == {
        *manifest["agent_execution_receipt_ids"],
        *manifest["policy_decision_ids"],
    }
    assert parse_artifact(
        mode_receipt, authorized_producers=PRODUCER_REGISTRY
    ).schema_name == "IsolatedSmokeModeReceipt"
    assert mode_receipt["manifest_artifact_id"] == manifest["artifact_id"]
    assert mode_receipt["manifest_content_hash"] == manifest["content_hash"]
    assert mode_receipt["agent_execution_receipt_ids"] == manifest[
        "agent_execution_receipt_ids"
    ]
    assert set(mode_receipt["input_artifact_ids"]) == {
        manifest["artifact_id"],
        *manifest["agent_execution_receipt_ids"],
    }
    assert mode_receipt["validation_status"] == "PASS"
    assert result["manifest_artifact_id"] == smoke_manifest_artifact_id(prefix)
    assert result["mode_receipt_artifact_id"] == (
        smoke_mode_receipt_artifact_id(prefix)
    )
    contract = _contract_from_result(result)
    assert verify_persisted_smoke_artifacts(
        ledger=ledger,
        contract=contract,
        manifest_artifact_id=smoke_manifest_artifact_id(prefix),
        mode_receipt_artifact_id=smoke_mode_receipt_artifact_id(prefix),
        cost_snapshot=result["cost"],
    )["mode_receipt_artifact_id"] == result["mode_receipt_artifact_id"]
    for run_id in result["run_ids"]:
        events = ledger.list_scan_run_events(run_id)
        assert sum(
            item.event_code is ScanRunEventCode.LEASE_ACQUIRED
            for item in events
        ) == 1
        assert all(
            item.event_code
            not in {
                ScanRunEventCode.LEASE_TAKEN_OVER,
                ScanRunEventCode.RETRY_SCHEDULED,
            }
            for item in events
        )
    with pytest.raises(RuntimeError, match="smoke_cost_snapshot_mismatch"):
        verify_persisted_smoke_artifacts(
            ledger=ledger,
            contract=contract,
            manifest_artifact_id=smoke_manifest_artifact_id(prefix),
            mode_receipt_artifact_id=smoke_mode_receipt_artifact_id(prefix),
            cost_snapshot={
                "reserved_usd_micros": result["cost"][
                    "reserved_usd_micros"
                ] + 1,
                "reconciled_usd_micros": result["cost"][
                    "reconciled_usd_micros"
                ],
            },
        )

    first_run = result["run_ids"][0]
    first_receipt = next(
        wire
        for wire in ledger.list_by_run(first_run)
        if wire["schema_name"] == "AgentExecutionReceipt"
        and wire["execution_status"] == "COMPLETED"
    )
    omitted_id = first_receipt["artifact_id"]
    extra_receipt = dict(first_receipt)
    extra_receipt["artifact_id"] = str(
        uuid5(NAMESPACE_URL, f"{first_receipt['artifact_id']}:extra")
    )
    extra_receipt["content_hash"] = content_hash(extra_receipt)
    extra_view = LedgerArtifactView(
        ledger,
        lambda run_id, rows: (
            [*rows, extra_receipt] if run_id == first_run else rows
        ),
    )
    with pytest.raises(
        RuntimeError, match="smoke_(per_run_topology|manifest_artifact_set)"
    ):
        verify_persisted_smoke_artifacts(
            ledger=extra_view,
            contract=contract,
            manifest_artifact_id=smoke_manifest_artifact_id(prefix),
            mode_receipt_artifact_id=smoke_mode_receipt_artifact_id(prefix),
            cost_snapshot=result["cost"],
        )

    pointer_view = LedgerArtifactView(
        ledger,
        record_transform=lambda record: (
            replace(record, terminal_policy_decision_id=str(uuid5(
                NAMESPACE_URL, f"{record.run_id}:wrong-policy"
            )))
            if record.run_id == first_run
            else record
        ),
    )
    with pytest.raises(RuntimeError, match="smoke_run_terminal_pointer_invalid"):
        verify_persisted_smoke_artifacts(
            ledger=pointer_view,
            contract=contract,
            manifest_artifact_id=smoke_manifest_artifact_id(prefix),
            mode_receipt_artifact_id=smoke_mode_receipt_artifact_id(prefix),
            cost_snapshot=result["cost"],
        )

    second_run = result["run_ids"][1]
    redistributed = dict(first_receipt)
    redistributed["artifact_id"] = str(
        uuid5(NAMESPACE_URL, f"{first_receipt['artifact_id']}:{second_run}")
    )
    redistributed["run_id"] = second_run
    redistributed["case_id"] = result["selected_case_ids"][1]
    redistributed["content_hash"] = content_hash(redistributed)

    def redistribute(run_id, rows):
        if run_id == first_run:
            return [
                wire for wire in rows if wire["artifact_id"] != omitted_id
            ]
        if run_id == second_run:
            return [*rows, redistributed]
        return rows

    with pytest.raises(RuntimeError, match="smoke_per_run_topology_invalid"):
        verify_persisted_smoke_artifacts(
            ledger=LedgerArtifactView(ledger, redistribute),
            contract=contract,
            manifest_artifact_id=smoke_manifest_artifact_id(prefix),
            mode_receipt_artifact_id=smoke_mode_receipt_artifact_id(prefix),
            cost_snapshot=result["cost"],
        )

    omitted_view = LedgerArtifactView(
        ledger,
        lambda run_id, rows: [
            wire
            for wire in rows
            if run_id != first_run or wire["artifact_id"] != omitted_id
        ],
    )
    with pytest.raises(
        RuntimeError, match="smoke_(per_run_topology|manifest_artifact_set)"
    ):
        verify_persisted_smoke_artifacts(
            ledger=omitted_view,
            contract=contract,
            manifest_artifact_id=smoke_manifest_artifact_id(prefix),
            mode_receipt_artifact_id=smoke_mode_receipt_artifact_id(prefix),
            cost_snapshot=result["cost"],
        )


def test_negative_smoke_is_disjoint_and_preserves_typed_failure_evidence() -> None:
    positive, *_ = _invoke("positive", DeterministicFullAuditRunner())
    negative, prefix, ledger_calls, ledger, coordinator = _invoke(
        "negative", FailingWatcherRunner()
    )

    assert set(positive["selected_case_ids"]).isdisjoint(
        negative["selected_case_ids"]
    )
    assert len(negative["selected_case_ids"]) == 1
    assert negative["mode"] == "NEGATIVE"
    assert ledger_calls == [prefix]
    assert negative["terminal_states"] == ["HALTED"]
    assert negative["audit_statuses"] == ["INCOMPLETE"]
    assert negative["policy_decision_ids"] == []
    assert negative["policy_decision_count"] == 0
    assert negative["technical_failure_codes"] == ["agent_schema_invalid"]
    assert negative["role_receipt_counts"] == {"EVIDENCE_WATCHER": 1}
    assert negative["total_model_turns"] <= 2
    assert negative["turn_budget"] == {"limit": 2, "observed": 1}
    assert len(negative["agent_execution_receipt_ids"]) == 1
    receipt = ledger.get_artifact(negative["agent_execution_receipt_ids"][0])
    assert receipt is not None
    assert receipt["execution_status"] == "FAILED"
    assert receipt["failure_code"] == "agent_schema_invalid"
    assert receipt["tool_call_ids"] == receipt["tool_response_ids"]
    assert len(receipt["tool_call_ids"]) == 1
    assert len(receipt["tool_records"]) == 1
    assert coordinator.cost_snapshot().reserved_usd_micros == (
        coordinator.cost_snapshot().reconciled_usd_micros
    )
    manifest = ledger.get_artifact(negative["manifest_artifact_id"])
    assert manifest is not None
    assert manifest["execution_status"] == "INCOMPLETE"
    assert manifest["failure_receipt_ids"] == negative["failure_receipt_ids"]
    assert manifest["agent_execution_receipt_ids"] == negative[
        "agent_execution_receipt_ids"
    ]
    assert manifest["turn_budget_limit"] == 2
    assert manifest["aggregate_turn_budget_limit"] == 26
    assert set(manifest["input_artifact_ids"]) == {
        *manifest["agent_execution_receipt_ids"],
        *manifest["failure_receipt_ids"],
    }
    assert negative["mode_receipt_artifact_id"] is None
    assert negative["mode_receipt_content_hash"] is None
    assert sum(
        item["schema_name"] == "IsolatedSmokeModeReceipt"
        for item in ledger.list_by_run(negative["run_ids"][0])
    ) == 0
    contract = _contract_from_result(negative)
    with pytest.raises(RuntimeError, match="smoke_run_terminal_pointer_invalid"):
        verify_persisted_smoke_artifacts(
            ledger=LedgerArtifactView(
                ledger,
                record_transform=lambda record: replace(
                    record, failure_receipt_ids=()
                ),
            ),
            contract=contract,
            manifest_artifact_id=negative["manifest_artifact_id"],
            mode_receipt_artifact_id=None,
            cost_snapshot=negative["cost"],
        )


def _contract_from_result(result):
    from recall.scheduler.smoke import build_smoke_contract

    return build_smoke_contract(
        mode=str(result["mode"]).lower(),
        smoke_id=str(result["smoke_id"]),
        collection_prefix=str(result["collection_prefix"]),
        source_commit=str(result["source_commit"]),
        plan_sha256=str(result["plan_sha256"]),
        image_digest=str(result["image_digest"]),
        expected_plan_sha256=str(result["plan_sha256"]),
        expected_image_digest=str(result["image_digest"]),
        preparation_bundle_sha256=str(
            result["preparation_bundle_sha256"]
        ),
        job_max_retries="0",
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["--smoke-mode", "positive"],
        ["--smoke-id", SMOKE_ID],
        ["--smoke-mode", "negative", "--smoke-id", SMOKE_ID],
    ],
)
def test_partial_smoke_cli_fails_before_ledger_construction(argv) -> None:
    calls = 0

    def forbidden(**_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("ledger_must_not_be_constructed")

    with pytest.raises(RuntimeError, match="smoke_contract_incomplete"):
        execute(
            argv,
            environment={"RECALL_SCHEDULER_MODE": "COMPRESSED_V3"},
            ledger_factory=forbidden,
            repo_root=ROOT,
        )
    assert calls == 0


def test_smoke_prefix_and_plan_digest_mismatch_fail_before_writes() -> None:
    from recall.scheduler.compressed_plan import load_compressed_plan

    plan = load_compressed_plan(ROOT)
    calls = 0

    def forbidden(**_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("ledger_must_not_be_constructed")

    with pytest.raises(RuntimeError, match="smoke_collection_prefix_mismatch"):
        execute(
            [
                "--smoke-mode",
                "positive",
                "--smoke-id",
                SMOKE_ID,
                "--smoke-prefix",
                "dev_recall_m2_compressed_forbidden_",
            ],
            environment=_environment(plan.sha256),
            ledger_factory=forbidden,
            repo_root=ROOT,
        )
    assert calls == 0

    environment = _environment("d" * 64)
    prefix = derive_smoke_prefix(
        source_commit=SOURCE_COMMIT,
        plan_sha256=plan.sha256,
        mode="positive",
        smoke_id=SMOKE_ID,
    )
    with pytest.raises(RuntimeError, match="smoke_plan_sha256_mismatch"):
        execute(
            [
                "--smoke-mode",
                "positive",
                "--smoke-id",
                SMOKE_ID,
                "--smoke-prefix",
                prefix,
            ],
            environment=environment,
            ledger_factory=forbidden,
            repo_root=ROOT,
        )
    assert calls == 0


def test_reusing_smoke_id_fails_before_any_second_execution_write() -> None:
    from recall.scheduler.compressed_plan import load_compressed_plan

    plan = load_compressed_plan(ROOT)
    prefix = derive_smoke_prefix(
        source_commit=SOURCE_COMMIT,
        plan_sha256=plan.sha256,
        mode="negative",
        smoke_id=SMOKE_ID,
    )
    ledger: InMemoryLedger | None = None
    factory, _coordinators = _factory(FailingWatcherRunner())

    def ledger_factory(*, privacy_receipt_verifier, **_kwargs):
        nonlocal ledger
        if ledger is None:
            ledger = InMemoryLedger(
                privacy_receipt_verifier=privacy_receipt_verifier
            )
        return ledger

    args = [
        "--smoke-mode",
        "negative",
        "--smoke-id",
        SMOKE_ID,
        "--smoke-prefix",
        prefix,
    ]
    execute(
        args,
        environment=_environment(plan.sha256),
        now_factory=lambda: plan.by_id("c6").window_start,
        ledger_factory=ledger_factory,
        full_audit_factory=factory,
        repo_root=ROOT,
    )
    assert ledger is not None
    before = {
        name: ledger.read_back_count(name) for name in ledger.collection_names
    }

    with pytest.raises(RuntimeError, match="smoke_id_already_used"):
        execute(
            args,
            environment=_environment(plan.sha256),
            now_factory=lambda: plan.by_id("c6").window_start,
            ledger_factory=ledger_factory,
            full_audit_factory=factory,
            repo_root=ROOT,
        )

    assert {
        name: ledger.read_back_count(name) for name in ledger.collection_names
    } == before


def test_auxiliary_firestore_namespace_must_be_empty_before_smoke_writes() -> None:
    class Query:
        def limit(self, _count):
            return self

        def stream(self):
            return iter((object(),))

    class Client:
        def collection(self, name):
            assert name.startswith("dev_recall_smoke_")
            return Query()

    class Ledger:
        collection_names = ("artifacts",)
        collection_prefix = (
            "dev_recall_smoke_aaaaaaaaaaaa_bbbbbbbbbbbb_positive_smoke0001_"
        )
        client = Client()

        def read_back_count(self, _name):
            return 0

    with pytest.raises(RuntimeError, match="smoke_id_already_used"):
        _require_empty_namespace(Ledger())
