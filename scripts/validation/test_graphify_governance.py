"""Disposable-copy mutation tests for Graphify governance."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from verify_graphify_governance import NORMATIVE_PATHS, ROOT, validate


EXPECTED_MUTATION_REJECTIONS = (
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
)


def isolated_root() -> tempfile.TemporaryDirectory[str]:
    temporary = tempfile.TemporaryDirectory(prefix="recall-graphify-governance-")
    root = Path(temporary.name)
    for relative in NORMATIVE_PATHS:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return temporary


def replace(path: str, old: str, new: str) -> Callable[[Path], None]:
    def mutate(root: Path) -> None:
        target = root / path
        text = target.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise AssertionError(f"mutation_target_count:{path}:{old}:{text.count(old)}")
        target.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    return mutate


def append(path: str, value: str) -> Callable[[Path], None]:
    def mutate(root: Path) -> None:
        target = root / path
        target.write_text(target.read_text(encoding="utf-8") + value, encoding="utf-8", newline="\n")

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


def expect_variants(label: str, variants: tuple[str, ...], error: str) -> str:
    for variant in variants:
        expect(label, append("docs/project/STATUS.md", f"\n{variant}\n"), error)
    return label


def replace_both_policy(old: str, new: str) -> Callable[[Path], None]:
    def mutate(root: Path) -> None:
        for path in ("AGENTS.md", "CLAUDE.md"):
            target = root / path
            text = target.read_text(encoding="utf-8")
            if text.count(old) != 1:
                raise AssertionError(f"policy_mutation_target_count:{path}:{text.count(old)}")
            target.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    return mutate


def append_both_policy(value: str) -> Callable[[Path], None]:
    def mutate(root: Path) -> None:
        for path in ("AGENTS.md", "CLAUDE.md"):
            target = root / path
            target.write_text(
                target.read_text(encoding="utf-8").rstrip("\n") + value + "\n",
                encoding="utf-8",
                newline="\n",
            )

    return mutate


def duplicate_snapshot(path: str) -> Callable[[Path], None]:
    def mutate(root: Path) -> None:
        target = root / path
        text = target.read_text(encoding="utf-8")
        start = text.index("```graphify-snapshot")
        end = text.index("\n```", start) + len("\n```")
        block = text[start:end]
        target.write_text(text + "\n" + block + "\n", encoding="utf-8", newline="\n")

    return mutate


def remove_snapshot(path: str) -> Callable[[Path], None]:
    def mutate(root: Path) -> None:
        target = root / path
        text = target.read_text(encoding="utf-8")
        start = text.index("```graphify-snapshot")
        end = text.index("\n```", start) + len("\n```")
        target.write_text(text[:start] + text[end:], encoding="utf-8", newline="\n")

    return mutate


def main() -> None:
    if validate(ROOT)["status"] != "PASS":
        raise AssertionError("baseline_failed")
    status = "docs/project/STATUS.md"
    handoff = "docs/project/HANDOFF.md"
    with isolated_root() as directory:
        portable_root = Path(directory)
        for relative in (status, handoff):
            target = portable_root / relative
            normalized = target.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
            target.write_bytes(normalized.replace("\n", "\r\n").encode("utf-8"))
        if validate(portable_root)["status"] != "PASS":
            raise AssertionError("normative_document_crlf_portability_failed")
    probes = [
        ("policy_drift", replace("CLAUDE.md", "every two hours", "every three hours"), "graphify_policy_drift"),
        ("missing_scope_clause", replace_both_policy("5000-token extraction budget", "extraction budget"), "graphify_policy_hash_mismatch"),
        ("synchronized_scope_expansion", append_both_policy("\nNew supported corpus: all repository files."), "graphify_policy_hash_mismatch"),
        ("old_blanket_wording", append(status, "\nAuthorization for each refresh is required.\n"), "old_blanket_authorization_wording"),
        ("prior_authorization_consumed", append(handoff, "\nPrior authorization is consumed.\n"), "old_blanket_authorization_wording"),
        ("outside_current_254", append(status, "\nCurrent Graphify nodes: 254.\n"), "snapshot_record_outside_block"),
        ("outside_latest_wrong_counts", append(handoff, "\nLatest Graphify counts: 999/998/997/996.\n"), "snapshot_record_outside_block"),
        ("outside_latest_wrong_hash", append(status, "\nLatest Graphify hash: DEADBEEF.\n"), "snapshot_record_outside_block"),
        ("outside_latest_wrong_build", append(handoff, "\nLatest Graphify build: deadbeef.\n"), "snapshot_record_outside_block"),
        ("outside_graph_current_nodes", append(status, "\nThe graph currently has 254 nodes.\n"), "snapshot_record_outside_block"),
        ("outside_counts_before_graph", append(handoff, "\n999 nodes are in the latest graph.\n"), "snapshot_record_outside_block"),
        ("outside_hash_before_graph", append(status, "\nDEADBEEF is the latest graph hash.\n"), "snapshot_record_outside_block"),
        ("outside_build_before_graph", append(handoff, "\nc8be1947 identifies the latest graph build.\n"), "snapshot_record_outside_block"),
        ("outside_sources_before_graph", append(status, "\n75/75 is the documented manifest coverage for the latest graph sources.\n"), "snapshot_record_outside_block"),
        ("snapshot_value_replacement", replace(status, "graph_nodes=254", "graph_nodes=255"), "snapshot_value_mismatch"),
        ("historical_key_rewrite", replace(handoff, "historical_snapshots=240/260/44/129;231/248/45/120;242/258/48/131@74/74", "historical_snapshots=1/2/3/4"), "snapshot_value_mismatch"),
        ("runtime_proof_addition", append(status, "\nGraphify scheduler runtime verified.\n"), "scheduler_runtime_claim_forbidden"),
        ("runtime_proof_before_graph", append(handoff, "\nRuntime proof confirms the Graphify scheduler.\n"), "scheduler_runtime_claim_forbidden"),
        ("duplicate_snapshot_block", duplicate_snapshot(status), "snapshot_block_count"),
        ("missing_snapshot_block", remove_snapshot(handoff), "snapshot_block_count"),
        ("duplicate_snapshot_key", replace(status, "missing_sources=0", "graph_nodes=0"), "snapshot_duplicate_key"),
        ("unknown_snapshot_key", replace(handoff, "missing_sources=0", "unknown_sources=0"), "snapshot_unknown_keys"),
        ("reordered_snapshot_keys", replace(status, "graph_nodes=254\ngraph_edges=276", "graph_edges=276\ngraph_nodes=254"), "snapshot_key_order"),
        ("malformed_snapshot_line", replace(handoff, "graph_nodes=254", "graph_nodes==254"), "snapshot_line_invalid"),
    ]
    variant_probes = [
        (
            "outside_source_count_before_graph",
            (
                "75 manifest sources are represented in the latest graph.",
                "The latest graph includes 75 sources.",
                "Manifest-source total for the latest graph is 75.",
            ),
            "snapshot_record_outside_block",
        ),
    ]
    rejected = [expect(label, mutate, error) for label, mutate, error in probes]
    rejected.extend(
        expect_variants(label, variants, error)
        for label, variants, error in variant_probes
    )
    context_omission_probes = [
        ("outside_latest_nodes_without_graph", "Latest nodes:254"),
        ("outside_current_source_coverage_without_graph", "Current source coverage 75/75"),
        ("outside_latest_manifest_source_total_without_graph", "Latest manifest-source total 75"),
        ("outside_current_build_without_graph", "Current build c8be1947"),
        ("outside_latest_hash_without_graph", "Latest hash DEADBEEF"),
    ]
    rejected.extend(
        expect(
            label,
            append("docs/project/STATUS.md", f"\n{line}\n"),
            "snapshot_record_outside_block",
        )
        for label, line in context_omission_probes
    )
    machine_key_probes = [
        ("outside_latest_graph_nodes_machine_key", "Latest graph_nodes=254."),
        ("outside_graph_nodes_machine_key_current_after", "graph_nodes=254 is current."),
        ("outside_current_manifest_sources_machine_key", "Current manifest_sources=75/75."),
        ("outside_manifest_sources_machine_key_latest_after", "manifest_sources=75/75 latest."),
        ("outside_latest_report_build_commit_machine_key", "Latest report_build_commit=c8be1947."),
        ("outside_current_graph_sha256_machine_key", "Current graph_sha256=DEADBEEF."),
        ("outside_currently_nodes_relation", "There are currently 254 nodes."),
        ("outside_nodes_currently_total_relation", "Nodes currently total 254."),
        ("outside_most_recent_node_total_relation", "The most recent node total is 254."),
    ]
    rejected.extend(
        expect(
            label,
            append("docs/project/STATUS.md", f"\n{line}\n"),
            "snapshot_record_outside_block",
        )
        for label, line in machine_key_probes
    )
    hash_fallback_probes = [
        (
            "status_unrelated_line_hash_fallback",
            replace(status, "## Current risks", "## Current project risks"),
            "normative_document_hash_mismatch:docs/project/STATUS.md",
        ),
        (
            "handoff_unrelated_line_hash_fallback",
            replace(handoff, "## Current objective", "## Present objective"),
            "normative_document_hash_mismatch:docs/project/HANDOFF.md",
        ),
    ]
    rejected.extend(
        expect(label, mutate, error)
        for label, mutate, error in hash_fallback_probes
    )
    if tuple(rejected) != EXPECTED_MUTATION_REJECTIONS:
        raise AssertionError(f"mutation_label_set:{rejected}")
    print(
        json.dumps(
            {
                "status": "PASS",
                "mutation_rejections": rejected,
                "positive_controls": ["normative_document_crlf_portability"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
