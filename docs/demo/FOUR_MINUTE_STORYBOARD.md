# Recall Four-Minute Demo Storyboard

- Status: version 2.1 shot plan. Opening narration locked by the owner 2026-08-24 after four review rounds.
  Screen-flow draft returns to the owner for approval before any recording.
- Version: 2.1.0, replacing 2.0.0
- **Timing decided 2026-08-24 by the external evaluator, ratified by the owner. The
  allocation below is final, not a proposal.**
- **The opening is closed. It is locked, measured at 71s, and is not reopened for
  wordsmithing by any party.**
- Tasks: RCL-207 and RCL-904
- Updated: 2026-08-24
- Target duration: 3 minutes 40 seconds
- Hard maximum: 4 minutes; rehearsal ceiling 3 minutes 50 seconds
- Language: English narration and English subtitles

This is the shot and evidence plan, not the final word-for-word script. RCL-904
writes and times the final script only after the critical path exists.

## What changed in version 2.1

| Change | Reason |
|---|---|
| Opening narration replaced by the owner's locked text, reproduced verbatim | Approved 2026-08-24 after four review rounds. It is quoted, not paraphrased, and not re-timed by estimate |
| Opening absorbs half of the old fleet-introduction job, so the Registry segment narrows to catalog plus evidence visuals | The opening now names the roles and the separation-of-duties rule itself |
| Evidence card added to the never-cut list | Owner's hard condition. The chronology claim is only defensible with its sources on screen |
| Stack named explicitly in one sentence | Gemini 3.7 Flash, Google ADK, Vertex AI Agent Engine, local Gemma 4 for redaction |
| Fault-run narration uses the rubric's own words, with a setup-and-payoff callback | The opening promises the abstain behaviour; the fault run delivers it |
| Closing numbers cite the frozen result from the corrected view, never the raw manifest | `corpus/ERRATUM_001_p1-frozen-001.md` section 8. The raw manifest carries stale arm labels |
| Cloud-proof segment uses current assets, and `resolution_mode` joins the visible proof list | Three permanent Agent Engines, Registry catalog auto-registration, four-span single trace |
| Conditional privacy segment resolved to the full version | The frozen manifest selected it: incremental +470 true positives, zero accepted escapes |
| Every duration computed from word count, none estimated | Evidence-discipline rule 3 applied to time. An estimated duration is an unmeasured number |

## What changed from version 1

| Change | Reason |
|---|---|
| Registry and role separation moved ahead of the privacy segment | The fleet claim is the architecture spine; the jury should see who may act before seeing what is protected |
| Privacy and local model became one conditional segment | The local model earns screen time only if protocol P1 measures an incremental contribution |
| Week timeline and fleet board moved after the fault run | Durable monitoring reads as a consequence of the audited run, not as a preamble |
| Closing numbers segment made explicit | Every spoken number must map to a committed artifact, so it needs its own shot |
| Target trimmed from 3:45 to 3:40 | Leaves rehearsal headroom below the 3:50 ceiling and the 4:00 hard maximum |
| Autonomy framing sentence and the Controller-level `ToolAuthorization` wording restored from the version 1 storyboard | Both were lost in the version 2 rewrite; the autonomy sentence is required in the first twenty seconds and the fault run is a Controller decision attributed to Assessor identity, not an agent action |
| Privacy claim separated from the local-model claim | The demonstrated boundary is the structured-only egress profile, which is deterministic; only the residual-span contribution depends on the P1 result |

## Demo thesis

Recall autonomously monitors, cites, audits, rejects, and queues; a human makes
the final decision. Autonomous agents normally fail by turning plausible model
output into action.
Recall makes that structurally impossible: specialist agents may propose and
audit evidence, but only deterministic policy can create a simulated review task
from a complete, independently verified artifact set.

## Viewer contract

The video must remain understandable without genetics expertise, and must state:

- all institutional records are synthetic;
- public evidence is `CAPTURED_REPLAY` or separately labelled `LIVE_PUBLIC`;
- execution is live even when the evidence input is a captured replay;
- the contest build is a non-clinical research prototype;
- no model classifies a variant, changes a report, or contacts a patient;
- every result on screen comes from the exact run artifacts being shown.

