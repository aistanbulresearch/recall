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
| Citation Auditor | Matching PMID/claim verifies | One fake, wrong-title, or unsupported material claim among valid claims | Independent refetch, rejected claim ID, exact lexical reason set | Current assessment becomes `ABSTAIN`; rejected claim cannot be dropped to rescue it; zero task | planned |
| Deterministic candidate normalizer | BRCA2 `c.7522G>C` matches exact allele, frozen GEO row, scope, complete snapshot, and new hash | Same-gene controls receive the same source event or Assessor says "not material" | `CandidateDeltaReceipt` and activation counters | Controls cannot invoke Assessor/Auditor; Assessor cannot suppress a real candidate or select `NO_ACTION` | planned |
| Counter-evidence check | Balanced evidence set passes | Material counter-evidence omitted | Audit-incomplete reason | No trusted recommendation | planned |
| Policy Gate | Complete verified artifact set produces expected truth-table result | Multiple failed or not-evaluated facts | Every applicable reason exactly once in lexical order | No model-created terminal state and no missing-equals-false collapse | planned |
| Idempotency | One event creates one run/task | Same event delivered repeatedly | Existing idempotency record returned | No duplicate task | planned |
| WatchCase scheduler and lease | Active due case creates one bounded run | Paused/closed case, expired lease, crash, or stale writer | Schedule, lease, resume, and compare-and-set receipts | No parallel stale run changes authoritative state | planned |
| Memory admission gate | Scoped operational hint is admitted and expires | Poisoned fact, clinical claim, cross-tenant entry, stale contradiction | Admission/rejection reason, scope, TTL, source hash | Memory never satisfies evidence, audit, policy, or transition prerequisites | planned |
| Memory retrieval boundary | Admitted hint informs an agent proposal | Memory Bank unavailable or returns conflicting context | Retrieval/rejection receipt plus memory-on/off comparison | Policy bytes and task count do not change when authoritative artifacts are identical | planned |
| Untrusted-source content gate | Benign structured source passes | Prompt injection, malicious instruction, Model Armor outage | Model Armor or structured-only fallback activation receipt | Raw hostile prose cannot reach agent tool authority | planned |
| Data-mode gate | Atomic modes form registered synthetic-plus-replay composition | Missing mode/set, replay labeled live, mock plus product, or live-public inside replay | `DataModeReceipt.mode_set`, composition, and schema/UI assertion | No unlabeled or disallowed composition reaches demo build | planned |
| WatchCase cursor gate | Verified `NO_ACTION` or `REVIEW_REQUIRED` advances exact audited snapshot | `ABSTAIN`, `HALTED`, or duplicate suppression with pending evidence | Cursor/backlog/attention read-back before and after recovery | Unaudited observation hash is not consumed and is observed again after recovery | planned |
| Replay capture integrity | Ten declared public-source captures verify offline | One captured byte is mutated or a manifest path escapes the capture root | Exact byte/hash, semantic-anchor, chronology, exact-row, and path-boundary checks | Corrupted or out-of-root evidence cannot enter replay evaluation | verified for source package; product route not implemented |
| Derived UI values | Backend artifact renders expected values | Artifact changes, required field missing, or fixture name changes independently | `docs/demo/DERIVED_VALUE_REGISTRY.md` plus UI-source path and automated assertion | No stale, default-clean, timer-driven, or preset-derived result remains | planned |

## Verification rule

Each verified row must link to the test, run manifest, trace or activation record, authoritative state read-back, and UI capture where relevant.

Replay capture integrity evidence: `scripts/evidence/verify-rcl-205-captures.ps1`, `scripts/evidence/test-rcl-205-captures.ps1`, `docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json`, and `docs/evaluation/reports/2026-08-17--rcl-205-protocol-1.0.1-verification.md`.
