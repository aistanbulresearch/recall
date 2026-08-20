# ADR-0008: External audit corrections before implementation

- Status: accepted decisions; latest external follow-up at `c8be19476c24672fbf65d4dbf767fa8144360d22`: `FAIL`; transcript-integrity and Graphify-governance remediation are in progress, while merge and Phase 3 remain `NO-GO`
- Date: 2026-08-17
- Owners: aistanbulresearch
- Related tasks: RCL-202 through RCL-205, RCL-211, RCL-302 through RCL-309, RCL-503, RCL-506
- Supersedes: conflicting details in the Phase 2 baseline identified by the PR #2 external audit

## Current external-gate state

```text
current_external_audit_head=c8be19476c24672fbf65d4dbf767fa8144360d22
current_external_audit_verdict=FAIL
audited_predecessor_head=877c78d06d9b78f3071d17c81232fbc4302f857e
rcl_211=IN_PROGRESS
merge_gate=NO_GO
phase_3_gate=NO_GO
external_re_review=REQUIRED
historical_external_pass_head=195422e4d762d68d38e2b7f531cc5b1cd059cdb7
```

## Context

The read-only audit of PR #2 found no P0 invariant violation and confirmed the main authority architecture. It also found six P1 contract gaps that could let implementation silently violate that architecture, plus two replay-package defects that make the frozen source package non-reproducible as written.

Independent read-only verification on 2026-08-17 confirmed both replay defects:

- two immediate downloads of the same ClinVar printable version had equal byte lengths but different SHA-256 values because the `ncbi_phid` metadata changed;
- NCBI GEO `GSE248438` is public from 2024-09-27 and currently links PMID `41957374`, while the qualifying 2025 Nature paper is PMID `39779848`. The Nature paper itself names `GSE248438` in its data-availability statement.

No product code exists, so these corrections can be made before implementation without migration risk.

## Decision

### 1. Deterministic candidate detection owns routing to assessment

The Controller/normalizer, never an LLM, derives whether a candidate delta exists. The derivation requires an exact normalized allele match, an allowed evidence scope, a complete source snapshot, and at least one observation hash absent from the last verified snapshot.

An Assessor may propose interpretation and uncertainty for a deterministic candidate. It cannot suppress the candidate path or cause `NO_ACTION`. A no-candidate run never invokes the Assessor or Auditor.

### 2. Rejected memory is ignored and receipted

Memory Bank remains outside policy inputs. Poisoned, stale, cross-scope, or conflicting memory is rejected or ignored with a typed receipt. Policy output and task count must be byte-identical with Memory Bank enabled and disabled for the same authoritative artifacts.

If a required fact has no authoritative support after memory is removed, the fact is `NOT_EVALUATED` or failed according to its own authoritative prerequisite. No memory-specific fact may independently change the policy outcome.

### 3. Any rejected material claim blocks review

A fabricated, mismatched, unsupported, or independently unverifiable material claim makes `all_material_claims_verified = FAIL`. The Policy Gate emits `ABSTAIN`, includes the stable reason code, and creates zero tasks. Removing the bad claim and continuing is permitted only in a new assessment artifact whose remaining material claims and counter-evidence are independently re-audited.

### 4. Policy facts are evaluated-state values and all applicable reasons are emitted

Policy prerequisites use closed evaluated states such as `PASS`, `FAIL`, and `NOT_EVALUATED`; presence facts use closed states such as `PRESENT`, `ABSENT`, and `UNKNOWN`. Missing and not-run are not represented as `false`.

Policy evaluation has no semantic short-circuit for reporting. It emits every applicable stable reason code in lexical order. `NOT_EVALUATED` produces an explicit `*_not_evaluated` code and fails closed when the fact is required for the current route.

### 5. Artifact modes remain atomic; run provenance is a declared set

Each source artifact retains one atomic mode: `SYNTHETIC`, `CAPTURED_REPLAY`, `LIVE_PUBLIC`, or `MOCK`. A deterministic `DataModeReceipt` carries the sorted transitive `mode_set`, a closed `declared_composition`, propagation status, and reasons.

The core demo composition `SYNTHETIC` plus `CAPTURED_REPLAY` is explicitly allowed and labeled. `MOCK` mixed with product evidence and `LIVE_PUBLIC` inserted into a captured replay timeline are rejected. Modes are provenance classes, not a scalar "stricter" ordering.

### 6. WatchCase cursors advance only on verified semantic completion

