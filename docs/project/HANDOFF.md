# Recall Handoff

## Current 2026-08-26 compressed-cycle checkpoint

- Active branch is `feature/rcl-3xx-core`; current product commit is `2d8bebbe97794865f77f037dea518a39e8f75e38` (tree `9d95719e9c8fb403780f7b26ee6ab5bef3331696`). This L2 work unit performed no push, merge, cloud action, or `infra/**` edit. The owner reports no compressed cycle ran; independent cloud read-back is `NOT VERIFIED`.
- Locked plan SHA-256 is `5f18998f11c17b8feef52f90edd9319532a36d525dbea9e9a40538425a28dfa4`; c1-c6 start 20:40/21:10/21:40/22:10/22:40/23:10Z. Dates, predictions, and policies are unchanged.
- Regenerated bundle SHA-256 is `5a69eb4394f64c1e666aeb624cac3e4e312b3758a9e48f311a8cb0eef610f7dd`; source commit `2d8bebbe97794865f77f037dea518a39e8f75e38`, 462 cases, five replay observations, no persisted signing key.
- Current namespaces are `dev_recall_m2_compressed_p5f18998f11c1_<cycle>_<logical-date>_`. The old unscoped namespaces' contents, untouched/abandoned state, and absence of accepted manifest references are `OWNER_REPORTED`; independent cloud inventory/read-back is `NOT VERIFIED`. See `docs/evidence/COMPRESSED_PLAN_ITERATIONS.md`.
- L1 handoff: set `RECALL_SCHEDULER_MODE=COMPRESSED_V3`; package the exact plan/bundle; use scheduler-SA only; set timeout 1200 seconds; derive one-shot triggers from the plan; re-prepare every prefix with current code; run Cloud Run `--verify-prefix YYYYMMDD` for every session prefix before c1; do not create c6 unless the content-addressed headroom receipt accepts exact c1-c5 read-back.
- L3 handoff: `CohortDayManifest 3.0.0` is a separate compressed contract. Rebind the parser/fixtures to cycle fields, plan hash, actual execution time, retained per-row `trigger_code`/`scheduled_for`, `headroom_receipt_id`, and `schedule_mode`. Derive the visible accelerated/machine-triggered label only from `schedule_mode`; the demo bundle may contain only the final manifest.
- Exact-current-tree local evidence is focused 27/27 with direct exit 0; plan/bundle hashes and the VCV-bound bundle inputs were verified. Bounded deterministic core 345/345, platform 259/259, privacy 140/140, web 48/48, and the mode-unspecified Firestore run are predecessor-tree evidence and were `NOT RERUN` on `2d8bebbe97794865f77f037dea518a39e8f75e38`. Independent product-diff review and Master Judge PASS.
- Runtime boundary: deployment, workload identity, prefix preflight, Firestore writes/read-back, Cloud Scheduler triggers, c1-c6 observations, c6 headroom decision, billing, and final demo binding are `NOT VERIFIED`.

## Current 2026-08-26 coordinator checkpoint

- Active branch is `feature/rcl-3xx-core`; current local product commit is `7ebc733063e816ac0f4f3b012b6e99d9f055ee8e` (tree `9742b3a97ec4792115c75e7290df529fb30854ec`). It adds typed failed-day continuation without changing frozen Day-1 evidence or `infra/**`.
- `CohortDayManifest 2.1.0` is emit-only; exact 2.0.0 wires have a strict legacy-read parser. History rows add required `execution_status` and `failure_receipt_id`; missing days use deterministic `CohortDayFailureReceipt 1.0.0` artifacts.
- The scheduler reconciles zero prior runs/events, walks the registered predecessor chain backward, checks deterministic predecessor IDs/dates, and resolves inherited receipts at their origin ledger before current-day writes. Wrong predecessor, dangling receipt, partial state, and backend-error negatives are locally verified fail-closed.
- Final evidence: focused 72/72, bounded core 318/318, platform excluding the unchanged token-process file 234/234, privacy 140/140, web 48/48; each evidence-bearing command exited 0. Independent code review and Master Judge PASS. The full platform parent-shell exit and production Firestore continuation are not claimed.
- Deployment is prohibited until L3 acknowledges 2.1.0 compatibility against exact commit `7ebc733063e816ac0f4f3b012b6e99d9f055ee8e`; current acknowledgement is `NOT_RECEIVED`. L1 must then rebuild/repoint before any production run. No push, merge, or cloud mutation occurred.
- The successor docs commit carries evidence-state-correct gateway acceptance criteria and the 17-rule Evidence Discipline mirror. Preserve the seven unrelated dirty paths.

