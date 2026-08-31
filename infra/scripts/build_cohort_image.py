"""Submit an immutable Git-object cohort build through the redacted wrapper.

The helper archives the accepted commit, adds a generated per-file SHA-256
manifest, verifies the extracted context, and submits that temporary context in
the same process. It never submits the mutable worktree and never retries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Callable, NamedTuple


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_RELATIVE = Path("infra/cohort-job/build_context_manifest.json")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
HASH64 = re.compile(r"^[0-9a-f]{64}$")
UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
BUILD_TIMEOUT_SECONDS = 3_600

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gcloud_redacted import resolve_project  # noqa: E402
from repoint_cohort_job import (  # noqa: E402
    PROJECT_PLACEHOLDER,
    REDACTED_WRAPPER,
    _run_redacted,
    verify_authoritative_image,
)


class BuildResult(NamedTuple):
    build_id: str
    image_digest: str


def verify_values(
    source_commit: str,
    source_tree: str,
    tag: str,
    context_manifest_sha256: str | None = None,
) -> None:
    if not COMMIT.fullmatch(source_commit):
        raise SystemExit("source_commit_invalid")
    if not COMMIT.fullmatch(source_tree):
        raise SystemExit("source_tree_invalid")
    if tag != source_commit:
        raise SystemExit("image_tag_not_source_commit")
    if (
        context_manifest_sha256 is not None
        and not HASH64.fullmatch(context_manifest_sha256)
    ):
        raise SystemExit("context_manifest_sha256_invalid")


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
        timeout=60, check=False,
    )
    if result.returncode != 0:
        raise SystemExit("git_preflight_failed")
    return result.stdout.strip()


def verify_checkout(
    source_commit: str,
    source_tree: str,
    *,
    git: Callable[..., str] = _git,
) -> dict[str, object]:
    verify_values(source_commit, source_tree, source_commit)
    observed_commit = git("rev-parse", "HEAD")
    observed_tree = git("show", "-s", "--format=%T", "HEAD")
    dirty = bool(git("status", "--porcelain=v1", "--untracked-files=all"))
    checks = {
        "head_matches": observed_commit == source_commit,
        "tree_matches": observed_tree == source_tree,
        "clean": not dirty,
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "verdict": "PASS" if not failures else "FAIL",
        "source_commit": source_commit if checks["head_matches"] else None,
        "source_tree": source_tree if checks["tree_matches"] else None,
        "checks": checks,
        "failures": failures,
    }


def _file_hashes(context: Path) -> dict[str, str]:
    manifest_path = (context / MANIFEST_RELATIVE).resolve()
    values: dict[str, str] = {}
    for path in sorted(item for item in context.rglob("*") if item.is_file()):
        if path.resolve() == manifest_path:
            continue
        values[path.relative_to(context).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    return values


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_context_manifest(context: Path, source_commit: str, source_tree: str) -> Path:
    verify_values(source_commit, source_tree, source_commit)
    path = context / MANIFEST_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {
        "schema_version": "1.0.0",
        "source_commit": source_commit,
        "source_tree": source_tree,
        "files": _file_hashes(context),
    }
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8", newline="\n",
    )
    return path


def verify_context(
    context: Path,
    manifest: Path,
    source_commit: str,
    source_tree: str,
    context_manifest_sha256: str | None = None,
) -> dict[str, object]:
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
        expected_files = value["files"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        raise SystemExit("build_context_manifest_invalid") from None
    valid_shape = (
        isinstance(value, dict)
        and value.get("schema_version") == "1.0.0"
        and value.get("source_commit") == source_commit
        and value.get("source_tree") == source_tree
        and isinstance(expected_files, dict)
        and all(
            isinstance(path, str)
            and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest)
            for path, digest in expected_files.items()
        )
    )
    observed_files = _file_hashes(context)
    files_match = valid_shape and observed_files == expected_files
    manifest_hash_matches = (
        context_manifest_sha256 is None
        or (
            HASH64.fullmatch(context_manifest_sha256) is not None
            and _sha256_file(manifest) == context_manifest_sha256
        )
    )
    passed = files_match and manifest_hash_matches
    return {
        "verdict": "PASS" if passed else "FAIL",
        "source_commit": source_commit if passed else None,
        "source_tree": source_tree if passed else None,
        "file_count": len(observed_files),
        "files_match": files_match,
        "manifest_hash_matches": manifest_hash_matches,
        "failures": (
            []
            if passed
            else [
                code
                for code, failed in (
                    ("build_context_bytes_mismatch", not files_match),
                    ("context_manifest_sha256_mismatch", not manifest_hash_matches),
                )
                if failed
            ]
        ),
    }


def _archive_commit(source_commit: str, destination: Path) -> None:
    archive = destination.parent / "context.tar"
    result = subprocess.run(
        ["git", "archive", "--format=tar", f"--output={archive}", source_commit],
        cwd=ROOT, capture_output=True, text=True, timeout=120, check=False,
    )
    if result.returncode != 0:
        raise SystemExit("git_archive_failed")
    with tarfile.open(archive, mode="r:") as value:
        members = value.getmembers()
        if any(
            member.name.startswith(("/", "../")) or "/../" in member.name
            for member in members
        ):
            raise SystemExit("git_archive_path_invalid")
        value.extractall(destination, filter="data")


def build_submit_args(
    source_commit: str,
    source_tree: str,
    context_manifest_sha256: str,
    context: Path,
) -> list[str]:
    verify_values(
        source_commit, source_tree, source_commit, context_manifest_sha256
    )
    substitutions = (
        f"_TAG={source_commit},_SOURCE_COMMIT={source_commit},"
        f"_SOURCE_TREE={source_tree},"
        f"_CONTEXT_MANIFEST_SHA256={context_manifest_sha256}"
    )
    return [
        "builds", "submit", "--config=infra/cohort-job/cloudbuild.yaml",
        f"--substitutions={substitutions}",
        "--format=json(id,status,substitutions,results.images)",
        str(context),
    ]


def parse_build_result(
    wire: str,
    source_commit: str,
    source_tree: str,
    context_manifest_sha256: str,
) -> BuildResult:
    try:
        value = json.loads(wire)
        build_id = value["id"]
        status = value["status"]
        substitutions = value["substitutions"]
        images = value["results"]["images"]
    except (json.JSONDecodeError, KeyError, TypeError):
        raise SystemExit("build_metadata_invalid") from None
    expected_substitutions = {
        "_TAG": source_commit,
        "_REGION": "us-central1",
        "_REPO": "recall-images",
        "_SOURCE_COMMIT": source_commit,
        "_SOURCE_TREE": source_tree,
        "_CONTEXT_MANIFEST_SHA256": context_manifest_sha256,
    }
    expected_name = (
        f"us-central1-docker.pkg.dev/{PROJECT_PLACEHOLDER}/recall-images/"
        f"recall-cohort-job:{source_commit}"
    )
    if status != "SUCCESS":
        raise SystemExit("build_metadata_status_not_success")
    if not isinstance(build_id, str) or UUID.fullmatch(build_id) is None:
        raise SystemExit("build_metadata_id_invalid")
    if substitutions != expected_substitutions:
        raise SystemExit("build_metadata_substitutions_mismatch")
    if not isinstance(images, list) or len(images) != 1:
        raise SystemExit("build_metadata_image_count_invalid")
    image = images[0]
    if not isinstance(image, dict) or image.get("name") != expected_name:
        raise SystemExit("build_metadata_image_name_mismatch")
    digest = image.get("digest")
    if not isinstance(digest, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None:
        raise SystemExit("build_metadata_digest_invalid")
    return BuildResult(build_id, digest)


def submit(source_commit: str, source_tree: str) -> dict[str, object]:
    checkout = verify_checkout(source_commit, source_tree)
    if checkout["verdict"] != "PASS":
        return checkout
    with tempfile.TemporaryDirectory(prefix="recall-cohort-build-") as temp:
        context = Path(temp) / "context"
        context.mkdir()
        _archive_commit(source_commit, context)
        manifest = write_context_manifest(context, source_commit, source_tree)
        context_manifest_sha256 = _sha256_file(manifest)
        context_report = verify_context(
            context,
            manifest,
            source_commit,
            source_tree,
            context_manifest_sha256,
        )
        if context_report["verdict"] != "PASS":
            return context_report
        result = _run_redacted(
            *build_submit_args(
                source_commit, source_tree, context_manifest_sha256, context
            ),
            timeout_seconds=BUILD_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            return {
                "verdict": "FAIL",
                "source_commit": source_commit,
                "source_tree": source_tree,
                "context_file_bytes_verified": context_report["file_count"],
                "wrapper": REDACTED_WRAPPER.name,
                "build_exit_code": int(result.returncode),
                "build_outcome": "OUTCOME_UNKNOWN",
                "failures": ["build_submit_nonzero"],
                "next_step": (
                    "STOP_READBACK_REQUIRED: do not retry build on nonzero outcome."
                ),
            }
        build = parse_build_result(
            result.stdout,
            source_commit,
            source_tree,
            context_manifest_sha256,
        )
        project = resolve_project()
        authority = verify_authoritative_image(
            project,
            build.build_id,
            build.image_digest,
            source_commit,
            source_tree,
            context_manifest_sha256,
        )
        if authority["verdict"] != "PASS":
            return {
                "verdict": "FAIL",
                "source_commit": source_commit,
                "source_tree": source_tree,
                "context_file_bytes_verified": context_report["file_count"],
                "build_exit_code": 0,
                "build_outcome": "COMPLETED_PROVENANCE_NOT_VERIFIED",
                "failures": list(authority["failures"]),
                "next_step": "STOP_READBACK_REQUIRED: do not repoint.",
            }
    return {
        "verdict": "PASS",
        "source_commit": source_commit,
        "source_tree": source_tree,
        "context_manifest_sha256": context_manifest_sha256,
        "context_file_bytes_verified": context_report["file_count"],
        "wrapper": REDACTED_WRAPPER.name,
        "build_exit_code": 0,
        "build_outcome": "COMPLETED_AND_PROVENANCE_VERIFIED",
        "build_id": build.build_id,
        "pushed_immutable_digest": build.image_digest,
        "build_metadata_matched": True,
        "registry_digest_matched": True,
        "failures": [],
        "next_step": "STOP: repoint requires a separate Director gate.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify-values")
    verify.add_argument("--source-commit", required=True)
    verify.add_argument("--source-tree", required=True)
    verify.add_argument("--tag", required=True)
    verify.add_argument("--context-manifest-sha256", required=True)
    context = sub.add_parser("verify-context")
    context.add_argument("--root", type=Path, required=True)
    context.add_argument("--manifest", type=Path, required=True)
    context.add_argument("--source-commit", required=True)
    context.add_argument("--source-tree", required=True)
    context.add_argument("--context-manifest-sha256", required=True)
    submit_parser = sub.add_parser("submit")
    submit_parser.add_argument("--source-commit", required=True)
    submit_parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()

    if args.command == "verify-values":
        verify_values(
            args.source_commit,
            args.source_tree,
            args.tag,
            args.context_manifest_sha256,
        )
        report = {"verdict": "PASS", "values": "EXACT"}
    elif args.command == "verify-context":
        report = verify_context(
            args.root.resolve(), args.manifest.resolve(),
            args.source_commit, args.source_tree, args.context_manifest_sha256,
        )
    else:
        report = submit(args.source_commit, args.source_tree)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
