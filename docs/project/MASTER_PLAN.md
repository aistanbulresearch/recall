# Recall Master Plan

## 2026-08-26 compressed machine-triggered cycle package

Status: plan-4 product commit `b5cd5a815baad5980a3d62bfb49ab980b63e3057` and bundle SHA-256 `4b494be9c82de3c3762ecc6249169b26922334f6e47af0010dafb163667a5f57` are implementation/test/Judge GREEN. c1 success and c2 missed-window facts are `OWNER_REPORTED`; independent cloud read-back is `NOT VERIFIED`.

1. Freeze c1 in plan-3. Use plan-4 SHA-256 `4c2b5ededcf79472781d0d58eca23b46278dcd0a9cc3fcaeb8c307f7a6c84e89` for all remaining timing, predictions, and prefix isolation.
2. Execute c2-c5 only inside 22:30/22:50/23:10/23:30Z windows with predictions 2/4/1/1. c2 reads the declared plan-3 c1 predecessor; c3-c5 read current-plan predecessors. No c1 copy is permitted.
3. Prepare all 450 c6 onboarding cases, but do not create its 2026-08-27 12:00Z trigger until Task 2 implements `FIRESTORE_BATCH_V1`, the exact c1-c5 `CohortHeadroomReceipt` is PASS, and authoritative read-back matches.
4. Rebuild/repoint, prepare only unexecuted `p4c2b5ededcf7` prefixes from the current bundle, and run Cloud Run `--verify-prefix`. Any nonzero result blocks that cycle.
5. L1 owns `infra/**`, scheduler-SA IAM, image/repoint, 1200-second timeout, plan-derived one-shot triggers, preflight, and cloud read-back. L2 owns the importable entrypoint, contracts, preparation, and tests. L3 derives UI labels only from manifest `schedule_mode`, preserves row-level provenance, and ships only the final manifest in the demo bundle.
6. Record each cycle as `cycle_id | prediction | observation | run IDs | event count | idempotency`; keep intermediate manifests in evidence and expose only the final manifest to the demo. Do not claim runtime before those artifacts exist.
7. After the frozen deployment, run one post-freeze verification tick against that exact revision. No Aug 29/30 tail-day claim remains under DEC-2026-08-26-046.

## 2026-08-26 typed incomplete-day continuation

Status: local product commit `7ebc733063e816ac0f4f3b012b6e99d9f055ee8e` is implementation/test/Judge GREEN. Production Firestore behavior and L3 compatibility remain gated.

1. Read exact `CohortDayManifest 2.0.0` predecessors without rewriting them; emit only 2.1.0 with typed COMPLETE/INCOMPLETE history rows.
2. Record each reconciled missing prior day as deterministic `CohortDayFailureReceipt 1.0.0`; retry reuses the first persisted bytes.
3. Validate the complete bounded predecessor chain and origin-ledger receipts before any current-day scheduler write. Partial prior state, backend failure, wrong predecessor, or dangling receipt fails closed.
4. Do not deploy 2.1.0 until L3 acknowledges its parser and fixtures against exact product commit `7ebc733063e816ac0f4f3b012b6e99d9f055ee8e`. L3 acknowledgement is currently `NOT_RECEIVED`.
5. After compatibility acknowledgement and L1 rebuild/repoint, run the production continuation fault path with exact Firestore read-back. Until then, runtime behavior remains `NOT VERIFIED`.

## 2026-08-25 M2 managed Day-N path

Status: L2 base implementation is at `367637b12e92eda0c2aa54c8bdc12af3adbfe99d`; the adversarial history/F5-lite successor is committed locally at `435fd46035c7a9e9dca7f06b2264799b52cffa30`. L1 rebuild/repoint and the first actual managed Day-2 tick remain gated.

