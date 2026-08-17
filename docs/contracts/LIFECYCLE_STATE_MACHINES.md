# Recall Lifecycle State Machines

- Status: corrected design baseline; implementation not started
- Date: 2026-08-17
- Related tasks: RCL-203, RCL-209, RCL-304, RCL-309
- Correction authority: ADR-0008

## Separation rule

`WatchCase`, `ScanRun`, and `ReviewTask` are separate authoritative objects. A long-lived watch case never implies a long-running model process. A review task never becomes scan state.

Privacy quarantine occurs inside the laboratory before a cloud `ScanRun` exists. A cloud run can be created only from a valid accepted `PrivacyReceipt`. This removes the misleading earlier sequence in which one cloud run could be both `RECEIVED` and `QUARANTINED`.

## WatchCase lifecycle

| From | Event | Guard | To | Deterministic action | Forbidden |
|---|---|---|---|---|---|
| none | `watch_case_create` | Accepted privacy receipt, valid mode, no duplicate case key | `ACTIVE` | Persist version 1 and schedule `next_scan_at` | Agent-created case |
| `ACTIVE` | `pause` | Authorized operator | `PAUSED` | Cancel future due marker | Scheduling a new run |
| `PAUSED` | `resume` | Authorized operator, no open terminal closure | `ACTIVE` | Recalculate due time from policy | Backdating silent scans |
| `ACTIVE` | `scan_no_action_committed` | Valid `NO_ACTION` without `duplicate_suppressed`; complete verified snapshot | `ACTIVE` | Advance cursors and last verified snapshot exactly to decision inputs; clear resolved pending hashes/attention; schedule next scan | Advancing to an unaudited snapshot |
| `ACTIVE` | `scan_abstained` | Valid `ABSTAIN` PolicyDecision | `ACTIVE` | Preserve verified cursors/snapshot; retain pending observation hashes; set attention marker; schedule bounded retry | Marking pending evidence as seen or clean |
| `ACTIVE` | `scan_halted` | Technical `HALTED` receipt | `ATTENTION_REQUIRED` | Preserve verified cursors/snapshot and pending hashes; set operator-required attention; clear `next_scan_at` | Automatic retry without an explicit recovery rule |
| `ACTIVE` | `review_task_created` | One committed task for current verified decision | `AWAITING_HUMAN` | Advance exactly to the audited snapshot, clear its pending hashes, and link task ID by CAS | Agent request as guard or advancement beyond audited inputs |
| `ACTIVE` | `duplicate_suppressed` | Existing open task matches exact case, decision, and verified-delta hash | `AWAITING_HUMAN` | Link existing task; do not advance beyond its already verified snapshot | Consuming a newer unaudited observation |
| `AWAITING_HUMAN` | `review_resolved_continue` | Valid `HumanDecisionReceipt` | `ACTIVE` | Clear open task and set next scan | Model-generated human action |
| `AWAITING_HUMAN` | `review_resolved_close` | Valid `HumanDecisionReceipt` | `CLOSED` | Clear schedule and retain audit history | Deleting history |
| `ATTENTION_REQUIRED` | `recover` | Authorized operator or preregistered deterministic recovery receipt; prerequisite restored | `ACTIVE` | Preserve pending hashes, calculate retry due time, clear operator-required flag only | Clearing evidence backlog |
| `ATTENTION_REQUIRED` | `close` | Authorized operator | `CLOSED` | Clear schedule and retain attention/failure history | Silent close by agent |
| `PAUSED` | `close` | Authorized operator | `CLOSED` | Clear schedule | Reopen without a new explicit case version |
| `ACTIVE` | `close` | Authorized operator and no open task | `CLOSED` | Clear schedule | Silent close by agent |

`CLOSED` is terminal. `AWAITING_HUMAN`, `ATTENTION_REQUIRED`, `PAUSED`, and `CLOSED` cannot be scheduled. One case has at most one open review task.

### Cursor and backlog invariants

1. `source_cursors`, `last_verified_snapshot_id`, and `last_verified_scan` advance only after a valid PolicyDecision of `NO_ACTION` without duplicate suppression or `REVIEW_REQUIRED` over the exact snapshot.
2. `ABSTAIN` and `HALTED` never advance verified cursors or snapshots. Their unverified observation hashes remain in `pending_observation_hashes`.
3. `duplicate_suppressed` never advances beyond the snapshot already referenced by the existing task and decision.
4. Restoring a failed source or prerequisite must expose the same pending observation hash to the next eligible run.
5. Empty pending hashes mean no recorded backlog only when the last transition explicitly cleared them after verified completion; missing is invalid.

