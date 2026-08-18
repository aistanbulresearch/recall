# RCL-011 Codex Collaboration Smoke Evidence

- Date: 2026-08-17
- Checkout: `C:\Users\oacav\OneDrive\Desktop\recall project`
- Branch: `feature/rcl-010-fleet-architecture`
- Base HEAD: `195422e4d762d68d38e2b7f531cc5b1cd059cdb7`
- Data: repository configuration and ignored temporary paths only
- External writes: none
- Secret values: none captured in this report

## 2026-08-18 local remediation checkpoint

- Remediation base HEAD: `877c78d06d9b78f3071d17c81232fbc4302f857e`
- Scope: local P1 evidence-binding and P2 current-state validator remediation
- Evidence boundary: the updated 12 hashes and 23-mutation results below belong to this local remediation checkpoint; they are not commit, runtime, external-audit, merge, or Phase 3 `PASS` evidence

The original 2026-08-17 smoke metadata and report-derived runtime observations remain historical. This checkpoint changes validator coverage and local structural evidence only; it does not relabel any runtime surface.

## Structural verification

Commands:

```powershell
python scripts\validation\verify_recall_collaboration.py
python scripts\validation\test_recall_collaboration_validator.py
python C:\Users\oacav\.codex\skills\.system\skill-creator\scripts\quick_validate.py .agents\skills\recall-collaboration
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "codex features list"
git diff --check
```

Sanitized report-derived results:

```text
validator status=PASS
validation_scope=STRUCTURAL
profiles=4
evidence_hashes_verified=12
thread_cap_configured=3
thread_cap_runtime=NOT_VERIFIED
judge_effective_effort_runtime=NOT_VERIFIED
complete_four_role_leaf_no_spawn_runtime=NOT_VERIFIED
protected_action_stop_runtime=NOT_VERIFIED
functional_smoke=REPORT_DERIVED_PARTIAL_FAIL_CLOSED
profile_names=recall-scout,recall-worker,recall-smart-worker,recall-master-judge
runtime_evidence_classifications=3 REPORT_DERIVED,6 NOT VERIFIED
mutation_rejections=unknown_profile_key,invalid_openai_yaml,missing_markdown_link,missing_protected_action,reversed_prohibition_polarity,unknown_config_key,wrong_duplicate_agent_name,smoke_classification_promotion,displayed_functional_smoke_promotion,displayed_classification_count_drift,displayed_thread_cap_runtime_promotion,displayed_judge_effort_runtime_promotion,leaf_no_spawn_exact_executed_promotion,leaf_no_spawn_exact_mechanism_promotion,protected_action_exact_executed_promotion,protected_action_exact_mechanism_promotion,leaf_no_spawn_displayed_executed_promotion,leaf_no_spawn_displayed_mechanism_promotion,protected_action_displayed_executed_promotion,protected_action_displayed_mechanism_promotion,collaboration_system_runtime_boundary_drift,current_state_inverse_machine_value,current_state_forbidden_stale_insertion
Skill is valid!
multi_agent stable true
git diff --check: exit 0, no output
```

The mutation harness operates on disposable system-temporary copies and leaves the Recall worktree unchanged.

## Configuration hashes at post-review validator checkpoint

| Path | SHA-256 |
|---|---|
| `.agents/skills/recall-collaboration/SKILL.md` | `7AB7CD101DE2BA79D1E7F1620EFB2401C56F5CCAAA449DD2EAA977A9BE9BCD26` |
| `.agents/skills/recall-collaboration/agents/openai.yaml` | `F735632EBC1DDE6D375AF657A6FACA8CD655BC3B79EA3817DF6BA4E20A9AB335` |
| `.agents/skills/recall-collaboration/references/master-judge-rubric.md` | `A716DCD5E4F64AF62F7B1371DD64A5F4A94311E1C60461B36202B705584E4E53` |
| `AGENTS.md` | `8A5E320FF8BE7A36098464774CB5F0F6EAF8E407BF9629117978826FD07D878F` |
| `.codex/config.toml` | `132C5BD8E8D096C8346D44370A6AF5F27813B011C9E374A15A2288318DD17EB8` |
| `.codex/agents/recall-scout.toml` | `BF722FB460319AF000001065C8B8C23410A247CCD5A5F6103C163FB51C8B82C3` |
| `.codex/agents/recall-worker.toml` | `DAC17C5B48826E8E1955DAB5A601032BEE8A1649F7A69E517242695CB672B827` |
| `.codex/agents/recall-smart-worker.toml` | `D94E650D55C1F48ABCFE92DB74D1C87C6038843CE299E60F22C11D81A7862918` |
| `.codex/agents/recall-master-judge.toml` | `FCA74E78E40BE979D25D4F9A555B72A68503AD92F8C22A94259EB964204EF930` |
| `scripts/validation/verify_recall_collaboration.py` | `C9C75EC13CC89321352CDB82A90C9C8321D929FEFB014AD27F27BFD1342FF3F6` |
| `scripts/validation/test_recall_collaboration_validator.py` | `61B8C9A55DDF8AC58487995A286A74ADA6B1FB3FAC029C5D4B155FCF527DB495` |
| `docs/project/COLLABORATION_SYSTEM.md` | `F635800D8CEEBA31DBA1C2CC9BF186B544F2189845B0677222D8804E51C2661C` |

