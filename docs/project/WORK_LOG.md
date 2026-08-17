# Work Log

Append-only. Record substantive actions, verification, and artifact paths.

## WORK-2026-08-14-001: Repository preflight and planning baseline

- Task IDs: RCL-001 through RCL-009
- Actor: aistanbulresearch project workflow
- Actions:
  - Verified GitHub CLI authentication as `aistanbulresearch`.
  - Verified `https://github.com/aistanbulresearch/recall` was private and empty.
  - Verified the requested local directory existed and was empty.
  - Cloned the empty repository to `C:\Users\oacav\OneDrive\Desktop\recall project`.
  - Drafted the living master plan, status, handoff, operating principles, documentation protocol, architecture, governance rules, and evidence ledgers.
- Verification:
  - Git remote points to `https://github.com/aistanbulresearch/recall.git`.
  - Initial branch state reported no commits on `main`.
  - No product code, patient data, model output, or credential was introduced.
- Result: in progress until documentation baseline is copied, reviewed, committed, pushed, and read back.

## WORK-2026-08-14-002: Documentation audit and Obsidian binding

- Task IDs: RCL-003 through RCL-008
- Actions:
  - Confirmed tracked content contains no prior-project names or dedicated reuse-disclosure document.
  - Ran whitespace and local Markdown-link checks; corrected the diagnostic script after its first failed attempt.
  - Added the exact local checkout to Git's safe-directory list to account for the restricted execution user.
  - Bootstrapped a local Obsidian binding with project ID `recall-project`.
  - Verified local project memory and required vault Hub, Plan, Source Inventory, and Codebase Overview files.
- Verification:
  - All 24 Markdown files passed relative-link resolution.
  - Git local state remained documentation-only and uncommitted.
  - `.claude/project-memory/` is ignored and will not publish local absolute paths.
- Result: documentation and local knowledge structure verified; canonical Obsidian synthesis and initial Git commit remain.

## WORK-2026-08-14-003: Phase 0 commit, push, and remote read-back

- Task ID: RCL-009
- Actions:
  - Configured repository-local author and committer as `aistanbulresearch` using the account's GitHub noreply address.
  - Staged 28 documentation and repository-control files.
  - Ran whitespace, secret-pattern, prior-project-reference, local-memory-ignore, operating-contract-tracking, identity, and attribution-trailer gates.
  - Created the documentation-only root commit and pushed `main`.
  - Read the commit back through GitHub.
- Verification:
  - Remote SHA: `5336432a3e353261813443f41a217388b68d585d`.
  - GitHub author login: `aistanbulresearch`.
  - GitHub committer login: `aistanbulresearch`.
  - Author and committer names and noreply emails belong to `aistanbulresearch`.
  - No co-author or generated-by trailer is present.
  - Local `main` tracks `origin/main` with no uncommitted tracked change at read-back.
- Result: Phase 0 repository baseline verified.

## WORK-2026-08-14-004: GitHub repository workflow settings

- Task IDs: RCL-007 and RCL-110
- Actions:
  - Queried the repository ruleset endpoint.
  - Preserved private visibility after GitHub reported that rulesets require Pro or a public repository.
  - Enabled Issues, squash merge only, branch update support, and automatic deletion of merged branches.
  - Disabled merge commits, rebase merges, and the repository wiki so repository documentation remains canonical.
- Verification:
  - `allow_squash_merge=true`
  - `allow_merge_commit=false`
  - `allow_rebase_merge=false`
  - `delete_branch_on_merge=true`
  - `allow_update_branch=true`
  - `has_issues=true`
  - `has_wiki=false`
- Result: PR workflow settings are active; server-enforced protected main remains blocked until RCL-110.

## WORK-2026-08-15-005: Fleet architecture decision package

- Task IDs: RCL-010, RCL-201, RCL-203, RCL-209, RCL-210
- Actions:
  - Reviewed the comprehensive Fortified Fleet requirements report against the current Recall target architecture.
  - Expanded the architecture into a durable `WatchCase`, short bounded `ScanRun`, and separate `ReviewTask` lifecycle.
  - Defined Firestore, ADK Sessions, and Memory Bank authority boundaries and a deterministic memory-admission contract.
  - Assigned explicit roles and outage behavior to Agent Runtime, Agent Registry, Agent Identity, Agent Gateway, Memory Bank, Model Armor, and observability.
  - Separated local Gemma residual-identifier detection from cloud-side untrusted-content screening.
  - Required explicit `SYNTHETIC`, `CAPTURED_REPLAY`, `LIVE_PUBLIC`, or `MOCK` mode across artifacts and product surfaces.
  - Created and accepted ADR-0001 through ADR-0005.
  - Synchronized the Master Plan, Status, Handoff, compact task plan, Decision Log, and planned Score, Claim, Guardrail, and Demo evidence rows.
  - Updated the bound Obsidian Hub, Plan, repo-local project memory, and `Daily/2026-08-15.md`.
  - Moved the uncommitted design package from `main` to `feature/rcl-010-fleet-architecture` before any commit.
- Verification:
  - `git diff --check` returned no whitespace errors.
  - Corrected ADR audit found five accepted ADRs dated 2026-08-15.
  - Local-link audit checked 30 Markdown files and found zero broken local links.
  - No stale “awaiting owner review” phase marker remained outside the intentionally unchanged internal contest report.
  - Obsidian Hub, Plan, Daily note, and repo-local project memory were read back from their expected paths.
  - New Score and Guardrail rows remain `planned`; new Claim rows remain `unverified`.
  - Active branch is `feature/rcl-010-fleet-architecture`; no commit or push was performed.
- Errors:
  - The first plan-synchronization patch and the first ADR-count diagnostic failed safely and are recorded as ERR-2026-08-15-009 and ERR-2026-08-15-010.
