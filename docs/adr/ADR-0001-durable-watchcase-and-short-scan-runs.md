# ADR-0001: Durable WatchCase with short bounded ScanRuns

- Status: accepted
- Date: 2026-08-15
- Owners: aistanbulresearch
- Related tasks: RCL-202, RCL-203, RCL-304, RCL-305, RCL-504
- Supersedes:

## Context

The Fleet category expects context to survive weeks of asynchronous operation. Pub/Sub and Eventarc trigger endpoints are synchronous and are not appropriate for one continuously running multi-week execution. A long model process would also make retries, cost, recovery, and audit boundaries ambiguous.

## Decision drivers

- explicit weeks-long institutional continuity;
- bounded execution and predictable cost;
- crash recovery and idempotency;
- replayable evidence and demo acceleration;
- no continuously running model session.

## Options considered

1. One long-lived agent execution. Rejected because trigger limits, crash recovery, and auditability are poor.
2. Firestore-backed `WatchCase` plus short event-driven `ScanRun` units. Accepted.
3. A demo-only time simulation without a durable parent object. Rejected because it would not prove the Fleet requirement.

## Decision

Model the multi-week process as a durable `WatchCase`. Scheduler or an approved event creates an idempotent `ScanRun`. Each run executes a short ADK graph and commits typed artifacts to Firestore. `ReviewTask` has a separate human lifecycle.

The demo may accelerate Week 0, Week 3, and Week 6, but every accelerated timestamp and source mode must be explicit.

## Consequences

- Continuity is carried by authoritative state rather than model process lifetime.
- Every scan can be retried, replayed, audited, and costed independently.
- State contracts and scheduler behavior become additional implementation work.
- The UI must distinguish parent case state, scan state, and review state.

## Failure modes

- duplicate event creates two runs;
- lease expires during agent execution;
- stale scan attempts to overwrite a newer snapshot;
- paused or closed case is scheduled;
- accelerated replay is presented as live elapsed time.

## Verification and evidence

- duplicate-delivery and compare-and-set tests;
- crash-resume fixture;
- stale-write rejection;
- paused/closed scheduling denial;
- visible Week 0, Week 3, and Week 6 run receipts with explicit data modes.

## Rollback or supersession

If managed triggers are unavailable, a Cloud Run Job or worker-pool scheduler may create the same `ScanRun` contract. The durable lifecycle and authority model remain unchanged.