## Current 2026-08-25 coordinator checkpoint

- Active branch is `feature/rcl-3xx-core`. Staged cohort expansion is commit `c65ee3d55524caf1d2d9d697c9bff712e35bca82`; the L2 managed Day-N implementation is commit `367637b12e92eda0c2aa54c8bdc12af3adbfe99d`. Older branch/head text below is historical and must not override this block.
- Day-1 remains the live historical record from source `14587ac5ab9fa854b4d9b0a2138dad81761bb756`; its frozen code and evidence were not changed. The new path contains 12 cases, five exact RCL-205 replay anchors, and committed Day2/3/4 predictions 3/2/4.
- L1 entrypoint: `python -m recall.scheduler.entrypoint`; deployment contract: `docs/platform/COHORT_JOB_ENTRYPOINT.md`; preparation bundle SHA-256: `c460340e75bf186980c8e7a938c5c5e0b4da89599890b2864af7dabdb4ffe841`. L2 made no `infra/**` change.
- Adversarial successor `435fd46035c7a9e9dca7f06b2264799b52cffa30` replaces the incorrect Day-1 free literal with a blob-bound `CohortHistoryReceipt 1.0.0` and bumps `CohortDayManifest 1.0.0 -> 2.0.0` with required `image_digest`. L1 must rebuild and repoint the job image, package the exact committed Day-1 `first.json`, set `RECALL_SOURCE_COMMIT=c65ee3d55524caf1d2d9d697c9bff712e35bca82`, and set `RECALL_IMAGE_DIGEST` to the actual deployed `sha256:<64 hex>` digest. Source mismatch fails before ledger construction.
- Base-product verification remains historical. Current successor verification is focused 36/36, bounded core 299/299, platform 234/234 excluding the known environment-bound token process file, privacy 140/140, web 48/48, and independent code-review PASS. The fresh live-Firestore attempt hung in auth/subprocess handling and is not promoted to PASS.
- Next gate: L1 supplies Cloud Run Job/Scheduler/IAM/deploy files, validates preview, and deploys the exact source. The actual Day-2 tick must occur on 2026-08-26 with Firestore read-back, source/image binding, inventory reconciliation, and measured billing/cost evidence.
- Honest boundary: deployment, workload identity, actual managed Day-2 execution, and billing are `NOT VERIFIED`; managed admission, cross-day WatchCase continuity, and terminal agent execution are not claimed. Do not alter the seven unrelated worktree entries.
- Failed/incomplete-day typed continuation is deferred to Day-3 morning. Current missing-prior behavior remains fail-closed; L1's retry 1 setting is partial protection, not the permanent semantic implementation.

## Incoming agent control block

This is the canonical handover for the next Recall coordinator. Do not create a second competing handover file.

### Exact checkout and remote state

- Open the next Codex task with `C:\Users\oacav\OneDrive\Desktop\recall project` as the primary workspace so repo-scoped skills, custom agents, and writable-role tests load under the correct permission root.
- Branch: `feature/rcl-010-fleet-architecture`.
- Local HEAD, origin branch, and PR #2 are published at `46afabfcc5716dde6f13e49d118a63b2beacc903`, whose exact-head audit returned `FAIL` with two bounded P1 findings. `c86139048d1532c79ed190d0cc98ce2ad878414b` is the last passing audited head; c8 and `877c78d` remain historical failures. Resolve all live SHAs before any later protected action.
- PR #2 author is `aistanbulresearch` with `OWNER` association. It remains open and unmerged.
- Do not reset, checkout, clean, stash, amend, rebase, or discard the current worktree. The local documentation changes belong to the owner.

### Current external-gate state

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

```graphify-snapshot
snapshot_scope=POINT_IN_TIME
snapshot_timestamp=2026-08-19T04:45:37Z
graph_nodes=254
graph_edges=276
graph_communities=49
graph_concepts=140
manifest_sources=75/75
missing_sources=0
broken_endpoints=0
policy_gate_nodes=1
policy_gate_incident_edges=5
graph_sha256=973089FA8EF6F333843879D213D3E3C721079BAB5234B95549F1DEBB920245AE
report_sha256=7F49F479F74FBF2424D255D632AB038C4EFDB7BF25873C9D45181DF63CE45F96
report_build_commit=c8be1947
historical_snapshots=240/260/44/129;231/248/45/120;242/258/48/131@74/74
evidence_scope=NAVIGATION_AND_ARTIFACT_INTEGRITY_ONLY
scheduler_runtime=NOT_VERIFIED
```

