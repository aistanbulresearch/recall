# Decision Log

Append-only. Supersede decisions with a new entry rather than deleting history.

## DEC-2026-08-14-001: Product name

- Status: accepted
- Decision: Name the project **Recall** and use the repository `aistanbulresearch/recall`.
- Consequence: Run a naming-collision and discoverability review before public launch; do not change the owner-selected name without a new decision.

## DEC-2026-08-14-002: Demo is part of the product

- Status: accepted
- Decision: Build the web experience with every vertical slice instead of after backend completion.
- Reason: Demo represents 30% of judging and previous experience showed that invisible depth earns no score.
- Consequence: A backend task is incomplete until its authoritative state and failure behavior are visible where relevant.

## DEC-2026-08-14-003: Structural safety authority

- Status: accepted
- Decision: LLM components may propose and audit typed artifacts but cannot own state transitions, classification, notification, or terminal outcomes.
- Consequence: Workflow Controller, Ledger API, and Policy Gate remain deterministic enforcement components.

## DEC-2026-08-14-004: Derived presentation values

- Status: accepted
- Decision: Every displayed result must be computed from the exact authoritative artifact for that run.
- Consequence: No hard-coded outcome, threshold label, status badge, metric, or chart value is permitted.

## DEC-2026-08-14-005: Repository authorship

- Status: accepted
- Decision: All Git and GitHub authorship must resolve to `aistanbulresearch`; no co-author, generated-by, assistant, or automation attribution trailers are allowed.
- Consequence: Identity verification is a pre-commit and pre-push gate.

## DEC-2026-08-14-006: Git branch simplification

- Status: accepted
- Decision: Use `main` plus short-lived feature branches rather than adding a long-lived `develop` branch initially.
- Reason: Preserve review gates while avoiding unnecessary hackathon integration overhead.

## DEC-2026-08-14-007: Deployment hostname unresolved

- Status: pending owner clarification
- Context: The product is Recall, while the supplied hostname was `racall.aistanbulresearch.com`.
- Decision: Do not mutate DNS or deployment configuration until the owner confirms the spelling.

## DEC-2026-08-14-008: Private-repository branch governance fallback

- Status: accepted with a pending platform upgrade gate
- Context: GitHub returned HTTP 403 because repository rulesets require GitHub Pro or a public repository in the current account configuration.
- Decision: Keep the repository private, use feature branches and pull requests by process, allow squash merges only, delete merged branches automatically, and activate a protected-main ruleset as soon as visibility or account capabilities permit it.
- Consequence: Until RCL-110 is complete, branch protection is a documented process control rather than a server-enforced control.

## DEC-2026-08-15-009: Durable weeks-long lifecycle

- Status: accepted
- Decision: Represent institutional continuity with a durable `WatchCase`, bounded event-driven `ScanRun` units, and a separate `ReviewTask` lifecycle.
- Reason: A multi-week process must survive without one continuously running model execution and remain idempotent, replayable, and auditable.
- Consequence: Scheduler, lease, stale-write, duplicate, crash-resume, and accelerated-time proof become mandatory.
- ADR: `docs/adr/ADR-0001-durable-watchcase-and-short-scan-runs.md`

## DEC-2026-08-15-010: Firestore and model-memory authority boundary

- Status: accepted
- Decision: Keep Firestore authoritative and permit Memory Bank only for admitted non-clinical operational context.
- Reason: Long-term memory can support Fleet continuity but cannot safely become clinical evidence, workflow state, or policy input.
- Consequence: Memory writes and retrievals require scope, provenance, TTL, contradiction, poisoning, and unavailable-service controls.
- ADR: `docs/adr/ADR-0002-firestore-authority-and-memory-bank-boundary.md`

## DEC-2026-08-15-011: Managed agent platform control plane

- Status: accepted with Phase 1 feasibility gates
- Decision: Put Agent Runtime and Agent Registry on the target critical path and give Memory Bank, Identity, Gateway, Model Armor, and observability explicit governed roles where access passes.
- Reason: Fleet proof requires cataloged, managed, identity-scoped capabilities rather than decorative agent cards.
- Consequence: Every managed component needs an authenticated smoke artifact, authority limit, denied action, outage behavior, and deterministic fallback or stop condition.
- ADR: `docs/adr/ADR-0003-managed-agent-platform-control-plane.md`

## DEC-2026-08-15-012: Separate local privacy and cloud content-security models

