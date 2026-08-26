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

## DEC-2026-08-20-033: Authorize exact-source remediation and fixed-scope recurring Graphify automation

- Status: accepted bounded remediation, local governance authorization, one publication successor, and one read-only re-review; external gate remains failed
- Decision: After the external re-review at `c8be19476c24672fbf65d4dbf767fa8144360d22` returned `FAIL`, the owner approved the remaining transcript-integrity correction and explicitly set the Graphify interpretation: 242/258/48/131 with 74/74 is historical, the latest verified snapshot is 254/276/49/140 with 75/75, and future handoffs must use timestamp/hash/build-scoped snapshots or live read-only reconciliation rather than unscoped current counts. The owner also approved reconciling the authorization text with the registered recurring Gemini automation and approved continuation of the other bounded remediation steps.
- Source-of-record rule: Preserve the 7,201-character external final answer from task `01a01671-1a00-70a2-af25-70f429682465`, turn `01a01671-21d7-7953-a911-6b060c889361`, as the authoritative transcript with LF UTF-8 SHA-256 `2F3CD3F4DDBE96CE9A5B33C8A041E94242A950CDA21862DDDE75F0B61538489E`. The existing report is a non-authoritative summary and may not claim faithful, verbatim, or exact transcription.
- Recurring authorization: The standing authorization is limited to the registered `Graphify-Refresh-All` action `refresh-repo.ps1 -All -NoBackup`, its two-hour trigger, protected Recall checkout, supported corpus, Gemini destination, `gemini` backend, `gemini-3.5-flash-lite`, `recall-concepts-v1`, token budget 5000, existing principal/logging/privilege, and inspected change-detection path. Unchanged corpus/profile must skip Gemini. Changed inputs may be sent only within this fixed scope.
- Manual and change boundary: Manual/ad-hoc refresh never inherits the recurring authorization. Any cadence, source-root, supported-file-class, destination, backend/model/profile, token-budget, logging, principal, or privilege change requires new explicit owner approval. This decision authorizes no Graphify refresh in the current task and is not runtime proof that the scheduler or failure controls executed.
- Publication boundary: After local implementation, independent code review, full validation, and stable-tree Master Judge `PASS`, this decision authorizes one owner-only Conventional Commit and push of the exact second-remediation scope, immediate and 20-second remote read-back, and one separate read-only external re-review against that exact successor SHA. It does not authorize merge, Phase 3, PR-body/comment/review writes, cloud, billing, destructive action, credential change, or later publication.
- Evidence: Owner instruction dated 2026-08-20; exact external task/turn above; read-only Graphify artifact and Task Scheduler evidence recorded in WORK-2026-08-20-009.

## DEC-2026-08-21-034: Record owner-reported billing display-name selection without operational authorization

- Status: `OWNER_REPORTED_SELECTED`; operational verification and authorization remain open
- Decision: The owner reports selecting the billing display name exactly `My Billing Account`. Store only that display name and state; do not store or infer a billing account ID.
- Evidence boundary: This is an owner report, not a live billing read-back. Billing linkage, credit terms or expiry, permissions, API states, budgets or alerts, resource creation, model calls, and spending remain `NOT VERIFIED`.
- Authorization boundary: The report does not authorize billing linkage, API enablement, budget or alert changes, resource creation, model invocation, spending, cloud mutation, or any other protected action. Each requires separate explicit owner approval after the relevant state is verified.
- Consequence: Billing selection is no longer described as awaiting an owner choice, but RCL-104/RCL-105 and billing-dependent platform smoke remain blocked on verified linkage, permissions, operational controls, and separate approval.
- Evidence: Owner-reported selection supplied to the coordinator on 2026-08-21; no cloud or billing call was made and no billing account ID was accessed or retained.

## DEC-2026-08-21-035: Fail closed when ignored runtime artifacts are no longer inspectable

