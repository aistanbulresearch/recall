# RCL-106 Termination Decision

- Decision: `DEC-2026-08-25-044`
- Status: `TERMINATED`
- Accepted by: owner
- Effective date: 2026-08-25

## Decision

The owner terminates RCL-106. The credential exposure was detected and
contained on 2026-08-22, and the repository and history secret scans recorded
for the task were clean. The credential value was not inspected, copied, or
stored as part of this decision.

## Rationale

The credential is shared by multiple owner workflows, and replacing it would
disrupt those workflows. The owner accepts the residual operational risk and
directs that the tracking item end rather than remain a recurring delivery
gate. This is an owner risk-acceptance decision after containment; it is not a
claim that the credential or every dependent workflow received technical
remediation.

## Boundary

This termination does not authorize a GitHub write, push, merge, publication,
credential disclosure, or use outside an otherwise approved workflow. A new
exposure, unauthorized use, or material change in the credential's scope opens
a new incident and requires a new owner decision.
