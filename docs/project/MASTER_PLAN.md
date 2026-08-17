# Recall Master Plan

## Document control

| Field | Value |
|---|---|
| Owner | aistanbulresearch |
| Status | Phase 2 final exact-head audit passed; PR #2 unmerged; collaboration runtime gate in progress; GitHub credential rotation deferred under explicit owner risk acceptance; billing selection blocked |
| Baseline date | 2026-08-14 |
| Architecture baseline | Product baseline ADR-0001 through ADR-0008; collaboration process ADR-0009 |
| Contest deadline | 2026-08-31 17:00 PT, corresponding to 2026-09-01 03:00 Europe/Istanbul |
| Internal submission target | 2026-08-31 18:00 Europe/Istanbul |
| Feature freeze | 2026-08-28 18:00 Europe/Istanbul |
| Repository | https://github.com/aistanbulresearch/recall |
| Local checkout | `C:\Users\oacav\OneDrive\Desktop\recall project` |
| Planned hostname | Unresolved: owner wrote `racall.aistanbulresearch.com`; confirm before DNS or deployment configuration |

This is a living plan. Any change to scope, sequencing, dates, acceptance gates, or task status must update this document in the same work unit.

## 1. Outcome

Deliver **Recall**, a privacy-preserving multi-agent research prototype that monitors changing public evidence for previously uncertain genetic results, independently audits material claims, and creates a simulated clinician-review task for a synthetic case only when deterministic policy allows it.

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
| Platform consideration | Unscored upside | Agent Runtime, Agent Registry, and observability are target critical-path controls; Memory Bank is a targeted Fleet proof; Identity, Gateway, and Model Armor are feasibility-gated governed extensions, without assuming a numerical bonus. |

## 3. Non-negotiable product invariants

- Raw identity and token mappings remain in the laboratory boundary.
- Genomic records are treated as sensitive pseudonymous data, not declared anonymous.
- Free text cannot leave the lab when privacy analysis is unavailable, invalid, or uncertain.
- The Workflow Controller is deterministic and owns state, budgets, retries, loop detection, and invocation.
- The Coordinator proposes a route; it does not execute arbitrary delegation.
- Agents cannot write Firestore directly and cannot emit terminal outcomes.
- The Citation Auditor is independent and cannot be skipped for a trusted review recommendation.
- Only deterministic policy emits `NO_ACTION`, `ABSTAIN`, or `REVIEW_REQUIRED`.
- Technical `HALTED` is distinct from policy abstention and is used only when trusted policy execution or ledger integrity is unavailable.
- `REVIEW_REQUIRED` is a review-priority signal, not a reclassification.
- A clinician remains the final authority.
- Missing or failed evidence is never converted into benign evidence or a positive clinical criterion.
- Every displayed result is derived from the authoritative run artifact.
- Every safety claim has positive, negative, and guardrail-activation proof.
- ADK Sessions and Memory Bank are non-authoritative and cannot satisfy evidence, audit, policy, or state-transition prerequisites.
- Multi-week continuity is represented by a durable `WatchCase`; each `ScanRun` is short, bounded, idempotent, and independently auditable.
- A deterministic `CandidateDeltaReceipt`, not an Assessor proposal, selects the candidate versus no-candidate route.
- Unsafe terminals preserve verified cursors and pending observation hashes; no missing evidence is consumed as seen.
- Every source artifact declares one atomic mode, and every run/product surface declares its transitive `mode_set` plus registered composition.

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
| RCL-010 | Review and approve the Fleet architecture direction | verified | Owner approval; updated target architecture and accepted ADR-0001 through ADR-0005 |
| RCL-011 | Establish repo-scoped Codex coordinator, custom subagents, Master Judge, and external-auditor cadence | in-progress | Structural validation passes; nested runtime observations are `REPORT_DERIVED`; the complete Recall-root per-profile, permission, effort, protected-action, and concurrency matrix remains |

**Phase gate:** another contributor can answer what, why, where, current status, next task, known errors, and proof requirements from repository documents alone.

