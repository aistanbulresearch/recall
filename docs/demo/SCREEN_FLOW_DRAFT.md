# Screen-flow draft, four-minute demo

- Status: **DRAFT for owner approval. Visuals are not final and nothing is recorded until this is approved.**
- Updated 2026-08-25: the live-path decision in section 4 has been made by the owner and is recorded, not proposed.
- Date: 2026-08-25
- Lane: L3
- Governed by: `docs/demo/FOUR_MINUTE_STORYBOARD.md` v2.1, frozen allocation
- Shooting date: 2026-08-29

This document says what is on screen in each segment, where every value comes
from, and what has to be built before the camera runs. It does not restate the
narration, which is locked and lives in the storyboard.

Two rules govern every frame here. Nothing on screen is typed into an editing
timeline: every result-bearing value is rendered by the interface from an
artifact. And every number spoken or shown traces to a committed artifact, with
the frozen privacy figures read from the corrected view rather than the raw
manifest.

## 1. What the interface renders today

Verified by reading the components rather than from memory.

| Component | Renders |
|---|---|
| `MissionControl` | mode and run-state badges, run id, trace id, runtime revision, cloud health, updated-at |
| `MissionControl` watch panel | watch status, last scan, next scan, pending evidence, attention reasons |
| `FleetBoard` | agent roster table (role, agent, revision, binding), route status, registry count, transitions, scan count, agent-state list, the blocked-action frame |
| `MissionControl` safety panel | evidence candidate, classification-unchanged, citation total, verified, audit status |
| `MissionControl` policy panel | policy outcome badge, reason list, missing prerequisites |
| `PrivacyPanel` | privacy decision, deterministic spans, model residual spans, cloud field paths, raw-text egress, egress profile |
| `RegistryView` | registry bindings |
| `Badges`, `FieldValue` | data-mode badge, run-state badge, status handling for every field |

Thirty-five registered field identifiers resolve through the view model. Every
one carries `source_refs`, and a field whose source artifact is absent renders
`UNKNOWN`, `UNAVAILABLE`, or `INCOMPLETE` rather than a zero.

## 2. Segment-by-segment flow

Durations are the frozen v2.1 allocation. Only the opening is a measured
duration; the rest are word budgets at 155 wpm and become measured in rehearsal.

### 00:00-01:11, opening, 71s

Single screen, no cuts. The specialist review queue with one synthetic watch case
due.

On screen throughout: `UI-GLOBAL-MODE` badge reading `SYNTHETIC`, the
non-clinical prototype label, and the watch panel showing status, last scan and
next scan.

**Evidence card, never cut.** Appears during the third paragraph, over the
existing layout rather than replacing it. Contents fixed by the storyboard:

| Field | Value |
|---|---|
| Variant | BRCA2 `c.7522G>C` |
| ClinVar | `VCV002895953` |
| Functional data public | GEO `GSE248438`, 2024-09-27 |
| Paper published | PMID `39779848`, 2025-01-08 |
| ClinVar first reflection | 2026-04-25, `VCV002895953.5` |

The 575-day counter animates between the GEO date and the ClinVar date only. The
472-day paper interval is a separate line and never shares the counter. Both
honesty sentences appear as on-screen text while the card is up: the aggregate
record became conflicting rather than uniformly pathogenic, and the chronology
does not establish that the paper caused the later submission.

**To build:** the evidence card does not exist. It is the largest new surface in
this flow. See section 3.

### 01:11-01:23, registry and fleet, 12s

`RegistryView` and the `FleetBoard` roster table. Four lanes with role, agent id,
revision and binding status, each drawn only because the registry resolved that
exact revision.

Visible proof: `UI-CLOUD-REGISTRY-COUNT`, `UI-AGENT-ROSTER`, `UI-ROUTE-STATUS`
with the `resolution_mode` badge.

**Stack sentence, never cut**, spoken over this segment: Gemini 3.7 Flash, Google
ADK, Vertex AI Agent Engine, and local Gemma 4 for redaction.

**To build:** the `resolution_mode` badge. `UI-ROUTE-STATUS` renders today as a
plain field value.

