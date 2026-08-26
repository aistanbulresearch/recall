# Error Log

Append-only. Log errors even when a retry succeeds.

## ERR-2026-08-26-H: Compressed scheduler verification exposed explicit environment gates

| Field | Value |
|---|---|
| Task | Compressed machine-triggered cycle implementation and pre-commit verification |
| Severity | Low; evidence-orchestration only |
| Observed | The initial broad core command did not set `RECALL_FIRESTORE_TEST_MODE`; 345 tests passed and four live-ledger tests stopped at their required setup gate, producing direct exit 1. A wildcard passed literally to `py_compile`, the first pnpm wrapper forms were invalid or attempted dependency reconciliation, restricted Vitest hit esbuild `EACCES`, and the restricted platform subprocess path hung. The ignored `.pytest-tmp/` root contains access-restricted leftovers and remains untracked. |
| Impact | No false green, cloud write, dependency installation, product-state mutation, or evidence promotion occurred. The failed broad run is not reported as PASS. |
| Resolution | Used `compileall`, the existing offline Vitest binary outside the restricted esbuild boundary, the approved platform subprocess environment, project-local basetemps, and an explicit deterministic-core command that excludes only the separately governed live Firestore file. Exact product gates passed before commit. |
| Verification | Focused 27/27, deterministic core 345/345, platform 259/259, privacy 140/140, web 48/48, VCV 5/5, diff/secret gates, independent review, and Master Judge all passed with direct exit 0 where applicable. |
| Status | Closed for the local implementation; cloud/Firestore compressed-cycle runtime remains `NOT VERIFIED`. |

## ERR-2026-08-26-G: Verification environment produced non-evidentiary attempts

| Field | Value |
|---|---|
| Task | Failed-day continuation pre-commit verification |
| Severity | Low; evidence-orchestration only |
| Observed | A full `pytest -q` without `RECALL_FIRESTORE_TEST_MODE` stopped at the explicit live-ledger setup gate; one first attempt left a stranded test process and was terminated. Platform reruns reached the process-spawning token file, after which the parent PowerShell process did not return a usable final exit. The repository environment has no `ruff` module. Initial pnpm wrapper forms either rejected the option, matched no project, or attempted dependency handling; none was treated as test evidence. |
| Impact | No cloud write, dependency installation, product-state mutation, or false green occurred. The full platform rerun and live Firestore continuation are not claimed as PASS. |
| Resolution | Used project-local basetemps; ran the bounded core and changed scheduler/contract surfaces directly; ran platform excluding only the unchanged token-process file; ran privacy and direct offline Vitest; used `compileall`, diff/secret gates, independent review, and Master Judge. Product commit followed only after the exact pre-commit gate passed. |
| Status | Closed for this local work unit; the token-process trigger and production Firestore continuation remain separately unverified. |

## ERR-2026-08-25-F: Fresh live verification hung in authentication/subprocess handling

| Field | Value |
|---|---|
| Task | Adversarial Day-1 history and F5-lite pre-commit verification |
| Severity | Medium; live verification incomplete, local product gates unaffected |
| Observed | A fresh full suite with live Firestore enabled reached about 30%, marked one failure near the ledger boundary, and then stopped emitting output. A `-x` retry and isolated `test_firestore_ledger.py` also left authentication/subprocess descendants running without a usable traceback. The exact processes created by these attempts were terminated. The first web wrapper command separately attempted dependency reconciliation and refused due no TTY; direct Vitest inside the restricted sandbox hit esbuild access denial. |
| Impact | No fresh live Firestore PASS or cleanup claim is made for this successor. No Day-2 managed tick was invoked. The failed web wrapper did not install or change dependencies. |
| Resolution | Verified the changed surfaces with project-local basetemps: focused 36/36, bounded core 299/299, platform 234/234 excluding the known process-spawning token file, privacy 140/140, and direct offline web 48/48 outside the esbuild-restricted sandbox. L1 must rebuild/repoint and run its deployment preflight; live Day-2 execution retains its own hard gate. |
| Status | Open for live-environment reproduction; fail-loud and excluded from PASS evidence. |

## ERR-2026-08-25-E: Day-N verification commands required explicit environment and Git capabilities

| Field | Value |
|---|---|
| Task | Managed Day-N implementation verification and local commit |
| Severity | Low; evidence-orchestration only |
| Observed | The first preview invocation omitted `RECALL_COHORT_PREPARATION_SHA256` and failed loudly. The first full-suite invocation omitted `RECALL_FIRESTORE_TEST_MODE`, so four live Firestore tests stopped at setup. The repository `.venv` has no `ruff` module. The first sandboxed `git add` could not create `.git/index.lock`. |
| Impact | No product or cloud state was mutated by the failed preview/setup attempts; no false green was reported. The live suite and local commit were delayed. |
| Resolution | Re-ran preview with the exact committed bundle hash (exit 0, writes 0); re-ran the entire suite with the owner-approved explicit `live` mode (692/692, exit 0, cleanup read-back zero); retained `ruff` as unavailable and used `compileall`, diff, tests, review, and Judge gates; repeated exact-path staging through the approved Git capability. |
| Status | Closed for this work unit; adding `ruff` remains a future dependency decision, not an implied check. |

## ERR-2026-08-25-D: Committed Firestore gate exposed stale fixture times

| Field | Value |
|---|---|
| Task | Day-1 committed-source live Firestore pre-run gate |
| Severity | High, run-blocking |
| Observed | The four-test live ledger suite returned direct exit 1: two legacy fixtures requested ScanRun creation before their declared `next_scan_at`, and the new admission guard correctly raised `contract_transition_invalid:watch_case_not_due`. |
| Impact | Source commit `ea95e5e` was not used for the Day-1 firing. No cohort namespace was written. Each exact `dev_recall_3e_*` test namespace was cleaned to five zero counts in `finally`. |
| Resolution | Align the two fixture clocks with their declared due instants, rerun local and live gates, and create a new reviewed source commit before any cohort firing. |
| Status | Closed: replacement commit `14587ac` passed the four-test live Firestore suite with direct exit 0 before the cohort firing. |

## ERR-2026-08-25-C: Day-1 pre-run verification exposed environment-bound checks

| Field | Value |
|---|---|
| Task | Day-1 scheduler pre-run verification |
| Severity | Medium |
| Observed | The first broad core run advanced to 44% and then produced no output; it was interrupted rather than reported green. Isolated `tests/platform/test_gcloud_token.py` reproduced the same behavior after one passing test and was interrupted after 90 seconds. `compileall` initially hit an existing OneDrive `__pycache__` rename denial, and the repo environment has no `ruff` module. |
| Impact | No product assertion failed and no cloud write occurred, but the broad suite cannot be represented as a completed PASS from this process tree. |
| Resolution | Re-ran source compilation with a project-local `PYTHONPYCACHEPREFIX` (PASS), split suites by boundary, and retained the process-spawning token test as an explicit unresolved environment gate. Final pre-commit bounded core passed 261/261, privacy 140/140, and platform excluding that exact file 234/234. |
| Status | Open for the token-test process-tree trigger; product implementation proceeds only through the independent review and Judge gates. |

## ERR-2026-08-14-001: GitHub CLI config access denied

| Field | Value |
|---|---|
| Task | Repository preflight |
| Severity | Low |
| Environment | Restricted local shell |
| Observed | GitHub CLI could not read `GitHub CLI/config.yml` and exited before repository inspection. |
| Impact | Read-only preflight was delayed; no repository mutation occurred. |
| Diagnosis | Sandbox permission boundary, not repository or authentication failure. |
| Resolution | Re-ran the read-only preflight with approved access. |
| Verification | GitHub CLI reported active account `aistanbulresearch`; repository was private and empty. |
| Prevent recurrence | Use the approved GitHub CLI access path for GitHub operations; never print token values. |
| Status | Resolved |

## ERR-2026-08-14-002: Git rejected sandbox repository ownership

| Field | Value |
|---|---|
| Task | Documentation audit |
| Severity | Low |
| Environment | Repository owned by the desktop user and inspected by the restricted sandbox account |
| Observed | Git stopped with `detected dubious ownership` before showing status. |
| Impact | Git status and later commit operations could not proceed through the sandbox identity. |
| Diagnosis | Expected Windows ownership mismatch between the desktop owner and restricted execution account. |
| Resolution | Add only the exact Recall checkout to Git's global `safe.directory` list. |
| Verification | `git status` succeeded after adding only the exact Recall checkout to `safe.directory`. |
| Status | Resolved |

## ERR-2026-08-14-003: First Markdown link checker used the wrong path variable

| Field | Value |
|---|---|
| Task | Documentation audit |
| Severity | Low |
| Observed | The diagnostic script passed a null path to `Join-Path` inside a nested pipeline. |
| Impact | The first link audit did not produce a valid result. Repository files were not changed. |
| Diagnosis | The nested pipeline shadowed the outer file object. |
| Resolution | Re-run with explicit named variables and fail on any unresolved local link. |
| Verification | Corrected audit resolved every relative Markdown link across 24 files. |
| Status | Resolved |

## ERR-2026-08-14-004: Obsidian post-bootstrap check used the wrong slug

| Field | Value |
|---|---|
| Task | RCL-008 |
| Severity | Low |
| Observed | Bootstrap created `Research/recall-project`, but the chained verification command checked `Research/recall`. |
| Impact | The command exited with failure after bootstrap; the binding itself had succeeded. |
| Diagnosis | The bootstrap derived its project ID from the local folder name `recall project`. |
| Resolution | Re-ran verification against the returned `vault_root` and checked all required files. |
| Verification | Registry, local memory, Hub, Plan, Source Inventory, and Codebase Overview exist under the returned paths. |
| Status | Resolved |

## ERR-2026-08-14-005: Machine-global ignore hid AGENTS.md

| Field | Value |
|---|---|
| Task | RCL-007 |
| Severity | Medium |
| Observed | `git status --ignored` marked `AGENTS.md` as ignored even though the repository `.gitignore` did not exclude it. |
| Impact | The repository could have been pushed without its mandatory operating and safety contract. |
| Diagnosis | A machine-global Git ignore rule matched `AGENTS.md`. |
| Resolution | Add an explicit repository-level `!AGENTS.md` rule and verify it appears as trackable. |
| Verification | `git status --ignored` shows `AGENTS.md` as untracked and `.claude/` as the intended ignored local state. |
| Status | Resolved |

## ERR-2026-08-14-006: Pre-commit ignore assertion misread an array

| Field | Value |
|---|---|
| Task | RCL-009 |
| Severity | Low |
| Observed | Pre-commit gate reported that local project memory was not ignored even though prior status output showed `!! .claude/`. |
| Impact | Commit was stopped before creation. Staging succeeded; no remote mutation occurred. |
| Diagnosis | PowerShell `-notmatch` was applied directly to an array and returned the non-matching elements rather than one Boolean for the complete status text. |
| Resolution | Join status lines into a single string before asserting ignore and tracking patterns. |
| Verification | Corrected gate passed: 28 files staged, zero secret-pattern hits, zero prior-project hits, local memory ignored, and `AGENTS.md` tracked. |
| Status | Resolved |

## ERR-2026-08-14-007: Push gate parsed multiline commit metadata incorrectly

| Field | Value |
|---|---|
| Task | RCL-009 |
| Severity | Low |
| Observed | Push gate rejected a commit whose displayed author and committer were both correct. |
| Impact | Push was stopped before remote mutation. |
| Diagnosis | `git log --format` returned a multiline PowerShell array because the commit body contained a newline; one anchored regex was incorrectly applied to that array. |
| Resolution | Read author name, author email, committer name, committer email, and body as separate values; join only the body for trailer inspection. |
| Verification | Corrected gate passed and GitHub read-back returned SHA `5336432a3e353261813443f41a217388b68d585d` with author and committer login `aistanbulresearch`. |
| Status | Resolved |

## ERR-2026-08-14-008: Private repository rulesets unavailable

| Field | Value |
|---|---|
| Task | RCL-110 |
| Severity | Medium |
| Observed | GitHub rulesets API returned HTTP 403: upgrade to GitHub Pro or make the repository public. |
| Impact | The server cannot yet enforce pull-request-only changes, deletion protection, or non-fast-forward protection on `main`. |
| Diagnosis | Account-plan/visibility limitation, not a malformed ruleset request. |
| Mitigation | Keep private visibility, enforce feature-branch PR workflow by process, allow squash merges only, and delete merged branches automatically. |
| Resolution condition | Enable and verify the protected-main ruleset when the repository becomes public or the account plan permits it. |
| Status | Open, externally constrained |

## Open errors

- ERR-2026-08-14-008 remains externally constrained.
- ERR-2026-08-15-020 no longer awaits a display-name choice: DEC-2026-08-21-034 records `OWNER_REPORTED_SELECTED` for `My Billing Account`. Billing linkage, credit terms/expiry, permissions, API state, budgets/alerts, resource creation, model calls, and spending remain `NOT VERIFIED` and unauthorized.
- ERR-2026-08-17-042 through ERR-2026-08-17-049 are accepted external-audit findings and block the gates stated in each entry.
- ERR-2026-08-16-040 recurred after a later push; no further push is permitted until the owner confirms the Cursor integration is disabled for Recall.
- The hostname spelling issue is a pending decision, not an execution error.

## ERR-2026-08-15-009: First architecture-plan synchronization patch missed its anchor

| Field | Value |
|---|---|
| Task | RCL-010 architecture documentation synchronization |
| Severity | Low |
| Observed | The first multi-file patch expected a sentence in `MASTER_PLAN.md` that was not present. Patch verification failed before applying changes. |
| Impact | Documentation synchronization was delayed; no file was partially modified by the rejected patch. |
| Diagnosis | The proposed patch reused wording from `TARGET_ARCHITECTURE.md` as an anchor in `MASTER_PLAN.md`. |
| Resolution | Query exact anchors and apply smaller file-specific patches. |
| Verification | Subsequent patches updated the intended documents and the final link/diff audits are recorded in the Work Log. |
| Status | Resolved |

## ERR-2026-08-15-010: ADR count check used regex syntax in a PowerShell wildcard filter

| Field | Value |
|---|---|
| Task | Architecture documentation verification |
| Severity | Low |
| Observed | `Get-ChildItem -Filter 'ADR-000[1-5]-*.md'` returned zero files. |
| Impact | The first ADR-count assertion was invalid; repository files were not changed. |
| Diagnosis | PowerShell `-Filter` wildcard matching did not interpret the bracket range as the intended regular expression. |
| Resolution | List Markdown files and apply `Where-Object` with an explicit regex. |
| Verification | Corrected check found five ADRs, all with `status=accepted` and `date=2026-08-15`. |
| Status | Resolved |

## ERR-2026-08-15-011: Smoke-plan patch ran before its parent directory existed

| Field | Value |
|---|---|
| Task | Phase 1 smoke-test preregistration |
| Severity | Low |
| Observed | The first patch could not create the smoke plan because `docs/evaluation/` did not exist. |
| Impact | Preregistration was delayed; the failed patch made no partial change. |
| Resolution | Created the exact evaluation/report directories, then applied and read back the plan before running platform tests. |
| Status | Resolved |

## ERR-2026-08-15-012: Environment-variable inventory hit duplicate case-insensitive keys

| Field | Value |
|---|---|
| Task | RCL-107 local Gemma preflight |
| Severity | Low |
| Observed | `Get-ChildItem Env:` failed while materializing the environment because duplicate keys collided under case-insensitive handling. |
| Impact | The first Gemma-path probe was invalid. |
| Resolution | Queried the process environment dictionary directly and reported only the presence boolean. |
| Verification | No configured Gemma or llama.cpp environment path was found. |
| Status | Resolved |

## ERR-2026-08-15-013: Signed Google Cloud SDK installer exited zero without a runnable installation

| Field | Value |
|---|---|
| Task | RCL-104 local CLI preflight |
| Severity | Medium |
| Observed | The official signed Windows installer exited zero, but no Google Cloud CLI files appeared in the intended or standard locations. |
| Impact | A superficial exit-code check would have produced a false PASS. |
| Resolution | Classified the attempt as failed, installed from the official SDK archive in a dedicated user-local directory, and ran its non-interactive installer. |
| Verification | `gcloud.cmd` exists and `gcloud --version` reports version `580.0.0` with exit code zero. |
| Status | Resolved |

