"""Deterministically validate Recall's repo-scoped Codex collaboration files."""

from __future__ import annotations

import ast
import json
import hashlib
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

from verify_external_audit_transcript import validate as validate_external_audit_transcript
from verify_graphify_governance import validate as validate_graphify_governance


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
    "CLAUDE.md",
    ".codex/config.toml",
    ".codex/agents/recall-scout.toml",
    ".codex/agents/recall-worker.toml",
    ".codex/agents/recall-smart-worker.toml",
    ".codex/agents/recall-master-judge.toml",
    "scripts/validation/verify_recall_collaboration.py",
    "scripts/validation/test_recall_collaboration_validator.py",
    "scripts/validation/verify_external_audit_transcript.py",
    "scripts/validation/test_external_audit_transcript.py",
    "scripts/validation/verify_graphify_governance.py",
    "scripts/validation/test_graphify_governance.py",
    "docs/project/COLLABORATION_SYSTEM.md",
    "docs/evaluation/reports/2026-08-18--rcl-011-recall-root-runtime.md",
    "docs/adr/ADR-0008-external-audit-corrections.md",
    "docs/adr/ADR-0009-repo-scoped-codex-collaboration.md",
    "docs/project/MASTER_PLAN.md",
}
CLAIM_DOCUMENT_SHA256 = {
    "docs/adr/ADR-0008-external-audit-corrections.md": (
        "1DB009E0D8A3FCB5843ECA66B39DB9299765FB6B6CFF1A435BCA34ADFCA6090E"
    ),
    "docs/adr/ADR-0009-repo-scoped-codex-collaboration.md": (
        "2C9CE4E104B657FD690EE309F4AF079D76A951468349E63EA6E76CE33D3B7509"
    ),
    "docs/evaluation/reports/2026-08-18--rcl-011-recall-root-runtime.md": (
        "FEE0223814A2A995A7AFA80DAB5FE740B48619A63AB8F06B8B5D2D02AB1CDC12"
    ),
    "docs/project/COLLABORATION_SYSTEM.md": (
        "7BA4C20242A7FF87A5C9355BEED26D0044F8AE43295BD9EF94365D8CB857A141"
    ),
    "docs/project/MASTER_PLAN.md": (
        "4786FA34D6F888F55A6419F956E486CB30F572EFBDD3BE93DFE3B300936B6FB1"
    ),
}
EXPECTED_STANDALONE_MUTATIONS = {
    "scripts/validation/test_external_audit_transcript.py": (
        "body_byte_addition", "body_byte_deletion", "body_word_addition",
        "body_word_deletion", "body_number_mutation", "classification_mutation",
        "source_task_mutation", "source_turn_mutation", "declared_hash_mutation",
        "declared_count_mutation", "duplicate_start_delimiter", "missing_end_delimiter",
        "summary_label_promotion", "summary_path_mutation", "summary_hash_mutation",
        "summary_count_mutation", "summary_task_mutation", "summary_turn_mutation",
        "summary_exactness_claim", "summary_unscoped_pass", "summary_same_line_pass",
        "summary_authoritative_claim", "summary_byte_identical_claim",
        "summary_conflicting_task_prose", "summary_complete_hash_mutation",
    ),
    "scripts/validation/test_graphify_governance.py": (
        "policy_drift", "missing_scope_clause", "synchronized_scope_expansion",
        "old_blanket_wording", "prior_authorization_consumed", "outside_current_254",
        "outside_latest_wrong_counts", "outside_latest_wrong_hash",
        "outside_latest_wrong_build", "outside_graph_current_nodes",
        "outside_counts_before_graph", "outside_hash_before_graph", "outside_build_before_graph",
        "outside_sources_before_graph",
        "snapshot_value_replacement", "historical_key_rewrite", "runtime_proof_addition",
        "runtime_proof_before_graph", "duplicate_snapshot_block", "missing_snapshot_block",
        "duplicate_snapshot_key", "unknown_snapshot_key", "reordered_snapshot_keys",
        "malformed_snapshot_line",
        "outside_source_count_before_graph",
        "outside_latest_nodes_without_graph",
        "outside_current_source_coverage_without_graph",
        "outside_latest_manifest_source_total_without_graph",
        "outside_current_build_without_graph",
        "outside_latest_hash_without_graph",
        "outside_latest_graph_nodes_machine_key",
        "outside_graph_nodes_machine_key_current_after",
        "outside_current_manifest_sources_machine_key",
        "outside_manifest_sources_machine_key_latest_after",
        "outside_latest_report_build_commit_machine_key",
        "outside_current_graph_sha256_machine_key",
        "outside_currently_nodes_relation",
        "outside_nodes_currently_total_relation",
        "outside_most_recent_node_total_relation",
        "status_unrelated_line_hash_fallback",
        "handoff_unrelated_line_hash_fallback",
    ),
}
EVIDENCE_MANIFEST_REPORT_PATH = (
    "docs/evaluation/reports/2026-08-17--codex-collaboration-smoke.md"
)
SMOKE_MANIFEST_CANONICAL_SHA256 = (
    "3C8B5130CBC61A2BB06BFA1083FA21364254E3A186D1828CF6C5F6488FFEF2C1"
)
EVIDENCE_TABLE_HEADING = (
    "## LF-normalized UTF-8 evidence hashes at successor validator checkpoint"
)
RUNTIME_REPORT_PATH = (
    "docs/evaluation/reports/2026-08-18--rcl-011-recall-root-runtime.md"
)
REQUIRED_RUNTIME_CLASSIFICATIONS = {
    "Custom profile discovery": "EXECUTED",
    "Inherited read-only fail-closed behavior": "NOT VERIFIED",
    "Master Judge verdict formatting": "EXECUTED",
    "Worker write in a Recall-root workspace": "NOT VERIFIED",
    "Smart Worker runtime profile": "NOT VERIFIED",
    "Effective Judge reasoning effort": "NOT VERIFIED",
    "Three-thread cap and fourth-thread behavior": "NOT VERIFIED",
    "Complete four-role leaf no-spawn": "NOT VERIFIED",
    "Protected owner-operation stop and no protected side effect": "NOT VERIFIED",
}
RUNTIME_BOUNDARY_REQUIREMENTS = {
    "docs/adr/ADR-0009-repo-scoped-codex-collaboration.md": (
        "zero `MECHANISM_PROVED`",
        "`EXECUTED`",
        "seven residual",
    ),
    "docs/project/STATUS.md": (
        "RCL-011:",
        "zero `MECHANISM_PROVED`",
        "seven `NOT VERIFIED`",
    ),
    "docs/project/HANDOFF.md": (
        "RCL-011 is `PARTIAL_FAIL_CLOSED / DEFERRED`",
        "2026-08-18--rcl-011-recall-root-runtime.md",
        "seven residual",
    ),
    "docs/project/COLLABORATION_SYSTEM.md": (
        "No row is considered runtime-verified from configuration alone",
        "2026-08-18--rcl-011-recall-root-runtime.md",
    ),
}
COLLABORATION_RUNTIME_CLASSIFICATIONS = {
    "Worker write in a Recall-root workspace": "NOT VERIFIED",
    "Three-thread cap and fourth-thread behavior": "NOT VERIFIED",
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

BOUNDED_CLAIM_PATHS = tuple(CLAIM_DOCUMENT_SHA256) + (
    "docs/project/STATUS.md",
    "docs/project/HANDOFF.md",
)


def validate_bounded_claim_prohibitions(root: Path) -> None:
    """Reject the three exact overclaim classes accepted by the external audit.

    This is intentionally a small deny-list, not a general natural-language
    verifier. Independent review remains the trust boundary for synchronized
    document and validator changes.
    """

    allowed_executed_subjects = (
        "custom profile discovery",
        "custom-profile discovery",
        "profile discovery",
        "skill discovery",
        "master judge verdict formatting",
        "judge verdict formatting",
        "verdict formatting",
        "master judge",
    )
    negative_markers = (
        "not verified",
        "unauthorized",
        "not proof",
        "does not prove",
        "do not ",
        "no billing",
        "await separate owner approval",
        "no resource creation",
        "separately protected",
    )
    billing_surfaces = re.compile(
        r"(?i)\b(?:billing linkage|permissions|apis?|budgets?|resources?|"
        r"model calls?|spending)\b"
    )
    billing_context = re.compile(r"(?i)\b(?:billing|cloud|apis?|model calls?|spending)\b")
    positive_billing_state = re.compile(
        r"(?i)\b(?:verified|enabled|linked|active|ready)\b"
    )
    explicit_authorization = re.compile(
        r"(?i)\b(?:under explicit owner approval|authorized by (?:the )?owner|"
        r"owner-approved enablement|after separate owner approval)\b"
    )
    aggregate_runtime_counts = re.compile(
        r"(?i)\b(?:zero|0)\s+MECHANISM_PROVED\s*,\s*"
        r"(?:two|2)\s+EXECUTED\s*,?\s*(?:and\s+)?"
        r"(?:seven|7)\s+(?:unchanged\s+|residual\s+)?NOT VERIFIED\b"
    )

    def clauses(raw_line: str) -> tuple[tuple[str, str], ...]:
        """Return (table subject, clause) pairs for claim-local checks."""

        line = raw_line.replace("`", "").strip()
        if not line:
            return ()
        cells = [cell.strip() for cell in line.split("|") if cell.strip()]
        table_subject = cells[0].lower() if len(cells) > 1 else ""
        segments: list[tuple[str, str]] = []
        for cell in cells or [line]:
            for clause in re.split(r"(?<=[.!?])\s+|\s*;\s*", cell):
                if clause.strip():
                    segments.append((table_subject, clause.strip()))
        return tuple(segments)

    for relative_path in BOUNDED_CLAIM_PATHS:
        document = read_text(root / relative_path, root)
        for line_number, raw_line in enumerate(document.splitlines(), start=1):
            for table_subject, clause in clauses(raw_line):
                lower = clause.lower()

                if "mechanism_proved" in lower:
                    aggregate_boundary = bool(
                        aggregate_runtime_counts.search(clause)
                        and lower.count("mechanism_proved") == 1
                    )
                    permitted_boundary = (
                        aggregate_boundary
                        or re.search(r"\bnot\b[^.]{0,80}\bmechanism_proved\b", lower)
                        or "promotion to either executed or mechanism_proved" in lower
                        or "unauthorized mechanism_proved" in lower
                    )
                    require(
                        bool(permitted_boundary),
                        f"bounded_claim_overreach:MECHANISM_PROVED:{relative_path}:{line_number}",
                    )

                if "executed" in lower:
                    count_boundary = bool(
                        aggregate_runtime_counts.search(clause)
                        and lower.count("executed") == 1
                    )
                    negative_boundary = bool(
                        re.search(r"\bnot\b[^.]{0,80}\bexecuted\b", lower)
                    )
                    positive_claim = bool(
                        re.search(
                            r"(?i)(?:\b(?:is|are|was|were|now|remain|remains)\b[^.]{0,80}"
                            r"\bEXECUTED\b|:\s*EXECUTED\b|\bEXECUTED\s+(?:observation|evidence|runtime|with)\b)",
                            clause,
                        )
                    )
                    allowed_sentence = bool(
                        re.fullmatch(
                            r"(?i)-?\s*(?:only\s+)?(?:(?:custom[- ]?)?profile discovery(?:\s+and\s+"
                            r"(?:master\s+)?judge verdict formatting)?|(?:master\s+)?judge verdict formatting|"
                            r"verdict formatting)(?:\s+(?:is|are|remain|remains)|:)\s+EXECUTED\.?",
                            clause.strip(),
                        )
                    )
                    allowed_table_subject = (
                        any(subject == table_subject for subject in allowed_executed_subjects)
                        and lower.count("executed") == 1
                    )
                    require(
                        not positive_claim
                        or count_boundary
                        or negative_boundary
                        or allowed_sentence
                        or allowed_table_subject,
                        f"bounded_claim_overreach:EXECUTED:{relative_path}:{line_number}",
                    )

                if (
                    billing_surfaces.search(clause)
                    and billing_context.search(clause)
                    and positive_billing_state.search(clause)
                    and "owner_reported_selected" not in lower
                    and not any(marker in lower for marker in negative_markers)
                    and not explicit_authorization.search(clause)
                ):
                    require(
                        False,
                        f"bounded_claim_overreach:BILLING_CLOUD:{relative_path}:{line_number}",
                    )
CURRENT_AUDIT_HEAD = "46afabfcc5716dde6f13e49d118a63b2beacc903"
LAST_PASSING_AUDIT_HEAD = "c86139048d1532c79ed190d0cc98ce2ad878414b"
FAILED_PARENT_HEAD = "c8be19476c24672fbf65d4dbf767fa8144360d22"
AUDITED_PREDECESSOR_HEAD = "877c78d06d9b78f3071d17c81232fbc4302f857e"
HISTORICAL_PASS_HEAD = "195422e4d762d68d38e2b7f531cc5b1cd059cdb7"
FAILED_AUDIT_HEAD_REFERENCES = (
    CURRENT_AUDIT_HEAD,
    CURRENT_AUDIT_HEAD[:8],
    CURRENT_AUDIT_HEAD[:7],
    FAILED_PARENT_HEAD,
    FAILED_PARENT_HEAD[:8],
    FAILED_PARENT_HEAD[:7],
)
AUDITED_PREDECESSOR_HEAD_REFERENCES = (
    AUDITED_PREDECESSOR_HEAD,
    AUDITED_PREDECESSOR_HEAD[:8],
    AUDITED_PREDECESSOR_HEAD[:7],
)
FAILED_AUDIT_HEAD_PATTERN = "|".join(
    re.escape(reference) for reference in FAILED_AUDIT_HEAD_REFERENCES
)
AUDITED_PREDECESSOR_HEAD_PATTERN = "|".join(
    re.escape(reference) for reference in AUDITED_PREDECESSOR_HEAD_REFERENCES
)
CURRENT_STATE_EXPECTED = {
    "current_external_audit_head": CURRENT_AUDIT_HEAD,
    "current_external_audit_verdict": "FAIL",
    "audited_predecessor_head": AUDITED_PREDECESSOR_HEAD,
    "rcl_211": "VERIFIED",
    "merge_gate": "NO_GO",
    "phase_3_gate": "OWNER_APPROVED",
    "external_re_review": "REQUIRED",
    "historical_external_pass_head": HISTORICAL_PASS_HEAD,
}
STALE_CURRENT_PASS_PATTERNS = (
    re.compile(
        r"(?i)\b(?:current\s+)?external audit\s*"
        r"(?::|=|\breturned\b|\bwas\b)?\s*`?PASS(?:ED)?`?\b"
    ),
    re.compile(r"(?i)\bpassed the external audit\b"),
    re.compile(
        r"(?i)\bthe final exact-head GitHub auditor re-review returned\s+`?PASS`?\b"
    ),
    re.compile(
        rf"(?i)\b(?:{FAILED_AUDIT_HEAD_PATTERN})\b[^;\n]{{0,60}}"
        r"(?:audit|re-review|verdict)?\s*(?::|=|,|—|-|\breturned\b|\bwas\b|\bis\b)?"
        r"\s*`?PASS(?:ED)?`?\b"
    ),
    re.compile(
        rf"(?i)\b(?:{AUDITED_PREDECESSOR_HEAD_PATTERN})\b[^;\n]{{0,60}}"
        r"(?:audit|re-review|verdict)?\s*(?::|=|,|—|-|\breturned\b|\bwas\b|\bis\b)?"
        r"\s*`?PASS(?:ED)?`?\b"
    ),
    re.compile(
        rf"(?i)(?:\b`?PASS(?:ED)?`?\b\s+(?:at|for|on)\s+[^;\n]{{0,40}}|"
        rf"\b`?PASS(?:ED)?`?\b\s*(?::|=|,|—|-)\s*(?:audited predecessor\s+)?)"
        rf"\b(?:{FAILED_AUDIT_HEAD_PATTERN}|{AUDITED_PREDECESSOR_HEAD_PATTERN})\b"
    ),
)
HISTORICAL_PASS_CLAIM_PATTERNS = (
    re.compile(
        rf"(?i)\b(?:historical|prior|earlier) external audit\s*:\s*`?PASS`?"
        rf"\s+at\s+`?{HISTORICAL_PASS_HEAD}`?\b"
    ),
    re.compile(
        rf"(?i)\b(?:last passing external audit|last passing audited head)\b"
        rf"[^;\n]{{0,80}}(?:`?PASS`?[^;\n]{{0,20}})?`?{LAST_PASSING_AUDIT_HEAD}`?\b"
    ),
)
CURRENT_PASS_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = ()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_text(path: Path, root: Path) -> str:
    require(path.is_file(), f"missing_file:{path.relative_to(root)}")
    return path.read_text(encoding="utf-8")


def lf_normalized_utf8_bytes(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


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
    report_path = root / EVIDENCE_MANIFEST_REPORT_PATH
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
        actual_hash = hashlib.sha256(lf_normalized_utf8_bytes(target)).hexdigest().upper()
        require(actual_hash == expected_hash, f"evidence_hash_mismatch:{relative_path}")
    return len(rows)


def canonical_smoke_manifest_bytes(root: Path) -> bytes:
    report_path = root / EVIDENCE_MANIFEST_REPORT_PATH
    normalized = lf_normalized_utf8_bytes(report_path).decode("utf-8")
    lines = normalized.split("\n")
    heading_indexes = [
        index for index, line in enumerate(lines) if line == EVIDENCE_TABLE_HEADING
    ]
    require(
        len(heading_indexes) == 1,
        f"evidence_table_heading_count:{len(heading_indexes)}",
    )
    heading_index = heading_indexes[0]
    require(
        lines[heading_index + 1 : heading_index + 4]
        == ["", "| Path | SHA-256 |", "|---|---|"],
        "evidence_table_header_invalid",
    )
    row_pattern = re.compile(r"\| `([^`]+)` \| `([0-9A-F]{64})` \|")
    row_index = heading_index + 4
    rows: list[tuple[str, str]] = []
    while row_index < len(lines) and lines[row_index]:
        match = row_pattern.fullmatch(lines[row_index])
        require(match is not None, f"evidence_table_row_invalid:{row_index + 1}")
        rows.append(match.groups())
        lines[row_index] = (
            f"| `{match.group(1)}` | `{'0' * 64}` |"
        )
        row_index += 1
    require(row_index < len(lines), "evidence_table_unterminated")
    require(
        len(rows) == len(HASHED_EVIDENCE_PATHS),
        f"evidence_table_row_count:{len(rows)}",
    )
    paths = [path.replace("\\", "/") for path, _ in rows]
    require(len(paths) == len(set(paths)), "evidence_table_path_duplicate")
    require(
        set(paths) == HASHED_EVIDENCE_PATHS,
        f"evidence_table_path_set_invalid:{sorted(paths)}",
    )
    return "\n".join(lines).encode("utf-8")


def validate_smoke_manifest_canonical_body(root: Path) -> str:
    actual_hash = hashlib.sha256(canonical_smoke_manifest_bytes(root)).hexdigest().upper()
    require(
        actual_hash == SMOKE_MANIFEST_CANONICAL_SHA256,
        "smoke_manifest_canonical_hash_mismatch",
    )
    return actual_hash


def validate_claim_document_hashes(root: Path) -> int:
    for relative_path, expected_hash in CLAIM_DOCUMENT_SHA256.items():
        target = root / relative_path
        require(target.is_file(), f"claim_document_missing:{relative_path}")
        actual_hash = hashlib.sha256(lf_normalized_utf8_bytes(target)).hexdigest().upper()
        require(
            actual_hash == expected_hash,
            f"claim_document_hash_mismatch:{relative_path}",
        )
    return len(CLAIM_DOCUMENT_SHA256)


def parse_collaboration_mutation_labels(root: Path) -> tuple[str, ...]:
    relative_path = "scripts/validation/test_recall_collaboration_validator.py"
    tree = ast.parse(read_text(root / relative_path, root), filename=relative_path)
    candidates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "EXPECTED_MUTATION_REJECTIONS":
            candidates.append(ast.literal_eval(node.value))
    require(len(candidates) == 1, f"collaboration_mutation_tuple_count:{len(candidates)}")
    labels = candidates[0]
    require(isinstance(labels, tuple), "collaboration_mutation_tuple_invalid")
    require(
        all(isinstance(label, str) and label for label in labels),
        "collaboration_mutation_label_invalid",
    )
    require(len(labels) == len(set(labels)), "collaboration_mutation_label_duplicate")
    return labels


def validate_smoke_manifest_summary(root: Path) -> dict[str, str]:
    report = read_text(root / EVIDENCE_MANIFEST_REPORT_PATH, root)
    matches = re.findall(
        r"(?ms)^Sanitized structural-manifest results:\r?\n\r?\n"
        r"```text\r?\n(.*?)\r?\n```(?=\r?\n|$)",
        report,
    )
    require(len(matches) == 1, f"manifest_summary_block_count:{len(matches)}")
    mutation_labels = parse_collaboration_mutation_labels(root)
    require(len(mutation_labels) == 88, f"collaboration_mutation_count:{len(mutation_labels)}")
    expected = {
        "validator status": "PASS",
        "validation_scope": "STRUCTURAL_PLUS_BOUNDED_RUNTIME_EVIDENCE",
        "profiles": "4",
        "evidence_hashes_verified": "21",
        "evidence_hash_mode": "LF_NORMALIZED_UTF8",
        "thread_cap_configured": "3",
        "profile_names": (
            "recall-scout,recall-worker,recall-smart-worker,recall-master-judge"
        ),
        "aggregate_collaboration_mutation_rejections": "88",
        "mutation_rejections": ",".join(mutation_labels),
        "external_audit_transcript": (
            "PASS; artifact integrity only; live Codex equivalence NOT_VERIFIED"
        ),
        "external_transcript_mutation_rejections": "25",
        "graphify_governance": (
            "PASS; portable repository policy/snapshot gate only; "
            "scheduler runtime NOT_VERIFIED"
        ),
        "graphify_governance_mutation_rejections": "41",
        "positive_controls": (
            "lf_normalized_utf8_crlf_portability,current_46_fail_last_passing_c861,"
            "failed_c8_and_877,historical_195_pass,explicit_owner_api_authorization"
        ),
    }
    parsed: dict[str, str] = {}
    non_field_lines: list[str] = []
    for line in matches[0].splitlines():
        if "=" not in line:
            non_field_lines.append(line)
            continue
        key, value = line.split("=", 1)
        require(key in expected, f"manifest_summary_unknown_key:{key}")
        require(key not in parsed, f"manifest_summary_duplicate_key:{key}")
        parsed[key] = value
    missing = sorted(set(expected) - set(parsed))
    require(not missing, f"manifest_summary_missing_keys:{missing}")
    require(
        non_field_lines
        == [
            "Skill is valid!",
            "multi_agent stable true",
            "git diff --check: exit 0, no output",
        ],
        f"manifest_summary_non_field_lines_mismatch:{non_field_lines}",
    )
    for key, expected_value in expected.items():
        actual = parsed[key]
        require(
            actual == expected_value,
            f"manifest_summary_value_mismatch:{key}:{actual}:{expected_value}",
        )
    return parsed


def validate_standalone_mutation_contracts(root: Path) -> None:
    for relative_path, expected in EXPECTED_STANDALONE_MUTATIONS.items():
        tree = ast.parse(read_text(root / relative_path, root), filename=relative_path)
        declared: tuple[str, ...] | None = None
        probes: tuple[str, ...] | None = None
        variant_probes: tuple[str, ...] = ()
        context_omission_probes: tuple[str, ...] = ()
        machine_key_probes: tuple[str, ...] = ()
        hash_fallback_probes: tuple[str, ...] = ()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            if target.id == "EXPECTED_MUTATION_REJECTIONS":
                value = ast.literal_eval(node.value)
                require(isinstance(value, tuple), f"mutation_expected_tuple_invalid:{relative_path}")
                declared = value
            elif target.id == "probes" and isinstance(node.value, (ast.List, ast.Tuple)):
                labels: list[str] = []
                for element in node.value.elts:
                    require(
                        isinstance(element, (ast.List, ast.Tuple))
                        and bool(element.elts)
                        and isinstance(element.elts[0], ast.Constant)
                        and isinstance(element.elts[0].value, str),
                        f"mutation_probe_shape_invalid:{relative_path}",
                    )
                    labels.append(element.elts[0].value)
                probes = tuple(labels)
            elif target.id == "variant_probes" and isinstance(node.value, (ast.List, ast.Tuple)):
                labels = []
                for element in node.value.elts:
                    require(
                        isinstance(element, (ast.List, ast.Tuple))
                        and bool(element.elts)
                        and isinstance(element.elts[0], ast.Constant)
                        and isinstance(element.elts[0].value, str),
                        f"mutation_variant_probe_shape_invalid:{relative_path}",
                    )
                    labels.append(element.elts[0].value)
                variant_probes = tuple(labels)
            elif target.id == "context_omission_probes" and isinstance(node.value, (ast.List, ast.Tuple)):
                labels = []
                for element in node.value.elts:
                    require(
                        isinstance(element, (ast.List, ast.Tuple))
                        and bool(element.elts)
                        and isinstance(element.elts[0], ast.Constant)
                        and isinstance(element.elts[0].value, str),
                        f"mutation_context_probe_shape_invalid:{relative_path}",
                    )
                    labels.append(element.elts[0].value)
                context_omission_probes = tuple(labels)
            elif target.id == "machine_key_probes" and isinstance(node.value, (ast.List, ast.Tuple)):
                labels = []
                for element in node.value.elts:
                    require(
                        isinstance(element, (ast.List, ast.Tuple))
                        and bool(element.elts)
                        and isinstance(element.elts[0], ast.Constant)
                        and isinstance(element.elts[0].value, str),
                        f"mutation_machine_key_probe_shape_invalid:{relative_path}",
                    )
                    labels.append(element.elts[0].value)
                machine_key_probes = tuple(labels)
            elif target.id == "hash_fallback_probes" and isinstance(node.value, (ast.List, ast.Tuple)):
                labels = []
                for element in node.value.elts:
                    require(
                        isinstance(element, (ast.List, ast.Tuple))
                        and bool(element.elts)
                        and isinstance(element.elts[0], ast.Constant)
                        and isinstance(element.elts[0].value, str),
                        f"mutation_hash_fallback_probe_shape_invalid:{relative_path}",
                    )
                    labels.append(element.elts[0].value)
                hash_fallback_probes = tuple(labels)
        require(declared == expected, f"mutation_expected_labels_mismatch:{relative_path}")
        require(
            probes is not None
            and probes
            + variant_probes
            + context_omission_probes
            + machine_key_probes
            + hash_fallback_probes
            == expected,
            f"mutation_probe_labels_mismatch:{relative_path}",
        )


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
    blocks = re.findall(
        r"(?ms)^## Validator-bound runtime classifications\r?\n\r?\n"
        r"(.*?)\r?\n\r?\nSanitized validator-bound results:$",
        report,
    )
    require(
        len(blocks) == 1,
        f"smoke_classification_block_count:{len(blocks)}",
    )
    classifications: dict[str, str] = {}
    for line_number, line in enumerate(blocks[0].splitlines(), start=1):
        candidate_label = line.removeprefix("- ").split(":", 1)[0]
        match = re.fullmatch(r"- ([^:\r\n]+): `([^`]+)`\.", line)
        require(
            match is not None,
            f"smoke_classification_line_invalid:{candidate_label}:{line_number}",
        )
        label, actual = match.groups()
        require(
            label in REQUIRED_RUNTIME_CLASSIFICATIONS,
            f"smoke_classification_unknown_label:{label}",
        )
        require(
            label not in classifications,
            f"smoke_classification_duplicate_label:{label}",
        )
        expected = REQUIRED_RUNTIME_CLASSIFICATIONS[label]
        require(
            actual == expected,
            f"smoke_classification_mismatch:{label}:{actual}:{expected}",
        )
        classifications[label] = actual
    missing = sorted(set(REQUIRED_RUNTIME_CLASSIFICATIONS) - set(classifications))
    require(not missing, f"smoke_classification_missing_labels:{missing}")
    return {
        label: classifications[label] for label in REQUIRED_RUNTIME_CLASSIFICATIONS
    }


def validate_runtime_residual_count(
    report: str,
    classifications: dict[str, str],
) -> int:
    matches = re.findall(
        r"(?m)^3\. The final Design Judge returned `PASS` .* "
        r"the final contract conservatively retains "
        r"(zero|one|two|three|four|five|six|seven|eight|nine) "
        r"`NOT VERIFIED` rows\.$",
        report,
    )
    require(
        len(matches) == 1,
        f"runtime_residual_count_claim_count:{len(matches)}",
    )
    number_words = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
    }
    actual_word = matches[0]
    actual_count = number_words[actual_word]
    expected_count = sum(
        classification == "NOT VERIFIED"
        for classification in classifications.values()
    )
    require(
        actual_count == expected_count,
        f"runtime_residual_count_mismatch:{actual_word}:{actual_count}:{expected_count}",
    )
    return actual_count


def validate_status_residual_count(
    root: Path,
    classifications: dict[str, str],
) -> int:
    status = read_text(root / "docs" / "project" / "STATUS.md", root)
    matches = re.findall(
        r"(?m)^\| Partial collaboration runtime evidence could be mistaken for full "
        r"enforcement \| High \| Preserve the "
        r"(zero|one|two|three|four|five|six|seven|eight|nine) exact "
        r"`NOT VERIFIED` residuals; require .* \|$",
        status,
    )
    require(
        len(matches) == 1,
        f"status_residual_count_claim_count:{len(matches)}",
    )
    number_words = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
    }
    actual_word = matches[0]
    actual_count = number_words[actual_word]
    expected_count = sum(
        classification == "NOT VERIFIED"
        for classification in classifications.values()
    )
    require(
        actual_count == expected_count,
        f"status_residual_count_mismatch:{actual_word}:{actual_count}:{expected_count}",
    )
    return actual_count