1. Preserve frozen Day-1 code and evidence. The new Day-N path derives selection from the actual UTC date and rejects a recurring 2026-08-25 execution.
2. Use the committed 12-case cohort and pre-run predictions: 2026-08-26 = 3, 2026-08-27 = 2, and 2026-08-28 = 4. Do not execute a future cohort day early.
3. L2 owns `src/recall/scheduler/**`, scheduler scripts/tests, contracts, and evidence examples. L1 exclusively owns `infra/**`, Cloud Run Job/Scheduler definitions, IAM, image packaging, and deployment tooling.
4. L1 deploys `python -m recall.scheduler.entrypoint` with workload ADC, bundle `source_commit` in `RECALL_SOURCE_COMMIT`, the actual immutable image digest in `RECALL_IMAGE_DIGEST`, and exact project/preparation hashes. Preview must remain a zero-write, no-client selection check. A source/bundle mismatch or malformed image digest stops before ledger construction.
5. Before each actual date, perform the separately governed lab-local exact preparation step. This is not managed privacy admission and creates no cross-day WatchCase continuity claim.
6. Day-2 acceptance requires the rebuilt image containing the exact Day-1 `first.json` blob and the then-authorized manifest contract. The current 2.1.0 emitter is blocked pending L3 compatibility acknowledgement. Actual managed tick, Firestore read-back, exact source/image binding, inventory reconciliation, and a measured billing/cost line remain required. No estimate may be promoted to a measurement.
7. Continue on the real dates only. Each cumulative manifest history entry must bind `day_index`, actual `executed_at`, matching `selected_for_date`, authoritative `runs_created`, and committed `runs_predicted`.
8. Typed failed/incomplete-day continuation is implemented and locally verified at `7ebc733063e816ac0f4f3b012b6e99d9f055ee8e`. Deployment and production Firestore proof remain blocked by the L3 compatibility and L1 rebuild/repoint gates; do not fabricate an execution timestamp or treat retry configuration as the semantic mechanism.

## 2026-08-25 governance docs batch

1. Terminate RCL-106 under owner residual-risk acceptance after the exposure was contained; preserve the distinction from technical remediation.
2. Reconcile measured L1 `ingress=all`, IAM, inherited-invoker, and application-refusal evidence separately from implemented and deterministically tested endpoint authentication; retain managed reachability as `UNANSWERED`.
3. Append Erratum 001 Revision 4 to correct the unsupported word "signed" to unkeyed SHA-256 `content_hash` plus Git commit provenance without changing prior bytes.
4. Integrate the byte-identical L1 evidence index from `3b45770`; retain every stated limitation.

## 2026-08-25 M2 Day-1 operational slice

Status: completed and live-verified from source commit `14587ac5ab9fa854b4d9b0a2138dad81761bb756`; evidence commit and 2026-08-26 integration review remain.

Day-2 acceptance adds a measured cloud-cost line from the billing source available at execution time. An estimate or inferred daily cost must not be reported as a measurement.

1. Freeze and commit one prediction plus the exact `DAY1_MANUAL` implementation before execution.
2. Admit exactly three SYNTHETIC WatchCases through an accepted signed PrivacyReceipt bound to the exact CloudBoundPayload; select only the one ACTIVE due case at `2026-08-25T15:00:00Z`.
3. Execute twice against live Firestore: first trigger creates one `ScanRun`/`RUN_CREATED`; second creates zero new runs/events.
4. Retain hash-bound read-back evidence with `source_commit`, committed runtime blob hashes, ten atomic checks, direct exit codes, and inventory reconciliation.
5. Claim boundary: working cohort selection plus a durable Day-1 scheduling record only. Managed recurrence and terminal agent execution remain deferred/not claimed.
6. Gate order: tests -> independent code review -> Master Judge -> local commit -> live trigger 1 -> live trigger 2 -> evidence commit -> 2026-08-26 13:00 integration and Master Judge re-review.

## Document control

| Field | Value |
|---|---|
| Owner | aistanbulresearch |
| Status | Last passing external audit: `c86139048d1532c79ed190d0cc98ce2ad878414b`; the published `46afabfcc5716dde6f13e49d118a63b2beacc903` successor audit found two bounded P1 evidence-integrity issues. RCL-011 is `PARTIAL_FAIL_CLOSED / DEFERRED` with seven unchanged residual rows; the owner approved Phase 3 product implementation on 2026-08-21. PR #2 may merge only after the bounded remediation receives a fresh exact-head PASS. Billing display-name selection is owner-reported; linkage and operations remain unverified and separately protected. |
| Baseline date | 2026-08-14 |
| Architecture baseline | Product baseline ADR-0001 through ADR-0008; collaboration process ADR-0009 |
| Contest deadline | 2026-08-31 17:00 PT, corresponding to 2026-09-01 03:00 Europe/Istanbul |
| Internal submission target | 2026-08-31 18:00 Europe/Istanbul |
| Feature freeze | 2026-08-28 18:00 Europe/Istanbul |
| Repository | https://github.com/aistanbulresearch/recall |
| Local checkout | `C:\Users\oacav\OneDrive\Desktop\recall project` |
| Planned hostname | Unresolved: owner wrote `racall.aistanbulresearch.com`; confirm before DNS or deployment configuration |

