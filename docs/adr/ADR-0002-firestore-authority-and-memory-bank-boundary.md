# ADR-0002: Firestore authority and non-authoritative Memory Bank

- Status: accepted
- Date: 2026-08-15
- Owners: aistanbulresearch
- Related tasks: RCL-104, RCL-202, RCL-203, RCL-303, RCL-609, RCL-706
- Supersedes:

## Context

Fleet continuity benefits from managed long-term memory, but clinical evidence, workflow state, and policy cannot depend on mutable model-generated memory. Memory poisoning or stale retrieval could otherwise influence future scans without an auditable evidence path.

## Decision drivers

- one authoritative source of workflow truth;
- useful cross-scan operational context;
- poisoning, tenant, region, and retention controls;
- deterministic replay;
- explicit degraded behavior when Memory Bank is unavailable.

## Options considered

1. Use Memory Bank as workflow and evidence storage. Rejected because it violates deterministic authority.
2. Avoid managed memory entirely. Safe fallback, but weakens Fleet continuity proof.
3. Keep Firestore authoritative and admit only bounded operational memory through a deterministic gate. Accepted.

## Decision

Firestore is authoritative for cases, scans, snapshots, deltas, decisions, tasks, and failures. ADK Sessions hold current-run interaction state only. Memory Bank holds admitted non-clinical operational context only.

Every memory write passes `MemoryAdmissionGate`; every retrieval creates a provenance receipt. Memory cannot satisfy evidence, citation, state-transition, or policy prerequisites.

## Consequences

- Recall can demonstrate managed multi-week memory without assigning it clinical authority.
- Memory schemas, TTL, scopes, and contradiction tests must be implemented.
- Some agent efficiency may be lost because authoritative facts must be re-read from Firestore.

## Failure modes

- false or malicious memory admitted;
- memory crosses tenant or region scope;
- stale memory contradicts current ledger facts;
- agent treats recalled prose as evidence;
- Memory Bank outage silently changes behavior.

## Verification and evidence

- poisoning and contradiction fixtures;
- tenant/agent/region isolation tests;
- TTL and deletion tests;
- retrieval receipt linked to the resulting proposal;
- identical policy outcome with Memory Bank disabled when authoritative inputs are unchanged.

## Rollback or supersession

If Memory Bank access or reliability fails Phase 1 gates, disable memory use and continue with Firestore plus current-run Sessions. Record the loss of Fleet-memory proof; do not change the authority model.
