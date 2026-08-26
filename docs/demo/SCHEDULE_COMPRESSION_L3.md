# Schedule compression, L3 lane record

- Status: directive received 2026-08-26, DEC-0XX (owner-accepted text relayed by
  the director); this file records the L3-relevant portion and this lane's
  Step-0 answers.
- Decision: all remaining monitoring cycles run today in one supervised
  accelerated session; the 16:00Z daily trigger is disabled (not deleted); one
  post-freeze verification tick is scheduled against the frozen deployment
  revision; the 29th/30th queue days are withdrawn from all claims.
- Lane: L3. Updated: 2026-08-26.

## Step-0 answers (L3)

**"Supervised accelerated schedule" label on the board: applicable, on one
condition.** The panel renders no run-specific fact that is not derived from an
artifact field (derived-value registry rule), so the label must ride on data,
not on copy typed into a component. The cleanest carrier is the manifest the
session emits: either `trigger_code` distinguishing the compressed session from
`COHORT_DAY_MANAGED`, or an explicit schedule-mode field, or the DEC reference.
Whichever field Codex's design carries, the panel maps it to the exact wording
"supervised accelerated schedule". If no field carries it, the label cannot
appear on the derived surface without violating the registry rule; it would
then belong only to static narrative copy, which is a weaker claim. Raised
with the director as the one L3 requirement on the session's contract.

**VCV-anchored cases: panel side ready, tested, in the registry.**
`SYNTHETIC_WITH_CAPTURED_REPLAY` renders per-case with its own copy; every
rendered VCV resolves in one step to `capture_path` + `sha256`; an unanchored
VCV is marked, never shown bare; the contract enforces `vcv null iff
SYNTHETIC_ONLY`, and the tests exercise the producer's real example including
its live anchor row. Registry doc rows added 2026-08-26 (commit 92f0b88).
Whether the capture files and mode declarations exist on the producing side is
L2/L1's half of the answer.

## What compression does to this panel, by design

- The elapsed-days sentence is **correctly withheld** for a compressed
  session: several cycles share a calendar date, so the panel renders
  "N daily cycles recorded" plus the reason. This is not a defect to fix; it
  is the guard doing exactly what it was built for. The claim "the program ran
  as N distinct days" is not available, and the surface will not make it.
- What the panel CAN prove for the session, from `execution_history` +
  `delta`: N cycles ran, each cycle's selection matched its prediction
  (`prediction_match`), counts by identity, totals agreeing with the rows they
  derive from. That is the compressed narrative's actual evidence shape.
- The label (above) is the only addition, and only from data.

## Withdrawn claim

Previously stated to the director (2026-08-26 12:45): queue cases due on the
29th/30th mean the operation ticks past freeze and submission. **Withdrawn per
DEC-0XX**: those queue days are removed from all claims. The panel never
hardcoded the claim, so no code changes; the record is corrected here.

## Schedule impacts on L3 commitments

- The "first real manifest after the 16:00Z tick" check becomes "first real
  manifest emitted by the compression session". Tooling is path-agnostic:
  `REAL_MANIFEST=<path> pnpm vitest run tests/real_manifest.test.ts`.
- The 27th rebind commitment (new schema version, 12-pin removal) moves to
  TODAY if the expansion is included in the session, because the expansion
  requires the new version before prediction table v2. Confirmed direction
  with the director; same drill as the 2.1.0 rebind: read the shipped parser,
  allowlist, byte-bound fixtures, compatibility confirmation.
- Version-scoped validation requirement stands and gains force under
  compression: day-4-style manifests carry earlier rows in their history, and
  each row must be validated against its own day's declaration, not the
  manifest's current one.