This is a living plan. Any change to scope, sequencing, dates, acceptance gates, or task status must update this document in the same work unit.

## Current external-gate state

```text
current_external_audit_head=46afabfcc5716dde6f13e49d118a63b2beacc903
current_external_audit_verdict=FAIL
audited_predecessor_head=877c78d06d9b78f3071d17c81232fbc4302f857e
rcl_211=VERIFIED
merge_gate=NO_GO
phase_3_gate=OWNER_APPROVED
external_re_review=REQUIRED
historical_external_pass_head=195422e4d762d68d38e2b7f531cc5b1cd059cdb7
```

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

### Scope boundary and vision

- Product scope is evidence recall for previously uncertain genetic results only. Laboratory workflow control (accessioning, QC, turnaround, report release, LIMS integration, classification) is out of scope; see DEC-2026-08-21-039 and ADR-0006.
- Vision is stated, not implemented: Recall is one "evidence-watch" cell of a future institutional fleet. README and video may carry one pattern sentence ("the same fleet pattern applies to other evidence-dependent institutional decisions"), gated by RCL-904 and RCL-906, never presented as a feature, metric, or roadmap promise.
- The only sanctioned step toward broader institutional use is RCL-315 (second-department consumer) after the 2026-08-24 entrance gate. The owner's separate laboratory-internal pipeline stays outside Recall under DEC-2026-08-15-014.

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
| Architecture | 30% | Four separated roles, Registry-or-pinned-manifest resolution, bounded typed routing, separate tool scopes, append-only artifacts, deterministic controller and policy, denied action, loop recovery, and independent citation audit. |
| Demo and readiness | 30% | Four-minute coherent flow, Cloud Run revision, Vertex/ADK execution, manifest resolution receipt, Firestore transitions, one Logging correlation, derived UI values, fault injection, synthetic-data labels, and a clinician-facing result. |
| Model bonus | `CUT / DEFERRED` | Local Gemma is outside the contest golden path; no bonus claim is planned without a later owner-approved measured experiment. |
| Platform consideration | Critical path plus bounded fallback and auditor extensions | Cloud Run, Vertex AI, Firestore, Logging, and separate agent identities remain in the golden path. Agent Registry receives one authenticated smoke day, then falls back to a pinned Controller-validated manifest. Memory Bank returns through a 2026-08-25 mini-brief limited to admitted operational hints plus parity; Gateway remains `CUT / DEFERRED`, and Model Armor remains planned as access-gated RCL-316. |

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
- ADK Sessions are non-authoritative and cannot satisfy evidence, audit, policy, or state-transition prerequisites. Memory Bank is scheduled for a 2026-08-25 mini-brief limited to admitted operational hints plus enabled/disabled parity; it cannot enter the contest authority path.
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
| RCL-011 | Establish repo-scoped Codex coordinator, custom subagents, Master Judge, and external-auditor cadence | `PARTIAL_FAIL_CLOSED / DEFERRED` | Preserve zero `MECHANISM_PROVED`, two `EXECUTED`, and seven `NOT VERIFIED` without relabeling. These Codex-runtime observability gaps are not dependencies of the Recall product fleet and no longer block local Phase 3 implementation. |

**Phase gate:** another contributor can answer what, why, where, current status, next task, known errors, and proof requirements from repository documents alone.

