# Recall Master Plan

## Document control

| Field | Value |
|---|---|
| Owner | aistanbulresearch |
| Status | Phase 0 verified; awaiting owner review before Phase 1 |
| Baseline date | 2026-08-14 |
| Contest deadline | 2026-08-31 17:00 PT, corresponding to 2026-09-01 03:00 Europe/Istanbul |
| Internal submission target | 2026-08-31 18:00 Europe/Istanbul |
| Feature freeze | 2026-08-28 18:00 Europe/Istanbul |
| Repository | https://github.com/aistanbulresearch/recall |
| Local checkout | `C:\Users\oacav\OneDrive\Desktop\recall project` |
| Planned hostname | Unresolved: owner wrote `racall.aistanbulresearch.com`; confirm before DNS or deployment configuration |

This is a living plan. Any change to scope, sequencing, dates, acceptance gates, or task status must update this document in the same work unit.

## 1. Outcome

Deliver **Recall**, a privacy-preserving multi-agent system that monitors changing public evidence for previously uncertain genetic results, independently audits material claims, and creates a clinician-review task only when deterministic policy allows it.

The submission must be understandable without clinical-genetics knowledge and must visibly prove:

1. a real operational burden is removed;
2. multiple specialist agents are necessary and strictly separated;
3. a common autonomous-agent failure is made structurally impossible;
4. failure, hallucination, and missing data terminate loudly;
5. the managed cloud critical path actually runs;
6. the web experience displays values derived from the same authoritative artifacts used by policy and evaluation.

## 2. Positioning and contest score budget

### Product story

Clinical teams cannot repeatedly reopen every historical uncertain result whenever new evidence appears. Recall continuously monitors approved public sources and brings the specialist only a small, audited review queue.

### Honest differentiation

Do not claim that longitudinal monitoring is new. The defensible distinction is:

- evidence-level signals rather than only classification-version changes;
- lab-local privacy enforcement before cloud processing;
- capability-separated agents with independently enforced authority;
- independent claim and citation audit;
- deterministic policy and terminal abstention;
- visible recovery artifacts for hallucination, loops, source failure, and missing data.

### Score allocation

| Criterion | Weight | Required proof |
|---|---:|---|
| Innovation and operational utility | 40% | One source-attributed historical replay showing an audited evidence signal before or while the comparison classification remains unchanged; negative controls; clear reduction in cases a specialist must open. |
| Architecture | 30% | Four separated roles, Registry discovery, bounded typed routing, separate tool scopes, append-only artifacts, deterministic controller and policy, denied action, loop recovery, and independent citation audit. |
| Demo and readiness | 30% | Four-minute coherent flow, managed runtime revision, Registry entries, Firestore transitions, one trace, derived UI values, fault injection, synthetic-data labels, and a clinician-facing result. |
| Model bonus | Unscored upside | Local Gemma performs measured residual identifier detection and visibly adds value beyond deterministic rules. |
| Platform consideration | Unscored upside | Agent Runtime, Agent Registry, and observability are part of the critical path, without assuming a numerical bonus. |

## 3. Non-negotiable product invariants

- Raw identity and token mappings remain in the laboratory boundary.
- Genomic records are treated as sensitive pseudonymous data, not declared anonymous.
- Free text cannot leave the lab when privacy analysis is unavailable, invalid, or uncertain.
- The Workflow Controller is deterministic and owns state, budgets, retries, loop detection, and invocation.
- The Coordinator proposes a route; it does not execute arbitrary delegation.
- Agents cannot write Firestore directly and cannot emit terminal outcomes.
- The Citation Auditor is independent and cannot be skipped for a trusted review recommendation.
- Only deterministic policy emits `NO_ACTION`, `ABSTAIN`, or `REVIEW_REQUIRED`.
- `REVIEW_REQUIRED` is a review-priority signal, not a reclassification.
- A clinician remains the final authority.
- Missing or failed evidence is never converted into benign evidence or a positive clinical criterion.
- Every displayed result is derived from the authoritative run artifact.
- Every safety claim has positive, negative, and guardrail-activation proof.

## 4. Delivery strategy

### Vertical-slice rule

The project is built as end-to-end slices. Each slice includes:

1. versioned contract;
2. deterministic backend behavior;
3. agent or connector behavior where needed;
4. authoritative ledger artifact;
5. web presentation derived from that artifact;
6. tests and fault injection;
7. trace or log proof;
8. updated ledgers and handoff.

The web application is therefore developed from the first executable slice. There is no separate late "build the demo website" phase.

### Gate discipline

Each task follows design, implementation/TDD, review, verification, documentation, then merge. A failed gate pauses dependent work.

### Branch strategy

