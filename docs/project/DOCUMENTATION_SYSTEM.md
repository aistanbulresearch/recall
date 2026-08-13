# Documentation System

## Objective

The repository must allow a new owner, reviewer, auditor, or contributor to reconstruct what was intended, what was attempted, what actually ran, what failed, what changed, and what evidence supports every claim.

## Sources of truth

| Question | Canonical file |
|---|---|
| What are we building and in what order? | `docs/project/MASTER_PLAN.md` |
| Where are we right now? | `docs/project/STATUS.md` |
| How can another contributor continue? | `docs/project/HANDOFF.md` |
| Why was an architectural or scope choice made? | `docs/project/DECISION_LOG.md` and `docs/adr/` |
| What work happened? | `docs/project/WORK_LOG.md` |
| What failed and how was it handled? | `docs/project/ERROR_LOG.md` |
| What does the architecture permit? | `docs/architecture/TARGET_ARCHITECTURE.md` |
| Which judging criterion has proof? | `docs/evidence/SCORE_MATRIX.md` |
| Which product claim has evidence? | `docs/evidence/CLAIM_EVIDENCE_LEDGER.md` |
| Which guardrail was actually triggered? | `docs/evidence/GUARDRAIL_PROOF_MATRIX.md` |
| What can be shown in the video? | `docs/evidence/DEMO_EVIDENCE_LOG.md` |

## Record types

### Canonical, editable documents

`MASTER_PLAN`, `STATUS`, `HANDOFF`, architecture specifications, runbooks, and evaluation protocols represent the latest accepted state. Changes must be described in the Work Log and, when they alter a decision, the Decision Log.

### Append-only ledgers

`WORK_LOG`, `ERROR_LOG`, `DECISION_LOG`, and evidence ledgers preserve history. Correct an old entry by adding a new superseding entry rather than silently rewriting the event.

### Architecture decision records

Use `docs/adr/ADR-NNNN-short-title.md` for decisions that affect authority, trust boundaries, data contracts, deployment, security, scientific interpretation, or substantial scope.

Each ADR includes context, options, decision, consequences, failure modes, verification, and supersession status.

### Generated evidence

Machine-produced test, metric, trace, and demo artifacts belong under `artifacts/evidence/<run-id>/`. Each committed evidence directory requires a manifest with:

- run ID and UTC timestamp;
- source revision;
- configuration and dependency lock hash;
- data classification and synthetic/replay/live label;
- commands executed;
- exit status;
- artifact hashes;
- limitations.

Raw sensitive output and local-only traces are never committed.

## Required update transaction

For every substantive work unit:

1. Assign or reference a master-plan task ID.
2. State acceptance criteria before implementation.
3. Record commands, files, and verification in the Work Log.
4. Record every material failure or abandoned attempt in the Error Log.
5. Update evidence ledgers with paths, not unsupported prose.
6. Update `STATUS.md` and `HANDOFF.md` before ending the work unit.
7. Update the master plan when status, scope, order, dates, or dependencies changed.

## Status vocabulary

- `not-started`: no implementation or verified artifact exists.
- `in-progress`: active work exists but acceptance criteria are not met.
- `blocked`: a named dependency prevents progress.
- `implemented`: code exists and local tests pass.
- `deployed`: a named revision is running in the target environment.
- `verified`: the preregistered acceptance gate passed with an artifact.
- `validated`: an explicitly defined scientific or clinical validation protocol passed. This term must not be used as a synonym for tested.
- `cut`: removed from contest scope with a recorded decision.

## Audit rules

- An accepted API write is not proof of correct read-back.
- A zero-finding report is not proof that the scanner received analyzable input.
- A UI status is not proof of backend state unless derived from the authoritative artifact.
- A document or graph node is not proof of executable implementation.
- A mock or replay is evidence only for the behavior it actually exercises and must be labeled.
- Every numerical claim must point to a reproducible artifact and calculation.