### Phase 1: Eligibility, access, security, and feasibility, 2026-08-15

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-101 | Re-read binding rules and freeze an eligibility checklist | verified | Hash-pinned checklist, owner eligibility attestation, `individual/solo` entry capacity, and repository authority recorded; live Devpost recheck remains a final-submission control |
| RCL-102 | Decide license and third-party dependency policy | verified | Rules impose no special repo license; owner approved Apache-2.0; policy, register, source notes, and `LICENSE` are present |
| RCL-103 | Freeze the independent-implementation boundary and review only mandatory submission wording | verified, continuous gate | Rules snapshot limits disclosure to incorporated work; DEC-2026-08-15-014 prohibits direct import; reopen if any component is imported or a mandatory field differs |
| RCL-104 | Verify Vertex model, ADK, Cloud Run execution, one-day Registry smoke, separate agent identity, region, quota, and billing | blocked | Owner reports selection `OWNER_REPORTED_SELECTED` for display name `My Billing Account`; no ID is stored, and linkage, credit terms/expiry, permissions, APIs, budgets/alerts, model calls, and spending remain `NOT VERIFIED` and unauthorized. Memory Bank is scheduled for the bounded 2026-08-25 mini-brief; Gateway discovery is deferred, and Model Armor discovery is retained under access-gated RCL-316. |
| RCL-105 | Verify Firestore, Pub/Sub, Cloud Run, Scheduler, Secret Manager, and telemetry access | blocked | Named resource plan exists; project-scoped discovery and read-back await separate owner approval plus verified billing linkage and permissions; no resource creation is authorized |
| RCL-106 | Contain known credential exposure and run repository/history secret scans | terminated by owner decision | Exposure detected and contained on 2026-08-22; repository and history secret scans clean; DEC-2026-08-25-044 ends the recurring tracking item under residual-risk acceptance. |
| RCL-107 | Benchmark local Gemma E2B Q4_0 startup, JSON validity, p50/p95 latency, and memory | `CUT / DEFERRED` | Not part of the contest golden path; reconsider only after final submission evidence is complete |
| RCL-108 | Resolve hostname spelling and document Hetzner/DNS ownership | `CUT / DEFERRED` | Hosted proof will use Cloud Run; custom Hetzner/DNS work is outside the contest golden path |
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
| RCL-209 | Freeze Firestore, ADK Sessions, and bounded Memory Bank authority and retention contracts | in-progress | Firestore remains authoritative; the 2026-08-25 Memory Bank mini-brief permits admitted operational hints only and requires enabled/disabled parity |
| RCL-210 | Freeze Cloud Run, Vertex/ADK, Registry fallback, separate identity, and observability failure contracts | in-progress, scope-reduced | Gateway is `CUT / DEFERRED`; Model Armor is outside the golden path but retained under RCL-316; Phase 1 access evidence remains required for the minimum platform |
| RCL-211 | Package Phase 2 and material collaboration successors for exact-head external review | verified | Historical review passed at `195422e4d762d68d38e2b7f531cc5b1cd059cdb7`; `877c78d` and c8 failed on distinct evidence-integrity defects; exact c861 successor passed with no actionable P0-P3 finding |

**Phase gate:** satisfied for local product implementation. F-01 through F-08 are resolved at corrected-design/source-package scope, the replay package verifies offline, the c861 follow-up audit passed, and the owner approved Phase 3 on 2026-08-21. The separate 46af P1 remediation blocks PR #2 merge, not product implementation.

### 72-hour recovery plan, 2026-08-21 to 2026-08-24

1. Hours 0-2: timebox the two P1 corrections; add only bounded guards for unauthorized `MECHANISM_PROVED`, `EXECUTED` outside the two allowlisted surfaces, and billing/cloud promotion beyond `OWNER_REPORTED_SELECTED`. Record any residual synchronized-change risk as an external-audit boundary; build no general prose-verification framework.
2. Hours 0-2, separately protected: verify billing linkage and, only with explicit owner authorization, enable Vertex AI, Firestore, Cloud Run, and Cloud Logging before model integration begins.
3. Hours 2-24: initialize the product package; implement strict golden-path contracts, Firestore abstraction/emulator, Controller, Policy Gate, and fixture-driven `NO_ACTION`, `ABSTAIN`, and `REVIEW_REQUIRED` tests. Decide F-09 with a deterministic Controller-level `ToolAuthorization` request attributed to Assessor identity plus a fake-citation `CAPTURED_REPLAY`; both institutional inputs are `SYNTHETIC`, never `MOCK`.
4. Hours 24-48: integrate Gemini and ADK Watcher, Assessor, and independent Citation Auditor; execute positive replay and two negative controls; measure end-to-end and segment latency before retaining the 75-second storyboard allocation (F-16).
5. Hours 48-72: deploy the minimum path to Cloud Run and Firestore, emit sanitized Cloud Logging correlation, and render the success/fault comparison on one web surface.
6. The 2026-08-23 evening checkpoint is owner-controlled. If the local three-outcome path or billing linkage is unavailable, pivot to captured replay + deterministic Controller/Policy Gate + one Gemini agent + Cloud Run.

