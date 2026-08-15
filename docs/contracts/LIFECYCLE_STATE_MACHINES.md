# Recall Lifecycle State Machines

- Status: frozen design baseline
- Date: 2026-08-16
- Related tasks: RCL-203, RCL-209, RCL-304, RCL-309

## Separation rule

`WatchCase`, `ScanRun`, and `ReviewTask` are separate authoritative objects. A long-lived watch case never implies a long-running model process. A review task never becomes scan state.

Privacy quarantine occurs inside the laboratory before a cloud `ScanRun` exists. A cloud run can be created only from a valid accepted `PrivacyReceipt`. This removes the misleading earlier sequence in which one cloud run could be both `RECEIVED` and `QUARANTINED`.

## WatchCase lifecycle

| From | Event | Guard | To | Deterministic action | Forbidden |
|---|---|---|---|---|---|
| none | `watch_case_create` | Accepted privacy receipt, valid mode, no duplicate case key | `ACTIVE` | Persist version 1 and schedule `next_scan_at` | Agent-created case |
| `ACTIVE` | `pause` | Authorized operator | `PAUSED` | Cancel future due marker | Scheduling a new run |
| `PAUSED` | `resume` | Authorized operator, no open terminal closure | `ACTIVE` | Recalculate due time from policy | Backdating silent scans |
| `ACTIVE` | `review_task_created` | One committed task for current decision | `AWAITING_HUMAN` | Link task ID by CAS | Agent request as guard |
| `AWAITING_HUMAN` | `review_resolved_continue` | Valid `HumanDecisionReceipt` | `ACTIVE` | Clear open task and set next scan | Model-generated human action |
| `AWAITING_HUMAN` | `review_resolved_close` | Valid `HumanDecisionReceipt` | `CLOSED` | Clear schedule and retain audit history | Deleting history |
| `PAUSED` | `close` | Authorized operator | `CLOSED` | Clear schedule | Reopen without a new explicit case version |
| `ACTIVE` | `close` | Authorized operator and no open task | `CLOSED` | Clear schedule | Silent close by agent |

`CLOSED` is terminal. `AWAITING_HUMAN` cannot be scheduled. One case has at most one open review task.

## ScanRun lifecycle

Policy outcomes and technical execution states are different. `NO_ACTION`, `ABSTAIN`, and `REVIEW_REQUIRED` can be emitted only by Policy Gate. `HALTED` is an operational terminal used only when integrity or availability prevents a trustworthy policy evaluation. It is not a semantic outcome and cannot create a review task.

| From | Event or guard | To | Required artifact or action |
|---|---|---|---|
| none | Valid accepted `PrivacyReceipt`, active due case, unique idempotency key | `CREATED` | Persist run and frozen budget snapshot |
| `CREATED` | Outbox publish committed | `QUEUED` | Publish run request once |
| `QUEUED` | Lease acquired by expected version | `ROUTING` | Lease owner, epoch, and expiry recorded |
| `ROUTING` | Valid route and Registry resolution | `WATCHING` | `RoutingPlan` plus `RegistryResolutionReceipt` |
| `WATCHING` | Complete no-material-change snapshot | `POLICY_EVALUATION` | Snapshot completeness and no-change fact, not a terminal result |
| `WATCHING` | Complete candidate change | `ASSESSING` | Current snapshot and candidate delta inputs |
| `ASSESSING` | Valid assessment proposal | `AUDITING` | `EvidenceDelta` and `AssessmentReceipt` |
| `AUDITING` | Audit completed or failed with typed facts | `POLICY_EVALUATION` | `CitationAuditReceipt` including completeness |
| Any nonterminal state | Recoverable failure within budget | same logical state, next attempt | `FailureReceipt`, incremented attempt, renewed lease |
| Any nonterminal state | Prerequisite failure expressible as policy facts | `POLICY_EVALUATION` | Typed failure and complete policy input fact projection |
| `POLICY_EVALUATION` | Valid `PolicyDecision: NO_ACTION` | `NO_ACTION` | Decision appended; schedule next eligible scan |
| `POLICY_EVALUATION` | Valid `PolicyDecision: ABSTAIN` | `ABSTAIN` | Decision and operations receipt appended; no task |
| `POLICY_EVALUATION` | Valid `PolicyDecision: REVIEW_REQUIRED` | `REVIEW_REQUIRED` | Decision appended; task created through transactional outbox |
| Any nonterminal state | Ledger integrity, Policy Gate availability, or unrecoverable Controller failure prevents trustworthy evaluation | `HALTED` | Technical failure receipt only; operator intervention required |