### Canonical handover publication

The canonical handover package originally contained seven tracked files. The owner's 2026-08-18 publication authorization adds `docs/project/DECISION_LOG.md`, making the exact approved package eight tracked files:

1. `AGENTS.md`
2. `docs/evaluation/reports/2026-08-17--codex-collaboration-smoke.md`
3. `docs/project/STATUS.md`
4. `docs/project/HANDOFF.md`
5. `docs/project/MASTER_PLAN.md`
6. `docs/project/ERROR_LOG.md`
7. `docs/project/WORK_LOG.md`
8. `docs/project/DECISION_LOG.md`

They record the owner-authorized final Graphify refresh and this handover. All eight were committed and pushed owner-only at checkpoint `788b56bcbef3d543f483d7f5a99033aba2d23ea9`. The later governance correction distinguishes the fixed-scope recurring automation authorization from separately approved manual refreshes. Because a commit cannot embed its own SHA, always use the live commands below to resolve the final successor head and worktree state. `graphify-out/` remains Git-ignored.

The owner separately authorized the exact canonical-handover commit/push, its publication-evidence successor, and the subsequent read-only external-auditor request on 2026-08-18. This does not authorize merge, Phase 3, cloud, billing, destructive, hostname, Graphify refresh, or later publication actions.

### Latest verified evidence

- Local collaboration validation binds four exact custom profiles, twenty-one LF-normalized evidence hashes, zero `MECHANISM_PROVED`, two `EXECUTED`, and seven unchanged `NOT VERIFIED` runtime classifications, plus exact negative sets of twenty-five transcript, forty-one Graphify-governance, and eighty-eight aggregate collaboration mutations. Four final clause-local cases reject count, allowlisted-subject, and billing-negation camouflage after synchronized hash refresh; external review remains the trust boundary for coordinated document-and-validator changes.
- Last passing external audit: `PASS` at `c86139048d1532c79ed190d0cc98ce2ad878414b`. The current published head `46afabfcc5716dde6f13e49d118a63b2beacc903` returned `FAIL` with bounded P1 findings. RCL-211 remains verified; Phase 3 is owner-approved, while merge and external re-review remain gated.
- The sole Recall-root successor is `docs/evaluation/reports/2026-08-18--rcl-011-recall-root-runtime.md`. During the live session, the Worker file was observed as 53 bytes with SHA-256 `BC91A143...EFFF7` and the Smart file as 661 bytes with SHA-256 `3339E8A5...7C15`.
- The ignored run root was later removed, so neither raw artifact is independently inspectable from the repository or checkout; the report and hashes are documentation only. The exact thread-limit refusal was likewise observed live without retained authoritative control-plane evidence.
- Canonical checkpoint `788b56b` was read back owner-only: commit author, committer, and GitHub actors were `aistanbulresearch`; message body, trailers, and notes were empty; immediate and 20-second delayed PR comments, review comments, reviews, statuses, and check runs were all zero.
- Recall-root runtime matrix: partial and fail-closed. No mechanism-level row is proved; only profile discovery and Judge verdict formatting are executed. Seven residual Worker-write/thread-cap/read-only/Smart-profile/effort/no-spawn/protected-order rows remain `NOT VERIFIED`; the ignored raw artifacts and immutable parent tool/control-plane logs were not retained, so the Runtime Judge's stronger `PASS` provenance assessment is not adopted.
- Graphify evidence is bound only by the canonical dated `graphify-snapshot` block above. It preserves earlier roots as history and must not be read as durable current truth; run the read-only quality gate and final-root reconciliation for live values.
- Four replay JSON files still produce zero-node warnings: `PMID39779848.data-availability-linkage.json`, `PMID39779848.esummary.json`, `PMID39779857.esummary.json`, and `HISTORICAL_REPLAY_SOURCE_MANIFEST.json`. Keep each warning visible; do not convert source-manifest coverage into semantic-node completeness.
- Product code, managed execution, privacy mechanism, scientific validation, clinical validation, and demo execution remain unimplemented or unverified as stated in STATUS.