Golden-path contract scope includes F-11/F-14: one `failure_code -> fact -> reason_code` registry, explicit `HALTED` fields, and approximately twelve derived UI fields. Atomic data-mode badges and run-level `mode_set` remain mandatory and are cut last.

Prize targeting by evidence fit remains Best Architectural Design first, Individual/Hobbyist second, Fleet third, and Honorable Mention fourth. This prize-fit preference is distinct from the owner-approved active M1 execution path, which is Fleet-first as of 2026-08-23. External-auditor probability estimates are directional opinions only; they are not project measurements and must not appear as expected scores or submission claims.

`docs/project/AUDITOR_ACTION_REGISTER_2026-08-21.md` is the binding item-by-item coverage map for the owner-supplied external auditor report. Its immediate conditions, seven degree-oriented extensions, daily schedule, non-cuttable invariants, five video proofs, milestone evidence, and five risks are all part of this plan. No report item may be removed or silently replaced without an owner decision.

### Phase 3: Deterministic vertical skeleton plus web surface, superseded by the 2026-08-21 recovery plan

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-301 | Initialize Python/uv and web workspaces with locked dependencies | in-progress | Workspaces and lockfiles exist; clean-clone install, exact direct/transitive inventory, license gate, notices, and CycloneDX or SPDX SBOM remain |
| RCL-302 | Implement common contracts and provenance hashing with TDD | implemented and locally verified | Unit tests include malformed and unknown fields |
| RCL-303 | Implement Ledger API and Firestore emulator adapter | implemented and locally verified | Append-only, producer authorization, compare-and-set, and live Firestore fallback tests pass |
| RCL-304 | Implement deterministic Workflow Controller | implemented and locally verified | Transition, duplicate, budget, loop, and terminal-failure tests pass |
| RCL-305 | Implement Pub/Sub request/outbox/dead-letter topology locally | not-started | Duplicate and retry fixture proof |
| RCL-306 | Implement deterministic Policy Gate truth table | implemented and locally verified | Identical artifacts produce identical outcomes in local tests |
| RCL-307 | Build the initial Recall web shell and live run timeline | not-started | UI reads backend artifacts and shows fixture labels |
| RCL-308 | Demonstrate fixture-driven `NO_ACTION`, `ABSTAIN`, and `REVIEW_REQUIRED` without LLMs | implemented and locally verified | Deterministic fixture runs cover the three policy outcomes plus technical `HALTED` |
| RCL-309 | Implement durable `WatchCase` scheduling, short `ScanRun` leases, and separate `ReviewTask` lifecycle | partial | Lease, CAS, idempotency, separate lifecycle contracts, and date-isolated Day-N scheduling are locally verified; L1 managed deployment, actual Day-2 execution, and terminal agent processing remain pending |
| RCL-310 | Package required run evidence in a machine-readable `RunEvidenceManifest` | proposed; owner decision required | Coordinator proposal only; if approved, it binds run ID, deployed revision, trace ID, `mode_set`, input/output artifact hashes, terminal state, simulated task count, guardrail activation counters, and measured latency. The auditor's underlying evidence requirements remain mandatory even if this packaging proposal is declined |

**Recovery gate:** the minimum authority path runs locally without models, all three terminal outcomes are visible from fixtures, mode badges and `mode_set` are derived, and no displayed result is hard-coded. Durable week-sequence orchestration is not required.

### 2026-08-24 conditional stretch entrance gate

No extension starts unless the golden path has executable evidence locally and on Cloud Run for all three terminal outcomes, one success run, one fault run, and authoritative Firestore read-back by the evening of 2026-08-24. Correlated sanitized telemetry, exact data-mode provenance, and measured latency remain mandatory milestone evidence. Every extension stays in the plan while the entrance gate is closed; the gate cannot be passed by screenshots or design documents alone.