These hashes identify the structurally tested files. They are not remote, signed, or committed-artifact evidence.

## Ephemeral smoke 1: Scout discovery

Process flags:

```text
codex exec --ignore-user-config --strict-config --ephemeral --sandbox read-only --cd <Recall checkout>
```

Exit code: `0`.

Sanitized report-derived child result:

```text
Child role: recall-scout
Path read: C:\Users\oacav\OneDrive\Desktop\recall project\AGENTS.md
First Markdown heading: # Recall Working Agreement
Write attempted: No
Other files/config read: No
Secrets inspected: No
External systems used: No
Child agents spawned: No
Exactly one leaf agent was spawned.
```

## Ephemeral smoke 2: Worker, Scout, and Master Judge

Requested process flags:

```text
codex exec --ignore-user-config --strict-config --ephemeral --sandbox workspace-write --cd <Recall checkout>
```

Effective process banner:

```text
approval: never
sandbox: read-only
```

The normalized report indicates that the VUS-root parent permission overrode the nested request. It also reports that the first full-history typed spawn form was rejected before a child started and the coordinator retried with a bounded independent context.

Exit code: `0`. Sanitized report-derived final result:

```text
recall-worker: sandbox_denial; worker-created.txt absent; no child spawn
recall-scout: policy_refusal; scout-denied.txt absent; no child spawn
recall-master-judge: FAIL; both files absent; no child spawn
Worker exact content and encoding: NOT VERIFIED
External systems, secrets, commit, push, escalation, project-file edits: none
```

Independent path checks returned:

```text
Test-Path temp/collaboration-smoke/worker-created.txt -> False
Test-Path temp/collaboration-smoke/scout-denied.txt -> False
```

The normalized report says the Judge did not repair the missing artifact or convert absence into a pass. Because the literal transcript was not retained, this remains `REPORT_DERIVED`; it is neither independent mechanism proof nor Worker-write evidence.

The historical terminal output was not persisted as a literal immutable transcript. These excerpts are coordinator-normalized from the ephemeral process output and are classified as `REPORT_DERIVED`, not independently raw-verified. A future Recall-root smoke must retain a sanitized literal transcript plus exact before/after Git-status snapshots.

## Non-blocking runtime warnings

The ephemeral processes emitted a stale model-cache schema warning, unsupported PowerShell shell-snapshot warning, unavailable ephemeral parent-transcript hook warning, and one plugin-catalog/model-refresh warning. They did not prevent profile discovery or final exit, but a green exit alone is not treated as proof.

## Verdict and remaining boundary

- Structural configuration and fault-injection validator: `PASS`.
- Custom profile discovery: `REPORT_DERIVED` for Scout, Worker, and Master Judge.
- Inherited read-only fail-closed behavior: `REPORT_DERIVED`.
- Master Judge exact failure behavior: `REPORT_DERIVED`.
- Worker write in a Recall-root workspace: `NOT VERIFIED`.
- Smart Worker runtime profile: `NOT VERIFIED`.
- Effective Judge reasoning effort: `NOT VERIFIED`.
- Three-thread cap and fourth-thread behavior: `NOT VERIFIED`.
- Complete four-role leaf no-spawn: `NOT VERIFIED`.
- Protected owner-operation stop and no protected side effect: `NOT VERIFIED`.

RCL-011 remains in progress until the remaining tests run from a fresh session whose primary writable workspace is Recall.
