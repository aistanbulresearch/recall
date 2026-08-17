# Recall Deterministic Policy Specification

- Status: corrected design baseline; implementation not started
- Policy version: 1.0.1
- Date: 2026-08-17
- Related tasks: RCL-204, RCL-306, RCL-701 through RCL-704
- Correction authority: ADR-0008

## Authority

Policy Gate is a pure deterministic function over a validated `PolicyDecision.input_facts` object and referenced artifact hashes. It does not call a model, tool, source, memory service, notification service, or web UI. Free-form agent text is not an input.

For the same policy version, normalized facts, and input hashes, the outcome and ordered reason codes must be byte-identical.

Memory content, memory acceptance, memory rejection, and memory conflict are not policy inputs. Rejected or contradictory memory is ignored and receipted before authoritative artifacts are projected into policy facts.

## Fact types and deterministic producers

Policy facts never use a Boolean where missing or not-run must remain distinguishable:

| Type | Closed values | Meaning |
|---|---|---|
| `FactState` | `PASS`, `FAIL`, `NOT_EVALUATED` | Required check passed, ran and failed, or did not produce an authoritative result |
| `PresenceState` | `PRESENT`, `ABSENT`, `UNKNOWN` | Condition is proven present, proven absent, or cannot be determined from complete authoritative artifacts |

The deterministic Evidence Normalizer produces `CandidateDeltaReceipt`. `candidate_delta_state = PRESENT` only when all of these are true:

1. previous and current snapshots resolve and pass integrity validation;
2. the normalized allele exactly matches the `WatchCase` target;
3. the observation is inside the declared source and evidence scope;
4. the current snapshot is complete for that route;
5. at least one current observation hash is absent from the last verified snapshot.

Otherwise the receipt records `ABSENT` only when completeness is proven, or `UNKNOWN` when the determination cannot be made. Assessor prose and `EvidenceDelta.materiality_proposal` cannot alter this receipt or route a deterministic candidate to `NO_ACTION`.

## Outcomes

| Outcome | Meaning | Side effect eligibility |
|---|---|---|
| `NO_ACTION` | The scan has no eligible audited change requiring a simulated review task | Controller schedules the next scan; no task |
| `ABSTAIN` | A semantic decision is unsafe because one or more required facts are failed, missing, invalid, or conflicted | Operations receipt; no task |
| `REVIEW_REQUIRED` | A material change is complete, independently audited, conflict-free, and eligible for one simulated human task | Controller transactional outbox may create one task |

`HALTED` is not a Policy Gate outcome. It is a Controller lifecycle state used when Policy Gate or authoritative integrity is unavailable.

## Evaluation precedence

1. Validate the policy schema, policy version, producer authorization, referenced hashes, `DataModeReceipt`, and fact enums before evaluation. Failure that prevents trustworthy policy execution produces technical `HALTED`; Controller does not fabricate a PolicyDecision.
2. Determine fact applicability from the validated route. Base facts, candidate state, unresolved-conflict state, and execution-failure state are always applicable. Assessment, audit, material-claim, and counter-evidence facts are applicable only when `candidate_delta_state = PRESENT`. Existing-task state is applicable only to an otherwise review-eligible candidate.
3. Project every applicable failed, not-evaluated, present-failure, or unknown fact to its stable reason code. There is no reporting short-circuit. Sort the complete reason set lexically.
4. If the reason set is non-empty, emit `ABSTAIN`.
5. Otherwise, if `candidate_delta_state = ABSENT`, emit `NO_ACTION` with `no_candidate_delta`.
6. Otherwise, if the candidate is review-eligible and `existing_open_task_state = PRESENT`, emit `NO_ACTION` with `duplicate_suppressed` and the existing task reference. Do not advance beyond that task's already verified snapshot.
7. Otherwise emit `REVIEW_REQUIRED` with `audited_candidate_delta`.

## Abstention predicates