- Initial documentation baseline may establish `main`.
- Subsequent work uses short-lived `feature/<task-id>-<slug>` branches.
- Pull requests target `main` and require checks.
- A separate long-lived `develop` branch is intentionally omitted for hackathon speed unless parallel integration pressure makes it necessary.
- Published history is not rewritten.

## 5. Work breakdown and schedule

Status values follow `DOCUMENTATION_SYSTEM.md`.

### Phase 0: Foundation and project control, 2026-08-14

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-001 | Verify remote repository, ownership, visibility, and empty state | verified | Work Log records GitHub and local preflight |
| RCL-002 | Clone to the approved local path | verified | Clean local checkout with correct origin |
| RCL-003 | Establish master plan and status/handoff protocol | verified | This document, `STATUS.md`, and `HANDOFF.md` agree |
| RCL-004 | Establish decision, work, and error ledgers | verified | Append-only ledgers contain initial entries |
| RCL-005 | Establish score, claim, guardrail, and demo evidence ledgers | verified | Every contest criterion has a planned proof path |
| RCL-006 | Record engineering, scientific, demo, and authorship rules | verified | `AGENTS.md` and governance documents exist |
| RCL-007 | Add baseline repository hygiene and PR templates | verified | Ignore rules, line endings, ownership, security, and PR template verified |
| RCL-008 | Bind Recall to a local Obsidian project memory | verified | Local binding and canonical project notes verified; machine paths excluded from Git |
| RCL-009 | Commit and push documentation-only baseline as aistanbulresearch | verified | Remote SHA `5336432a3e353261813443f41a217388b68d585d`; GitHub author and committer both `aistanbulresearch`; no co-author trailers |

**Phase gate:** another contributor can answer what, why, where, current status, next task, known errors, and proof requirements from repository documents alone.

### Phase 1: Eligibility, access, security, and feasibility, 2026-08-15

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-101 | Re-read binding rules and freeze an eligibility checklist | not-started | Rule text, interpretation, uncertainty, and owner action recorded |
| RCL-102 | Decide license and third-party dependency policy | not-started | License decision and dependency inventory protocol |
| RCL-103 | Confirm actual reuse scope and any required submission disclosure | not-started | Owner-approved eligibility decision based only on components actually reused |
| RCL-104 | Verify Vertex model, ADK, Agent Runtime, Registry, region, quota, and billing | not-started | Minimal authenticated smoke artifacts with no product logic |
| RCL-105 | Verify Firestore, Pub/Sub, Cloud Run, Scheduler, Secret Manager, and telemetry access | not-started | Named resource plan and read-back proof |
| RCL-106 | Rotate known exposed credentials and run repository/history secret scans | not-started | Rotation confirmation without secret values; scanner artifacts |
| RCL-107 | Benchmark local Gemma E2B Q4_0 startup, JSON validity, p50/p95 latency, and memory | not-started | Reproducible synthetic smoke report |
| RCL-108 | Resolve hostname spelling and document Hetzner/DNS ownership | blocked | Owner confirms `recall` or `racall` before external mutation |
| RCL-109 | Check product-name collision and discoverability risk | not-started | Naming decision records search, branding, and URL consequences |

**Phase gate:** every mandatory platform dependency has a working smoke path or an explicit fallback; no secret, license, or eligibility ambiguity is silently carried into implementation.

### Phase 2: Architecture, contracts, evaluation, and demo design, 2026-08-16

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-201 | Review and approve trust zones, authority hierarchy, and four agent roles | not-started | Architecture ADRs and threat model |
| RCL-202 | Define strict versioned contracts and common provenance envelope | not-started | Schemas with unknown-field rejection and examples |
| RCL-203 | Define the state machine, idempotency, retry/hop/time/token budgets, and failure codes | not-started | Transition table and invariant tests written first |
| RCL-204 | Define deterministic policy inputs and outcomes | not-started | Truth table for `NO_ACTION`, `ABSTAIN`, and `REVIEW_REQUIRED` |
| RCL-205 | Select a source-attributed historical replay case and negative controls | not-started | Evidence timeline, licensing, and expected signal preregistered |
| RCL-206 | Freeze privacy, citation, reliability, and utility metrics before runs | not-started | Evaluation protocols and failure criteria committed |
| RCL-207 | Design the four-minute storyboard and web information architecture | not-started | Timed storyboard and UI wireframe linked to score rows |
| RCL-208 | Define derived-value lineage from artifact fields to every planned UI metric | not-started | UI value registry has no manual result values |

**Phase gate:** contracts, failure behavior, expected evidence direction, and demo moments are clear enough to write tests without inventing behavior during implementation.