## Locked opening narration

Approved by the owner on 2026-08-24 after four review rounds. **Reproduced
verbatim. It is not edited, re-broken, or paraphrased**, and the em dashes below
are the owner's own and are preserved for that reason, notwithstanding the
house style rule against them in documents this lane writes.

> You monitor dependencies for CVEs. Now imagine alerts only fired when the vendor updated the changelog — not when the exploit went public. Clinical genetics works that way today: the tools watch the changelog.
>
> A cancer patient's genetic test comes back 'uncertain significance': a classification that means do not act, wait for evidence. That one label can stand between her and a drug approved for exactly her kind of tumor.
>
> For one real variant in the BRCA2 gene, laboratory evidence that it behaves like the harmful ones went public in September 2024. The clinical record first moved in April 2026. Five hundred and seventy-five days — and in between, nothing was watching.
>
> Recall stands watch for her clinical geneticist: a fleet of specialized agents running in the background, unprompted. One watches evidence. One assesses it. One audits every citation — because models invent them. Separate agents, because the one that proposes must never be the one that checks. The controller delegates the work; decisions stay in deterministic policy. And when the evidence is too weak, Recall says so instead of guessing.

### Measured length, not estimated

| Measure | Value |
|---|---|
| Spoken words | **178** |
| At 150 wpm | 71.2s |
| At 155 wpm | 68.9s |
| At 160 wpm | 66.8s |

The count excludes the three em dashes, which are pauses rather than spoken
words. Rehearsal verifies the delivered figure; until then the planning figure is
the 150 wpm worst case, 71.2s.

The instruction accompanying the locked text stated 172 words and roughly 65 to
69 seconds. The recount gives 178 words and 66.8 to 71.2 seconds. The measured
figures are used here. This is not a correction to the narration, which is
unchanged, only to its timing.

### Fault-run callback

At the moment `ABSTAIN` appears on screen:

> Too weak to act on — so it abstains. Exactly as promised.

12 spoken words, 4.6s at 155 wpm. Setup is in the opening's final sentence.

## Runtime arithmetic, and the decision it forces

Version 2.0 ran 220s across seven segments of 15, 20, 20, 75, 45, 25 and 20
seconds. The locked opening replaces the 15 second segment and takes half the job
of the 20 second segment, so it displaces 25 seconds of the old plan.

At its measured length the opening is 66.8 to 71.2 seconds. That is a swing of
**+41.8 to +46.2 seconds** against what it replaces.

The instruction says total runtime is conserved. Computed from the actual word
count, it cannot be, and no arrangement of the remaining segments makes 220
seconds reachable without cutting material. Stating that plainly is the point of
computing durations rather than estimating them.

Budget remaining after the opening, using the 71.2s planning figure:

| Ceiling | Remaining for the other six segments |
|---|---:|
| Target 220s | 148.8s |
| Rehearsal ceiling 230s | 158.8s |
| Hard maximum 240s | 168.8s |

The old six remaining segments total 205 seconds. Fitting them into 148.8
requires removing 56.2 seconds.

### Decided allocation

Ruled by the external evaluator on 2026-08-24 and ratified by the owner. This is
the allocation, not a proposal.

| Segment | v2.0 | Decided | Word budget at 155 wpm |
|---|---:|---:|---:|
| Locked opening | 15 | **71** | 178, measured and fixed |
| Registry catalog and fleet | 20 | 12 | 31 |
| Privacy, full version | 20 | 20 | 52 |
| Uninterrupted audited run | 75 | **55** | 142 |
| Fault run with denial and abstain | 45 | **35** | 90 |
| Cloud proof and fleet board | 25 | 15 | 39 |
| Closing numbers and limitations | 20 | 12 | 31 |
| **Total** | **220** | **220** | |

### Why the run gives seconds to the fault segment

The reasoning travels with the numbers, because a later reader will otherwise
assume the live run was trimmed for convenience.

The uninterrupted run proves one scored sub-criterion, Proof of Action, and that
requirement is **binary**: the take is uninterrupted or it is not. Fifty-five
seconds satisfies it as completely as seventy-five.