### Phase 1: Eligibility, access, security, and feasibility, 2026-08-15

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-101 | Re-read binding rules and freeze an eligibility checklist | verified | Hash-pinned checklist, owner eligibility attestation, `individual/solo` entry capacity, and repository authority recorded; live Devpost recheck remains a final-submission control |
| RCL-102 | Decide license and third-party dependency policy | verified | Rules impose no special repo license; owner approved Apache-2.0; policy, register, source notes, and `LICENSE` are present |
| RCL-103 | Freeze the independent-implementation boundary and review only mandatory submission wording | verified, continuous gate | Rules snapshot limits disclosure to incorporated work; DEC-2026-08-15-014 prohibits direct import; reopen if any component is imported or a mandatory field differs |
| RCL-104 | Verify Vertex model, ADK, Agent Runtime, Registry, Memory Bank, Agent Identity, Agent Gateway, Model Armor, region, quota, and billing | blocked | Dedicated project, local CLI/SDK/auth passed; billing account selection blocks project-scoped smoke |
| RCL-105 | Verify Firestore, Pub/Sub, Cloud Run, Scheduler, Secret Manager, and telemetry access | blocked | Named resource plan exists; project-scoped discovery and read-back await billing linkage |
| RCL-106 | Rotate known exposed credentials and run repository/history secret scans | in-progress, owner-deferred risk | ERR-2026-08-17-086 records a newly exposed GitHub credential without its value. Rotation remains recommended; on 2026-08-17 the owner accepted the risk and authorized only the exact collaboration-infrastructure commit/push before rotation. |
| RCL-107 | Benchmark local Gemma E2B Q4_0 startup, JSON validity, p50/p95 latency, and memory | blocked | No checked local runtime command or GGUF model is installed; select/install artifacts before benchmark |
| RCL-108 | Resolve hostname spelling and document Hetzner/DNS ownership | blocked | Owner confirms `recall` or `racall` before external mutation |
| RCL-109 | Check product-name collision and discoverability risk | not-started | Naming decision records search, branding, and URL consequences |
| RCL-110 | Activate a protected-main ruleset when repository visibility or account plan permits it | blocked | Ruleset requires pull requests and prevents deletion/non-fast-forward updates; current private plan returns HTTP 403 |

**Phase gate:** every mandatory platform dependency has a working smoke path or an explicit fallback; no secret, license, or eligibility ambiguity is silently carried into implementation.

### Phase 2: Architecture, contracts, evaluation, and demo design, 2026-08-16

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-201 | Review and approve trust zones, authority hierarchy, four agent roles, and managed control-plane boundaries | verified design | Threat model, authority graph, component denied-action matrix, and activation-proof requirements frozen |
| RCL-202 | Define strict versioned contracts and common provenance envelope | verified corrected design | PolicyDecision, WatchCase, EvidenceDelta, and DataModeReceipt breaking changes are versioned; evaluated-state facts, candidate receipt, mode composition, and examples pass the local document audit |
| RCL-203 | Define `WatchCase`, `ScanRun`, and `ReviewTask` state machines plus idempotency, lease, retry/hop/time/token budgets, and failure codes | verified corrected design | Per-terminal cursor, backlog, attention, retry, scheduling, duplicate, and recovery actions pass the local document audit |
| RCL-204 | Define deterministic policy inputs and outcomes | verified corrected design | Deterministic candidate routing, memory exclusion, immutable material-claim blocking, evaluated states, and complete lexical reason sets pass the local document audit |
| RCL-205 | Select a source-attributed historical replay case, negative controls, and a separately labeled live public smoke | verified frozen source package | Protocol 1.0.1 binds ten exact captures, corrected GEO chronology/linkage, one exact XLSX row, clean-copy verification, mutated-byte rejection, and path-boundary rejection; product replay remains RCL-503/RCL-506 |
| RCL-206 | Freeze privacy, citation, reliability, and utility metrics before runs | verified design | Six preregistered protocols, thresholds, stop rules, rollback, counts, confidence intervals, and mechanism-activation gates frozen |
| RCL-207 | Design the four-minute storyboard and web information architecture | verified design | 3:45 storyboard, uninterrupted Proof of Action, fault run, cloud proof, single-screen wireframe, and cut rules recorded under `docs/demo/` |
| RCL-208 | Define derived-value lineage from artifact fields to every planned UI metric | verified design | Registry defines source paths, deterministic derivations, missing-data behavior, and tests; implementation evidence remains future work |
| RCL-209 | Freeze Firestore, ADK Sessions, and Memory Bank authority and retention contracts | in-progress | ADR-0002 accepted; schemas, IAM conditions, poisoning fixtures, and unavailable-service behavior remain |
| RCL-210 | Freeze managed Registry, Runtime, Identity, Gateway, Model Armor, and observability failure contracts | in-progress | ADR-0003 and ADR-0004 accepted; Phase 1 access evidence and threat-model mapping remain |
| RCL-211 | Package Phase 2 for GitHub auditor-agent review and notify the owner | verified | Final exact-head external audit passed at `195422e4d762d68d38e2b7f531cc5b1cd059cdb7`; owner-only metadata and zero bot surfaces; PR remains open/unmerged |

**Phase gate:** contracts, failure behavior, expected evidence direction, and demo moments are clear enough to write tests without inventing behavior during implementation. F-01 through F-08 must be resolved, the replay package must verify offline, and follow-up audit must pass before Phase 3 begins.

