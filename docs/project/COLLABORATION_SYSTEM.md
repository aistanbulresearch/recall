# Recall Codex Collaboration System

## Purpose

Recall uses one owner-facing coordinator plus short-lived, task-scoped subagents. This operating system governs development collaboration only; it is separate from the Recall product's managed clinical-evidence agent fleet.

## File tree

```text
.agents/skills/recall-collaboration/
|-- SKILL.md
|-- agents/openai.yaml
`-- references/master-judge-rubric.md

.codex/
|-- config.toml
`-- agents/
    |-- recall-scout.toml
    |-- recall-worker.toml
    |-- recall-smart-worker.toml
    `-- recall-master-judge.toml
```

## Authority and model matrix

| Role | Model and effort | Default permission | Authority boundary |
|---|---|---|---|
| Coordinator | Primary session | Owner-approved session scope | Decomposes work, assigns ownership, verifies evidence, communicates with owner; cannot replace owner approval |
| Recall Scout | GPT-5.6 Terra, low | Read-only | Focused discovery only; no writes, external mutation, or subagent spawning |
| Recall Worker | GPT-5.6 Sol, medium | Workspace-write | Implements only exclusive owned paths and tests; no scope expansion or protected actions |
| Recall Smart Worker | GPT-5.6 Sol, high | Workspace-write | Difficult bounded implementation/integration; same protected-action boundary |
| Recall Master Judge | GPT-5.6 Sol, high by project default | Read-only | Independently audits; cannot edit, repair, approve, publish, or spawn |

The Master Judge profile intentionally omits `model_reasoning_effort`. Project config supplies `high`; a critical gate may explicitly request `xhigh` or `max` with a bounded or no-history fork when the runtime supports an override. A full-history fork must not be used when an explicit model or effort override is required.

`sandbox_mode = "read-only"` is a default execution boundary, not the only control. Parent-session permissions are reapplied to subagents, so the coordinator must keep Scout and Judge assignments read-only, reject escalation requests, and execute the negative write-denial smoke test before relying on this boundary.

## Assignment contract

Every delegated task states:

1. one objective;
2. exact exclusively owned writable paths;
3. read-only dependencies;
4. out-of-scope work;
5. acceptance criteria and tests;
6. evidence to return;
7. stop conditions;
8. that the agent is a leaf and must not spawn agents;
9. that other work may exist and must not be reverted.

Parallel scouts may answer distinct questions. Parallel writers are allowed only when their file sets and mutable dependencies do not overlap. The coordinator keeps at most three spawned threads active.

Each writing assignment holds an explicit writer lease from dispatch until the coordinator inspects its returned diff and tests. A dependent writer cannot start before lease release. `STATUS.md`, `MASTER_PLAN.md`, `HANDOFF.md`, project logs, evidence ledgers, and dependency lockfiles are coordinator-owned unless one named finalizer receives exclusive ownership.

## Gate sequence

```text
design and acceptance criteria; owner approval when the AGENTS.md checkpoint applies
  -> scoped implementation and tests
  -> independent Master Judge
  -> artifact and mechanism verification
  -> project records
  -> owner approval for any protected action
