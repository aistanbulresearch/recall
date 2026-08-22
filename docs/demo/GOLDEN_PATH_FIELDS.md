# Golden-Path Field Selection

- Status: proposed by lane L3; **pending lane L2 confirmation** (stop point 3)
- Date: 2026-08-22
- Source of truth: `docs/demo/DERIVED_VALUE_REGISTRY.md`
- Implementation: `web/src/viewmodel/registry.ts`

The derived-value registry defines 52 fields. The demo surface implements 34 of
them today and marks 12 as the golden path: the minimum set that must resolve
for the audited replay segment to be shown at all. No field identifier here is
new. If lane L2 emits a different field set, this document changes before the
interface does; the interface never invents a field.

## Golden path

| Field ID | Source artifact | JSON path | Missing behaviour |
|---|---|---|---|
| UI-GLOBAL-MODE | DataModeReceipt | `$.mode_set[*]` plus `$.declared_composition` | UNKNOWN |
| UI-GLOBAL-RUN-ID | ScanRun | `$.run_id` | UNKNOWN |
| UI-GLOBAL-RUN-STATE | ScanRun | `$.state` | UNKNOWN |
| UI-GLOBAL-TRACE-ID | ScanRun | `$.trace_id` | UNAVAILABLE |
| UI-WATCH-STATUS | WatchCase | `$.state` | UNKNOWN |
| UI-WATCH-NEXT-SCAN | WatchCase | `$.next_scan_at` | UNKNOWN |
| UI-EVIDENCE-CANDIDATE | CandidateDeltaReceipt | `$.candidate_delta_state` | UNKNOWN |
| UI-CITATION-STATUS | CitationAuditReceipt | `$.audit_status` | INCOMPLETE |
| UI-CITATION-VERIFIED | CitationAuditReceipt | `$.claim_verdicts[*]` filtered to `VERIFIED` | UNKNOWN |
| UI-POLICY-OUTCOME | PolicyDecision | `$.outcome` | INCOMPLETE |
| UI-POLICY-REASONS | PolicyDecision | `$.reason_codes[*]` | UNKNOWN |
| UI-TASK-COUNT-RUN | ReviewTask ledger | count of task artifacts for the run | UNKNOWN |

## Privacy fields

All five privacy rows of the registry are implemented and resolve from a real
`PrivacyReceipt` produced by `src/recall/privacy`:

`UI-PRIVACY-STATUS`, `UI-PRIVACY-DETERMINISTIC-SPANS`, `UI-PRIVACY-GEMMA-SPANS`,
`UI-PRIVACY-OUTBOUND-FIELDS`, `UI-PRIVACY-RAW-TEXT-EGRESS`.

## Fleet board and registry view

`UI-AGENT-ROSTER`, `UI-AGENT-STATE`, `UI-ROUTE-STATUS`, `UI-TOOL-DENIAL`,
`UI-CLOUD-REGISTRY-COUNT`, `UI-CLOUD-TRANSITIONS`, `UI-CLOUD-RUNTIME-REV`,
`UI-CLOUD-HEALTH`, `UI-WATCH-SCAN-COUNT`.

## Supporting fields

`UI-GLOBAL-UPDATED` (carries the stale state), `UI-WATCH-LAST-SCAN`,
`UI-WATCH-PENDING`, `UI-WATCH-ATTENTION`, `UI-EVIDENCE-CLASS-UNCHANGED`,
`UI-CITATION-TOTAL`, `UI-POLICY-MISSING`, `UI-TASK-STATE`.

## Not implemented yet

Evidence snapshot dates, observation and delta counts, the citation source row,
queue-level task counts, task provenance, loop hop count, and every
evaluation-only field. They stay unimplemented rather than stubbed, because a
stubbed result field would be exactly the failure the registry forbids.

## Rules the implementation enforces

1. A field renders a value only when an authoritative artifact resolved it.
2. A missing source produces `UNKNOWN`, `UNAVAILABLE`, or `INCOMPLETE`, never
   zero, clean, safe, or passed.
3. An empty collection renders as zero only when the contract's guard also
   resolves. `UI-WATCH-PENDING` requires a verified scan before zero is shown.
4. Every rendered field carries artifact type, JSON path, artifact identifier,
   content hash, builder version, and derivation time.
5. A known value without lineage throws instead of rendering.
6. The fixture selector changes input artifacts only. A static scan fails the
   build when a result component contains an outcome literal, a fixture name, or
   a rendered number.
7. Technical `HALTED` and policy `ABSTAIN` use different markup and different
   explanatory copy.
