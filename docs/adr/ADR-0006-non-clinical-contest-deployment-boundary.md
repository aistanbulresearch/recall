# ADR-0006: Non-clinical Contest Deployment Boundary

- Status: accepted
- Date: 2026-08-15
- Owners: Recall project
- Related tasks: RCL-102, RCL-104, RCL-201, RCL-804, RCL-906

## Context

Recall is designed around a real laboratory workflow problem, but the contest implementation uses Gemini and managed Google Cloud agent services. The current Google Cloud Service Specific Terms prohibit Generative AI Services for clinical purposes and state that these services are not designed to satisfy the customer's regulatory or legal obligations.

An anonymization or pseudonymization layer reduces privacy exposure but does not change the purpose for which a service is used. Therefore a de-identified clinical workflow cannot be assumed to be permitted merely because direct identifiers were removed.

## Decision

The hackathon build is a non-clinical research prototype.

- Institutional watch records are synthetic.
- Historical replay uses source-attributed public evidence.
- A separately labeled live smoke may query approved public sources.
- No real patient data is processed.
- No claim states or implies that the Gemini path is authorized, validated, or deployed for clinical production.
- `REVIEW_REQUIRED` remains a deterministic research workflow signal and any resulting `ReviewTask` is explicitly simulated. Neither is a reclassification, diagnosis, report amendment, patient notification, or medical recommendation.
- The laboratory integration design is a future target architecture, not a claim about the contest deployment.

A future clinical deployment requires a new approval gate covering the then-current provider contract, healthcare and regulatory restrictions, privacy law, data-processing terms, institutional authorization, security, validation, and human oversight. That gate cannot be satisfied by technical anonymization alone.

## Consequences

### Positive

- The contest remains eligible to demonstrate the architecture with synthetic and public data.
- Product claims align with the actual terms and evidence.
- The privacy layer can be measured honestly without implying regulatory clearance.

### Costs

- Public copy must say `non-clinical research prototype` where the deployment purpose could be misunderstood.
- Production clinical integration is explicitly out of current scope.
- Terms must be rechecked at feature freeze and before submission.

## Rejected alternatives

### Treat de-identification as sufficient authorization

Rejected. Purpose restrictions and data-identification controls answer different questions.

### Remove all laboratory framing

Rejected. The workflow problem and intended future user remain central, but the implemented deployment boundary must be accurate.

### Ignore the restriction because the system is decision support

Rejected. Current terms refer broadly to clinical purposes, not only autonomous diagnosis.

## Failure modes and controls

| Failure | Control |
|---|---|
| Real or patient-derived data enters a contest run | Input allowlist, synthetic-data manifest, privacy gate, and immediate stop/quarantine. |
| Demo language implies clinical deployment | Claim ledger and RCL-906 wording audit fail. |
| A model output becomes a clinical decision | Authority tests deny the transition; only deterministic policy emits workflow outcomes, and clinicians retain final authority. |
| Terms change before submission | Scheduled source recheck; reopen ADR and deployment gate. |
| Future team assumes anonymization resolves provider terms | Architecture and deployment runbook cite this ADR and require separate approval. |

## Verification

- Every run artifact and screen carries an explicit data mode.
- Public demo copy contains a visible non-clinical research-prototype statement.
- Every contest `ReviewTask` surface is visibly labeled as a synthetic simulation and has no production routing integration.
- Test fixtures prove no real-data mode exists in the contest input contract.
- Claim audit contains no clinical-production, diagnosis, reclassification, or regulatory-clearance claim.
- Feature-freeze evidence records the date and hash or snapshot reference for the controlling terms.
