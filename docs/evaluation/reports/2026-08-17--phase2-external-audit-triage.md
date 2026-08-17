# Recall Phase 2 External Audit Triage

- Date: 2026-08-17
- Subject: PR #2 at `c4e2b02d7e596ee99879686b3f53b214809d4673`
- Audit mode: read-only GitHub and source verification
- Auditor verdict: `PASS WITH REQUIRED CHANGES`
- Owner-side disposition: accepted; merge and Phase 3 remain `NO-GO`
- Canonical correction decision: `docs/adr/ADR-0008-external-audit-corrections.md`

## Evidence boundary

The audited repository contains verified design only. Product code, executable contracts, deployment, replay execution, and safety validation have not started. This triage records accepted findings and required work; it is not evidence that a correction has been implemented.

On 2026-08-17 the owner-side review independently confirmed:

- NCBI GEO `GSE248438` reports `Public on Sep 27, 2024`, currently cites PMID `41957374`, and was last updated 2026-07-29;
- the qualifying Nature paper, PMID `39779848`, names `GSE248438` in its data-availability statement;
- two immediate downloads of the same `VCV002895953.1` printable page had equal lengths but unequal SHA-256 hashes, and their `ncbi_phid` lines differed.

> Resolution update, 2026-08-17: F-01 through F-06 pass the scoped normative consistency audit. F-07 and F-08 pass locally at frozen-source-package level under protocol 1.0.1 with ten exact repository captures, offline hash verification, mutated-byte and path-boundary rejection, corrected GEO chronology/linkage, and exact-row validation. Product execution, complete follow-up audit, push, and external auditor re-review remain pending.

## Required findings

| ID | Severity | Disposition | Gate | Required action |
|---|---|---|---|---|
| F-01 | P1 | Accepted | Blocks merge and Phase 3 | Deterministic Controller/normalizer owns candidate-delta detection; Assessor cannot select `NO_ACTION` |
| F-02 | P1 | Accepted | Blocks merge and Phase 3 | Remove memory from policy inputs; reject/ignore and receipt conflicts; require memory-on/off parity |
| F-03 | P1 | Accepted | Blocks merge and Phase 3 | Any rejected material claim blocks review; correct storyboard reason-code precommitment |
| F-04 | P1 | Accepted | Blocks merge and Phase 3 | Use evaluated-state facts; emit all applicable lexical reason codes; remove short-circuit ambiguity |
| F-05 | P1 | Accepted | Blocks merge and Phase 3 | Add run-level mode set and allowed composition rules for synthetic case plus captured replay |
| F-06 | P1 | Accepted | Blocks merge and Phase 3 | Define terminal WatchCase cursor, pending-observation, attention, retry, and scheduling actions |
| F-07 | P1 | Accepted | Blocks merge and RCL-205/RCL-503 | Replace dynamic-page response hashes with exact captured repository bytes and offline hash verification |
| F-08 | P1 | Accepted | Blocks merge and RCL-205/RCL-503/RCL-506 | Record GEO chronology/current linked PMID, paper-to-GEO linkage rule, anchor rationale, and as-captured row status |

## Scheduled findings

These findings are accepted and must be resolved before the named implementation surface begins:

| IDs | Required before | Planned resolution |
|---|---|---|
| F-09, F-10 | RCL-302, RCL-304, fault-run implementation | Align deterministic fault trigger, requester role, receipt producer, and strict-schema behavior |
| F-11, F-12 | RCL-302, RCL-307, RCL-503, RCL-505 | Add missing receipt/UI contracts and explicit replay-stage/as-of semantics |
| F-13, F-14 | RCL-302, RCL-306, RCL-606 | Define fallback resolution mode and one failure-to-fact-to-reason registry |
| F-15, F-16 | RCL-601 and demo rehearsal | Give Coordinator a visible bounded choice and preregister measured latency/fallback timing |
| F-17 | RCL-701 through RCL-707 | Expand guardrail proof matrix for halt, outbox, tamper, telemetry, and managed outages |
| F-18 | Final submission wording gate | Preserve the narrow incorporated-work rule, exact rule snapshot, and truthful response only if asked |

## Tracked completeness findings

F-19 through F-29 are accepted as documentation and contract debt. They cover status vocabulary, stale text, role-count wording, state-hash composition, nullability, simulated-task wording, Cursor integration pre-push confirmation, per-source retrieval times, `STALE` criteria, public privacy-demo limits, and PrivacyReceipt reuse. They do not authorize Phase 3 while F-01 through F-08 remain open.

## Preserved strengths

- deterministic Controller and sole Policy Gate authority;
- `HALTED` distinct from `ABSTAIN`;
- local privacy boundary before cloud intake;
- strict non-clinical contest boundary;
- fail-loud missing-data behavior;
- activation proof plus forbidden-downstream read-back;
- derived UI values and fixture-independent mutation tests;
- preregistered positive/control geometry and bounded claims;
- owner-only GitHub authorship and clean visible PR surface at audit time.

## Exit criteria

RCL-211 can complete only after:

1. F-01 through F-06 are synchronized across normative documents;
2. replay protocol 1.0.1 resolves F-07 and F-08 or RCL-205 is explicitly kept in progress outside the merge baseline;
3. local link, schema-example, contradiction, stale-marker, field-registry, secret-pattern, and offline replay audits pass;
4. follow-up review finds no material contradiction;
5. any push occurs only after owner confirmation that the recurring Cursor integration is disabled, followed by owner-only metadata and visible-surface read-back.
