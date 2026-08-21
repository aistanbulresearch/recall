# RCL-011 Codex Collaboration Smoke Evidence

- Date: 2026-08-17
- Checkout: `C:\Users\oacav\OneDrive\Desktop\recall project`
- Branch: `feature/rcl-010-fleet-architecture`
- Base HEAD: `195422e4d762d68d38e2b7f531cc5b1cd059cdb7`
- Data: repository configuration and ignored temporary paths only
- External writes: none
- Secret values: none captured in this report

## 2026-08-21 successor manifest checkpoint

- Successor base HEAD: `c86139048d1532c79ed190d0cc98ce2ad878414b`
- Audited predecessor HEAD: `877c78d06d9b78f3071d17c81232fbc4302f857e`
- Scope: structural validation plus bounded runtime evidence for external-transcript integrity, Graphify governance, current-state validation, and the sole Recall-root runtime successor
- Evidence boundary: the updated 21 hashes and 83-mutation collaboration results below belong to the current local finalization worktree. They are not a commit, merge, product-runtime, cloud, clinical, or Phase 3 `PASS`.

The original 2026-08-17 smoke metadata and report-derived runtime observations remain historical. Current bounded runtime classifications and their limitations live only in `2026-08-18--rcl-011-recall-root-runtime.md`.

## Structural verification

Commands:

```powershell
python scripts\validation\verify_recall_collaboration.py
python scripts\validation\test_recall_collaboration_validator.py
python scripts\validation\verify_external_audit_transcript.py
python scripts\validation\test_external_audit_transcript.py
python scripts\validation\verify_graphify_governance.py
python scripts\validation\test_graphify_governance.py
python C:\Users\oacav\.codex\skills\.system\skill-creator\scripts\quick_validate.py .agents\skills\recall-collaboration
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "codex features list"
git diff --check
```

Sanitized structural-manifest results:

```text
validator status=PASS
validation_scope=STRUCTURAL_PLUS_BOUNDED_RUNTIME_EVIDENCE
profiles=4
evidence_hashes_verified=21
evidence_hash_mode=LF_NORMALIZED_UTF8
thread_cap_configured=3
profile_names=recall-scout,recall-worker,recall-smart-worker,recall-master-judge
aggregate_collaboration_mutation_rejections=83
mutation_rejections=unknown_profile_key,invalid_openai_yaml,missing_markdown_link,missing_protected_action,reversed_prohibition_polarity,unknown_config_key,wrong_duplicate_agent_name,smoke_classification_promotion,displayed_functional_smoke_promotion,displayed_classification_count_drift,displayed_thread_cap_runtime_promotion,displayed_judge_effort_runtime_promotion,leaf_no_spawn_exact_executed_promotion,leaf_no_spawn_exact_mechanism_promotion,protected_action_exact_executed_promotion,protected_action_exact_mechanism_promotion,leaf_no_spawn_displayed_executed_promotion,leaf_no_spawn_displayed_mechanism_promotion,protected_action_displayed_executed_promotion,protected_action_displayed_mechanism_promotion,collaboration_system_runtime_boundary_drift,current_state_inverse_machine_value,current_state_predecessor_missing,current_state_predecessor_duplicate,current_state_unknown_key,current_state_predecessor_reordered,current_state_predecessor_inverse,current_predecessor_head_confusion,external_transcript_dependency_mutation,graphify_governance_dependency_mutation,transcript_probe_deletion_hash_refresh,graphify_probe_deletion_hash_refresh,current_state_forbidden_stale_insertion,current_c8_head_then_pass,current_c8_pass_then_head,predecessor_877_head_then_pass,predecessor_877_pass_then_head,current_c8_report_head_then_pass,current_c8_report_pass_then_head,predecessor_877_report_head_then_pass,predecessor_877_report_pass_then_head,displayed_evidence_hash_count_drift,displayed_evidence_hash_mode_drift,displayed_transcript_mutation_count_drift,displayed_graphify_mutation_count_drift,displayed_positive_control_drift,current_c8_passed_variant,predecessor_877_passed_variant,current_c8_passed_external_audit,predecessor_877_passed_external_audit,runtime_custom_profile_discovery_demotion,runtime_read_only_fail_closed_promotion,runtime_judge_formatting_demotion,runtime_worker_write_executed_promotion,runtime_smart_profile_demotion,runtime_judge_effort_promotion,runtime_thread_cap_demotion,runtime_leaf_no_spawn_promotion,runtime_protected_stop_promotion,current_c861_head_reverted,current_c861_pass_reverted,displayed_aggregate_mutation_count_drift,runtime_classification_unknown,runtime_classification_missing,runtime_classification_duplicate,runtime_report_failed_head_pass_hash_refresh,runtime_residual_promotion_hash_refresh,collaboration_residual_promotion_hash_refresh,adr0009_runtime_promotion_hash_refresh,adr0008_successful_no_findings_hash_refresh,master_plan_long_distance_failed_head_pass_hash_refresh,displayed_validation_scope_drift,smoke_outside_block_runtime_promotion,smoke_outside_block_failed_head_pass,smoke_failed_head_successful_no_findings,smoke_historical_classification_promotion,smoke_narrative_count_drift,smoke_arbitrary_body_mutation_hash_refresh,smoke_table_cell_actual_hash_mismatch,runtime_thread_cap_mechanism_promotion,runtime_residual_count_stale_five_hash_refresh,runtime_worker_write_mechanism_promotion,status_residual_count_stale_six_hash_refresh
external_audit_transcript=PASS; artifact integrity only; live Codex equivalence NOT_VERIFIED
external_transcript_mutation_rejections=25
graphify_governance=PASS; portable repository policy/snapshot gate only; scheduler runtime NOT_VERIFIED
graphify_governance_mutation_rejections=41
positive_controls=lf_normalized_utf8_crlf_portability,current_c861_pass,failed_c8_and_877,historical_195_pass
Skill is valid!
multi_agent stable true
git diff --check: exit 0, no output
```