- `NO_ACTION`: advance to the decision's complete verified snapshot and schedule the next scan.
- `REVIEW_REQUIRED`: advance to the audited snapshot, link the task, and enter `AWAITING_HUMAN`.
- `ABSTAIN`: do not advance verified cursors or `last_verified_snapshot_id`; retain pending observation hashes and create an attention marker.
- `HALTED`: do not advance cursors; clear automatic scheduling until an explicit recovery action or authorized retry policy applies.
- `duplicate_suppressed`: never advances beyond the snapshot already referenced by the existing verified decision/task.

After an outage is restored, the next run must observe the previously unaudited observation hash again.

### 7. Replay hashes bind captured repository bytes

Protocol 1.0.1 will store the exact permitted captured source bytes under `artifacts/evidence/rcl-205/` and hash those bytes. Dynamic live re-fetches are separate `LIVE_PUBLIC` observations and cannot be compared directly with frozen capture hashes.

Every source entry records `retrieved_at`, capture path, byte count, SHA-256, semantic locator, and data mode. A clean clone must reproduce every frozen hash offline; one mutated byte must fail. Until those bytes and tests exist, RCL-205 is `in-progress`, not verified.

### 8. Replay chronology separates publication, dataset, and capture dates

The conservative 472-day arithmetic remains publication date 2025-01-08 to later public ClinVar appearance 2026-04-25. It is a case-specific chronology, not product detection performance.

The package must also record GEO public date 2024-09-27, current GEO-linked PMID `41957374`, Nature PMID `39779848`, the Nature data-availability link to `GSE248438`, GEO last-update date, and the exact XLSX capture date. Exact row values are "as captured" unless an archived historical byte source proves an earlier file state.

The Auditor verifies the publication-to-dataset relationship through the paper's data-availability statement, accession, contributor/scope consistency, and exact allele row. It must not require the GEO page's current linked PMID to equal the earlier qualifying paper PMID.

## Consequences

- Decisions 1 through 6 are synchronized across the normative documents and their required executable tests are named. This is document-level evidence only.
- Decisions 7 and 8 produced an offline-replayable protocol 1.0.1 package with exact repository bytes, corrected chronology/linkage, clean-copy verification, mutated-byte rejection, path-boundary rejection, and exact-row validation.
- Merge and Phase 3 remain `NO-GO` until the complete follow-up audit, safe owner-only push, and external auditor re-review pass.
- RCL-503 and RCL-506 remain not started; source-package verification does not prove product replay behavior.
- F-09 through F-18 must be resolved before their affected implementation tasks begin.
- F-19 through F-29 remain tracked cleanup and completeness work; none may be silently dropped.
- The historical Phase 2 follow-up passed at `195422e4d762d68d38e2b7f531cc5b1cd059cdb7`. The collaboration audit at `877c78d06d9b78f3071d17c81232fbc4302f857e` then returned `FAIL` on validator evidence coverage and current-state consistency. Its remediation successor was published at `c8be19476c24672fbf65d4dbf767fa8144360d22`; the second external re-review also returned `FAIL`, this time on transcript integrity and stale Graphify evidence wording. RCL-211 remains in progress until the second remediation is published and a new exact-head re-review passes.

## Verification gate

1. Cross-document search finds no remaining contradictory memory, citation, reason-code, mode, or cursor rule.
2. Policy examples use evaluated states and list all applicable lexical reason codes.
3. Candidate-plus-Assessor-dismissal cannot produce `NO_ACTION`; no candidate never invokes agents.
4. Poisoned memory produces a rejection receipt and identical policy/task output with memory disabled.
5. One mismatched material claim produces `ABSTAIN` and zero tasks.
6. The canonical mixed demo mode is accepted and displayed; disallowed combinations fail.
7. `ABSTAIN` and `HALTED` preserve unaudited observation visibility across retry.
8. A clean clone verifies every replay capture hash offline and rejects a mutated byte.

Local verification of items 1 through 7 is recorded in `docs/evaluation/reports/2026-08-17--adr-0008-normative-consistency-audit.md`. Item 8 and the F-07/F-08 chronology/linkage correction are recorded in `docs/evaluation/reports/2026-08-17--rcl-205-protocol-1.0.1-verification.md`. The historical exact-head review passed at `195422e4d762d68d38e2b7f531cc5b1cd059cdb7`; external reviews at `877c78d06d9b78f3071d17c81232fbc4302f857e` and then `c8be19476c24672fbf65d4dbf767fa8144360d22` returned `FAIL` on distinct collaboration evidence-integrity defects. Second remediation and a new exact-head external re-review are required before merge or Phase 3.

## Rollback or supersession

Any replacement must preserve deterministic candidate routing, non-authoritative memory, fail-closed material-claim audit, evaluated-state policy facts, explicit mixed provenance, non-advancing unsafe cursors, and offline replay integrity.
