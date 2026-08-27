from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from recall.contracts import DataMode
from recall.contracts.enums import DataComposition

from .cohort import MANAGED_COHORT, ManagedCohortCase
from .compressed_plan import CompressedCycle


ONBOARDING_CASE_COUNT = 450
RAMP_SIZES = {"c3": 20, "c4": 80, "c5": 200}


@dataclass(frozen=True, slots=True)
class CompressedCohortCase:
    case_id: str
    cycle_id: str
    next_scan_at: str
    cursor: str
    data_mode: DataMode
    declared_composition: DataComposition
    vcv: str | None = None


def cases_for_cycle(cycle: CompressedCycle) -> tuple[CompressedCohortCase, ...]:
    if cycle.cycle_id in {"c1", "c2"}:
        source = tuple(
            item
            for item in MANAGED_COHORT
            if item.due_date == cycle.cohort_due_date
        )
        source = tuple(_bind_existing(item, cycle) for item in source)
    else:
        pool = _unrun_pool(cycle)
        if cycle.cycle_id == "c3":
            source = pool[:20]
        elif cycle.cycle_id == "c4":
            source = pool[20:100]
        elif cycle.cycle_id == "c5":
            source = pool[100:300]
        elif cycle.cycle_id == "c6":
            source = pool
        else:
            raise RuntimeError("compressed_cycle_case_set_unknown")
    if len(source) != cycle.runs_predicted:
        raise RuntimeError("compressed_cycle_case_count_mismatch")
    return tuple(sorted(source, key=lambda item: item.case_id))


def all_compressed_cases(
    cycles: tuple[CompressedCycle, ...],
) -> tuple[CompressedCohortCase, ...]:
    historical = tuple(
        CompressedCohortCase(
            case_id=item.case_id,
            cycle_id="historical-day1",
            next_scan_at=item.next_scan_at,
            cursor=item.cursor,
            data_mode=item.data_mode,
            declared_composition=item.declared_composition,
            vcv=item.vcv,
        )
        for item in MANAGED_COHORT
        if item.due_date.isoformat() == "2026-08-25"
    )
    values = historical + tuple(
        item for cycle in cycles for item in cases_for_cycle(cycle)
    )
    if len({(item.case_id, item.cycle_id) for item in values}) != len(values):
        raise RuntimeError("compressed_evaluation_identity_collision")
    return values


def portfolio_cases(
    cycles: tuple[CompressedCycle, ...],
) -> tuple[CompressedCohortCase, ...]:
    """Return 462 distinct logical cases; repeated evaluations are excluded."""
    historical = tuple(
        CompressedCohortCase(
            case_id=item.case_id,
            cycle_id="historical-day1",
            next_scan_at=item.next_scan_at,
            cursor=item.cursor,
            data_mode=item.data_mode,
            declared_composition=item.declared_composition,
            vcv=item.vcv,
        )
        for item in MANAGED_COHORT
        if item.due_date.isoformat() == "2026-08-25"
    )
    values = historical + cases_for_cycle(cycles[0]) + cases_for_cycle(cycles[1])
    values += cases_for_cycle(cycles[-1])
    if len(values) != 462 or len({item.case_id for item in values}) != 462:
        raise RuntimeError("compressed_portfolio_identity_invalid")
    return tuple(sorted(values, key=lambda item: item.case_id))


def _bind_existing(
    item: ManagedCohortCase, cycle: CompressedCycle
) -> CompressedCohortCase:
    return CompressedCohortCase(
        case_id=item.case_id,
        cycle_id=cycle.cycle_id,
        next_scan_at=cycle.schedule_epoch,
        cursor=item.cursor,
        data_mode=item.data_mode,
        declared_composition=item.declared_composition,
        vcv=item.vcv,
    )


def _unrun_pool(
    cycle: CompressedCycle,
) -> tuple[CompressedCohortCase, ...]:
    existing = tuple(
        CompressedCohortCase(
            case_id=item.case_id,
            cycle_id=cycle.cycle_id,
            next_scan_at=cycle.schedule_epoch,
            cursor=item.cursor,
            data_mode=item.data_mode,
            declared_composition=item.declared_composition,
            vcv=item.vcv,
        )
        for item in MANAGED_COHORT
        if item.due_date.isoformat() in {"2026-08-28", "2026-08-29", "2026-08-30"}
    )
    onboarding = tuple(
        CompressedCohortCase(
            case_id=str(
                uuid5(NAMESPACE_URL, f"recall:compressed-onboarding:v1:{index:04d}")
            ),
            cycle_id=cycle.cycle_id,
            next_scan_at=cycle.schedule_epoch,
            cursor=f"compressed-onboarding-{index:04d}",
            data_mode=DataMode.SYNTHETIC,
            declared_composition=DataComposition.SYNTHETIC_ONLY,
        )
        for index in range(1, ONBOARDING_CASE_COUNT + 1)
    )
    values = existing + onboarding
    if len(values) != 456 or len({item.case_id for item in values}) != 456:
        raise RuntimeError("compressed_unrun_pool_invalid")
    return tuple(sorted(values, key=lambda item: item.case_id))