- Result: architecture design baseline accepted and documented; Phase 1 is active, but no feasibility, implementation, deployment, guardrail, scientific, or model claim has been verified.

## WORK-2026-08-15-006: Phase 1 local platform and authentication smoke

- Task IDs: RCL-104, RCL-105, RCL-107
- Actions:
  - Preregistered test levels, result taxonomy, safe resource names, metrics, and stop conditions before platform calls.
  - Installed Google Cloud CLI in a dedicated user-local directory after rejecting a false-success installer result.
  - Completed user authentication and Application Default Credentials login.
  - Counted accessible and billing-enabled projects without persisting their identifiers.
  - Imported five required Google Cloud and ADK packages in an isolated `uv` environment without changing repository dependencies.
  - Checked standard local Gemma, Ollama, llama.cpp, Hugging Face, and repository model locations.
- Verification:
  - Google Cloud CLI `580.0.0` version call passed.
  - User authentication and suppressed ADC token acquisition passed.
  - Five of five required SDK imports passed.
  - Fourteen active projects are accessible; six are billing enabled; no Recall project is selected.
  - A sanitized name-match probe found zero billing-enabled candidates explicitly named for Recall, so automatic selection remained rejected.
  - Zero cloud resources were created, modified, or deleted.
  - No local Gemma runtime command or GGUF model was found.
- Errors:
  - ERR-2026-08-15-011 through ERR-2026-08-15-018.
- Artifact:
  - `docs/evaluation/reports/2026-08-15--phase1-platform-smoke.md`
- Result at this step: partial. L0 tooling and authentication passed; project-scoped discovery and roundtrips stopped pending a Recall project decision. WORK-2026-08-15-007 subsequently resolved the project decision by creating a dedicated project. RCL-107 remains blocked by absent local runtime/model artifacts.

## WORK-2026-08-15-007: Dedicated Recall GCP project creation

- Task IDs: RCL-104, RCL-105
- Actions:
  - Verified one accessible organization.
  - Generated a unique non-secret project identifier and created one project with display name `Recall` under that organization.
  - Set the project as the local Google Cloud CLI target and ADC quota project.
  - Attempted billing linkage only after an initial uniqueness check, then stopped when corrected parsing proved two open billing accounts exist.
- Verification:
  - Project lifecycle is `ACTIVE`.
  - Display name is `Recall`.
  - Parent type is organization.
  - CLI target and ADC quota-project configuration passed.
  - Billing-enabled read-back is false.
  - Two open billing accounts exist; zero have a unique organization-parent or Recall/AIstanbul name match.
  - No API was enabled and no model, managed runtime, or temporary service resource was invoked.
- Errors:
  - ERR-2026-08-15-019 through ERR-2026-08-15-021.
- Result: project creation passed; readiness remains blocked until the owner selects the billing account.

## WORK-2026-08-15-008: Independent implementation boundary

- Task ID: RCL-103
- Decision:
  - Recall is a distinct project implemented independently in its own repository.
  - Other codebases may be inspected only for abstract engineering patterns, failure modes, and lessons.
  - No source code, tests, fixtures, schemas, prompts, configuration, UI, documentation, generated artifacts, or commit history will be copied.
  - No voluntary public `pre-existing work` section will be created when no component is imported or reused.
- Verification:
  - DEC-2026-08-15-014 records the owner-approved boundary.
  - `AGENTS.md`, Operating Principles, Master Plan, Status, Handoff, compact task plan, and project memory were synchronized.
- Remaining gate:
  - RCL-101 must inspect the exact binding rules and submission fields. Any explicit mandatory question must be answered truthfully and narrowly.
- Result: engineering boundary accepted; rule-text verification remains before RCL-103 can be marked verified.

## WORK-2026-08-15-009: RCL-101 official Rules eligibility audit

- Tasks: RCL-101 and RCL-103
- Actions:
  - Read the complete 404-line owner-supplied official Rules snapshot.
  - Hash-pinned the source and mapped eligibility, timing, technology, category, originality, licensing, submission, judging, bonus, IP, and verification requirements.
  - Attempted to verify the live Devpost Rules page; search returned no indexed result and direct retrieval was blocked by the browsing layer.
  - Verified the repository's first commit falls inside the Submission Period, tracked product-code count is zero, and tracked prior-project-name hits are zero.
  - Converted the submission and credit-request deadlines from PT to Europe/Istanbul.
- Evidence:
  - `docs/governance/ELIGIBILITY_SOURCE_NOTES.md`
  - `docs/governance/ELIGIBILITY_CHECKLIST.md`
  - DEC-2026-08-15-015
- Result:
  - RCL-101 is in progress pending owner eligibility assertions, entry capacity, and later live-page recheck.
  - RCL-103 is verified as a continuous gate: no work is incorporated, so no voluntary pre-existing-work section is required on current facts.

## WORK-2026-08-15-010: Owner eligibility and entry-capacity closure

- Task: RCL-101
- Owner attestations:
  - All personal age, residence, sanctions, and general eligibility conditions are met.
  - No prohibited Contest Entity, household, government, or conflict condition applies.
  - Entry capacity is `individual/solo`.
  - Owner is authorized to use the `aistanbulresearch` identity and repository.
- Privacy handling:
  - Recorded only eligibility outcomes and entry capacity; no sensitive personal detail was persisted.
- Result:
  - RCL-101 verified.
  - Future work should focus on architecture and technical gates; live Rules currentness remains a final-submission recheck.

## WORK-2026-08-15-011: RCL-102 dependency, license, API-terms, and data-rights gate