- Status: accepted
- Decision: Use local Gemma only to propose residual identifier spans before deterministic redaction and egress approval; use Model Armor only for untrusted cloud-side source/tool content when feasible.
- Reason: Raw identity must never reach cloud services and neither model may become authoritative.
- Consequence: Gemma and Model Armor have separate metrics, failure tests, receipts, and fallback behavior.
- ADR: `docs/adr/ADR-0004-local-gemma-and-model-armor-separation.md`

## DEC-2026-08-15-013: Explicit data modes

- Status: accepted with ADR-0008 correction
- Decision: Require one atomic `SYNTHETIC`, `CAPTURED_REPLAY`, `LIVE_PUBLIC`, or `MOCK` mode on every source artifact, plus a deterministic run/result `mode_set` and registered composition. Permit `SYNTHETIC_WITH_CAPTURED_REPLAY`; reject mock-plus-product and live-public-inside-replay compositions.
- Reason: Demo reliability cannot justify presenting replay, cache, synthetic, or mock data as live or production patient data.
- Consequence: Atomic modes and run composition become schema, API, UI, capture, and claim-evidence requirements; modes are not a scalar trust ordering.
- ADR: `docs/adr/ADR-0005-explicit-data-modes-and-demo-authenticity.md`

## DEC-2026-08-15-014: Independent implementation and pattern-reference boundary

- Status: accepted
- Decision: Build Recall independently in this repository. Other codebases may be inspected only for abstract engineering patterns, handled failure modes, and lessons; no source code, tests, fixtures, schemas, prompts, configuration, UI, documentation, generated artifact, or commit history may be copied.
- Reason: Recall is a distinct hackathon product with a different system objective, architecture, scope, and evidence burden. Learning from a problem-handling pattern is not component reuse.
- Submission consequence: Do not add a voluntary public `pre-existing work` section when no component is imported or reused. If a binding rule or submission field explicitly asks about prior work, inspiration, or reuse, review the exact wording and answer truthfully and narrowly.
- Engineering consequence: Every Recall component requires repository-local requirements, acceptance tests, implementation, provenance, and verification evidence.

## DEC-2026-08-15-015: Eligibility gate proceeds with conditions

- Status: accepted pending owner assertions
- Decision: Continue architecture, contract, evaluation, and demo-storyboard work under the owner-supplied official Rules snapshot. Do not begin product implementation until owner eligibility assertions and RCL-102 dependency/license policy are closed.
- Reason: The repository was created inside the Submission Period, contains no tracked product code, and enforces independent implementation. Personal eligibility, entry capacity, and live Rules currency remain unverified.
- Consequence: `docs/governance/ELIGIBILITY_CHECKLIST.md` is the RCL-101 gate. Any direct prior-project import, mandatory-field change, or Rules change reopens this decision.

## DEC-2026-08-15-016: Personal eligibility and entry capacity verified

- Status: accepted
- Decision: Record RCL-101 as verified based on the owner's confirmation that all personal eligibility conditions are met, no prohibited conflict applies, entry capacity is `individual/solo`, and the owner is authorized to use the `aistanbulresearch` identity and repository.
- Privacy consequence: Persist only the pass/fail assertions and entry capacity, not age, residence, identity-document, or sanctions-screening details.
- Remaining condition: Recheck the live Devpost Rules before feature freeze and final submission; this is a source-currentness control, not an open personal-eligibility question.

## DEC-2026-08-15-017: Non-clinical contest deployment boundary

- Status: accepted
- Decision: Implement and present Recall as a non-clinical research prototype using synthetic institutional records and source-attributed public evidence.
- Reason: Current Google Cloud Service Specific Terms prohibit Generative AI Services for clinical purposes. De-identification changes privacy risk but does not change the deployment purpose.
- Consequence: No real patient data or clinical-production claim is allowed. Future laboratory deployment requires a separate provider-terms, regulatory, privacy, security, validation, and institutional-approval gate.
- ADR: `docs/adr/ADR-0006-non-clinical-contest-deployment-boundary.md`

## DEC-2026-08-15-018: Conservative third-party admission policy and proposed repository license

- Status: accepted policy; repository license pending owner approval
- Decision: Admit only exact, locked, inventoried dependencies and separately governed model/data artifacts; block unknown and restrictive licenses by default. Propose Apache-2.0 for Recall because it is permissive and includes an explicit patent grant.
- Consequence: No `LICENSE` file is added until the owner approves the IP decision. RCL-301 must produce the exact transitive inventory, notices, and CycloneDX or SPDX SBOM; RCL-902 repeats the gate at feature freeze.
- Evidence: `docs/governance/DEPENDENCY_LICENSE_POLICY.md`, `docs/governance/THIRD_PARTY_REGISTER.md`, and `docs/governance/TERMS_SOURCE_NOTES.md`.