| ID | Conditional extension | Status | Admission and acceptance evidence |
|---|---|---|---|
| RCL-311 | Synthetic scale funnel | planned 2026-08-25 after entrance gate | Run 100-200 fixed synthetic WatchCases and report scanned, candidate, audited, and simulated-task counts through `UtilityEvaluation`, with exact denominators and Wilson 95% confidence intervals; label the result exploratory and make no clinical-performance claim |
| RCL-312 | Correlated Cloud Trace and fleet dashboard | planned 2026-08-25 after entrance gate | Render sanitized agent health, runs, denials, and `HALTED`; the same deployed revision, run ID, trace ID, and Firestore facts appear in the app and Google Cloud proof |
| RCL-313 | Accelerated Week 0/3/6 continuity | planned 2026-08-26 after entrance gate | Execute three genuine separately receipted ScanRuns for one WatchCase, emit `NO_ACTION` on unchanged runs, prove F-12 as-of cursor behavior, label acceleration explicitly, and prohibit seeded outcomes |
| RCL-314 | Blog, social, and bounded Gemma bonuses | planned 2026-08-28 after entrance gate | Publish blog and social evidence before the last day; add Gemma only as a small visible critical-path-independent use with measured incremental value |
| RCL-315 | Agent Registry runtime resolution plus second-department consumer | planned 2026-08-26; access-gated after entrance gate | Publish versioned manifests, resolve them at runtime, emit `RegistryResolutionReceipt`, and let a second small institutional flow discover and reuse Citation Auditor. If preview access fails on the same-day smoke, execute the pinned fallback and disclose F-13 honestly |
| RCL-316 | Per-role service accounts, IAM denial, and Model Armor adversarial run | planned 2026-08-26; access-gated after entrance gate | Prove IAM-level forbidden tool denial and zero forbidden downstream effect; under the separately approved credential posture, use Model Armor to block a poisoned source document when access is available |
| RCL-317 | Agent Runtime deployment in addition to Cloud Run | planned 2026-08-24; rule/access-gated after entrance gate | Ask the organizer because Rules do not bind this FAQ bonus; if confirmed and accessible, deploy and capture exact runtime/revision proof |
| RCL-318 | `LIVE_PUBLIC` ClinVar evidence over a synthetic case | planned 2026-08-26 after entrance gate | Fetch current public evidence live, label it `LIVE_PUBLIC`, bind it to a synthetic case, and preserve the non-clinical simulated-action boundary |

Fleet-target minimum is RCL-311, RCL-313, and RCL-314 plus at least one real implementation from RCL-315 or RCL-316. The auditor identifies RCL-311 through RCL-314 as the realistic solo set, but RCL-315 through RCL-318 remain planned and gated rather than removed. Memory Bank returns only through the 2026-08-25 admitted-hints/parity mini-brief; Gateway, remote A2A, and Hetzner remain base-plan cuts. Gemma, Model Armor, and Agent Runtime remain outside the golden path but are retained as the explicit conditional extensions above.

### Phase 4: Minimum privacy boundary folded into the golden path; prior schedule superseded

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-401 | Implement strict local input schema, minimizer, token vault interface, and deterministic detectors | not-started | Unit tests by identifier class |
| RCL-402 | Implement local Gemma span-only adapter and deterministic redaction | `CUT / DEFERRED` | Deterministic minimization and strict schema remain; Gemma is not a contest dependency |
| RCL-403 | Implement outbound scan, quarantine, and signed PrivacyReceipt | not-started | Seeded identifier never reaches cloud-bound fixture |
| RCL-404 | Build bilingual synthetic privacy corpus and preregister splits | `CUT / DEFERRED` | Use the fixed synthetic golden-path fixtures only; broader corpus work follows submission |
| RCL-405 | Measure deterministic baseline and Gemma incremental contribution | `CUT / DEFERRED` | No Gemma contribution claim will be made in the contest submission |
| RCL-406 | Add privacy boundary and quarantine evidence to the web flow | not-started | UI fields derive from PrivacyReceipt; redacted text is not logged |

**Recovery gate:** the demo uses only fixed synthetic inputs, visibly labels data mode, and proves deterministic minimization/quarantine before any cloud-bound payload. No Gemma claim is required.