### First commands after the mandatory read

Use one preflight order: read `AGENTS.md`, return to this incoming-agent control block, then read STATUS, MASTER_PLAN, and COLLABORATION_SYSTEM; invoke `$recall-collaboration` after those five surfaces. Every path or range in the longer `Read first` list is mandatory before implementation or a phase decision; the minimum preflight is sufficient for initial read-only state verification and the owner approval question. Then run:

```powershell
Set-Location 'C:\Users\oacav\OneDrive\Desktop\recall project'
git rev-parse --show-toplevel
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/feature/rcl-010-fleet-architecture
gh api repos/aistanbulresearch/recall/pulls/2 --jq '.head.sha'
python scripts\validation\verify_recall_collaboration.py
python scripts\validation\test_recall_collaboration_validator.py
git diff --check
```

The two live remote commands are read-only but may require network approval from the execution sandbox. Before any protected action, require local HEAD, the live origin branch result, and the live PR head to match; if they do not, stop and report.

For Recall graph traversal, never use raw `graphify query`, `graphify explain`, or `graphify path`. Use:

```powershell
& 'C:\Users\oacav\graphify-all-repos\gfvenv\Scripts\python.exe' `
  'C:\Users\oacav\graphify-all-repos\graphify_agent_runner.py' `
  query '<question>' --graph '.\graphify-out\graph.json'
```

The owner authorizes the registered `Graphify-Refresh-All` task's fixed inspected two-hour scope, including change-triggered Gemini extraction/labeling with `gemini-3.5-flash-lite`, `recall-concepts-v1`, and token budget 5000. Unchanged corpus and profile must skip Gemini. Manual/ad-hoc refresh and any change to cadence, corpus scope, destination, backend/model/profile, token budget, logging, principal, or privilege require new explicit owner authorization. This is a governance authorization plus inspected source behavior, not runtime proof of scheduler enforcement.

### Required next-gate order

1. Read `AGENTS.md`, return to this incoming-agent control block, then read STATUS, MASTER_PLAN, and COLLABORATION_SYSTEM; invoke `$recall-collaboration`; then run the listed read-only local/live state and validator commands. Read every remaining enumerated path or range before implementation or a phase decision.
2. Last passing external audit: `PASS` at `c86139048d1532c79ed190d0cc98ce2ad878414b`; current published head `46afabfcc5716dde6f13e49d118a63b2beacc903` returned `FAIL`. Retain failed c8 and `877c78d` as historical failures and the exact `195422e` historical result only.
3. Preserve the seven RCL-011 residual rows without relabeling. RCL-011 is `PARTIAL_FAIL_CLOSED / DEFERRED` and no longer blocks local product implementation.
4. Keep ignored artifacts under `temp/collaboration-smoke/<run-id>/`; do not create another runtime report, retain raw tool/environment logs, or promote absence/policy refusal into mechanism proof.
5. Phase 3 local product implementation is owner-approved. PR #2 merge still requires the bounded P1 remediation, fresh exact-head PASS, and the already-issued owner merge instruction.

### Stop and ask the owner

Stop before any GitHub write, commit, push, merge, destructive action, cloud change, billing decision, external publication, new Graphify semantic transmission, hostname/DNS choice, or use of a credential outside the existing approved workflow. RCL-106 is terminated under the owner's residual-risk acceptance after the exposure was contained; do not inspect, print, copy, or persist the credential.

The 2026-08-18 owner instruction authorizes the read-only external-auditor request only after the exact publication successor is stable and read back. Future auditor requests remain owner-protected.

## Read first

