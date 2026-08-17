# Recall Preregistered Evaluation Protocols

- Status: corrected protocol baseline, execution not started
- Date: 2026-08-17
- Related tasks: RCL-205, RCL-206, RCL-404, RCL-405, RCL-506, RCL-801 through RCL-803

## Purpose and claim boundary

These protocols test a non-clinical research prototype. They do not establish clinical validity, diagnostic performance, regulatory compliance, production privacy, or patient safety.

All thresholds, failure rules, expected directions, data modes, and rollback decisions are fixed before evaluation runs. A synthetic, replay, live public, or mock result supports only the mode it actually exercised.

## Measurement-before-build gate

Each proposed subsystem must pass four questions before expensive implementation:

| Gate | Required evidence | Decision if absent |
|---|---|---|
| O1 prior signal | Authoritative literature, source history, or a documented failure mechanism supports the target problem | Redesign or stop the claim |
| O2 capability and data | Required runtime, model, source rights, fixtures, and measurable ground truth exist | Block implementation |
| O3 route validity | A minimal real route returns analyzable outputs at a nonzero rate | Redesign before scaling |
| O4 measurement cost | Runtime, source quota, labeling effort, and evaluation time fit the contest budget | Cut or narrow scope |

Mock responses can test interfaces but cannot satisfy O3 or measure product performance.

## Shared evidence requirements

Every execution writes a manifest under `artifacts/evidence/<run-id>/` containing commit, configuration hash, dependency-lock hash, dataset/source manifest, data mode, command, exit status, artifact hashes, counts, activation counters, and limitations. Runs with missing manifests are excluded and reported, not silently dropped.

Proportions are reported as numerator/denominator with Wilson 95% confidence intervals. Paired detector outcomes use McNemar's test only when discordant counts support it. Latencies report p50, p95, maximum, and bootstrap confidence intervals. Small samples are labeled exploratory. No percentage is shown without its count.

## Protocol P1: Local privacy contribution

### Question

Does local Gemma find seeded residual identifier spans beyond deterministic detectors without weakening fail-closed egress?

### Data

- Bilingual synthetic records only, generated from a committed template and seed.
- Identifier classes include names, dates, contact details, addresses, record IDs, relatives, and contextual quasi-identifiers.
- Freeze train/development/test separation before tuning. The test manifest remains unread by prompt and rule tuning.
- No real or patient-derived text.

### Comparators and metrics

| Path | Metrics |
|---|---|
| Deterministic baseline | Span precision, recall, F1; document escape count; false-redaction span count; latency |
| Baseline plus Gemma proposals plus deterministic approval | Same metrics; incremental true positives; incremental false positives; strict-JSON validity; timeout/unavailable rate; p50/p95 latency |
| Deterministic outbound gate | Accepted/quarantined counts and seeded-identifier escapes among accepted payloads |

### Preregistered success and failure

- Mandatory safety gate: zero seeded direct-identifier spans in accepted cloud-bound payloads.
- Gemma earns a demo claim only if it adds at least one true-positive residual span on the frozen test set and does not increase accepted identifier escapes.
- Every invalid JSON, timeout, unavailable model, or uncertain span must quarantine or remain blocked by deterministic egress logic.
- If Gemma adds no true positive, increases escapes, or cannot complete within the allocated local privacy segment, remove it from the critical path and video. Keep the deterministic Privacy Gate.

## Protocol P2: Citation and counter-evidence integrity

### Data

A frozen source-attributed fixture set with valid claim/source pairs, fake identifiers, mismatched titles/records, unsupported material claims, unavailable metadata, duplicated claims, and intentionally omitted counter-evidence. Public metadata rights and retrieval timestamps are recorded.

### Metrics

- invalid material-claim block rate;
- valid claim verification rate;
- counter-evidence omission detection rate;
- audit completeness rate;
- false review-task count;
- auditor activation count and independent-refetch count.

### Gates

- Every frozen fake, mismatched, unsupported, and omission fault on a material claim must make the current immutable assessment ineligible and block `REVIEW_REQUIRED`.
- Zero review tasks may exist when audit completeness is false.
- A green outcome without a nonzero auditor/refetch activation count is invalid evidence.
- If the auditor cannot independently retrieve the required metadata, the policy result is `ABSTAIN`, not a passed audit.
- One mismatched material claim among otherwise verified claims must produce `material_claim_unverified`, zero tasks, and no rescue by removing the claim from the same assessment.

## Protocol P3: Workflow reliability and recovery

### Fault set

Duplicate delivery, crash after state commit, crash before outbox delivery, expired lease, stale writer, invalid route, forbidden tool, agent schema failure, source outage, repeated state hash, budget exhaustion, Registry outage, Policy Gate outage, notification outage, poisoned memory, cross-scope memory, and Model Armor outage.

### Metrics and gates