## DEC-2026-08-15-019: GitHub auditor gate before implementation

- Status: accepted
- Decision: After the complete Phase 2 architecture, contracts, threat model, evaluation protocol, storyboard, and derived-value registry are committed and pushed by `aistanbulresearch`, notify the owner that the GitHub auditor-agent review is ready. Do not start Phase 3 until findings are logged and triaged.
- Reason: The auditor must review the same remote state that implementation will use, while findings can still change architecture without code rework.
- Consequence: RCL-211 is a mandatory Phase 2 exit gate. A final follow-up remains part of RCL-902 if material changes occur.

## DEC-2026-08-15-020: Apache-2.0 repository license

- Status: accepted
- Decision: License the Recall repository under Apache License 2.0.
- Rules basis: The binding Rules snapshot imposes no special repository license or open-source-publication requirement. It permits open-source components when their licenses are followed and requires the entrant to own the submission and hold necessary third-party rights.
- Owner approval: Approved 2026-08-15, conditional on the absence of a special Rules license requirement; that condition passed against the hash-pinned snapshot.
- Consequence: `LICENSE` is present. Dependencies, models, APIs, data, and assets retain their separate terms and inventory gates.

## DEC-2026-08-15-021: One-screen demo critical path

- Status: accepted design
- Decision: Use one Mission Control screen for a 3:45 video: workload hook, conditional Gemma privacy proof, 75-second uninterrupted managed success run, combined mismatched-citation and forbidden-tool fault run, correlated Google Cloud proof, and bounded close.
- Reason: The three scoring axes must be visible in one coherent flow. Extra controls that do not replace a score-bearing moment are excluded from the video.
- Consequence: Memory poisoning and untrusted-source tests remain supporting evidence unless they replace another proof moment. The final script cannot introduce an unverified numerical claim.
- Evidence: `docs/demo/FOUR_MINUTE_STORYBOARD.md` and `docs/demo/WEB_INFORMATION_ARCHITECTURE.md`.

## DEC-2026-08-15-022: Deterministic UI lineage contract

- Status: accepted design
- Decision: Build every result-bearing web field through a deterministic View Model Builder with artifact IDs, JSON paths, hashes, and explicit missing-data status. Fixture names select inputs only and cannot map to outcomes or presentation badges.
- Reason: This prevents hard-coded demo results, preset-to-label drift, timer-driven fake progress, and empty-equals-clean failures.
- Consequence: RCL-202 schemas must satisfy the field paths in the registry. A new UI result requires registry and missing-source tests before merge.
- Evidence: `docs/demo/DERIVED_VALUE_REGISTRY.md`.

## DEC-2026-08-16-023: Strict flat artifact envelope and shared UI paths

- Status: accepted design
- Decision: Use one strict flat common envelope for all artifacts, reject unknown fields recursively, and change contract and derived-value paths in the same work unit.
- Reason: A nested UI path and flat contract path had diverged before implementation. One canonical shape prevents silent frontend/backend disagreement.
- Consequence: Executable schemas in RCL-302 must implement the frozen catalog and mutation tests. UI code cannot introduce a result path outside the registry.
- Evidence: `docs/contracts/ARTIFACT_CONTRACTS.md` and `docs/demo/DERIVED_VALUE_REGISTRY.md`.

## DEC-2026-08-16-024: Semantic policy outcomes versus technical halt

- Status: accepted design correction
- Decision: Keep privacy quarantine outside cloud `ScanRun`; route no-change evidence through Policy Gate; reserve `NO_ACTION`, `ABSTAIN`, and `REVIEW_REQUIRED` for Policy Gate; use Controller `HALTED` only when trustworthy policy execution or ledger integrity is impossible.
- Reason: Allowing Controller to fabricate `ABSTAIN` during policy outage would violate the sole-authority rule.
- Consequence: UI, tests, failure receipts, and operations views distinguish `HALTED` from `ABSTAIN`; neither state creates a task.
- ADR: `docs/adr/ADR-0007-policy-outcomes-and-technical-halt.md`.

## DEC-2026-08-16-025: Preregistered mechanism-activation evaluation

- Status: accepted design
- Decision: Freeze privacy, citation, reliability, UI integrity, historical replay, and managed-fleet metrics and stop rules before implementation and evaluation.
- Reason: A safe-looking output is not evidence that its guardrail ran, and a post-hoc metric invites cherry-picking.
- Consequence: Every safety result needs an activation counter plus forbidden-downstream read-back. Historical replay selection is logged before the product run.
- Evidence: `docs/evaluation/EVALUATION_PROTOCOLS.md`.

