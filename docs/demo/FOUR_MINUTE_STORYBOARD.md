# Recall Four-Minute Demo Storyboard

- Status: verified design; execution evidence not yet available
- Tasks: RCL-207 and RCL-904
- Updated: 2026-08-15
- Target duration: 3 minutes 45 seconds
- Hard maximum: 4 minutes
- Language: English narration and English subtitles

This is the shot and evidence plan, not the final word-for-word script. RCL-904 writes and times the final English script only after the critical path exists.

## Demo thesis

Autonomous agents normally fail by turning plausible model output into action. Recall makes that structurally impossible: specialist agents can propose and audit evidence, but only deterministic policy can create a simulated review task from a complete, independently verified artifact set.

## Viewer contract

The video must remain understandable without genetics expertise. It must visibly state:

- all institutional records are synthetic;
- public evidence is either `CAPTURED_REPLAY` or separately labeled `LIVE_PUBLIC`;
- execution is live even when the evidence input is a captured replay;
- the contest build is a non-clinical research prototype;
- no AI classifies a variant, changes a report, contacts a patient, or creates a clinical decision;
- every result on screen comes from the exact run artifacts being shown.

## Timed storyboard

| Time | Duration | Screen and action | Narration objective | Visible proof | Score rows |
|---|---:|---|---|---|---|
| 00:00-00:15 | 15s | Open directly on the workload panel. One synthetic watch case is waiting; no logo animation or team introduction. | State the human friction: a specialist cannot repeatedly reopen every old uncertain result whenever public evidence changes. | `SYNTHETIC` badge, due-case state, last scan time, next scan time. All values resolve from the selected `WatchCase`. | Operational utility, Unlikely Hero, Demo clarity |
| 00:15-00:30 | 15s | Reveal the single-screen agent lanes and authority boundary. | One sentence: Recall continuously scans approved public evidence, independently audits every material claim, and lets deterministic policy decide whether a simulated review is allowed. | Four named roles, deterministic Controller, independent Auditor, Policy Gate, and forbidden direct path from agents to review queue. | Multi-agent complexity, strict separation |
| 00:30-00:50 | 20s | Submit a synthetic lab note. Deterministic detector runs, local Gemma proposes one residual span, deterministic outbound scan approves the minimized payload. | Show why Gemma is useful but not authoritative. | `PrivacyReceipt`, detector counts, Gemma residual count, outbound result, zero raw-text cloud fields. If Gemma has no measured incremental detection, this segment is removed rather than overstated. | Bonus, Architecture, privacy boundary |
| 00:50-02:05 | 75s | One uninterrupted click starts `Run audited replay`. Keep the screen recording uncut while the managed run updates agent lanes, Firestore-backed state, and the evidence panel. | Let the system explain itself through motion: Registry resolution, Watcher observation, Assessor proposal, independent citation verification, deterministic policy, one simulated task. | Exact Runtime and agent revisions, Registry receipt, live state transitions, captured public evidence label, citation verdicts, policy reason codes, one idempotent simulated `ReviewTask`, run ID and trace ID. | Proof of Action, delegation, managed discovery, state discipline, product demo |
| 02:05-02:55 | 50s | Start a second synthetic fault run using a fixture that includes a mismatched citation and an Assessor request for a forbidden task-creation tool. | State the standard autonomous-agent weakness, then show why Recall cannot take the unsafe path. | Tool authorization denial, independent citation refetch failure, `AUDIT_INCOMPLETE`, deterministic `ABSTAIN`, and explicit proof that no review task was created. | Hallucination recovery, strict separation, failure-tolerant routing, Demo |
| 02:55-03:25 | 30s | Open the managed-proof drawer, then briefly show the matching Google Cloud console/log view. | Prove the backend is not a local mock and connect each managed service to one visible control. | Cloud Run or Agent Runtime revision, Registry binding, Firestore transitions, sanitized trace, deployed URL, exact run/trace correlation. No credential, project identifier, or sensitive payload is shown. | Managed deployment, Architecture, production readiness |
| 03:25-03:45 | 20s | Return to the result comparison: audited run produced one simulated task; unsafe run produced none. End on the authority statement and limitations badge. | Close with the user and the structural contrast: the specialist sees only audited candidates; agents may reason, but they cannot decide. | Derived counts, linked source artifacts, `NON-CLINICAL RESEARCH PROTOTYPE`, `SYNTHETIC`, clinician final authority. | Operational utility, derived presentation, trustworthy close |

Target runtime is 225 seconds, leaving 15 seconds below the binding four-minute maximum for natural pauses and edit variance.

## Critical live path

The 00:50-02:05 segment is the primary unedited Proof of Action. It must show one real invocation of the deployed backend. The evidence source may be a frozen captured replay for reliability, but the controller, agent invocations, artifact writes, policy evaluation, database transitions, and UI updates must execute during recording.

The run is invalid as demo evidence if:

- a prerecorded video is played inside the UI;
- the UI advances from timers rather than authoritative state;
- a preset label directly determines the displayed outcome;
- a model or frontend writes the terminal result;
- the cloud view cannot be correlated to the same run and trace;
- any mode badge is missing or manually overlaid during editing.

## Fault-run contract

The fault button selects an input fixture, not an output. The fixture manifest contains:

- a synthetic case reference;
- one captured replay reference;
- one deliberately mismatched citation input;
- one forbidden tool request injected into the Assessor output;
- expected safety invariants, but no hard-coded terminal outcome.

The actual result is derived by the normal Controller, Citation Auditor, authorization layer, and Policy Gate. The run passes only if the denial and audit receipts exist and authoritative read-back confirms that no task was created.

## Historical lead-time claim gate

The phrase “before the classification changed” may appear only if RCL-205 and RCL-206 produce a source-attributed historical timeline and frozen comparison protocol that verify it. If that gate does not pass, the demo uses the bounded wording “Recall found a new evidence signal while the captured classification snapshot remained unchanged.” If even that statement is not proven, it is removed.

No numerical workload reduction, lead time, accuracy, privacy improvement, or false-positive claim is spoken until its evaluation artifact is frozen in the Claim Evidence Ledger.

## Required capture checklist

- Public YouTube or Vimeo video, no longer than four minutes.
- English narration or English subtitles; the plan requires both.
- Hosted application URL visible.
- Google Cloud deployment proof visible and correlated to the run.
- Architecture visible without leaving the critical story.
- One uninterrupted managed execution.
- One visibly blocked unsafe execution.
- Explicit data-mode and non-clinical labels in the captured frames.
- No third-party advertising or unauthorized logo usage.
- No credentials, account/project identifiers, raw prompts, chain-of-thought, or sensitive data.
- Every result-bearing frame audited against `DERIVED_VALUE_REGISTRY.md`.

## Cut rules

If time exceeds 3:50 during rehearsal, cut in this order:

1. shorten the privacy narration while preserving the receipt;
2. reduce the managed-proof drawer explanation while retaining Google Cloud visual proof;
3. remove non-critical architecture labels;
4. remove Gemma from the video if its incremental value is not measured.

Never cut the human friction, uninterrupted live run, independent audit, forbidden-action denial, deterministic outcome, cloud proof, data-mode labels, or limitations statement.