The mutation harness operates on disposable system-temporary copies and leaves the Recall worktree unchanged.

## LF-normalized UTF-8 evidence hashes at successor validator checkpoint

| Path | SHA-256 |
|---|---|
| `.agents/skills/recall-collaboration/SKILL.md` | `7AB7CD101DE2BA79D1E7F1620EFB2401C56F5CCAAA449DD2EAA977A9BE9BCD26` |
| `.agents/skills/recall-collaboration/agents/openai.yaml` | `B52DFD3A248F55EFBD6788FB8534F5B43BC75293F7D3E014DFDA48BE661E8086` |
| `.agents/skills/recall-collaboration/references/master-judge-rubric.md` | `A716DCD5E4F64AF62F7B1371DD64A5F4A94311E1C60461B36202B705584E4E53` |
| `AGENTS.md` | `89CE20983DAE96C4BD26914A1F3F3FD6C2FFD6A8E030BF30080C88B4CD61B32C` |
| `CLAUDE.md` | `E7A85809F2ACBAD547DBEF7D7AEBC668FCA299963B5F8336CF0FB19B996F0D77` |
| `.codex/config.toml` | `132C5BD8E8D096C8346D44370A6AF5F27813B011C9E374A15A2288318DD17EB8` |
| `.codex/agents/recall-scout.toml` | `BF722FB460319AF000001065C8B8C23410A247CCD5A5F6103C163FB51C8B82C3` |
| `.codex/agents/recall-worker.toml` | `DAC17C5B48826E8E1955DAB5A601032BEE8A1649F7A69E517242695CB672B827` |
| `.codex/agents/recall-smart-worker.toml` | `D94E650D55C1F48ABCFE92DB74D1C87C6038843CE299E60F22C11D81A7862918` |
| `.codex/agents/recall-master-judge.toml` | `FCA74E78E40BE979D25D4F9A555B72A68503AD92F8C22A94259EB964204EF930` |
| `scripts/validation/verify_recall_collaboration.py` | `66EC0CFCE534F6EE849920E08AAAB8291786BAB228D493930C9C7D9DEF6B60AB` |
| `scripts/validation/test_recall_collaboration_validator.py` | `C90A7D5FB5CB2468A49AFE012FB4B48B9A07F7A07BB9764B6FB53DE678887184` |
| `scripts/validation/verify_external_audit_transcript.py` | `655E6C4C1192EAA2180C8C67799DDF37D0A5836A4871D052F74FDBEA64C70C32` |
| `scripts/validation/test_external_audit_transcript.py` | `7A48C6A28E1B425C2373BD25684B3CA632565E24D73F330844E99436CBB0D2B5` |
| `scripts/validation/verify_graphify_governance.py` | `4EE641234D6062E216E941074688F7B4952AE1C63F40E5CA00D5DCDCD5A55554` |
| `scripts/validation/test_graphify_governance.py` | `18718069E0D887F08179E7B669B328D9A072B44989D06E193E61757FEBE12EE9` |
| `docs/project/COLLABORATION_SYSTEM.md` | `2A5E3B37C0CB6A747E6B61ACC38DC1B186900E04E0F1FC513AB0951CD6BBA53E` |
| `docs/evaluation/reports/2026-08-18--rcl-011-recall-root-runtime.md` | `6F1516C0FF42E0A0ABF7AD3369A30CB4CFE61D67AECF9B90CA250C58C74B058D` |
| `docs/adr/ADR-0008-external-audit-corrections.md` | `9AAF3B1CAC749027FF6D582DAC5C176FF225317DEA4B8DF6057389387E84DE17` |
| `docs/adr/ADR-0009-repo-scoped-codex-collaboration.md` | `C324A8F8E43D9EA88F136D5EAE7496D27E719D8272C5F9FFDEC25AB24EE1C589` |
| `docs/project/MASTER_PLAN.md` | `E84FEDA9B56AE42A32BCE45776A425C5BA225A308FA1C82350A0D4BB4802F9BC` |

Hash mode: `LF_NORMALIZED_UTF8`. Each file is decoded as strict UTF-8, CRLF and lone CR are normalized to LF, and SHA-256 is computed over the normalized UTF-8 bytes. These hashes identify the structurally tested text content. They are not remote, signed, or committed-artifact evidence.

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

- Historical structural configuration and fault-injection validator: `PASS`.
- Custom profile discovery: `REPORT_DERIVED` for Scout, Worker, and Master Judge.
- Inherited read-only fail-closed behavior: `REPORT_DERIVED`.
- Master Judge exact failure behavior: `REPORT_DERIVED`.
- Worker write in a Recall-root workspace: `NOT VERIFIED`.
- Smart Worker runtime profile: `NOT VERIFIED`.
- Effective Judge reasoning effort: `NOT VERIFIED`.
- Three-thread cap and fourth-thread behavior: `NOT VERIFIED`.
- Complete four-role leaf no-spawn: `NOT VERIFIED`.
- Protected owner-operation stop and no protected side effect: `NOT VERIFIED`.

These original runtime rows are historical and are not the current classification source. RCL-011 remains in progress under the seven residual rows in `2026-08-18--rcl-011-recall-root-runtime.md`.