1. `AGENTS.md`
2. `docs/project/HANDOFF.md`, including the incoming-agent control block
3. `docs/project/STATUS.md`
4. `docs/project/MASTER_PLAN.md`
5. `docs/project/COLLABORATION_SYSTEM.md`
6. `docs/project/OPERATING_PRINCIPLES.md`
7. `docs/architecture/TARGET_ARCHITECTURE.md`
8. `docs/governance/DEPENDENCY_LICENSE_POLICY.md`
9. `docs/governance/THIRD_PARTY_REGISTER.md`
10. `docs/demo/FOUR_MINUTE_STORYBOARD.md`
11. `docs/demo/WEB_INFORMATION_ARCHITECTURE.md`
12. `docs/demo/DERIVED_VALUE_REGISTRY.md`
13. `docs/security/THREAT_MODEL.md`
14. `docs/contracts/ARTIFACT_CONTRACTS.md`
15. `docs/contracts/LIFECYCLE_STATE_MACHINES.md`
16. `docs/policy/DETERMINISTIC_POLICY_SPEC.md`
17. `docs/evaluation/EVALUATION_PROTOCOLS.md`
18. `docs/evaluation/HISTORICAL_REPLAY_CASE.md`
19. `docs/evaluation/HISTORICAL_REPLAY_CANDIDATE_LEDGER.md`
20. `docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json`
21. `docs/adr/ADR-0001-durable-watchcase-and-short-scan-runs.md` through `ADR-0009-repo-scoped-codex-collaboration.md`
22. `docs/evaluation/reports/2026-08-17--phase2-external-audit-triage.md`
23. `docs/evaluation/reports/2026-08-17--github-auditor-rereview.md`
24. `docs/project/ERROR_LOG.md`
25. `docs/evidence/CLAIM_EVIDENCE_LEDGER.md`
26. `docs/evidence/GUARDRAIL_PROOF_MATRIX.md`
27. `docs/evidence/DEMO_EVIDENCE_LOG.md`
28. `docs/evidence/SCORE_MATRIX.md`
29. `docs/project/AUDITOR_ACTION_REGISTER_2026-08-21.md`

## Current objective

Establish Recall as a prize-competitive hackathon project with a managed, auditable, privacy-preserving multi-agent critical path and a web experience built concurrently with the backend.

## Current state

- Date: 2026-08-21.
- Phase: 72-hour recovery; RCL-011 is `PARTIAL_FAIL_CLOSED / DEFERRED`, Phase 3 local implementation is owner-approved, billing/cloud operations remain separately protected, and PR #2 merge awaits fresh exact-head PASS.
- GitHub: `https://github.com/aistanbulresearch/recall`, private; PR #2 is open and unmerged. The audits at `877c78d` and c8 failed on distinct evidence-integrity defects; exact successor c861 passed with no actionable P0-P3 finding.
- Local repository: `C:\Users\oacav\OneDrive\Desktop\recall project`.
- Product implementation: not started.
- Prize-fit preference remains Best Architectural Design, then Individual/Hobbyist, Fleet, and Honorable Mention; it is not a measured probability or score. The owner-approved active M1 execution path is Fleet-first as of 2026-08-23.
- No privacy, scientific, reliability, or production claim has been validated.
- Documentation baseline passed local structure, link, identity, ignore-rule, commit, push, and remote read-back checks.
- Google Cloud CLI, user auth, ADC, and five required SDK imports passed; no cloud resource was created.
- A dedicated Recall project is `ACTIVE` under the single organization; CLI and ADC target it.
- Billing account selection is `OWNER_REPORTED_SELECTED` for display name exactly `My Billing Account`; no billing account ID is stored. Billing linkage, credit terms or expiry, permissions, API states, budget/alerts, resource creation, model calls, and spending remain `NOT VERIFIED` and unauthorized pending separate owner approval.
- A read-only cloud preflight on 2026-08-21 could not locate the `gcloud` launcher in the coordinator shell or checked standard user locations. Treat live billing and API state as `NOT VERIFIED`, not disabled; no cloud mutation occurred.
- Local Gemma runtime and model artifacts were not found in checked standard locations.
- RCL-101 is verified: owner eligibility and authority are confirmed, entry capacity is `individual/solo`, and no sensitive personal details are stored. A live Devpost recheck remains only as a final-submission control.
- RCL-102 is verified. The Rules require rights and license compliance but no special repository license; the owner approved Apache-2.0 and `LICENSE` is present.
- Current Google Cloud terms prohibit Generative AI Services for clinical purposes. The contest build is therefore a synthetic, non-clinical research prototype; future clinical deployment is blocked behind a separate terms and regulatory gate.
- The prior Phase 2 exact-head GitHub auditor re-review passed at `195422e4d762d68d38e2b7f531cc5b1cd059cdb7`. Material collaboration changes then failed at `877c78d` on validator coverage/normative state; c8 failed on transcript integrity/stale Graphify wording; c861 passed the exact-head re-review. PR #2 remains open and unmerged; product and cloud behavior remain unverified.
- RCL-207 and RCL-208 are verified design gates. The implementation must follow the 3:45 storyboard, single-screen evidence surface, and deterministic derived-value registry.
- RCL-201 through RCL-204 and RCL-206 are verified corrected-design gates for F-01 through F-06. Candidate authority, memory parity, citation failure, evaluated policy reasons, mode composition, cursor recovery, and their executable test obligations are synchronized but not implemented.
- ADR-0007 separates technical `HALTED` from Policy Gate `ABSTAIN`, routes no-change through Policy Gate, and keeps privacy quarantine outside the cloud run lifecycle.
- RCL-205 is verified locally at frozen-source-package level. Ten exact captures, seven source-derived chronology checks, twelve semantic checks, eleven rights checks, one exact XLSX row, and byte/semantic/root/traversal/rights/hash-role/junction fault rejection pass offline. Product replay remains unimplemented.
- RCL-211 is verified. The historical `195422e` review passed, `877c78d` and c8 failed on successive evidence-integrity defects, and exact successor c861 passed external review.
- RCL-011 is `PARTIAL_FAIL_CLOSED / DEFERRED`. `$recall-collaboration`, four custom profiles, a configured three-thread cap, ADR-0009, and mutation-tested structural validation are implemented. The Recall-root run has zero `MECHANISM_PROVED`, two `EXECUTED`, and seven `NOT VERIFIED` classifications. Preserve those seven residual rows without promotion; they are not a dependency for Phase 3 product implementation.
- The first two independent collaboration reviews returned `FAIL`; exact-schema, YAML, link, canonical negative-action, evidence classification, acceptance-matrix, baseline-metadata, and profile-name remediations are implemented. The local remediation harness now rejects exactly twenty-three named defects, including the original profile/config/report/displayed-state mutations plus protected-evidence suffix/conflict promotions and inverse/composite current-state mutations.
- An earlier collaboration follow-up returned `PASS`, but later pre-push review superseded it with `FAIL`. Subsequent remediation and publication led through failed `877c78d` and c8 audits. `c86139048d1532c79ed190d0cc98ce2ad878414b` is the last passing audited head; the current `46afabfcc5716dde6f13e49d118a63b2beacc903` audit returned `FAIL`. RCL-011 is deferred with seven runtime mechanisms/telemetry rows still open.
- The canonical dated `graphify-snapshot` block near the top is the sole normative count/hash/build record. Run the read-only gate for live values. The fixed-scope recurring task is authorized; manual refresh and scope changes are not standing-authorized. Four replay JSON files still produced zero-node warnings without missing manifest coverage; raw Graphify traversal remains prohibited.
- ERR-2026-08-17-086: exposure detected and contained on 2026-08-22.