`ABSTAIN` is mandatory if any applicable fact projects a reason. This includes:

- any base `FactState` is `FAIL` or `NOT_EVALUATED`;
- `candidate_delta_state = UNKNOWN`;
- a candidate is present and assessment, citation audit, material-claim verification, or counter-evidence coverage is `FAIL` or `NOT_EVALUATED`;
- `unresolved_conflict_state = PRESENT` or `UNKNOWN`;
- `budget_or_loop_failure_state = PRESENT` or `UNKNOWN`;
- an otherwise eligible review has `existing_open_task_state = UNKNOWN`.

No-candidate runs do not invoke Assessor or Citation Auditor. Their downstream facts are explicitly `NOT_EVALUATED` but not applicable. They still require all base facts, candidate determination, conflict state, and execution-failure state to be trustworthy.

Any `REJECTED` or mismatched material claim makes `all_material_claims_verified = FAIL`. Dropping that claim cannot rescue the current assessment. Continuing requires a new immutable assessment artifact and a complete new independent audit over its full material-claim and counter-evidence set.

## Representative truth table

`P`, `F`, and `N` mean `PASS`, `FAIL`, and `NOT_EVALUATED`. Presence values are written in full. `base` is explanatory shorthand for all eight base facts; it is not stored. Every listed reason set is complete and lexically ordered.

| Row | base | candidate | assessment | audit | claims | counter | conflict | budget/loop | open task | Outcome | Complete reason codes |
|---:|---|---|---|---|---|---|---|---|---|---|---|
| 1 | P | `ABSENT` | N | N | N | N | `ABSENT` | `ABSENT` | `UNKNOWN` | `NO_ACTION` | `no_candidate_delta` |
| 2 | P | `PRESENT` | P | P | P | P | `ABSENT` | `ABSENT` | `ABSENT` | `REVIEW_REQUIRED` | `audited_candidate_delta` |
| 3 | P | `PRESENT` | P | P | P | P | `ABSENT` | `ABSENT` | `PRESENT` | `NO_ACTION` | `duplicate_suppressed` |
| 4 | privacy F; route N; all other base P | `UNKNOWN` | N | N | N | N | `UNKNOWN` | `ABSENT` | `UNKNOWN` | `ABSTAIN` | `candidate_delta_not_evaluated`, `privacy_not_accepted`, `route_not_evaluated`, `unresolved_conflict_not_evaluated` |
| 5 | P | `PRESENT` | F | N | N | N | `ABSENT` | `ABSENT` | `UNKNOWN` | `ABSTAIN` | `assessment_invalid`, `citation_audit_not_evaluated`, `counter_evidence_not_evaluated`, `material_claims_not_evaluated` |
| 6 | P | `PRESENT` | P | F | F | P | `ABSENT` | `ABSENT` | `UNKNOWN` | `ABSTAIN` | `citation_audit_incomplete`, `material_claim_unverified` |
| 7 | P | `PRESENT` | P | P | F | P | `ABSENT` | `ABSENT` | `UNKNOWN` | `ABSTAIN` | `material_claim_unverified` |
| 8 | P | `PRESENT` | P | P | P | F | `ABSENT` | `ABSENT` | `UNKNOWN` | `ABSTAIN` | `counter_evidence_incomplete` |
| 9 | P | `PRESENT` | P | P | P | P | `PRESENT` | `ABSENT` | `UNKNOWN` | `ABSTAIN` | `unresolved_evidence_conflict` |
| 10 | P | `UNKNOWN` | N | N | N | N | `ABSENT` | `PRESENT` | `UNKNOWN` | `ABSTAIN` | `candidate_delta_not_evaluated`, `execution_budget_failed` |
| 11 | P | `PRESENT` | P | P | P | P | `ABSENT` | `ABSENT` | `UNKNOWN` | `ABSTAIN` | `existing_open_task_not_evaluated` |

