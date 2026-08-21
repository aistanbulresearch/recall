"""Fault-injection tests for verify_recall_collaboration.py."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from verify_recall_collaboration import (
    CLAIM_DOCUMENT_SHA256,
    HASHED_EVIDENCE_PATHS,
    ROOT,
    validate,
    validate_current_state_contract,
)
from verify_graphify_governance import NORMATIVE_DOCUMENT_SHA256


EXPECTED_MUTATION_REJECTIONS = (
    "unknown_profile_key", "invalid_openai_yaml", "missing_markdown_link",
    "missing_protected_action", "reversed_prohibition_polarity", "unknown_config_key",
    "wrong_duplicate_agent_name", "smoke_classification_promotion",
    "displayed_functional_smoke_promotion", "displayed_classification_count_drift",
    "displayed_thread_cap_runtime_promotion", "displayed_judge_effort_runtime_promotion",
    "leaf_no_spawn_exact_executed_promotion", "leaf_no_spawn_exact_mechanism_promotion",
    "protected_action_exact_executed_promotion",
    "protected_action_exact_mechanism_promotion",
    "leaf_no_spawn_displayed_executed_promotion",
    "leaf_no_spawn_displayed_mechanism_promotion",
    "protected_action_displayed_executed_promotion",
    "protected_action_displayed_mechanism_promotion",
    "collaboration_system_runtime_boundary_drift", "current_state_inverse_machine_value",
    "current_state_predecessor_missing", "current_state_predecessor_duplicate",
    "current_state_unknown_key", "current_state_predecessor_reordered",
    "current_state_predecessor_inverse", "current_predecessor_head_confusion",
    "external_transcript_dependency_mutation", "graphify_governance_dependency_mutation",
    "transcript_probe_deletion_hash_refresh", "graphify_probe_deletion_hash_refresh",
    "current_state_forbidden_stale_insertion", "current_c8_head_then_pass",
    "current_c8_pass_then_head", "predecessor_877_head_then_pass",
    "predecessor_877_pass_then_head", "current_c8_report_head_then_pass",
    "current_c8_report_pass_then_head", "predecessor_877_report_head_then_pass",
    "predecessor_877_report_pass_then_head", "displayed_evidence_hash_count_drift",
    "displayed_evidence_hash_mode_drift", "displayed_transcript_mutation_count_drift",
    "displayed_graphify_mutation_count_drift", "displayed_positive_control_drift",
    "current_c8_passed_variant", "predecessor_877_passed_variant",
    "current_c8_passed_external_audit", "predecessor_877_passed_external_audit",
    "runtime_custom_profile_discovery_demotion",
    "runtime_read_only_fail_closed_promotion",
    "runtime_judge_formatting_demotion", "runtime_worker_write_executed_promotion",
    "runtime_smart_profile_demotion", "runtime_judge_effort_promotion",
    "runtime_thread_cap_demotion", "runtime_leaf_no_spawn_promotion",
    "runtime_protected_stop_promotion", "current_c861_head_reverted",
    "current_c861_pass_reverted", "displayed_aggregate_mutation_count_drift",
    "runtime_classification_unknown", "runtime_classification_missing",
    "runtime_classification_duplicate",
    "runtime_report_failed_head_pass_hash_refresh",
    "runtime_residual_promotion_hash_refresh",
    "collaboration_residual_promotion_hash_refresh",
    "adr0009_runtime_promotion_hash_refresh",
    "adr0008_successful_no_findings_hash_refresh",
    "master_plan_long_distance_failed_head_pass_hash_refresh",
    "displayed_validation_scope_drift",
    "smoke_outside_block_runtime_promotion",
    "smoke_outside_block_failed_head_pass",
    "smoke_failed_head_successful_no_findings",
    "smoke_historical_classification_promotion",
    "smoke_narrative_count_drift",
    "smoke_arbitrary_body_mutation_hash_refresh",
    "smoke_table_cell_actual_hash_mismatch",
    "runtime_thread_cap_mechanism_promotion",
    "runtime_residual_count_stale_five_hash_refresh",
    "runtime_worker_write_mechanism_promotion",
    "status_residual_count_stale_six_hash_refresh",
)


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def isolated_root() -> tempfile.TemporaryDirectory[str]:
    temporary = tempfile.TemporaryDirectory(prefix="recall-collaboration-validator-")
    target = Path(temporary.name)
    shutil.copytree(ROOT / ".agents", target / ".agents")
    shutil.copytree(ROOT / ".codex", target / ".codex")
    shutil.copytree(
        ROOT / "scripts" / "validation",
        target / "scripts" / "validation",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    report_target = target / "docs" / "evaluation" / "reports"
    report_target.mkdir(parents=True)
    shutil.copy2(
        ROOT / "docs" / "evaluation" / "reports" / "2026-08-17--codex-collaboration-smoke.md",
        report_target / "2026-08-17--codex-collaboration-smoke.md",
    )
    shutil.copy2(
        ROOT
        / "docs"
        / "evaluation"
        / "reports"
        / "2026-08-18--rcl-011-recall-root-runtime.md",
        report_target / "2026-08-18--rcl-011-recall-root-runtime.md",
    )
    adr_target = target / "docs" / "adr"
    adr_target.mkdir(parents=True)
    shutil.copy2(
        ROOT / "docs" / "adr" / "ADR-0009-repo-scoped-codex-collaboration.md",
        adr_target / "ADR-0009-repo-scoped-codex-collaboration.md",
    )
    shutil.copy2(
        ROOT / "docs" / "adr" / "ADR-0008-external-audit-corrections.md",
        adr_target / "ADR-0008-external-audit-corrections.md",
    )
    project_target = target / "docs" / "project"
    project_target.mkdir(parents=True)
    for filename in ("STATUS.md", "MASTER_PLAN.md", "HANDOFF.md", "COLLABORATION_SYSTEM.md"):
        shutil.copy2(ROOT / "docs" / "project" / filename, project_target / filename)
    shutil.copy2(ROOT / "AGENTS.md", target / "AGENTS.md")
    shutil.copy2(ROOT / "CLAUDE.md", target / "CLAUDE.md")
    transcript_target = target / "docs" / "evaluation" / "transcripts"
    transcript_target.mkdir(parents=True)
    shutil.copy2(
        ROOT
        / "docs"
        / "evaluation"
        / "transcripts"
        / "2026-08-18--github-auditor-collaboration-fail-source-final.md",
        transcript_target
        / "2026-08-18--github-auditor-collaboration-fail-source-final.md",
    )
    shutil.copy2(
        ROOT
        / "docs"
        / "evaluation"
        / "reports"
        / "2026-08-18--github-auditor-collaboration-fail.md",
        report_target / "2026-08-18--github-auditor-collaboration-fail.md",
    )
    return temporary


def expect_rejection(
    label: str,
    mutate: Callable[[Path], None],
    expected_error: str,
) -> str:
    with isolated_root() as directory:
        root = Path(directory)
        original_claim_hashes = CLAIM_DOCUMENT_SHA256.copy()
        original_normative_hashes = NORMATIVE_DOCUMENT_SHA256.copy()
        try:
            mutate(root)
            try:
                validate(root)
            except ValueError as exc:
                message = str(exc)
                if expected_error not in message:
                    raise AssertionError(f"{label}:wrong_error:{message}") from exc
                return label
            raise AssertionError(f"{label}:mutation_not_rejected")
        finally:
            CLAIM_DOCUMENT_SHA256.clear()
            CLAIM_DOCUMENT_SHA256.update(original_claim_hashes)
            NORMATIVE_DOCUMENT_SHA256.clear()
            NORMATIVE_DOCUMENT_SHA256.update(original_normative_hashes)


def refresh_evidence_hash(root: Path, relative_path: str) -> None:
    import hashlib
    import re

    target = root / relative_path
    normalized = (
        target.read_bytes()
        .decode("utf-8")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .encode("utf-8")
    )
    new_hash = hashlib.sha256(normalized).hexdigest().upper()
    report_path = (
        root / "docs" / "evaluation" / "reports" / "2026-08-17--codex-collaboration-smoke.md"
    )
    report = report_path.read_text(encoding="utf-8")
    tick = chr(96)
    pattern = re.compile(
        re.escape(f"| {tick}{relative_path}{tick} | {tick}") + r"[0-9A-F]{64}" + re.escape(f"{tick} |")
    )
    replacement = f"| {tick}{relative_path}{tick} | {tick}{new_hash}{tick} |"
    updated, count = pattern.subn(replacement, report)
    if count != 1:
        raise AssertionError(f"evidence_hash_row_not_unique:{relative_path}:{count}")
    write_text(report_path, updated)


def refresh_claim_document_hash(root: Path, relative_path: str) -> None:
    import hashlib

    target = root / relative_path
    normalized = (
        target.read_bytes()
        .decode("utf-8")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .encode("utf-8")
    )
    new_hash = hashlib.sha256(normalized).hexdigest().upper()
    old_hash = CLAIM_DOCUMENT_SHA256[relative_path]
    verifier_path = root / "scripts" / "validation" / "verify_recall_collaboration.py"
    verifier = verifier_path.read_text(encoding="utf-8")
    if verifier.count(old_hash) != 1:
        raise AssertionError(
            f"claim_hash_source_target_count:{relative_path}:{verifier.count(old_hash)}"
        )
    write_text(verifier_path, verifier.replace(old_hash, new_hash))
    CLAIM_DOCUMENT_SHA256[relative_path] = new_hash
    refresh_evidence_hash(root, "scripts/validation/verify_recall_collaboration.py")


def refresh_graphify_normative_hash(root: Path, relative_path: str) -> None:
    import hashlib

    target = root / relative_path
    normalized = (
        target.read_bytes()
        .decode("utf-8")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .encode("utf-8")
    )
    new_hash = hashlib.sha256(normalized).hexdigest().upper()
    old_hash = NORMATIVE_DOCUMENT_SHA256[relative_path]
    verifier_relative_path = "scripts/validation/verify_graphify_governance.py"
    verifier_path = root / verifier_relative_path
    verifier = verifier_path.read_text(encoding="utf-8")
    if verifier.count(old_hash) != 1:
        raise AssertionError(
            f"normative_hash_source_target_count:{relative_path}:{verifier.count(old_hash)}"
        )
    write_text(verifier_path, verifier.replace(old_hash, new_hash))
    NORMATIVE_DOCUMENT_SHA256[relative_path] = new_hash
    refresh_evidence_hash(root, verifier_relative_path)


def main() -> None:
    runtime_report = (
        ROOT
        / "docs"
        / "evaluation"
        / "reports"
        / "2026-08-18--rcl-011-recall-root-runtime.md"
    )
    if not runtime_report.is_file():
        raise AssertionError("runtime_report_missing")
    clean = validate(ROOT)
    if clean["status"] != "PASS":
        raise AssertionError("clean_validation_failed")

    rejected = []
    rejected.append(
        expect_rejection(
            "unknown_profile_key",
            lambda root: write_text(
                root / ".codex" / "agents" / "recall-master-judge.toml",
                (root / ".codex" / "agents" / "recall-master-judge.toml").read_text(encoding="utf-8")
                + '\nmodel_reasoning_effrot = "max"\n',
            ),
            "key_set_invalid",
        )
    )
    rejected.append(
        expect_rejection(
            "invalid_openai_yaml",
            lambda root: write_text(
                root / ".agents" / "skills" / "recall-collaboration" / "agents" / "openai.yaml",
                'interface:\n  display_name: "Recall Collaboration\n',
            ),
            "openai_yaml:line_2_invalid",
        )
    )
    rejected.append(
        expect_rejection(
            "missing_markdown_link",
            lambda root: write_text(
                root / ".agents" / "skills" / "recall-collaboration" / "SKILL.md",
                (root / ".agents" / "skills" / "recall-collaboration" / "SKILL.md")
                .read_text(encoding="utf-8")
                .replace("references/master-judge-rubric.md", "references/missing.md"),
            ),
            "markdown_link_missing",
        )
    )
    rejected.append(
        expect_rejection(
            "missing_protected_action",
            lambda root: write_text(
                root / ".codex" / "agents" / "recall-worker.toml",
                (root / ".codex" / "agents" / "recall-worker.toml")
                .read_text(encoding="utf-8")
                .replace("Do not perform destructive actions.", "Do not perform unsafe operations."),
            ),
            "protected_clause_missing:do not perform destructive actions.",
        )
    )
    def reverse_polarity(root: Path) -> None:
        relative_path = ".codex/agents/recall-worker.toml"
        profile_path = root / relative_path
        write_text(
            profile_path,
            profile_path.read_text(encoding="utf-8").replace(
                "Do not perform destructive actions.", "Perform destructive actions."
            ),
        )
        refresh_evidence_hash(root, relative_path)

    rejected.append(
        expect_rejection(
            "reversed_prohibition_polarity",
            reverse_polarity,
            "protected_clause_missing:do not perform destructive actions.",
        )
    )
    rejected.append(
        expect_rejection(
            "unknown_config_key",
            lambda root: write_text(
                root / ".codex" / "config.toml",
                (root / ".codex" / "config.toml").read_text(encoding="utf-8")
                + "\nmax_threads_typo = 9\n",
            ),
            "agents_keys_invalid",
        )
    )

    def duplicate_stable_agent_name(root: Path) -> None:
        relative_path = ".codex/agents/recall-scout.toml"
        profile_path = root / relative_path
        write_text(
            profile_path,
            profile_path.read_text(encoding="utf-8").replace(
                'name = "recall-scout"', 'name = "recall-worker"'
            ),
        )
        refresh_evidence_hash(root, relative_path)

    rejected.append(
        expect_rejection(
            "wrong_duplicate_agent_name",
            duplicate_stable_agent_name,
            "recall-scout.toml:name_invalid",
        )
    )

    def promote_report_derived_to_executed(root: Path) -> None:
        report_path = (
            root
            / "docs"
            / "evaluation"
            / "reports"
            / "2026-08-18--rcl-011-recall-root-runtime.md"
        )
        write_text(
            report_path,
            report_path.read_text(encoding="utf-8").replace(
                "- Custom profile discovery: `EXECUTED`",
                "- Custom profile discovery: `REPORT_DERIVED`",
            ),
        )

    rejected.append(
        expect_rejection(
            "smoke_classification_promotion",
            promote_report_derived_to_executed,
            "smoke_classification_mismatch:Custom profile discovery:REPORT_DERIVED:EXECUTED",
        )
    )

    def promote_displayed_functional_smoke(root: Path) -> None:
        report_path = (
            root
            / "docs"
            / "evaluation"
            / "reports"
            / "2026-08-18--rcl-011-recall-root-runtime.md"
        )
        write_text(
            report_path,
            report_path.read_text(encoding="utf-8").replace(
                "functional_smoke=PARTIAL_FAIL_CLOSED",
                "functional_smoke=MECHANISM_PROVED",
            ),
        )

    rejected.append(
        expect_rejection(
            "displayed_functional_smoke_promotion",
            promote_displayed_functional_smoke,
            "smoke_summary_functional_mismatch:MECHANISM_PROVED:PARTIAL_FAIL_CLOSED",
        )
    )

    def drift_displayed_classification_counts(root: Path) -> None:
        report_path = (
            root
            / "docs"
            / "evaluation"
            / "reports"
            / "2026-08-18--rcl-011-recall-root-runtime.md"
        )
        write_text(
            report_path,
            report_path.read_text(encoding="utf-8").replace(
                "runtime_evidence_classifications=0 MECHANISM_PROVED,2 EXECUTED,7 NOT VERIFIED",
                "runtime_evidence_classifications=1 MECHANISM_PROVED,2 EXECUTED,6 NOT VERIFIED",
            ),
        )

    rejected.append(
        expect_rejection(
            "displayed_classification_count_drift",
            drift_displayed_classification_counts,
            "smoke_summary_counts_mismatch:1 MECHANISM_PROVED,2 EXECUTED,6 NOT VERIFIED:0 MECHANISM_PROVED,2 EXECUTED,7 NOT VERIFIED",
        )
    )

    def promote_displayed_thread_cap_runtime(root: Path) -> None:
        report_path = (
            root
            / "docs"
            / "evaluation"
            / "reports"
            / "2026-08-18--rcl-011-recall-root-runtime.md"
        )
        write_text(
            report_path,
            report_path.read_text(encoding="utf-8").replace(
                "thread_cap_runtime=NOT_VERIFIED",
                "thread_cap_runtime=EXECUTED",
            ),
        )

    rejected.append(
        expect_rejection(
            "displayed_thread_cap_runtime_promotion",
            promote_displayed_thread_cap_runtime,
            "smoke_summary_classification_mismatch:thread_cap_runtime:EXECUTED:NOT_VERIFIED",
        )
    )

    def promote_displayed_judge_effort_runtime(root: Path) -> None:
        report_path = (
            root
            / "docs"
            / "evaluation"
            / "reports"
            / "2026-08-18--rcl-011-recall-root-runtime.md"
        )
        write_text(
            report_path,
            report_path.read_text(encoding="utf-8").replace(
                "judge_effective_effort_runtime=NOT_VERIFIED",
                "judge_effective_effort_runtime=EXECUTED",
            ),
        )

    rejected.append(
        expect_rejection(
            "displayed_judge_effort_runtime_promotion",
            promote_displayed_judge_effort_runtime,
            "smoke_summary_classification_mismatch:judge_effective_effort_runtime:EXECUTED:NOT_VERIFIED",
        )
    )

    report_relative_path = (
        "docs/evaluation/reports/2026-08-18--rcl-011-recall-root-runtime.md"
    )

    def replace_report_text(old: str, new: str) -> Callable[[Path], None]:
        def mutate(root: Path) -> None:
            report_path = root / report_relative_path
            source = report_path.read_text(encoding="utf-8")
            if source.count(old) != 1:
                raise AssertionError(f"report_mutation_target_count:{old}:{source.count(old)}")
            write_text(report_path, source.replace(old, new))

        return mutate

    p1_exact_promotions = (
        (
            "leaf_no_spawn_exact_executed_promotion",
            "- Complete four-role leaf no-spawn: `NOT VERIFIED`",
            "- Complete four-role leaf no-spawn: `NOT VERIFIED`. `EXECUTED`",
            "smoke_classification_line_invalid:Complete four-role leaf no-spawn",
        ),
        (
            "leaf_no_spawn_exact_mechanism_promotion",
            "- Complete four-role leaf no-spawn: `NOT VERIFIED`",
            "- Complete four-role leaf no-spawn: `NOT VERIFIED`. `MECHANISM_PROVED`",
            "smoke_classification_line_invalid:Complete four-role leaf no-spawn",
        ),
        (
            "protected_action_exact_executed_promotion",
            "- Protected owner-operation stop and no protected side effect: `NOT VERIFIED`",
            "- Protected owner-operation stop and no protected side effect: `NOT VERIFIED`. `EXECUTED`",
            "smoke_classification_line_invalid:Protected owner-operation stop and no protected side effect",
        ),
        (
            "protected_action_exact_mechanism_promotion",
            "- Protected owner-operation stop and no protected side effect: `NOT VERIFIED`",
            "- Protected owner-operation stop and no protected side effect: `NOT VERIFIED`. `MECHANISM_PROVED`",
            "smoke_classification_line_invalid:Protected owner-operation stop and no protected side effect",
        ),
    )
    for label, old, new, expected_error in p1_exact_promotions:
        rejected.append(
            expect_rejection(label, replace_report_text(old, new), expected_error)
        )

    p1_displayed_promotions = (
        (
            "leaf_no_spawn_displayed_executed_promotion",
            "complete_four_role_leaf_no_spawn_runtime=NOT_VERIFIED",
            "complete_four_role_leaf_no_spawn_runtime=NOT_VERIFIED EXECUTED",
            "smoke_summary_classification_mismatch:complete_four_role_leaf_no_spawn_runtime:NOT_VERIFIED EXECUTED:NOT_VERIFIED",
        ),
        (
            "leaf_no_spawn_displayed_mechanism_promotion",
            "complete_four_role_leaf_no_spawn_runtime=NOT_VERIFIED",
            "complete_four_role_leaf_no_spawn_runtime=NOT_VERIFIED MECHANISM_PROVED",
            "smoke_summary_classification_mismatch:complete_four_role_leaf_no_spawn_runtime:NOT_VERIFIED MECHANISM_PROVED:NOT_VERIFIED",
        ),
        (
            "protected_action_displayed_executed_promotion",
            "protected_action_stop_runtime=NOT_VERIFIED",
            "protected_action_stop_runtime=NOT_VERIFIED EXECUTED",
            "smoke_summary_classification_mismatch:protected_action_stop_runtime:NOT_VERIFIED EXECUTED:NOT_VERIFIED",
        ),
        (
            "protected_action_displayed_mechanism_promotion",
            "protected_action_stop_runtime=NOT_VERIFIED",
            "protected_action_stop_runtime=NOT_VERIFIED MECHANISM_PROVED",
            "smoke_summary_classification_mismatch:protected_action_stop_runtime:NOT_VERIFIED MECHANISM_PROVED:NOT_VERIFIED",
        ),
    )
    for label, old, new, expected_error in p1_displayed_promotions:
        rejected.append(
            expect_rejection(label, replace_report_text(old, new), expected_error)
        )

    def contradict_collaboration_runtime_boundary(root: Path) -> None:
        relative_path = "docs/project/COLLABORATION_SYSTEM.md"
        target = root / relative_path
        source = target.read_text(encoding="utf-8")
        required = "Complete four-role leaf no-spawn: `NOT VERIFIED`."
        if source.count(required) != 1:
            raise AssertionError(
                f"collaboration_boundary_mutation_target_count:{source.count(required)}"
            )
        contradictory = required + "\n- Complete four-role leaf no-spawn: `EXECUTED`."
        write_text(target, source.replace(required, contradictory))
        refresh_evidence_hash(root, relative_path)

    rejected.append(
        expect_rejection(
            "collaboration_system_runtime_boundary_drift",
            contradict_collaboration_runtime_boundary,
            "collaboration_classification_count:Complete four-role leaf no-spawn:2",
        )
    )

    def invert_current_state_required_fact(root: Path) -> None:
        target = root / "docs" / "adr" / "ADR-0008-external-audit-corrections.md"
        source = target.read_text(encoding="utf-8")
        write_text(
            target,
            source.replace(
                "current_external_audit_verdict=PASS",
                "current_external_audit_verdict=FAIL",
            ),
        )

    rejected.append(
        expect_rejection(
            "current_state_inverse_machine_value",
            invert_current_state_required_fact,
            "current_state_value_mismatch:docs/adr/ADR-0008-external-audit-corrections.md:current_external_audit_verdict:FAIL:PASS",
        )
    )

    state_path = "docs/adr/ADR-0008-external-audit-corrections.md"

    def mutate_state_block(old: str, new: str) -> Callable[[Path], None]:
        def mutate(root: Path) -> None:
            target = root / state_path
            source = target.read_text(encoding="utf-8")
            if source.count(old) != 1:
                raise AssertionError(f"state_mutation_target_count:{old}:{source.count(old)}")
            write_text(target, source.replace(old, new))

        return mutate

    new_state_mutations = (
        (
            "current_state_predecessor_missing",
            "audited_predecessor_head=877c78d06d9b78f3071d17c81232fbc4302f857e\n",
            "",
            "current_state_missing_keys",
        ),
        (
            "current_state_predecessor_duplicate",
            "audited_predecessor_head=877c78d06d9b78f3071d17c81232fbc4302f857e",
            "audited_predecessor_head=877c78d06d9b78f3071d17c81232fbc4302f857e\naudited_predecessor_head=877c78d06d9b78f3071d17c81232fbc4302f857e",
            "current_state_duplicate_key",
        ),
        (
            "current_state_unknown_key",
            "audited_predecessor_head=877c78d06d9b78f3071d17c81232fbc4302f857e",
            "audited_predecessor_head=877c78d06d9b78f3071d17c81232fbc4302f857e\nunknown_gate=FAIL",
            "current_state_unknown_key",
        ),
        (
            "current_state_predecessor_reordered",
            "current_external_audit_verdict=PASS\naudited_predecessor_head=877c78d06d9b78f3071d17c81232fbc4302f857e",
            "audited_predecessor_head=877c78d06d9b78f3071d17c81232fbc4302f857e\ncurrent_external_audit_verdict=PASS",
            "current_state_block_format_mismatch",
        ),
        (
            "current_state_predecessor_inverse",
            "audited_predecessor_head=877c78d06d9b78f3071d17c81232fbc4302f857e",
            "audited_predecessor_head=195422e4d762d68d38e2b7f531cc5b1cd059cdb7",
            "current_state_value_mismatch",
        ),
        (
            "current_predecessor_head_confusion",
            "current_external_audit_head=c86139048d1532c79ed190d0cc98ce2ad878414b",
            "current_external_audit_head=877c78d06d9b78f3071d17c81232fbc4302f857e",
            "current_state_value_mismatch",
        ),
    )
    for label, old, new, error in new_state_mutations:
        rejected.append(expect_rejection(label, mutate_state_block(old, new), error))

    def mutate_transcript_dependency(root: Path) -> None:
        target = (
            root
            / "docs"
            / "evaluation"
            / "transcripts"
            / "2026-08-18--github-auditor-collaboration-fail-source-final.md"
        )
        source = target.read_text(encoding="utf-8")
        write_text(target, source.replace("FAIL\n\n## Findings", "PASS\n\n## Findings", 1))

    rejected.append(
        expect_rejection(
            "external_transcript_dependency_mutation",
            mutate_transcript_dependency,
            "transcript_body_hash_mismatch",
        )
    )

    rejected.append(
        expect_rejection(
            "graphify_governance_dependency_mutation",
            lambda root: write_text(
                root / "CLAUDE.md",
                (root / "CLAUDE.md").read_text(encoding="utf-8").replace(
                    "every two hours", "every three hours", 1
                ),
            ),
            "graphify_policy_drift",
        )
    )

    def delete_probe_and_refresh(
        root: Path, relative_path: str, marker: str
    ) -> None:
        target = root / relative_path
        lines = target.read_text(encoding="utf-8").splitlines()
        matches = [index for index, line in enumerate(lines) if marker in line]
        if len(matches) != 1:
            raise AssertionError(f"probe_deletion_target_count:{relative_path}:{len(matches)}")
        del lines[matches[0]]
        write_text(target, "\n".join(lines) + "\n")
        refresh_evidence_hash(root, relative_path)

    rejected.append(
        expect_rejection(
            "transcript_probe_deletion_hash_refresh",
            lambda root: delete_probe_and_refresh(
                root,
                "scripts/validation/test_external_audit_transcript.py",
                '("body_byte_addition", TRANSCRIPT_PATH,',
            ),
            "mutation_probe_labels_mismatch:scripts/validation/test_external_audit_transcript.py",
        )
    )
    rejected.append(
        expect_rejection(
            "graphify_probe_deletion_hash_refresh",
            lambda root: delete_probe_and_refresh(
                root,
                "scripts/validation/test_graphify_governance.py",
                '("policy_drift", replace(',
            ),
            "mutation_probe_labels_mismatch:scripts/validation/test_graphify_governance.py",
        )
    )

    historical_head = "195422e4d762d68d38e2b7f531cc5b1cd059cdb7"

    def append_status_line(line: str) -> Callable[[Path], None]:
        def mutate(root: Path) -> None:
            target = root / "docs" / "project" / "STATUS.md"
            source = target.read_text(encoding="utf-8")
            write_text(target, source + f"\n{line}\n")

        return mutate

    stale_pass_probes = (
        (
            "composite_unqualified",
            f"Historical external audit: PASS at {historical_head}; External audit: PASS",
        ),
        (
            "composite_final",
            f"Earlier external audit: PASS at {historical_head}; "
            "The final exact-head GitHub auditor re-review returned PASS",
        ),
        ("standalone_unqualified", "External audit: PASS"),
        (
            "standalone_final",
            "The final exact-head GitHub auditor re-review returned PASS",
        ),
        ("historical_missing_head", "Historical external audit: PASS"),
        (
            "current_c8_exact_head_pass",
            "External audit: PASS at c8be19476c24672fbf65d4dbf767fa8144360d22",
        ),
        (
            "predecessor_877_pass",
            "Audited predecessor 877c78d06d9b78f3071d17c81232fbc4302f857e: PASS",
        ),
    )
    for probe, line in stale_pass_probes:
        expect_rejection(
            f"current_state_forbidden_stale_insertion:{probe}",
            append_status_line(line),
            "current_state_forbidden:docs/project/STATUS.md:unqualified_current_pass",
        )

    with isolated_root() as directory:
        root = Path(directory)
        append_status_line(
            f"Historical external audit: PASS at {historical_head}"
        )(root)
        validate_current_state_contract(root)

    with isolated_root() as directory:
        root = Path(directory)
        portability_targets = (
            root
            / ".agents"
            / "skills"
            / "recall-collaboration"
            / "agents"
            / "openai.yaml",
            root
            / "docs"
            / "evaluation"
            / "reports"
            / "2026-08-17--codex-collaboration-smoke.md",
        )
        for portability_target in portability_targets:
            normalized = (
                portability_target.read_bytes()
                .decode("utf-8")
                .replace("\r\n", "\n")
                .replace("\r", "\n")
            )
            portability_target.write_bytes(
                normalized.replace("\n", "\r\n").encode("utf-8")
            )
        portability_result = validate(root)
        if portability_result["status"] != "PASS":
            raise AssertionError("lf_normalized_utf8_crlf_portability_failed")

    rejected.append("current_state_forbidden_stale_insertion")

    ordered_failed_head_probes = (
        (
            "current_c8_head_then_pass",
            "c8be19476c24672fbf65d4dbf767fa8144360d22: PASS",
        ),
        (
            "current_c8_pass_then_head",
            "PASS at c8be19476c24672fbf65d4dbf767fa8144360d22",
        ),
        (
            "predecessor_877_head_then_pass",
            "Audited predecessor 877c78d06d9b78f3071d17c81232fbc4302f857e: PASS",
        ),
        (
            "predecessor_877_pass_then_head",
            "PASS at audited predecessor 877c78d06d9b78f3071d17c81232fbc4302f857e",
        ),
    )
    for label, contradiction in ordered_failed_head_probes:
        rejected.append(
            expect_rejection(
                label,
                append_status_line(
                    f"Historical external audit: PASS at {historical_head}; {contradiction}"
                ),
                "current_state_forbidden:docs/project/STATUS.md:unqualified_current_pass",
            )
        )

    report_head_probes = (
        ("current_c8_report_head_then_pass", "c8be1947: PASS"),
        ("current_c8_report_pass_then_head", "PASS - c8be1947"),
        ("predecessor_877_report_head_then_pass", "877c78d0: PASS"),
        ("predecessor_877_report_pass_then_head", "PASS - 877c78d0"),
    )
    for label, contradiction in report_head_probes:
        rejected.append(
            expect_rejection(
                label,
                append_status_line(
                    f"Historical external audit: PASS at {historical_head}; {contradiction}"
                ),
                "current_state_forbidden:docs/project/STATUS.md:unqualified_current_pass",
            )
        )

    report_head_auxiliary_probes = (
        ("c8be1947", "PASS at c8be1947"),
        ("c8be1947", "c8be1947 returned PASS"),
        ("c8be1947", "c8be1947 audit: PASS"),
        ("877c78d0", "PASS at 877c78d0"),
        ("877c78d0", "877c78d0 returned PASS"),
        ("877c78d0", "877c78d0 audit: PASS"),
    )
    for reference, contradiction in report_head_auxiliary_probes:
        expect_rejection(
            f"failed_report_head_auxiliary:{reference}:{contradiction}",
            append_status_line(
                f"Historical external audit: PASS at {historical_head}; {contradiction}"
            ),
            "current_state_forbidden:docs/project/STATUS.md:unqualified_current_pass",
        )

    displayed_contract_mutations = (
        (
            "displayed_evidence_hash_count_drift",
            "evidence_hashes_verified=21",
            "evidence_hashes_verified=20",
            "smoke_summary_classification_mismatch:evidence_hashes_verified:20:21",
        ),
        (
            "displayed_evidence_hash_mode_drift",
            "evidence_hash_mode=LF_NORMALIZED_UTF8",
            "evidence_hash_mode=RAW_BYTES",
            "smoke_summary_classification_mismatch:evidence_hash_mode:RAW_BYTES:LF_NORMALIZED_UTF8",
        ),
        (
            "displayed_transcript_mutation_count_drift",
            "external_transcript_mutation_rejections=25",
            "external_transcript_mutation_rejections=24",
            "smoke_summary_classification_mismatch:external_transcript_mutation_rejections:24:25",
        ),
        (
            "displayed_graphify_mutation_count_drift",
            "graphify_governance_mutation_rejections=41",
            "graphify_governance_mutation_rejections=40",
            "smoke_summary_classification_mismatch:graphify_governance_mutation_rejections:40:41",
        ),
        (
            "displayed_positive_control_drift",
            "positive_controls=lf_normalized_utf8_crlf_portability,current_c861_pass,failed_c8_and_877,historical_195_pass",
            "positive_controls=none",
            "smoke_summary_classification_mismatch:positive_controls:none:lf_normalized_utf8_crlf_portability,current_c861_pass,failed_c8_and_877,historical_195_pass",
        ),
    )
    for label, old, new, error in displayed_contract_mutations:
        rejected.append(expect_rejection(label, replace_report_text(old, new), error))

    pass_variant_probes = (
        (
            "current_c8_passed_variant",
            "c8be19476c24672fbf65d4dbf767fa8144360d22 — PASSED",
        ),
        (
            "predecessor_877_passed_variant",
            "PASSED at 877c78d06d9b78f3071d17c81232fbc4302f857e",
        ),
        (
            "current_c8_passed_external_audit",
            "c8be19476c24672fbf65d4dbf767fa8144360d22 passed the external audit",
        ),
        (
            "predecessor_877_passed_external_audit",
            "Passed the external audit at 877c78d06d9b78f3071d17c81232fbc4302f857e",
        ),
    )
    for label, contradiction in pass_variant_probes:
        rejected.append(
            expect_rejection(
                label,
                append_status_line(
                    f"Historical external audit: PASS at {historical_head}; {contradiction}"
                ),
                "current_state_forbidden:docs/project/STATUS.md:unqualified_current_pass",
            )
        )

    runtime_classification_mutations = (
        (
            "runtime_custom_profile_discovery_demotion",
            "Custom profile discovery", "EXECUTED", "REPORT_DERIVED",
        ),
        (
            "runtime_read_only_fail_closed_promotion",
            "Inherited read-only fail-closed behavior", "NOT VERIFIED", "EXECUTED",
        ),
        (
            "runtime_judge_formatting_demotion",
            "Master Judge verdict formatting", "EXECUTED", "REPORT_DERIVED",
        ),
        (
            "runtime_worker_write_executed_promotion",
            "Worker write in a Recall-root workspace", "NOT VERIFIED", "EXECUTED",
        ),
        (
            "runtime_smart_profile_demotion",
            "Smart Worker runtime profile", "NOT VERIFIED", "EXECUTED",
        ),
        (
            "runtime_judge_effort_promotion",
            "Effective Judge reasoning effort", "NOT VERIFIED", "EXECUTED",
        ),
        (
            "runtime_thread_cap_demotion",
            "Three-thread cap and fourth-thread behavior", "NOT VERIFIED", "EXECUTED",
        ),
        (
            "runtime_leaf_no_spawn_promotion",
            "Complete four-role leaf no-spawn", "NOT VERIFIED", "EXECUTED",
        ),
        (
            "runtime_protected_stop_promotion",
            "Protected owner-operation stop and no protected side effect",
            "NOT VERIFIED", "EXECUTED",
        ),
    )
    for label, classification, expected, mutated in runtime_classification_mutations:
        rejected.append(
            expect_rejection(
                label,
                replace_report_text(
                    f"- {classification}: `{expected}`.",
                    f"- {classification}: `{mutated}`.",
                ),
                f"smoke_classification_mismatch:{classification}:{mutated}:{expected}",
            )
        )

    rejected.append(
        expect_rejection(
            "current_c861_head_reverted",
            mutate_state_block(
                "current_external_audit_head=c86139048d1532c79ed190d0cc98ce2ad878414b",
                "current_external_audit_head=c8be19476c24672fbf65d4dbf767fa8144360d22",
            ),
            "current_state_value_mismatch:docs/adr/ADR-0008-external-audit-corrections.md:current_external_audit_head",
        )
    )
    rejected.append(
        expect_rejection(
            "current_c861_pass_reverted",
            mutate_state_block(
                "current_external_audit_verdict=PASS",
                "current_external_audit_verdict=FAIL",
            ),
            "current_state_value_mismatch:docs/adr/ADR-0008-external-audit-corrections.md:current_external_audit_verdict",
        )
    )
    rejected.append(
        expect_rejection(
            "displayed_aggregate_mutation_count_drift",
            replace_report_text(
                "aggregate_collaboration_mutation_rejections=83",
                "aggregate_collaboration_mutation_rejections=82",
            ),
            "smoke_summary_classification_mismatch:aggregate_collaboration_mutation_rejections:82:83",
        )
    )
    rejected.append(
        expect_rejection(
            "runtime_classification_unknown",
            replace_report_text(
                "- Custom profile discovery: `EXECUTED`.",
                "- Custom profile discovery: `EXECUTED`.\n- Unexpected runtime surface: `EXECUTED`.",
            ),
            "smoke_classification_unknown_label",
        )
    )
    rejected.append(
        expect_rejection(
            "runtime_classification_missing",
            replace_report_text(
                "- Smart Worker runtime profile: `NOT VERIFIED`.\n",
                "",
            ),
            "smoke_classification_missing_labels",
        )
    )
    rejected.append(
        expect_rejection(
            "runtime_classification_duplicate",
            replace_report_text(
                "- Master Judge verdict formatting: `EXECUTED`.",
                "- Master Judge verdict formatting: `EXECUTED`.\n- Master Judge verdict formatting: `EXECUTED`.",
            ),
            "smoke_classification_duplicate_label:Master Judge verdict formatting",
        )
    )

    def append_claim_and_refresh(relative_path: str, line: str) -> Callable[[Path], None]:
        def mutate(root: Path) -> None:
            target = root / relative_path
            write_text(target, target.read_text(encoding="utf-8") + f"\n{line}\n")
            refresh_evidence_hash(root, relative_path)

        return mutate

    rejected.append(
        expect_rejection(
            "runtime_report_failed_head_pass_hash_refresh",
            append_claim_and_refresh(
                report_relative_path,
                "The c8be19476c24672fbf65d4dbf767fa8144360d22 external audit returned PASS.",
            ),
            f"claim_document_hash_mismatch:{report_relative_path}",
        )
    )

    def promote_runtime_residual_and_refresh(root: Path) -> None:
        target = root / report_relative_path
        old = "Those seven residual rows remain fail-closed `NOT VERIFIED`."
        new = "Those seven residual rows are now `EXECUTED`."
        source = target.read_text(encoding="utf-8")
        if source.count(old) != 1:
            raise AssertionError(f"runtime_residual_target_count:{source.count(old)}")
        write_text(target, source.replace(old, new))
        refresh_evidence_hash(root, report_relative_path)

    rejected.append(
        expect_rejection(
            "runtime_residual_promotion_hash_refresh",
            promote_runtime_residual_and_refresh,
            f"claim_document_hash_mismatch:{report_relative_path}",
        )
    )

    collaboration_path = "docs/project/COLLABORATION_SYSTEM.md"
    rejected.append(
        expect_rejection(
            "collaboration_residual_promotion_hash_refresh",
            append_claim_and_refresh(
                collaboration_path,
                "The inherited read-only fail-closed mechanism is now EXECUTED.",
            ),
            f"claim_document_hash_mismatch:{collaboration_path}",
        )
    )

    adr0009_path = "docs/adr/ADR-0009-repo-scoped-codex-collaboration.md"
    rejected.append(
        expect_rejection(
            "adr0009_runtime_promotion_hash_refresh",
            append_claim_and_refresh(
                adr0009_path,
                "The Smart Worker runtime profile is now EXECUTED.",
            ),
            f"claim_document_hash_mismatch:{adr0009_path}",
        )
    )

    adr0008_path = "docs/adr/ADR-0008-external-audit-corrections.md"
    rejected.append(
        expect_rejection(
            "adr0008_successful_no_findings_hash_refresh",
            append_claim_and_refresh(
                adr0008_path,
                "The c8be19476c24672fbf65d4dbf767fa8144360d22 review was successful with no findings.",
            ),
            f"claim_document_hash_mismatch:{adr0008_path}",
        )
    )

    master_plan_path = "docs/project/MASTER_PLAN.md"
    rejected.append(
        expect_rejection(
            "master_plan_long_distance_failed_head_pass_hash_refresh",
            append_claim_and_refresh(
                master_plan_path,
                "c8be19476c24672fbf65d4dbf767fa8144360d22 was assessed after a deliberately "
                "long explanatory separation that exceeds the semantic proximity guard and "
                "the final verdict was PASS.",
            ),
            f"claim_document_hash_mismatch:{master_plan_path}",
        )
    )

    smoke_manifest_path = (
        "docs/evaluation/reports/2026-08-17--codex-collaboration-smoke.md"
    )

    def drift_displayed_validation_scope(root: Path) -> None:
        target = root / smoke_manifest_path
        source = target.read_text(encoding="utf-8")
        old = "validation_scope=STRUCTURAL_PLUS_BOUNDED_RUNTIME_EVIDENCE"
        if source.count(old) != 1:
            raise AssertionError(f"validation_scope_target_count:{source.count(old)}")
        write_text(target, source.replace(old, "validation_scope=STRUCTURAL"))

    rejected.append(
        expect_rejection(
            "displayed_validation_scope_drift",
            drift_displayed_validation_scope,
            "manifest_summary_value_mismatch:validation_scope:STRUCTURAL:"
            "STRUCTURAL_PLUS_BOUNDED_RUNTIME_EVIDENCE",
        )
    )

    def append_smoke_body(line: str, refresh_hashes: bool = False) -> Callable[[Path], None]:
        def mutate(root: Path) -> None:
            target = root / smoke_manifest_path
            write_text(target, target.read_text(encoding="utf-8") + f"\n{line}\n")
            if refresh_hashes:
                for relative_path in sorted(HASHED_EVIDENCE_PATHS):
                    refresh_evidence_hash(root, relative_path)

        return mutate

    canonical_hash_error = "smoke_manifest_canonical_hash_mismatch"
    rejected.append(
        expect_rejection(
            "smoke_outside_block_runtime_promotion",
            append_smoke_body("Current Smart Worker runtime profile: EXECUTED."),
            canonical_hash_error,
        )
    )
    rejected.append(
        expect_rejection(
            "smoke_outside_block_failed_head_pass",
            append_smoke_body(
                "The c8be19476c24672fbf65d4dbf767fa8144360d22 external audit returned PASS."
            ),
            canonical_hash_error,
        )
    )
    rejected.append(
        expect_rejection(
            "smoke_failed_head_successful_no_findings",
            append_smoke_body(
                "The c8be19476c24672fbf65d4dbf767fa8144360d22 review was successful with no findings."
            ),
            canonical_hash_error,
        )
    )

    def promote_historical_classification(root: Path) -> None:
        target = root / smoke_manifest_path
        source = target.read_text(encoding="utf-8")
        old = "- Worker write in a Recall-root workspace: `NOT VERIFIED`."
        new = "- Worker write in a Recall-root workspace: `EXECUTED`."
        if source.count(old) != 1:
            raise AssertionError(f"historical_classification_target_count:{source.count(old)}")
        write_text(target, source.replace(old, new))

    rejected.append(
        expect_rejection(
            "smoke_historical_classification_promotion",
            promote_historical_classification,
            canonical_hash_error,
        )
    )

    def drift_smoke_narrative_counts(root: Path) -> None:
        target = root / smoke_manifest_path
        source = target.read_text(encoding="utf-8")
        old = "the updated 21 hashes and 83-mutation collaboration results"
        new = "the updated 22 hashes and 84-mutation collaboration results"
        if source.count(old) != 1:
            raise AssertionError(f"narrative_count_target_count:{source.count(old)}")
        write_text(target, source.replace(old, new))

    rejected.append(
        expect_rejection(
            "smoke_narrative_count_drift",
            drift_smoke_narrative_counts,
            canonical_hash_error,
        )
    )
    rejected.append(
        expect_rejection(
            "smoke_arbitrary_body_mutation_hash_refresh",
            append_smoke_body("Arbitrary canonical-body mutation.", refresh_hashes=True),
            canonical_hash_error,
        )
    )

    def mutate_evidence_table_cell(root: Path) -> None:
        target = root / smoke_manifest_path
        source = target.read_text(encoding="utf-8")
        pattern = re.compile(
            r"(?m)^\| `AGENTS\.md` \| `[0-9A-F]{64}` \|$"
        )
        replacement = f"| `AGENTS.md` | `{'0' * 64}` |"
        updated, count = pattern.subn(replacement, source)
        if count != 1:
            raise AssertionError(f"table_cell_target_count:{count}")
        write_text(target, updated)

    rejected.append(
        expect_rejection(
            "smoke_table_cell_actual_hash_mismatch",
            mutate_evidence_table_cell,
            "evidence_hash_mismatch:AGENTS.md",
        )
    )
    rejected.append(
        expect_rejection(
            "runtime_thread_cap_mechanism_promotion",
            replace_report_text(
                "- Three-thread cap and fourth-thread behavior: `NOT VERIFIED`.",
                "- Three-thread cap and fourth-thread behavior: `MECHANISM_PROVED`.",
            ),
            "smoke_classification_mismatch:Three-thread cap and fourth-thread behavior:"
            "MECHANISM_PROVED:NOT VERIFIED",
        )
    )

    def restore_stale_runtime_residual_count(root: Path) -> None:
        target = root / report_relative_path
        old = "the final contract conservatively retains seven `NOT VERIFIED` rows."
        new = "the final contract conservatively retains five `NOT VERIFIED` rows."
        source = target.read_text(encoding="utf-8")
        if source.count(old) != 1:
            raise AssertionError(
                f"runtime_residual_count_target_count:{source.count(old)}"
            )
        write_text(target, source.replace(old, new))
        refresh_evidence_hash(root, report_relative_path)
        refresh_claim_document_hash(root, report_relative_path)

    rejected.append(
        expect_rejection(
            "runtime_residual_count_stale_five_hash_refresh",
            restore_stale_runtime_residual_count,
            "runtime_residual_count_mismatch:five:5:7",
        )
    )

    rejected.append(
        expect_rejection(
            "runtime_worker_write_mechanism_promotion",
            replace_report_text(
                "- Worker write in a Recall-root workspace: `NOT VERIFIED`.",
                "- Worker write in a Recall-root workspace: `MECHANISM_PROVED`.",
            ),
            "smoke_classification_mismatch:Worker write in a Recall-root workspace:"
            "MECHANISM_PROVED:NOT VERIFIED",
        )
    )

    def restore_stale_status_residual_count(root: Path) -> None:
        status_relative_path = "docs/project/STATUS.md"
        target = root / status_relative_path
        old = "Preserve the seven exact `NOT VERIFIED` residuals;"
        new = "Preserve the six exact `NOT VERIFIED` residuals;"
        source = target.read_text(encoding="utf-8")
        if source.count(old) != 1:
            raise AssertionError(
                f"status_residual_count_target_count:{source.count(old)}"
            )
        write_text(target, source.replace(old, new))
        refresh_graphify_normative_hash(root, status_relative_path)

    rejected.append(
        expect_rejection(
            "status_residual_count_stale_six_hash_refresh",
            restore_stale_status_residual_count,
            "status_residual_count_mismatch:six:6:7",
        )
    )

    if tuple(rejected) != EXPECTED_MUTATION_REJECTIONS:
        raise AssertionError(f"mutation_label_set:{rejected}")

    print(
        json.dumps(
            {
                "status": "PASS",
                "mutation_rejections": rejected,
                "positive_controls": [
                    "lf_normalized_utf8_crlf_portability",
                    "current_c861_pass",
                    "failed_c8_and_877",
                    "historical_195_pass",
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