- Task IDs: RCL-102 and RCL-211
- Actions:
  - Reviewed current authoritative sources for Google ADK, Pydantic, FastAPI, `llama.cpp`, Gemma, Google Cloud AI/ML services, ClinVar, NCBI E-utilities, and PubMed copyright handling.
  - Defined conservative allowed, conditional, and blocked license classes plus exact-lock, integrity, notice, SBOM, model-artifact, API-terms, and data-rights gates.
  - Created the initial third-party register without treating a candidate component as an approved unpinned dependency.
  - Proposed Apache-2.0 for the Recall repository but did not add a license without owner approval.
  - Recorded that current Google Cloud terms prohibit Generative AI Services for clinical purposes and created ADR-0006 to constrain the contest build to synthetic, non-clinical research use.
  - Added a mandatory GitHub auditor-agent gate after the complete Phase 2 package is committed and pushed and before Phase 3 implementation.
- Evidence:
  - `docs/governance/DEPENDENCY_LICENSE_POLICY.md`
  - `docs/governance/THIRD_PARTY_REGISTER.md`
  - `docs/governance/TERMS_SOURCE_NOTES.md`
  - `docs/adr/ADR-0006-non-clinical-contest-deployment-boundary.md`
  - DEC-2026-08-15-017 through DEC-2026-08-15-019
- Verification:
  - `git diff --check` returned no whitespace errors.
  - Local-link audit checked 39 Markdown files and found zero broken links.
  - Required-policy consistency appeared across the canonical plan, status, handoff, architecture, repository rules, and Obsidian project memory.
  - Secret-pattern scan found zero matching files.
  - No `LICENSE`, GGUF model, or model-directory artifact was added.
  - All four Obsidian and repo-local project-memory artifacts were read back.
- Errors:
  - The first multi-file synchronization patch used a stale STATUS wording anchor and was rejected before any partial write. See ERR-2026-08-15-024.
- Result:
  - Technical policy package complete.
  - RCL-102 remains `in-progress` only because the repository-license IP decision belongs to the owner.
  - No dependency, model, cloud resource, product code, license file, commit, or push was added by this work unit.

## WORK-2026-08-15-012: Apache-2.0 approval and RCL-102 closure

- Task ID: RCL-102
- Actions:
  - Re-read the full owner-supplied official Rules snapshot for special repository-license, open-source, ownership, and third-party-rights conditions.
  - Confirmed zero special-license requirements, one explicit third-party license-compliance clause, and one explicit open-source-permission clause.
  - Retried live Rules discovery; the page remained unavailable to search, so the hash-pinned snapshot remains the working source and the final live recheck remains open.
  - Applied the owner-approved Apache License 2.0 and synchronized the dependency policy, register, source notes, Master Plan, Status, Handoff, README, and project memory.
- Verification:
  - `LICENSE` contains the Apache-2.0 header and all nine numbered terms sections.
  - License SHA256 is `C71D239DF91726FC519C6EB72D318EC65820627232B2F796219E87DCF35D0AB4`.
  - RCL-102 appears exactly once as `verified` in the Master Plan.
  - No dependency, model artifact, product code, cloud resource, commit, or push was created.
- Errors:
  - ERR-2026-08-15-025 through ERR-2026-08-15-027.
- Result: RCL-102 verified. Exact direct/transitive dependency and asset decisions remain RCL-301 and release gates.

## WORK-2026-08-15-013: RCL-207 and RCL-208 demo-first design package

- Task IDs: RCL-207 and RCL-208
- Actions:
  - Converted the 40/30/30 score matrix and binding video requirements into one 3:45 narrative.
  - Defined a 75-second uninterrupted managed Proof of Action and a second live fault run combining a mismatched citation with a forbidden tool request.
  - Designed a single Mission Control screen that shows workload, strict agent lanes, independent audit, deterministic policy, simulated tasks, and managed-cloud correlation.
  - Registered every planned result field with its source artifact/path, deterministic derivation, explicit missing behavior, and anti-hard-coding tests.
  - Mapped storyboard moments to the Demo Evidence Log and design paths to the Score, Claim, and Guardrail ledgers.
  - Updated canonical repository documents and the bound Obsidian Hub, Plan, Daily note, and repo-local project memory.
- Evidence:
  - `docs/demo/FOUR_MINUTE_STORYBOARD.md`
  - `docs/demo/WEB_INFORMATION_ARCHITECTURE.md`
  - `docs/demo/DERIVED_VALUE_REGISTRY.md`
  - DEC-2026-08-15-021 and DEC-2026-08-15-022
- Verification:
  - Seven storyboard segments total 225 seconds with 15 seconds of buffer and zero timeline gaps or duration mismatches.
  - The derived-value registry contains 48 unique Field IDs, zero duplicates, and zero malformed table rows.
  - Local-link audit checked 44 Markdown files and found zero broken links.
  - `git diff --check` and the new-file trailing-whitespace scan returned zero findings.
  - Canonical status scan found zero stale license or RCL-207/RCL-208 markers.
  - Secret-pattern scan found zero matching files.
  - Recall and the unrelated VUS workspace both have no accidental `.venv` remaining from the failed helper attempt.
- Error:
  - ERR-2026-08-15-028.
- Result:
  - RCL-207 and RCL-208 are verified as design gates only.
  - Web implementation, deployed execution, guardrail activation, model metrics, and public claims remain unverified.
  - No commit or push was performed; work remains on `feature/rcl-010-fleet-architecture`.

## WORK-2026-08-16-014: Phase 2 authority, contract, lifecycle, policy, and evaluation freeze

