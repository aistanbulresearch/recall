# External Exact-Head Collaboration Audit

- Date: 2026-08-18
- Repository: `aistanbulresearch/recall`
- Branch: `feature/rcl-010-fleet-architecture`
- Audited local, origin, and PR #2 head: `877c78d06d9b78f3071d17c81232fbc4302f857e`
- Prior audited checkpoint: `195422e4d762d68d38e2b7f531cc5b1cd059cdb7`
- Canonical handover checkpoint: `788b56bcbef3d543f483d7f5a99033aba2d23ea9`
- External task: `01a01671-1a00-70a2-af25-70f429682465`
- Source turn: `01a01671-21d7-7953-a911-6b060c889361`
- Mode: independent read-only exact-head audit; no repository, GitHub, Graphify, cloud, or publication mutation
- Verdict: `FAIL`

This report is a faithful repository transcription of the external task's final answer. The separate task and source turn are the raw source of record; this file normalizes its local links to repository paths and does not upgrade its evidence classifications.

## Findings

### P1: Protected-action evidence can be falsely promoted while the structural validator still passes

- Evidence: `docs/project/COLLABORATION_SYSTEM.md` requires complete leaf no-spawn and protected-action verification. `docs/evaluation/reports/2026-08-17--codex-collaboration-smoke.md` says protected-operation stopping is not runtime-tested, but `scripts/validation/verify_recall_collaboration.py` omits that runtime surface from its bound classification set.
- Executed evidence: The clean structural validator and existing twelve mutations passed. The auditor changed the protected-action evidence line in memory only to `MECHANISM_PROVED`; validation still returned `PASS`, exit 0, without a filesystem change.
- Impact: A green structural gate can coexist with an unsupported mechanism-level claim for owner-protected operations or external-auditor side-effect controls. This breaks the evidence-honesty gate.
- Required correction: Bind protected-action stopping and complete four-role leaf no-spawn enforcement as explicit `NOT VERIFIED` classifications. Include them in derived counts, current-state documents, and the mutation harness.
- Verification: Disposable or in-memory mutations promoting either surface to `EXECUTED` or `MECHANISM_PROVED` must fail with typed classification errors. Clean validation must still pass with every required runtime surface accounted for.

### P2: Current normative records retain stale pending-gate statements

- Evidence: `docs/adr/ADR-0008-external-audit-corrections.md` still called external follow-up pending. `docs/project/STATUS.md` said a new pre-publish Master Judge verdict remained required, while `docs/project/HANDOFF.md` recorded that gate as passed.
- Executed evidence: Direct exact-head source search reproduced the contradictory present-tense statements.
- Impact: A successor can misidentify completed gates as open and the current failed external gate as passed, weakening the canonical-state contract.
- Required correction: Close current ADR, status, plan, and handoff wording with exact completed checkpoints. Preserve time-accurate pending/pass language only in dated historical reports and append-only log entries.
- Verification: A deterministic current-state contract and fresh-reader search must agree that the `877c78d` audit failed, RCL-211 is in progress, merge and Phase 3 are `NO-GO`, and a new exact-head external re-review is required after remediation.

## Scope and exact identity

- PR base and live main: `459a0225d32e8aa7ba5c9d1a333bb5cc7028a5ff`.
- Local, live origin branch, and PR #2 head matched `877c78d06d9b78f3071d17c81232fbc4302f857e` initially and finally.
- PR #2 was open and unmerged; owner and association were `aistanbulresearch` and `OWNER`.
- The full PR contained thirteen commits. The audit emphasized all five commits after `195422e4` and the five-file publication successor after `788b56b`.
- The worktree remained clean.

## Executed checks and evidence classifications

- `STRUCTURAL`: collaboration validator passed with four exact profiles, eleven hashes, configured thread cap three, and the existing seven bound runtime statements. Official skill validation passed.
- `EXECUTED`: the twelve-mutation collaboration harness passed; `git diff --check` passed; `codex.cmd features list` reported `multi_agent stable true`.
- `REPORT_DERIVED`: historical nested Scout, Worker, and Judge observations only; no raw immutable transcript exists.
- `NOT VERIFIED`: every Recall-root runtime row remains open, including Worker write, Smart Worker behavior, effective Judge effort, concurrency enforcement, complete leaf no-spawn, and protected-operation stopping.
- `MECHANISM_PROVED`: only the existing twelve validator defect classes and bounded RCL-205 frozen-package fault controls, not protected actions.
- The RCL-205 verifier and full fault harness passed within frozen-source-package scope. This does not prove product replay.
- High-confidence tracked and PR-patch secret-signature scans returned zero. This is not credential rotation or remediation.

## Graphify reconciliation and boundary

Read-only artifact reconciliation found 242 nodes, 258 edges, 48 communities, 131 concepts, 74 of 74 manifest sources represented, zero missing manifest sources, zero broken edges, and one `Policy Gate` node with five incident edges. Root graph hash was `853D9B8F18CACEC23190A94217CFD7DEC57F9C977C60E2D687D08C4E47CF6D38`; report hash was `4F1A3108F99280C4945F455C7D475447CDA80B3D40A088E91A23CE97E49DDBD3`. No refresh or external transmission occurred.

The graph reports `built_at_commit` `d5777b528d141b0d82489d5a3f7fcc5b4a377bbd`, behind the audited head, and the later ignored-artifact rewrite producer remains unknown. The graph is stale navigation and artifact-integrity context only; it does not prove that this remediation or the audited collaboration behavior is implemented.

## Remote publication evidence

- `788b56b` contained exactly the eight approved handover paths; `877c78d` contained exactly the five publication-record paths.
- All thirteen remote commits resolved author, committer, name, email, and GitHub actor only to `aistanbulresearch`.
- Commit bodies, Git notes, and prohibited attribution trailers were zero.
- PR issue comments, review comments, reviews, statuses, and check runs were zero at the audit snapshot.
- The PR body retained structural/runtime evidence boundaries and contained no prohibited attribution marker.

Zero current surfaces do not prove that no transient or deleted bot item ever existed or that automation is disabled. Zero checks is absence of checks, not a passed CI mechanism.

## Gate

RCL-106 remains an accepted, unremediated owner risk; no new credential exposure was found. Product code, managed execution, privacy enforcement, scientific or clinical validation, demo execution, and every Recall-root RCL-011 runtime row remain unverified.

The exact audited head is not fit for the next owner-controlled gate until P1 and P2 are corrected and independently rechecked. This verdict authorizes no merge, Phase 3, publication, cloud action, or GitHub write.
