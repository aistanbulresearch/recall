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
- A Recall-root functional smoke records bounded custom-profile discovery, contemporaneous Worker/Smart artifact observations, exact verdict formatting, and an observed fourth-spawn refusal while keeping unproved mechanisms fail-closed. The ignored run root was later removed, so the raw artifacts are not independently inspectable from the repository/current checkout; their documented bytes and hashes do not establish Worker write or Smart runtime-profile execution.
- The authoritative external-audit transcript gate binds the fixed source task/turn, exact LF-normalized body count and SHA-256, delimiters, and the complete LF-normalized non-authoritative summary hash. It proves repository-artifact integrity after bootstrap, not live Codex equivalence.
- The portable Graphify governance gate binds terminal-newline-normalized AGENTS/CLAUDE policy equality plus the complete canonical policy SHA-256. STATUS and HANDOFF must each contain one byte-identical, ordered 17-key `graphify-snapshot` block and match their frozen complete LF-normalized UTF-8 hashes; conflicting or otherwise unenumerated alterations fail closed. The Graphify harness separately proves CRLF portability. This does not prove scheduler identity, execution, permissions, or failure handling at runtime.
- The structural evidence table binds twenty-one strict UTF-8 text files, including force-tracked `CLAUDE.md`, all six verifier/test entrypoints, the sole Recall-root runtime successor, ADR-0008, ADR-0009, and MASTER_PLAN. Its hash mode is `LF_NORMALIZED_UTF8`: CRLF and lone CR normalize to LF before UTF-8 SHA-256, so semantically identical Git index and Windows working-tree text remain portable while content mutations still fail.
- The standalone transcript and Graphify harnesses bind exact ordered label tuples of 25 and 41 negative mutations. The aggregate collaboration harness binds an exact ordered 88-label tuple: the prior 84 remain in order and four clause-local camouflage cases reject aggregate-count, allowlisted-subject, and billing-negation bypasses after synchronized hash refresh. The Worker baseline is `NOT VERIFIED`; exact probes reject promotion to either `EXECUTED` or `MECHANISM_PROVED`. Hash-refreshed semantic probes reject stale runtime-report and STATUS residual counts plus the three external-audit overclaim classes before hash validation. These checks are an intentional deny-list, not a general natural-language verifier; independent external review remains the trust boundary for synchronized document and validator changes. The structural validator binds the displayed hash count, hash mode, validation scope, aggregate count and label list, both standalone mutation counts, and the CRLF portability and explicit-owner-authorization positive controls rather than trusting prose or counts alone. The smoke report's canonical LF-normalized body hash masks only exact SHA-256 cells inside its recognized evidence table; every other byte remains frozen, while the actual table-cell hashes are still checked independently.

## Runtime acceptance matrix

| Surface | Implemented/configured | Nested VUS-root evidence | Required Recall-root evidence |
|---|---|---|---|
| Skill discovery | Yes | Historical `REPORT_DERIVED` | `EXECUTED` with all four custom profiles in the Recall-root run |
| Scout | Yes; Terra low, read-only configured | Historical policy refusal | Policy refusal and absent file were observed; inherited sandbox denial remains `NOT VERIFIED` |
| Worker | Yes; Sol medium, workspace-write configured | Historical inherited denial | `NOT VERIFIED`: the exact ignored file was observed as 53 bytes with SHA-256 `BC91A143...EFFF7`, but the ignored run root was later removed and raw parent tool events were not retained |
| Smart Worker | Yes; Sol high, workspace-write configured | None | `NOT VERIFIED`: the 661-byte artifact was observed during the live session, but the ignored run root was later removed and immutable runtime-profile/tool telemetry was not retained |
| Master Judge | Yes; Sol and project default high configured | Historical formatted `FAIL` | Verdict formatting `EXECUTED`; effective runtime effort `NOT VERIFIED` |
| Thread cap | Three configured | Historical sequential observation | `NOT VERIFIED`: three active children and the exact fourth-spawn refusal were observed live, but authoritative retained control-plane evidence no longer exists |
| Leaf no-spawn | Yes in all profiles | Historical partial observations | `NOT VERIFIED`: no single retained parent tree covers all four role finals and descendants |
| Protected actions | Exhaustive profile prohibitions | Historical no-action report | `NOT VERIFIED`: refusal and no-observed-side-effect snapshots exist, but authoritative child tool ordering is unavailable |