- Task IDs: RCL-201 through RCL-206, RCL-208 through RCL-210
- Actions:
  - Froze a threat model with protected assets, trust zones, authority graph, per-component denied actions, 20 threat classes, and activation-proof tests.
  - Defined a strict versioned common envelope, artifact catalog, compatibility rules, authorized producers, policy fact projection, and examples.
  - Froze separate `WatchCase`, `ScanRun`, and `ReviewTask` transition tables with idempotency, CAS, leases, retries, budgets, failure codes, and invariant tests.
  - Corrected the lifecycle authority model so local quarantine creates no cloud run, no-change still reaches Policy Gate, and technical `HALTED` is distinct from semantic `ABSTAIN`.
  - Defined deterministic policy authority, precedence, abstention predicates, representative truth table, ordered reasons, and transactional task creation.
  - Preregistered privacy, citation, reliability, derived-UI, historical replay, and managed-fleet evaluation protocols with failure and rollback rules.
  - Reconciled the artifact catalog with every derived UI JSON path and added an explicit run-state field that distinguishes `HALTED`.
- Evidence:
  - `docs/security/THREAT_MODEL.md`
  - `docs/contracts/ARTIFACT_CONTRACTS.md`
  - `docs/contracts/LIFECYCLE_STATE_MACHINES.md`
  - `docs/policy/DETERMINISTIC_POLICY_SPEC.md`
  - `docs/evaluation/EVALUATION_PROTOCOLS.md`
  - `docs/adr/ADR-0007-policy-outcomes-and-technical-halt.md`
- Design status:
  - RCL-201 through RCL-204 and RCL-206 are verified as design gates only.
  - RCL-205 is in progress because no historical case or negative controls are frozen.
  - RCL-209 and RCL-210 remain in progress pending executable schemas, IAM/platform access, fixtures, and outage evidence.
- Errors:
  - ERR-2026-08-16-029 through ERR-2026-08-16-031.
- Result:
  - No product code, cloud resource, empirical run, commit, or push was created.
  - The GitHub auditor-agent gate is not ready until RCL-205 and the complete Phase 2 audit are finished and pushed.

## WORK-2026-08-16-015: RCL-205 historical replay selection freeze

- Task ID: RCL-205
- Actions:
  - Applied the preregistered measurement-before-build and anti-cherry-picking gates before any Recall replay execution.
  - Screened four positive candidates and retained all rejection reasons.
  - Selected BRCA2 `NM_000059.4:c.7522G>C (p.Gly2508Arg)` as the bounded positive case.
  - Selected two same-gene, source-scope-negative controls: `c.425+3A>G` and `c.1315T>G (p.Phe439Val)`.
  - Verified the exact positive row in the official NCBI GEO `GSE248438` XLSX and recorded its source values and binary hash.
  - Pinned ClinVar v1, v4, and v5 locators and retrieval hashes; PubMed metadata hashes; two control-record hashes; source dates; rights notes; and explicit `CAPTURED_REPLAY`, `SYNTHETIC`, and `LIVE_PUBLIC` separation.
  - Derived the case-specific 391-day evaluator interval and 472-day public-appearance interval from exact frozen dates.
  - Updated the plan, status, handoff, score, claim, demo, guardrail, and third-party registers without approving an empirical product claim.
- Evidence:
  - `docs/evaluation/HISTORICAL_REPLAY_CASE.md`
  - `docs/evaluation/HISTORICAL_REPLAY_CANDIDATE_LEDGER.md`
  - `docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json`
  - DEC-2026-08-16-026
- Verification at selection time:
  - Official GEO file contained exactly one matching `c.7522G>C / G2508R` row.
  - Exact GEO file SHA256 was `91e8fcd081dbaf200be4640b99685a1c612259e4a8e02ce7db59806451b9817f` over 570186 bytes.
  - Calendar differences independently resolved to 391 and 472 days.
  - ClinVar semantic anchors and response hashes are recorded separately so dynamic-byte drift cannot masquerade as semantic-version drift.
- Errors:
  - ERR-2026-08-16-032 through ERR-2026-08-16-037.
- Result:
  - RCL-205 is verified as a design and source-selection gate only.
  - Recall has not detected the case, executed an agent, emitted policy, created a task, or validated operational utility.
  - The next gate is the complete Phase 2 consistency audit. No commit or push was performed.

## WORK-2026-08-16-016: Complete local Phase 2 design package audit

- Task ID: RCL-211 preparation
- Actions:
  - Audited RCL-205 manifest structure, source IDs, hashes, control count, exact-row linkage, and independently recalculated chronology.
  - Audited all repository Markdown links and bound Obsidian wikilinks.
  - Parsed every fenced JSON example.
  - Recounted UI Field IDs with ordinal case-sensitive logic and compared every UI artifact reference with the contract catalog.
  - Scanned canonical records for stale RCL-205 state and asserted exact Master Plan task rows.
  - Scanned secret-shaped filenames and common credential signatures.
  - Removed and read back the absence of the two exact temporary downloads created during source verification.
- Evidence: `docs/evaluation/reports/2026-08-16--phase2-design-audit.md`.
- Corrected errors: ERR-2026-08-16-038 and ERR-2026-08-16-039.
- Result:
  - The local Phase 2 design package passes the documented consistency audit.
  - No product behavior, empirical claim, managed deployment, commit, or push was verified.
  - The next gate is Git/GitHub attribution preflight, commit, push, remote read-back, owner notification, and GitHub auditor-agent review.

## WORK-2026-08-16-017: Phase 2 attribution gate, commit, push, and remote read-back

- Task ID: RCL-211
- Actions:
  - Verified repository root, origin, feature branch, and prior verified commit identity.
  - Verified local Git name is `aistanbulresearch`, configured email matches the prior verified author and committer, and no `GIT_AUTHOR_*` or `GIT_COMMITTER_*` override exists.
  - Verified no commit template, custom hooks path, Git note, or existing prohibited authorship trailer is present.
  - Verified the active GitHub login is `aistanbulresearch` before mutation.
  - Staged 44 files and reran whitespace, secret-pattern, binary, machine-memory, identity, and commit-message gates.
  - Created the trailers-free Conventional Commit `docs(architecture): freeze phase 2 design`.
  - Pushed `feature/rcl-010-fleet-architecture` and independently read the branch and commit through Git and GitHub APIs.
  - Recorded the remote gate in a second owner-only commit, pushed it, and independently verified the new remote branch tip.
  - Opened PR #2 from the feature branch to `main` and read back PR author, branches, commit authors, and text metadata.
  - Detected an unsolicited `cursor[bot]` disabled-Bugbot upsell comment during the mandatory post-PR actor scan.
  - Deleted only the exact bot comment and repeated the complete visible comment, review, commit-actor, and PR-text audit.
