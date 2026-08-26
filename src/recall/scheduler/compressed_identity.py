from __future__ import annotations

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


def _cycle_identity(plan: CompressedPlan, cycle: CompressedCycle) -> str:
    return (
        "recall:compressed-cycle:"
        f"{plan.sha256}:{plan.version}:{cycle.cycle_id}:"
        f"{cycle.cycle_index}:{cycle.cohort_due_date.isoformat()}"
    )