| Property | Frozen gate |
|---|---|
| Idempotency | Repeated delivery yields one logical run per idempotency key and at most one task |
| Crash recovery | Resume preserves committed history and does not repeat a logical transition |
| Stale-write safety | Every expired-lease or wrong-version mutation is rejected |
| Loop safety | Repeated state hash stops within the frozen hop budget and creates no task |
| Candidate authority | Exact allele, scope, completeness, and new-hash geometry is derived by `CandidateDeltaReceipt`; an Assessor dismissal cannot produce `NO_ACTION` |
| Policy authority | Identical authoritative artifacts yield byte-identical outcome and reasons plus zero task-count delta with memory on and off |
| Cursor safety | `ABSTAIN`, `HALTED`, and duplicate suppression do not consume unaudited observation hashes; recovery observes them again |
| Managed outage | No outage path widens identity, tool, endpoint, or policy authority |
| Notification isolation | Delivery retry does not re-run policy or duplicate a task |
| Mechanism proof | Each safe result has a nonzero guardrail activation counter and forbidden-downstream read-back |

Any duplicate task, unauthorized invocation, stale successful write, silent bypass, or policy change caused solely by memory fails the architecture gate and blocks demo evidence.

## Protocol P4: Derived UI integrity

### Method

Use every Field ID in `docs/demo/DERIVED_VALUE_REGISTRY.md`. For each result field, mutate its source artifact while keeping fixture names constant; remove required source paths; change data modes; reorder events; and inject unknown fields.

### Gates

- Zero unregistered result-bearing UI fields.
- Every artifact mutation changes only the values that depend on that path.
- Missing required data renders `UNKNOWN` or blocks the panel, never a clean/default value.
- Atomic mode or run `mode_set` deletion fails schema/API/UI assertions. Registered synthetic-plus-captured-replay composition passes; mock-plus-product and live-public-inside-replay compositions fail.
- No outcome, metric, counter, badge, elapsed time, or threshold label derives from fixture name, URL route, timer, or preset.

## Protocol P5: Historical evidence replay and utility

### Candidate selection before implementation

1. Search source-attributed public history for a case where a material evidence signal predates a later public classification update.
2. Record all screened candidates and rejection reasons before choosing the demo case.
3. Freeze one positive candidate and at least two negative controls with exact source versions, retrieval dates, locators, hashes, and rights notes.
4. Define the expected signal and time ordering before running Recall.
5. Keep a separately labeled `LIVE_PUBLIC` connector smoke. It cannot replace the deterministic `CAPTURED_REPLAY`.

### Metrics

- evidence-signal detection in the preregistered positive case;
- false material-delta count in negative controls;
- lead time in days between the qualifying evidence date and later public classification update, derived from source timestamps;
- source coverage and retrieval completeness;
- run reproducibility from frozen snapshots.

### Gates and wording

- The positive case must produce a deterministic candidate receipt under the frozen exact-allele/scope/new-hash rule and both negative controls must complete without a fabricated candidate delta.
- Lead time is reported for this case only. It is not generalized to all variants or laboratories.
- If the case fails, report it and select no replacement after seeing the result unless a new protocol version records why. No cherry-picking.
- RCL-205 is verified at frozen-source-package level under protocol 1.0.1: ten exact captures, corrected chronology/linkage, one exact XLSX row, clean-copy verification, mutated-byte rejection, and path-boundary rejection pass offline. Product replay and utility remain unverified until RCL-503, RCL-506, and RCL-801 execute this package.

## Protocol P6: Managed fleet proof

### Required route

One uninterrupted run must show exact Registry resolution, separate runtime revisions and service identities, allowed and denied tool receipts, authoritative Firestore transitions, non-authoritative memory receipt, PolicyDecision, and one sanitized correlated trace.

### Gates

- Exact revision and manifest digest read back from the managed platform.
- At least one allowed tool call and one forbidden call use the expected role identities.
- No agent identity can transition state or create a task.
- Trace correlation matches artifact/run IDs and contains none of the prohibited telemetry fields.
- If a managed feature is unavailable, disclose it and use only its frozen non-widening fallback. Do not display a decorative platform badge as proof.

## Stop and rollback rules

Stop the run series and open an error entry if real data, a secret, unlicensed content, accepted identifier escape, duplicate task, unauthorized tool call, stale successful write, missing data displayed as clean, hard-coded result behavior, or non-authoritative memory affecting policy is observed.

Rollback removes the failing optional component from the critical path, preserves raw evidence manifests, increments the protocol version for any changed threshold or dataset, and reruns from a clean state. Failed results remain in the ledger.

## Phase 2 exit status

RCL-206 is verified as a corrected design gate, and RCL-205 is verified at frozen-source-package level after protocol 1.0.1 passed offline integrity and chronology/linkage checks. This is not external follow-up approval, product replay evidence, or an empirical utility claim. No empirical claim becomes verified until RCL-801 executes the frozen protocols.