### Phase 3: Deterministic vertical skeleton plus web surface, 2026-08-17 to 2026-08-19

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-301 | Initialize Python/uv and web workspaces with locked dependencies | not-started | Clean-clone install succeeds |
| RCL-302 | Implement common contracts and provenance hashing with TDD | not-started | Unit tests include malformed and unknown fields |
| RCL-303 | Implement Ledger API and Firestore emulator adapter | not-started | Append-only and compare-and-set tests |
| RCL-304 | Implement deterministic Workflow Controller | not-started | Transition, duplicate, budget, loop, and terminal-failure tests |
| RCL-305 | Implement Pub/Sub request/outbox/dead-letter topology locally | not-started | Duplicate and retry fixture proof |
| RCL-306 | Implement deterministic Policy Gate truth table | not-started | Identical artifacts always produce identical outcomes |
| RCL-307 | Build the initial Recall web shell and live run timeline | not-started | UI reads backend artifacts and shows fixture labels |
| RCL-308 | Demonstrate fixture-driven `NO_ACTION`, `ABSTAIN`, and `REVIEW_REQUIRED` without LLMs | not-started | Three visible end-to-end runs and manifests |

**Phase gate:** the full authority path runs locally without models, all three terminal outcomes are visible, and no displayed result is hard-coded.

### Phase 4: Lab-local privacy slice plus web proof, 2026-08-20 to 2026-08-21

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-401 | Implement strict local input schema, minimizer, token vault interface, and deterministic detectors | not-started | Unit tests by identifier class |
| RCL-402 | Implement local Gemma span-only adapter and deterministic redaction | not-started | Invalid JSON, timeout, and unavailable-model tests |
| RCL-403 | Implement outbound scan, quarantine, and signed PrivacyReceipt | not-started | Seeded identifier never reaches cloud-bound fixture |
| RCL-404 | Build bilingual synthetic privacy corpus and preregister splits | not-started | Corpus generator and manifest, no real data |
| RCL-405 | Measure deterministic baseline and Gemma incremental contribution | not-started | Recall/false-positive/latency artifacts with limitations |
| RCL-406 | Add privacy boundary and quarantine evidence to the web flow | not-started | UI fields derive from PrivacyReceipt; redacted text is not logged |

**Phase gate:** the demo visibly shows a residual identifier caught by Gemma, a signed cloud-bound payload without the identifier, and a failure case quarantined.

### Phase 5: Evidence monitoring and historical replay plus web timeline, 2026-08-22 to 2026-08-23

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-501 | Implement allowlisted PubMed connector with rate, retry, cache, and drift controls | not-started | Recorded fixtures plus one labeled live smoke |
| RCL-502 | Implement ClinVar comparison connector and normalization | not-started | Submission/conflict fixtures and schema-drift test |
| RCL-503 | Implement historical replay connector with source hashes | not-started | Exact replay produces deterministic snapshot |
| RCL-504 | Implement observation, snapshot, and temporal delta artifacts | not-started | Hash/provenance and no-change tests |
| RCL-505 | Render previous/current evidence and delta in the web timeline | not-started | UI values trace to artifact IDs |
| RCL-506 | Verify one evidence signal and negative controls | not-started | Preregistered comparison report, no cherry-picking |

**Phase gate:** the same historical replay reliably produces a source-attributed delta, while negative controls remain `NO_ACTION`.

### Phase 6: Registered agent fleet plus observability, 2026-08-24 to 2026-08-25

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-601 | Implement Fleet Coordinator with typed bounded RoutingPlan only | not-started | Forbidden-route and invalid-schema tests |
| RCL-602 | Implement Evidence Watcher with connector-only tool scope | not-started | Denied interpretation and arbitrary-URL tests |
| RCL-603 | Implement Evidence Assessor with counter-evidence and uncertainty contracts | not-started | No decision authority; grounded artifact references |
| RCL-604 | Implement independent Citation Auditor | not-started | Fake PMID, mismatched metadata, omitted counter-evidence tests |
| RCL-605 | Deploy separate revisions and identities to Agent Runtime | not-started | Runtime revision and IAM evidence |
| RCL-606 | Publish manifests to Agent Registry and resolve them dynamically | not-started | Registry catalog and selected-version receipt |
| RCL-607 | Implement sanitized cross-service tracing | not-started | One trace without clinical content |
| RCL-608 | Show fleet roles, versions, scopes, and live route on the web surface | not-started | UI reads catalog/run receipts, no decorative hard-coding |

**Phase gate:** a Registry-resolved managed run produces typed artifacts and one trace; a forbidden capability is visibly denied.

### Phase 7: Governance and recovery, 2026-08-26

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-701 | Complete claim-level audit and removal behavior | not-started | Fabricated citation cannot reach trusted output |
| RCL-702 | Complete terminal abstention and operations incidents | not-started | Source, schema, audit, and budget failures produce typed receipts |
| RCL-703 | Complete duplicate suppression and notification outbox | not-started | Zero duplicate review tasks under repeated delivery |
| RCL-704 | Complete loop and repeated-state recovery | not-started | Worker loop terminates within budget with no task |
| RCL-705 | Add fault-injection controls and proof states to the web surface | not-started | Jury can see cause, blocked action, and terminal result |