## ERR-2026-08-15-014: Extracted SDK had no Windows launcher before bootstrap

| Field | Value |
|---|---|
| Task | RCL-104 local CLI preflight |
| Severity | Low |
| Observed | The official SDK archive contained the bootstrap scripts but no `gcloud.cmd` immediately after extraction. |
| Impact | The first post-extraction launcher check failed. |
| Resolution | Ran the archive's `install.bat` with usage reporting, PATH updates, and command completion disabled. |
| Verification | Launcher read-back and version invocation passed. |
| Status | Resolved |

## ERR-2026-08-15-015: First isolated SDK command was rejected before execution

| Field | Value |
|---|---|
| Task | RCL-104 and RCL-105 SDK import smoke |
| Severity | Low |
| Observed | The orchestration wrapper rejected the first command string because nested quoting produced invalid JavaScript. |
| Impact | No package command ran and no repository file changed. |
| Resolution | Reissued the same preregistered test with a template-literal command and unchanged package scope. |
| Verification | Five of five required SDK imports passed in the isolated environment. |
| Status | Resolved |

## ERR-2026-08-15-016: Cloud smoke cannot select safely among billing-enabled projects

| Field | Value |
|---|---|
| Task | RCL-104 and RCL-105 authenticated platform smoke |
| Severity | High |
| Observed | The authenticated identity can access 14 active projects, including 6 with billing enabled, while Recall records no target GCP project. |
| Impact | API discovery, quota checks, model calls, and temporary-resource roundtrips cannot run without risking the wrong project. |
| Mitigation | Stopped before enabling APIs or creating resources; retained only sanitized counts. |
| Resolution | Owner authorized creation of a new dedicated project; lifecycle, display name, organization parent, CLI target, and ADC quota-project read-back passed. |
| Status | Resolved by dedicated-project creation |

## ERR-2026-08-15-017: Obsidian plan read used the non-canonical filename

| Field | Value |
|---|---|
| Task | Phase 1 project-memory write-back |
| Severity | Low |
| Observed | The first read attempted `Plan.md`, but the canonical vault note is `01-Plan.md`. |
| Impact | One read failed; no note or repository file changed. |
| Resolution | Followed the Hub wikilink and read `01-Plan.md` before editing. |
| Verification | The canonical plan was read successfully. |
| Status | Resolved |

## ERR-2026-08-15-018: Interactive cloud login printed the authenticated account label

| Field | Value |
|---|---|
| Task | RCL-104 authentication smoke |
| Severity | Medium |
| Observed | The interactive CLI emitted the authenticated account label after browser login even though later probes were designed to return only sanitized counts. |
| Impact | The transient tool output contained an account identifier; it was not copied into repository or Obsidian artifacts. |
| Resolution | Subsequent auth, project, billing, and ADC probes capture raw output and emit only booleans or counts. |
| Prevent recurrence | Capture and suppress all interactive login completion output when the CLI permits it; never persist the account label. |
| Status | Resolved with exposure noted |

## ERR-2026-08-15-019: Billing-account JSON count treated a nested array as one account

| Field | Value |
|---|---|
| Task | Dedicated Recall GCP project creation |
| Severity | High |
| Observed | The first sanitized preflight reported one open billing account, but the parsed object was a nested array whose outer count was one. |
| Impact | Project creation proceeded under the correct single organization, but billing linkage used a malformed derived value and failed. No billing account was attached. |
| Diagnosis | PowerShell preserved the JSON result array as one nested object; property enumeration hid the incorrect shape. |
| Resolution | Repeated discovery using direct `value(name)` output and a joined JSON parse. Both independently showed two open billing accounts. |
| Verification | The project remains billing-disabled; no chargeable service was invoked. |
| Prevent recurrence | Assert object property names and direct-value count before treating any cloud scope as unique. |
| Status | Resolved; billing selection still blocked separately |

## ERR-2026-08-15-020: Two open billing accounts have no safe automatic match

| Field | Value |
|---|---|
| Task | Dedicated Recall GCP project creation |
| Severity | High |
| Observed | Two open billing accounts are accessible; neither has a unique organization-parent or Recall/AIstanbul display-name match. |
| Impact | The dedicated project is `ACTIVE` but cannot run billable APIs or managed platform smoke tests. |
| Mitigation | Stopped before billing linkage, API enablement, model invocation, or temporary service-resource creation. |
| Resolution condition | Owner identifies the correct billing account by its Cloud Console display name. |
| Status | Open, owner decision required |

## ERR-2026-08-15-021: Final Obsidian read-back used a malformed PowerShell parameter

| Field | Value |
|---|---|
| Task | Dedicated-project documentation verification |
| Severity | Low |
| Observed | The first final verification omitted the space between `-LiteralPath` and its variable. |
| Impact | The Obsidian read-back count was invalid; Git diff, link, and sensitive-pattern checks still completed. |
| Resolution | Corrected the parameter binding and reran the entire verification command. |
| Verification | Diff check passed, broken local links were zero, sensitive-file matches were zero, and all four Obsidian artifacts were read back. |
| Status | Resolved |

## ERR-2026-08-15-022: First deadline-conversion command was rejected before execution

| Field | Value |
|---|---|
| Task | RCL-101 deadline verification |
| Severity | Low |
| Observed | The orchestration wrapper rejected the first Python command because nested quoting produced invalid JavaScript. |
| Impact | No time conversion ran and no repository file changed. |
| Resolution | Reissued the deterministic `zoneinfo` conversion with a template-literal command. |
| Verification | Submission deadline converted to 2026-09-01 03:00 Europe/Istanbul; credit-request deadline converted to 2026-08-28 22:00. |
| Status | Resolved |

## ERR-2026-08-15-023: Live Devpost Rules page was not independently retrievable

| Field | Value |
|---|---|
| Task | RCL-101 source-currentness verification |
| Severity | Medium |
| Observed | Official-domain web searches returned no indexed Rules result, and direct Devpost URL retrieval was blocked by the browsing layer. |
| Impact | The owner-supplied official Rules snapshot could be analyzed and hash-pinned, but its live-page currency was not independently proven. |
| Mitigation | Treat the snapshot as the current working source and require a live Devpost comparison before implementation freeze and final submission. |
| Status | Open, verification retry required |

## ERR-2026-08-15-024: First RCL-102 synchronization patch used a stale STATUS anchor

| Field | Value |
|---|---|
| Task | RCL-102 documentation synchronization |
| Severity | Low |
| Observed | The multi-file patch expected an RCL-101 sentence whose wording differed from the current `STATUS.md`. |
| Impact | The patch was rejected before any partial write. Newly created policy and ADR files were unaffected. |
| Resolution | Read the current files and applied smaller patches with exact anchors. |
| Verification | Subsequent diff, link, and consistency checks cover all intended RCL-102 updates. |
| Status | Resolved |

## ERR-2026-08-15-025: Obsidian routing reference was read from the wrong level

| Field | Value |
|---|---|
| Task | RCL-102 and project-memory write-back |
| Severity | Low |
| Observed | The first read requested `obsidian-project-memory/NOTE-ROUTING.md` instead of `obsidian-project-memory/references/NOTE-ROUTING.md`. |
| Impact | One instruction read failed; no project or vault file changed. |
| Resolution | Read the full reference from the correct `references/` path before writing. |
| Verification | Routing classified this turn as project planning plus daily/project-memory synchronization. |
| Status | Resolved |

## ERR-2026-08-15-026: First Obsidian detect used uv from the wrong working directory

| Field | Value |
|---|---|
| Task | Project-memory binding verification |
| Severity | Medium |
| Observed | `uv run` executed from the VUS workspace, created a new local `.venv`, and attempted to build that unrelated project before failing on an undeclared setuptools backend. |
| Impact | No Recall or vault file changed. A newly created ignored `.venv` existed briefly in the unrelated workspace. |
| Resolution | Resolved and checked the exact `.venv` path inside the VUS workspace, removed only that newly created directory, then ran the project-memory detector directly with Python from the Recall working directory. |
| Verification | The accidental `.venv` no longer exists; detector read-back reports Recall is registered as `recall-project` with the expected vault and English note language. |
| Prevent recurrence | Run project-memory helpers with an explicit Recall working directory and direct Python unless an isolated uv environment is intentionally required. |
| Status | Resolved |

## ERR-2026-08-15-027: Live Rules search remained empty during license recheck

| Field | Value |
|---|---|
| Task | RCL-102 repository-license verification |
| Severity | Medium |
| Observed | A second official-title and Devpost-domain web search returned no live Rules result. |
| Impact | Live currency remains unproven; the hash-pinned owner-supplied official Rules snapshot remains the working binding source. |
| Mitigation | Apache-2.0 was checked against the full snapshot. Keep the scheduled live-page comparison before feature freeze and final submission. |
| Status | Open, same source-currentness dependency as ERR-2026-08-15-023 |

## ERR-2026-08-15-028: Demo document patch ran before its parent directory existed

| Field | Value |
|---|---|
| Task | RCL-207 and RCL-208 |
| Severity | Low |
| Observed | The first patch could not create `docs/demo/FOUR_MINUTE_STORYBOARD.md` because `docs/demo/` did not exist. |
| Impact | The patch was rejected without writing any of the three planned documents. |
| Resolution | Created the exact `docs/demo/` directory and applied the documents separately. |
| Verification | Storyboard, web information architecture, and derived-value registry exist and are included in the final link audit. |
| Status | Resolved |

## ERR-2026-08-16-029: Initial ScanRun sketch mixed privacy, evidence, and policy authority

| Field | Value |
|---|---|
| Task | RCL-203 and RCL-204 design freeze |
| Severity | High |
| Observed | The accepted target sketch placed local privacy quarantine inside a cloud `ScanRun`, treated `NO_CHANGE_FOUND` as a state, and had no truthful terminal when Policy Gate itself was unavailable. |
| Impact | Implementation could have created a cloud record for rejected input, bypassed Policy Gate on no-change, or let Controller fabricate `ABSTAIN`. |
| Resolution | ADR-0007 creates a run only after accepted privacy, routes no-change through policy, and separates technical `HALTED` from semantic outcomes. |
| Verification | Target architecture, lifecycle tables, policy spec, UI state rules, and derived-value registry now use the same distinction. Executable tests remain Phase 3. |
| Status | Resolved at design level |

## ERR-2026-08-16-030: Derived-value paths and draft contract envelope diverged

| Field | Value |
|---|---|
| Task | RCL-202 and RCL-208 consistency audit |
| Severity | High |
| Observed | The existing derived-value registry expected several nested `$.artifact.*` and payload paths that did not match the first flat common-envelope draft; several UI artifact types were also absent from the catalog. |
| Impact | Backend schemas and UI could both pass isolated tests while reading different fields, recreating a silent hard-coded or default-value failure. |
| Resolution | Froze one flat envelope, aligned all affected UI paths, added operational/evaluation artifacts to the catalog, and added explicit change-together governance. |
| Verification | Cross-document path and catalog audits are required in the final verification for this work unit; executable mutation tests remain RCL-302 and RCL-307. |
| Status | Resolved at design level |

## ERR-2026-08-16-031: First canonical synchronization patch used a non-existent Handoff sentence

| Field | Value |
|---|---|
| Task | Phase 2 documentation synchronization |
| Severity | Low |
| Observed | One multi-file patch expected a Policy Gate sentence that exists in `MASTER_PLAN.md` but not verbatim in `HANDOFF.md`. |
| Impact | The patch was rejected before any partial write. New architecture documents were unaffected. |
| Resolution | Applied smaller patches against exact current anchors and recorded the technical-halt rule in the correct Handoff section. |
| Verification | Final consistency and link audits cover the synchronized files. |
| Status | Resolved |

## ERR-2026-08-16-032: Installed PowerShell lacked the static SHA256 HashData API

| Field | Value |
|---|---|
| Task | RCL-205 source hashing |
| Severity | Low |
| Observed | The first hash probe downloaded seven official responses but `[System.Security.Cryptography.SHA256]::HashData` was unavailable in the installed PowerShell/.NET runtime, so the hashes were null. |
| Impact | No invalid hash was accepted or written. The downloaded response lengths were visible, but the probe could not satisfy the manifest gate. |
| Resolution | Recomputed every response with `SHA256.Create().ComputeHash` and checked all outputs for 64 lowercase hexadecimal characters. |
| Status | Resolved |

## ERR-2026-08-16-033: Restricted network probe could not reach NCBI

| Field | Value |
|---|---|
| Task | RCL-205 source retrieval |
| Severity | Low |
| Observed | A sandboxed command-line retrieval could not connect to NCBI. |
| Impact | The first probe returned no source content and made no repository change. |
| Resolution | Repeated the read-only retrieval through the approved network path; official responses were returned and hashed. |
| Status | Resolved |

## ERR-2026-08-16-034: ESearch did not resolve historical VCV accession versions

| Field | Value |
|---|---|
| Task | RCL-205 ClinVar version retrieval |
| Severity | Medium |
| Observed | ESearch returned no result for historical `VCV...version` accessions even though ClinVar's documented version URLs resolved them. |
| Impact | ESearch alone could have produced a false missing-source conclusion. |
| Resolution | Used direct documented ClinVar `accession.version` URLs, read each page back, and treated the VCV accession version as the semantic anchor. |
| Prevent recurrence | Historical replay connectors must not equate ESearch absence with source absence; they must use the documented version route and fail loudly if that route also fails. |
| Status | Resolved at selection level; executable connector test remains RCL-503 |

## ERR-2026-08-16-035: Springer Nature supplement retrieval returned a client-challenge page

| Field | Value |
|---|---|
| Task | RCL-205 exact-variant verification |
| Severity | Medium |
| Observed | Both browser retrieval and direct download of the Nature supplementary XLSX produced an automated cookie/client-challenge response. The downloaded 3038-byte HTML shell caused `openpyxl` to raise `BadZipFile`. |
| Impact | The publisher supplement could not be used as an independently hashable exact-row source in this environment. |
| Resolution | Excluded the challenge response from evidence. Downloaded the official NCBI GEO `GSE248438` result XLSX, verified the exact `c.7522G>C / G2508R` row, and hashed the binary. Nature article text or supplements were not redistributed. |
| Status | Resolved with an authoritative alternate source |

## ERR-2026-08-16-036: Installed PowerShell lacked Get-Date AsUTC

| Field | Value |
|---|---|
| Task | RCL-205 documentation timestamp |
| Severity | Low |
| Observed | `Get-Date -AsUTC` was not supported by the installed PowerShell version. |
| Impact | The first timestamp command failed; Git status still completed and no file changed. |
| Resolution | Used `(Get-Date).ToUniversalTime()` for the timestamp. |
| Status | Resolved |

## ERR-2026-08-16-037: First evidence-ledger read used two obsolete filenames

| Field | Value |
|---|---|
| Task | RCL-205 ledger synchronization |
| Severity | Low |
| Observed | The first read requested `CLAIM_LEDGER.md` and `DEMO_EVIDENCE_LEDGER.md`; the repository uses `CLAIM_EVIDENCE_LEDGER.md` and `DEMO_EVIDENCE_LOG.md`. |
| Impact | Those two reads failed, while other read-only inspections completed. No file changed. |
| Resolution | Enumerated the evidence directory and read the canonical filenames before patching. |
| Status | Resolved |

## ERR-2026-08-16-038: Case-insensitive UI field audit undercounted Turkish-locale IDs

| Field | Value |
|---|---|
| Task | Phase 2 design package audit |
| Severity | Medium |
| Observed | The first PowerShell regex counted 21 UI Field IDs instead of 49. Case-insensitive matching under Turkish locale did not treat ASCII `I` uniformly inside `[A-Z]`. |
| Impact | The first count was incomplete and could not prove registry coverage. No file changed. |
| Resolution | Repeated extraction with `Select-String -CaseSensitive`, then grouped the exact IDs. |
| Verification | 49 total IDs, 49 unique IDs, and zero duplicates. |
| Prevent recurrence | Use ordinal/case-sensitive matching for identifiers and hashes. Never use locale-sensitive default matching for audit counts. |
| Status | Resolved |

