# ADR-0007: Policy outcomes and technical halt

- Status: accepted design correction
- Date: 2026-08-16
- Owners: aistanbulresearch
- Related tasks: RCL-203, RCL-204, RCL-304, RCL-306
- Supersedes: the `ScanRun` sequence in the 2026-08-15 target architecture baseline

## Context

The initial `ScanRun` sketch included `NO_CHANGE_FOUND` as a state and implied that privacy quarantine occurred after a cloud run was received. It also lacked a truthful state for the case where the deterministic Policy Gate itself is unavailable.

Those details conflicted with two accepted authority rules: privacy decides locally before cloud egress, and only Policy Gate emits semantic outcomes.

## Options considered

1. Let Controller emit `ABSTAIN` when Policy Gate is unavailable. Rejected because it fabricates an outcome outside the sole policy authority.
2. Treat `NO_CHANGE_FOUND` and quarantine as cloud terminal states. Rejected because no-change still requires policy completeness checks and rejected raw input must not enter the cloud workflow.
3. Create cloud runs only after accepted privacy receipts, route no-change through policy, and add a separate technical `HALTED` terminal. Accepted.

## Decision

- Privacy quarantine is local and prevents creation of a cloud `ScanRun`.
- `NO_CHANGE_FOUND` is an evidence fact/event, not a terminal state.
- Every trustworthy semantic terminal is one of `NO_ACTION`, `ABSTAIN`, or `REVIEW_REQUIRED`, emitted only by Policy Gate.
- `HALTED` is a technical terminal for failures that prevent trustworthy policy execution, including Policy Gate unavailability or ledger integrity failure.
- `HALTED` never creates a review task and is never presented as a clinical or semantic outcome.

## Consequences

- No-change runs still prove source and snapshot completeness before Policy Gate emits `NO_ACTION`.
- A missing Policy Gate fails loudly instead of being disguised as a safe policy decision.
- Operational dashboards and tests must distinguish technical halt from semantic abstention.
- The target architecture, lifecycle contract, demo lineage, and failure receipts must use this distinction.

## Failure modes

- UI collapses `HALTED` into `ABSTAIN`.
- Controller signs a fabricated PolicyDecision during policy outage.
- A quarantined payload creates a cloud run.
- No-change path skips base completeness checks.

## Verification

- Policy-outage fixture produces `HALTED` and zero `PolicyDecision` and `ReviewTask` records.
- Privacy-rejection fixture produces zero cloud intake and run records.
- No-change fixture contains a valid PolicyDecision with `NO_ACTION`.
- UI and derived-value tests render `HALTED` and `ABSTAIN` as distinct states.

## Rollback or supersession

Any replacement must preserve local privacy rejection, sole Policy Gate semantic authority, and an explicit fail-loud state when trusted policy execution is impossible.