## Locked decisions

- Product name is Recall.
- The web demo is a first-class product entity and evolves with every vertical slice.
- The jury story begins with human workload, not genetics jargon.
- Safety is expressed as structural inability, not a claim that an agent is well behaved.
- Every displayed number is derived from an authoritative artifact.
- Missing data is unknown and must fail loudly where integrity is required.
- LLMs never hold classification, notification, or terminal workflow authority.
- Four roles are separated: Fleet Coordinator, Evidence Watcher, Evidence Assessor, Citation Auditor.
- A deterministic Workflow Controller owns routing enforcement and execution budgets.
- A deterministic Policy Gate owns terminal workflow outcomes.
- Controller uses technical `HALTED`, never a fabricated policy outcome, when trusted policy execution or ledger integrity is unavailable.
- Commit, push, tag, and PR ownership must resolve only to `aistanbulresearch`; no co-author trailers.
- Recall is implemented independently in this repository. Other codebases may inform abstract engineering patterns or failure-mode questions, but no code, tests, fixtures, schemas, prompts, configuration, UI, documentation, artifact, or history may be copied.
- Do not create a voluntary public `pre-existing work` section when no component is imported. Review the exact wording only if a binding rule or submission field explicitly asks about prior work, inspiration, or reuse.
- A durable `WatchCase` carries multi-week continuity; each `ScanRun` is short, bounded, idempotent, and independently auditable; `ReviewTask` has a separate human lifecycle.
- Firestore remains authoritative. ADK Sessions are non-authoritative; Memory Bank implementation is `CUT / DEFERRED`.
- Any future Memory Bank work requires a new owner scope decision and cannot enter Policy Gate inputs or change outcome/task count.
- Cloud Run with Vertex/ADK, Firestore, Logging, and separate identities is the contest critical path. The auditor action register also retains Agent Registry plus a second consumer, IAM/Model Armor governance, and Agent Runtime as access/rule-gated post-entrance extensions. Registry failure uses a pinned Controller-validated manifest fallback. Gateway and Memory Bank remain `CUT / DEFERRED`.
- Deterministic local logic owns minimization, redaction, and egress approval. Local Gemma and Model Armor remain outside the golden path but stay planned as conditional RCL-314/RCL-316 extensions; strict structured input and deterministic `ABSTAIN` remain mandatory.
- Each artifact declares one atomic mode; each run declares its transitive mode set. The core synthetic-case plus captured-replay composition is explicit, not a silent mismatch.
- The contest deployment is non-clinical and synthetic-only for institutional records. De-identification does not itself authorize clinical-purpose use.