No row is considered runtime-verified from configuration alone. Historical structural evidence remains in `docs/evaluation/reports/2026-08-17--codex-collaboration-smoke.md`; current bounded runtime evidence and exact limits are in `docs/evaluation/reports/2026-08-18--rcl-011-recall-root-runtime.md`.

Validator-bound P1 runtime evidence contract:

- Worker write in a Recall-root workspace: `NOT VERIFIED`.
- Three-thread cap and fourth-thread behavior: `NOT VERIFIED`.
- Complete four-role leaf no-spawn: `NOT VERIFIED`.
- Protected owner-operation stop and no protected side effect: `NOT VERIFIED`.

The partial nested observations for Scout, Worker, and Judge do not prove the complete four-role leaf property. Likewise, a report that no protected action occurred does not prove the stop mechanism or the absence of every protected downstream side effect.

Current exact classification counts are zero `MECHANISM_PROVED`, two `EXECUTED`, and seven `NOT VERIFIED`. The aggregate result is partial and fail-closed; RCL-011 is `PARTIAL_FAIL_CLOSED / DEFERRED` without relabeling any residual. The Runtime Judge returned `PASS`, but the final contract conservatively rejects its stronger provenance assessment because the ignored raw artifacts and immutable parent tool/control-plane logs were not retained.

## Safe smoke-test plan

### Structural tests in the current session

1. Run the skill validator.
2. Parse every TOML with Python `tomllib` and assert schema, model, effort, sandbox, count, and required instruction fragments.
3. Parse `openai.yaml`, assert literal `$recall-collaboration`, and resolve every Markdown link.
4. Run `codex features list` and confirm multi-agent support is enabled.
5. Run Git ignore, whitespace, secret-signature, and prohibited-authorship scans.
6. Run `verify_external_audit_transcript.py` and its disposable-copy mutation harness.
7. Run `verify_graphify_governance.py` and its disposable-copy mutation harness without reading ignored Graphify artifacts or external automation files.

### Functional tests in the Recall-root Codex session

Launch the session with Recall as its primary writable workspace, not as a nested process from a different repository. Use only ignored `temp/collaboration-smoke/` paths and preserve a before/after Git status snapshot.

1. Scout read the named heading and returned policy refusal; the denial file was absent. This did not directly prove inherited sandbox denial.
2. Worker produced one exact ignored file and the coordinator reproduced its bytes and hash during the live session; the ignored run root was later removed, so the documentation alone leaves Worker write `NOT VERIFIED`.
3. Smart Worker produced one exact ignored JSON artifact during the live session; the ignored run root was later removed, and the documentation does not prove the runtime profile without retained immutable telemetry.
4. Three concurrent children were observed active while a fourth spawn failed with the exact thread-limit error; the observation is not independently durable mechanism evidence.
5. Master Judge returned exact `PASS` formatting and reproduced artifacts without repair; runtime-emitted effort telemetry was unavailable.
6. Protected-action refusal and identical remote/local before-after snapshots showed no observed side effect, but parent-visible evidence could not prove child tool ordering.

The run closes no mechanism-level runtime row. Worker write, thread-cap/fourth-thread behavior, inherited read-only fail-closed behavior, Smart Worker runtime profile, effective Judge effort, complete four-role leaf no-spawn, and protected-action stop ordering remain `NOT VERIFIED`; RCL-011 is not fully verified.

The first nested ephemeral smoke is retained only as `REPORT_DERIVED`: it reported Scout, Worker, and Master Judge discovery, inherited read-only denial, Scout refusal, and Master Judge `FAIL`. It is navigation context for the required Recall-root smoke, not runtime or mechanism proof.
