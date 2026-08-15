# Recall Deterministic Policy Specification

- Status: frozen design baseline
- Policy version: 1.0.0
- Date: 2026-08-16
- Related tasks: RCL-204, RCL-306, RCL-701 through RCL-704

## Authority

Policy Gate is a pure deterministic function over a validated `PolicyDecision.input_facts` object and referenced artifact hashes. It does not call a model, tool, source, memory service, notification service, or web UI. Free-form agent text is not an input.

For the same policy version, normalized facts, and input hashes, the outcome and ordered reason codes must be byte-identical.

## Outcomes

| Outcome | Meaning | Side effect eligibility |
|---|---|---|
| `NO_ACTION` | The scan has no eligible audited change requiring a simulated review task | Controller schedules the next scan; no task |
| `ABSTAIN` | A semantic decision is unsafe because one or more required facts are failed, missing, invalid, or conflicted | Operations receipt; no task |
| `REVIEW_REQUIRED` | A material change is complete, independently audited, conflict-free, and eligible for one simulated human task | Controller transactional outbox may create one task |

`HALTED` is not a Policy Gate outcome. It is a Controller lifecycle state used when Policy Gate or authoritative integrity is unavailable.

## Evaluation precedence

1. Validate the policy schema, policy version, producer authorization, referenced hashes, and data mode before evaluation. Failure here prevents policy execution and produces technical `HALTED` where integrity is not trustworthy.
2. If any abstention predicate is true, emit `ABSTAIN` with every applicable stable reason code in lexical order.
3. Otherwise, if `material_delta_present` is true and no open duplicate task exists, emit `REVIEW_REQUIRED`.
4. Otherwise emit `NO_ACTION`. If an eligible decision already has an open task, include `duplicate_suppressed` and return that task reference without creating another.

## Abstention predicates

`ABSTAIN` is mandatory if any of these facts applies:

- privacy not accepted;
- Registry resolution or route invalid;
- required tool authorization incomplete or denied for the executed route;
- source retrieval incomplete or source schema invalid;
- data mode or snapshot integrity invalid;
- a material delta exists but assessment is invalid;
- a material delta exists but citation audit is incomplete;
- a material delta exists but not all material claims verify;
- a material delta exists but counter-evidence coverage is incomplete;
- unresolved evidence conflict is present;
- loop or budget failure occurred;
- memory attempted to supply an authoritative fact or conflicted with ledger state.

No-change runs do not require an assessment or citation audit. They do require valid privacy, route, source retrieval, data mode, and snapshot integrity facts.

## Representative truth table

`T` is true, `F` is false, and `*` is irrelevant after a higher-precedence predicate. `base_ok` means privacy, Registry, route, tool authorization, source retrieval, source schema, data mode, and snapshot integrity are all valid.

| Row | base_ok | delta | assessment | audit complete | claims verified | counter-evidence complete | conflict | budget/loop failure | memory conflict | open task | Outcome | Primary reason |
|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | T | F | * | * | * | * | F | F | F | F | `NO_ACTION` | `no_material_delta` |
| 2 | T | T | T | T | T | T | F | F | F | F | `REVIEW_REQUIRED` | `audited_material_delta` |
| 3 | T | T | T | T | T | T | F | F | F | T | `NO_ACTION` | `duplicate_suppressed` |
| 4 | F | * | * | * | * | * | * | * | * | * | `ABSTAIN` | Exact failed base prerequisites |
| 5 | T | T | F | * | * | * | * | F | F | F | `ABSTAIN` | `assessment_invalid` |
| 6 | T | T | T | F | * | * | * | F | F | F | `ABSTAIN` | `citation_audit_incomplete` |
| 7 | T | T | T | T | F | * | * | F | F | F | `ABSTAIN` | `material_claim_unverified` |
| 8 | T | T | T | T | T | F | * | F | F | F | `ABSTAIN` | `counter_evidence_incomplete` |
| 9 | T | T | T | T | T | T | T | F | F | F | `ABSTAIN` | `unresolved_evidence_conflict` |
| 10 | T | * | * | * | * | * | * | T | F | F | `ABSTAIN` | `execution_budget_failed` |
| 11 | T | * | * | * | * | * | * | F | T | F | `ABSTAIN` | `memory_authority_conflict` |
| 12 | T | F | F | F | F | F | F | F | F | F | `NO_ACTION` | Assessment fields are irrelevant when no delta exists |

## Base prerequisite projection

The policy implementation must report each failed base prerequisite separately. `base_ok` is explanatory shorthand only and is not stored as an input field. This prevents one aggregate green flag from hiding a dead mechanism.

| Failed fact | Reason code |
|---|---|
| `privacy_accepted = false` | `privacy_not_accepted` |
| `registry_resolution_valid = false` | `registry_resolution_invalid` |
| `route_valid = false` | `route_invalid` |
| `tool_authorization_complete = false` | `tool_authorization_incomplete` |
| `source_retrieval_complete = false` | `source_retrieval_incomplete` |
| `source_schema_valid = false` | `source_schema_invalid` |
| `data_mode_valid = false` | `data_mode_invalid` |
| `snapshot_integrity_valid = false` | `snapshot_integrity_invalid` |

## Task creation protocol

1. Policy Gate emits one signed `PolicyDecision` with `REVIEW_REQUIRED`.
2. Controller validates decision version, hashes, current run version, and absence of an existing deduplication key.
3. Controller commits the run transition, WatchCase link, task record, and notification outbox atomically.
4. Repeated delivery returns the existing task ID.
5. Notification failure retries the outbox only. It never re-evaluates policy or creates another task.

## Required tests

- Exhaust every boolean combination of policy inputs that is semantically valid and snapshot the ordered result.
- Generate invalid combinations and prove schema or projection rejection before policy.
- Run each representative row twice and compare byte-identical outputs after excluding trusted creation metadata.
- Mutate one prerequisite at a time and prove the corresponding reason code activates.
- Prove no-change runs cannot skip base completeness checks.
- Prove material-change runs cannot skip assessment, audit, citation, or counter-evidence checks.
- Prove memory content is absent from the policy input type.
- Prove agents and web clients cannot sign or persist a `PolicyDecision`.
- Prove only one `ReviewTask` exists under repeated decision/outbox delivery.
- Make Policy Gate unavailable and prove Controller records `HALTED` without inventing an outcome.