```

Master Judge runs after design, after implementation/tests, after each pair of completed writing assignments in a long work unit, on disagreement, on any high-risk boundary change, and before commit, push, merge, release, or phase exit. Its exact evidence classes and verdicts are versioned in the skill reference.

Judge review starts only when the in-scope writer leases are released and the worktree is stable.

## External GitHub auditor cadence

The external GitHub auditor is not a Codex subagent and is not controlled by the coordinator. It audits only stable owner-published remote heads and must remain read-only without GitHub comments, reviews, bot records, or authorship metadata.

Request an external audit:

1. after this collaboration infrastructure is owner-committed and pushed, before it is merged or used as a phase gate;
2. after every two completed writing-agent assignments or three remote commits, whichever first produces a stable new remote checkpoint;
3. immediately after any material privacy, safety, scientific, evidence, provenance, eligibility, architecture, or audit-remediation change is published;
4. before every merge and phase exit;
5. at RCL-902 feature freeze even if no earlier trigger fired.

Do not audit an unchanged remote head. The coordinator tells the owner when a reviewable head exists and reports the auditor's exact scope and evidence boundary. The external audit never replaces Master Judge or owner approval.

## Acceptance criteria

- The repo skill has valid frontmatter, an exact `$recall-collaboration` invocation, and a resolving judge-rubric link.
- `.codex/config.toml` parses and enables agents with at most three spawned threads.
- Exactly four custom agent TOMLs parse with unique file stems and required fields.
- Scout and Judge default to read-only; Worker roles default to workspace-write.
- Model and reasoning settings match the authority matrix; Judge inherits high and permits a critical explicit override.
- Every profile prohibits child spawning and protected external actions.
- `AGENTS.md`, this document, ADR-0009, status, plan, handoff, work log, decision log, and error log agree.
- No skill/profile file is ignored by Git and no credential or prohibited authorship marker appears.
- A fresh-session functional smoke proves custom-agent discovery, read-only write denial, scoped temporary Worker write, no child spawn, and exact verdict formatting.

## Runtime acceptance matrix

| Surface | Implemented/configured | Nested VUS-root evidence | Required Recall-root evidence |
|---|---|---|---|
| Skill discovery | Yes | `REPORT_DERIVED`; reported strict-config load | Repeat with retained literal transcript after owner-published checkout |
| Scout | Yes; Terra low, read-only configured | `REPORT_DERIVED`; reported bounded read, policy refusal, and no child | Direct sandbox-denial test with retained literal transcript |
| Worker | Yes; Sol medium, workspace-write configured | `REPORT_DERIVED`; reported profile discovery and inherited denial | Exact ignored-file write and content read-back |
| Smart Worker | Yes; Sol high, workspace-write configured | `NOT_VERIFIED` | Bounded hard-task dry smoke without protected action |
| Master Judge | Yes; Sol and project default high configured | `REPORT_DERIVED`; reported `FAIL` with no repair | Read-only denial plus independent PASS/FAIL formatting; effective effort evidence |
| Thread cap | Three configured | `REPORT_DERIVED`; sequential one-child report only | Three concurrent children allowed; fourth refused or queued according to runtime contract |
| Leaf no-spawn | Yes in all profiles | `REPORT_DERIVED` for Scout, Worker, and Judge | Repeat all roles with retained events, including Smart Worker |
| Protected actions | Exhaustive profile prohibitions | `REPORT_DERIVED`; no external or protected action reported | Controlled owner-operation request stops and returns to coordinator |

No row is considered runtime-verified from configuration alone. The sanitized report-derived evidence and exact limits are in `docs/evaluation/reports/2026-08-17--codex-collaboration-smoke.md`.

## Safe smoke-test plan

### Structural tests in the current session

1. Run the skill validator.
2. Parse every TOML with Python `tomllib` and assert schema, model, effort, sandbox, count, and required instruction fragments.
3. Parse `openai.yaml`, assert literal `$recall-collaboration`, and resolve every Markdown link.
4. Run `codex features list` and confirm multi-agent support is enabled.
5. Run Git ignore, whitespace, secret-signature, and prohibited-authorship scans.

### Functional tests in a fresh Recall-root Codex session

Launch the session with Recall as its primary writable workspace, not as a nested process from a different repository. Use only ignored `temp/collaboration-smoke/` paths and preserve a before/after Git status snapshot.

1. Ask `recall-scout` to read one named heading and return its evidence. Confirm no file changed.
2. For permission-boundary testing only, ask Scout to attempt one controlled file creation. Expected result: permission denial, no escalation, and no file.
3. Ask `recall-worker` to create one exact temporary text file in its exclusive scope. Confirm the file and content, then remove the temporary directory.
4. Ask `recall-master-judge` to inspect the smoke artifacts and return one allowed verdict without editing.
5. Confirm no child agent was spawned, no external write occurred, and tracked Git status matches the pre-smoke snapshot.

Until the fresh-session tests pass, configuration is `IMPLEMENTED` and structurally verified, but runtime role discovery and permission enforcement are `NOT VERIFIED`.

The first nested ephemeral smoke is retained only as `REPORT_DERIVED`: it reported Scout, Worker, and Master Judge discovery, inherited read-only denial, Scout refusal, and Master Judge `FAIL`. It is navigation context for the required Recall-root smoke, not runtime or mechanism proof.