def derive_functional_smoke(classifications: dict[str, str]) -> str:
    normalized = {value.replace(" ", "_") for value in classifications.values()}
    require(bool(normalized), "smoke_classifications_empty")
    supported = {"MECHANISM_PROVED", "EXECUTED", "NOT_VERIFIED"}
    require(
        normalized <= supported,
        f"smoke_classifications_unsupported:{sorted(normalized)}",
    )
    require("NOT_VERIFIED" in normalized, "smoke_fail_closed_boundary_missing")
    return "PARTIAL_FAIL_CLOSED"


def parse_sanitized_results_block(report: str) -> str:
    pattern = re.compile(
        r"(?ms)^Sanitized validator-bound results:\r?\n\r?\n```text\r?\n(.*?)\r?\n```(?=\r?\n|$)"
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
    mechanism_proved_count = sum(
        value == "MECHANISM_PROVED" for value in classifications.values()
    )
    executed_count = sum(value == "EXECUTED" for value in classifications.values())
    not_verified_count = sum(
        value == "NOT VERIFIED" for value in classifications.values()
    )
    expected_counts = (
        f"{mechanism_proved_count} MECHANISM_PROVED,"
        f"{executed_count} EXECUTED,"
        f"{not_verified_count} NOT VERIFIED"
    )
    expected_summary = {
        "evidence_hashes_verified": "21",
        "evidence_hash_mode": "LF_NORMALIZED_UTF8",
        "external_transcript_mutation_rejections": "25",
        "graphify_governance_mutation_rejections": "41",
        "aggregate_collaboration_mutation_rejections": "88",
        "positive_controls": (
            "lf_normalized_utf8_crlf_portability,current_46_fail_last_passing_c861,"
            "failed_c8_and_877,historical_195_pass,explicit_owner_api_authorization"
        ),
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
            for pattern in CURRENT_PASS_CLAIM_PATTERNS + HISTORICAL_PASS_CLAIM_PATTERNS:
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
    report = read_text(root / RUNTIME_REPORT_PATH, root)
    runtime_classifications = parse_runtime_classifications(report)
    validate_runtime_residual_count(report, runtime_classifications)
    validate_status_residual_count(root, runtime_classifications)
    functional_smoke = derive_functional_smoke(runtime_classifications)
    displayed_smoke_summary = validate_displayed_smoke_summary(
        report, runtime_classifications, functional_smoke
    )
    validate_runtime_boundary_docs(root)
    validate_current_state_contract(root)
    validate_bounded_claim_prohibitions(root)
    validate_standalone_mutation_contracts(root)
    manifest_summary = validate_smoke_manifest_summary(root)
    smoke_manifest_canonical_hash = validate_smoke_manifest_canonical_body(root)
    claim_documents = validate_claim_document_hashes(root)
    transcript_result = validate_external_audit_transcript(root)
    graphify_result = validate_graphify_governance(root)
    evidence_hashes = validate_evidence_hashes(root)

    return {
        "status": "PASS",
        "validation_scope": "STRUCTURAL_PLUS_BOUNDED_RUNTIME_EVIDENCE",
        "profiles": len(profiles),
        "resolved_skill_links": links,
        "evidence_hashes_verified": evidence_hashes,
        "claim_documents_verified": claim_documents,
        "evidence_hash_mode": "LF_NORMALIZED_UTF8",
        "external_audit_transcript": transcript_result["status"],
        "graphify_governance": graphify_result["status"],
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
        "displayed_manifest_summary": manifest_summary,
        "smoke_manifest_canonical_sha256": smoke_manifest_canonical_hash,
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
