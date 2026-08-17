# ADR-0008 Normative Consistency Audit

- Date: 2026-08-17
- Scope: F-01 through F-06 only
- Result: PASS at corrected-document level
- Implementation evidence: none
- External follow-up audit: pending

## Purpose

Verify that ADR-0008 decisions 1 through 6 are synchronized across the normative architecture, artifact contracts, lifecycle rules, deterministic policy, threat model, evaluation protocols, replay design, demo narrative, UI lineage, plans, and evidence ledgers.

This report does not resolve F-07 or F-08, approve RCL-205, authorize merge, or authorize Phase 3 implementation.

## Finding closure evidence

| Finding | Corrected invariant | Primary evidence | Local result |
|---|---|---|---|
| F-01 | Deterministic Evidence Normalizer alone emits `CandidateDeltaReceipt`; Assessor cannot suppress a candidate or select `NO_ACTION`; an absent candidate invokes zero Assessor/Auditor calls | Policy, artifact contract, lifecycle, architecture, replay case, threat model | PASS |
| F-02 | Memory content and conflict state are absent from policy inputs; rejection is receipted; authoritative policy/task output must be identical with memory enabled or disabled | ADR-0002, policy, artifact contract, architecture, threat model, evaluation protocol | PASS |
| F-03 | One rejected or mismatched material claim makes the immutable assessment ineligible, emits `material_claim_unverified`, creates zero tasks, and requires a new fully audited assessment to continue | Policy, architecture, threat model, evaluation protocol, storyboard | PASS |
| F-04 | Policy facts use `FactState` and `PresenceState`; all applicable reasons are emitted once in lexical order; not-run is distinct from failed | Policy and PolicyDecision 2.0.0 contract/example | PASS |
| F-05 | Source artifacts retain one atomic mode; `DataModeReceipt` 2.0.0 records the sorted transitive mode set and registered composition; the canonical synthetic-plus-replay demo is allowed and visible | ADR-0005, artifact contract, architecture, threat model, demo registry | PASS |
| F-06 | Only verified `NO_ACTION` and `REVIEW_REQUIRED` advance exact verified cursors; `ABSTAIN`, `HALTED`, and duplicate suppression preserve unaudited evidence under explicit attention/recovery rules | Lifecycle, WatchCase 2.0.0 contract, architecture, threat model, UI registry | PASS |

## Executed checks

| Check | Result |
|---|---|
| Stale normative phrase scan | Zero contradictory occurrences outside append-only historical logs/reports |
| Policy representative rows | 11 rows; zero lexical-order or duplicate-code errors |
| Fenced JSON parse | 3 blocks; zero parse errors |
| Repository JSON parse | 71 files; zero parse errors |
| Derived UI registry | 52 rows, 52 unique field IDs, zero duplicates |
| UI artifact-contract reconciliation | 21 actual artifact types referenced; zero missing from the catalog |
| Markdown local links | Canonical scope: 50 files and 15 local links; full workspace scope: 88 files and 22 local links; zero scanner errors and zero broken links in both scopes |
| Whitespace | Zero trailing-whitespace matches; `git diff --check` passed |
| Credential-shaped content | Zero matches in the checked repository scope |

The first policy-row ordering probe failed before execution because PowerShell parsed `$row:` as an invalid variable reference. The corrected probe used `${row}` and returned 11 checked rows with zero errors. Later compressed batch probes repeated missing-whitespace `foreach` errors for policy and JSON checks; separate readable retries checked 11 policy rows, 3 fenced JSON examples, and 71 JSON files with zero errors. ERR-2026-08-17-052, ERR-2026-08-17-054, and ERR-2026-08-17-055 retain all failed attempts so later green results cannot erase them.

## Boundaries

- These are document-level consistency results, not executable guardrail activation evidence.
- F-07 and F-08 remain open until replay protocol 1.0.1 stores exact permitted bytes, validates them offline, and records corrected chronology/linkage metadata.
- RCL-205, merge, push, and Phase 3 remain blocked by their existing gates.
- The GitHub auditor checkpoint is not ready. It becomes ready only after F-07/F-08 are resolved, the complete local follow-up audit passes, and the owner confirms Cursor integration is disabled before push.
- A post-edit `graphify update .` did not complete and the graph timestamps did not change. ERR-2026-08-17-053 records the stale-graph condition; all PASS results above come from direct source-document checks, not Graphify coverage.