- Status: accepted evidence-portability correction; RCL-011 remains `IN_PROGRESS`
- Decision: A documented byte count or hash does not remain current executable evidence after its ignored raw artifact has been removed and no immutable parent control-plane record is retained. Preserve the live observation historically, but classify the affected Worker-write and Smart-profile claims as `NOT VERIFIED` in current truth.
- Evidence boundary: During run `rcl011-20260820T204231Z-bf5d6641`, Worker and Smart files were observed, byte-counted, and hashed. The ignored run root was later removed after the initial gate and is absent from the current checkout. Repository reports and hashes are documentation only; they cannot independently reproduce the raw files or their creating runtime identity/tool path.
- Consequence: Only custom-profile discovery and Master Judge verdict formatting remain `EXECUTED`. Worker write plus the prior six residual mechanism/telemetry rows remain seven `NOT VERIFIED` rows; current totals are zero/two/seven and RCL-011 remains partial fail-closed.
- Authorization boundary: This decision changes evidence classification only. It does not authorize recreation of artifacts, raw-trace retention, a new runtime probe, Git/GitHub publication, cloud/billing action, Graphify refresh, merge, or Phase 3.

## DEC-2026-08-21-036: Freeze meta-work and authorize the 72-hour golden path

- Status: accepted owner direction; bounded P1 remediation in progress
- Decision: Timebox the two current P1 evidence-integrity corrections to two hours, keep them as a deny-list for unauthorized `MECHANISM_PROVED`, `EXECUTED` outside the two allowlisted surfaces, and billing/cloud promotion beyond `OWNER_REPORTED_SELECTED`, then record remaining synchronized-change risk as an external-audit boundary. Do not build a general prose-verification framework.
- RCL-011 boundary: Set RCL-011 to `PARTIAL_FAIL_CLOSED / DEFERRED`; preserve all seven `NOT VERIFIED` rows without relabeling. Codex collaboration telemetry is separate from the Recall product fleet and no longer blocks local Phase 3 implementation.
- Delivery sequence: Contracts and three deterministic terminal outcomes first; Gemini/ADK and measured latency second; Cloud Run, Firestore, Logging correlation, and the one-screen success/fault demo third. The 2026-08-23 evening pivot is owner-controlled.
- Fault and UI contracts: F-09 uses a deterministic Controller-level `ToolAuthorization` request attributed to Assessor identity plus a fake-citation `CAPTURED_REPLAY`; institutional inputs are `SYNTHETIC`, not `MOCK`. F-11/F-14 require one failure-to-fact-to-reason registry, explicit `HALTED`, approximately twelve golden-path derived fields, atomic data-mode badges, and run-level `mode_set`. F-16 requires measured latency before the storyboard retains a 75-second run allocation.
- Explicit cuts: Gemma, Memory Bank, Model Armor, Gateway, remote A2A, Week 0/3/6 orchestration, Hetzner, the second connector, and nonessential polish are `CUT / DEFERRED`. Registry gets one authenticated smoke day, then falls back to a pinned Controller-validated manifest with a receipt.
- Review cadence: The coordinator implements by default. Agents are exceptional helpers only. Master Judge runs at the completed vertical slice, pre-deployment, and final freeze. External audit runs asynchronously after this remediation, after the cloud golden path, and before submission.
- Credential gate: The owner continues the current operational risk acceptance, but rotation is mandatory before repository publication or submission, whichever is earlier, and no later than 2026-08-28 18:00 Europe/Istanbul. Read-only metadata inspection confirmed only that the generic `C:\Users\oacav\.codex\sessions` root is outside OneDrive and is not a reparse link. The exact credential-bearing log could not be identified without reopening sensitive content; its exact path, deletion state, and sync containment therefore remain `NOT VERIFIED`.
- Git boundary: PR #2 may merge only after the current P1 remediation is owner-published and receives a fresh exact-head PASS. The owner has instructed that merge; subsequent product work must use a new `feature/rcl-30x-*` branch.
- Cloud boundary: Billing linkage and API enablement remain protected until the owner explicitly authorizes the exact dedicated project, `My Billing Account`, and the minimum Vertex AI, Firestore, Cloud Run, and Cloud Logging API set. Budget, resources, model calls, and spending are outside that authorization unless separately stated.