The fault run touches **three** scored rows: failure-tolerant inter-agent
routing, which is the only concrete Architecture sub-question written for this
track, the abstain behaviour under Innovation, and the narrative payoff of the
promise made in the opening's final sentence. The five seconds moved from the run
to the fault segment buy comprehension where scoring density is highest.

Cloud proof holds at 15 seconds as reserve. It is not raided to fund anything
else.

## Evidence card, never cut

Owner's hard condition. During the third paragraph of the opening, an on-screen
source card shows:

| Field | Value |
|---|---|
| Variant | BRCA2 `c.7522G>C` |
| ClinVar | `VCV002895953` |
| Functional data public | GEO `GSE248438`, 2024-09-27 |
| Paper published | PMID `39779848`, 2025-01-08 |
| ClinVar first reflection | 2026-04-25, `VCV002895953.5` |

The spoken 575 anchors the **GEO date to the ClinVar date**. Verified:
2024-09-27 to 2026-04-25 is 575 days.

The paper date is a **separate line and a different number**: 2025-01-08 to
2026-04-25 is 472 days. The two must never be conflated, spoken as one figure, or
shown on the same counter.

Two honesty sentences travel with the claim wherever it appears, quoted from
`docs/evaluation/HISTORICAL_REPLAY_CASE.md`:

- the aggregate record became **conflicting, not uniformly pathogenic**;
- the chronology **does not establish that the paper caused the later
  submission**.

The video description carries the same references as clickable links, plus a link
to `docs/evaluation/HISTORICAL_REPLAY_CASE.md`.

## Stack sentence, never cut

One sentence in the fleet segment names the stack: Gemini 3.7 Flash, Google ADK,
Vertex AI Agent Engine, and local Gemma 4 for redaction.

## Timed storyboard

| Time | Duration | Screen and action | Narration objective | Visible proof | Score rows |
|---|---:|---|---|---|---|
| 00:00-01:11 | 71s | Locked opening narration over the specialist review queue and the evidence card. See the locked text above. | Carry the whole opening verbatim. | `UI-GLOBAL-MODE`, non-clinical label, **evidence card, never cut**, **stack sentence, never cut** | Operational utility, demo clarity, architecture |
| 01:11-01:23 | 12s | Registry catalog listing with auto-registered agents, exact revisions, and binding status. | Introduce the fleet before any run: four separated roles, registry-resolved revisions, deterministic controller, deterministic policy. | `UI-CLOUD-REGISTRY-COUNT`, `UI-AGENT-ROSTER` with role, agent, revision, binding status, `UI-ROUTE-STATUS` | Architecture, multi-agent separation, managed discovery |
| 01:23-01:43 | 20s | Submit a synthetic laboratory note. Deterministic detectors run, the local model proposes residual spans, deterministic adjudication runs, and the structured-only egress profile decides which field paths may exist in the cloud-bound payload at all. | Show that prose never leaves because the payload has no prose field, and that the local model is useful but never authoritative. Full version, selected by the frozen manifest. | `UI-PRIVACY-STATUS`, `UI-PRIVACY-DETERMINISTIC-SPANS`, `UI-PRIVACY-GEMMA-SPANS`, `UI-PRIVACY-OUTBOUND-FIELDS`, `UI-PRIVACY-EGRESS-PROFILE`, `UI-PRIVACY-RAW-TEXT-EGRESS` reading zero | Model bonus, privacy boundary, architecture |
| 01:43-02:38 | 55s | One uninterrupted click starts the audited replay. The screen recording is uncut while lanes, persisted transitions, evidence, and audit update. | Let the system explain itself through motion: registry resolution, observation, candidate comparison, independent citation verification, deterministic policy, one simulated task. | `UI-GLOBAL-RUN-ID`, `UI-GLOBAL-TRACE-ID`, `UI-AGENT-STATE`, `UI-CLOUD-TRANSITIONS`, `UI-EVIDENCE-CANDIDATE`, `UI-CITATION-TOTAL`, `UI-CITATION-VERIFIED`, `UI-CITATION-STATUS`, `UI-POLICY-OUTCOME`, `UI-POLICY-REASONS`, `UI-TASK-COUNT-RUN` | Proof of action, delegation, state discipline, product demo |
| 02:38-03:13 | 35s | Second run with a fault fixture: one mismatched material citation, and a deterministic Controller-level `ToolAuthorization` request attributed to Assessor identity for a forbidden task-creation tool. | Use the rubric's own words: when a worker agent returns a hallucinated citation, the system recovers, the audit fails it, and policy abstains. At the moment `ABSTAIN` appears, speak the locked callback. The `DENIED` frame must satisfy the comprehension gate below. | `UI-TOOL-DENIAL` with role, tool, and reason codes, `UI-CITATION-STATUS` incomplete, `UI-POLICY-OUTCOME` abstain, `UI-POLICY-MISSING`, `UI-TASK-COUNT-RUN` read back from the task ledger, `UI-WATCH-PENDING` retained | Hallucination recovery, strict separation, failure-tolerant routing |
| 03:13-03:28 | 15s | Week timeline and fleet board, then the three permanent Agent Engines in the console, the Registry catalog listing showing auto-registration, and the four-span single-trace view. | Durable monitoring without a running model process, and proof the backend is not a local mock. | `UI-WATCH-SCAN-COUNT`, `UI-WATCH-PENDING`, `UI-WATCH-ATTENTION`, `UI-CLOUD-RUNTIME-REV`, `UI-CLOUD-HEALTH`, `UI-ROUTE-STATUS` with the `resolution_mode` badge, correlated run and trace identifiers | Managed deployment, architecture, production readiness |
| 03:28-03:40 | 12s | Return to the contrast: the audited run produced one simulated task, the unsafe run produced none. Close on authority and limitations. | The specialist sees only audited candidates. Agents may reason; they cannot decide. Frozen privacy numbers are cited from the corrected view, never the raw manifest. | Derived counts with source links, `NON-CLINICAL RESEARCH PROTOTYPE`, exact `SYNTHETIC` plus `CAPTURED_REPLAY` composition, clinician final authority | Operational utility, derived presentation, trustworthy close |

