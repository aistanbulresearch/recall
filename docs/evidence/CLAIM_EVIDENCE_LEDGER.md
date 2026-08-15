# Claim Evidence Ledger

No submission, README, UI, or video claim is approved until its evidence path is populated.

| Claim ID | Proposed claim | Evidence required | Artifact | Status | Approved wording |
|---|---|---|---|---|---|
| CLM-001 | Recall detects evidence changes before a classification-only monitor | Source-attributed historical timeline and frozen comparison protocol | `docs/evaluation/HISTORICAL_REPLAY_CASE.md`; `docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json`; execution TBD | unverified | Not approved |
| CLM-002 | Recall prevents unaudited model claims from creating a clinician task | Fake/mismatched citation and incomplete-audit fault tests | TBD | unverified | Not approved |
| CLM-003 | Local Gemma adds privacy value beyond deterministic rules | Frozen bilingual synthetic corpus and paired metrics | TBD | unverified | Not approved |
| CLM-004 | Duplicate events do not produce duplicate review tasks | Repeated-delivery test and authoritative ledger read-back | TBD | unverified | Not approved |
| CLM-005 | Recall uses a dynamically discoverable managed agent fleet | Registry catalog, selected manifest receipt, runtime revisions, and trace | TBD | unverified | Not approved |
| CLM-006 | Every displayed result is derived from run artifacts | Automated derived-value audit against the frozen field registry | `docs/demo/DERIVED_VALUE_REGISTRY.md`; execution TBD | unverified | Not approved |
| CLM-007 | Recall safely maintains institutional watch context across weeks | Durable WatchCase and separate bounded ScanRuns with scheduler, crash-resume, stale-write, and replay evidence | TBD | unverified | Not approved |
| CLM-008 | Long-term model memory cannot become clinical evidence or workflow authority | Memory admission, poisoning, contradiction, disabled-memory parity, and Firestore read-back tests | TBD | unverified | Not approved |
| CLM-009 | Recall interacts with public production sources without using real patient data | Synthetic case manifest, captured public replay, separately labeled live smoke, source hashes, and data-mode audit | `docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json`; synthetic and execution manifests TBD | unverified | Not approved |
| CLM-010 | Untrusted external content cannot silently expand agent authority | Source-injection controls, Model Armor or structured-only fallback receipt, and denied tool-call evidence | TBD | unverified | Not approved |

## Wording rule

Use bounded language that matches the tested geometry. A synthetic, historical, or replay result cannot be generalized into clinical accuracy, compliance, safety, or production-readiness claims.