- Evidence:
  - Package commit: `9ab9fa9a59aa92ce9cf9b4a9a6ca7e8e7446c4f4`.
  - Local and remote branch SHAs matched exactly.
  - Active login, GitHub author login, GitHub committer login, commit author name, and commit committer name all equaled `aistanbulresearch`.
  - Commit message matched exactly and contained no `Co-authored-by`, generated-by, model, tool, or agent authorship marker.
  - PR #2 is open at `https://github.com/aistanbulresearch/recall/pull/2`; PR author and all included commit author names/logins equal `aistanbulresearch`, with no prohibited authorship marker in title or body.
  - After exact bot-comment deletion, visible PR comments and reviews both equal zero; ERR-2026-08-16-040 records the event and recurrence control.
- Result:
  - Phase 2 package is present on GitHub with owner-only authorship metadata.
  - RCL-211 remains in progress until external findings are recorded and triaged.
  - No product implementation or merge was performed.

## WORK-2026-08-17-018: PR #2 external audit triage and correction decision

- Task ID: RCL-211
- Actions:
  - Read and checked the read-only PR #2 audit against the local Phase 2 documents.
  - Independently confirmed ClinVar printable hash drift, GEO public/update metadata, current linked PMID, and the qualifying Nature paper's data-availability link to `GSE248438`.
  - Accepted F-01 through F-08, scheduled F-09 through F-18 before affected tasks, and retained F-19 through F-29 as explicit completeness debt.
  - Created ADR-0008 and the canonical external-audit triage report.
  - Corrected RCL-202 through RCL-205 and RCL-211 status across Status, Master Plan, Handoff, Decision Log, Error Log, compact plan, and project memory.
  - Marked Phase 3, merge, and push as blocked under their separate gates.
- Evidence:
  - `docs/adr/ADR-0008-external-audit-corrections.md`.
  - `docs/evaluation/reports/2026-08-17--phase2-external-audit-triage.md`.
  - ERR-2026-08-17-042 through ERR-2026-08-17-051.
- Result:
  - The external audit and triage are complete, but the correction package is not implemented or verified.
  - RCL-205 is `in-progress`; the frozen case/control geometry remains, while replay protocol 1.0.1 is required.
  - No product code, cloud resource, commit, push, PR comment, review, or merge was created.

## WORK-2026-08-17-019: ADR-0008 F-01 through F-06 normative correction

- Task IDs: RCL-201 through RCL-204, RCL-206 through RCL-208, RCL-211
- Actions:
  - Added deterministic `CandidateDeltaReceipt` routing and prohibited Assessor suppression or `NO_ACTION` authority.
  - Removed memory state from PolicyDecision inputs and required byte-identical policy/task parity with rejected memory enabled or disabled.
  - Made any rejected material claim block the immutable assessment and require a new fully audited assessment before continuation.
  - Replaced Boolean policy prerequisites with `FactState` and `PresenceState`, projected every applicable reason, and sorted complete reason sets lexically.
  - Versioned breaking payload corrections and replaced scalar data-mode ordering with atomic artifact modes plus deterministic run-level mode set/composition.
  - Defined exact WatchCase cursor, pending-evidence, attention, scheduling, duplicate, and recovery behavior for every terminal path.
  - Synchronized architecture, contracts, lifecycle, policy, threat model, evaluation, replay design, demo narrative, derived UI, plans, and evidence ledgers.
- Verification:
  - 11 representative policy rows had zero lexical-order or duplicate-code errors.
  - Three fenced JSON blocks and 71 repository JSON files parsed with zero errors.
  - The registry contains 52 unique UI Field IDs and zero duplicates; all 21 actual UI artifact types are present in the contract catalog.
  - Canonical scope contained 50 Markdown files and 15 local links; full workspace scope contained 88 Markdown files and 22 local links. Both scans completed with zero scanner errors and zero broken links.
  - `git diff --check`, trailing-whitespace scan, and credential-shaped-content scan were clean.
  - Two policy-order probes and one JSON batch probe failed before execution and are retained as ERR-2026-08-17-052, ERR-2026-08-17-054, and ERR-2026-08-17-055; corrected independent probes supplied the stated results.
- Evidence:
  - `docs/adr/ADR-0008-external-audit-corrections.md`
  - `docs/evaluation/reports/2026-08-17--adr-0008-normative-consistency-audit.md`
- Result:
  - F-01 through F-06 are closed at corrected-document level. No executable guardrail behavior is claimed.
  - F-07/F-08, RCL-205, complete follow-up audit, safe push, external auditor re-review, merge, and Phase 3 remain pending or blocked.
  - Graphify refresh did not complete and the graph remains stale; ERR-2026-08-17-053 records the non-blocking tooling issue.
  - No product code, cloud resource, commit, push, PR write, review, or merge was created.

## WORK-2026-08-17-020: RCL-205 replay protocol 1.0.1 source-package verification