Total 220 seconds under the decided allocation: 71 + 12 + 20 + 55 + 35 + 15 + 12.
The rehearsal ceiling is 230 seconds and the binding maximum is 240 seconds.

Only the opening duration is measured from real text. The other six are budgets,
expressed above as word counts at 155 wpm, and each becomes a measured figure once
RCL-904 writes its narration. No duration in this document is an estimate, and
none may be entered as one.

## Conditional privacy segment

The privacy claim itself is not conditional. The demonstrated egress profile is
`STRUCTURED_ONLY`: the cloud-bound payload declares only registered structured
field paths and no free-text field, so laboratory prose has no field to travel
in and `UI-PRIVACY-RAW-TEXT-EGRESS` reads zero structurally rather than because
a detector stayed silent. That segment is spoken in every version below.

Only the **local-model** part of the 00:35-00:55 segment is conditional, and it
is selected only by the frozen P1 result:

| P1 result | Segment | Duration | Spoken claim |
|---|---|---:|---|
| Local model adds at least one incremental true positive and adds no accepted escape | Full version above | 20s | The local model found a residual identifier the rules missed; deterministic redaction and the outbound gate decided |
| Local model adds nothing, or the measurement did not run | Deterministic-only version: submit the note, show detections, the structured-only egress profile, and the released field paths | 12s | The payload carries registered structured fields and no prose field at all, so nothing unrecognised can leave |
| Local model increases accepted escapes | Segment removed entirely | 0s | No local-model claim is spoken |

The segment version is chosen from the committed P1 manifest, never from a
rehearsal impression.

**Resolved on 2026-08-24.** The frozen run `p1-frozen-001` selected the full
version: the primary arm contributes 470 incremental true positives and adds zero
accepted escapes, so the first row's condition is met. Recorded in
`corpus/ERRATUM_001_p1-frozen-001.md` and read from the corrected view.

## Comprehension gate on the fault segment

Binding, applied at rehearsal. One question decides the segment:

> Does a first-time viewer understand **what** the system refused and **why**?