## DEC-2026-08-21-038: Bind every external-auditor action and reserve scope authority to the owner

- Status: accepted owner correction; recorded after DEC-037 and placed adjacent to the superseded local decision
- Owner authority: The external auditor report is binding planning input. The coordinator must put every report action into the plan and may not remove, downgrade, or silently replace any of them without owner approval. Coordinator initiative is limited to presenting additional ideas as proposals for owner decision.
- Full coverage: `docs/project/AUDITOR_ACTION_REGISTER_2026-08-21.md` binds all immediate conditions, prize targeting, seven degree-oriented extensions, daily dates, scientific/structural invariants, five video proofs, milestone evidence requirements, and five risks. Scale, Week 0/3/6, blog/social/bounded Gemma, Cloud Trace/fleet dashboard, Registry plus second consumer, IAM plus Model Armor, Agent Runtime, and `LIVE_PUBLIC` evidence all remain planned behind their stated entrance/access/rule gates.
- Base versus extension: A component may remain outside the 72-hour golden path while still being a required conditional extension in the plan. Gemma, Model Armor, Week 0/3/6, Registry/second consumer, and Agent Runtime therefore cannot be described as removed. Memory Bank, Gateway, A2A, Hetzner, and the generic second connector retain the report's explicit base-plan cuts unless the owner later changes scope.
- Proposal correction: `RunEvidenceManifest` is a coordinator idea, not an auditor requirement. It is now `PROPOSED / OWNER_DECISION_REQUIRED` and cannot become an implementation dependency until the owner approves it. The report's underlying revision/run/trace/mode/hash/count/activation/latency evidence remains mandatory regardless of packaging.
- PR boundary: The report requires PR #2 merge and `feature/rcl-30x-*` product work. Exact repository evidence currently conflicts with the report's PASS premise because published 46af is recorded as FAIL. The action remains planned and blocked: owner-publish local remediation, obtain fresh exact-head PASS, receive separate owner merge approval, merge PR #2, then move product work to the new branch. No false PASS may be recorded to accelerate this sequence.
- No protected action: This decision authorizes planning corrections only. It does not authorize commit, push, merge, branch creation, billing linkage, API enablement, cloud resources, model calls, spending, credential rotation, public repository changes, publication, Graphify refresh, or destructive actions.

## DEC-2026-08-21-037: Prioritize architectural proof and gate every stretch extension

- Status: superseded by owner correction; see DEC-2026-08-21-038
- Decision: Optimize first for Best Architectural Design, then Individual/Hobbyist, Fleet, and Honorable Mention. Treat the external auditor's probability estimates as directional judgment, not measured project evidence. Preserve the 72-hour golden path and all scientific, authority, provenance, privacy, and fail-closed invariants.
- Evidence envelope: Add one machine-readable `RunEvidenceManifest` per visible run. It binds the run ID, deployed revision, trace ID, `mode_set`, input/output artifact hashes, terminal state, simulated task count, guardrail activation counters, and measured latency so the UI, repository evidence, video, and Google Cloud proof cannot silently diverge.
- Stretch gate: Scale funnel, correlated fleet dashboard, accelerated Week 0/3/6 runs, public build narrative, and optional Registry/second-consumer proof may begin only after executable local and Cloud Run golden-path evidence exists for three terminal outcomes, success and fault runs, authoritative Firestore read-back, correlated sanitized telemetry, explicit modes, and measured latency. Scale results require exact denominators and Wilson 95% confidence intervals and remain exploratory; accelerated weeks must be explicitly labeled.
- Deferred boundary at the time of this decision: this line was rejected by the owner because it removed auditor extensions without authorization. DEC-2026-08-21-038 and the auditor action register restore the complete extension plan.
- Audit correction: The report's recommendation to merge PR #2 based on an audit PASS is not adopted because published head 46af remains `FAIL`; c861 is the last passing audited head. The required order is owner-authorized remediation publication, fresh exact-head external PASS, then separate owner-approved merge.
- Cloud observation: A read-only preflight in the coordinator shell could not locate `gcloud` in `PATH` or checked standard user locations. This leaves billing linkage and API state `NOT VERIFIED`; it does not show they are disabled. No cloud, billing, resource, API, model, spending, GitHub, or publication action occurred.