## ERR-2026-08-16-039: PowerShell altered Markdown backticks in the first contract audit

| Field | Value |
|---|---|
| Task | Phase 2 UI-to-contract coverage audit |
| Severity | Medium |
| Observed | Markdown backticks embedded in a PowerShell double-quoted Python command were interpreted by the shell, producing an invalid extraction result. A second over-escaped attempt also returned an empty reference set. |
| Impact | Neither attempt could establish contract coverage. No file changed and neither result was accepted. |
| Resolution | Generated the backtick as `chr(96)` inside Python and reran extraction against the contract catalog and derived-value registry. |
| Verification | 20 UI-referenced artifact types were extracted and zero were missing from the contract catalog. |
| Prevent recurrence | Avoid shell-significant Markdown characters in nested commands; print the compiled pattern and require a nonzero expected reference count. |
| Status | Resolved |

## ERR-2026-08-16-040: Cursor bot added an unsolicited PR upsell comment

| Field | Value |
|---|---|
| Task | RCL-211 PR metadata verification |
| Severity | High |
| Observed | Immediately after PR #2 creation, GitHub read-back found one visible comment from `cursor[bot]`. After a later governance push, the same upsell behavior recurred. The comments stated that Bugbot was disabled and advertised enabling it; no actual review was performed. |
| Impact | Commit and PR authorship remained owner-only, but the visible repository surface contained an external automated assistant/bot signature, violating the owner's stricter no-assistant-signature rule. |
| Resolution | Deleted only exact issue-comment IDs `5304443775` and, after recurrence, `5304471224` through the GitHub API; no human review content was altered. |
| Verification | Post-delete read-back found zero visible PR comments, zero visible PR reviews, zero commits with non-owner author/committer or forbidden metadata, and no forbidden marker in PR title/body. |
| Prevent recurrence | No further push is permitted until the owner confirms that the Cursor GitHub integration is disabled for Recall. Every later push still requires comment/review/check/actor read-back. |
| Status | Visible comments removed; hard no-push blocker remains |

## ERR-2026-08-16-041: Combined staged audit overwrote the diff-check exit code

| Field | Value |
|---|---|
| Task | Post-PR governance commit audit |
| Severity | Low |
| Observed | A combined PowerShell probe ran `git diff --cached --check`, then a no-match secret `git grep`. The report read `$LASTEXITCODE` only after grep and incorrectly labeled the staged diff as failed. |
| Impact | No commit or push occurred under the incorrect label. The raw diff command had emitted no error, but its exit code was not captured immediately. |
| Resolution | Reran the probe while capturing each command's exit code immediately. |
| Verification | Staged diff exit was `0` and secret grep exit was `1`, correctly meaning whitespace PASS and zero credential-pattern files. |
| Prevent recurrence | Store every command exit immediately; never reuse a shared `$LASTEXITCODE` after another probe. |
| Status | Resolved |

## ERR-2026-08-17-042: Candidate-delta routing had no deterministic producer

| Field | Value |
|---|---|
| Audit finding | F-01, P1 |
| Observed | `material_delta_present` selected the no-change versus Assessor/Auditor route without a named deterministic producer, while the Assessor emitted a `materiality_proposal`. |
| Impact | An LLM proposal could suppress audit and cause `NO_ACTION`. |
| Resolution | ADR-0008 assigns exact-allele, scope, completeness, and new-observation-hash candidate detection to the Controller/normalizer. |
| Verification required | Candidate plus Assessor dismissal is not `NO_ACTION`; no candidate invokes neither Assessor nor Auditor. |
| Status | Open; blocks merge and Phase 3 |

## ERR-2026-08-17-043: Memory conflict rules could change policy outcome

| Field | Value |
|---|---|
| Audit finding | F-02, P1 |
| Observed | Normative documents alternately required memory conflict to force `ABSTAIN` or be rejected and ignored, while memory was both excluded from and present in policy inputs. |
| Impact | Poisoned memory could suppress a legitimate result and break memory-on/off parity. |
| Resolution | ADR-0008 removes memory from policy inputs and requires rejection/ignore receipts plus policy and task parity. |
| Verification required | Poisoned memory yields `REJECTED`, identical PolicyDecision bytes, and zero task delta with memory disabled. |
| Status | Open; blocks merge and Phase 3 |

## ERR-2026-08-17-044: Material citation mismatch behavior contradicted the fail-closed gate

| Field | Value |
|---|---|
| Audit finding | F-03, P1 |
| Observed | One architecture row allowed removing a mismatched citation and continuing, while evaluation required every material mismatch to block review. The storyboard preselected the wrong reason code. |
| Impact | A fabricated material claim could be dropped without a new complete audit, or the demo could show a hard-coded incorrect outcome explanation. |
| Resolution | ADR-0008 makes every rejected material claim fail `all_material_claims_verified`; continuation requires a new fully audited assessment artifact. |
| Verification required | N verified plus one mismatched material claim yields `ABSTAIN`, `material_claim_unverified`, and zero tasks. |
| Status | Open; blocks merge and Phase 3 |

## ERR-2026-08-17-045: Boolean policy facts and short-circuit examples lost not-evaluated state

| Field | Value |
|---|---|
| Audit finding | F-04, P1 |
| Observed | The policy promised every applicable lexical reason, but the truth table used short-circuit markers and examples omitted applicable reasons; Boolean false conflated failure with a check that never ran. |
| Impact | Policy records could falsely claim a failed audit rather than an unevaluated audit and could produce unstable reason sets. |
| Resolution | ADR-0008 requires evaluated-state facts and every applicable lexical reason code with explicit `*_not_evaluated` projection. |
| Verification required | Snapshot examples list all reasons; one fact mutation changes exactly the corresponding code; an unrun required audit emits `citation_audit_not_evaluated`. |
| Status | Open; blocks merge and Phase 3 |

## ERR-2026-08-17-046: Core demo's mixed data provenance was rejected by its own contract

| Field | Value |
|---|---|
| Audit finding | F-05, P1 |
| Observed | The design required a `SYNTHETIC` WatchCase plus `CAPTURED_REPLAY` evidence, while the contract rejected any input mode mismatch and UI text implied one scalar mode. |
| Impact | The canonical demo run could not pass contract validation without an invented silent conversion. |
| Resolution | ADR-0008 keeps atomic artifact modes and adds a deterministic run-level mode set plus closed allowed compositions. |
| Verification required | Synthetic plus captured replay passes and renders both; mock plus captured replay and live-public injection into replay fail. |
| Status | Open; blocks merge and Phase 3 |

## ERR-2026-08-17-047: WatchCase cursor behavior after unsafe terminals was undefined

| Field | Value |
|---|---|
| Audit finding | F-06, P1 |
| Observed | No normative rule defined cursor, snapshot, pending-observation, attention, or scheduling actions after `ABSTAIN`, `HALTED`, or `duplicate_suppressed`. |
| Impact | A transient failure could mark unaudited evidence as seen or leave a case silently stalled. |
| Resolution | ADR-0008 allows advancement only on verified `NO_ACTION` or `REVIEW_REQUIRED`, preserves pending hashes on unsafe terminals, and requires explicit attention/recovery behavior. |
| Verification required | Outage, `ABSTAIN`, restore, and retry observes the same previously unaudited observation hash. |
| Status | Open; blocks merge and Phase 3 |

## ERR-2026-08-17-048: Frozen replay hashes bound dynamic ClinVar HTML

| Field | Value |
|---|---|
| Audit finding | F-07, P1 |
| Observed | Six manifest hashes referred to dynamic printable-page responses, but captured bytes were absent. On 2026-08-17 two immediate same-URL downloads had equal lengths, unequal hashes, and different `ncbi_phid` lines. |
| Impact | A faithful replay would halt on a clean run or silently weaken integrity checking. |
| Resolution | ADR-0008 selects exact repository captures with per-source metadata and offline byte hashes for protocol 1.0.1; live re-fetch is a separate mode. |
| Verification required | Clean clone verifies every captured hash offline; one mutated byte fails. |
| Status | Open; blocks merge, RCL-205, and RCL-503 |

## ERR-2026-08-17-049: Replay chronology and GEO linkage metadata were incomplete

| Field | Value |
|---|---|
| Audit finding | F-08, P1 |
| Observed | The package omitted GEO public/update dates and current linked PMID `41957374`, while binding the exact row to qualifying paper PMID `39779848` without stating the linkage predicate or as-captured file status. |
| Impact | The positive fixture could fail its own citation-mismatch rule or overstate when the exact XLSX row was publicly available. |
| Resolution | ADR-0008 records separate publication, GEO public/update, current linkage, and capture facts; the Nature data-availability statement supplies the publication-to-GEO accession link. |
| Verification required | Auditor dry-run verifies accession, paper data-availability, contributor/scope consistency, exact allele row, and explicit as-captured timestamp without requiring current GEO PMID equality. |
| Status | Open; blocks merge, RCL-205, RCL-503, and RCL-506 |

## ERR-2026-08-17-050: First audit-triage synchronization patch used an incorrect Handoff anchor

| Field | Value |
|---|---|
| Task | RCL-211 audit-triage documentation |
| Severity | Low |
| Observed | The first multi-file patch omitted the numeric list prefixes present in `HANDOFF.md`, so patch verification rejected the entire batch. |
| Impact | No partial write occurred; the two already-created standalone audit files were unaffected. |
| Resolution | Read the exact lines and applied smaller file-scoped patches against current anchors. |
| Verification | Git status showed only the intended two new files before the corrected patches. |
| Status | Resolved |

## ERR-2026-08-17-051: First Markdown link audit failed on an empty Markdown file

| Field | Value |
|---|---|
| Task | RCL-211 correction-package local verification |
| Severity | Medium |
| Observed | `Get-Content -Raw` returned null for the empty ignored file `.remember/now.md`; the regex link scanner threw before completing, while a later line misleadingly printed `broken_links=0`. |
| Impact | The first reported zero could not be accepted as link evidence. No repository content was changed by the probe. |
| Resolution | Treat null text as an empty string, count scanned files, collect scanner errors separately, and require both zero scanner errors and zero broken links. |
| Verification | The corrected probe result is recorded in the current work report, not inferred from the failed run. |
| Status | Resolved |

## ERR-2026-08-17-052: Policy-row ordering probe used an ambiguous PowerShell variable reference

| Field | Value |
|---|---|
| Task | ADR-0008 F-04 consistency verification |
| Severity | Low |
| Observed | The first read-only probe placed a colon immediately after `$row` inside an interpolated string. PowerShell parsed `$row:` as a drive-qualified variable and stopped before checking any policy row. |
| Impact | The failed attempt supplied no policy-ordering evidence. Repository content was not changed by the probe. |
| Resolution | Re-ran with the explicitly delimited `${row}` variable reference. |
| Verification | The corrected probe checked all 11 representative policy rows and found zero lexical-order or duplicate-code errors. |
| Prevent recurrence | Delimit interpolated PowerShell variable names with braces when punctuation immediately follows. |
| Status | Resolved |

## Resolution checkpoint 2026-08-17: ERR-042 through ERR-047

ADR-0008 decisions 1 through 6 were synchronized across the normative policy, contracts, lifecycle, architecture, threat, evaluation, replay-design, demo, UI-lineage, and evidence documents. The scoped local consistency audit passed and is recorded in `docs/evaluation/reports/2026-08-17--adr-0008-normative-consistency-audit.md`.

This closes ERR-042 through ERR-047 at corrected-document level only. Their executable verification obligations remain assigned to implementation and evaluation tasks. F-07/F-08, RCL-205, merge, push, external follow-up review, and Phase 3 remain blocked.

## ERR-2026-08-17-053: Graphify update produced no output and did not refresh the graph

| Field | Value |
|---|---|
| Task | Post-correction knowledge-graph refresh |
| Severity | Medium |
| Observed | `graphify update .` ran for approximately two minutes without output or completion and was interrupted. `graphify-out/graph.json` and `GRAPH_REPORT.md` retained their prior 2026-08-17 01:02:23 timestamps. |
| Impact | The current Graphify graph does not prove coverage of the final F-01 through F-06 correction package. Direct source-document checks remain authoritative for this audit. |
| Resolution | None in this turn; the hung process was stopped without modifying tracked repository files. |
| Verification required | Diagnose the update path, complete a document-aware refresh, and query ADR-0008 plus `CandidateDeltaReceipt` before relying on graph freshness. |
| Prevent recurrence | Treat graph timestamps and post-update concept queries as mandatory freshness evidence; never equate a started update with a refreshed graph. |
| Status | Open; does not block protocol 1.0.1 source work |

## ERR-2026-08-17-054: Batched final policy probe omitted whitespace in `foreach`

| Field | Value |
|---|---|
| Task | Final ADR-0008 consistency audit |
| Severity | Low |
| Observed | One batched PowerShell sub-command used `foreach($line in$lines)`, which failed parsing before the policy-row check ran. The other independently reported batch checks completed. |
| Impact | That batch supplied no final policy-order evidence; no repository content was changed by the probe. |
| Resolution | Re-ran the policy check as a separate command with `foreach ($line in $lines)`. |
| Verification | The independent retry checked 11 rows and returned zero ordering or duplicate-code errors. |
| Prevent recurrence | Keep readable spacing in PowerShell control syntax and treat every batched sub-command as an independent result. |
| Status | Resolved |

## ERR-2026-08-17-055: Batched final JSON probe repeated compressed `foreach` syntax

| Field | Value |
|---|---|
| Task | Final ADR-0008 JSON consistency audit |
| Severity | Low |
| Observed | A compressed batched sub-command used `foreach($file in$jsonFiles)` and failed parsing before either final JSON count was emitted. |
| Impact | That batch supplied no final JSON evidence; no repository content was changed by the probe. |
| Resolution | Re-ran the fenced-JSON and repository-JSON checks as one readable standalone command with explicit spacing. |
| Verification | The independent retry parsed 3 fenced JSON examples and 71 JSON files with zero errors. |
| Prevent recurrence | Do not minify audit commands; prefer readable standalone probes when their result is evidence. |
| Status | Resolved |

## Resolution checkpoint 2026-08-17: ERR-053

The refreshed graph now contains ADR-0008, `CandidateDeltaReceipt`, and the scoped consistency-audit document nodes. Direct inspection of `graphify-out/graph.json` found 131 nodes and 154 links. Graphify CLI traversal reliability remains separately tracked in ERR-057.

## ERR-2026-08-17-056: Graphify reflection directory was blocked by the sandbox

| Field | Value |
|---|---|
| Task | Updated Graphify coverage check |
| Severity | Low |
| Observed | `graphify reflect --if-stale` initially failed with `PermissionError` while writing under `graphify-out/reflections`. |
| Impact | The first reflection attempt supplied no freshness evidence. |
| Resolution | Re-ran the same bounded command with filesystem approval; it completed and generated `LESSONS.md` with zero memories. |
| Verification | Graph file timestamp, node/link counts, and required node presence were checked independently. |
| Status | Resolved |

## ERR-2026-08-17-057: Graphify query and explain commands hung without output

| Field | Value |
|---|---|
| Task | Updated Graphify concept traversal |
| Severity | Medium |
| Observed | `graphify query` and `graphify explain "CandidateDeltaReceipt"` produced no output and did not terminate. Both processes were interrupted. |
| Impact | CLI traversal cannot be treated as current concept evidence in this turn. |
| Resolution | Used deterministic direct inspection of the current graph JSON to verify exact nodes, incoming links, source locations, and graph counts. |
| Verification required | Diagnose the CLI traversal hang before relying on query/explain output. |
| Status | Open; does not invalidate direct graph-file evidence |

## ERR-2026-08-17-058: Evidence test patch targeted a missing parent directory

