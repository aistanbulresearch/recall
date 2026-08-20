"""Disposable-copy fault tests for the external-audit transcript verifier."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from verify_external_audit_transcript import ROOT, SUMMARY_PATH, TRANSCRIPT_PATH, validate


EXPECTED_MUTATION_REJECTIONS = (
    "body_byte_addition", "body_byte_deletion", "body_word_addition",
    "body_word_deletion", "body_number_mutation", "classification_mutation",
    "source_task_mutation", "source_turn_mutation", "declared_hash_mutation",
    "declared_count_mutation", "duplicate_start_delimiter", "missing_end_delimiter",
    "summary_label_promotion", "summary_path_mutation", "summary_hash_mutation",
    "summary_count_mutation", "summary_task_mutation", "summary_turn_mutation",
    "summary_exactness_claim", "summary_unscoped_pass", "summary_same_line_pass",
    "summary_authoritative_claim", "summary_byte_identical_claim",
    "summary_conflicting_task_prose", "summary_complete_hash_mutation",
)


def isolated_root() -> tempfile.TemporaryDirectory[str]:
    temporary = tempfile.TemporaryDirectory(prefix="recall-transcript-")
    root = Path(temporary.name)
    for relative in (TRANSCRIPT_PATH, SUMMARY_PATH):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return temporary


def replace(relative: Path, old: str, new: str) -> Callable[[Path], None]:
    def mutate(root: Path) -> None:
        path = root / relative
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise AssertionError(f"mutation_target_count:{relative}:{old}:{text.count(old)}")
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    return mutate


def expect(label: str, mutate: Callable[[Path], None], error: str) -> str:
    with isolated_root() as directory:
        root = Path(directory)
        mutate(root)
        try:
            validate(root)
        except ValueError as exc:
            if error not in str(exc):
                raise AssertionError(f"{label}:wrong_error:{exc}") from exc
            return label
        raise AssertionError(f"{label}:mutation_not_rejected")


def main() -> None:
    if validate(ROOT)["status"] != "PASS":
        raise AssertionError("baseline_failed")
    probes = [
        ("body_byte_addition", TRANSCRIPT_PATH, "FAIL\n", "FAIL!\n", "transcript_body_count_mismatch"),
        ("body_byte_deletion", TRANSCRIPT_PATH, "## Findings", "##Finding", "transcript_body_count_mismatch"),
        ("body_word_addition", TRANSCRIPT_PATH, "FAIL\n", "FAIL now\n", "transcript_body_count_mismatch"),
        ("body_word_deletion", TRANSCRIPT_PATH, "## Findings", "## Finding", "transcript_body_count_mismatch"),
        ("body_number_mutation", TRANSCRIPT_PATH, "- 242 nodes", "- 243 nodes", "transcript_body_hash_mismatch"),
        ("classification_mutation", TRANSCRIPT_PATH, "- `REPORT_DERIVED`:", "- `EXECUTED`:", "transcript_body_count_mismatch"),
        ("source_task_mutation", TRANSCRIPT_PATH, "source_task: 01a01671-1a00-70a2-af25-70f429682465", "source_task: wrong", "transcript_source_task_mismatch"),
        ("source_turn_mutation", TRANSCRIPT_PATH, "source_turn: 01a01671-21d7-7953-a911-6b060c889361", "source_turn: wrong", "transcript_source_turn_mismatch"),
        ("declared_hash_mutation", TRANSCRIPT_PATH, "2F3CD3F4DDBE96CE9A5B33C8A041E94242A950CDA21862DDDE75F0B61538489E", "0" * 64, "transcript_declared_hash_mismatch"),
        ("declared_count_mutation", TRANSCRIPT_PATH, "source_body_characters_lf: 7201", "source_body_characters_lf: 7202", "transcript_declared_count_mismatch"),
        ("duplicate_start_delimiter", TRANSCRIPT_PATH, "<!-- SOURCE_FINAL_START -->", "<!-- SOURCE_FINAL_START -->\n<!-- SOURCE_FINAL_START -->", "transcript_start_delimiter_count"),
        ("missing_end_delimiter", TRANSCRIPT_PATH, "<!-- SOURCE_FINAL_END -->", "<!-- SOURCE_FINAL_STOP -->", "transcript_end_delimiter_count"),
        ("summary_label_promotion", SUMMARY_PATH, "# Non-Authoritative Summary:", "# Authoritative Transcript:", "summary_label_invalid"),
        ("summary_path_mutation", SUMMARY_PATH, "../transcripts/2026-08-18--github-auditor-collaboration-fail-source-final.md", "../transcripts/wrong.md", "summary_path_mismatch"),
        ("summary_hash_mutation", SUMMARY_PATH, "2F3CD3F4DDBE96CE9A5B33C8A041E94242A950CDA21862DDDE75F0B61538489E", "1" * 64, "summary_hash_mismatch"),
        ("summary_count_mutation", SUMMARY_PATH, "Transcript body characters: `7201`", "Transcript body characters: `7202`", "summary_count_mismatch"),
        ("summary_task_mutation", SUMMARY_PATH, "External task: `01a01671-1a00-70a2-af25-70f429682465`", "External task: `wrong`", "summary_task_mismatch"),
        ("summary_turn_mutation", SUMMARY_PATH, "Source turn: `01a01671-21d7-7953-a911-6b060c889361`", "Source turn: `wrong`", "summary_turn_mismatch"),
        ("summary_exactness_claim", SUMMARY_PATH, "## Findings", "This is a faithful transcription.\n\n## Findings", "summary_exactness_claim_forbidden"),
        ("summary_unscoped_pass", SUMMARY_PATH, "## Gate", "External audit: PASS\n\n## Gate", "summary_unscoped_pass_forbidden"),
        ("summary_same_line_pass", SUMMARY_PATH, "- Verdict: `FAIL`", "- Verdict: `FAIL`; External audit: PASS", "summary_unscoped_pass_forbidden"),
        ("summary_authoritative_claim", SUMMARY_PATH, "## Findings", "This file is authoritative.\n\n## Findings", "summary_authoritative_claim_forbidden"),
        ("summary_byte_identical_claim", SUMMARY_PATH, "## Findings", "This summary is byte-for-byte identical.\n\n## Findings", "summary_exactness_claim_forbidden"),
        ("summary_conflicting_task_prose", SUMMARY_PATH, "## Findings", "Conflicting task: 01a01671-1a00-70a2-af25-70f429682466.\n\n## Findings", "summary_conflicting_source_identifier"),
        ("summary_complete_hash_mutation", SUMMARY_PATH, "- Date: 2026-08-18", "- Date: 2026-08-19", "summary_complete_hash_mismatch"),
    ]
    rejected = [expect(label, replace(path, old, new), error) for label, path, old, new, error in probes]
    if tuple(rejected) != EXPECTED_MUTATION_REJECTIONS:
        raise AssertionError(f"mutation_label_set:{rejected}")
    print(json.dumps({"status": "PASS", "mutation_rejections": rejected}, indent=2))


if __name__ == "__main__":
    main()
