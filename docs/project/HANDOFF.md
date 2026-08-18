# Recall Handoff

## Incoming agent control block

This is the canonical handover for the next Recall coordinator. Do not create a second competing handover file.

### Exact checkout and remote state

- Open the next Codex task with `C:\Users\oacav\OneDrive\Desktop\recall project` as the primary workspace so repo-scoped skills, custom agents, and writable-role tests load under the correct permission root.
- Branch: `feature/rcl-010-fleet-architecture`.
- Local HEAD, origin branch, and PR #2 were independently audited at `877c78d06d9b78f3071d17c81232fbc4302f857e` on 2026-08-18. The external verdict was `FAIL`; resolve all three SHAs live before any later protected action.
- PR #2 author is `aistanbulresearch` with `OWNER` association. It remains open and unmerged.
- Do not reset, checkout, clean, stash, amend, rebase, or discard the current worktree. The local documentation changes belong to the owner.

### Current external-gate state

```text
current_external_audit_head=877c78d06d9b78f3071d17c81232fbc4302f857e
current_external_audit_verdict=FAIL
rcl_211=IN_PROGRESS
merge_gate=NO_GO
phase_3_gate=NO_GO
external_re_review=REQUIRED
historical_external_pass_head=195422e4d762d68d38e2b7f531cc5b1cd059cdb7
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

They record the owner-authorized final Graphify refresh, the per-run Graphify approval rule, and this handover. All eight were committed and pushed owner-only at checkpoint `788b56bcbef3d543f483d7f5a99033aba2d23ea9`. This document's publication-evidence successor records the exact read-back; because a commit cannot embed its own SHA, always use the live commands below to resolve the final successor head and worktree state. `graphify-out/` remains Git-ignored.

The owner separately authorized the exact canonical-handover commit/push, its publication-evidence successor, and the subsequent read-only external-auditor request on 2026-08-18. This does not authorize merge, Phase 3, cloud, billing, destructive, hostname, Graphify refresh, or later publication actions.

### Latest verified evidence

- Collaboration structural validator: local remediation `PASS`, four exact custom profiles and twelve evidence hashes.
- Collaboration mutation harness: local remediation `PASS`, exactly twenty-three named mutation classes rejected; the final independent code review also passed 42 of 42 disposable-copy probes.
- The first eight-file staged-tree Master Judge verdict was `FAIL`; after Graphify and index-state remediation, the fresh stable-tree re-review returned `PASS` with no remaining staged-tree findings. That verdict covered exact scope, current Graphify artifacts, structural and mutation checks, secret/trailer scans, local owner identity, and evidence boundaries. The coordinator separately verified live local/origin/PR equality and owner identity before the protected action.
- Canonical checkpoint `788b56b` was read back owner-only: commit author, committer, and GitHub actors were `aistanbulresearch`; message body, trailers, and notes were empty; immediate and 20-second delayed PR comments, review comments, reviews, statuses, and check runs were all zero.
- Recall-root runtime matrix: still open. The current bound classification set contains three `REPORT_DERIVED` and six `NOT VERIFIED`; they are not runtime proof.
- Graphify refresh: the pre-label quality gate passed at 240 nodes, 260 edges, 44 communities, and 129 concepts. An intermediate post-label snapshot recorded 231/248/45/120, but the ignored graph JSON and root report were later rewritten. Direct current reconciliation now finds 242 nodes, 258 edges, 48 communities, 131 concepts, 74 of 74 tracked sources represented, zero missing sources, and zero broken edges. A fresh read-only post-label quality-gate execution passed with one connected `Policy Gate` node and five incident edges. The exact producer of the later ignored-artifact rewrite was not independently identified.
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

The owner explicitly authorized the completed 2026-08-18 Graphify transmission of changed private Recall content to Gemini semantic extraction. Treat that as authorization for the completed run, not as standing permission for future transmissions.

### Required next-gate order

1. Read `AGENTS.md`, return to this incoming-agent control block, then read STATUS, MASTER_PLAN, and COLLABORATION_SYSTEM; invoke `$recall-collaboration`; then run the listed read-only local/live state and validator commands. Read every remaining enumerated path or range before implementation or a phase decision.
2. Inspect the locally implemented P1 validator/evidence and P2 current-state remediation recorded in `docs/evaluation/reports/2026-08-18--github-auditor-collaboration-fail.md`; its structural validator, 23 typed mutations, independent code review, and fresh stable-tree Master Judge pass locally.
3. Publish only the owner-authorized remediation successor after `aistanbulresearch` identity and exact staged-tree checks, then perform immediate and 20-second delayed actor/surface read-back.
4. Request the owner-authorized read-only external GitHub re-review only against that final exact live SHA, never `d5777b5`, `788b56b`, or failed head `877c78d`.
5. In the Recall-root task, execute every remaining RCL-011 runtime-matrix row with retained literal sanitized transcripts and exact before/after Git status. Use ignored `temp/collaboration-smoke/<run-id>/` only for ephemeral write/denial artifacts. The predecessor is `docs/evaluation/reports/2026-08-17--codex-collaboration-smoke.md`; create exactly one successor at `docs/evaluation/reports/2026-08-18--rcl-011-recall-root-runtime.md` for sanitized literal transcripts, commands, hashes, and before/after status. Do not create competing runtime reports, persist secrets or unsanitized raw traces, or upgrade configuration/report-derived observations into runtime proof.
6. Do not begin Phase 3 product implementation or merge PR #2 until the new external re-review, RCL-011 gate, and applicable owner approvals pass.

### Stop and ask the owner

Stop before any GitHub write, commit, push, merge, destructive action, cloud change, billing decision, external publication, new Graphify semantic transmission, hostname/DNS choice, or use of a credential outside the existing approved workflow. The exposed GitHub credential remains an open risk; do not inspect, print, copy, or persist it.

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

## Current objective

Establish Recall as a prize-competitive hackathon project with a managed, auditable, privacy-preserving multi-agent critical path and a web experience built concurrently with the backend.

## Current state

- Date: 2026-08-18.
- Phase: Phase 0 collaboration-evidence remediation; Phase 1 smoke is partial and stopped at billing selection; current exact-head external audit failed; Phase 3 is `NO-GO`.
- GitHub: `https://github.com/aistanbulresearch/recall`, private; PR #2 is open and unmerged. Exact audited head `877c78d06d9b78f3071d17c81232fbc4302f857e` was owner-only with clean current surfaces, but the independent audit returned `FAIL`; the remediated successor will require a new exact-head re-review.
- Local repository: `C:\Users\oacav\OneDrive\Desktop\recall project`.
- Product implementation: not started.
- No privacy, scientific, reliability, or production claim has been validated.
- Documentation baseline passed local structure, link, identity, ignore-rule, commit, push, and remote read-back checks.
- Google Cloud CLI, user auth, ADC, and five required SDK imports passed; no cloud resource was created.
- A dedicated Recall project is `ACTIVE` under the single organization; CLI and ADC target it.
- The project is billing-disabled. Two open billing accounts exist with no safe automatic organization/name match.
- Local Gemma runtime and model artifacts were not found in checked standard locations.
- RCL-101 is verified: owner eligibility and authority are confirmed, entry capacity is `individual/solo`, and no sensitive personal details are stored. A live Devpost recheck remains only as a final-submission control.
- RCL-102 is verified. The Rules require rights and license compliance but no special repository license; the owner approved Apache-2.0 and `LICENSE` is present.
- Current Google Cloud terms prohibit Generative AI Services for clinical purposes. The contest build is therefore a synthetic, non-clinical research prototype; future clinical deployment is blocked behind a separate terms and regulatory gate.
- The prior Phase 2 exact-head GitHub auditor re-review passed at `195422e4d762d68d38e2b7f531cc5b1cd059cdb7`. Material collaboration changes were published later; their external audit at `877c78d06d9b78f3071d17c81232fbc4302f857e` returned `FAIL` on P1 validator coverage and P2 normative state. PR #2 remains open and unmerged; product and cloud behavior remain unverified.
- RCL-207 and RCL-208 are verified design gates. The implementation must follow the 3:45 storyboard, single-screen evidence surface, and deterministic derived-value registry.
- RCL-201 through RCL-204 and RCL-206 are verified corrected-design gates for F-01 through F-06. Candidate authority, memory parity, citation failure, evaluated policy reasons, mode composition, cursor recovery, and their executable test obligations are synchronized but not implemented.
- ADR-0007 separates technical `HALTED` from Policy Gate `ABSTAIN`, routes no-change through Policy Gate, and keeps privacy quarantine outside the cloud run lifecycle.
- RCL-205 is verified locally at frozen-source-package level. Ten exact captures, seven source-derived chronology checks, twelve semantic checks, eleven rights checks, one exact XLSX row, and byte/semantic/root/traversal/rights/hash-role/junction fault rejection pass offline. Product replay remains unimplemented.
- RCL-211 is in progress. The historical `195422e` review passed, but the current `877c78d` exact-head audit failed; remediation and a new exact-head external `PASS` are required.
- RCL-011 is in progress. `$recall-collaboration`, four custom profiles with exact stable identifier names, a three-thread cap, ADR-0009, and mutation-tested structural validation are implemented. The VUS-root nested observations are `REPORT_DERIVED`, not runtime proof. Every Recall-root row in `COLLABORATION_SYSTEM.md` must pass before verification.
- The first two independent collaboration reviews returned `FAIL`; exact-schema, YAML, link, canonical negative-action, evidence classification, acceptance-matrix, baseline-metadata, and profile-name remediations are implemented. The local remediation harness now rejects exactly twenty-three named defects, including the original profile/config/report/displayed-state mutations plus protected-evidence suffix/conflict promotions and inverse/composite current-state mutations.
- An earlier collaboration follow-up returned `PASS`, but the later pre-publish Master Judge superseded it with `FAIL`. Four independent code-review cycles closed those findings, and the collaboration infrastructure through `d5777b5` was published owner-only. The exact eight-file canonical handover then passed its remediated Master Judge gate and was published owner-only at `788b56b`; this publication-evidence successor records that read-back. RCL-011 remains in progress and every Recall-root runtime row is still open.
- The owner explicitly authorized transmission of changed private Recall content to Gemini semantic extraction for one completed run. Its pre-label gate passed at 240/260/44/129. The later ignored-artifact sequence included an intermediate 231/248/45/120 snapshot and the current 242/258/48/131 root. Fresh read-only reconciliation and a post-label quality-gate execution passed at the current root with 74/74 represented sources, 0 missing sources, 0 broken edges, and a connected `Policy Gate`. The exact producer of the post-record rewrite remains unknown. Four replay JSON files still produced zero-node warnings without missing manifest coverage. The no-stamp query surfaced the final collaboration remediations; raw Graphify traversal remains prohibited.
- ERR-2026-08-17-086 records an exposed GitHub credential without its value. Rotation remains recommended, but the owner explicitly deferred it and accepted the risk for the exact collaboration-infrastructure commit/push on 2026-08-17.

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
- Firestore remains authoritative. ADK Sessions and Memory Bank are explicitly non-authoritative.
- Memory Bank is allowed only for admitted operational context with provenance, scope, TTL, contradiction checks, and retrieval receipts.
- Rejected or conflicting memory is ignored and receipted; it is absent from Policy Gate inputs and cannot change outcome or task count.
- Agent Runtime and Agent Registry are target critical-path components. Identity, Gateway, Memory Bank, and Model Armor require Phase 1 access and failure-behavior gates.
- Local Gemma proposes residual identifier spans; deterministic local logic approves redaction and egress. Model Armor screens untrusted cloud-side source content when feasible.
- Each artifact declares one atomic mode; each run declares its transitive mode set. The core synthetic-case plus captured-replay composition is explicit, not a silent mismatch.
- The contest deployment is non-clinical and synthetic-only for institutional records. De-identification does not itself authorize clinical-purpose use.