If the answer is no, **the fix is not more seconds.** Adding time to an
unreadable frame produces a longer unreadable frame. The on-screen presentation
of the `DENIED` receipt changes instead.

### Required shape of the DENIED frame

The frame reads at a glance, then rewards a closer look:

- a **plain-language label** sits next to the receipt, naming the tool and the
  refusal in ordinary words, for example the tool name followed by
  "refused: not on this agent's allowlist";
- the **raw reason codes sit beneath that label**, not in place of it, so the
  frame keeps its authenticity as a real receipt rather than a caption;
- the agent identity and the tool identifier are legible without pausing;
- nothing in the frame is added in editing. The plain label is rendered by the
  interface from the receipt itself, so it is derived rather than narrated over.

The last point matters: a label typed into an editing timeline would be a preset
value in the sense the derived-value rule forbids. The label is a view of the
receipt, produced the same way every other displayed value is produced.

## Critical live path

The 00:55-02:10 segment is the primary unedited proof of action. It must show
one real invocation of the deployed backend. The evidence source may be a frozen
captured replay, but the controller, agent invocations, artifact writes, policy
evaluation, database transitions, and interface updates must execute during
recording.

The run is invalid as demo evidence if a prerecorded video plays inside the
interface, the interface advances on timers rather than persisted state, a preset
label determines a displayed outcome, a model or the frontend writes the terminal
result, the cloud view cannot be correlated to the same run and trace, or a mode
badge is missing or overlaid in editing.

## Fault-run contract

The fault button selects an input fixture, not an output. The fixture manifest
contains:

- a synthetic case reference;
- one captured replay reference;
- one deliberately mismatched citation input;
- one deterministic Controller-level `ToolAuthorization` request attributed to
  Assessor identity for a forbidden tool;
- expected safety invariants, but no hard-coded terminal outcome.

The result is produced by the normal controller, citation auditor, authorisation
layer, and policy gate. The run passes only if the denial and audit receipts
exist and authoritative read-back confirms that no task was created.

## Claim gates

- The phrase "before the classification changed" may appear only if RCL-205 and
  RCL-206 produce a source-attributed timeline and a frozen comparison protocol
  that verify it. Otherwise the bounded wording is "Recall found a new evidence
  signal while the captured classification snapshot stayed unchanged". If even
  that is unproven, the sentence is removed.
- No workload reduction, lead time, accuracy, privacy, or false-positive number
  is spoken until its evaluation artifact is frozen in the claim ledger.
- The frozen privacy numbers are cited from
  `artifacts/evidence/p1-frozen-001/p1-frozen-001.corrected-view.json`, never from
  the raw manifest, which carries the stale arm labels recorded in
  `corpus/ERRATUM_001_p1-frozen-001.md`. The spoken figures are: accepted payloads
  0 of 180 rising to 136 of 180, exact recall 0.76 rising to 0.98, and zero
  identifier escapes on every path. All three verified against the corrected view.
- Privacy results are described as synthetic-corpus results, never as
  de-identification performance.

## Required capture checklist

- Public video no longer than four minutes, English narration and subtitles.
- Hosted application URL visible.
- Cloud deployment proof visible and correlated to the run.
- One uninterrupted managed execution and one visibly blocked unsafe execution.
- Explicit data-mode and non-clinical labels in the captured frames.
- No credentials, account or project identifiers, raw prompts, or sensitive data.
- Every result-bearing frame audited against `DERIVED_VALUE_REGISTRY.md`.

## Cut ladder

Apply in order if rehearsal exceeds 3:50:

1. shorten the privacy narration, keeping the receipt on screen;
2. use the 12-second deterministic-only privacy segment;
3. shorten the managed-proof explanation while keeping the cloud view;
4. drop the fleet board detail, keeping the week timeline;
5. remove the local model from the video entirely.

Removing the local model does not remove the privacy segment. The structured-only
egress profile is deterministic and model-independent, and it is what the
zero-raw-text claim rests on.

Never cut the human friction, the uninterrupted live run, the independent audit,
the forbidden-action denial, the deterministic outcome, the cloud proof, the
data-mode labels, or the limitations statement.
