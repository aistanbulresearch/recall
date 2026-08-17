# ADR-0009: Repo-scoped Codex collaboration system

- Status: accepted; structural verification passes; runtime profile discovery is `REPORT_DERIVED`, not runtime-verified; Recall-root runtime smoke pending
- Date: 2026-08-17
- Owners: aistanbulresearch
- Related tasks: RCL-011, RCL-106, RCL-211, RCL-301 through RCL-907
- Supersedes: ad hoc single-session delegation without versioned Recall agent profiles

## Context

Recall's development process requires independent evidence review, strict responsibility separation, and owner-controlled external actions. `AGENTS.md` described the workflow, but the repository had no versioned Codex coordinator skill, custom subagent profiles, concurrency limit, or Master Judge contract.

## Decision drivers

- Keep the owner-facing coordinator responsive.
- Parallelize independent discovery without duplicating work.
- Prevent overlapping mutable ownership and silent scope expansion.
- Make independent review event-driven and evidence-backed.
- Preserve owner authority over GitHub, cloud, billing, destructive, and publication actions.
- Separate internal Master Judge review from the uncontrolled external GitHub auditor.

## Options considered

1. One general agent: rejected because authority, ownership, and review independence are ambiguous.
2. Permanently reserve one judge thread: rejected because it consumes the four-thread budget while idle.
3. Coordinator skill plus event-driven custom agents: accepted.

## Decision

Version `$recall-collaboration` under `.agents/skills/` and four custom profiles under `.codex/agents/`. Limit spawned concurrency to three so the primary coordinator remains available. Use read-only Scout and Master Judge profiles, scoped Worker profiles with exclusive file ownership, and a separate judge rubric.

Master Judge runs after design, after implementation/tests, after each pair of completed writing assignments in a long task, on disagreement, on high-risk boundary changes, and before protected repository or phase actions. The external GitHub auditor reviews stable owner-published heads on the cadence in `docs/project/COLLABORATION_SYSTEM.md`.

## Consequences

- Agent delegation becomes a versioned repository contract rather than session convention.
- Parallel writes require explicit disjoint ownership.
- A judge result is review evidence, not owner approval.
- Read-only TOML defaults require a functional permission-denial smoke because parent permissions may be reapplied.
- Current-session structural checks do not prove fresh-session discovery or runtime permission enforcement.
- A nested session from another repository cannot prove Worker write behavior because parent permissions correctly override the profile default.
- The newly exposed GitHub credential remains an open security risk. The owner explicitly deferred rotation and authorized only the exact collaboration-infrastructure commit/push on 2026-08-17; this exception is not remediation or standing authorization.

## Failure modes

- Duplicate investigation or overlapping file ownership.
- Child agents bypass the coordinator and exhaust the thread budget.
- A read-only profile receives broader parent permissions.
- Agent summaries are mistaken for independently inspected evidence.
- External auditor is asked to review an unchanged or unstable remote head.
- Judge findings are self-repaired by the same judge or treated as owner approval.

## Verification and evidence

- Skill initializer output and repository diff.
- Skill frontmatter and `openai.yaml` validation.
- Python `tomllib` assertions for config and four profiles.
- Parsed smoke-report classifications plus ADR, status, and handoff runtime-boundary assertions.
- Codex feature discovery plus fresh-session role/permission smoke.
- Independent design and post-implementation review.
- Work and error ledger entries without secret values.

## Rollback or supersession

Remove the repo-scoped skill, profiles, and config only through a new owner-approved ADR. Any replacement must preserve exclusive write ownership, bounded concurrency, independent read-only review, evidence classification, external-auditor separation, and owner-only protected actions.
