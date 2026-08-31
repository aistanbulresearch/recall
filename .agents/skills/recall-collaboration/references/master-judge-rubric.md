# Recall Master Judge Rubric

## Evidence protocol

The judge must independently inspect the exact source, diff, tests, raw logs, and artifacts in scope. Agent reports, documentation claims, accepted writes, and green test labels are navigation aids only.

Classify every material claim as one of:

- `SPECIFIED`: written design or acceptance intent only.
- `IMPLEMENTED`: executable behavior exists but has not been independently run.
- `EXECUTED`: the relevant verification ran against the stated checkout or artifact.
- `EXTERNALLY_ACCEPTED`: a remote or cloud write was read back from the target system.
- `MECHANISM_PROVED`: activation and forbidden-downstream checks independently prove the claimed mechanism.
- `NOT_VERIFIED`: evidence is missing, stale, ambiguous, or outside the inspected boundary.

## Review dimensions

1. Scope and ownership: no unauthorized expansion, overlapping writes, or unowned mutation.
2. Authority boundaries: LLM and agent outputs cannot become deterministic, clinical, notification, or terminal authority.
3. Failure behavior: missing data, timeouts, loops, malformed output, and unavailable dependencies fail loudly and within budget.
4. Privacy and security: no real patient data, secret, raw identifier, or prohibited payload crosses its boundary.
5. Scientific validity: provenance, counter-evidence, uncertainty, mode labeling, and claim limits remain exact.
6. Evidence integrity: every displayed result is derived from the exact artifact and the tested mechanism actually ran.
7. Reliability: retries, idempotency, duplicate suppression, recovery, and state transitions match the contracts.
8. Eligibility and authorship: contest and owner-only repository constraints remain satisfied.
9. Documentation truth: status, plan, handoff, logs, and evidence boundaries match the inspected state.

## Verdicts

- `PASS`: all in-scope acceptance criteria are independently supported; no required change remains.
- `PASS WITH REQUIRED CHANGES`: the core gate is sound, but explicitly listed changes must be completed before the next protected action.
- `FAIL`: a material acceptance, safety, correctness, or evidence requirement is violated.
- `BLOCKED`: required evidence or access is unavailable and no honest verdict can be reached.
- `NOT VERIFIED`: the claimed behavior lies outside the inspected evidence boundary.

The report must list scope, exact checkout or artifact identity, commands and files inspected, findings ordered by severity, evidence classifications, verdict, required next action, and residual unverified boundaries. The judge must not edit files, repair findings, approve owner actions, or rely on another agent's verdict.
