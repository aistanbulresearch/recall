"""Validate portable Recall Graphify governance and snapshot evidence."""

from __future__ import annotations

import json
import hashlib
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY_HEADING = "## Recall Graphify agent policy"
POLICY_SHA256 = "E7A85809F2ACBAD547DBEF7D7AEBC668FCA299963B5F8336CF0FB19B996F0D77"
NORMATIVE_DOCUMENT_SHA256 = {
    "docs/project/STATUS.md": "EC1EAA34BDF3CDDE6843572B81C1CECBAE480AB1558C6EAAF21C452F175EEC6D",
    "docs/project/HANDOFF.md": "E59C4E2819861460B32D09D469EA707630385F644DA04A051184B89F226F4DCD",
}
SNAPSHOT_EXPECTED = (
    ("snapshot_scope", "POINT_IN_TIME"),
    ("snapshot_timestamp", "2026-08-19T04:45:37Z"),
    ("graph_nodes", "254"),
    ("graph_edges", "276"),
    ("graph_communities", "49"),
    ("graph_concepts", "140"),
    ("manifest_sources", "75/75"),
    ("missing_sources", "0"),
    ("broken_endpoints", "0"),
    ("policy_gate_nodes", "1"),
    ("policy_gate_incident_edges", "5"),
    ("graph_sha256", "973089FA8EF6F333843879D213D3E3C721079BAB5234B95549F1DEBB920245AE"),
    ("report_sha256", "7F49F479F74FBF2424D255D632AB038C4EFDB7BF25873C9D45181DF63CE45F96"),
    ("report_build_commit", "c8be1947"),
    ("historical_snapshots", "240/260/44/129;231/248/45/120;242/258/48/131@74/74"),
    ("evidence_scope", "NAVIGATION_AND_ARTIFACT_INTEGRITY_ONLY"),
    ("scheduler_runtime", "NOT_VERIFIED"),
)
NORMATIVE_PATHS = (
    "AGENTS.md",
    "CLAUDE.md",
    "docs/project/STATUS.md",
    "docs/project/HANDOFF.md",
    "docs/project/COLLABORATION_SYSTEM.md",
)
POLICY_FRAGMENTS = (
    "registered `Graphify-Refresh-All` automation to run\n`refresh-repo.ps1 -All -NoBackup` every two hours",
    "`gemini` backend, `gemini-3.5-flash-lite` model,\n`recall-concepts-v1` profile, 5000-token extraction budget",
    "When both fingerprints are unchanged, it must skip Gemini\nextraction.",
    "it may transmit only the configured\nsupported Recall corpus to Gemini semantic extraction and missing-label\ngeneration within that fixed scope.",
    "Logs must not contain credentials or private\nsource contents.",
    "Any change to cadence, source roots, supported file classes, destination,\nbackend, model, profile, token budget, logging destination, task principal, or\nprivilege requires a new explicit owner authorization.",
    "Manual or ad-hoc refresh\ndoes not inherit the recurring automation authorization: before each manual run,\nobtain explicit owner authorization",
    "Future handoffs must either cite a dated, hash-bound snapshot or instruct the\nincoming agent to run the read-only quality gate and final-root reconciliation.",
    "This is source-level behavior of the inspected runner, not proof that scheduler\nidentity, permissions, execution, or failure handling worked at runtime.",
)
OLD_BLANKET_WORDING = (
    "authorization for each refresh",
    "Prior authorization is consumed",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read(path: Path, root: Path) -> str:
    require(path.is_file(), f"missing_file:{path.relative_to(root).as_posix()}")
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def terminal_normalize(text: str) -> str:
    return text.rstrip("\n") + "\n"


def lf_normalized_utf8_sha256(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest().upper()


def has_graph_context(line: str) -> bool:
    return re.search(r"(?i)\b(?:Graphify|graph|snapshot)\b", line) is not None


def has_snapshot_record(line: str) -> bool:
    graph_context = has_graph_context(line)
    temporal_context = re.search(
        r"(?i)\b(?:current(?:ly)?|latest|most\s+recent)\b", line
    ) is not None
    if not graph_context and not temporal_context:
        return False
    count_field_pattern = r"(?:nodes?|edges?|communities|concepts|counts?)"
    identifier_field_pattern = r"(?:sha-?256|hash|build(?:_commit)?)"
    source_field_pattern = (
        r"(?:manifest[-\s]+sources?|sources|source\s+(?:inventory|count|total)|"
        r"source(?![-\s]+(?:behavior|transcript|content|notes|final)))"
    )
    machine_key_pattern = "(?:" + "|".join(
        re.escape(key) for key, _ in SNAPSHOT_EXPECTED
    ) + ")"
    number_pattern = r"(?:[0-9]+(?:/[0-9]+)*|[0-9A-F]{7,64})"
    count_field = re.search(
        rf"(?i)(?<![-\w]){count_field_pattern}(?![-\w])", line
    )
    identifier_field = re.search(
        rf"(?i)(?<![-\w]){identifier_field_pattern}(?![-\w])", line
    )
    source_field = re.search(
        rf"(?i)(?<![\w]){source_field_pattern}(?![\w])", line
    )
    machine_key = re.search(
        rf"(?i)(?<![\w]){machine_key_pattern}(?![\w])", line
    )
    number = re.search(rf"(?i)(?<![-\w]){number_pattern}(?![-\w])", line)
    hex_identifier = re.search(
        r"(?i)(?<![-\w])(?=[0-9A-F]{7,64}(?![-\w]))(?=[0-9A-F]*[A-F])"
        r"[0-9A-F]{7,64}(?![-\w])",
        line,
    )
    relation_number = re.search(r"(?i)\b(?:is|has|contains)\b\s*`?[0-9]+|[:=]\s*`?[0-9]+", line)
    identifier_machine_key = machine_key is not None and re.search(
        r"(?i)(?:sha256|build_commit)$", machine_key.group(0)
    ) is not None
    recognized_numeric_field = (
        count_field is not None
        or source_field is not None
        or (machine_key is not None and not identifier_machine_key)
    )
    recognized_identifier_field = (
        identifier_field is not None or identifier_machine_key
    )
    if temporal_context and (
        (recognized_numeric_field and number is not None)
        or (recognized_identifier_field and hex_identifier is not None)
    ):
        return True
    return graph_context and (
        (
            (recognized_numeric_field or recognized_identifier_field)
            and number is not None
        )
        or relation_number is not None
    )


def has_positive_runtime_claim(line: str) -> bool:
    if not has_graph_context(line) and re.search(r"(?i)\b(?:scheduler|automation)\b", line) is None:
        return False
    normalized = line.lower()
    if "not runtime proof" in normalized or "not_verified" in normalized:
        return False
    return re.search(
        r"(?i)(?:runtime\s+proof|runtime[_ -]?(?:verified|proved|pass)|"
        r"(?:verified|proved|confirmed)\s+(?:at\s+)?runtime|"
        r"scheduler\s+(?:is\s+)?(?:verified|proved)|execution\s+(?:is\s+)?verified)",
        line,
    ) is not None


def extract_policy(agents: str) -> str:
    require(agents.count(POLICY_HEADING) == 1, f"agents_policy_heading_count:{agents.count(POLICY_HEADING)}")
    return POLICY_HEADING + agents.split(POLICY_HEADING, 1)[1]


def parse_snapshot(path: str, text: str) -> tuple[str, str]:
    pattern = re.compile(r"(?ms)^```graphify-snapshot\n(.*?)\n```$")
    blocks = pattern.findall(text)
    require(len(blocks) == 1, f"snapshot_block_count:{path}:{len(blocks)}")
    block = blocks[0]
    parsed: list[tuple[str, str]] = []
    for line_number, line in enumerate(block.splitlines(), start=1):
        match = re.fullmatch(r"([a-z][a-z0-9_]*)=([^\n=]+)", line)
        require(match is not None, f"snapshot_line_invalid:{path}:{line_number}")
        parsed.append(match.groups())
    require(len(parsed) == len(SNAPSHOT_EXPECTED), f"snapshot_key_count:{path}:{len(parsed)}")
    actual_keys = [key for key, _ in parsed]
    expected_keys = [key for key, _ in SNAPSHOT_EXPECTED]
    require(len(set(actual_keys)) == len(actual_keys), f"snapshot_duplicate_key:{path}")
    unknown = sorted(set(actual_keys) - set(expected_keys))
    require(not unknown, f"snapshot_unknown_keys:{path}:{unknown}")
    missing = sorted(set(expected_keys) - set(actual_keys))
    require(not missing, f"snapshot_missing_keys:{path}:{missing}")
    require(actual_keys == expected_keys, f"snapshot_key_order:{path}")
    for (key, actual), (_, expected) in zip(parsed, SNAPSHOT_EXPECTED, strict=True):
        require(actual == expected, f"snapshot_value_mismatch:{path}:{key}:{actual}")
    full = f"```graphify-snapshot\n{block}\n```"
    outside = text.replace(full, "", 1)
    for line in outside.splitlines():
        require(not has_snapshot_record(line), f"snapshot_record_outside_block:{path}")
    require(
        re.search(r"\b\d+/\d+/\d+/\d+(?:@\d+/\d+)?\b", outside) is None,
        f"historical_snapshot_outside_block:{path}",
    )
    for line in outside.splitlines():
        require(
            not has_positive_runtime_claim(line),
            f"scheduler_runtime_claim_forbidden:{path}",
        )
    return block, outside


def validate(root: Path = ROOT) -> dict[str, object]:
    documents = {path: read(root / path, root) for path in NORMATIVE_PATHS}
    policy = terminal_normalize(extract_policy(documents["AGENTS.md"]))
    claude = terminal_normalize(documents["CLAUDE.md"])
    require(policy == claude, "graphify_policy_drift:AGENTS.md:CLAUDE.md")
    policy_hash = hashlib.sha256(policy.encode("utf-8")).hexdigest().upper()
    require(policy_hash == POLICY_SHA256, f"graphify_policy_hash_mismatch:{policy_hash}")
    for index, fragment in enumerate(POLICY_FRAGMENTS, start=1):
        require(fragment in policy, f"graphify_policy_clause_missing:{index}")
    for wording in OLD_BLANKET_WORDING:
        for path, text in documents.items():
            require(wording.lower() not in text.lower(), f"old_blanket_authorization_wording:{path}:{wording}")
    stale_current = re.compile(
        r"(?i)(?:current|latest)\s+(?:Graphify|snapshot|counts?)[^\n]{0,100}"
        r"(?:242(?:\s+nodes|/258/48/131)|258\s+edges|131\s+concepts)"
    )
    for path, text in documents.items():
        require(stale_current.search(text) is None, f"stale_graphify_current_claim:{path}")
    status_block, _ = parse_snapshot(
        "docs/project/STATUS.md", documents["docs/project/STATUS.md"]
    )
    handoff_block, _ = parse_snapshot(
        "docs/project/HANDOFF.md", documents["docs/project/HANDOFF.md"]
    )
    require(status_block == handoff_block, "snapshot_blocks_drift")
    for path, expected_hash in NORMATIVE_DOCUMENT_SHA256.items():
        actual_hash = lf_normalized_utf8_sha256(documents[path])
        require(
            actual_hash == expected_hash,
            f"normative_document_hash_mismatch:{path}:{actual_hash}",
        )
    snapshot = dict(SNAPSHOT_EXPECTED)
    return {
        "status": "PASS",
        "verification_scope": "PORTABLE_REPOSITORY_GOVERNANCE",
        "scheduler_runtime": "NOT_VERIFIED",
        "policy_sha256": policy_hash,
        "snapshot_timestamp": snapshot["snapshot_timestamp"],
        "snapshot_counts": "/".join(
            snapshot[key]
            for key in (
                "graph_nodes",
                "graph_edges",
                "graph_communities",
                "graph_concepts",
                "manifest_sources",
            )
        ),
        "graph_sha256": snapshot["graph_sha256"],
        "report_sha256": snapshot["report_sha256"],
        "report_build": snapshot["report_build_commit"],
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