## DEC-2026-08-16-026: Frozen BRCA2 historical replay geometry

- Status: accepted design
- Decision: Freeze BRCA2 `NM_000059.4:c.7522G>C (p.Gly2508Arg)` as the RCL-205 positive case and BRCA2 `c.425+3A>G` plus `c.1315T>G (p.Phe439Val)` as same-gene negative controls.
- Reason: Versioned ClinVar records retain an aggregate VUS through `VCV002895953.4`; the 2025 qualifying paper has an exact official GEO row; and `VCV002895953.5` later adds a likely-pathogenic submission that cites the studies. The controls are outside the paper's exons 15 through 26 scope and expose gene-only false attribution.
- Claim boundary: The 472-day interval is specific to this case. Chronology and citation do not prove that the paper caused the later assertion. Recall does not classify the variant.
- Consequence: Protocol version `1.0.0` cannot silently replace the case or controls after product results are observed. RCL-503 must halt on source/hash mismatch and keep the live-current smoke separate from captured replay.
- Evidence: `docs/evaluation/HISTORICAL_REPLAY_CASE.md`, `docs/evaluation/HISTORICAL_REPLAY_CANDIDATE_LEDGER.md`, and `docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json`.

## DEC-2026-08-17-027: Accept PR #2 audit findings and block implementation

- Status: accepted correction package
- Decision: Accept F-01 through F-08 as required changes. F-01 through F-06 block merge and Phase 3; F-07 and F-08 block merge plus RCL-205/RCL-503/RCL-506 acceptance. Track F-09 through F-18 before their affected tasks and F-19 through F-29 as explicit completeness debt.
- Reason: The audit found no P0 architectural failure, but it demonstrated that undefined candidate routing, contradictory memory/citation rules, Boolean missing-state collapse, mixed-mode rejection, undefined cursor advancement, dynamic HTML hashes, and incomplete GEO chronology could silently violate core invariants.
- Independent confirmation: Two same-URL ClinVar printable downloads produced different hashes because `ncbi_phid` changed. NCBI GEO reports public date 2024-09-27 and current PMID `41957374`; the qualifying Nature paper PMID `39779848` names `GSE248438` in its data-availability statement.
- Consequence: RCL-202 through RCL-205 return to correction/in-progress status. Product code, merge, and push remain blocked until the stated gates pass.
- ADR: `docs/adr/ADR-0008-external-audit-corrections.md`.
- Evidence: `docs/evaluation/reports/2026-08-17--phase2-external-audit-triage.md`.

## DEC-2026-08-17-028: Freeze replay protocol 1.0.1 as an offline-verifiable source package

- Status: accepted and locally verified at source-package level
- Decision: Replace dynamic-page hash assumptions with ten exact repository captures, per-capture bytes and SHA256, bounded semantic anchors, corrected chronology/linkage predicates, an offline verifier, and mutation plus path-boundary fault tests. Keep `LIVE_PUBLIC` ClinVar retrieval outside the frozen replay package.
- Rights boundary: Store PubMed ESummary JSON rather than abstracts, one minimal Nature data-availability linkage excerpt rather than article content, and attributed public NCBI ClinVar/GEO captures. Do not infer that the captured workbook row existed on GEO's original public date.
- Reason: Replay evidence must remain reproducible if upstream pages drift, while public-source chronology, publication-to-dataset linkage, and as-captured facts remain distinct.
- Consequence: F-07 and F-08 are locally closed at source-package level. This decision does not prove Recall detection, operational utility, a managed run, a policy outcome, or a demo claim.
- Evidence: `docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json` and `docs/evaluation/reports/2026-08-17--rcl-205-protocol-1.0.1-verification.md`.

## DEC-2026-08-17-029: Repo-scoped Codex collaboration and two independent review layers

- Status: accepted; local implementation under verification
- Decision: Keep the primary Codex session as Recall's owner-facing coordinator and use the repo-scoped `$recall-collaboration` skill to dispatch four short-lived custom profiles: Scout, Worker, Smart Worker, and Master Judge. Limit spawned concurrency to three, require exclusive writer leases, and keep protected actions behind owner approval.
- Independent-review boundary: Master Judge is an internal read-only event-based gate. The external GitHub auditor remains outside the Codex hierarchy, reviews only stable owner-published heads, and cannot be controlled by the coordinator. Neither verdict replaces owner approval.
- External cadence: Request the external auditor after this infrastructure is owner-published, after every two completed writing assignments or three remote commits when that produces a new stable head, immediately after published high-risk changes, before merge/phase exit, and at RCL-902 feature freeze.
- Consequence: Runtime discovery and permission behavior require fresh-session smoke evidence. The credential incident in ERR-2026-08-17-086 remains open; DEC-2026-08-17-030 records the owner's one-operation publication exception.
- ADR: `docs/adr/ADR-0009-repo-scoped-codex-collaboration.md`.
- Evidence: `docs/project/COLLABORATION_SYSTEM.md`.