- Task IDs: RCL-205, RCL-211
- Actions:
  - Captured ten exact official public-source artifacts for the positive case, two same-gene controls, publication metadata, GEO metadata/workbook, and bounded publication-to-dataset linkage.
  - Replaced dynamic-page assumptions with exact repository paths, byte counts, SHA256 values, retrieval timestamps, media types, semantic anchors, transformations, and rights boundaries.
  - Corrected chronology by separating GEO submission, GEO public date, qualifying publication date, later evaluator publication, ClinVar v4/v5 dates, GEO last update, and current GEO-linked PMID.
  - Implemented a zero-network verifier, exact XLSX row reader, mutated-byte test, and manifest path-escape test.
  - Kept the current `LIVE_PUBLIC` ClinVar connector outside the frozen replay package and removed PubMed abstract capture in favor of ESummary JSON.
- Verification:
  - Clean result: `PASS`, 10 captures, 1,400,869 bytes, 7 chronology checks, 1 exact XLSX row, 1 separate live-public source, and 0 network calls.
  - Fault result: clean copy verified, mutated byte rejected, path traversal rejected, and 0 network calls.
  - Exact workbook SHA256 remained `91e8fcd081dbaf200be4640b99685a1c612259e4a8e02ce7db59806451b9817f` over 570186 bytes.
- Evidence:
  - `docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json`
  - `docs/evaluation/reports/2026-08-17--rcl-205-protocol-1.0.1-verification.md`
  - `scripts/evidence/verify-rcl-205-captures.ps1`
  - `scripts/evidence/test-rcl-205-captures.ps1`
- Errors: ERR-2026-08-17-056 through ERR-2026-08-17-063.
- Result:
  - F-07 and F-08 pass locally at frozen-source-package level.
  - Recall product execution, operational-utility claims, managed deployment, and demo evidence remain unverified.
  - No product code, cloud resource, commit, push, PR write, review, or merge was created.

## WORK-2026-08-17-021: Complete F-01 through F-08 local follow-up audit

- Task ID: RCL-211
- Actions:
  - Rechecked all eight accepted P1 findings against the corrected architecture, contracts, lifecycle, policy, evaluation, demo, replay, governance, and evidence records.
  - Re-ran the evidence-script parser, clean offline verifier, mutation/path fault test, policy-row ordering, JSON parsing, UI/contract reconciliation, Markdown-link audit, whitespace checks, credential-signature scan, authorship-marker scan, capture inventory, article-rights boundary, Graphify coverage, and Git identity/state checks.
  - Updated Status, Master Plan, Handoff, compact plan, evidence ledgers, decision/error/work logs, repo-local memory, daily note, Obsidian plan/hub, and a durable result note.
- Verification:
  - F-01 through F-06: PASS at corrected-document level.
  - F-07 and F-08: PASS at frozen-source-package level.
  - Three evidence scripts parsed; ten captures and 1,400,869 bytes verified; mutation and path escape rejected; eleven policy rows ordered; 52 UI IDs and 21 artifact types reconciled; JSON, links, whitespace, secret, and authorship-marker checks passed.
  - HEAD remained `c4e2b02d7e596ee99879686b3f53b214809d4673`; no commit or push occurred.
- Evidence: `docs/evaluation/reports/2026-08-17--phase2-f01-f08-follow-up-audit.md`.
- Errors: ERR-2026-08-17-064 through ERR-2026-08-17-069.
- Result:
  - The correction package is locally ready for the GitHub auditor re-review gate.
  - Push remains blocked until the owner explicitly confirms the Cursor GitHub integration is disabled for Recall.
  - Product implementation, merge, managed deployment, and empirical claims remain blocked.

## WORK-2026-08-17-022: Recall Graphify no-stamp runner recovery

- Task: Graphify traversal reliability
- Actions:
  - Confirmed the repository-local `AGENTS.md` already prohibits raw `graphify query`, `graphify explain`, and `graphify path` on the Recall OneDrive checkout and records the exact no-stamp runner.
  - Identified three stuck Recall raw-command shells and their three direct `graphify.exe` children; stopped only those six exact processes and left an unrelated global-graph process untouched.
  - Re-ran architecture traversal through `graphify_agent_runner.py` using the dedicated Graphify virtual environment.
- Verification:
  - `query` completed with exit code 0 and returned a 61-node BFS subgraph.
  - `explain CandidateDeltaReceipt` completed with exit code 0 and returned its source plus two extracted incoming references.
  - Directed `path` completed normally and reported no directed path; `--undirected` completed with a three-hop extracted path to Policy Gate.
  - No raw Recall Graphify traversal process remained after cleanup.
- Error: ERR-2026-08-17-070; ERR-2026-08-17-057 is closed by the resolution checkpoint.
- Result:
  - Future Recall graph traversal must use the no-stamp runner only.
  - No graph rebuild, commit, push, PR write, product execution, or cloud mutation occurred.

## WORK-2026-08-17-023: Owner-only publish and first GitHub auditor re-review

- Task ID: RCL-211
- Actions:
  - Verified active GitHub identity, local/remote branch state, staged replay bytes, commit metadata, PR ownership, and prohibited authorship markers before publication.
  - Added the exact evidence tree rule `binary -eol` after staged-hash verification proved repository-wide text normalization changed one captured GEO file.
  - Created and pushed commit `05ff0b59cad88ef00adc2be2e239e57f73226cda` with message `fix(architecture): close phase 2 audit`.
  - Read back GitHub commit and PR metadata and ran a clean-clone verifier/fault-harness gate.
  - Deleted the exact recurring `cursor[bot]` comment and reread issue comments, review comments, reviews, and checks twice.
  - Requested a read-only auditor re-review against the exact remote head.
- Verification:
  - GitHub author login, committer login, commit author, commit committer, and PR author were only `aistanbulresearch`; the commit had no body or trailer.
  - Clean clone passed 10-capture, 1,400,869-byte verification and the then-current fault harness.
  - Remote surfaces were empty after exact bot-comment deletion, but recurrence proved Cursor disablement was not established.
  - Auditor verdict: `FAIL`, with three High and one Medium finding.
