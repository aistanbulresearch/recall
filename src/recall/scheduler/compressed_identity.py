from __future__ import annotations

from dataclasses import replace
from uuid import NAMESPACE_URL, UUID, uuid5

from .compressed_plan import CompressedCycle, CompressedPlan


def tick_run_id(plan: CompressedPlan, cycle: CompressedCycle) -> str:
    return str(uuid5(NAMESPACE_URL, _cycle_identity(plan, cycle)))


def manifest_artifact_id(plan: CompressedPlan, cycle: CompressedCycle) -> str:
    return str(uuid5(UUID(tick_run_id(plan, cycle)), "cohort-day-manifest-v3"))


def mode_receipt_artifact_id(plan: CompressedPlan, cycle: CompressedCycle) -> str:
    return str(uuid5(UUID(tick_run_id(plan, cycle)), "cohort-data-mode-receipt-v3"))


def trace_id(plan: CompressedPlan, cycle: CompressedCycle, case_id: str) -> str:
    return str(uuid5(UUID(tick_run_id(plan, cycle)), f"trace:{case_id}"))


def prepared_watch_artifact_id(
    case_id: str, cycle: CompressedCycle
) -> str:
    return str(
        uuid5(
            UUID(case_id),
            f"compressed-watch-case:{cycle.cycle_id}:{cycle.schedule_epoch}",
        )
    )


def ramp_gate_receipt_id(
    plan: CompressedPlan, cycle: CompressedCycle, snapshot_sha256: str
) -> str:
    if cycle.cycle_index < 3:
        raise RuntimeError("compressed_ramp_gate_requires_runnable_cycle")
    return str(
        uuid5(
            UUID(tick_run_id(plan, cycle)),
            f"ramp-gate-v1:{snapshot_sha256}",
        )
    )


def legacy_failure_receipt_id(plan: CompressedPlan, cycle: CompressedCycle) -> str:
    if cycle.cycle_id != "c1":
        raise RuntimeError("compressed_legacy_failure_only_c1")
    return str(uuid5(UUID(tick_run_id(plan, cycle)), "legacy-day2-failure"))


def headroom_receipt_id(
    plan: CompressedPlan, cycle: CompressedCycle, snapshot_sha256: str
) -> str:
    if cycle.cycle_id != "c6":
        raise RuntimeError("compressed_headroom_only_c6")
    return str(
        uuid5(
            UUID(tick_run_id(plan, cycle)),
            f"c6-headroom-gate-v1:{snapshot_sha256}",
        )
    )


def collection_prefix(plan: CompressedPlan, cycle: CompressedCycle) -> str:
    return (
        f"dev_recall_m2_compressed_p{plan.sha256[:12]}_{cycle.cycle_id}_"
        f"{cycle.cohort_due_date:%Y%m%d}_"
    )


def evidence_plan(plan: CompressedPlan, cycle: CompressedCycle) -> CompressedPlan:
    successor_index = cycle.cycle_index
    if successor_index < len(plan.cycles):
        binding = plan.cycles[successor_index].predecessor
        if (
            binding is not None
            and binding.cycle_id == cycle.cycle_id
            and binding.binding == "EXTERNAL_PLAN"
        ):
            assert binding.plan_sha256 is not None
            return replace(plan, sha256=binding.plan_sha256)
    return plan


def evidence_collection_prefix(plan: CompressedPlan, cycle: CompressedCycle) -> str:
    successor_index = cycle.cycle_index
    if successor_index < len(plan.cycles):
        binding = plan.cycles[successor_index].predecessor
        if binding is not None and binding.binding == "EXTERNAL_PLAN":
            assert binding.collection_prefix is not None
            return binding.collection_prefix
    return collection_prefix(plan, cycle)


def evidence_manifest_artifact_id(plan: CompressedPlan, cycle: CompressedCycle) -> str:
    successor_index = cycle.cycle_index
    if successor_index < len(plan.cycles):
        binding = plan.cycles[successor_index].predecessor
        if binding is not None and binding.binding == "EXTERNAL_PLAN":
            assert binding.manifest_artifact_id is not None
            return binding.manifest_artifact_id
    return manifest_artifact_id(plan, cycle)


def evidence_mode_receipt_artifact_id(plan: CompressedPlan, cycle: CompressedCycle) -> str:
    successor_index = cycle.cycle_index
    if successor_index < len(plan.cycles):
        binding = plan.cycles[successor_index].predecessor
        if binding is not None and binding.binding == "EXTERNAL_PLAN":
            assert binding.mode_receipt_artifact_id is not None
            return binding.mode_receipt_artifact_id
    return mode_receipt_artifact_id(evidence_plan(plan, cycle), cycle)


def evidence_legacy_failure_receipt_id(plan: CompressedPlan) -> str:
    c1 = plan.by_id("c1")
    return legacy_failure_receipt_id(evidence_plan(plan, c1), c1)


def _cycle_identity(plan: CompressedPlan, cycle: CompressedCycle) -> str:
    return (
        "recall:compressed-cycle:"
        f"{plan.sha256}:{plan.version}:{cycle.cycle_id}:"
        f"{cycle.cycle_index}:{cycle.cohort_due_date.isoformat()}"
    )