### 01:23-01:43, privacy, 20s

`PrivacyPanel`, full version, selected by the frozen manifest.

A synthetic laboratory note is submitted. Detectors run, the local model proposes
residual spans, deterministic adjudication runs, and the structured-only egress
profile decides which field paths may exist in the payload.

Visible proof: `UI-PRIVACY-STATUS`, `UI-PRIVACY-DETERMINISTIC-SPANS`,
`UI-PRIVACY-GEMMA-SPANS`, `UI-PRIVACY-OUTBOUND-FIELDS`,
`UI-PRIVACY-EGRESS-PROFILE`, and `UI-PRIVACY-RAW-TEXT-EGRESS` reading zero.

The last two are shown together, never apart. The zero means the payload declares
no free-text field at all, and the profile beside it is what makes that legible
rather than vacuous.

**Renders today.** No new work.

### 01:43-02:38, uninterrupted audited run, 55s

One click, one continuous take, no cuts. This is the primary proof of action, and
the requirement is binary: uninterrupted or not.

The screen updates through registry resolution, observation, candidate
comparison, independent citation verification, deterministic policy, and one
simulated task, while lanes and persisted transitions move.

Visible proof: `UI-GLOBAL-RUN-ID`, `UI-GLOBAL-TRACE-ID`, `UI-AGENT-STATE`,
`UI-CLOUD-TRANSITIONS`, `UI-EVIDENCE-CANDIDATE`, `UI-CITATION-TOTAL`,
`UI-CITATION-VERIFIED`, `UI-CITATION-STATUS`, `UI-POLICY-OUTCOME`,
`UI-POLICY-REASONS`, `UI-TASK-COUNT-RUN`.

**Films live.** The interface renders correctly today against a static bundle,
which is the rehearsal rendering. For the shoot it is bound to L2's `run_fixture`
output so the controller, agent invocations, artifact writes, policy evaluation
and database transitions execute while the camera runs. That binding is scheduled
M2 work landing before the 28th freeze. See section 4.

### 02:38-03:13, fault run, 35s

Second run, fault fixture. One mismatched material citation, and a deterministic
Controller-level `ToolAuthorization` request attributed to Assessor identity for
a forbidden task-creation tool.

This segment carries three scored rows, which is why it holds five seconds taken
from the live run. It is also where the comprehension gate applies.

Visible proof: the `DENIED` frame, `UI-CITATION-STATUS` incomplete,
`UI-POLICY-OUTCOME` abstain, `UI-POLICY-MISSING`, `UI-TASK-COUNT-RUN` read back
from the ledger, `UI-WATCH-PENDING` retained.

The locked callback is spoken at the moment `ABSTAIN` appears.

**To build:** the DENIED frame headline. See section 3.

### 03:13-03:28, cloud proof, 15s

Week timeline and fleet board, then the three permanent Agent Engines in the
console, the Registry catalog listing showing auto-registration, and the
four-span single-trace view.

Visible proof: `UI-WATCH-SCAN-COUNT`, `UI-WATCH-PENDING`, `UI-WATCH-ATTENTION`,
`UI-CLOUD-RUNTIME-REV`, `UI-CLOUD-HEALTH`, correlated run and trace identifiers.

This segment is reserve and is not raided to fund anything else.

**Renders today** in the application. The console views are captured separately
and must correlate to the same run and trace.

### 03:28-03:40, closing, 12s

Return to the contrast: the audited run produced one simulated task, the unsafe
run produced none. Close on authority and limitations.

Frozen privacy figures appear here, read from
`artifacts/evidence/p1-frozen-001/p1-frozen-001.corrected-view.json` and verified
against it while writing this draft:

| Figure | Value |
|---|---|
| Records | 180 |
| Accepted payloads, deterministic baseline | 0 of 180 |
| Accepted payloads, primary arm | 136 of 180 |
| Accepted payloads, structured-only egress | 180 of 180 |
| Exact recall, baseline | 0.760648 |
| Exact recall, primary arm | 0.978241 |
| Incremental true positives | 470 |
| Accepted identifier escapes, every path | 0 |