## DEC-2026-08-21-039: Product scope is VUS evidence recall; laboratory workflow control is out of scope

- Status: accepted; owner-authorized entry recorded by the external auditor on 2026-08-21
- Context: An earlier, unrecorded idea considered a broader "whole laboratory workflow" agent fleet. The Phase 0 contest report promised a candidate-idea screening record that was never written into the repository. This entry closes that gap so the submission's "why this problem" section rests on a recorded decision.
- Decision: Recall's product scope is the monitoring of approved public evidence for previously uncertain genetic results and the creation of audited, simulated review-priority signals. Laboratory workflow control (sample accessioning, QC, turnaround, report release, LIMS integration, classification) is out of scope for the contest and for the current architecture.
- Reasons: (1) ADR-0006: current Google Cloud terms restrict clinical-purpose use; operational laboratory control cannot be defended as a non-clinical research prototype. (2) Schedule: the remaining contest window supports one complete vertical slice, not a multi-workflow fleet. (3) Judging: the Innovation "Twist" and "Unlikely Hero" criteria reward one sharply defined friction; breadth dilutes both and is unprovable in four minutes.
- Accepted trade-off: the broader idea would map more directly to the Fleet track's "network of institutional agents" language. That is a conscious loss, offset by the conditional extension below, not by widening the golden path.
- Vision positioning without scope expansion: Recall is described as one "evidence-watch" cell of a future institutional fleet. README and video may carry exactly one vision sentence of the form "the same fleet pattern applies to other evidence-dependent institutional decisions, such as drug-label updates or standard revisions." This is a statement of pattern, not an implemented or claimed capability, and it must not appear as a feature, metric, or roadmap promise. Wording is gated by RCL-904 and RCL-906.
- Bridge: RCL-315 (second-department consumer, admitted only after the 2026-08-24 entrance gate) is the only sanctioned step toward broader institutional use: a second WatchCase type or a laboratory-QA consumer that discovers and reuses the same Citation Auditor through the Registry. Nothing else about laboratory workflow enters the plan.
- Separation: the owner's separate laboratory-internal classification pipeline remains a distinct project under DEC-2026-08-15-014 and the independent-implementation boundary. Recall does not import, reference, or integrate it. A future integration in which a Recall `REVIEW_REQUIRED` signal becomes an input to that pipeline is a post-submission story and is not claimed in the contest.
- Consequence: Any proposal to add laboratory workflow control before submission requires a new owner decision superseding this entry, a new ADR, and a terms review under ADR-0006.

## DEC-2026-08-22-040: Credential exposure closed

- Status: accepted; owner-authorized entry recorded by the external auditor on 2026-08-22
- Decision: ERR-2026-08-17-086 is closed: exposure detected and contained on 2026-08-22. This supersedes the credential gate in DEC-2026-08-21-038.

## DEC-2026-08-22-041: Prioritize Fleet-first delivery and restore bounded Memory Bank work

