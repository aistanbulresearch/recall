"""Fault-injection tests for verify_recall_collaboration.py."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from verify_recall_collaboration import ROOT, validate


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
    return temporary


def expect_rejection(
    label: str,
    mutate: Callable[[Path], None],
    expected_error: str,
) -> str:
    with isolated_root() as directory:
        root = Path(directory)
        mutate(root)
        try:
            validate(root)
        except ValueError as exc:
            message = str(exc)
            if expected_error not in message:
                raise AssertionError(f"{label}:wrong_error:{message}") from exc
            return label
        raise AssertionError(f"{label}:mutation_not_rejected")


def refresh_evidence_hash(root: Path, relative_path: str) -> None:
    import hashlib
    import re

    target = root / relative_path
    new_hash = hashlib.sha256(target.read_bytes()).hexdigest().upper()
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


def main() -> None:
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
            / "2026-08-17--codex-collaboration-smoke.md"
        )
        write_text(
            report_path,
            report_path.read_text(encoding="utf-8").replace(
                "- Custom profile discovery: `REPORT_DERIVED`",
                "- Custom profile discovery: `EXECUTED`",
            ),
        )

    rejected.append(
        expect_rejection(
            "smoke_classification_promotion",
            promote_report_derived_to_executed,
            "smoke_classification_mismatch:Custom profile discovery:EXECUTED:REPORT_DERIVED",
        )
    )

    def promote_displayed_functional_smoke(root: Path) -> None:
        report_path = (
            root
            / "docs"
            / "evaluation"
            / "reports"
            / "2026-08-17--codex-collaboration-smoke.md"
        )
        write_text(
            report_path,
            report_path.read_text(encoding="utf-8").replace(
                "functional_smoke=REPORT_DERIVED_PARTIAL_FAIL_CLOSED",
                "functional_smoke=EXECUTED",
            ),
        )

    rejected.append(
        expect_rejection(
            "displayed_functional_smoke_promotion",
            promote_displayed_functional_smoke,
            "smoke_summary_functional_mismatch:EXECUTED:REPORT_DERIVED_PARTIAL_FAIL_CLOSED",
        )
    )

    def drift_displayed_classification_counts(root: Path) -> None:
        report_path = (
            root
            / "docs"
            / "evaluation"
            / "reports"
            / "2026-08-17--codex-collaboration-smoke.md"
        )
        write_text(
            report_path,
            report_path.read_text(encoding="utf-8").replace(
                "runtime_evidence_classifications=3 REPORT_DERIVED,6 NOT VERIFIED",
                "runtime_evidence_classifications=2 REPORT_DERIVED,7 NOT VERIFIED",
            ),
        )

    rejected.append(
        expect_rejection(
            "displayed_classification_count_drift",
            drift_displayed_classification_counts,
            "smoke_summary_counts_mismatch:2 REPORT_DERIVED,7 NOT VERIFIED:3 REPORT_DERIVED,6 NOT VERIFIED",
        )
    )

    def promote_displayed_thread_cap_runtime(root: Path) -> None:
        report_path = (
            root
            / "docs"
            / "evaluation"
            / "reports"
            / "2026-08-17--codex-collaboration-smoke.md"
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
            / "2026-08-17--codex-collaboration-smoke.md"
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
        "docs/evaluation/reports/2026-08-17--codex-collaboration-smoke.md"
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
                "current_external_audit_verdict=FAIL",
                "current_external_audit_verdict=PASS",
            ),
        )

    rejected.append(
        expect_rejection(
            "current_state_inverse_machine_value",
            invert_current_state_required_fact,
            "current_state_value_mismatch:docs/adr/ADR-0008-external-audit-corrections.md:current_external_audit_verdict:PASS:FAIL",
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
        if validate(root)["status"] != "PASS":
            raise AssertionError("historical_exact_head_positive_control_failed")

    rejected.append("current_state_forbidden_stale_insertion")

    if len(rejected) != 23:
        raise AssertionError(f"mutation_rejection_count:{len(rejected)}:23")

    print(json.dumps({"status": "PASS", "mutation_rejections": rejected}, indent=2))


if __name__ == "__main__":
    main()