**Phase gate:** every critical guardrail has visible activation evidence and all dangerous incomplete paths end without a clinical task.

### Phase 8: Evaluation, deployment, and narrative integration, 2026-08-27

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-801 | Run frozen privacy, citation, reliability, and utility protocols | not-started | Artifact manifests and honest limitations |
| RCL-802 | Audit every UI number and badge against source artifacts | not-started | Derived-value audit has zero unresolved manual values |
| RCL-803 | Complete jury-language UX and remove avoidable genetics jargon | not-started | Non-specialist comprehension review |
| RCL-804 | Deploy web/API to Hetzner and cloud agent services to managed platform | not-started | HTTPS health, revision IDs, and rollback runbook |
| RCL-805 | Connect approved hostname and verify TLS/DNS | blocked | Depends on RCL-108 and owner-created DNS |
| RCL-806 | Complete score matrix and claim-evidence ledger | not-started | No unsupported score or numerical claim |

**Phase gate:** every claim and score row points to a real artifact and the full hosted critical path is reproducible.

### Phase 9: Feature freeze, rehearsal, and submission, 2026-08-28 to 2026-08-31

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-901 | Freeze features on 2026-08-28 18:00 Istanbul | not-started | Freeze commit and open-risk list |
| RCL-902 | Perform security, secret, dependency, license, and repository-history audit | not-started | Signed checklist and scan artifacts |
| RCL-903 | Perform clean-clone install and full local/cloud rehearsal | not-started | Exact commands and timings from a clean environment |
| RCL-904 | Write and time the English four-minute script | not-started | Script maps every segment to a score criterion |
| RCL-905 | Record the unedited critical path and supporting screenshots | not-started | Video ledger with artifact references |
| RCL-906 | Audit submission wording, data labels, disclosures, and limitations | not-started | Owner-approved final submission text |
| RCL-907 | Submit by internal target and verify read-back | not-started | Submission confirmation and content read-back |

**Phase gate:** the repository, hosted demo, video, and submission all describe the same verified product state.

## 6. Mandatory checkpoints

### 25% checkpoint, 2026-08-18

- The deterministic state path and web timeline must be visible.
- Identify score-matrix rows with no evidence path.
- Cut at least one non-critical item if the critical path is late.

### 50% checkpoint, 2026-08-22

- Privacy proof must be measured, not merely implemented.
- Historical replay must be selected and reproducible.
- Agent platform access must no longer be speculative.

### 75% checkpoint, 2026-08-26

- Managed fleet run, independent audit, and abstention must work.
- The four-minute demo must already be rehearsable.
- No new subsystem begins after this checkpoint.

## 7. Scope cut order

Cut in this order when schedule slips:

1. Memory Bank demonstration.
2. Agent Gateway, managed Agent Identity, and Model Armor integration.
3. Remote A2A invocation; retain Registry-resolved Controller invocation.
4. Second live evidence connector; retain source-attributed replay.
5. Advanced reviewer filters, accounts, and administration.
6. Cloud object versioning beyond normalized snapshots and hashes.
7. Multiple historical cases beyond the minimum proof set.
8. Larger local Gemma comparison.
9. Visual polish that does not increase comprehension.

Never cut privacy enforcement, strict authority separation, Firestore state, independent audit, deterministic policy, abstention, fault-injection proof, derived UI values, secret hygiene, synthetic-data labeling, or clean-clone rehearsal.

## 8. Definition of done

Recall is submission-ready only when:

- the managed critical path works from privacy receipt to clinician review task;
- four roles and their tool boundaries are visible;
- one common autonomous-agent failure is demonstrated and structurally blocked;
- all terminal failures produce typed, trace-linked receipts;
- historical replay and negative controls pass their preregistered protocol;
- the UI contains no untracked static result value;
- every numerical and safety claim links to a committed artifact;
- public content contains no real patient data, secret, unsupported clinical claim, or misleading live-data implication;
- commit, PR, and submission ownership is `aistanbulresearch` without automated co-author attribution;
- the clean-clone rehearsal and hosted rollback runbook pass;
- the owner approves the final video and submission.

## 9. Open owner decisions

1. Confirm whether the hostname is `recall.aistanbulresearch.com` or `racall.aistanbulresearch.com`.
2. Approve or revise the internal feature-freeze and submission target times.
3. Select the final repository license after dependency and submission requirements are reviewed.
4. Approve the exact disclosure language only after the actual reused component set is known.

## 10. Current next action

Stop for owner review of the Phase 0 baseline. After approval and hostname clarification, begin Phase 1 eligibility, access, security, license, and Gemma feasibility gates without starting product implementation prematurely.