### Phase 5: Evidence monitoring and historical replay plus web timeline, 2026-08-22 to 2026-08-23

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-501 | Implement allowlisted PubMed connector with rate, retry, cache, and drift controls | not-started | Recorded fixtures plus one labeled live smoke |
| RCL-502 | Implement ClinVar comparison connector and normalization | `CUT / DEFERRED` | Second connector is outside the golden path; retain one source-attributed replay path |
| RCL-503 | Implement historical replay connector with source hashes | not-started | Exact replay produces deterministic snapshot |
| RCL-504 | Implement observation, snapshot, and temporal delta artifacts | not-started | Hash/provenance and no-change tests |
| RCL-505 | Render previous/current evidence and delta in the web timeline | not-started | UI values trace to artifact IDs |
| RCL-506 | Verify one evidence signal and negative controls | not-started | Preregistered comparison report, no cherry-picking |
| RCL-507 | Enforce and display `SYNTHETIC`, `CAPTURED_REPLAY`, `LIVE_PUBLIC`, and `MOCK` modes | not-started | Schema, API, artifact, and UI mode assertions |

**Phase gate:** the same historical replay reliably produces a source-attributed delta, while negative controls remain `NO_ACTION`.

### Phase 6: Minimum agent fleet plus observability; prior schedule superseded

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-601 | Implement Fleet Coordinator with typed bounded RoutingPlan only | not-started | Forbidden-route and invalid-schema tests |
| RCL-602 | Implement Evidence Watcher with connector-only tool scope | not-started | Denied interpretation and arbitrary-URL tests |
| RCL-603 | Implement Evidence Assessor with counter-evidence and uncertainty contracts | not-started | No decision authority; grounded artifact references |
| RCL-604 | Implement independent Citation Auditor | not-started | Fake PMID, mismatched metadata, omitted counter-evidence tests |
| RCL-605 | Deploy the minimum ADK fleet to Cloud Run with separate revisions and identities | not-started | Cloud Run revision, IAM boundary, and correlation evidence |
| RCL-606 | Attempt authenticated Agent Registry publication and resolution for one day | timeboxed fallback | Registry catalog and selected-version receipt, or a typed fallback receipt for the pinned Controller-validated manifest |
| RCL-607 | Implement sanitized cross-service tracing | not-started | One trace without clinical content |
| RCL-608 | Show fleet roles, versions, scopes, and live route on the web surface | not-started | UI reads catalog/run receipts, no decorative hard-coding |
| RCL-609 | Implement Memory Bank admission, retrieval, expiry, scope, and Firestore-conflict controls | planned 2026-08-25 mini-brief | Admit operational hints only; Firestore remains authoritative, memory is excluded from policy facts, and enabled/disabled parity is mandatory |
| RCL-610 | Enforce separate identity and Controller allowlists without widening authority | scope-reduced | Gateway is `CUT / DEFERRED`; allowed/denied tool receipts remain mandatory and RCL-316 adds access-gated IAM/Model Armor proof after the entrance gate |

**Recovery gate:** a Cloud Run ADK run produces typed artifacts and one sanitized correlation trail; a forbidden capability is visibly denied. Registry resolution is preferred but the documented pinned-manifest fallback is acceptable after the one-day smoke.

### Phase 7: Governance and recovery, 2026-08-26

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-701 | Complete claim-level audit and removal behavior | not-started | Fabricated citation cannot reach trusted output |
| RCL-702 | Complete terminal abstention and operations incidents | not-started | Source, schema, audit, and budget failures produce typed receipts |
| RCL-703 | Complete duplicate suppression and notification outbox | not-started | Zero duplicate review tasks under repeated delivery |
| RCL-704 | Complete loop and repeated-state recovery | not-started | Worker loop terminates within budget with no task |
| RCL-705 | Add fault-injection controls and proof states to the web surface | not-started | Jury can see cause, blocked action, and terminal result |
| RCL-706 | Complete memory poisoning, stale-memory, and cross-scope recovery | planned 2026-08-25 mini-brief | Reject poisoned, stale, cross-scope, and authority-conflicting hints; prove byte/task parity with memory disabled while Firestore remains authoritative |
| RCL-707 | Complete untrusted-source injection and Model Armor outage recovery | scope-reduced plus conditional extension | Structured-only restriction and deterministic `ABSTAIN` with a typed receipt remain mandatory; actual Model Armor activation/adversarial evidence is retained under access-gated RCL-316 |