## Immediate next step

Complete the exact staged-tree and owner-identity gates for the locally passing, independently code-reviewed, and Master-Judge-approved P1/P2 remediation; publish one owner-only successor only if every protected gate passes; then request the authorized read-only external re-review against that exact live SHA. Until it passes, merge and Phase 3 remain `NO-GO`. Then complete every remaining RCL-011 runtime row. RCL-106 credential rotation remains recommended and open.

## Known blocker

The owner wrote `racall.aistanbulresearch.com` while the product and repository are `recall`. Do not create DNS, TLS, reverse-proxy, or application configuration until spelling is confirmed.

The dedicated Recall project is active, but two open billing accounts are available and neither has a safe automatic match. Do not enable APIs or create service smoke resources until the owner identifies the billing account.

## Operational notes

- GitHub CLI is authenticated as `aistanbulresearch` when run with permission to access its local config.
- An initial sandboxed `gh` preflight failed because the restricted process could not read the GitHub CLI config; the approved retry succeeded.
- Do not expose GitHub tokens, cloud credentials, SSH material, or Hetzner host details in logs or committed files.
- Domain creation remains an owner action when the deployment phase is reached.
- GitHub currently rejects repository rulesets for this private repository without Pro. Squash-only merge, automatic merged-branch deletion, PR branch updates, and Issues are enabled; direct-push avoidance is process-enforced until a ruleset can be activated.
- Cursor's GitHub integration added an unsolicited disabled-Bugbot upsell comment again immediately after the `05ff0b59` push. The exact comment was deleted; two bounded rereads were visibly clean. Recurrence is proof that disablement was not established.
- Historical note: the owner authorized only the completed 2026-08-17 remediation push, subject to owner-only identity, staged-tree evidence, remote read-back, and delayed actor scans. That authorization is consumed and does not permit any current push; bot recurrence still fails the gate.
- ERR-080 records repeated HTTP 503 failures while refreshing the stale PR #2 verification summary. The owner web-interface fallback succeeded and API read-back confirmed the corrected current body.
- The prior Phase 2 exact-head GitHub auditor re-review passed at `195422e4d762d68d38e2b7f531cc5b1cd059cdb7`; the later collaboration audit at `877c78d06d9b78f3071d17c81232fbc4302f857e` failed and requires remediation plus a new exact-head re-review. PR #2 remains unmerged.
- A design-review subagent exposed a GitHub PAT from global Codex config in its private tool log. Do not repeat the value or inspect credential-bearing config. The owner deferred rotation and accepted the risk for the exact 2026-08-17 collaboration-infrastructure publish; this is not remediation or standing authorization for later Git writes.

## Stop conditions

Stop and report if:

- a contest rule or disclosure obligation is ambiguous;
- a required managed service is unavailable;
- a test passes without proving the target mechanism ran;
- a model output is about to become authoritative;
- a UI value cannot be traced to a typed artifact;
- real clinical data or a secret is found;
- a commit would use an identity other than `aistanbulresearch`.