- Status: accepted owner direction on 2026-08-22.
- Target order: Fleet-first. Best Architectural Design, Individual/Hobbyist, and the other eligible targets remain relevant, but implementation sequencing now prioritizes visible fleet persistence, governance, reuse, and managed execution evidence.
- Memory Bank scope: Return Memory Bank to the plan through a 2026-08-25 mini-brief limited to admitted non-clinical operational hints plus enabled/disabled parity. Firestore remains authoritative; memory cannot satisfy evidence, audit, policy, outcome, task-count, or state-transition prerequisites and remains absent from `PolicyDecision.input_facts`.
- Scheduled extensions: RCL-311 and RCL-312 are scheduled for 2026-08-25; RCL-313, RCL-315, RCL-316, and RCL-318 for 2026-08-26; RCL-314 for 2026-08-28; and RCL-317 for the 2026-08-24 rule/access-gated deployment milestone. The 2026-08-24 entrance gate and each existing access/rule condition remain binding.
- Lifecycle alignment: `HALTED` is the technical `ScanRun` terminal. `ATTENTION_REQUIRED` is used only as the resulting durable `WatchCase` state after the `scan_halted` transition, with verified cursors preserved, pending evidence retained, and automatic scheduling cleared until explicit recovery.
- Delivery lanes: L1 Platform, L2 Core, and L3 Privacy and Demo are AI developer lanes coordinated by Codex. They do not add human entrants, collaborators, authors, or submitters; the competition entry capacity remains `individual/solo` under owner `aistanbulresearch`.
- Boundary: This decision schedules work and narrows authority. It does not authorize a cloud mutation, GitHub write, push, merge, publication, expanded Memory Bank content, or any change to the non-clinical synthetic/public-evidence boundary.

## DEC-2026-08-23-042: Open the Fleet-first path under a bounded fallback

- Status: owner-approved `GO` on 2026-08-23.
- Decision: Allocate the M1 critical path and resources to the Fleet-first route because the owner accepted Brief 002 as passed on owner/external-reviewer-reported live evidence. The raw Brief 002 runtime artifacts were not re-opened in this decision-recording gate. One extension of at most 24 hours is permitted only for a transient infrastructure failure.
- Fallback: A second agentic failure without an identified root cause returns the delivery target to the Best Architectural Design baseline; the fallback remains a guarantee, not a silent downgrade.
- Resource boundary: This decision sets sequencing and the M1 target. Every persistent new cloud resource type still requires separate owner approval.

## DEC-2026-08-23-043: Permit exact local integration records with legacy hash gates retained as failed

- Status: accepted bounded exception under the owner's 2026-08-23 instruction to close the green 21:00 integration with one governance commit and one small lazy-import commit.
- Decision: Permit only the exact current local documentation and lazy Firestore-import commits after the product gates passed. Do not regenerate or expand the legacy collaboration/Graphify hash framework in this product integration.
- Evidence boundary: `verify_graphify_governance.py` remains `FAIL` at the STATUS normative hash, and `verify_recall_collaboration.py` remains `FAIL` at the MASTER_PLAN claim hash. STATUS, HANDOFF, and MASTER_PLAN hash bindings are stale; fail-fast checks after the first error are `NOT EXECUTED`. The zero/two/seven collaboration evidence classification remains unchanged.
- Protection boundary: This exception does not turn either validator green and does not authorize push, PR, main merge, cloud action, publication, or any later commit.

## DEC-2026-08-25-044: Terminate RCL-106 after owner-accepted containment

- Status: accepted by the owner on 2026-08-25.
- Decision: RCL-106 is terminated. The exposure was detected and contained on 2026-08-22. This decision supersedes the remaining delivery-gate language in DEC-2026-08-21-038 and the earlier operational-risk entries that kept RCL-106 open.
- Rationale: The credential supports multiple owner workflows, and replacing it would disrupt them. The owner accepts the residual operational risk and ends the recurring tracking item.
- Evidence boundary: This is owner risk acceptance after containment, not proof that the credential or every dependent workflow received technical remediation. The credential value was not inspected, copied, or stored for this decision.
- Authority boundary: The decision does not authorize a GitHub write, push, merge, publication, disclosure, or credential use outside an otherwise approved workflow. A new exposure or unauthorized use requires a new incident and owner decision.
- Canonical detail: `docs/governance/RCL-106_TERMINATION_DECISION.md`.

## DEC-2026-08-26-045: Version failed-day continuity and block deployment on UI compatibility