### Phase 3: Deterministic vertical skeleton plus web surface, 2026-08-17 to 2026-08-19

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-301 | Initialize Python/uv and web workspaces with locked dependencies | not-started | Clean-clone install succeeds; exact direct/transitive inventory, license gate, notices, and CycloneDX or SPDX SBOM pass |
| RCL-302 | Implement common contracts and provenance hashing with TDD | not-started | Unit tests include malformed and unknown fields |
| RCL-303 | Implement Ledger API and Firestore emulator adapter | not-started | Append-only and compare-and-set tests |
| RCL-304 | Implement deterministic Workflow Controller | not-started | Transition, duplicate, budget, loop, and terminal-failure tests |
| RCL-305 | Implement Pub/Sub request/outbox/dead-letter topology locally | not-started | Duplicate and retry fixture proof |
| RCL-306 | Implement deterministic Policy Gate truth table | not-started | Identical artifacts always produce identical outcomes |
| RCL-307 | Build the initial Recall web shell and live run timeline | not-started | UI reads backend artifacts and shows fixture labels |
| RCL-308 | Demonstrate fixture-driven `NO_ACTION`, `ABSTAIN`, and `REVIEW_REQUIRED` without LLMs | not-started | Three visible end-to-end runs and manifests |
| RCL-309 | Implement durable `WatchCase` scheduling, short `ScanRun` leases, and separate `ReviewTask` lifecycle | not-started | Week-sequence replay, crash resume, stale-write rejection, and paused/closed-case tests |

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
| RCL-507 | Enforce and display `SYNTHETIC`, `CAPTURED_REPLAY`, `LIVE_PUBLIC`, and `MOCK` modes | not-started | Schema, API, artifact, and UI mode assertions |

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
| RCL-609 | Implement Memory Bank admission, retrieval, expiry, scope, and Firestore-conflict controls | not-started | Poisoning rejection, isolation, TTL, retrieval receipt, and disabled-memory parity tests |
| RCL-610 | Integrate feasible Identity, Gateway, and Model Armor controls without widening authority | not-started | Allowed/denied tool receipts, source-injection control, and unavailable-service behavior |

**Phase gate:** a Registry-resolved managed run produces typed artifacts and one trace; a forbidden capability is visibly denied.

### Phase 7: Governance and recovery, 2026-08-26

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-701 | Complete claim-level audit and removal behavior | not-started | Fabricated citation cannot reach trusted output |
| RCL-702 | Complete terminal abstention and operations incidents | not-started | Source, schema, audit, and budget failures produce typed receipts |
| RCL-703 | Complete duplicate suppression and notification outbox | not-started | Zero duplicate review tasks under repeated delivery |
| RCL-704 | Complete loop and repeated-state recovery | not-started | Worker loop terminates within budget with no task |
| RCL-705 | Add fault-injection controls and proof states to the web surface | not-started | Jury can see cause, blocked action, and terminal result |
| RCL-706 | Complete memory poisoning, stale-memory, and cross-scope recovery | not-started | Memory is rejected or ignored; Firestore remains authoritative; no unsafe task is created |
| RCL-707 | Complete untrusted-source injection and Model Armor outage recovery | not-started | Attack is blocked or structured-only fallback/`ABSTAIN` activates with a typed receipt |

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
| RCL-902 | Perform security, secret, dependency, license, and repository-history audit | not-started | Signed checklist and scan artifacts; Phase 2 auditor findings have final disposition and material changes receive follow-up review |
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

1. Remote A2A invocation; retain Registry-resolved Controller invocation.
2. Advanced Agent Gateway integration; retain Controller allowlists and separate service accounts.
3. Model Armor integration if access or reliability fails; retain structured-only source restriction and `ABSTAIN`.
4. Advanced Memory Bank search or visualization; retain the minimal admission/rejection proof if access passes.
5. Second live evidence connector; retain source-attributed replay and one separately labeled live smoke.
6. Advanced reviewer filters, accounts, and administration.
7. Cloud object versioning beyond normalized snapshots and hashes.
8. Multiple historical cases beyond the minimum proof set.
9. Larger local Gemma comparison.
10. Visual polish that does not increase comprehension.

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
3. Review the completed protocol 1.0.1 verification report before the safe-push gate; technical offline verification has passed locally.
4. Review exact wording only if a binding submission field explicitly asks about prior work, inspiration, or reuse; do not create a voluntary pre-existing-work section when no component is imported.

## 10. Current next action

The Phase 2 exact-head external audit passed. The owner explicitly authorized publication of the collaboration infrastructure despite deferring RCL-106 credential rotation. Publish with owner-only attribution, verify the exact remote head and GitHub surfaces, then request the external GitHub auditor before merge or Phase 3. In a fresh Recall-root Codex task, complete every remaining RCL-011 runtime row. Billing-dependent platform smoke remains paused.