## ScanRun lifecycle

Policy outcomes and technical execution states are different. `NO_ACTION`, `ABSTAIN`, and `REVIEW_REQUIRED` can be emitted only by Policy Gate. `HALTED` is an operational terminal used only when integrity or availability prevents a trustworthy policy evaluation. It is not a semantic outcome and cannot create a review task.

| From | Event or guard | To | Required artifact or action |
|---|---|---|---|
| none | Valid accepted `PrivacyReceipt`, active due case, unique idempotency key | `CREATED` | Persist run and frozen budget snapshot |
| `CREATED` | Outbox publish committed | `QUEUED` | Publish run request once |
| `QUEUED` | Lease acquired by expected version | `ROUTING` | Lease owner, epoch, and expiry recorded |
| `ROUTING` | Valid route and Registry resolution | `WATCHING` | `RoutingPlan` plus `RegistryResolutionReceipt` |
| `WATCHING` | Valid `CandidateDeltaReceipt: ABSENT` from complete snapshots | `POLICY_EVALUATION` | Candidate receipt and snapshot completeness, not a terminal result |
| `WATCHING` | Valid `CandidateDeltaReceipt: PRESENT` | `ASSESSING` | Current snapshot plus deterministic candidate receipt; Assessor cannot suppress route |
| `WATCHING` | Valid `CandidateDeltaReceipt: UNKNOWN` | `POLICY_EVALUATION` | Candidate receipt projects fail-closed policy facts; no Assessor invocation |
| `ASSESSING` | Valid assessment proposal | `AUDITING` | `EvidenceDelta` and `AssessmentReceipt` |
| `AUDITING` | Audit completed or failed with typed facts | `POLICY_EVALUATION` | `CitationAuditReceipt` including completeness |
| Any nonterminal state | Recoverable failure within budget | same logical state, next attempt | `FailureReceipt`, incremented attempt, renewed lease |
| Any nonterminal state | Prerequisite failure expressible as policy facts | `POLICY_EVALUATION` | Typed failure and complete policy input fact projection |
| `POLICY_EVALUATION` | Valid `PolicyDecision: NO_ACTION` without duplicate suppression | `NO_ACTION` | Decision appended; verified WatchCase cursor action committed; schedule next eligible scan |
| `POLICY_EVALUATION` | Valid `PolicyDecision: NO_ACTION` with `duplicate_suppressed` | `NO_ACTION` | Return existing task reference; no new task and no cursor advance beyond existing verified snapshot |
| `POLICY_EVALUATION` | Valid `PolicyDecision: ABSTAIN` | `ABSTAIN` | Decision and operations receipt appended; preserve cursors and pending observations; set attention; no task |
| `POLICY_EVALUATION` | Valid `PolicyDecision: REVIEW_REQUIRED` | `REVIEW_REQUIRED` | Decision appended; task created through transactional outbox |
| Any nonterminal state | Ledger integrity, Policy Gate availability, or unrecoverable Controller failure prevents trustworthy evaluation | `HALTED` | Technical failure receipt only; preserve cursors/pending observations; WatchCase enters attention-required behavior |

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

`privacy_not_accepted`, `contract_unknown_field`, `contract_required_field_missing`, `artifact_integrity_failed`, `producer_not_authorized`, `data_mode_conflict`, `registry_unavailable`, `registry_revision_rejected`, `route_invalid`, `tool_denied`, `source_unavailable`, `source_schema_drift`, `candidate_delta_unknown`, `agent_schema_invalid`, `citation_mismatch`, `counter_evidence_incomplete`, `audit_incomplete`, `memory_rejected`, `duplicate_suppressed`, `lease_expired`, `stale_write_rejected`, `loop_detected`, `budget_exhausted`, `policy_unavailable`, `ledger_integrity_failed`, and `controller_failed`.

`memory_rejected` is an operational receipt code only. It does not project a memory-specific PolicyDecision fact or reason. Policy reasons are defined solely in `docs/policy/DETERMINISTIC_POLICY_SPEC.md`.

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
11. Prove `ABSTAIN`, `HALTED`, and `duplicate_suppressed` do not advance beyond unaudited evidence.
12. Run outage, `ABSTAIN`, restore, and retry; prove the previously pending observation hash is observed again.
13. Prove a deterministic candidate cannot reach `NO_ACTION` because of an Assessor proposal.