- Status: accepted implementation decision under the owner-approved failed-day brief; deployment condition remains open.
- Decision: Preserve exact `CohortDayManifest 2.0.0` wires as strict legacy-read inputs and emit only 2.1.0. Version 2.1.0 adds required `execution_status` and `failure_receipt_id` history fields; `CohortDayFailureReceipt 1.0.0` records a reconciled missing prior day without fabricating an execution timestamp.
- Integrity rule: The scheduler must validate the complete registered predecessor chain and resolve inherited receipts at their origin ledger before current-day writes. Missing means zero authoritative runs and events; partial or unreachable state fails closed.
- Coordination gate: L3 must acknowledge parser and fixture compatibility against exact product commit `7ebc733063e816ac0f4f3b012b6e99d9f055ee8e` before L1 builds, repoints, or executes a 2.1.0 image. Current acknowledgement is `NOT_RECEIVED`.
- Evidence boundary: Local contracts, tests, independent review, and Master Judge pass. No production Firestore continuation execution or L3 compatibility is claimed.

## DEC-2026-08-26-046: Cohort schedule compression

- Status: owner-approved for implementation; the paragraph below is the canonical owner-approved decision text. Its past-tense execution clauses remain `NOT VERIFIED` until the named runtime artifacts exist.
- Canonical text: DEC-2026-08-26-046: Cohort schedule compression — The remaining cycles of the declared monitoring program (logical days 2026-08-26 through 2026-08-30) were executed as machine-triggered accelerated cycles on a compressed schedule instead of spreading across the remaining UTC days. Reason: operational constraints on the remaining calendar days; made safe because selection semantics are driven by case due-state, not wall-clock dates — compressing the schedule changes no executable behaviour and loses no mechanism coverage. Safeguards: COMPRESSED_PREDICTION_PLAN_V2 committed before any cycle ran (prior prediction table preserved byte-unchanged); every cycle fired by Cloud Scheduler from a per-cycle one-shot trigger instantiated from the committed plan — no human started any run; human action was limited to between-cycle verification and instantiating the next pre-declared trigger; each cycle's selection verified against its committed prediction before the next trigger was created; every timestamp is real; every surface derives its "machine-triggered accelerated schedule" label from the manifest's declared schedule-mode field; the failed 2026-08-26 16:00Z execution is recorded in the evidence ledger and its cycle was re-run as cycle 1 of the compressed schedule after preparation was corrected, carrying its real timestamps; Aug 29/30 tail-day claims are withdrawn; one post-freeze verification tick is scheduled against the frozen deployment revision. Accepted by: owner.
- Identifier resolution: The supplied brief used an unresolved decision placeholder. The canonical identifier was resolved to the next append-only decision ID, `DEC-2026-08-26-046`, before the plan, contracts, or evidence were hash-bound; no placeholder remains in the implementation.
- Current evidence boundary: implementation, deterministic local tests, independent review, and Master Judge are verified. Every clause that says a cycle ran, Cloud Scheduler fired, a prediction matched, c6 passed headroom, or a post-freeze tick occurred remains `NOT VERIFIED` until exact cloud/runtime evidence is appended.

## DEC-2026-08-26-047: Shift compressed windows before the first cycle

- Status: owner-accepted before any compressed cycle ran. The superseded c1 trigger stoppage is `OWNER_REPORTED`; independent cloud read-back is `NOT VERIFIED`.
- Decision: Replace only the six UTC execution windows in `COMPRESSED_PREDICTION_PLAN_V2`: c1 `20:00:00-20:09:59`, c2 `20:30:00-20:39:59`, c3 `21:00:00-21:09:59`, c4 `21:30:00-21:39:59`, c5 `22:00:00-22:09:59`, and c6 `22:30:00-22:39:59`, all on 2026-08-26. Preserve logical due dates, predictions, case identities, semantic payload values, and trigger policies.
- Integrity consequence: Because the preparation bundle binds `plan_sha256` and WatchCase `next_scan_at` to each schedule epoch, it must be regenerated from the shifted product commit; preserving stale bundle bytes would fail preflight. This is a binding/schedule update, not a cohort-content change.
- Evidence boundary: Plan hash, bundle hash, local tests, and Master Judge are verified. Rebuild, repoint, re-preparation, Cloud Run prefix preflight, Scheduler triggers, and every cycle result remain `NOT VERIFIED`.
