# Recall Four-Minute Demo Storyboard

- Status: version 2 shot plan; **awaiting owner approval** (lane L3 stop point 4)
- Version: 2.0.0, replacing the 2026-08-15 version 1 ordering
- Tasks: RCL-207 and RCL-904
- Updated: 2026-08-22
- Target duration: 3 minutes 40 seconds
- Hard maximum: 4 minutes; rehearsal ceiling 3 minutes 50 seconds
- Language: English narration and English subtitles

This is the shot and evidence plan, not the final word-for-word script. RCL-904
writes and times the final script only after the critical path exists.

## What changed from version 1

| Change | Reason |
|---|---|
| Registry and role separation moved ahead of the privacy segment | The fleet claim is the architecture spine; the jury should see who may act before seeing what is protected |
| Privacy and local model became one conditional segment | The local model earns screen time only if protocol P1 measures an incremental contribution |
| Week timeline and fleet board moved after the fault run | Durable monitoring reads as a consequence of the audited run, not as a preamble |
| Closing numbers segment made explicit | Every spoken number must map to a committed artifact, so it needs its own shot |
| Target trimmed from 3:45 to 3:40 | Leaves rehearsal headroom below the 3:50 ceiling and the 4:00 hard maximum |

## Demo thesis

Autonomous agents normally fail by turning plausible model output into action.
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

## Timed storyboard

| Time | Duration | Screen and action | Narration objective | Visible proof | Score rows |
|---|---:|---|---|---|---|
| 00:00-00:15 | 15s | Open on the specialist review queue with one synthetic watch case due. No logo, no team slide. | State the human friction: a specialist cannot reopen every old uncertain result whenever public evidence changes. | `UI-GLOBAL-MODE`, `UI-WATCH-STATUS`, `UI-WATCH-LAST-SCAN`, `UI-WATCH-NEXT-SCAN`, non-clinical label | Operational utility, demo clarity |
| 00:15-00:35 | 20s | Registry resolution and the four agent lanes with exact revisions, then the authority boundary. | Introduce the fleet before any run: four separated roles, registry-resolved revisions, deterministic controller, deterministic policy. | `UI-CLOUD-REGISTRY-COUNT`, `UI-AGENT-ROSTER` with role, agent, revision, binding status, `UI-ROUTE-STATUS` | Architecture, multi-agent separation, managed discovery |
| 00:35-00:55 | 20s | Submit a synthetic laboratory note. Deterministic detectors run, the local model proposes residual spans, deterministic adjudication and the outbound allowlist decide. | Show why the local model is useful but never authoritative. | `UI-PRIVACY-STATUS`, `UI-PRIVACY-DETERMINISTIC-SPANS`, `UI-PRIVACY-GEMMA-SPANS`, `UI-PRIVACY-OUTBOUND-FIELDS`, `UI-PRIVACY-RAW-TEXT-EGRESS` reading zero | Model bonus, privacy boundary, architecture |
| 00:55-02:10 | 75s | One uninterrupted click starts the audited replay. The screen recording is uncut while lanes, persisted transitions, evidence, and audit update. | Let the system explain itself through motion: registry resolution, observation, candidate comparison, independent citation verification, deterministic policy, one simulated task. | `UI-GLOBAL-RUN-ID`, `UI-GLOBAL-TRACE-ID`, `UI-AGENT-STATE`, `UI-CLOUD-TRANSITIONS`, `UI-EVIDENCE-CANDIDATE`, `UI-CITATION-TOTAL`, `UI-CITATION-VERIFIED`, `UI-CITATION-STATUS`, `UI-POLICY-OUTCOME`, `UI-POLICY-REASONS`, `UI-TASK-COUNT-RUN` | Proof of action, delegation, state discipline, product demo |
| 02:10-02:55 | 45s | Second run with a fault fixture: one mismatched material citation and one forbidden tool request from the assessor. | Name the standard autonomous-agent failure, then show why Recall cannot take the unsafe path. | `UI-TOOL-DENIAL` with role, tool, and reason codes, `UI-CITATION-STATUS` incomplete, `UI-POLICY-OUTCOME` abstain, `UI-POLICY-MISSING`, `UI-TASK-COUNT-RUN` read back from the task ledger, `UI-WATCH-PENDING` retained | Hallucination recovery, strict separation, failure-tolerant routing |
| 02:55-03:20 | 25s | Week timeline and fleet board, then the managed-proof drawer and the matching cloud console view. | Durable monitoring without a running model process, and proof the backend is not a local mock. | `UI-WATCH-SCAN-COUNT`, `UI-WATCH-PENDING`, `UI-WATCH-ATTENTION`, `UI-CLOUD-RUNTIME-REV`, `UI-CLOUD-HEALTH`, correlated run and trace identifiers | Managed deployment, architecture, production readiness |
| 03:20-03:40 | 20s | Return to the contrast: the audited run produced one simulated task, the unsafe run produced none. Close on authority and limitations. | The specialist sees only audited candidates. Agents may reason; they cannot decide. | Derived counts with source links, `NON-CLINICAL RESEARCH PROTOTYPE`, exact `SYNTHETIC` plus `CAPTURED_REPLAY` composition, clinician final authority | Operational utility, derived presentation, trustworthy close |

Total runtime 220 seconds. The rehearsal ceiling is 230 seconds and the binding
maximum is 240 seconds.

## Conditional privacy segment

The 00:35-00:55 segment has three versions, selected only by the frozen P1 result:

| P1 result | Segment | Duration | Spoken claim |
|---|---|---:|---|
| Local model adds at least one incremental true positive and adds no accepted escape | Full version above | 20s | The local model found a residual identifier the rules missed; deterministic redaction and the outbound gate decided |
| Local model adds nothing, or the measurement did not run | Deterministic-only version: submit the note, show detections, redaction, outbound gate, and quarantine of a residual case | 12s | Rules detect, a deterministic allowlist decides, and anything unrecognised stays in the laboratory |
| Local model increases accepted escapes | Segment removed entirely | 0s | No local-model claim is spoken |

The segment version is chosen from the committed P1 manifest, never from a
rehearsal impression. Until that manifest exists, the deterministic-only version
is the default.

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

The fault button selects an input fixture, not an output. The fixture contains a
synthetic case reference, one captured replay reference, one deliberately
mismatched citation, and one forbidden tool request. The result is produced by
the normal controller, auditor, authorisation layer, and policy gate. The run
passes only if the denial and audit receipts exist and authoritative read-back
confirms that no task was created.

## Claim gates

- The phrase "before the classification changed" may appear only if RCL-205 and
  RCL-206 produce a source-attributed timeline and a frozen comparison protocol
  that verify it. Otherwise the bounded wording is "Recall found a new evidence
  signal while the captured classification snapshot stayed unchanged". If even
  that is unproven, the sentence is removed.
- No workload reduction, lead time, accuracy, privacy, or false-positive number
  is spoken until its evaluation artifact is frozen in the claim ledger.
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

Never cut the human friction, the uninterrupted live run, the independent audit,
the forbidden-action denial, the deterministic outcome, the cloud proof, the
data-mode labels, or the limitations statement.