Terminal states are `NO_ACTION`, `ABSTAIN`, `REVIEW_REQUIRED`, and `HALTED`. `NO_CHANGE_FOUND` is an event/fact, not a state. This preserves the invariant that Policy Gate owns every semantic terminal outcome.

## ReviewTask lifecycle

| From | Event | Guard | To | Action |
|---|---|---|---|---|
| none | Transactional outbox consumes one eligible decision | Unique deduplication key and `simulation=true` in contest build | `OPEN` | Create exactly one simulated task |
| `OPEN` | Reviewer opens task | Authenticated reviewer | `ACKNOWLEDGED` | Append human interaction event |
| `OPEN` | Reviewer dismisses | Authenticated reviewer and reason code | `DISMISSED` | Append `HumanDecisionReceipt` |
| `ACKNOWLEDGED` | Reviewer dismisses | Authenticated reviewer and reason code | `DISMISSED` | Append receipt |
| `ACKNOWLEDGED` | Reviewer escalates | Authenticated reviewer and reason code | `ESCALATED` | Append receipt; no automated patient/report action |
| `DISMISSED` | Workflow closes | Receipt committed | `CLOSED` | Update WatchCase according to human action |
| `ESCALATED` | Workflow closes | Receipt committed | `CLOSED` | Update WatchCase according to human action |

The contest build has no production queue, patient contact, report edit, or clinical action integration.

## Concurrency and idempotency

| Mechanism | Frozen rule |
|---|---|
| Case scheduling key | Hash of tenant, case, monitoring-policy version, and due window |
| Scan idempotency key | Hash of watch-case ID, source cursor set, schedule epoch, and data mode |
| Review deduplication key | Hash of case ID, policy decision ID, and verified delta hash |
| Lease | Owner, epoch, acquired time, expiry, and heartbeat version are stored authoritatively |
| Compare-and-set | Every transition supplies expected object version and lease epoch |
| Inbox | Duplicate event returns the existing run ID and does not re-run policy |
| Outbox | State change and outbound event are committed atomically; delivery is at-least-once and consumer is idempotent |
| Artifact write | Artifact ID and content hash are immutable; same ID with different content is rejected |

## Frozen execution budgets

Budgets are configuration values copied into each `ScanRun`; they are never inferred from model output or silently expanded.

| Budget | Maximum | Exhaustion behavior |
|---|---:|---|
| Delegation depth | 1 | Policy-bound abstention path |
| Specialist agent invocations | 3 | Policy-bound abstention path |
| Normal model calls per role | 1 | One schema repair may follow |
| Schema repair attempts per agent | 1 | Invalid artifact receipt |
| Transient agent runtime retries | 1 | Runtime failure receipt |
| Connector retries per source | 3 | Source-incomplete receipt |
| Repeated identical state hash | 1 repeat after first observation | `loop_detected` receipt and no further invocation |
| Total scan wall time | Less than 10 minutes | Policy-bound abstention if reachable, otherwise `HALTED` |

Exact step deadlines and token ceilings are selected after Phase 1 capability and latency measurements, versioned in run configuration, and preregistered before evaluation.

## Stable failure codes

`privacy_not_accepted`, `contract_unknown_field`, `contract_required_field_missing`, `artifact_integrity_failed`, `producer_not_authorized`, `data_mode_conflict`, `registry_unavailable`, `registry_revision_rejected`, `route_invalid`, `tool_denied`, `source_unavailable`, `source_schema_drift`, `agent_schema_invalid`, `citation_mismatch`, `counter_evidence_incomplete`, `audit_incomplete`, `memory_rejected`, `memory_authority_conflict`, `duplicate_suppressed`, `lease_expired`, `stale_write_rejected`, `loop_detected`, `budget_exhausted`, `policy_unavailable`, `ledger_integrity_failed`, and `controller_failed`.

## Invariant tests required before implementation gate

1. Enumerate every state/event pair and reject all unlisted transitions.
2. Replay an identical event and prove state version, run count, task count, and outbox count do not increase incorrectly.
3. Crash after state commit but before event delivery, resume, and prove one logical transition.
4. Reject an expired lease and stale expected version without modifying state.
5. Prove paused, awaiting-human, and closed cases do not schedule scans.
6. Prove no-change evidence still passes through Policy Gate before `NO_ACTION`.
7. Make Policy Gate unavailable and prove `HALTED`, not forged `ABSTAIN`.
8. Prove only `REVIEW_REQUIRED` can feed task creation and that one decision creates at most one task.
9. Prove an agent identity cannot perform any lifecycle transition.
10. Prove every terminal run contains either one valid `PolicyDecision` or a technical `FailureReceipt` for `HALTED`, never both semantic authorities.
