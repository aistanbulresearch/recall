# Demo Evidence Log

Append evidence at the moment it is produced. Do not rely on recreating a transient result near submission.

| Evidence ID | Date | Demo moment | Criterion | Mode | Run/artifact | Capture | Status | Limitations |
|---|---|---|---|---|---|---|---|---|
| DEMO-001 | TBD | Gemma catches a residual identifier and cloud payload stays clean | Bonus, Demo | Synthetic | TBD | TBD | planned | Metrics not established |
| DEMO-002 | TBD | Coordinator discovers approved agent versions | Innovation, Architecture | Synthetic/replay | TBD | TBD | planned | Platform access unverified |
| DEMO-003 | 2026-08-17 | Historical evidence delta appears before classification change | Innovation | Captured public replay | Frozen source package and offline verifier; product execution TBD | `docs/evaluation/reports/2026-08-17--rcl-205-protocol-1.0.1-verification.md` | source package verified; demo planned | Ten captures, chronology, exact row, mutation rejection, and path rejection verified; product route not executed |
| DEMO-004 | TBD | Auditor rejects a fake or mismatched citation | Architecture | Fault injection | TBD | TBD | planned | Auditor not implemented |
| DEMO-005 | TBD | Actual failed/not-evaluated facts produce lexical reasons, `ABSTAIN`, preserved pending evidence, and no simulated task | Architecture, Demo | Fault injection | TBD | TBD | planned | Policy path absent |
| DEMO-006 | TBD | Valid audited change creates exactly one simulated review task | Demo | Synthetic plus captured replay | TBD | TBD | planned | End-to-end path absent |
| DEMO-007 | TBD | One durable WatchCase shows separately receipted Week 0, Week 3, and Week 6 scans | Innovation, Fleet, Demo | Synthetic plus captured replay | TBD | TBD | planned | Lifecycle and scheduler absent |
| DEMO-008 | TBD | Poisoned or contradictory memory is rejected and Firestore remains authoritative | Architecture, Fleet | Fault injection | TBD | TBD | planned | Memory access and admission gate absent |
| DEMO-009 | TBD | Untrusted source instruction is blocked or forces structured-only fallback/`ABSTAIN` | Architecture, Fleet | Fault injection | TBD | TBD | planned | Model Armor access and fallback absent |
| DEMO-010 | TBD | Registry resolves exact agent revisions and a forbidden tool call is denied | Architecture, Fleet | Synthetic/replay | TBD | TBD | planned | Registry, IAM, and Gateway path absent |
| DEMO-011 | TBD | Cloud evidence shows Runtime revision, Registry, Memory receipt, Firestore states, and sanitized trace | Demo, Fleet | Managed cloud | TBD | TBD | planned | Platform not smoke-tested |
| DEMO-012 | TBD | All screens visibly show synthetic, captured replay, live public, or mock mode from artifacts | Demo | Mixed, explicitly labeled | TBD | TBD | planned | Data-mode contract absent |

## Capture requirements

- exact commit and deployed revision;
- exact run ID;
- atomic data modes, run `mode_set`, and declared composition;
- source artifact hashes;
- screen recording or screenshot path;
- criterion supported;
- known limitations;
- confirmation that displayed values were derived, not entered manually.
- confirmation that accelerated Week labels and every non-live data mode were explicit in the captured frame.

## Storyboard mapping

| Storyboard time | Planned evidence IDs | Required mechanism |
|---|---|---|
| 00:00-00:30 | DEMO-007, DEMO-012 | Derived synthetic WatchCase state, separate scan history, workload-first framing, and explicit mode labels |
| 00:30-00:50 | DEMO-001, DEMO-012 | Measured local Gemma contribution plus deterministic outbound approval; remove segment if incremental value is unverified |
| 00:50-02:05 | DEMO-002, DEMO-003, DEMO-006, DEMO-010, DEMO-011, DEMO-012 | One uninterrupted managed run through Registry, agents, Firestore, independent audit, policy, and one simulated task |
| 02:05-02:55 | DEMO-004, DEMO-005, DEMO-010, DEMO-012 | Forbidden tool denial, mismatched citation rejection, deterministic `ABSTAIN`, and authoritative proof of zero task creation |
| 02:55-03:25 | DEMO-011 | Matching Google Cloud revision, database transitions, trace, and hosted URL correlated to the same run |
| 03:25-03:45 | DEMO-005, DEMO-006, DEMO-012 | Derived success/fault comparison, non-clinical boundary, and clinician authority |

DEMO-008 and DEMO-009 remain supporting architecture evidence. They enter the four-minute video only if they replace, rather than extend, another proof moment.

Design sources: `docs/demo/FOUR_MINUTE_STORYBOARD.md`, `docs/demo/WEB_INFORMATION_ARCHITECTURE.md`, and `docs/demo/DERIVED_VALUE_REGISTRY.md`.