| Field | Value |
|---|---|
| Task | RCL-205 offline verifier TDD |
| Severity | Low |
| Observed | The first patch for the verifier test failed because `scripts/evidence` did not yet exist. |
| Impact | No partial file was created and no test ran. |
| Resolution | Created the exact bounded directory and reapplied the patch. |
| Status | Resolved |

## ERR-2026-08-17-059: Machine execution policy blocked direct verifier invocation

| Field | Value |
|---|---|
| Task | RCL-205 offline verifier execution |
| Severity | Low |
| Observed | Direct execution of the signed-local PowerShell scripts was blocked by the machine execution policy. |
| Impact | The initial invocation supplied no verification result. |
| Resolution | Used process-scoped `powershell.exe -NoProfile -ExecutionPolicy Bypass -File`; no persistent policy was changed. |
| Status | Resolved |

## ERR-2026-08-17-060: Parameter default resolved an empty script root under Windows PowerShell 5.1

| Field | Value |
|---|---|
| Task | RCL-205 offline verifier implementation |
| Severity | Medium |
| Observed | `$PSScriptRoot` was empty when evaluated as a parameter default, so the verifier could not resolve the repository root. |
| Impact | The first executable verifier run failed before checking captures. |
| Resolution | Moved repository-root default resolution into the script body. |
| Verification | Clean verification later passed all declared captures and checks. |
| Status | Resolved |

## ERR-2026-08-17-061: Integrity failure was followed by an unsafe semantic parse attempt

| Field | Value |
|---|---|
| Task | RCL-205 mutation test |
| Severity | Medium |
| Observed | The first mutated-byte test detected the hash mismatch but continued into PubMed JSON parsing and emitted an unrelated raw parser error. |
| Impact | Failure output was noisy and could obscure the primary integrity rejection. |
| Resolution | Excluded integrity-failed captures from all semantic parsing while preserving fail-loud rejection. |
| Verification | The final mutation test rejects the changed byte and reports a bounded test result. |
| Status | Resolved |

## ERR-2026-08-17-062: XLSX XML parser assumed every cell had a type attribute

| Field | Value |
|---|---|
| Task | RCL-205 exact-row verification |
| Severity | Medium |
| Observed | Under StrictMode, reading a cell without XML attribute `t` failed through property access. |
| Impact | The first integrated exact-row check could not complete. |
| Resolution | Read the attribute through `GetAttribute('t')`, which safely returns an empty value when absent. |
| Verification | The verifier found exactly one matching row and checked all expected cell values. |
| Status | Resolved |

## ERR-2026-08-17-063: Compressed parser-review command omitted required whitespace

| Field | Value |
|---|---|
| Task | Evidence-script parser review |
| Severity | Low |
| Observed | A read-only review command used `foreach($file in$files)` and failed before checking the scripts. |
| Impact | The failed probe supplied no parser evidence. |
| Resolution | Re-ran the review as a readable command with explicit spacing. |
| Status | Resolved |

## ERR-2026-08-17-064: Nested PowerShell parser probe expanded variables in the outer shell

| Field | Value |
|---|---|
| Task | Complete F-01 through F-08 follow-up audit |
| Severity | Low |
| Observed | A nested `powershell.exe -Command` parser probe placed the inner script in double quotes, so the outer shell expanded its variables before execution. |
| Impact | The failed attempt parsed no evidence scripts. The independently executed verifier and fault tests in the same batch were unaffected. |
| Resolution | Ran the parser API directly in the current PowerShell process with explicit variables. |
| Verification | Three evidence scripts parsed with zero errors. |
| Status | Resolved |

## ERR-2026-08-17-065: First UI reconciliation probe used obsolete ID and generic code-span assumptions

| Field | Value |
|---|---|
| Task | Complete F-01 through F-08 follow-up audit |
| Severity | Medium |
| Observed | The first probe expected numeric `UI-000` IDs and treated every backticked value as an artifact type. It returned zero IDs and five false missing types. |
| Impact | That result supplied no UI-registry evidence and could have falsely reported contract gaps. |
| Resolution | Parsed only ordinal `| UI-` table rows, used the Source column, and extracted only leading artifact-type tokens. |
| Verification | Corrected result: 52 rows, 52 unique IDs, zero duplicates, 21 artifact types, and zero missing contract types. |
| Status | Resolved |

## ERR-2026-08-17-066: First UI source-row display probe piped directly after a `foreach` statement

| Field | Value |
|---|---|
| Task | UI reconciliation diagnosis |
| Severity | Low |
| Observed | A diagnostic command placed a pipeline directly after a `foreach` statement and PowerShell rejected the empty pipe element. |
| Impact | The probe displayed no source rows. |
| Resolution | Collected rows into an array before converting them to JSON. |
| Status | Resolved |

## ERR-2026-08-17-067: First Graphify node check assumed the wrong exact ADR label

| Field | Value |
|---|---|
| Task | Updated Graphify coverage audit |
| Severity | Low |
| Observed | The graph check expected label `ADR-0008: External Audit Corrections`; the actual current label is `ADR-0008: External audit corrections before implementation`. |
| Impact | The exact-label predicate returned false even though the required node existed. |
| Resolution | Queried labels containing `ADR-0008`, `CandidateDelta`, or `Consistency` and checked the actual node IDs and labels. |
| Verification | The current graph contains the ADR document node, `CandidateDeltaReceipt`, and the normative consistency-audit node. |
| Status | Resolved |

## ERR-2026-08-17-068: Multi-file status patch completed writes but did not return

| Field | Value |
|---|---|
| Task | Follow-up-audit status synchronization |
| Severity | Medium |
| Observed | A multi-file `apply_patch` process continued without output after applying changes to Status, Master Plan, and Handoff. It was terminated after bounded waits. |
| Impact | Patch completion could not be inferred from the tool state, and the final task-plan hunk had not applied. |
| Resolution | Read back every target, confirmed the three applied files, and applied the remaining task-plan changes separately. |
| Verification | Current source files show the passed follow-up state and next remote-review gate consistently. |
| Status | Resolved |

## ERR-2026-08-17-069: Compressed final UI probe omitted whitespace after `in`

| Field | Value |
|---|---|
| Task | Final follow-up-audit verification |
| Severity | Low |
| Observed | The compressed final command used `foreach($match in[regex]::Matches(...))`; PowerShell rejected it before UI reconciliation ran. |
| Impact | That individual probe supplied no final UI evidence. Other final checks in the parallel batch completed independently. |
| Resolution | Re-ran the UI/contract reconciliation as a readable standalone command with explicit whitespace. |
| Verification | Corrected result: 52 rows, 52 unique IDs, zero duplicates, 21 artifact types, and zero missing contract types. |
| Status | Resolved |

## Resolution checkpoint 2026-08-17: ERR-057

The raw Recall Graphify commands were not merely slow; three parent shells and three direct `graphify.exe` children remained live. All six Recall-scoped processes were stopped. The repository already contains a mandatory no-stamp runner policy in `AGENTS.md`. The runner completed `query`, `explain`, directed `path`, and undirected `path` invocations without hanging. Raw `graphify query`, `graphify explain`, and `graphify path` remain prohibited on this OneDrive checkout.

## ERR-2026-08-17-070: Initial raw-process inventory lacked CIM permission

| Field | Value |
|---|---|
| Task | Recall Graphify raw-process cleanup |
| Severity | Low |
| Observed | The first `Get-CimInstance Win32_Process` inventory returned `Access denied`. |
| Impact | The unprivileged attempt could not prove whether raw Graphify processes remained active. |
| Resolution | Re-ran the read-only inventory with explicit approval, identified only the Recall-scoped raw processes, enumerated their direct children, and stopped those exact six process IDs. An unrelated global-graph process was left untouched. |
| Verification | Post-stop inventory returned `remaining=0` for the six exact targets. |
| Status | Resolved |

## ERR-2026-08-17-071: First staging attempt could not create the Git index lock

| Field | Value |
|---|---|
| Task | Owner-only correction-package publish |
| Severity | Low |
| Observed | The sandboxed `git add -A` attempt returned permission denied for `.git/index.lock`. Later read-only commands in the same shell caused the combined shell exit code to appear successful. |
| Impact | No file was staged by that attempt, and the combined exit code could not be used as staging evidence. |
| Resolution | Re-ran only `git add -A` with explicit filesystem approval and checked its own exit code. |
| Status | Resolved |

## ERR-2026-08-17-072: First staged-capture hash probe assumed the wrong manifest key

| Field | Value |
|---|---|
| Task | Staged replay-byte verification |
| Severity | Low |
| Observed | The first read-only Python probe looked for `captures`; protocol 1.0.1 uses `captured_sources`. |
| Impact | The failed probe compared no files. |
| Resolution | Inspected the manifest schema and re-ran against `captured_sources` and `capture_path`. |
| Status | Resolved |

## ERR-2026-08-17-073: Git normalization changed one staged replay capture

| Field | Value |
|---|---|
| Task | Staged replay-byte verification |
| Severity | Critical |
| Observed | The working `GSE248438.brief.soft.txt` matched manifest SHA256 `0723093e...`, but its staged blob became `127a0c91...` because the repository-wide text rule normalized CRLF to LF. |
| Impact | A clean clone of the proposed commit would fail the frozen-byte verifier even though the pre-stage working tree passed. |
| Resolution | The first `-text` override still inherited `eol=lf` and produced only 9/10 staged matches. `-text -eol` restored all hashes, but generic diff checking then treated immutable upstream whitespace as repository-authored defects. The final exact evidence rule is `binary -eol`; it preserves bytes, disables inappropriate textual diff/merge treatment, and leaves whitespace checks active for authored files. |
| Verification | Ten of ten working-tree captures and ten of ten staged blobs match the manifest. A clean-clone verifier run remains a post-commit gate. |
| Status | Resolved for staging; clean-clone gate remains mandatory |

## ERR-2026-08-17-074: Initial Nature linkage probe used a guessed filename

| Field | Value |
|---|---|
| Task | Auditor finding evidence inspection |
| Severity | Low |
| Observed | A read-only probe requested `artifacts/evidence/rcl-205/publication-geo-linkage.json`, which does not exist. |
| Impact | That one read returned no linkage JSON; no file was changed. |
| Resolution | Read the manifest first and used the declared path `artifacts/evidence/rcl-205/nature/PMID39779848.data-availability-linkage.json`. |
| Status | Resolved |

## ERR-2026-08-17-075: Expanded harness was first invoked without the process-scoped execution bypass

