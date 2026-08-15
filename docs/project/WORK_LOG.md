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
- Evidence:
  - Package commit: `9ab9fa9a59aa92ce9cf9b4a9a6ca7e8e7446c4f4`.
  - Local and remote branch SHAs matched exactly.
  - Active login, GitHub author login, GitHub committer login, commit author name, and commit committer name all equaled `aistanbulresearch`.
  - Commit message matched exactly and contained no `Co-authored-by`, generated-by, model, tool, or agent authorship marker.
- Result:
  - Phase 2 package is present on GitHub with owner-only authorship metadata.
  - RCL-211 remains in progress until the review surface is opened, the owner is notified, and external findings are triaged.
  - No product implementation or merge was performed.
