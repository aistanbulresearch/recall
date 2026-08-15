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