Spoken as 0.76 rising to 0.98, acceptance 0 of 180 rising to 136 of 180, and zero
identifier escapes. Every one traces to the corrected view, never to the raw
manifest, which carries the stale arm labels recorded in the erratum.

Closing frames: `NON-CLINICAL RESEARCH PROTOTYPE`, the exact `SYNTHETIC` plus
`CAPTURED_REPLAY` composition, and clinician final authority.

## 3. The DENIED frame, against the comprehension gate

The gate asks one question: does a first-time viewer understand **what** the
system refused and **why**? If not, the fix is the frame, not more seconds.

### What renders today

The frame exists in `FleetBoard` and is already derived from the receipt, not
typed. It shows a `DENIED` headline with the line "The action was refused before
it could run", then a definition list of `agent_role`, `tool_id`,
`requested_action`, `decision`, and `reason_codes`, each code carrying a plain
gloss such as "The requested tool is not in this role tool scope."

For the fault fixture the receipt holds: role `EVIDENCE_ASSESSOR`, tool
`review-task-writer`, action `create_review_task`, decision `DENIED`, codes
`tool_not_allowlisted` and `role_cannot_create_terminal_outcome`.

### Why that does not pass the gate yet

The headline says a refusal happened. It does not say **what** was refused. The
tool and the action are in a definition list, and a viewer with roughly ten
seconds of screen time will not parse a `<dl>`. The glosses are good and they sit
below the fold of attention.

### The change

Compose the headline from the receipt so it names the actor, the action and the
reason in one line, for example: the Evidence Assessor was refused
`review-task-writer`, because that tool is not in this role's scope.

Every component of that sentence comes from a field already in the receipt, so
the composition is a view of the artifact. Nothing is typed into an editing
timeline, which is what makes this a UI change rather than a post-production one.
Raw reason codes stay beneath the label, not in place of it, so the frame remains
a real receipt rather than a caption.

Rehearsal decides whether it passes. If it does not, the frame changes again.

## 4. What must be built before the 29th

| Item | Segment | Size | Blocking |
|---|---|---|---|
| Evidence card | opening | largest new surface | yes, it is never-cut |
| DENIED frame headline | fault run | small, composition only | yes, the gate applies |
| `resolution_mode` badge | registry | small | yes, named in visible proof |
| Live binding to `run_fixture` output | audited run | M2 work, scheduled | yes, the live path ships |

**Decided by the owner, 2026-08-25: the live path ships.** The audited-run
segment films the real controller, agent invocations, artifact writes, policy
evaluation, and database transitions, executing during recording, which is what
the storyboard's critical-live-path rule requires.

The M2 UI binding is therefore a scheduled deliverable with a hard land-by ahead
of the 28th freeze, not a contingency. The static bundle remains rehearsal
rendering only.

There is no fallback branch in this plan and no alternative claim language to
prepare. The video claims the live system because the live system will be there.

## 5. What the owner is being asked to approve

1. The segment-by-segment flow above, against the frozen v2.1 allocation.
2. The evidence card contents and the rule that the 575 and 472 intervals never
   share a counter.
3. The DENIED frame change, and that rehearsal rather than this document decides
   whether it passes the gate.
4. The build list in section 4. The live-binding question that was open when this
   draft was written has since been decided by the owner and is recorded above,
   so it is no longer among the approvals sought here.

Visuals are not final. Approving this approves what is shown and where it comes
from, not how it looks.

## 6. Honesty boundaries carried into every frame

- All institutional records are synthetic. The data-mode badge is on screen and
  is never overlaid in editing.
- Public evidence is `CAPTURED_REPLAY` or separately labelled `LIVE_PUBLIC`.
- Execution is live even when the evidence input is a captured replay.
- The build is a non-clinical research prototype.
- No model classifies a variant, changes a report, or contacts a patient.
- Every result on screen comes from the exact run artifacts being shown.
- Privacy results are synthetic-corpus results and are never described as
  de-identification performance.
- Structured-only acceptance is a property of the payload shape, not a detection
  result, and is never shown as detector or model performance.
