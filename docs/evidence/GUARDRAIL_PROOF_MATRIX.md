# Guardrail Proof Matrix

This matrix prevents green-but-dead verification. A guardrail is not proven merely because the final state looks safe.

| Guardrail | Positive control | Fault injection | Activation proof | Forbidden downstream assertion | Status |
|---|---|---|---|---|---|
| Privacy outbound gate | Clean structured payload passes | Seeded direct identifier remains after first pass | Detector/outbound-scan activation receipt | No Pub/Sub event for rejected payload | planned |
| Gemma residual detector | Semantic identifier span is returned | Invalid JSON, timeout, unavailable model | Model invocation and schema-validation receipt | Free text does not leave lab on failure | planned |
| Route validator | Allowlisted typed route accepted | Forbidden specialist/tool/version | Route rejection reason and selected fallback | Forbidden endpoint never invoked | planned |
| Registry resolution gate | Healthy approved version resolves | Stale, unbound, wrong-region, or forbidden revision | `RegistryResolutionReceipt` and validation reason | Unvalidated revision never invoked | planned |
| Identity and tool authorization | Allowed role uses one permitted tool | Role attempts forbidden tool or credential escalation | `ToolAuthorizationReceipt` with service identity and denial | No alternate endpoint or credential fallback | planned |
| Loop detector | Distinct state progression completes | Repeated identical state hash | `loop_detected` receipt and hop count | No further agent invocation or task | planned |
| Citation Auditor | Matching PMID/claim verifies | Fake PMID, wrong title, unsupported claim | Independent refetch and claim verdict | Incomplete audit cannot reach review task | planned |
| Exact evidence attribution | BRCA2 `c.7522G>C` matches the frozen exact GEO row and source scope | Same-gene `c.425+3A>G` and `c.1315T>G` controls receive the same source event | Normalized allele-match and scope-check receipts | Gene-only or out-of-scope match cannot create a material delta or task | planned |
| Counter-evidence check | Balanced evidence set passes | Material counter-evidence omitted | Audit-incomplete reason | No trusted recommendation | planned |
| Policy Gate | Complete verified artifact set produces expected truth-table result | Missing receipt or schema failure | Deterministic reason codes | No model-created terminal state | planned |
| Idempotency | One event creates one run/task | Same event delivered repeatedly | Existing idempotency record returned | No duplicate task | planned |
| WatchCase scheduler and lease | Active due case creates one bounded run | Paused/closed case, expired lease, crash, or stale writer | Schedule, lease, resume, and compare-and-set receipts | No parallel stale run changes authoritative state | planned |
| Memory admission gate | Scoped operational hint is admitted and expires | Poisoned fact, clinical claim, cross-tenant entry, stale contradiction | Admission/rejection reason, scope, TTL, source hash | Memory never satisfies evidence, audit, policy, or transition prerequisites | planned |
| Memory retrieval boundary | Admitted hint informs an agent proposal | Memory Bank unavailable or returns conflicting context | Retrieval or degraded receipt linked to proposal | Policy outcome does not change when authoritative artifacts are identical | planned |
| Untrusted-source content gate | Benign structured source passes | Prompt injection, malicious instruction, Model Armor outage | Model Armor or structured-only fallback activation receipt | Raw hostile prose cannot reach agent tool authority | planned |
| Data-mode gate | Valid mode propagates from connector to UI | Missing mode, replay labeled live, cached fallback without mode change | `DataModeReceipt` and schema/UI assertion | No unlabeled artifact or screen reaches demo build | planned |
| Derived UI values | Backend artifact renders expected values | Artifact changes, required field missing, or fixture name changes independently | `docs/demo/DERIVED_VALUE_REGISTRY.md` plus UI-source path and automated assertion | No stale, default-clean, timer-driven, or preset-derived result remains | planned |

## Verification rule

Each verified row must link to the test, run manifest, trace or activation record, authoritative state read-back, and UI capture where relevant.
