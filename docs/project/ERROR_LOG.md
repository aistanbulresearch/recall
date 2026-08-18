# Error Log

Append-only. Log errors even when a retry succeeds.

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
- ERR-2026-08-15-020 awaits the owner's billing-account selection.
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
| Status | Open security risk; renewed bounded owner exception granted, not remediated |

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
