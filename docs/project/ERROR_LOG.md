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
| Verification | Pending corrected push gate and remote read-back. |
| Status | In progress |

## Open errors

- ERR-2026-08-14-007 remains open until corrected push-gate and remote read-back verification.
- The hostname spelling issue is a pending decision, not an execution error.