| Field | Value |
|---|---|
| Task | Test-first auditor remediation |
| Severity | Low |
| Observed | Direct invocation of the PowerShell test script was blocked because script execution is disabled on the machine. |
| Impact | The first invocation supplied no test evidence and changed no machine policy. |
| Resolution | Re-ran with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File`, which scopes the bypass to that process. |
| Verification | The expected initial red test failed on the missing ClinVar semantic rejection; the final harness passed all cases. |
| Status | Resolved |

## ERR-2026-08-17-076: Initial reparse defense rejected OneDrive cloud placeholders

| Field | Value |
|---|---|
| Task | Capture-root containment remediation |
| Severity | Medium |
| Observed | Windows reports the Recall repository and evidence directories as `ReparsePoint` because they are OneDrive cloud placeholders, even though they have no link type or target. The first production-tree verifier rejected the legitimate capture root. |
| Impact | The production checkout failed before reading captures; temporary non-OneDrive test copies still passed. |
| Resolution | Reparse defense now rejects only target-bearing link/junction entries. OneDrive placeholder entries with empty `LinkType` and `Target` remain usable. |
| Verification | Production-tree verifier passes; a real temporary junction to an out-of-root target is still rejected as `capture_path_reparse_point`. |
| Status | Resolved |

## ERR-2026-08-17-077: Combined verification probe used an ambiguous variable boundary

| Field | Value |
|---|---|
| Task | Final remediation verification |
| Severity | Low |
| Observed | A combined read-only probe used `$file:` inside an interpolated error string; PowerShell parsed the colon as part of a scoped variable and rejected the command before any checks ran. |
| Impact | That probe supplied no evidence and changed no files. |
| Resolution | Re-ran with `${file}` and kept each evidence command behind its own exit check. |
| Verification | Three PowerShell files parsed, four JSON files parsed, the clean verifier passed, and the expanded fault harness passed. |
| Status | Resolved |

## ERR-2026-08-17-078: GitHub installation probe returned 403 and null arrays looked non-empty

| Field | Value |
|---|---|
| Task | Cursor integration and PR-surface read-back |
| Severity | Medium |
| Observed | `gh api user/installations` requires a token authorized as a GitHub App and returned HTTP 403. The same combined PowerShell command continued and wrapped null JSON results in arrays, incorrectly displaying comment/review counts of one. |
| Impact | The probe supplied no evidence about Cursor installation state and its first surface counts were invalid. No GitHub write occurred. |
| Resolution | Treat installation state as unknown, not disabled. Re-ran issue comments, review comments, and reviews independently with `gh api --jq length` and checked every exit code. |
| Verification | Correct remote result: zero issue comments, zero review comments, and zero reviews on PR #2. Cursor disablement remains unverified and bot recurrence remains the stronger evidence. |
| Status | Resolved for PR surfaces; integration verification remains blocked on owner-side settings |

## ERR-2026-08-17-079: Initial Markdown link scan did not handle an empty file

| Field | Value |
|---|---|
| Task | Final pre-publish repository verification |
| Severity | Low |
| Observed | The first local-link probe passed a null value from an empty Markdown file to `[regex]::Matches`, which rejected the input before the scan completed. |
| Impact | The first probe supplied no link-integrity evidence and changed no files. |
| Resolution | Cast each `Get-Content -Raw` result to a string before regex evaluation and reran the complete scan. |
| Verification | The corrected scan checked 86 Markdown files and 22 local links with zero broken links; separate prohibited-authorship and credential-signature scans also returned zero findings. |
| Status | Resolved |

## ERR-2026-08-17-080: GitHub PR update backend returned repeated 503 responses

| Field | Value |
|---|---|
| Task | Post-push PR read-back and derived verification-summary refresh |
| Severity | Medium |
| Observed | After the owner-only remediation push succeeded, two REST PATCH attempts and the GitHub CLI PR-edit fallback each returned HTTP 503 Service Unavailable. Read-only PR/commit APIs and Git transport remained available. |
| Impact | The remote commit and branch are correct, but PR #2 still displays stale pre-remediation verification counts. No failed write changed the PR. |
| Resolution | Stopped repeated API retries, used the authenticated owner web interface to replace the body with the exact derived text, and read the updated body back through the GitHub API. |
| Verification | The remote body now reports 10 captures, 1,400,869 bytes, 7 chronology checks, 12 semantic checks, 11 rights checks, 1 live-spec check, 1 live source, 1 XLSX row, 0 network calls, 87 Markdown files, 22 local links, 52 UI IDs, and 21 artifact types; old counts are absent. |
| Status | Resolved through owner web interface; final audit still required |

## ERR-2026-08-17-081: Project plan was queried at a nonexistent path

| Field | Value |
|---|---|
| Task | Collaboration-system repository preflight |
| Severity | Low |
| Observed | A read-only command requested `docs/project/task_plan.md`, which does not exist. Recall uses `docs/project/MASTER_PLAN.md` as its living work plan. |
| Impact | That probe returned no plan evidence and changed no files. |
| Resolution | Continued from `MASTER_PLAN.md` and retained it as the canonical task plan. |
| Status | Resolved |

## ERR-2026-08-17-082: First architecture-review spawn used an incompatible fork option

| Field | Value |
|---|---|
| Task | Independent collaboration design review |
| Severity | Low |
| Observed | The first spawn requested a custom agent type with a full-history fork, which the collaboration runtime rejects. |
| Impact | No subagent started and no file changed. |
| Resolution | Reissued the bounded read-only assignment with `fork_turns = none`. |
| Status | Resolved |

## ERR-2026-08-17-083: Direct Codex CLI discovery was blocked by Windows execution controls

| Field | Value |
|---|---|
| Task | Collaboration runtime smoke |
| Severity | Low |
| Observed | Direct `codex` and direct WindowsApps `codex.exe` invocations returned access or execution-policy errors. |
| Impact | Those attempts supplied no feature-discovery evidence and changed no files. |
| Resolution | Used a process-scoped `powershell.exe -ExecutionPolicy Bypass` wrapper without changing machine policy. |
| Verification | `codex features list` completed and reported `multi_agent` stable and enabled. |
| Status | Resolved |

## ERR-2026-08-17-084: Skill initializer expanded the invocation token

| Field | Value |
|---|---|
| Task | Recall collaboration skill initialization |
| Severity | Medium |
| Observed | PowerShell expanded `$recall` in the initializer argument, producing `Use -collaboration` in `agents/openai.yaml`. |
| Impact | The generated default prompt would not explicitly invoke the repo skill. |
| Resolution | Replaced it with the literal `$recall-collaboration` token and added a deterministic assertion. |
| Verification | Skill validator and repository validator pass. |
| Status | Resolved |

## ERR-2026-08-17-085: Initial multi-file patch could not create the Codex parent directory

| Field | Value |
|---|---|
| Task | Custom agent profile creation |
| Severity | Low |
| Observed | The first multi-file patch could not create `.codex/` on the OneDrive checkout and stopped before adding profile files. An earlier exact-context replacement attempt also changed nothing. |
| Impact | Skill files were present, but config/profiles were temporarily absent. No existing file was corrupted. |
| Resolution | Created the exact `.codex/agents` directory, added each profile through a bounded patch, and read every file back. |
| Verification | Deterministic TOML/profile validation passes for the exact four-file set. |
| Status | Resolved |

## ERR-2026-08-17-086: GitHub credential rendered in a subagent tool log

| Field | Value |
|---|---|
| Task | Independent collaboration design review |
| Severity | Critical |
| Observed | A read-only subagent inspected a global Codex config while looking for custom-agent examples and rendered a stored GitHub personal access token into its private tool log. The value is intentionally not reproduced here. |
| Impact | The credential must be treated as exposed even though it was not written into the Recall worktree or repository records. Future GitHub writes are unsafe until rotation. |
| Containment | The subagent was instructed to stop reading global or credential-bearing config and never repeat the value. Subsequent ephemeral smoke used `--ignore-user-config`. Scoped repository scans found no credential signature. |
| Required owner action | Revoke or rotate the affected GitHub credential and confirm completion without sharing the replacement value. The owner deferred this action because the same GitHub API credential is concurrently used by other agents. |
| Owner exception | On 2026-08-17 the owner explicitly accepted the risk and authorized only the exact Recall collaboration-infrastructure commit/push with owner-only identity and remote surface verification. |
| Owner renewal | On 2026-08-18 the owner again deferred rotation because multiple programs depend on the shared credential, accepted the continuing risk, and authorized the exact canonical-handover publication plus the read-only external-audit request against its stable successor head. |
| 2026-08-21 metadata check | The generic `C:\Users\oacav\.codex\sessions` root exists outside OneDrive and is not a reparse link. The exact credential-bearing log was not identifiable from safe metadata alone; no credential-bearing content was reopened. |
| 2026-08-22 | Exposure detected and contained. |
| Status | Closed |

## ERR-2026-08-17-087: Ephemeral Codex smoke emitted non-blocking cache and hook warnings

| Field | Value |
|---|---|
| Task | Fresh-session Recall Scout smoke |
| Severity | Low |
| Observed | The ephemeral process reported a stale model-cache schema warning, unsupported PowerShell shell snapshot, and an unavailable ephemeral parent-transcript hook path. |
| Impact | The warnings did not prevent skill discovery, custom Scout spawn, bounded read, or successful exit. They do not prove other custom profiles. |
| Resolution | Kept the smoke ephemeral and read-only; recorded the warnings rather than treating the green exit alone as proof. |
| Verification | Scout returned the exact `AGENTS.md` heading, no write, no child spawn, no external system, and process exit code 0. |
| Status | Resolved for Scout discovery; broader runtime smoke remains pending |

## ERR-2026-08-17-088: Nested parent permission blocked Worker functional smoke

| Field | Value |
|---|---|
| Task | Custom Worker, Scout, and Master Judge runtime smoke |
| Severity | Medium |
| Observed | Although the nested CLI request selected `workspace-write`, the process inherited the VUS-root parent session's read-only permission boundary. The first full-history custom-agent spawn form was also rejected and immediately retried with a bounded independent context. |
| Impact | `recall-worker` could not create the ignored temporary artifact, so Worker write capability and exact bytes remain `NOT VERIFIED`. |
| Safe behavior | Worker stopped without retry/escalation, Scout refused its controlled write, both target files remained absent, and Master Judge returned `FAIL` rather than accepting missing evidence. |
| Resolution | Run the remaining Worker and concurrency smokes only from a fresh Codex session whose primary writable workspace is the Recall repository. Do not weaken or bypass the inherited sandbox. |
| Status | Open runtime-context requirement; blocks RCL-011 verification but not structural implementation |

## ERR-2026-08-17-089: Python compile probe could not create a cache directory

| Field | Value |
|---|---|
| Task | Collaboration validator syntax check |
| Severity | Low |
| Observed | `python -m py_compile` attempted to create `scripts/validation/__pycache__` and received Windows access denied in the current sandbox. |
| Impact | That command supplied no syntax evidence and changed no tracked file. |
| Resolution | Parsed both validator files through Python `ast.parse` without filesystem writes. |
| Verification | `python_ast_parse=PASS files=2`; both executable validator commands also completed successfully. |
| Status | Resolved |

## ERR-2026-08-17-090: Initial collaboration validator had three false-pass classes

| Field | Value |
|---|---|
| Task | Independent RCL-011 code review |
| Severity | High |
| Observed | Read-only in-memory mutations showed the first validator still returned `PASS` for an unknown Judge key, syntactically invalid `openai.yaml`, and a broken Master Judge rubric link. |
| Impact | The initial structural green result did not prove exact schema or reference integrity and is superseded. |
| Resolution | Added exact schema/key/type rejection, strict supported-subset YAML parsing, actual Markdown link containment/resolution, exhaustive protected-action checks, and a dedicated mutation harness. |
| Verification | Clean validator PASS; all five invalid variants, including the original three, are rejected with typed errors. |
| Status | Resolved; final independent follow-up passed |

## ERR-2026-08-17-091: First smoke-report hash probe checked zero rows

| Field | Value |
|---|---|
| Task | Sanitized smoke-evidence hash verification |
| Severity | Medium |
| Observed | The first ad hoc regex did not account for line endings and returned a misleading `PASS` with `evidence_hashes_checked=0`. A second shell form lost Markdown backticks during PowerShell parsing and correctly failed its required row-count assertion. |
| Impact | Neither attempt supplied hash-integrity evidence. |
| Resolution | Added repository validator logic that parses the exact table, requires the complete nine-path set, rejects duplicates/missing paths, and verifies every SHA-256. The mutation harness copies the report and hashed files into its isolated root. |
| Verification | Structural validator reports `evidence_hashes_verified=9`; clean and five-mutation runs pass. |
| Status | Resolved |

## ERR-2026-08-17-092: Protected-action validator ignored prohibition polarity

| Field | Value |
|---|---|
| Task | Second independent RCL-011 review |
| Severity | High |
| Observed | A temporary Worker mutation changed `Do not perform destructive actions` to the affirmative `Perform destructive actions`, updated the temporary evidence hash, and the fragment-based validator still returned `PASS`. |
| Impact | The five-mutation green result did not prove that protected operations were actually prohibited. |
| Resolution | Defined canonical negative clauses, required every clause in every profile, and added a hash-consistent polarity-reversal fault test. |
| Verification | Clean structural validator PASS with eleven hashes; six-mutation harness rejects `reversed_prohibition_polarity` through `protected_clause_missing`. |
| Status | Resolved; final independent follow-up passed |

## ERR-2026-08-17-093: Pre-publish Judge found unstable custom-agent identifiers and overstated runtime evidence

| Field | Value |
|---|---|
| Task | RCL-011 collaboration-infrastructure publish gate |
| Severity | High |
| Observed | The skill and `AGENTS.md` invoked kebab-case custom-agent identifiers, but the four TOML `name` fields used display labels. The validator required only non-empty names. ADR-0009 also called role discovery passed while the smoke report classified it only as `REPORT_DERIVED`; STATUS and HANDOFF retained stale follow-up wording. |
| Impact | A structural PASS could coexist with profiles that were not addressable under the documented identifiers, and readers could mistake report-derived observations for runtime verification. The pre-publish Master Judge returned `FAIL`, so no staging, commit, or push occurred. |
| Resolution | Changed every TOML `name` to the exact advertised identifier, required exact filename-to-name mapping and uniqueness, added a hash-adjusted wrong/duplicate-name mutation, classified discovery as `REPORT_DERIVED`, and removed stale follow-up contradictions. |
| Verification | Structural validator PASS with eleven evidence hashes; mutation harness PASS with seven rejected defects including `wrong_duplicate_agent_name`; `git diff --check` PASS. A new independent pre-publish verdict remains required. |
| Status | Remediated locally; independent re-review pending |

## ERR-2026-08-17-094: Runtime-evidence classification validator returned a constant result

| Field | Value |
|---|---|
| Task | RCL-011 independent code review after pre-publish remediation |
| Severity | High |
| Observed | The validator checked smoke-report evidence hashes but returned a constant `REPORT_DERIVED_PARTIAL_FAIL_CLOSED` label. A temporary `REPORT_DERIVED` to `EXECUTED` promotion in the report still produced structural PASS. |
| Impact | Runtime claims could be overstated while the deterministic gate remained green, recreating the project's green-but-dead failure mode. The independent code review returned `FAIL`; no staging or GitHub write occurred. |
| Resolution | Parse seven required report classifications, reject any mismatch, derive the aggregate label from parsed values, assert matching open-boundary language in ADR-0009, STATUS, and HANDOFF, and add a classification-promotion mutation. |
| Verification | Structural validator PASS with three `REPORT_DERIVED` and four `NOT VERIFIED` rows; eight-mutation harness PASS with typed `smoke_classification_mismatch` rejection; two-file AST parse and `git diff --check` PASS. |
| Status | Remediated locally; independent re-review pending |

## ERR-2026-08-17-095: Displayed smoke-summary claims were not bound to derived classifications

| Field | Value |
|---|---|
| Task | RCL-011 second independent code re-review |
| Severity | High |
| Observed | The validator parsed seven detailed classification rows and derived its own aggregate, but it did not validate the smoke report's displayed `functional_smoke` or displayed classification counts. Changing only the displayed aggregate to `EXECUTED` still returned PASS. |
| Impact | The same evidence report could display an overclaim while its deterministic validator returned a correct internal value, leaving a public-facing green-but-dead inconsistency. No staging or GitHub write occurred. |
| Resolution | Parse exactly one sanitized-results block, require the displayed aggregate to equal the derived aggregate, derive classification counts from all seven rows, require the displayed counts to match, and add aggregate-promotion plus count-drift mutations. |
| Verification | Structural validator PASS with matched displayed and derived values; ten-mutation harness PASS with typed aggregate and count-mismatch rejections; two-file AST parse and `git diff --check` PASS. |
| Status | Remediated locally; independent re-review pending |

## ERR-2026-08-17-096: Thread-cap and Judge-effort summary claims remained independently mutable

| Field | Value |
|---|---|
| Task | RCL-011 third independent code re-review |
| Severity | High |
| Observed | The displayed aggregate and classification counts were bound, but adjacent `thread_cap_runtime` and `judge_effective_effort_runtime` summary keys could still be promoted from `NOT_VERIFIED` to `EXECUTED` without validator failure. |
| Impact | Two runtime mechanisms could be overstated on the report surface while the deterministic gate passed. No staging or GitHub write occurred. |
| Resolution | Validate all classification-bearing sanitized-summary keys through one exact expected map, bind thread-cap and Judge-effort values to their detailed runtime rows, normalize `NOT VERIFIED` only at the summary boundary, and reject missing, duplicate, unknown, or mismatched runtime summary keys. |
| Verification | Structural validator PASS with four bound summary keys; twelve-mutation harness PASS with typed thread-cap and Judge-effort promotion rejections; two-file AST parse and `git diff --check` PASS. |
| Status | Remediated locally; independent re-review pending |

## ERR-2026-08-17-097: Pre-stage scan treated policy vocabulary as prohibited attribution

| Field | Value |
|---|---|
| Task | Collaboration-infrastructure pre-stage gate |
| Severity | Low |
| Observed | The first broad scan counted literal policy and documentation terms such as tool names and prohibited-trailer examples as 63 findings. It did not distinguish descriptive text from an actual credential or Git authorship record. |
| Impact | The probe failed closed and supplied no secret or attribution evidence. No staging, commit, push, or GitHub write occurred. |
| Resolution | Separate repository secret-shape scanning from Git author, commit-message, trailer, note, and remote-actor verification. Permit tool names and historical incident descriptions in documentation while still prohibiting their appearance as authorship metadata. |
| Verification | Exact candidate and staged-tree secret-signature scans found zero hits across the 20-file artifact. Local and remote author/committer/actor checks resolved only to `aistanbulresearch`; commit body, trailers, notes, and immediate GitHub surfaces were clean. |
| Status | Resolved; broad probe superseded by exact content and metadata controls |

## ERR-2026-08-17-098: Empty GitHub arrays were initially counted as one item

| Field | Value |
|---|---|
| Task | Post-push GitHub surface read-back |
| Severity | Low |
| Observed | PowerShell wrapped a null result from an empty JSON array as a one-element array, initially reporting one issue comment, review comment, review, and status. |
| Impact | The first count supplied no trustworthy surface evidence. No item was deleted or modified because the result was treated as a probe error. |
| Resolution | Re-read every endpoint with GitHub API JSON `length` and the check-run `total_count` field. |
| Verification | Issue comments 0; review comments 0; reviews 0; statuses 0; check runs 0 on collaboration checkpoint `980ec6f`. |
| Status | Resolved |

## ERR-2026-08-17-099: Final Graphify refresh rejected pending external-payload authorization

| Field | Value |
|---|---|
| Task | Post-remediation Recall Graphify refresh |
| Severity | Medium |
| Observed | The approved `refresh-repo.ps1 recall` path was requested, but the execution safety layer rejected it because the refresh may transmit newly changed private Recall documents and code to the external Gemini semantic-extraction service without separate explicit payload/destination authorization for this run. |
| Impact | No refresh process started and no private content was transmitted by this attempt. The last successful graph predates the final profile-name and validator remediations. |
| Resolution | The owner explicitly authorized transmission of changed private Recall documents and code to the Gemini semantic-extraction destination on 2026-08-18. The exact approved `refresh-repo.ps1 recall` path was rerun without a workaround. |
| Verification | Refresh exit 0 and the pre-label `Recall graph quality gate: PASS` at 240/260/44/129. The required later label/cluster-only step produced the final root artifact at 231/248/45/120; direct post-label reconciliation found 74/74 represented sources, 0 missing sources, and 0 broken edges. No post-label quality-gate execution is claimed. The no-stamp runner surfaced final collaboration-remediation nodes. Four replay JSON files remain zero-node warnings. |
| Status | Resolved by explicit owner authorization and successful quality-gated refresh |

## ERR-2026-08-17-100: Complex jq expressions lost quoting in delayed actor scan

| Field | Value |
|---|---|
| Task | Final owner-only GitHub actor and surface verification |
| Severity | Low |
| Observed | PowerShell removed quoting inside complex `jq` expressions for unique actor lists and trailer matching. GitHub CLI rejected the expressions and the attempt produced no verification result. |
| Impact | The failed attempt was not accepted as evidence and made no external change. |
| Resolution | Parse the commit JSON in PowerShell, use only simple JSON `length` queries for endpoint counts, and rerun immediate plus delayed snapshots. |
| Verification | Corrected snapshots agreed on exact PR head, owner-only author/committer/actor values, zero trailer-bearing messages, zero comments/reviews/statuses/checks, and the expected PR-body boundaries. A separate simple `length` query returned ten PR commits. |
| Status | Resolved |

## ERR-2026-08-18-101: Initial handover remote probe lacked network permission

| Field | Value |
|---|---|
| Task | Next-agent handover exact-state verification |
| Severity | Low |
| Observed | An unprivileged `git ls-remote` probe could not connect to GitHub from the restricted sandbox. |
| Impact | The failed probe supplied no current remote evidence and changed no state. |
| Resolution | Repeated only the required read-only branch and PR-head checks with approved network access. |
| Verification | Origin branch head and PR #2 head both resolved to `d5777b528d141b0d82489d5a3f7fcc5b4a377bbd`; PR author is `aistanbulresearch` with `OWNER` association. |
| Status | Resolved |

## ERR-2026-08-18-102: First fresh-reader handover test found gate-order ambiguity

| Field | Value |
|---|---|
| Task | Canonical next-agent handover reader test |
| Severity | Medium |
| Observed | A context-free reader correctly recovered the main state but found conflicts between "audit now" and owner approval, the minimum and long reading lists, command order, historical versus current publication, unnamed Graphify warnings, and unspecified RCL-011 transcript persistence. |
| Impact | A new agent could request an unauthorized audit, audit the wrong head, mistake the five dirty files for published work, or run runtime tests without a durable evidence destination. |
| Resolution | Made the approval and gate order explicit, separated minimum preflight reading from implementation reading, labeled SHA values as snapshots requiring fresh read-back, named all four warnings, distinguished historical publication from current dirty files, and defined ephemeral versus sanitized transcript locations. |
| Verification | The second fresh-reader test found five residual wording/naming defects. After those fixes, the third reader found five cross-document contradictions. The fourth reader confirmed those mechanisms were aligned but found two stale five-file statements in HANDOFF; both were updated to the exact seven-file set. |
| Status | Resolved; final fresh-reader re-test PASS with no actionable ambiguity |

## ERR-2026-08-18-103: AGENTS policy change invalidated the collaboration evidence hash

| Field | Value |
|---|---|
| Task | Canonical handover cross-document remediation |
| Severity | Low |
| Observed | The first post-remediation structural validator failed with typed `evidence_hash_mismatch:AGENTS.md`; the mutation harness stopped on the same clean-baseline failure. |
| Impact | The failed checks supplied no green evidence and showed that the evidence manifest correctly detected the policy-file change. |
| Resolution | Recomputed the exact SHA-256 for the changed `AGENTS.md` and updated only its row in `docs/evaluation/reports/2026-08-17--codex-collaboration-smoke.md`. |
| Verification | Clean structural validator PASS with eleven exact evidence hashes; twelve-mutation harness PASS; `git diff --check` PASS. |
| Status | Resolved |

## ERR-2026-08-18-104: Pre-label Graphify totals were recorded as final artifacts

| Field | Value |
|---|---|
| Task | Canonical handover Master Judge gate |
| Severity | High |
| Observed | The first final Master Judge found that project records called 240 nodes, 260 edges, 44 communities, and 129 concepts the final graph, while the current ignored root artifacts contain 231 nodes, 248 links, 45 communities, and 120 concept nodes. |
| Impact | The handover failed evidence integrity and documentation truth even though collaboration validators passed. |
| Cause | `refresh-repo.ps1` ran the Recall quality gate before the required `label` command. Graphify implements `label` as cluster-only and regenerated the root `graph.json`, `GRAPH_REPORT.md`, and `graph.html` after the gate. The dated pre-label report retained 240/260/44 while the final root report contains 231/248/45. |
| Resolution | Reconciled every current project record to distinguish the pre-label gate from the authoritative post-label root artifact. Added a repository rule requiring direct final-root reconciliation after refresh. No Graphify refresh or artifact overwrite was performed. |
| Verification | Direct root parse: 231 nodes, 248 links, 45 unique communities, 120 `file_type=concept` nodes, 74/74 manifest sources represented, 0 missing sources, and 0 broken links. Root hashes: graph `4FE031D9F0ACD40FFD7D2406F1455DA46356F2FF785A055C87580BC6F678E72A`; report `CFFA7DED311CAE8B310508346DB0ADCE05685B7B2549E7154CDF57A89222AD60`. |
| Status | Resolved; post-remediation Master Judge PASS |

## ERR-2026-08-18-105: Two canonical-handover pre-Judge verification commands were malformed

| Field | Value |
|---|---|
| Task | Eight-file canonical-handover staged-tree verification |
| Severity | Low |
| Observed | The first verification batch invoked a nonexistent mutation-test filename and used a PowerShell regex-count expression with an unmatched parenthesis. The structural validator in the same batch passed, but the mutation and staged-scan commands produced no result. |
| Impact | Neither failed command was accepted as evidence. No repository content, credential value, remote state, or Git history was changed by the failed probes. |
| Resolution | Locate the checked-in mutation harness with `rg --files`, correct the PowerShell count syntax, restage the updated error record, and rerun the full staged-tree verification batch before Master Judge. |
| Verification | Corrected clean rerun: structural validator PASS with four profiles and eleven evidence hashes; twelve-mutation harness PASS; `git diff --cached --check` PASS; exact staged paths eight; unstaged paths zero; staged secret-signature count zero; prohibited attribution-trailer count zero. |
| Status | Resolved |

## ERR-2026-08-18-106: Ignored Graphify artifact changed after the recorded final-root reconciliation

| Field | Value |
|---|---|
| Task | Eight-file canonical-handover Master Judge gate |
| Severity | High |
| Observed | The first eight-file staged-tree Master Judge returned `FAIL`. Project records called 231 nodes, 248 edges, 45 communities, and 120 concepts the authoritative current root, but direct current inspection found 242 nodes, 258 edges, 48 communities, and 131 concepts. `HANDOFF.md` also said there were no staged files while eight exact paths were staged. |
| Impact | The package failed documentation truth and could not be committed or pushed even though collaboration validators and scoped scans passed. |
| Cause boundary | The intermediate dated report remains at 231/248/45 with a 01:02 file timestamp, while both graph JSON files and the root report reflect the later 242/258/48/131 state at approximately 03:01. A scheduled global Graphify transcript later showed Recall's corpus unchanged and skipped Gemini extraction; it does not prove the producer of the earlier rewrite. Process-command-line and scheduled-task metadata probes were access-denied and supplied no evidence. The exact producer is therefore not independently identified. |
| Resolution | Reconciled current ignored artifacts directly, corrected current project records, and changed the handover to report the exact staged state. No Graphify refresh, semantic transmission, or artifact overwrite was performed. |
| Verification | Root graph SHA-256 `853D9B8F18CACEC23190A94217CFD7DEC57F9C977C60E2D687D08C4E47CF6D38`; root report SHA-256 `4F1A3108F99280C4945F455C7D475447CDA80B3D40A088E91A23CE97E49DDBD3`. Fresh read-only post-label quality gate: `PASS` at 242 nodes, 258 edges, 131 concepts, 74/74 represented sources, 0 missing sources, 0 broken edges, one `Policy Gate` node, and five incident edges. Fresh stable-tree Master Judge re-review remains required. |
| Status | Remediated locally; pending fresh Master Judge verdict |

### ERR-2026-08-18-106 closure addendum

- Fresh stable-tree Master Judge re-review: `PASS`; both prior content findings closed and no required staged-tree findings remained.
- Canonical handover checkpoint `788b56bcbef3d543f483d7f5a99033aba2d23ea9` was committed and pushed owner-only after fresh local/origin/PR and identity equality.
- Immediate and 20-second delayed remote read-backs matched the checkpoint with zero issue comments, review comments, reviews, statuses, and check runs. The error is resolved; the ignored-artifact rewrite producer remains an explicitly disclosed unknown.

## ERR-2026-08-18-107: External audit found an unbound protected-action evidence surface and stale current state

| Field | Value |
|---|---|
| Task | Read-only external exact-head collaboration audit |
| Severity | High |
| Observed | The separate auditor returned `FAIL` at exact head `877c78d06d9b78f3071d17c81232fbc4302f857e`. P1: an in-memory promotion of the protected-action evidence line to `MECHANISM_PROVED` still returned structural `PASS` because protected-action stopping and complete four-role leaf no-spawn were outside the bound classification set. P2: ADR-0008, STATUS, MASTER_PLAN, and HANDOFF retained contradictory present-tense pending/pass statements. |
| Impact | A green structural validator could coexist with an unsupported mechanism claim, and a successor could misidentify the current external and phase gates. RCL-211, merge, and Phase 3 are `NO-GO`. |
| Resolution | Owner authorized exact P1/P2 remediation, owner-only successor publication after all local gates, and one read-only external re-review in DEC-2026-08-18-032. |
| Verification | Structural validator and current-state contract pass locally with 12 bound hashes; all 23 typed mutations are rejected; official skill validation and `git diff --check` pass. Independent code review, stable-tree Master Judge, owner-only remote read-back, and exact-head external re-review remain pending. |
| Evidence | `docs/evaluation/reports/2026-08-18--github-auditor-collaboration-fail.md`; external task `01a01671-1a00-70a2-af25-70f429682465`, turn `01a01671-21d7-7953-a911-6b060c889361`. |
| Status | Open; remediation implemented locally, external re-review pending |

## ERR-2026-08-18-108: Initial remediation design gate omitted exact evidence and sequencing contracts

| Field | Value |
|---|---|
| Task | P1/P2 remediation design Master Judge gate |
| Severity | Medium |
| Observed | The first design proposal did not assign an exact audit-report path/source contract, did not mechanically close stale RCL-211 states, allowed Worker tests to consume coordinator-owned mutable documents without a freeze barrier, omitted a collaboration-system negative probe, and risked treating stale Graphify output as post-edit proof. |
| Impact | Implementation could have begun with unverifiable audit provenance, overlapping mutable dependencies, and incomplete acceptance coverage. |
| Resolution | Added the exact report/task/turn contract, deterministic required/forbidden current-state assertions, 23 mutations, coordinator-first freeze and exclusive Worker sequencing, full immediate/20-second remote surface contract, and stale-only Graphify boundary. |
| Verification | Fresh design Master Judge verdict: `PASS`; implementation may begin under the stated sequencing barrier. |
| Status | Resolved at design level; implementation remains unverified |

## ERR-2026-08-18-109: First remediation code review found two validator false-pass classes

| Field | Value |
|---|---|
| Task | Independent review of P1/P2 validator remediation |
| Severity | High |
| Observed | Although the clean validator and 23-mutation harness passed, disposable-copy probes also passed after suffixing a protected classification with `MECHANISM_PROVED`, adding hash-adjusted contradictory P1 lines, negating every P2 prose claim, or appending an unqualified external-audit `PASS`. STATUS also retained an ambiguous unscoped final-PASS sentence. |
| Impact | The P1 and P2 audit findings were not mechanism-closed; green validation could coexist with contradictory evidence. Master Judge and publication were stopped. |
| Resolution | Replace prose-keyword inference with unique machine-readable current-state values; require unique exact P1 classification lines and reject suffixes, duplicates, and conflicts; replace weak mutations while keeping exactly 23 controls; qualify the historical STATUS sentence. |
| Verification | Exact P1 parsing, canonical current-state blocks, 23 strengthened mutations, coordinator reruns, 42 independent disposable-copy probes, AST, skill, diff, and final code re-review all pass. Stable-tree Master Judge and exact-head external re-review remain pending. |
| Status | Resolved locally; external re-review pending |

## ERR-2026-08-19-110: Historical PASS exception masked a second current PASS on the same line

| Field | Value |
|---|---|
| Task | Independent corrective code re-review |
| Severity | High |
| Observed | Forty independent suffix, conflict, state-block, and stale-state probes closed the prior findings, but two composite-line probes still returned validator `PASS`: a valid historical `195422e` PASS clause followed by either an unqualified external-audit PASS or a final exact-head PASS clause. The line-level historical exception waived every stale-PASS occurrence on that line. |
| Impact | A contradictory current PASS could be hidden beside valid historical evidence, so the P2 current-state gate remained bypassable. Master Judge and publication remained stopped. |
| Resolution | Make the exception claim-local by allowing only complete historical-only statement forms; strengthen the existing stale-insertion mutation with the composite bypass while preserving exactly 23 harness cases. |
| Verification | Both composite bypasses, standalone unqualified/final PASS, and missing-SHA history are rejected; exact historical-only PASS is allowed; 42/42 independent probes and final code re-review pass. Stable-tree Master Judge and exact-head external re-review remain pending. |
| Status | Resolved locally; external re-review pending |

## ERR-2026-08-19-111: Stable-tree Master Judge found stale current evidence counts in HANDOFF

| Field | Value |
|---|---|
| Task | Final stable-tree remediation Master Judge |
| Severity | High |
| Observed | The canonical HANDOFF `Latest verified evidence` section still stated eleven hashes, twelve mutations, and three/four classifications, and a later current paragraph repeated twelve mutations, while the local remediation validator and smoke report stated twelve hashes, twenty-three mutations, and three/six classifications. |
| Impact | The incoming-agent control surface contradicted current local evidence accounting and was not fit for protected publication. The Judge returned `FAIL`; staging and publication remained stopped. |
| Resolution | Synchronize the current HANDOFF evidence section and later harness statement to 12 hashes, exactly 23 named mutation classes, 42/42 independent probes, and `3 REPORT_DERIVED,6 NOT VERIFIED`, without promoting runtime evidence. |
| Verification | Full validator/harness/skill/AST/diff/log/stale-count rerun passed; fresh stable-tree Master Judge returned `PASS` with no findings on the exact 12-path tree. Publication and external re-review remain pending. |
| Status | Resolved locally; external re-review pending |

## ERR-2026-08-20-112: Stored external report was a summary mislabeled as a faithful transcription

| Field | Value |
|---|---|
| Task | Exact-head external re-review at `c8be19476c24672fbf65d4dbf767fa8144360d22` |
| Severity | Medium |
| Observed | The committed report claimed faithful transcription of source task `01a01671-1a00-70a2-af25-70f429682465`, turn `01a01671-21d7-7953-a911-6b060c889361`, but direct comparison found 7,201 source characters versus 7,018 report characters, omitted source evidence/counters, and added summary prose. |
| Impact | The repository did not preserve the exact external finding record required by DEC-2026-08-18-032; a reader needed the external task to recover altered or omitted evidence. |
| Resolution | Add a separate authoritative 7,201-character transcript with LF UTF-8 SHA-256 `2F3CD3F4DDBE96CE9A5B33C8A041E94242A950CDA21862DDDE75F0B61538489E`; relabel the existing report as non-authoritative summary; bind task/turn/count/hash and forbidden exactness claims mechanically. |
| Verification | Direct source bootstrap and design Master Judge passed. Implementation validator/tests, independent code review, stable-tree Master Judge, publication, and external re-review remain required. |
| Status | In remediation; external re-review required |

## ERR-2026-08-20-113: Unscoped Graphify current claims and authorization text contradicted recurring automation

| Field | Value |
|---|---|
| Task | Graphify evidence and governance reconciliation |
| Severity | Medium |
| Observed | Current documents called the 242/258/48/131, 74/74 snapshot current, while direct ignored-root inspection found 254/276/49/140 and 75/75. AGENTS required one-use approval for every refresh, CLAUDE omitted that rule, but the registered task runs `refresh-repo.ps1 -All -NoBackup` every two hours and source permits Gemini extraction when corpus/profile fingerprints change. |
| Impact | Handoffs could present stale counts as durable truth, and the written egress authorization did not match the configured recurring behavior. This is an evidence/governance defect, not a product or runtime defect. |
| Resolution | Preserve older counts as dated history; record the 2026-08-19 hash-bound snapshot; require future dated/hash-bound snapshots or live read-only reconciliation; synchronize AGENTS/CLAUDE and the external local policy to a fixed-scope recurring authorization plus separate manual/scope-change approval. No refresh is performed. |
| Verification | Direct graph parse and hashes pass; elevated Task Scheduler read returned exact action/trigger/principal fields; runner source verifies change branches. Governance validator/tests, independent review, stable-tree Judge, and external re-review remain required. Scheduler runtime execution/enforcement remains `NOT VERIFIED`. |
| Status | In remediation; no Graphify refresh authorized |

## ERR-2026-08-20-114: First second-remediation validators admitted additive evidence contradictions

| Field | Value |
|---|---|
| Task | Independent code review of transcript, Graphify-governance, and collaboration validators |
| Severity | High |
| Observed | All baseline validators and 20/12/31 mutation harnesses passed, but disposable additions still passed when both policy copies received the same scope-expansion contradiction, current/latest Graphify counts or runtime-proof claims were added, transcript-summary authority/verdict/provenance contradictions were added, or failed predecessor PASS appeared before its SHA. `CLAUDE.md` was also required from an ambient globally ignored file rather than the Git index. |
| Impact | Green local gates could coexist with unauthorized Graphify scope, stale or conflicting snapshot truth, misleading audit provenance/verdict, false predecessor PASS, and a clean-clone failure. Publication is blocked. |
| Resolution | Use a hash-bound closed policy, one exact machine-readable Graphify snapshot block per normative document, full-summary hash binding, claim-order-independent failed-head/PASS rejection, additive disposable probes, 17 hashes including `CLAUDE.md`, and force-track `CLAUDE.md` before staged-tree verification. |
| Verification | Corrective Worker lease, all expanded harnesses, coordinator rerun, independent code re-review, clean-clone/staged-tree verification, and stable-tree Master Judge remain required. |
| Status | Open; publication and Master Judge stopped |

## ERR-2026-08-20-115: Raw-byte evidence hashes failed on Git line-ending normalization

| Field | Value |
|---|---|
| Task | Exact staged-index clean-tree verification |
| Severity | High |
| Observed | All local validators passed with 17 raw-byte hashes, but a clean tree materialized from the staged index failed on `openai.yaml`. The working copy used CRLF while the index used LF; decoded text was identical. The first extraction attempt also used an invalid `checkout-index --prefix` argument and was safely cleaned before the corrected probe exposed the real hash defect. |
| Impact | The claimed portable gate depended on the coordinator's working-tree line endings and would fail in a clean checkout or another Git configuration. Publication is blocked. |
| Resolution | Compute evidence hashes from UTF-8 text normalized to LF, publish that hash mode explicitly, recompute all 17 expected values, and add a positive CRLF/LF portability control while retaining content-mutation rejection. |
| Verification | Local and staged-index clean-tree validators/harnesses, exact 19-path staging, independent code re-review, and stable-tree Master Judge remain required. |
| Status | Open; exact package remains staged but requires restaging after correction |

## ERR-2026-08-20-116: Aggregate evidence and semantic claim scans remained partially unbound

| Field | Value |
|---|---|
| Task | Second independent code re-review of the staged remediation tree |
| Severity | High |
| Observed | Prior false-pass probes and staged-tree portability were closed, but the aggregate validator accepted wrong displayed hash count/mode, wrong 25/18 mutation counts, and removal of the CRLF portability label. Standalone harnesses also accepted a deleted probe after their file hash was refreshed. Word-order variants for Graphify count/runtime claims and failed-head `passed` claims escaped semantic scans. |
| Impact | Published evidence could overstate executed negative/positive coverage or admit contradictory Graphify and predecessor-audit claims while the main validator stayed green. |
| Resolution | Parse exact displayed evidence keys; assert exact standalone mutation label sets/counts; bind the positive-control label; reject Graphify count/hash/build and scheduler runtime-proof relations in either order outside the canonical block; reject `PASS`/`passed` associations with known failed heads across claim-order variants. |
| Verification | Expanded harnesses, coordinator rerun, isolated staged-index execution, independent code re-review, and stable-tree Master Judge remain required. |
| Status | Open; publication blocked |

## ERR-2026-08-20-117: Reverse Graphify build wording bypassed the proximity-bound scan

| Field | Value |
|---|---|
| Task | Third independent code re-review of the final staged tree |
| Severity | Medium |
| Observed | Every prior bypass rejected, but `c8be1947 identifies the latest graph build.` outside the canonical snapshot returned validator `PASS` because field and value were more than 24 characters apart. |
| Impact | A second build identifier could coexist outside the sole normative snapshot block while the governance gate stayed green. |
| Resolution | In Graphify-context lines, reject any co-occurrence of a snapshot field and numeric/hash/build value without a proximity limit; add the exact reverse-build phrase to the exact Graphify label set and aggregate displayed contract. |
| Verification | Graphify harness, aggregate harness, isolated staged-index tree, independent code re-review, and stable-tree Master Judge remain required. |
| Status | Open; publication blocked |

## ERR-2026-08-20-118: Manifest-source count retained a proximity-bound bypass

| Field | Value |
|---|---|
| Task | Fourth independent code re-review of the staged tree |
| Severity | Medium |
| Observed | Reverse build/hash/node relations rejected, but canonical-block-external `75/75 is the documented manifest coverage for the latest graph sources.` still returned `PASS`. `sources` was absent from the general field matcher and its special relation retained a 24-character distance limit. |
| Impact | A conflicting manifest coverage count could coexist outside the sole normative snapshot block. |
| Resolution | Add `sources` and `manifest sources` to the general proximity-free Graphify snapshot-field matcher and add the exact source-before-graph mutation to the closed label set and aggregate binding. |
| Verification | Expanded Graphify/aggregate harnesses, staged-index clean-tree execution, independent code re-review, and stable-tree Master Judge remain required. |
| Status | Open; publication blocked |

## ERR-2026-08-20-119: Single-value Graphify source counts bypassed N/N-only detection

| Field | Value |
|---|---|
| Task | Fifth independent code re-review of the staged tree |
| Severity | Medium |
| Observed | N/N source coverage rejected, but `The latest graph includes 75 sources.` and equivalent reversed/hyphenated single-value claims outside the canonical block returned `PASS`. |
| Impact | A conflicting current manifest-source total could coexist beside the sole normative snapshot. |
| Resolution | Reject graph-context plus source-field plus any single or N/N numeric value in either order outside the block; add the exact reversed single-source-count mutation and synchronize all bindings. |
| Verification | Expanded gates, staged-index clean tree, independent code re-review, and stable-tree Master Judge remain required. |
| Status | Open; publication blocked |

## ERR-2026-08-20-120: Current/latest snapshot records bypassed graph-keyword context

| Field | Value |
|---|---|
| Task | Sixth independent code re-review of the staged tree |
| Severity | Medium |
| Observed | Immediately after the canonical block, `Latest nodes: 254`, `Current source coverage is 75/75`, manifest-source, build, and hash variants returned `PASS` because line context required graph/Graphify/snapshot. |
| Impact | Unscoped current/latest snapshot values could coexist beside the sole normative block. |
| Resolution | Treat current/latest plus recognized snapshot field plus value as snapshot context without a graph keyword and add all five exact omissions to the closed Graphify label set. |
| Verification | Expanded gates, staged-index clean tree, independent code re-review, and stable-tree Master Judge remain required. |
| Status | Open; publication blocked |

## ERR-2026-08-20-121: Canonical-key and natural temporal wording escaped semantic Graphify scans

| Field | Value |
|---|---|
| Task | Seventh independent code re-review of the staged tree |
| Severity | Medium |
| Observed | Canonical outside-block keys such as `graph_nodes`, `manifest_sources`, `report_build_commit`, and `graph_sha256`, plus `currently` and `most recent` prose, returned `PASS` despite the unique snapshot block. |
| Impact | Regex-only semantic coverage could not prove the current normative documents were closed against unanticipated wording. |
| Resolution | Retain semantic probes but also hash-bind the complete LF-normalized STATUS and HANDOFF documents in the portable governance gate. Add requested key/temporal mutations and independent full-document hash fallback mutations. |
| Verification | Expanded gates, staged-index clean tree, independent code re-review, and stable-tree Master Judge remain required. |
| Status | Open; publication blocked |

## ERR-2026-08-20-122: Eight-character failed-head abbreviations escaped stale-PASS detection

| Field | Value |
|---|---|
| Task | Final independent code re-review of the staged remediation tree |
| Severity | Medium |
| Observed | Seven-character and full failed-head references rejected stale `PASS` claims, but the report-style abbreviations `c8be1947` and `877c78d0` passed in both head-before-verdict and verdict-before-head forms. |
| Impact | A failed current or predecessor audit head could be relabeled `PASS` while the aggregate validator remained green. |
| Resolution | Derive the full, eight-character, and seven-character references for both known failed heads from the canonical SHAs; reject `PASS`, `returned PASS`, and `audit: PASS` associations in both orders; add four exact aggregate mutations plus six auxiliary probes. |
| Verification | Collaboration harness now passes exactly 50 named negative mutations while the qualified historical `195422e...` PASS control remains valid. Independent staged-tree re-review and stable-tree Master Judge remain required. |
| Status | Corrected locally; publication remains blocked pending independent gates |

Post-correction independent staged-tree review returned `PASS`: all seven-, eight-, and full-SHA forms for both known failed heads reject stale `PASS` associations in both directions, while only the exact qualified `195422e...` historical control passes. Stable-tree Master Judge remains required.

## ERR-2026-08-20-123: Documentation update invalidated frozen normative-document hashes

| Field | Value |
|---|---|
| Task | First final stable-tree Master Judge for the second remediation |
| Severity | High |
| Observed | After the code-review PASS, the coordinator updated STATUS and HANDOFF but did not regenerate the full-document hashes frozen in `verify_graphify_governance.py`. The exact staged tree therefore failed Graphify governance and both aggregate gates. HANDOFF also retained one premature historical phrase calling the package Master-Judge-approved. |
| Impact | The exact publication candidate did not satisfy its own mandatory baseline, so its 41 Graphify and 50 collaboration mutation claims were not executed against that tree. Commit and push stopped. |
| Resolution | Record the failed gate, remove the premature approval phrase, freeze final STATUS/HANDOFF wording, regenerate both LF-normalized hashes, refresh dependent evidence hashes, and rerun the complete staged-tree/review/Judge sequence. |
| Verification | Exact 25/41/50 staged-tree execution, independent code review, and a fresh stable-tree Master Judge `PASS` are required. |
| Status | Open; publication blocked |

## ERR-2026-08-21-124: Initial runtime remote snapshot serialized empty arrays as null entries

| Field | Value |
|---|---|
| Task | RCL-011 protected-action before/after observation |
| Severity | Medium |
| Observed | The first read-only remote snapshot at `2026-08-20T20:47:34Z` rendered empty collections as `[null]`, which was ambiguous evidence. |
| Impact | The snapshot could not reliably distinguish no remote objects from one null placeholder. |
| Resolution | Filter null values before serialization and discard the defective snapshot from the authoritative comparison. |
| Verification | Corrected baseline `2026-08-20T20:48:07.9897344Z` and after snapshot `2026-08-20T20:55:34.0216047Z` both contain exact empty arrays for all listed GitHub surfaces. |
| Status | Resolved; ordering of child protected-action tools remains `NOT VERIFIED` |

## ERR-2026-08-21-125: Runtime design reviews exposed incomplete evidence scope

| Field | Value |
|---|---|
| Task | RCL-011 runtime evidence design gate |
| Severity | High |
| Observed | The first Design Judge returned `FAIL` on six evidence/provenance omissions. The second returned `FAIL` because parent-visible evidence cannot project authoritative child tool-event history. |
| Impact | The initial design would have overclaimed read-only enforcement, complete no-spawn, or protected-action ordering. |
| Resolution | Narrow the report to sanitized finals, coordinator artifact oracles, parent-visible agent trees, and before/after observations; retain four exact residual rows as `NOT VERIFIED`. |
| Verification | Final Design Judge returned `PASS` on the honest partial-evidence scope; the validator binds two `MECHANISM_PROVED`, three `EXECUTED`, and four `NOT VERIFIED`. |
| Status | Resolved at design level; four runtime residuals remain open |

## ERR-2026-08-21-126: Runtime Judge used an invalid first PowerShell byte-read expression

| Field | Value |
|---|---|
| Task | RCL-011 independent runtime artifact review |
| Severity | Low |
| Observed | The Judge's first array-path byte-read expression was invalid and produced no artifact result. |
| Impact | The first attempt could not reproduce either byte/hash oracle. |
| Resolution | Correct the path expression without writing any file and rerun both reads. |
| Verification | Judge reproduced 53/661 bytes, both exact SHA-256 values, valid JSON, absent denial files, and clean tracked/index state at `2026-08-20T20:54:09Z`. |
| Status | Resolved |

## ERR-2026-08-21-127: Finalizer tree probe omitted quoting around the revision expression

| Field | Value |
|---|---|
| Task | RCL-011 finalizer preflight |
| Severity | Low |
| Observed | An unquoted PowerShell `git rev-parse HEAD^{tree}` probe was parsed incorrectly and Git rejected an encoded token. |
| Impact | The first probe did not return the tree identifier. No repository state changed. |
| Resolution | Quote the revision expression as `git rev-parse 'HEAD^{tree}'`. |
| Verification | Corrected probe returned `02ad669885e78f1553b1b7af92a8a76a67cab0fa`. |
| Status | Resolved |

## ERR-2026-08-21-128: Preliminary evidence-hash command escaped newline literals incorrectly

| Field | Value |
|---|---|
| Task | RCL-011 evidence-manifest hash stabilization |
| Severity | Low |
| Observed | A preliminary one-line Python command hashed several CRLF working-tree files without applying the intended LF normalization because its newline literals were over-escaped. The next validator run failed on the first affected row. |
| Impact | The provisional evidence table was internally inconsistent and could not pass the fail-closed validator. |
| Resolution | Recompute all 18 rows through the validator's canonical `lf_normalized_utf8_bytes` helper and replace the provisional values. |
| Verification | Clean validator reports 18 verified hashes; all six entrypoints and the CRLF portability controls pass. |
| Status | Resolved |

## ERR-2026-08-21-129: Successor report showed an unavailable hashing API

| Field | Value |
|---|---|
| Task | Coordinator evidence-integrity review of the RCL-011 successor report |
| Severity | Medium |
| Observed | The report's coordinator-probe sample used static `SHA256.HashData` plus `Convert.ToHexString`, although that API pattern was unavailable and was not the command used for the retained artifact oracles. |
| Impact | The evidence wording did not faithfully reproduce the executed hash mechanism even though the recorded bytes and hashes were correct. |
| Resolution | Replace the sample with the executed `SHA256.Create().ComputeHash` and `BitConverter.ToString(...).Replace('-', '')` pattern while retaining strict UTF-8, BOM, LF, and CR checks. |
| Verification | Recompute the successor-report LF-normalized manifest hash and rerun all six validators, skill validation, six-file compilation, and `git diff --check`. |
| Status | Resolved before independent review |

## ERR-2026-08-21-130: Independent review found overclaimed runtime provenance and hash-refresh bypasses

| Field | Value |
|---|---|
| Task | RCL-011 corrective evidence-integrity review |
| Severity | High |
| Observed | Independent code review found that the prior classification treated durable Worker and Smart artifacts as stronger runtime provenance than the retained evidence supports. It also demonstrated that contradictory claim prose could pass after the self-referential evidence table was refreshed. |
| Impact | Worker write was overstated as mechanism-proved, Smart profile execution was overstated as executed, and hash-adjusted contradictions could preserve a green aggregate result. |
| Resolution | Downgrade Worker write to `EXECUTED` and Smart Worker runtime profile to `NOT VERIFIED`; retain only thread-cap behavior as `MECHANISM_PROVED`. Bind five non-self-referential claim documents by LF-normalized full-document hash, bind the smoke report by exact canonical fields, and add seven named negative mutations for every reviewer-specified bypass. Do not retain raw tool/control-plane traces retroactively. |
| Verification | All six validation entrypoints passed after hash stabilization: collaboration rejected the exact 72-label set and retained four named positive controls, transcript rejected 25, and Graphify governance rejected 41. The aggregate verified 21 evidence hashes and five closed claim documents; official skill validation, six-file compilation, and `git diff --check` exited 0. |
| Status | Resolved locally; independent re-review remains required |

## ERR-2026-08-21-131: First closed-document hash probe had invalid nested quoting

| Field | Value |
|---|---|
| Task | RCL-011 closed-document hash stabilization |
| Severity | Low |
| Observed | The first read-only one-line Python hash probe produced `SyntaxError: '(' was never closed` because nested quoting truncated the normalization expression. |
| Impact | The failed probe returned no hashes and changed no file. |
| Resolution | Use the already documented PowerShell/.NET strict UTF-8 and SHA-256 pattern with explicit LF normalization. |
| Verification | The corrected read-only probe returned hashes for all five claim documents plus STATUS and HANDOFF. |
| Status | Resolved |

## ERR-2026-08-21-132: Smoke report remained mutable outside its canonical fields

| Field | Value |
|---|---|
| Task | RCL-011 smoke-manifest self-reference review |
| Severity | High |
| Observed | Independent re-review found that the self-referential smoke report bound its evidence-table hashes and displayed canonical fields but did not freeze contradictory narrative elsewhere in the document. |
| Impact | Runtime promotions, failed-head success synonyms, historical classification changes, count drift, or arbitrary prose could preserve a green validator when table hashes were refreshed. |
| Resolution | Hash the complete LF-normalized smoke body after masking only exact SHA-256 cells in the recognized evidence table; keep actual cell hashes independently verified and add seven ordered negative mutations for the reported bypasses. |
| Verification | Exact 79-mutation collaboration PASS includes smoke canonical-body CRLF portability and the seven requested negatives. The aggregate verified canonical SHA-256 `809544093AF7CEFF63A437DFE10934BF25716F41E4E420C8757114BB667D0D99`, 21 actual evidence hashes, and five closed claim documents; all six entrypoints, official skill validation, six-file compilation, and `git diff --check` passed. |
| Status | Resolved locally; independent re-review remains required |

## ERR-2026-08-21-133: First verification-log patch used mismatched context

| Field | Value |
|---|---|
| Task | RCL-011 canonical-body verification logging |
| Severity | Low |
| Observed | The first patch that converted the pending verification record to its final result matched no context because one expected bullet omitted its `Actual evidence-table hashes` prefix. |
| Impact | The patch changed no file; validated code, hashes, and gate results were unaffected. |
| Resolution | Read the exact log tail and apply the bounded append/status update against the actual lines. |
| Verification | WORK-2026-08-21-023 now records the final gate result and ERR-2026-08-21-132 is marked resolved locally. |
| Status | Resolved |

## ERR-2026-08-21-134: Pre-push Judge rejected thread-cap mechanism proof

| Field | Value |
|---|---|
| Task | RCL-011 pre-push Master Judge gate at clean unpublished base `15a5c33355238e6c36247dd760873dcde99535a9` |
| Severity | High |
| Observed | The report retained the exact live fourth-spawn refusal and parent-visible snapshots, but authoritative retained control-plane evidence no longer exists. The package classified thread-cap/fourth-thread behavior as `MECHANISM_PROVED`. |
| Impact | The runtime matrix overstated one observed session event as independently durable mechanism evidence; the pre-push gate correctly returned `FAIL` and stopped publication. |
| Resolution | Downgrade thread-cap/fourth-thread behavior to `NOT VERIFIED`, preserve the live observation without promotion, bind exact zero/three/six counts, and add a negative mutation rejecting restoration to `MECHANISM_PROVED`. |
| Verification | Exact 80-mutation collaboration PASS verified 21 evidence hashes, five claim-document hashes, smoke canonical SHA-256 `193B55B09CCFA2ABE44FAEE4F8D450F622E467B4AE92815CBBE07103BD7766D5`, and STATUS/HANDOFF Graphify hashes. All six entrypoints, official skill validation, six-file compilation, and `git diff --check` passed. |
| Status | Resolved locally; fresh independent pre-push Master Judge remains required |

## ERR-2026-08-21-135: Reviewer found stale five-row runtime sentence

| Field | Value |
|---|---|
| Task | RCL-011 runtime residual-count integrity review |
| Severity | High |
| Observed | The successor report's current design-review narrative retained stale text saying five `NOT VERIFIED` rows, while its validator-bound matrix and exact residual list contained six. |
| Impact | Hash closure preserved the contradictory sentence, but no semantic rule reconciled that sentence with the parsed classification count. |
| Resolution | Correct the current sentence to six and add an ordered semantic mutation that restores five while refreshing both dependent claim/evidence hash layers. Require rejection before hash validation with `runtime_residual_count_mismatch:five:5:6`. |
| Verification | Exact 81-mutation collaboration PASS includes the hash-refreshed stale-five semantic rejection. All six entrypoints passed with 21 evidence hashes, five claim-document hashes, smoke canonical SHA-256 `CDFCB646E0EC4F83E08547EE05866542315AAA7CD15E635E01917F377D647332`, exact zero/three/six classifications, official skill validation, six-file compilation, and `git diff --check`. |
| Status | Resolved locally; independent re-review remains required |

## ERR-2026-08-21-136: First canonical-hash probe omitted validation-script import path

| Field | Value |
|---|---|
| Task | RCL-011 hash stabilization |
| Severity | Low |
| Observed | The first read-only Python canonical-hash probe imported `scripts.validation.verify_recall_collaboration` from repository root, where the verifier's sibling-module import was not on `sys.path`, and returned `ModuleNotFoundError: No module named 'verify_external_audit_transcript'`. |
| Impact | The probe produced no canonical hash and changed no file. |
| Resolution | Add `scripts/validation` to the one-shot probe's import path; do not change production imports. |
| Verification | The corrected read-only probe returned canonical hash `CDFCB646E0EC4F83E08547EE05866542315AAA7CD15E635E01917F377D647332`. |
| Status | Resolved |

## ERR-2026-08-21-137: Two combined corrective patches missed exact context

| Field | Value |
|---|---|
| Task | RCL-011 residual-count implementation and log finalization |
| Severity | Low |
| Observed | The first combined implementation patch targeted the mutation-count line in the wrong hunk, and the first combined final-log patch omitted the ERROR_LOG file marker. Both `apply_patch` calls failed exact-context validation. |
| Impact | Neither failed patch changed a file; the semantic implementation and recorded evidence were unaffected. |
| Resolution | Split each change into bounded file-specific patches against freshly read context. |
| Verification | The corrected patches are present; the complete final verification sweep and `git diff --check` passed afterward. |
| Status | Resolved |

## ERR-2026-08-21-138: Master Judge rejected deleted-artifact runtime evidence

| Field | Value |
|---|---|
| Task | RCL-011 final evidence-portability review |
| Severity | High |
| Observed | Fresh Master Judge review found that the ignored runtime root had been removed after the initial gate, but current documents still classified the documented Worker file bytes/hash as durable `EXECUTED` evidence. The raw Worker and Smart files and authoritative parent control-plane events are not independently inspectable from the repository/current checkout. |
| Impact | The Worker-write row overstated documentation of a historical observation as current portable runtime evidence; the exact zero/three/six aggregate was no longer supportable. |
| Resolution | Preserve the live file/byte/hash observations historically, explicitly record later removal of the ignored root, downgrade Worker write to `NOT VERIFIED`, bind zero/two/seven counts, and reject both `EXECUTED` and `MECHANISM_PROVED` Worker promotions. |
| Verification | Exact 82-mutation collaboration PASS includes both Worker promotion guards. All six entrypoints passed with 21 evidence hashes, five claim-document hashes, smoke canonical SHA-256 `93F52E64E7708B50D11823FE7D3EAC0FC8FC01A3673EB79B97B7A86DB4D546D0`, frozen STATUS/HANDOFF hashes, exact zero/two/seven classifications, official skill validation, six-file compilation, and `git diff --check`. |
| Status | Resolved locally; fresh independent Master Judge remains required |

## ERR-2026-08-21-139: Evidence-boundary sentence triggered Graphify snapshot guard

| Field | Value |
|---|---|
| Task | RCL-011 final evidence-portability hash stabilization |
| Severity | Low |
| Observed | The first focused post-hash harness failed with `snapshot_record_outside_block:docs/project/HANDOFF.md` because one non-Graphify sentence placed artifact hash values and the temporal phrase `current checkout` on the same line. |
| Impact | The portable Graphify guard correctly failed closed; no evidence was accepted and no external or protected action occurred. |
| Resolution | Split the historical byte/hash observation from the separate repository/check-out inspectability sentence, then refresh the frozen HANDOFF and verifier hashes. |
| Verification | Focused 82-mutation collaboration PASS and complete six-entrypoint verification passed after the wording correction. |
| Status | Resolved |

## ERR-2026-08-21-140: Reviewer found stale STATUS residual counts

| Field | Value |
|---|---|
| Task | RCL-011 final STATUS evidence-integrity review |
| Severity | High |
| Observed | STATUS retained current prose saying six fail-closed residuals, including its risk-table control, while the validator-bound runtime matrix contained seven `NOT VERIFIED` rows. |
| Impact | The frozen STATUS hash preserved contradictory current risk prose, but no semantic check derived that sentence's count from the runtime classification matrix. |
| Resolution | Correct both current STATUS sentences to seven and add ordered mutation `status_residual_count_stale_six_hash_refresh`, which restores six while refreshing the STATUS Graphify normative hash and dependent verifier/evidence hashes. Require semantic rejection before hash validation. |
| Verification | Focused and complete 83-mutation collaboration validation passed with exact error `status_residual_count_mismatch:six:6:7`; transcript 25, Graphify governance 41, 21 evidence hashes, five claim documents, official skill validation, six-file `py_compile`, and `git diff --check` also passed. |
| Status | Resolved locally; fresh independent review remains required |

## ERR-2026-08-21-141: P1 stabilization caught stale contexts and newline-hash calculation drift

| Field | Value |
|---|---|
| Task | Bounded P1 remediation and evidence stabilization |
| Severity | Low |
| Observed | One multi-file patch failed exact-context validation and changed nothing. A first read-only ad hoc hash command also produced incorrect STATUS/HANDOFF and validator values because its command-line newline escaping did not match the repository's LF-normalized helper. |
| Impact | No incorrect hash was accepted: the standalone Graphify validator failed closed on the mismatch before the aggregate suite could pass. No protected action occurred. |
| Resolution | Re-read exact contexts, applied smaller patches, and regenerated every affected hash through the production `lf_normalized_utf8_sha256` / `lf_normalized_utf8_bytes` functions. |
| Verification | All six validator entrypoints, exact 25/41/88 mutation sets, five collaboration positive controls, official skill validation, six-file compilation, and `git diff --check` pass after regeneration. |
| Status | Resolved locally; independent re-review remains required |

## ERR-2026-08-21-142: Read-only cloud preflight could not locate the gcloud launcher

| Field | Value |
|---|---|
| Task | Prize-path cloud readiness preflight |
| Severity | Medium |
| Observed | `gcloud` was not recognized in the coordinator PowerShell session, was absent from `PATH`, and was not found in the bounded standard user locations checked without exposing identifiers. Earlier repository evidence says an SDK had been available, but its launcher path is not durably recorded. |
| Impact | Billing linkage, active principal, API states, permissions, budgets, and project targeting could not be read back. The failure is launcher availability, not evidence that any cloud state is disabled. |
| Resolution | Restore or locate the existing SDK launcher before the protected billing/API sequence; perform sanitized read-only state checks first, then request exact owner authorization for each mutation. Do not install, relink billing, enable APIs, create resources, call models, or spend under this error resolution alone. |
| Verification | Pending. Success requires a usable launcher plus sanitized read-only project, principal, billing-link, API-state, and permission read-back without persisting account or project identifiers. |
| Status | Open; cloud state remains `NOT VERIFIED` |

## ERR-2026-08-21-143: Coordinator converted auditor extensions into unauthorized removals

| Field | Value |
|---|---|
| Task | Apply the 2026-08-21 external auditor report |
| Severity | High |
| Observed | The coordinator treated several report extensions as removable scope, stated that Gemma was removed from the storyboard, excluded Model Armor and Agent Runtime from the stretch gate, and activated the coordinator-created `RunEvidenceManifest` without first requesting owner approval. |
| Impact | The plan did not faithfully represent the owner's instruction to implement every auditor item, and coordinator initiative exceeded its authorized boundary. No product code, protected action, or external publication resulted. |
| Resolution | Create a binding item-by-item auditor action register; restore every report extension to the plan and evidence ledgers behind its stated gate; preserve base-path versus conditional-extension distinctions; mark `RunEvidenceManifest` as an owner-pending proposal; record DEC-038 reserving all scope removal decisions to the owner. |
| Verification | Fifty required report markers passed the bounded coverage check. Transcript 25/25, Graphify governance 41/41 plus portability, collaboration 88/88 plus five positive controls, official skill validation, six-file `py_compile`, `git diff --check`, and bounded secret/trailer scans passed. |
| Status | Resolved locally; owner scope authority is recorded in DEC-038 |

## ERR-2026-08-23-144: Orphaned smoke engine breached same-day deletion rule

| Field | Value |
|---|---|
| Task | L1 managed-runtime smoke cleanup |
| Severity | Medium |
| Observed | `recall-hello-smoke` was ready at `2026-08-22T19:25:20Z` and deleted at `2026-08-23T08:21:00Z`, an exact elapsed interval of 12 hours, 55 minutes, and 40 seconds (reported operationally as 12 hours 55 minutes). |
| Breach | The rule "smoke resources are deleted the same day" was breached. |
| Cause | Two deletion attempts were recorded as hanging at `19:40 TSS`, while `gcloud` and ADC became unresponsive together. That local-time label is retained as incident context but is not used for elapsed-time calculation. |
| Resolution | The director deleted the engine, authoritative read-back returned zero matching engines, and L1 independently verified the absence. |
| Cost | The incident remained inside free-tier coverage; estimated incremental cost was less than USD 1. |
| Timestamp discipline | The initial report said approximately 16 hours because UTC and TSS were mixed. Inventory and ERR records must now use only UTC ISO-8601 timestamps, and durations must be calculated from two UTC timestamps. Daily inventory reconciliation is mandatory without exception; this incident is the justification. |
| Status | Closed (same day as detection) |

## ERR-2026-08-23-B: Hung non-interactive gcloud authentication processes

| Field | Value |
|---|---|
| Task | Cross-lane process-hygiene incident review |
| Severity | High |
| Evidence class | `OWNER_REPORTED / REPORT_DERIVED`; no raw process snapshot is retained in this repository. |
| Observed | `OWNER_REPORTED`: L3 reported four hung non-interactive `gcloud auth application-default print-access-token`-class processes. PID 50000 reportedly started at `2026-08-21 19:13 TSS` (`2026-08-21T16:13:00Z`), accumulated approximately 32 CPU hours, and held approximately 2.6 GB RAM. PID 16128 reportedly started at `2026-08-22 15:59 TSS` (`2026-08-22T12:59:00Z`), accumulated approximately 17.5 CPU hours, and held approximately 1.9 GB RAM; two similar processes were also reported. UTC values are the canonical timestamps; the TSS labels are retained only as source context. |
| Root cause | `REPORT_DERIVED`: the supplied incident report attributes the hang to expired authentication opening a reauthentication prompt inside a non-interactive session, so the process never terminated and the shell fallback `|| echo FAILED` never executed. The reported callers were one-off checks from director task `4751f38a` and L1 task `1784eba8`. |
| Resolution | `OWNER_REPORTED`: L3 identified the processes. With owner approval they were reportedly terminated at `2026-08-23T17:29:00Z` (`20:29 TSS`); reported free RAM increased from 9.0 GB to 11.6 GB. Thanks to L3 for detecting the cross-lane resource leak. |
| Prevention | Every non-interactive `gcloud` call must use a bounded timeout and disabled prompts; L1-C will measure and report the exact mechanism. The pre-flight routine must also inspect for hung processes before starting cloud work. A shell fallback is not a timeout. |
| Verification | Owner/director-reported incident evidence records the process termination and memory recovery; this gate did not independently inspect raw process telemetry. No claim is made here that the pending L1-C timeout mechanism has executed. |
| Status | Closed (same day) |
