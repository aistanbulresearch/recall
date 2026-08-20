"""Verify the frozen external-audit transcript and its summary metadata."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRANSCRIPT_PATH = Path(
    "docs/evaluation/transcripts/"
    "2026-08-18--github-auditor-collaboration-fail-source-final.md"
)
SUMMARY_PATH = Path(
    "docs/evaluation/reports/2026-08-18--github-auditor-collaboration-fail.md"
)
SUMMARY_SHA256_LF_UTF8 = "FBBFA41A02DAAD57F8A7453E858DC4310709B54499C6699871737C839D34ADEF"
SOURCE_TASK = "01a01671-1a00-70a2-af25-70f429682465"
SOURCE_TURN = "01a01671-21d7-7953-a911-6b060c889361"
BODY_CHARACTERS = 7201
BODY_SHA256 = "2F3CD3F4DDBE96CE9A5B33C8A041E94242A950CDA21862DDDE75F0B61538489E"
START = "<!-- SOURCE_FINAL_START -->"
END = "<!-- SOURCE_FINAL_END -->"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_lf(path: Path, root: Path) -> str:
    require(path.is_file(), f"missing_file:{path.relative_to(root).as_posix()}")
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def exact_value(text: str, pattern: str, label: str) -> str:
    values = re.findall(pattern, text, flags=re.MULTILINE)
    require(len(values) == 1, f"{label}_count:{len(values)}")
    return values[0]


def validate(root: Path = ROOT) -> dict[str, object]:
    transcript = read_lf(root / TRANSCRIPT_PATH, root)
    require(transcript.count(START) == 1, f"transcript_start_delimiter_count:{transcript.count(START)}")
    require(transcript.count(END) == 1, f"transcript_end_delimiter_count:{transcript.count(END)}")
    frontmatter_match = re.fullmatch(
        r"---\n"
        r"source_task: ([^\n]+)\n"
        r"source_turn: ([^\n]+)\n"
        r"source_body_characters_lf: ([0-9]+)\n"
        r"source_body_sha256_lf_utf8: ([0-9A-F]{64})\n"
        r"capture_mode: Codex read_thread final answer only\n"
        r"---\n"
        + re.escape(START)
        + r"\n([\s\S]*)"
        + re.escape(END)
        + r"\n?",
        transcript,
    )
    require(frontmatter_match is not None, "transcript_structure_invalid")
    task, turn, count_text, declared_hash, body = frontmatter_match.groups()
    require(task == SOURCE_TASK, f"transcript_source_task_mismatch:{task}")
    require(turn == SOURCE_TURN, f"transcript_source_turn_mismatch:{turn}")
    require(int(count_text) == BODY_CHARACTERS, f"transcript_declared_count_mismatch:{count_text}")
    require(declared_hash == BODY_SHA256, f"transcript_declared_hash_mismatch:{declared_hash}")
    actual_hash = hashlib.sha256(body.encode("utf-8")).hexdigest().upper()
    require(len(body) == BODY_CHARACTERS, f"transcript_body_count_mismatch:{len(body)}")
    require(actual_hash == BODY_SHA256, f"transcript_body_hash_mismatch:{actual_hash}")
    require(body.startswith("FAIL\n"), "transcript_body_verdict_invalid")
    require(body.endswith("\n\n") and not body.endswith("\n\n\n"), "transcript_body_ending_invalid")

    summary = read_lf(root / SUMMARY_PATH, root)
    require(summary.startswith("# Non-Authoritative Summary:"), "summary_label_invalid")
    required_summary_values = {
        "summary_task": (r"^- External task: `([^`]+)`$", SOURCE_TASK),
        "summary_turn": (r"^- Source turn: `([^`]+)`$", SOURCE_TURN),
        "summary_path": (
            r"^- Authoritative transcript: `([^`]+)`$",
            "../transcripts/2026-08-18--github-auditor-collaboration-fail-source-final.md",
        ),
        "summary_hash": (r"^- Transcript body SHA-256 \(LF UTF-8\): `([^`]+)`$", BODY_SHA256),
        "summary_count": (r"^- Transcript body characters: `([^`]+)`$", str(BODY_CHARACTERS)),
    }
    for label, (pattern, expected) in required_summary_values.items():
        actual = exact_value(summary, pattern, label)
        require(actual == expected, f"{label}_mismatch:{actual}")
    require(
        "This file is a non-authoritative repository summary." in summary,
        "summary_non_authoritative_boundary_missing",
    )
    prohibited = re.compile(
        r"(?i)\b(?:(?:faithful|verbatim|exact)\s+(?:source\s+)?transcription|"
        r"byte-for-byte identical)\b"
    )
    require(prohibited.search(summary) is None, "summary_exactness_claim_forbidden")
    require(
        re.search(r"(?i)\bthis file is authoritative\b", summary) is None,
        "summary_authoritative_claim_forbidden",
    )
    require(
        re.search(r"(?i)\bexternal audit\s*:\s*`?PASS`?\b", summary)
        is None,
        "summary_unscoped_pass_forbidden",
    )
    source_identifiers = set(
        re.findall(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", summary)
    )
    unexpected_identifiers = sorted(source_identifiers - {SOURCE_TASK, SOURCE_TURN})
    require(
        not unexpected_identifiers,
        f"summary_conflicting_source_identifier:{unexpected_identifiers}",
    )
    summary_hash = hashlib.sha256(summary.encode("utf-8")).hexdigest().upper()
    require(
        summary_hash == SUMMARY_SHA256_LF_UTF8,
        f"summary_complete_hash_mismatch:{summary_hash}",
    )
    return {
        "status": "PASS",
        "verification_scope": "REPOSITORY_ARTIFACT_INTEGRITY",
        "live_codex_equivalence": "NOT_VERIFIED",
        "source_task": task,
        "source_turn": turn,
        "body_characters_lf": len(body),
        "body_sha256_lf_utf8": actual_hash,
        "summary_sha256_lf_utf8": summary_hash,
    }


def main() -> int:
    try:
        print(json.dumps(validate(), indent=2, sort_keys=True))
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