## Stable reason projection

Every applicable state projects independently. `_not_evaluated` is distinct from a check that ran and failed.

| Fact | `FAIL` or `PRESENT` reason | `NOT_EVALUATED` or `UNKNOWN` reason |
|---|---|---|
| `privacy_accepted` | `privacy_not_accepted` | `privacy_not_evaluated` |
| `registry_resolution_valid` | `registry_resolution_invalid` | `registry_resolution_not_evaluated` |
| `route_valid` | `route_invalid` | `route_not_evaluated` |
| `tool_authorization_complete` | `tool_authorization_incomplete` | `tool_authorization_not_evaluated` |
| `source_retrieval_complete` | `source_retrieval_incomplete` | `source_retrieval_not_evaluated` |
| `source_schema_valid` | `source_schema_invalid` | `source_schema_not_evaluated` |
| `data_mode_valid` | `data_mode_invalid` | `data_mode_not_evaluated` |
| `snapshot_integrity_valid` | `snapshot_integrity_invalid` | `snapshot_integrity_not_evaluated` |
| `candidate_delta_state` | not applicable | `candidate_delta_not_evaluated` for `UNKNOWN` |
| `assessment_valid` | `assessment_invalid` | `assessment_not_evaluated` |
| `citation_audit_complete` | `citation_audit_incomplete` | `citation_audit_not_evaluated` |
| `all_material_claims_verified` | `material_claim_unverified` | `material_claims_not_evaluated` |
| `counter_evidence_complete` | `counter_evidence_incomplete` | `counter_evidence_not_evaluated` |
| `unresolved_conflict_state` | `unresolved_evidence_conflict` for `PRESENT` | `unresolved_conflict_not_evaluated` for `UNKNOWN` |
| `budget_or_loop_failure_state` | `execution_budget_failed` for `PRESENT` | `execution_budget_not_evaluated` for `UNKNOWN` |
| `existing_open_task_state` | `duplicate_suppressed` is a successful `NO_ACTION` reason, not abstention | `existing_open_task_not_evaluated` for `UNKNOWN` on an otherwise eligible review |

## Task creation protocol

1. Policy Gate emits one signed `PolicyDecision` with `REVIEW_REQUIRED`.
2. Controller validates decision version, hashes, current run version, and absence of an existing deduplication key.
3. Controller commits the run transition, WatchCase link, task record, and notification outbox atomically.
4. Repeated delivery returns the existing task ID.
5. Notification failure retries the outbox only. It never re-evaluates policy or creates another task.

## Required tests

- Exhaust every semantically valid combination of closed fact states and snapshot the ordered result.
- Generate invalid combinations and prove schema or projection rejection before policy.
- Run each representative row twice and compare byte-identical outputs after excluding trusted creation metadata.
- Mutate one prerequisite at a time and prove the corresponding reason code activates.
- Prove no-change runs cannot skip base completeness checks.
- Prove material-change runs cannot skip assessment, audit, citation, or counter-evidence checks.
- Prove a deterministic candidate plus an Assessor `not material` proposal cannot produce `NO_ACTION` and still invokes Auditor.
- Prove no deterministic candidate means Assessor and Auditor activation counts are zero.
- Prove one mismatched material claim among verified claims produces `material_claim_unverified`, `ABSTAIN`, and zero tasks.
- Prove an unrun required audit emits `citation_audit_not_evaluated`, not `citation_audit_incomplete`.
- Prove multiple simultaneous failures emit every applicable reason exactly once in lexical order.
- Prove memory content, memory receipts, and memory-conflict state are absent from the policy input type; memory enabled/disabled parity is byte-identical over authoritative inputs.
- Prove agents and web clients cannot sign or persist a `PolicyDecision`.
- Prove only one `ReviewTask` exists under repeated decision/outbox delivery.
- Make Policy Gate unavailable and prove Controller records `HALTED` without inventing an outcome.
