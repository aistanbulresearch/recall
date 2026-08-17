# Contest Score Matrix

Blank evidence cells represent work, not assumed credit.

| Criterion | Weight | Planned visible proof | Artifact path | Status | Gap |
|---|---:|---|---|---|---|
| Genuine multi-agent complexity | Innovation 40% | Four roles solve conflicting responsibilities and Coordinator selects a bounded route | `docs/security/THREAT_MODEL.md`; `docs/contracts/ARTIFACT_CONTRACTS.md`; execution TBD | planned | Design fixed; no implementation |
| Operational utility | Innovation 40% | Historical evidence signal reduces the cases a specialist must manually reopen | `docs/evaluation/EVALUATION_PROTOCOLS.md`; `docs/evaluation/HISTORICAL_REPLAY_CASE.md`; source manifest; protocol 1.0.1 verification report | source package verified; product proof planned | Positive and two controls plus exact captures are frozen; product route and workload metric not executed |
| Unlikely hero | Innovation 40% | Explain specialist backlog in plain language and show one review task | TBD | planned | Non-specialist UX not built |
| Weeks-long institutional continuity | Innovation 40%, Fleet | One `WatchCase` produces separately receipted Week 0, Week 3, and Week 6 `ScanRun` units without a long-running model process | `docs/contracts/LIFECYCLE_STATE_MACHINES.md`; execution TBD | planned | Lifecycle design fixed; scheduler absent |
| Strict responsibility separation | Architecture 30% | Agent catalog, distinct tool scopes, and denied action | `docs/security/THREAT_MODEL.md`; `docs/demo/FOUR_MINUTE_STORYBOARD.md`; execution TBD | planned | Design fixed; IAM and denial test absent |
| Fault-tolerant routing | Architecture 30% | Invalid route repair, loop termination, timeout/retry receipts | `docs/contracts/LIFECYCLE_STATE_MACHINES.md`; `docs/evaluation/EVALUATION_PROTOCOLS.md`; execution TBD | planned | Contracts fixed; Controller absent |
| Hallucination recovery | Architecture 30% | Mismatched citation rejected by independent Auditor and task withheld if audit is incomplete | `docs/security/THREAT_MODEL.md`; `docs/evaluation/EVALUATION_PROTOCOLS.md`; `docs/demo/FOUR_MINUTE_STORYBOARD.md`; execution TBD | planned | Design fixed; Auditor absent |
| Deterministic authority | Architecture 30% | Same artifacts produce same policy outcome; agents cannot emit terminal states | `docs/policy/DETERMINISTIC_POLICY_SPEC.md`; execution TBD | planned | Truth table fixed; Policy Gate absent |
| Memory authority and poisoning recovery | Architecture 30%, Fleet | Poisoned or contradictory Memory Bank entry is rejected; PolicyDecision bytes and task count match memory-disabled execution | `docs/security/THREAT_MODEL.md`; `docs/evaluation/EVALUATION_PROTOCOLS.md`; execution TBD | planned | Corrected design fixed; Memory access and gate absent |
| Managed discovery and identity | Architecture 30%, Fleet | Registry resolves an exact revision; Controller validates it; allowed and denied tool calls use distinct identities | TBD | planned | Platform not smoke-tested |
| Managed deployment | Demo 30% | Agent Runtime revision, Registry entries, cloud state, and one sanitized trace | `docs/demo/FOUR_MINUTE_STORYBOARD.md`; execution TBD | planned | Visible proof fixed; platform not smoke-tested |
| Product demo | Demo 30% | 3:45 workload-to-simulated-task flow with uninterrupted success and fault runs | `docs/demo/FOUR_MINUTE_STORYBOARD.md`; execution TBD | planned | Storyboard verified; web app absent |
| Derived presentation | Demo 30% | UI value audit proves every result comes from run artifacts | `docs/demo/DERIVED_VALUE_REGISTRY.md`; execution TBD | planned | Registry verified as design; implementation absent |
| Data-mode authenticity | Demo 30% | Atomic modes and the exact run composition visibly distinguish synthetic, replay, live public, and mock provenance without scalar collapse | `docs/demo/WEB_INFORMATION_ARCHITECTURE.md`; execution TBD | planned | Corrected presentation contract fixed; schemas and UI absent |
| Local Gemma contribution | Bonus upside | Residual identifier found beyond deterministic baseline | `docs/evaluation/EVALUATION_PROTOCOLS.md`; execution TBD | planned | Protocol frozen; benchmark absent |
| Model Armor contribution | Platform upside | Untrusted source injection is blocked or a typed structured-only fallback/`ABSTAIN` occurs | TBD | planned | Access and test corpus absent |

## Rule

A row becomes `verified` only when its artifact exists, can be reproduced, and proves that the target mechanism actually ran.
