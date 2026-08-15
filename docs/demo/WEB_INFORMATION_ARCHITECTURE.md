# Recall Web Information Architecture

- Status: verified design; implementation not started
- Task: RCL-207
- Updated: 2026-08-15

## Design objective

The product and demo share one evidence surface. The jury should not need to navigate a clinical dashboard or infer architecture from narration. One primary screen must show the human workload, multi-agent execution, independent audit, deterministic authority, failure recovery, and resulting simulated review queue.

## Route map

| Route | Purpose | Demo use | Authority source |
|---|---|---|---|
| `/` | Workload-first introduction, non-clinical boundary, and entry to the demo | Opening only if it can reach `/demo` in one action | Static product copy plus deployment metadata |
| `/demo` | Primary Mission Control for synthetic runs and captured replay | Main four-minute surface | Authoritative API view model assembled from typed artifacts |
| `/runs/{run_id}` | Stable deep link to one run, receipts, source lineage, and trace | Used for audit and post-video judging | Firestore ledger and immutable artifact references |
| `/architecture` | Full trust zones, agent responsibilities, managed components, and failure contracts | Supporting documentation, not required during the live run | Versioned architecture manifest and deployment inventory |
| `/evidence` | Claim, score, guardrail, and demo evidence index | Supporting proof for judges and auditor | Committed evidence ledgers and artifact manifests |
| `/limitations` | Non-clinical scope, synthetic-data policy, unverified claims, and known service limits | Linked from every result page | Versioned release limitations artifact |

The public application is read-only except for explicitly labeled synthetic demo controls. No route accepts real patient data.

## Primary `/demo` layout

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Recall | NON-CLINICAL RESEARCH PROTOTYPE | SYNTHETIC / CAPTURED_REPLAY     │
│ Run: <derived>  Trace: <derived>  Cloud revision: <derived>  Health: <derived>│
├───────────────────┬───────────────────────────────────┬──────────────────────┤
│ WATCHCASE         │ LIVE AGENT LANES                  │ SAFETY & AUTHORITY   │
│                   │                                   │                      │
│ Due/last/next     │ Controller state timeline         │ PrivacyReceipt       │
│ scan, all derived │ Coordinator → route proposal      │ Registry receipt      │
│                   │ Watcher → observations            │ Tool denial receipt   │
│ Week timeline     │ Assessor → evidence delta         │ Citation audit        │
│ with separate     │ Auditor → independent verdicts    │ Policy reason codes   │
│ ScanRuns          │                                   │                      │
├───────────────────┴───────────────────────────────────┼──────────────────────┤
│ EVIDENCE BEFORE / AFTER                               │ SIMULATED REVIEW     │
│ source snapshots, claims, citations, counter-evidence│ QUEUE                │
│ and artifact links                                   │ derived task count   │
├───────────────────────────────────────────────────────┴──────────────────────┤
│ [Run audited replay] [Inject mismatched citation + forbidden tool request]   │
│ Fixture selection changes inputs only. Outcomes are never preset.            │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Interaction model

### Run audited replay

1. The user selects a source-attributed captured replay fixture.
2. The UI displays the fixture ID and data mode before execution.
3. The backend creates a new `ScanRun`; the UI follows authoritative state events.
4. The UI never predicts the next state or advances on a timer.
5. On completion, the result panel renders the deterministic `PolicyDecision` and any simulated `ReviewTask` read back from Firestore.

### Inject fault

1. The user selects a synthetic fault fixture containing a mismatched citation and forbidden tool request.
2. The same production code path executes.
3. Safety receipts appear at the exact step that activated them.
4. The UI proves downstream absence by querying the authoritative task ledger, not by displaying a success toast.

### Inspect lineage

Every result-bearing value has an adjacent or expandable source control. Selecting it reveals:

- artifact type and ID;
- JSON path or deterministic derivation;
- content hash;
- producer and version;
- data mode;
- creation time;
- run and trace correlation.

## Visual priority

1. Human workload and current case state.
2. Live transition through distinct agent lanes.
3. Safety activation and deterministic terminal result.
4. Evidence and citation details.
5. Managed infrastructure metadata.

Agent cards are not decorative. A card is visible only when its exact version is resolved for the run, and its allowed tool scope is accessible from the card.

## State presentation rules

- `UNKNOWN`, `UNAVAILABLE`, `INCOMPLETE`, `ABSTAIN`, technical `HALTED`, and `DENIED` are distinct visual states.
- Missing data never renders as zero, clean, safe, or passed.
- A replay never renders as live.
- A simulated task never renders as a clinical task.
- An agent proposal never uses the same visual treatment as a verified audit or policy decision.
- Color is redundant with text, icon, and reason code.
- The timeline renders only persisted state transitions.
- Stale UI data displays its source timestamp and a visible stale warning.

## Demo durability

- The selected run has a stable deep link.
- A browser refresh reconstructs the page from authoritative artifacts.
- WebSocket or stream loss falls back to polling without inventing states.
- If managed services are unavailable, the UI shows the typed failure receipt; it does not silently switch to a mock.
- If Policy Gate or ledger integrity is unavailable, the UI shows technical `HALTED`; it never relabels the condition as a Policy Gate `ABSTAIN`.
- A captured replay supports deterministic source input but does not bypass live backend execution.
- The demo controls remain available only for allowlisted synthetic fixtures.

## Accessibility and non-specialist language

- Lead with “specialist review queue,” not ACMG terminology.
- Translate `ABSTAIN` on first use as “Recall stopped because required proof was incomplete.”
- Explain citation audit as “a second agent independently reopened every source.”
- Keep raw genomic notation secondary to the plain-language evidence event.
- Provide keyboard operation, focus visibility, sufficient contrast, captions, and reduced-motion behavior.

## Implementation acceptance criteria

The web shell is incomplete until:

1. all result fields are registered in `DERIVED_VALUE_REGISTRY.md`;
2. fixture controls select inputs and cannot choose outcomes;
3. refresh reproduces the same state from authoritative read-back;
4. missing-field tests render explicit unknown states;
5. one success and one fault run are screen-recordable without developer tools;
6. the matching Cloud run and trace are reachable from the same screen;
7. every simulated and replayed element is labeled in the captured frame.