**Recovery gate:** every golden-path guardrail has visible activation evidence and all dangerous incomplete paths end without a clinical task. The bounded Memory Bank mini-brief is scheduled but is not a golden-path or policy dependency; Model Armor remains an access-gated post-entrance extension rather than a golden-path dependency.

### Phase 8: Evaluation, deployment, and narrative integration, 2026-08-27

| ID | Task | Status | Acceptance evidence |
|---|---|---|---|
| RCL-801 | Run frozen privacy, citation, reliability, and utility protocols | not-started | Artifact manifests and honest limitations |
| RCL-802 | Audit every UI number and badge against source artifacts | not-started | Derived-value audit has zero unresolved manual values |
| RCL-803 | Complete jury-language UX and remove avoidable genetics jargon | not-started | Non-specialist comprehension review |
| RCL-804 | Deploy the minimum web/API and agent path to Cloud Run | not-started | Visible `.run.app` URL, revision IDs, health/read-back, and rollback runbook |
| RCL-805 | Connect approved hostname and verify TLS/DNS | `CUT / DEFERRED` | Cloud Run URL is sufficient for contest proof; Hetzner/custom DNS is outside the golden path |
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

### Superseded legacy checkpoints

The earlier 25/50/75% dates and phase sequence below are historical planning context. The 72-hour recovery sequence and the owner-controlled 2026-08-23 evening pivot now govern execution; deferred items cannot re-enter silently.

### 25% checkpoint, 2026-08-18 (superseded)

- The deterministic state path and web timeline must be visible.
- Identify score-matrix rows with no evidence path.
- Cut at least one non-critical item if the critical path is late.

### 50% checkpoint, 2026-08-22 (superseded)

- Privacy proof must be measured, not merely implemented.
- Historical replay must be selected and reproducible.
- Agent platform access must no longer be speculative.

### 75% checkpoint, 2026-08-26 (superseded)

- Managed fleet run, independent audit, and abstention must work.
- The four-minute demo must already be rehearsable.
- No new subsystem begins after this checkpoint.

## 7. Scope cut order

### Committed recovery cuts

The following remain outside the contest golden path: local Gemma, Model Armor, Agent Gateway, remote A2A, Week 0/3/6 orchestration, Hetzner deployment, the second connector, and nonessential visual polish. Memory Bank is separately scheduled for a 2026-08-25 mini-brief limited to admitted operational hints and parity; it is not evidence, policy, or workflow authority. This base-path boundary does not delete the auditor's conditional extension plan: Gemma bonus is RCL-314, accelerated Week 0/3/6 is RCL-313, Model Armor is RCL-316, Registry plus the second consumer is RCL-315, and Agent Runtime is RCL-317. Agent Registry receives one authenticated smoke day; otherwise use a pinned Controller-validated manifest with a visible fallback receipt. Every state remains visible in the score and demo ledgers.

Golden-path substitutes are Controller allowlists plus separate identities instead of Gateway, strict structured input plus deterministic `ABSTAIN` before any conditional Model Armor evidence, Firestore-only authority even when bounded Memory Bank hints are enabled, one source-attributed replay connector, a pinned Controller-validated manifest if the one-day Registry smoke fails, and Cloud Run instead of Hetzner. These substitutes protect delivery but do not erase RCL-314 through RCL-317.

If the remaining schedule slips, cut only in this order:

1. Advanced reviewer filters, accounts, and administration.
2. Cloud object versioning beyond normalized snapshots and hashes.
3. Multiple historical cases beyond the minimum proof set.
4. Visual polish that does not increase comprehension.

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
5. Approve, revise, or decline the coordinator-proposed `RunEvidenceManifest` packaging; the external auditor's underlying evidence requirements do not depend on this decision.

## 10. Current next action

Execute the full auditor register without unilateral cuts. The first product work is RCL-301/RCL-302 with F-09, F-11, F-14, mode propagation, and three deterministic outcomes. In parallel, restore `gcloud` and complete the separately protected billing/API action as the overdue hour-zero prerequisite. Preserve the seven RCL-011 residual rows. The published 46af remediation must be owner-published and receive fresh exact-head PASS before the required PR #2 merge and `feature/rcl-30x-*` product branch transition. `RunEvidenceManifest` remains a separate coordinator proposal pending owner decision.
