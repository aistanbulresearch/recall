"""Deterministically validate Recall's repo-scoped Codex collaboration files."""

from __future__ import annotations

import json
import hashlib
import re
import sys
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG_KEYS = {
    "enabled",
    "max_concurrent_threads_per_session",
    "default_subagent_model",
    "default_subagent_reasoning_effort",
}
COMMON_PROFILE_KEYS = {
    "name",
    "description",
    "model",
    "sandbox_mode",
    "developer_instructions",
}
PROTECTED_CLAUSES = (
    "do not perform destructive actions.",
    "do not make any github write, including comments, issues, reviews, pull requests, or settings.",
    "do not commit, push, merge, rebase, tag, or release.",
    "do not publish externally.",
    "do not change cloud resources.",
    "do not make billing decisions.",
    "do not request escalation.",
    "do not spawn agents.",
    "stop and return control to the coordinator",
)
HASHED_EVIDENCE_PATHS = {
    ".agents/skills/recall-collaboration/SKILL.md",
    ".agents/skills/recall-collaboration/agents/openai.yaml",
    ".agents/skills/recall-collaboration/references/master-judge-rubric.md",
    "AGENTS.md",
    ".codex/config.toml",
    ".codex/agents/recall-scout.toml",
    ".codex/agents/recall-worker.toml",
    ".codex/agents/recall-smart-worker.toml",
    ".codex/agents/recall-master-judge.toml",
    "scripts/validation/verify_recall_collaboration.py",
    "scripts/validation/test_recall_collaboration_validator.py",
    "docs/project/COLLABORATION_SYSTEM.md",
}
SMOKE_REPORT_PATH = (
    "docs/evaluation/reports/2026-08-17--codex-collaboration-smoke.md"
)
REQUIRED_SMOKE_CLASSIFICATIONS = {
    "Custom profile discovery": "REPORT_DERIVED",
    "Inherited read-only fail-closed behavior": "REPORT_DERIVED",
    "Master Judge exact failure behavior": "REPORT_DERIVED",
    "Worker write in a Recall-root workspace": "NOT VERIFIED",
    "Smart Worker runtime profile": "NOT VERIFIED",
    "Effective Judge reasoning effort": "NOT VERIFIED",
    "Three-thread cap and fourth-thread behavior": "NOT VERIFIED",
    "Complete four-role leaf no-spawn": "NOT VERIFIED",
    "Protected owner-operation stop and no protected side effect": "NOT VERIFIED",
}
RUNTIME_BOUNDARY_REQUIREMENTS = {
    "docs/adr/ADR-0009-repo-scoped-codex-collaboration.md": (
        "`REPORT_DERIVED`",
        "not runtime-verified",
        "Recall-root runtime smoke pending",
    ),
    "docs/project/STATUS.md": (
        "RCL-011:",
        "`REPORT_DERIVED`",
        "Every Recall-root matrix row remains",
    ),
    "docs/project/HANDOFF.md": (
        "RCL-011 is in progress",
        "`REPORT_DERIVED`",
        "Every Recall-root row in `COLLABORATION_SYSTEM.md` must pass before verification",
    ),
    "docs/project/COLLABORATION_SYSTEM.md": (
        "No row is considered runtime-verified from configuration alone",
    ),
}
COLLABORATION_RUNTIME_CLASSIFICATIONS = {
    "Complete four-role leaf no-spawn": "NOT VERIFIED",
    "Protected owner-operation stop and no protected side effect": "NOT VERIFIED",
}
PROTECTED_SMOKE_CLASSIFICATIONS = COLLABORATION_RUNTIME_CLASSIFICATIONS
CURRENT_STATE_PATHS = (
    "docs/adr/ADR-0008-external-audit-corrections.md",
    "docs/project/STATUS.md",
    "docs/project/MASTER_PLAN.md",
    "docs/project/HANDOFF.md",
)
FAILED_AUDIT_HEAD = "877c78d06d9b78f3071d17c81232fbc4302f857e"
HISTORICAL_PASS_HEAD = "195422e4d762d68d38e2b7f531cc5b1cd059cdb7"
CURRENT_STATE_EXPECTED = {
    "current_external_audit_head": FAILED_AUDIT_HEAD,
    "current_external_audit_verdict": "FAIL",
    "rcl_211": "IN_PROGRESS",
    "merge_gate": "NO_GO",
    "phase_3_gate": "NO_GO",
    "external_re_review": "REQUIRED",
    "historical_external_pass_head": HISTORICAL_PASS_HEAD,
}
STALE_CURRENT_PASS_PATTERNS = (
    re.compile(r"(?i)\b(?:current\s+)?external audit\s*:\s*`?PASS`?\b"),
    re.compile(
        r"(?i)\bthe final exact-head GitHub auditor re-review returned\s+`?PASS`?\b"
    ),
)
HISTORICAL_PASS_CLAIM_PATTERNS = (
    re.compile(
        rf"(?i)\b(?:historical|prior|earlier) external audit\s*:\s*`?PASS`?"
        rf"\s+at\s+`?{HISTORICAL_PASS_HEAD}`?\b"
    ),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_text(path: Path, root: Path) -> str:
    require(path.is_file(), f"missing_file:{path.relative_to(root)}")
    return path.read_text(encoding="utf-8")


def load_toml(path: Path, root: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing_file:{path.relative_to(root)}")
    with path.open("rb") as handle:
        return tomllib.load(handle)


def parse_scalar_mapping(text: str, allowed_keys: set[str], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        require(":" in line, f"{label}:line_{line_number}_invalid")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        require(key in allowed_keys, f"{label}:unknown_key:{key}")
        require(key not in result, f"{label}:duplicate_key:{key}")
        require(bool(value), f"{label}:empty_value:{key}")
        result[key] = value
    require(set(result) == allowed_keys, f"{label}:key_set_invalid:{sorted(result)}")
    return result


def parse_openai_yaml(text: str) -> dict[str, str]:
    lines = [line for line in text.splitlines() if line.strip()]
    require(lines and lines[0] == "interface:", "openai_yaml:root_invalid")
    allowed = {"display_name", "short_description", "default_prompt"}
    result: dict[str, str] = {}
    pattern = re.compile(r'^  ([a-z_]+):\s*("(?:[^"\\]|\\.)*")$')
    for line_number, line in enumerate(lines[1:], start=2):
        match = pattern.fullmatch(line)
        require(match is not None, f"openai_yaml:line_{line_number}_invalid")
        key, encoded = match.groups()
        require(key in allowed, f"openai_yaml:unknown_key:{key}")
        require(key not in result, f"openai_yaml:duplicate_key:{key}")
        value = json.loads(encoded)
        require(isinstance(value, str) and bool(value.strip()), f"openai_yaml:value_invalid:{key}")
        result[key] = value
    require(set(result) == allowed, f"openai_yaml:key_set_invalid:{sorted(result)}")
    require(25 <= len(result["short_description"]) <= 64, "openai_yaml:short_description_length_invalid")
    require("$recall-collaboration" in result["default_prompt"], "openai_yaml:skill_invocation_invalid")
    return result


def validate_markdown_links(markdown: str, source: Path, allowed_root: Path) -> list[str]:
    targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown)
    require(bool(targets), f"markdown_links:none:{source.name}")
    resolved_targets: list[str] = []
    allowed_root_resolved = allowed_root.resolve()
    for raw_target in targets:
        target = raw_target.strip().strip("<>").split("#", 1)[0]
        if not target or re.match(r"^[a-z]+://", target, re.IGNORECASE):
            continue
        resolved = (source.parent / target).resolve()
        require(resolved.is_relative_to(allowed_root_resolved), f"markdown_link_escape:{raw_target}")
        require(resolved.is_file(), f"markdown_link_missing:{raw_target}")
        resolved_targets.append(resolved.relative_to(allowed_root_resolved).as_posix())
    require("references/master-judge-rubric.md" in resolved_targets, "judge_rubric_link_missing")
    return resolved_targets


def validate_evidence_hashes(root: Path) -> int:
    report_path = root / SMOKE_REPORT_PATH
    report = read_text(report_path, root)
    tick = chr(96)
    rows: dict[str, str] = {}
    for line in report.splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) != 4 or not cells[1].startswith(tick):
            continue
        path_text = cells[1].strip(tick).replace("\\", "/")
        hash_text = cells[2].strip(tick)
        if re.fullmatch(r"[0-9A-F]{64}", hash_text):
            require(path_text not in rows, f"evidence_hash_duplicate:{path_text}")
            rows[path_text] = hash_text
    require(set(rows) == HASHED_EVIDENCE_PATHS, f"evidence_hash_path_set_invalid:{sorted(rows)}")
    for relative_path, expected_hash in rows.items():
        target = root / relative_path
        require(target.is_file(), f"evidence_hash_file_missing:{relative_path}")
        actual_hash = hashlib.sha256(target.read_bytes()).hexdigest().upper()
        require(actual_hash == expected_hash, f"evidence_hash_mismatch:{relative_path}")
    return len(rows)


def parse_exact_markdown_classifications(
    text: str,
    expected_classifications: dict[str, str],
    error_prefix: str,
) -> dict[str, str]:
    classifications: dict[str, str] = {}
    lines = text.splitlines()
    for label, expected in expected_classifications.items():
        prefix = f"- {label}:"
        candidates = [line for line in lines if line.lstrip().startswith(prefix)]
        require(
            len(candidates) == 1,
            f"{error_prefix}_classification_count:{label}:{len(candidates)}",
        )
        match = re.fullmatch(rf"- {re.escape(label)}: `([^`]+)`\.", candidates[0])
        require(
            match is not None,
            f"{error_prefix}_classification_line_invalid:{label}:{candidates[0]}",
        )
        actual = match.group(1)
        require(
            actual == expected,
            f"{error_prefix}_classification_mismatch:{label}:{actual}:{expected}",
        )
        classifications[label] = actual
    return classifications


def parse_runtime_classifications(report: str) -> dict[str, str]:
    exact = parse_exact_markdown_classifications(
        report,
        PROTECTED_SMOKE_CLASSIFICATIONS,
        "smoke",
    )
    classifications: dict[str, str] = {}
    for label, expected in REQUIRED_SMOKE_CLASSIFICATIONS.items():
        if label in PROTECTED_SMOKE_CLASSIFICATIONS:
            classifications[label] = exact[label]
            continue
        pattern = re.compile(rf"(?m)^- {re.escape(label)}: `([^`]+)`")
        matches = pattern.findall(report)
        require(
            len(matches) == 1,
            f"smoke_classification_count:{label}:{len(matches)}",
        )
        actual = matches[0]
        require(
            actual == expected,
            f"smoke_classification_mismatch:{label}:{actual}:{expected}",
        )
        classifications[label] = actual
    return classifications


def derive_functional_smoke(classifications: dict[str, str]) -> str:
    normalized = {value.replace(" ", "_") for value in classifications.values()}
    require(bool(normalized), "smoke_classifications_empty")
    parts: list[str] = []
    if "REPORT_DERIVED" in normalized:
        parts.append("REPORT_DERIVED")
    if "NOT_VERIFIED" in normalized:
        parts.extend(("PARTIAL", "FAIL_CLOSED"))
    require(parts, f"smoke_classifications_unsupported:{sorted(normalized)}")
    return "_".join(parts)


def parse_sanitized_results_block(report: str) -> str:
    pattern = re.compile(
        r"(?ms)^Sanitized report-derived results:\r?\n\r?\n```text\r?\n(.*?)\r?\n```(?=\r?\n|$)"
    )
    matches = pattern.findall(report)
    require(len(matches) == 1, f"smoke_summary_block_count:{len(matches)}")
    return matches[0]


def validate_displayed_smoke_summary(
    report: str,
    classifications: dict[str, str],
    functional_smoke: str,
) -> dict[str, str]:
    block = parse_sanitized_results_block(report)
    report_derived_count = sum(
        value == "REPORT_DERIVED" for value in classifications.values()
    )
    not_verified_count = sum(
        value == "NOT VERIFIED" for value in classifications.values()
    )
    expected_counts = (
        f"{report_derived_count} REPORT_DERIVED,"
        f"{not_verified_count} NOT VERIFIED"
    )
    expected_summary = {
        "functional_smoke": functional_smoke,
        "runtime_evidence_classifications": expected_counts,
        "thread_cap_runtime": classifications[
            "Three-thread cap and fourth-thread behavior"
        ].replace(" ", "_"),
        "judge_effective_effort_runtime": classifications[
            "Effective Judge reasoning effort"
        ].replace(" ", "_"),
        "complete_four_role_leaf_no_spawn_runtime": classifications[
            "Complete four-role leaf no-spawn"
        ].replace(" ", "_"),
        "protected_action_stop_runtime": classifications[
            "Protected owner-operation stop and no protected side effect"
        ].replace(" ", "_"),
    }
    summary_pairs = re.findall(r"(?m)^([a-z][a-z0-9_]*)=([^\r\n]+)$", block)
    relevant_pairs = [
        (key, value)
        for key, value in summary_pairs
        if key in expected_summary or key.endswith("_runtime")
    ]
    unknown_keys = sorted(
        {key for key, _ in relevant_pairs} - set(expected_summary)
    )
    require(
        not unknown_keys,
        f"smoke_summary_classification_unknown_keys:{unknown_keys}",
    )

    displayed_summary: dict[str, str] = {}
    for key, expected in expected_summary.items():
        values = [value for candidate, value in relevant_pairs if candidate == key]
        require(
            len(values) == 1,
            f"smoke_summary_classification_key_count:{key}:{len(values)}",
        )
        actual = values[0]
        if key == "functional_smoke":
            require(
                actual == expected,
                f"smoke_summary_functional_mismatch:{actual}:{expected}",
            )
        elif key == "runtime_evidence_classifications":
            require(
                actual == expected,
                f"smoke_summary_counts_mismatch:{actual}:{expected}",
            )
        else:
            require(
                actual == expected,
                f"smoke_summary_classification_mismatch:{key}:{actual}:{expected}",
            )
        displayed_summary[key] = actual
    return displayed_summary


def validate_runtime_boundary_docs(root: Path) -> None:
    for relative_path, fragments in RUNTIME_BOUNDARY_REQUIREMENTS.items():
        document = read_text(root / relative_path, root)
        for fragment in fragments:
            require(
                fragment in document,
                f"runtime_boundary_missing:{relative_path}:{fragment}",
            )
    collaboration_path = root / "docs" / "project" / "COLLABORATION_SYSTEM.md"
    collaboration = read_text(collaboration_path, root)
    parse_exact_markdown_classifications(
        collaboration,
        COLLABORATION_RUNTIME_CLASSIFICATIONS,
        "collaboration",
    )


def validate_current_state_contract(root: Path) -> None:
    for relative_path in CURRENT_STATE_PATHS:
        document = read_text(root / relative_path, root)
        headings = re.findall(
            r"(?m)^#{2,3} Current external-gate state$",
            document,
        )
        require(
            len(headings) == 1,
            f"current_state_block_heading_count:{relative_path}:{len(headings)}",
        )
        blocks = re.findall(
            r"(?ms)^#{2,3} Current external-gate state\r?\n\r?\n"
            r"```text\r?\n(.*?)\r?\n```(?=\r?\n|$)",
            document,
        )
        require(
            len(blocks) == 1,
            f"current_state_block_count:{relative_path}:{len(blocks)}",
        )
        parsed: dict[str, str] = {}
        for line_number, line in enumerate(blocks[0].splitlines(), start=1):
            match = re.fullmatch(r"([a-z][a-z0-9_]*)=([A-Za-z0-9_]+)", line)
            require(
                match is not None,
                f"current_state_line_invalid:{relative_path}:{line_number}:{line}",
            )
            key, value = match.groups()
            require(
                key in CURRENT_STATE_EXPECTED,
                f"current_state_unknown_key:{relative_path}:{key}",
            )
            require(
                key not in parsed,
                f"current_state_duplicate_key:{relative_path}:{key}",
            )
            parsed[key] = value
        missing = sorted(set(CURRENT_STATE_EXPECTED) - set(parsed))
        require(
            not missing,
            f"current_state_missing_keys:{relative_path}:{missing}",
        )
        for key, expected in CURRENT_STATE_EXPECTED.items():
            actual = parsed[key]
            require(
                actual == expected,
                f"current_state_value_mismatch:{relative_path}:{key}:{actual}:{expected}",
            )
        canonical_block = "\n".join(
            f"{key}={value}" for key, value in CURRENT_STATE_EXPECTED.items()
        )
        require(
            blocks[0] == canonical_block,
            f"current_state_block_format_mismatch:{relative_path}",
        )
        for line in document.splitlines():
            unmatched = line
            for pattern in HISTORICAL_PASS_CLAIM_PATTERNS:
                unmatched = pattern.sub("", unmatched)
            require(
                not any(
                    pattern.search(unmatched)
                    for pattern in STALE_CURRENT_PASS_PATTERNS
                ),
                f"current_state_forbidden:{relative_path}:unqualified_current_pass",
            )


def validate(root: Path = ROOT) -> dict[str, object]:
    root = root.resolve()
    skill_root = root / ".agents" / "skills" / "recall-collaboration"
    profile_root = root / ".codex" / "agents"

    config = load_toml(root / ".codex" / "config.toml", root)
    require(set(config) == {"agents"}, f"config_top_keys_invalid:{sorted(config)}")
    agents = config["agents"]
    require(isinstance(agents, dict), "agents_table_invalid")
    require(set(agents) == CONFIG_KEYS, f"agents_keys_invalid:{sorted(agents)}")
    require(agents["enabled"] is True, "agents_not_enabled")
    require(agents["max_concurrent_threads_per_session"] == 3, "thread_cap_invalid")
    require(isinstance(agents["max_concurrent_threads_per_session"], int), "thread_cap_type_invalid")
    require(agents["default_subagent_model"] == "gpt-5.6-sol", "default_model_invalid")
    require(agents["default_subagent_reasoning_effort"] == "high", "default_effort_invalid")

    expected: dict[str, tuple[str, str, str | None, str]] = {
        "recall-scout.toml": ("recall-scout", "gpt-5.6-terra", "low", "read-only"),
        "recall-worker.toml": ("recall-worker", "gpt-5.6-sol", "medium", "workspace-write"),
        "recall-smart-worker.toml": (
            "recall-smart-worker",
            "gpt-5.6-sol",
            "high",
            "workspace-write",
        ),
        "recall-master-judge.toml": (
            "recall-master-judge",
            "gpt-5.6-sol",
            None,
            "read-only",
        ),
    }
    actual = {path.name for path in profile_root.glob("*.toml")}
    require(actual == set(expected), f"profile_set_invalid:{sorted(actual)}")

    profiles: dict[str, dict[str, Any]] = {}
    profile_names: set[str] = set()
    for filename, (name, model, effort, sandbox) in expected.items():
        profile = load_toml(profile_root / filename, root)
        profiles[filename] = profile
        expected_keys = set(COMMON_PROFILE_KEYS)
        if effort is not None:
            expected_keys.add("model_reasoning_effort")
        require(set(profile) == expected_keys, f"{filename}:key_set_invalid:{sorted(profile)}")
        for field in ("name", "description", "developer_instructions"):
            require(isinstance(profile[field], str) and profile[field].strip(), f"{filename}:{field}_invalid")
        require(profile["name"] == name, f"{filename}:name_invalid")
        require(profile["name"] not in profile_names, f"{filename}:name_duplicate:{profile['name']}")
        profile_names.add(profile["name"])
        require(profile["model"] == model, f"{filename}:model_invalid")
        require(profile["sandbox_mode"] == sandbox, f"{filename}:sandbox_invalid")
        if effort is not None:
            require(profile["model_reasoning_effort"] == effort, f"{filename}:effort_invalid")
        instructions = " ".join(str(profile["developer_instructions"]).lower().split())
        for clause in PROTECTED_CLAUSES:
            require(clause in instructions, f"{filename}:protected_clause_missing:{clause}")

    skill = read_text(skill_root / "SKILL.md", root)
    require("TODO" not in skill, "skill_todo_present")
    frontmatter_match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", skill, re.DOTALL)
    require(frontmatter_match is not None, "skill_frontmatter_invalid")
    frontmatter = parse_scalar_mapping(
        frontmatter_match.group(1), {"name", "description"}, "skill_frontmatter"
    )
    require(frontmatter["name"] == "recall-collaboration", "skill_name_invalid")
    require(len(frontmatter["description"]) >= 80, "skill_description_too_short")
    links = validate_markdown_links(skill, skill_root / "SKILL.md", skill_root)

    metadata = parse_openai_yaml(read_text(skill_root / "agents" / "openai.yaml", root))
    agents_md = read_text(root / "AGENTS.md", root)
    require("$recall-collaboration" in agents_md, "agents_skill_trigger_missing")
    require("recall-master-judge" in agents_md, "agents_judge_trigger_missing")

    all_text = "\n".join(
        [skill, json.dumps(metadata), agents_md]
        + [read_text(profile_root / filename, root) for filename in sorted(expected)]
    )
    require(
        re.search(r"(?im)^\s*(co-authored-by|generated-by):", all_text) is None,
        "prohibited_authorship_marker",
    )
    report = read_text(root / SMOKE_REPORT_PATH, root)
    runtime_classifications = parse_runtime_classifications(report)
    functional_smoke = derive_functional_smoke(runtime_classifications)
    displayed_smoke_summary = validate_displayed_smoke_summary(
        report, runtime_classifications, functional_smoke
    )
    validate_runtime_boundary_docs(root)
    validate_current_state_contract(root)
    evidence_hashes = validate_evidence_hashes(root)

    return {
        "status": "PASS",
        "validation_scope": "STRUCTURAL",
        "profiles": len(profiles),
        "resolved_skill_links": links,
        "evidence_hashes_verified": evidence_hashes,
        "thread_cap_configured": agents["max_concurrent_threads_per_session"],
        "thread_cap_runtime": displayed_smoke_summary["thread_cap_runtime"],
        "judge_effort_config_source": ".codex/config.toml:agents.default_subagent_reasoning_effort",
        "judge_effective_effort_runtime": displayed_smoke_summary[
            "judge_effective_effort_runtime"
        ],
        "read_only_profiles": sorted(
            filename for filename, profile in profiles.items() if profile["sandbox_mode"] == "read-only"
        ),
        "workspace_write_profiles": sorted(
            filename for filename, profile in profiles.items() if profile["sandbox_mode"] == "workspace-write"
        ),
        "runtime_evidence_classifications": runtime_classifications,
        "displayed_smoke_summary": displayed_smoke_summary,
        "functional_smoke": functional_smoke,
    }


def main() -> int:
    try:
        print(json.dumps(validate(), indent=2, sort_keys=True))
    except (OSError, ValueError, tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