- Evidence: `docs/evaluation/reports/2026-08-17--github-auditor-rereview.md`.
- Result:
  - Owner-only publication succeeded, but no further push is allowed until Cursor is actually disabled.
  - Merge and Phase 3 remain `NO-GO`.

## WORK-2026-08-17-024: First re-review remediation

- Task IDs: RCL-205, RCL-211
- Actions:
  - Corrected the historical case so the Ambry submission cites Sahu et al. only and Huang et al. remains separately labeled corroborating literature.
  - Replaced constant verifier counters with counters incremented by successful source assertions.
  - Parsed chronology and classification/citation semantics from frozen GEO, PubMed, and ClinVar captures; derived intervals now use parsed source dates.
  - Added immediate capture-root rejection, repository-plus-capture-root containment, and target-bearing junction rejection before content/hash reads.
  - Added per-source raw/normalized hash roles, rights-profile bindings, official terms review dates, retention/redistribution decisions, limitations, and attribution.
  - Expanded the fault harness with absolute-root, parent-root, hash-rebound ClinVar citation, hash-rebound Nature word-count, and junction-escape cases.
- Verification:
  - Parser: PASS for verifier and harness.
  - Then-current clean verifier: PASS, 10 captures, 1,400,869 bytes, 7 chronology checks, one mixed 22-check counter, 1 exact XLSX row, 0 network calls. WORK-025 later split and corrected that counter.
  - Fault harness: PASS for byte mutation, lexical traversal, absolute root, parent root, ClinVar semantic mutation, Nature word-count mutation, invalid rights-profile binding, invalid hash-role binding, and junction escape.
- Evidence:
  - `scripts/evidence/verify-rcl-205-captures.ps1`
  - `scripts/evidence/test-rcl-205-captures.ps1`
  - `docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json`
  - `docs/evaluation/reports/2026-08-17--rcl-205-protocol-1.0.1-verification.md`
- Errors: ERR-2026-08-17-074 through ERR-2026-08-17-077.
- Result:
  - Four auditor findings are remediated locally, not yet independently accepted.
  - Second local auditor review is the next gate. No remediation commit, push, merge, product execution, or cloud mutation occurred.

## WORK-2026-08-17-025: Second local review and counter/live-rights remediation

- Task IDs: RCL-205, RCL-211
- Actions:
  - Received a second read-only auditor verdict of `FAIL` with two Medium findings; all first-review High findings were confirmed closed.
  - Declared the live ClinVar entry as an unexecuted connector specification with explicit null raw/normalized byte roles, NCBI rights profile, source-specific limitations, attribution, and mandatory runtime timestamp/hash rule.
  - Split the mixed 22 counter into 12 source semantic checks and 11 rights metadata checks.
  - Replaced anonymous increments with exact successful-check ID sets and made the harness assert both complete sets.
  - Added live-rights-profile mutation rejection.
- Verification:
  - Clean verifier: PASS, 10 captures, 1,400,869 bytes, 7 chronology checks, exact 12-ID semantic set, exact 11-ID rights set, 1 XLSX row, 0 network calls.
  - Fault harness: PASS, including captured and live rights-profile mutations and hash-role mutation.
- Evidence:
  - `docs/evaluation/reports/2026-08-17--github-auditor-rereview.md`
  - `docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json`
  - `scripts/evidence/verify-rcl-205-captures.ps1`
  - `scripts/evidence/test-rcl-205-captures.ps1`
- Result:
  - Both second-review Medium findings are remediated locally, not yet independently accepted.
  - Third read-only auditor review is the next gate. No commit, push, merge, product execution, or cloud mutation occurred.

## WORK-2026-08-17-026: Cursor installation and PR-surface read-back

- Task ID: RCL-211
- Actions:
  - Verified active GitHub login remains `aistanbulresearch`.
  - Attempted a read-only installed-app inventory and separately reread PR #2 issue comments, review comments, and reviews.
- Verification:
  - GitHub denied installed-app listing with HTTP 403 for the current token, so Cursor installation state is `UNKNOWN`, not disabled.
  - Correct fail-loud surface probes report zero issue comments, zero review comments, and zero reviews.
- Error: ERR-2026-08-17-078.
- Result:
  - PR #2 is visibly clean at read time.
  - Cursor disablement cannot be proven through the current GitHub token. Bot recurrence after `05ff0b59` remains evidence that the integration was active, so the push gate stays closed.

## WORK-2026-08-17-027: Third local review and live runtime-provenance remediation

- Task IDs: RCL-205, RCL-211
- Actions:
  - Received a third read-only auditor verdict of `FAIL` with one Medium finding; all prior findings were confirmed closed.
  - Added a machine-validated live runtime provenance contract requiring data mode, raw hash, retrieval time, semantic anchor, source locator, SHA-256, and a prohibition on captured-replay hash comparison.
  - Added allowlisted HTTPS locator, semantic-anchor, integrity-rule, and structured-contract validation for unexecuted live connector specs.
  - Added the distinct successful check ID `live_spec:clinvar_positive_current_xml` and made the harness assert the exact one-ID set.
  - Added an empty-runtime-rule mutation requiring `live_integrity_rule_invalid`.
- Verification:
  - Clean verifier: PASS, 10 captures, 1,400,869 bytes, 7 chronology checks, 12 semantic checks, 11 rights checks, 1 live-spec check, 1 XLSX row, 0 network calls.
  - Fault harness: PASS, including `live_runtime_rule_mutation_rejected=true`.
- Result:
  - The third-review finding is remediated locally, not yet independently accepted.
  - Fourth read-only auditor review is the next gate. No commit, push, merge, product execution, or cloud mutation occurred.

## WORK-2026-08-17-028: Fourth local review and live-source uniqueness remediation

