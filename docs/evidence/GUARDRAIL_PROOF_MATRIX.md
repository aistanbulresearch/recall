# Guardrail Proof Matrix

This matrix prevents green-but-dead verification. A guardrail is not proven merely because the final state looks safe.

| Guardrail | Positive control | Fault injection | Activation proof | Forbidden downstream assertion | Status |
|---|---|---|---|---|---|
| Privacy outbound gate | Clean structured payload passes | Seeded direct identifier remains after first pass | Detector/outbound-scan activation receipt | No Pub/Sub event for rejected payload | planned |
| Gemma residual detector | Semantic identifier span is returned | Invalid JSON, timeout, unavailable model | Model invocation and schema-validation receipt | Free text does not leave lab on failure | planned |
| Route validator | Allowlisted typed route accepted | Forbidden specialist/tool/version | Route rejection reason and selected fallback | Forbidden endpoint never invoked | planned |
| Loop detector | Distinct state progression completes | Repeated identical state hash | `loop_detected` receipt and hop count | No further agent invocation or task | planned |
| Citation Auditor | Matching PMID/claim verifies | Fake PMID, wrong title, unsupported claim | Independent refetch and claim verdict | Incomplete audit cannot reach review task | planned |
| Counter-evidence check | Balanced evidence set passes | Material counter-evidence omitted | Audit-incomplete reason | No trusted recommendation | planned |
| Policy Gate | Complete verified artifact set produces expected truth-table result | Missing receipt or schema failure | Deterministic reason codes | No model-created terminal state | planned |
| Idempotency | One event creates one run/task | Same event delivered repeatedly | Existing idempotency record returned | No duplicate task | planned |
| Derived UI values | Backend artifact renders expected values | Artifact value changes between runs | UI-source path and automated assertion | No stale or preset label remains | planned |

## Verification rule

Each verified row must link to the test, run manifest, trace or activation record, authoritative state read-back, and UI capture where relevant.
