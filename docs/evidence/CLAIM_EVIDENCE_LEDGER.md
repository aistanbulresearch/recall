# Claim Evidence Ledger

No submission, README, UI, or video claim is approved until its evidence path is populated.

| Claim ID | Proposed claim | Evidence required | Artifact | Status | Approved wording |
|---|---|---|---|---|---|
| CLM-001 | Recall detects evidence changes before a classification-only monitor | Source-attributed historical timeline and frozen comparison protocol | `docs/evaluation/HISTORICAL_REPLAY_CASE.md`; `docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json`; source-package verification report; product execution TBD | unverified | Not approved |
| CLM-002 | Recall prevents unaudited model claims from creating a simulated review task | Deterministic candidate routing, one mismatched material claim among valid claims, exact lexical reasons, and zero-task read-back | TBD | unverified | Not approved |
| CLM-003 | Local Gemma adds privacy value beyond deterministic rules | Frozen bilingual synthetic corpus and paired metrics | TBD | unverified | Not approved |
| CLM-004 | Duplicate events do not produce duplicate review tasks | Repeated-delivery test and authoritative ledger read-back | TBD | unverified | Not approved |
| CLM-005 | Recall uses a dynamically discoverable managed agent fleet | Registry catalog, selected manifest receipt, runtime revisions, and trace | TBD | unverified | Not approved |
| CLM-006 | Every displayed result is derived from run artifacts | Automated derived-value audit against the frozen field registry | `docs/demo/DERIVED_VALUE_REGISTRY.md`; execution TBD | unverified | Not approved |
| CLM-007 | Recall safely maintains institutional watch context across weeks | Durable WatchCase, separate bounded ScanRuns, and `ABSTAIN`/`HALTED`/duplicate fixtures proving pending evidence survives without cursor advancement | TBD | unverified | Not approved |
| CLM-008 | Long-term model memory cannot become clinical evidence or workflow authority | Memory admission, poisoning, contradiction, byte-identical disabled-memory policy parity, zero task-count delta, and Firestore read-back tests | TBD | unverified | Not approved |
| CLM-009 | Recall interacts with public production sources without using real patient data | Synthetic case manifest, captured public replay, separately labeled live smoke, source hashes, atomic modes, run composition, and data-provenance audit | `docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json`; `docs/evaluation/reports/2026-08-17--rcl-205-protocol-1.0.1-verification.md`; synthetic and product execution manifests TBD | unverified | Not approved |
| CLM-010 | Untrusted external content cannot silently expand agent authority | Source-injection controls, Model Armor or structured-only fallback receipt, and denied tool-call evidence | TBD | unverified | Not approved |
| CLM-011 | A due WatchCase can create one durable ScanRun without duplicate creation on repeated manual delivery | Committed prediction, two live triggers, full Firestore read-back equality, direct exits, and hash-bound manifest | `artifacts/evidence/day1-manual-20260825-a7f31c9d/` | verified for LIVE infrastructure with SYNTHETIC data | One manual Day-1 trigger selected one due case and persisted one run; repeated delivery created no new run or event. Managed recurrence and terminal agent execution are not claimed. |
| CLM-012 | Recall has a date-aware, idempotent Day-N cohort path ready for managed deployment | Strict manifest contract, committed predictions/preparation locks, preview without cloud clients, crash/resume tests, independent review, and Master Judge | `367637b12e92eda0c2aa54c8bdc12af3adbfe99d`; `artifacts/evidence/cohort-preparation-v1/preparation-bundle.json`; `artifacts/evidence/cohort-manifest-example/` | verified locally; managed runtime not verified | Date-isolated Day-N scheduler implementation and deterministic local tests are verified. Cloud Run Job deployment and actual managed Day-2 execution are not yet verified. |

## Wording rule

Use bounded language that matches the tested geometry. A synthetic, historical, or replay result cannot be generalized into clinical accuracy, compliance, safety, or production-readiness claims.