- Task IDs: RCL-205, RCL-211
- Actions:
  - Received a fourth read-only auditor verdict of `FAIL` with one Medium finding; all prior findings were confirmed closed.
  - Registered live source IDs in the same global uniqueness set as captured source IDs.
  - Added clean-result assertion for exactly one declared live source.
  - Added a duplicated-live-spec mutation requiring `source_id_duplicate`.
- Verification:
  - Clean verifier: PASS with `live_public_sources=1` and the unchanged exact live-spec ID set.
  - Fault harness: PASS with `live_duplicate_rejected=true`.
- Result:
  - The fourth-review finding is remediated locally, not yet independently accepted.
  - Fifth read-only auditor review is the next gate. No commit, push, merge, product execution, or cloud mutation occurred.

## WORK-2026-08-17-029: Fifth local auditor review

- Task ID: RCL-211
- Actions:
  - Ran the same auditor read-only against the complete local diff after duplicate-live remediation.
- Verification:
  - Verdict: `PASS`; no actionable findings.
  - Auditor independently confirmed global captured/live ID uniqueness, exact live count and check sets, duplicate-live and cross-class collision rejection, runtime provenance enforcement, citation scope, path/junction controls, PowerShell 5.1 behavior, and prohibited-authorship scan.
- Result:
  - Local auditor gate passes.
  - Remote committed state remains at owner-only `05ff0b59`; the passing remediation is uncommitted.
  - No commit or push is allowed until Cursor disablement is proven. Merge and Phase 3 remain `NO-GO`.

## WORK-2026-08-17-030: Cursor disablement confirmation and publish preflight

- Task ID: RCL-211
- Actions:
  - Received the owner's explicit confirmation that Cursor is disabled.
  - Verified local branch and remote tip remain aligned at `05ff0b59cad88ef00adc2be2e239e57f73226cda` before publication.
  - Verified active GitHub login, local author identity, local committer identity, PR author, and remote repository ownership resolve only to `aistanbulresearch`.
  - Verified PR #2 is open from `feature/rcl-010-fleet-architecture` to `main` and currently has zero issue comments, zero review comments, and zero reviews.
  - Re-ran three PowerShell parser checks, five non-Graphify JSON parses, the clean verifier, the full mutation/path harness, whitespace validation, 86-file/22-link local-link resolution, prohibited-authorship scanning, and credential-signature scanning.
- Verification:
  - Clean verifier: PASS with 10 captures, 1,400,869 bytes, 7 chronology checks, 12 semantic checks, 11 rights checks, 1 live-spec check, 1 live source, 1 XLSX row, and 0 network calls.
  - Fault harness: PASS for every declared byte, semantic, rights, runtime, duplicate, hash-role, traversal, absolute/parent-root, and junction mutation; 0 network calls.
  - `git diff --check`, corrected local-link scan, prohibited-authorship scan, and credential-signature scan passed.
  - ERR-079 records the first null-unsafe link probe; it supplied no evidence and was replaced by the passing complete scan.
- Result:
  - The Cursor owner-confirmation gate is satisfied and the preregistered owner-only remediation publish may proceed.
  - Any prohibited attribution or post-push bot recurrence fails the gate. Merge and Phase 3 remain `NO-GO` pending clean-clone, remote read-back, delayed actor scan, and final remote auditor re-review.

## WORK-2026-08-17-031: Owner-only remediation publish and remote read-back

- Task ID: RCL-211
- Actions:
  - Committed the 13-file remediation/audit package as `9cfee55883fc67cc48e79745ae8d73e3e4a21b3a` with subject `fix(evidence): harden replay verification`, an empty body, and no trailers.
  - Verified author and committer name/email are only the owner identity before push.
  - Ran the verifier and complete fault harness against both the staged index tree and a separate clean clone at the exact commit.
  - Pushed `feature/rcl-010-fleet-architecture` and read back the exact PR head, remote branch tip, commit metadata, PR owner, comments, reviews, and check actors.
- Verification:
  - Remote PR head and branch tip equal `9cfee55883fc67cc48e79745ae8d73e3e4a21b3a`; remote author and committer resolve only to `aistanbulresearch`.
  - Clean clone is clean and both verifier/harness pass with 0 network calls.
  - Immediate and first delayed scans found zero issue comments, zero review comments, zero reviews, and zero check actors.
- Blocker:
  - PR #2 still contains stale pre-remediation verification counts. Three owner-authenticated update paths returned HTTP 503 and changed nothing; ERR-080 records the open external-service failure.
- Result:
  - Commit/push and owner-only read-back pass. Final remote auditor re-review remains blocked until the PR body is refreshed and read back, followed by a new delayed actor scan.

## WORK-2026-08-17-032: Final remote audit metadata correction

- Task ID: RCL-211
- Auditor result:
  - `FAIL` on two Medium remote-metadata findings only: stale PR-body counts and a STATUS row that called remediation checkpoint `9cfee558` the current head after its documentation successor was pushed.
  - All committed verifier/harness checks, F-01 through F-08 boundaries, seven-commit owner-only attribution, prohibited-marker scan, and GitHub actor surfaces passed.
- Actions:
  - Confirmed repeated REST and CLI PR-body updates returned HTTP 503 while read APIs and Git transport remained available.
  - Used the authenticated `aistanbulresearch` web session to replace the stale body with derived current counts and explicit evidence boundaries.
  - Read the corrected PR body back through the GitHub API and confirmed zero comments/reviews.
  - Rephrased STATUS so `9cfee558` is the remediation checkpoint and the current head is its owner-only documentation successor, avoiding a self-stale exact SHA.
- Result:
  - Both remote-audit metadata findings are remediated locally/at the remote PR surface.
  - Final owner-only documentation publish, delayed actor scan, and exact-head auditor re-review remain mandatory. Merge and Phase 3 remain `NO-GO`.
