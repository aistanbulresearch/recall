# Phase 2 F-01 Through F-08 Follow-up Audit

- Date: 2026-08-17
- Scope: complete local follow-up after ADR-0008 and replay protocol 1.0.1
- Result: PASS within the stated design and source-package boundaries
- Product execution evidence: none
- External auditor re-review: pending safe owner-only push

## Finding disposition

| Finding | Local evidence | Result | Boundary |
|---|---|---|---|
| F-01 deterministic candidate authority | `CandidateDeltaReceipt` is emitted only by the deterministic normalizer; Assessor cannot suppress the candidate or select `NO_ACTION` | PASS | Corrected design, not executable routing proof |
| F-02 memory authority | Memory state is excluded from policy inputs and enabled/disabled byte/task parity is required | PASS | Corrected design, not Memory Bank runtime proof |
| F-03 material citation failure | Any rejected material claim invalidates the immutable assessment, yields `material_claim_unverified`, and requires a new fully audited assessment | PASS | Corrected design, not Auditor fault-run proof |
| F-04 evaluated policy facts | `FactState` and `PresenceState` distinguish failure, absence, and not-evaluated; all applicable reasons are lexical and unique | PASS | Eleven representative rows checked; Policy Gate not implemented |
| F-05 data-mode composition | Atomic source modes derive a sorted run-level mode set and a closed composition; synthetic-plus-replay is explicit | PASS | Corrected design, not UI/runtime proof |
| F-06 cursor and backlog safety | Only exact verified `NO_ACTION` or `REVIEW_REQUIRED` inputs advance; `ABSTAIN`, `HALTED`, and duplicate suppression preserve pending evidence | PASS | Corrected design, not Firestore/CAS proof |
| F-07 reproducible replay bytes | Ten exact repository captures verify by byte count, SHA256, source host, semantic anchor, and capture-root boundary | PASS | Frozen source package only |
| F-08 chronology and linkage | GEO submission/public/update facts, publication dates, ClinVar version dates, current PMID, qualifying PMID, accession linkage, and exact as-captured row are distinct | PASS | Chronology does not prove causation or original-public-date row availability |

## Executed checks

| Check | Result |
|---|---|
| Evidence-script parser | 3 files; 0 parse errors |
| Replay clean verification | PASS; 10 captures; 1,400,869 bytes; 7 chronology checks; 1 exact XLSX row; 1 separate live-public source; 0 network calls |
| Replay fault tests | Clean copy passed; mutated byte rejected; capture-root path escape rejected; 0 network calls |
| Policy representative rows | 11 rows; 0 lexical-order or duplicate-code errors |
| Canonical/source JSON parse | 5 files excluding generated Graphify data; 0 parse errors |
| Full workspace JSON parse | 104 files including generated Graphify data; 0 parse errors |
| Fenced JSON parse | 3 blocks across 87 Markdown files; 0 parse errors |
| Derived UI registry | 52 rows; 52 unique IDs; 0 duplicates |
| UI artifact-contract reconciliation | 21 actual artifact types; 0 missing contracts |
| Markdown local links | 87 files; 22 local links; 0 scanner errors; 0 broken links |
| Whitespace | `git diff --check` passed; 0 trailing-whitespace matches |
| Credential-shaped content | 120 checked non-capture/non-Graphify files; 0 signature matches; 0 secret-shaped filenames |
| Authorship markers in diff | 0 prohibited authorship/co-authorship markers |
| Third-party article boundary | One Nature linkage JSON file, 826 bytes; no Nature HTML or PDF stored |
| Capture inventory | 10 files and 1,400,869 bytes, matching the manifest and verifier |
| Staged capture bytes | 10 working files and 10 staged blobs match the manifest after the evidence tree was marked `binary -eol` |
| Graphify freshness | Current graph has 131 nodes and 154 links; ADR-0008, `CandidateDeltaReceipt`, and consistency-audit nodes are present. Post-audit no-stamp runner recovery completed query/explain/path without hanging; raw traversal remains prohibited |
| Git identity and state | HEAD remains `c4e2b02d7e596ee99879686b3f53b214809d4673`; branch is `feature/rcl-010-fleet-architecture`; owner identity is `aistanbulresearch`; no commit or push occurred |

## Failed probes retained

The audit did not infer success from failed checks. ERR-064 records outer-shell variable expansion in the first parser probe. ERR-065 and ERR-066 record the obsolete UI regex/generic code-span assumptions and a diagnostic pipeline parse error. ERR-067 records an incorrect exact Graphify label assumption. ERR-068 records a multi-file patch that wrote partially before hanging. ERR-069 records a compressed final UI command that omitted whitespace. Each failed probe was replaced by a corrected, independently executed check whose result appears above.

## Boundaries and gate decision

- F-01 through F-06 pass at corrected-document level only.
- F-07 and F-08 pass at frozen-source-package level only.
- No Recall agent, source connector, Policy Gate, Firestore transition, simulated task, managed runtime, web surface, or contest metric has been executed.
- No clinical, production, compliance, operational-utility, lead-time, or safety claim is approved.
- The correction package is locally ready for the owner-only remote re-review gate.
- Push remains blocked until the owner explicitly confirms the Cursor GitHub integration is disabled for Recall. After confirmation, attribution preflight, commit, push, remote read-back, visible actor scan, and GitHub auditor re-review are mandatory.
