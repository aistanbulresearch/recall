# Recall Handoff

## Incoming agent control block

This is the canonical handover for the next Recall coordinator. Do not create a second competing handover file.

### Exact checkout and remote state

- Open the next Codex task with `C:\Users\oacav\OneDrive\Desktop\recall project` as the primary workspace so repo-scoped skills, custom agents, and writable-role tests load under the correct permission root.
- Branch: `feature/rcl-010-fleet-architecture`.
- Local HEAD, origin branch, and PR #2 were independently re-audited at `c8be19476c24672fbf65d4dbf767fa8144360d22`. The external verdict was `FAIL`; `877c78d06d9b78f3071d17c81232fbc4302f857e` is the audited predecessor, not the current checkout. Resolve all three SHAs live before any later protected action.
- PR #2 author is `aistanbulresearch` with `OWNER` association. It remains open and unmerged.
- Do not reset, checkout, clean, stash, amend, rebase, or discard the current worktree. The local documentation changes belong to the owner.

### Current external-gate state

```text
current_external_audit_head=c8be19476c24672fbf65d4dbf767fa8144360d22
current_external_audit_verdict=FAIL
audited_predecessor_head=877c78d06d9b78f3071d17c81232fbc4302f857e
rcl_211=IN_PROGRESS
merge_gate=NO_GO
phase_3_gate=NO_GO
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

- Before the final documentation freeze, collaboration validation passed with four exact custom profiles, seventeen LF-normalized evidence hashes, three `REPORT_DERIVED` plus six `NOT VERIFIED` runtime classifications, and exact negative sets of twenty-five transcript, forty-one Graphify-governance, and fifty aggregate collaboration mutations.
- Independent staged-tree code review returned `PASS` on that package, but the next Master Judge correctly returned `FAIL` after this handoff and STATUS changed without regenerating their full-document hashes. That failure supersedes the earlier green baseline for publication purposes.
- This frozen handoff makes no Master Judge `PASS` claim about itself. Regenerate the two normative-document hashes, rerun all six staged-tree gates and independent code review, then require a fresh stable-tree Master Judge verdict before any protected action.
- Canonical checkpoint `788b56b` was read back owner-only: commit author, committer, and GitHub actors were `aistanbulresearch`; message body, trailers, and notes were empty; immediate and 20-second delayed PR comments, review comments, reviews, statuses, and check runs were all zero.
- Recall-root runtime matrix: still open. The current bound classification set contains three `REPORT_DERIVED` and six `NOT VERIFIED`; they are not runtime proof.
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
2. Inspect the authoritative source transcript at `docs/evaluation/transcripts/2026-08-18--github-auditor-collaboration-fail-source-final.md`, its non-authoritative summary, and the second external `FAIL` at `c8be194`; rerun the transcript, Graphify-governance, collaboration-state, and mutation gates.
3. Publish only the owner-authorized remediation successor after `aistanbulresearch` identity and exact staged-tree checks, then perform immediate and 20-second delayed actor/surface read-back.
4. Request the owner-authorized read-only external GitHub re-review only against that final exact live SHA, never `d5777b5`, `788b56b`, predecessor `877c78d`, or failed successor `c8be194`.
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

- Date: 2026-08-20.
- Phase: Phase 0 collaboration-evidence remediation; Phase 1 smoke is partial and stopped at billing selection; current exact-head external audit failed; Phase 3 is `NO-GO`.
- GitHub: `https://github.com/aistanbulresearch/recall`, private; PR #2 is open and unmerged. The predecessor audit at `877c78d` failed; its owner-only remediation successor `c8be19476c24672fbf65d4dbf767fa8144360d22` was re-audited and also returned `FAIL` on distinct evidence-integrity defects. The second remediated successor will require a new exact-head re-review.
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
- The prior Phase 2 exact-head GitHub auditor re-review passed at `195422e4d762d68d38e2b7f531cc5b1cd059cdb7`. Material collaboration changes then failed at `877c78d` on validator coverage/normative state; the remediation successor `c8be194` failed on transcript integrity/stale Graphify wording. PR #2 remains open and unmerged; product and cloud behavior remain unverified.
- RCL-207 and RCL-208 are verified design gates. The implementation must follow the 3:45 storyboard, single-screen evidence surface, and deterministic derived-value registry.
- RCL-201 through RCL-204 and RCL-206 are verified corrected-design gates for F-01 through F-06. Candidate authority, memory parity, citation failure, evaluated policy reasons, mode composition, cursor recovery, and their executable test obligations are synchronized but not implemented.
- ADR-0007 separates technical `HALTED` from Policy Gate `ABSTAIN`, routes no-change through Policy Gate, and keeps privacy quarantine outside the cloud run lifecycle.
- RCL-205 is verified locally at frozen-source-package level. Ten exact captures, seven source-derived chronology checks, twelve semantic checks, eleven rights checks, one exact XLSX row, and byte/semantic/root/traversal/rights/hash-role/junction fault rejection pass offline. Product replay remains unimplemented.
- RCL-211 is in progress. The historical `195422e` review passed, while the `877c78d` audit and `c8be194` re-review failed on successive evidence-integrity defects; second remediation and a new exact-head external `PASS` are required.
- RCL-011 is in progress. `$recall-collaboration`, four custom profiles with exact stable identifier names, a three-thread cap, ADR-0009, and mutation-tested structural validation are implemented. The VUS-root nested observations are `REPORT_DERIVED`, not runtime proof. Every Recall-root row in `COLLABORATION_SYSTEM.md` must pass before verification.
- The first two independent collaboration reviews returned `FAIL`; exact-schema, YAML, link, canonical negative-action, evidence classification, acceptance-matrix, baseline-metadata, and profile-name remediations are implemented. The local remediation harness now rejects exactly twenty-three named defects, including the original profile/config/report/displayed-state mutations plus protected-evidence suffix/conflict promotions and inverse/composite current-state mutations.
- An earlier collaboration follow-up returned `PASS`, but the later pre-publish Master Judge superseded it with `FAIL`. Four independent code-review cycles closed those findings, and the collaboration infrastructure through `d5777b5` was published owner-only. The exact eight-file canonical handover then passed its remediated Master Judge gate and was published owner-only at `788b56b`; this publication-evidence successor records that read-back. RCL-011 remains in progress and every Recall-root runtime row is still open.
- The canonical dated `graphify-snapshot` block near the top is the sole normative count/hash/build record. Run the read-only gate for live values. The fixed-scope recurring task is authorized; manual refresh and scope changes are not standing-authorized. Four replay JSON files still produced zero-node warnings without missing manifest coverage; raw Graphify traversal remains prohibited.
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

Regenerate the frozen STATUS/HANDOFF hashes, rerun the exact staged-tree and independent code-review gates, and obtain a fresh stable-tree Master Judge `PASS`. Only then run the owner-identity gates and publish one owner-only successor if every protected gate passes; request the authorized read-only external re-review against that exact live SHA. Until it passes, merge and Phase 3 remain `NO-GO`. Then complete every remaining RCL-011 runtime row. RCL-106 credential rotation remains recommended and open.

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
- The prior Phase 2 exact-head GitHub auditor re-review passed at `195422e4d762d68d38e2b7f531cc5b1cd059cdb7`; later collaboration audits at `877c78d` and `c8be194` failed on successive evidence-integrity defects and require second remediation plus a new exact-head re-review. PR #2 remains unmerged.
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