## Immediate next step

Execute every row in `AUDITOR_ACTION_REGISTER_2026-08-21.md` without unilateral removal. Start RCL-301/RCL-302 with F-09/F-11/F-14, mode propagation, and three deterministic outcomes while restoring the cloud launcher and completing the separately protected hour-zero billing/API action. Retain all seven post-entrance extensions in the plan. Obtain owner authorization for exact publication of the independently reviewed P1 remediation, then fresh exact-head PASS and the required PR #2 merge before product work moves to `feature/rcl-30x-*`. `RunEvidenceManifest` is only a coordinator proposal pending owner decision. RCL-106 is terminated by DEC-2026-08-25-044 after the owner accepted the residual risk and recorded that the exposure was contained; reopen only for a new exposure, unauthorized use, material credential-scope change, or new owner decision.

## Known blocker

The owner wrote `racall.aistanbulresearch.com` while the product and repository are `recall`. Do not create DNS, TLS, reverse-proxy, or application configuration until spelling is confirmed.

The owner reports selecting the billing display name `My Billing Account`, state `OWNER_REPORTED_SELECTED`; no billing account ID is stored. This is not proof of linkage, credit terms/expiry, permissions, API state, budgets/alerts, resource creation, model calls, or spending. Do not link billing, enable APIs, create resources, call models, or incur spending without separate explicit owner approval and verification.

## Operational notes

- GitHub CLI is authenticated as `aistanbulresearch` when run with permission to access its local config.
- An initial sandboxed `gh` preflight failed because the restricted process could not read the GitHub CLI config; the approved retry succeeded.
- Do not expose GitHub tokens, cloud credentials, SSH material, or Hetzner host details in logs or committed files.
- Domain creation remains an owner action when the deployment phase is reached.
- GitHub currently rejects repository rulesets for this private repository without Pro. Squash-only merge, automatic merged-branch deletion, PR branch updates, and Issues are enabled; direct-push avoidance is process-enforced until a ruleset can be activated.
- Cursor's GitHub integration added an unsolicited disabled-Bugbot upsell comment again immediately after the `05ff0b59` push. The exact comment was deleted; two bounded rereads were visibly clean. Recurrence is proof that disablement was not established.
- Historical note: the owner authorized only the completed 2026-08-17 remediation push, subject to owner-only identity, staged-tree evidence, remote read-back, and delayed actor scans. That authorization is consumed and does not permit any current push; bot recurrence still fails the gate.
- ERR-080 records repeated HTTP 503 failures while refreshing the stale PR #2 verification summary. The owner web-interface fallback succeeded and API read-back confirmed the corrected current body.
- Historical external audit: `PASS` at `195422e4d762d68d38e2b7f531cc5b1cd059cdb7`. Collaboration audits at `877c78d` and c8 failed. `c86139048d1532c79ed190d0cc98ce2ad878414b` is the last passing audited head; current head `46afabfcc5716dde6f13e49d118a63b2beacc903` returned `FAIL`. PR #2 remains unmerged.
- ERR-2026-08-17-086: exposure detected and contained on 2026-08-22. Do not inspect credential-bearing config files.

## Stop conditions

Stop and report if:

- a contest rule or disclosure obligation is ambiguous;
- a required managed service is unavailable;
- a test passes without proving the target mechanism ran;
- a model output is about to become authoritative;
- a UI value cannot be traced to a typed artifact;
- real clinical data or a secret is found;
- a commit would use an identity other than `aistanbulresearch`.