## DEC-2026-08-17-030: Owner risk acceptance for one collaboration-infrastructure publish

- Status: accepted owner exception; security remediation remains open
- Decision: The owner cannot rotate the exposed shared GitHub credential while it is concurrently used by other agents. The owner explicitly accepts that risk and authorizes the exact Recall collaboration-infrastructure commit and push on 2026-08-17.
- Boundary: This decision does not make the credential safe, close RCL-106, disclose its value, or authorize later GitHub writes. Every later commit, push, merge, PR mutation, cloud action, or publication still requires its own owner approval.
- Required controls: Verify local Git author and committer as `aistanbulresearch`, verify the active GitHub account without printing credentials, scan the staged tree, use no attribution trailers, read back the exact remote head, and inspect PR comments, reviews, statuses, checks, and actors for prohibited bot or assistant surfaces.
- Consequence: The collaboration infrastructure may be published before the fresh Recall-root runtime matrix. It remains `IMPLEMENTED` and structurally verified, not runtime-verified, until RCL-011 passes in a new Recall-root task.
- Evidence: Owner instruction dated 2026-08-17, ERR-2026-08-17-086, and the eventual exact-head read-back recorded in `WORK_LOG.md`.

## DEC-2026-08-18-031: Renew owner risk acceptance for the canonical handover publication

- Status: accepted owner exception for the exact publication and read-only audit sequence; security remediation remains open
- Decision: The owner cannot rotate the shared GitHub credential because multiple programs currently depend on it. On 2026-08-18 the owner explicitly accepts the continuing risk and authorizes publication of the canonical handover documentation package, followed by the read-only external-auditor request against the resulting stable exact remote head.
- Boundary: This operational acceptance does not prove the credential is technically safe, close RCL-106, disclose its value, authorize merge or Phase 3, or create standing permission for later GitHub, cloud, billing, or publication actions.
- Required controls: Verify local, origin, and PR head equality; verify Git and GitHub identity as `aistanbulresearch`; stage only the exact approved package; run structural, mutation, whitespace, and secret-signature checks; require a fresh Master Judge verdict; use no attribution trailers; and read back the remote commit, actors, and bot surfaces before requesting the external audit.
- Consequence: Credential rotation remains deferred and recommended. The external audit reviews the successor published head; RCL-011 remains in progress until the Recall-root runtime matrix passes.
- Evidence: Owner instruction dated 2026-08-18, ERR-2026-08-17-086, and the publication evidence to be recorded in `WORK_LOG.md`.

## DEC-2026-08-18-032: Authorize exact external-audit remediation publication and re-review

- Status: accepted bounded remediation and publication authorization; external gate remains failed
- Decision: After receiving the exact `877c78d06d9b78f3071d17c81232fbc4302f857e` external-audit `FAIL` summary and being asked to authorize the P1/P2 remediation plus its push scope, the owner replied `onaylıyorum`. This authorizes the coupled collaboration-evidence remediation, one owner-only feature-branch remediation commit/push after all local gates pass, and one separate read-only external re-review against the resulting stable exact head.
- Required remediation: Bind complete four-role leaf no-spawn and protected owner-operation stopping as explicit `NOT VERIFIED` runtime surfaces; reject exact and displayed `EXECUTED`/`MECHANISM_PROVED` promotions; enforce current normative state mechanically; preserve the exact external-audit report and historical head-scoped PASS evidence.
- Required controls: Coordinator-first document freeze, exclusive Worker lease, 23 typed mutation rejections, independent code review, stable-tree Master Judge `PASS`, exact local/origin/PR equality, `aistanbulresearch` owner identity, zero secret/attribution findings, and immediate plus 20-second delayed remote actor/surface read-back.
- Boundary: This authorization does not make the shared credential technically safe, close RCL-106, authorize merge, Phase 3, cloud, billing, destructive actions, Graphify refresh, PR-body/comment/review mutations, or any later publication. Any failed gate, identity/SHA mismatch, or bot/assistant recurrence stops the publication sequence.
- Evidence: Owner approval in the current task on 2026-08-18; external task `01a01671-1a00-70a2-af25-70f429682465`, source turn `01a01671-21d7-7953-a911-6b060c889361`; `docs/evaluation/reports/2026-08-18--github-auditor-collaboration-fail.md`.
