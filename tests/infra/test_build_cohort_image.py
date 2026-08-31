from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "infra" / "scripts" / "build_cohort_image.py"
SOURCE_COMMIT = "b" * 40
SOURCE_TREE = "c" * 40
CONTEXT_SHA = "d" * 64
BUILD_ID = "12345678-1234-1234-1234-1234567890ab"
IMAGE_DIGEST = "sha256:" + "a" * 64
PROJECT = "project-canary-123"


def _load_build():
    spec = importlib.util.spec_from_file_location("build_cohort_image", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exact_clean_checkout_is_required() -> None:
    build = _load_build()

    def git(*args: str) -> str:
        values = {
            ("rev-parse", "HEAD"): SOURCE_COMMIT,
            ("show", "-s", "--format=%T", "HEAD"): SOURCE_TREE,
            ("status", "--porcelain=v1", "--untracked-files=all"): "",
        }
        return values[args]

    report = build.verify_checkout(SOURCE_COMMIT, SOURCE_TREE, git=git)

    assert report["verdict"] == "PASS"
    assert report["checks"] == {
        "head_matches": True,
        "tree_matches": True,
        "clean": True,
    }


def test_dirty_or_mismatched_checkout_fails_closed() -> None:
    build = _load_build()

    def git(*args: str) -> str:
        values = {
            ("rev-parse", "HEAD"): "d" * 40,
            ("show", "-s", "--format=%T", "HEAD"): "e" * 40,
            ("status", "--porcelain=v1", "--untracked-files=all"): " M src/file.py",
        }
        return values[args]

    report = build.verify_checkout(SOURCE_COMMIT, SOURCE_TREE, git=git)

    assert report["verdict"] == "FAIL"
    assert report["source_commit"] is None
    assert report["source_tree"] is None
    assert report["failures"] == ["head_matches", "tree_matches", "clean"]


def test_build_substitutions_bind_tag_commit_tree_and_immutable_context() -> None:
    build = _load_build()
    context = Path("C:/safe/immutable-context")

    args = build.build_submit_args(
        SOURCE_COMMIT, SOURCE_TREE, CONTEXT_SHA, context
    )

    assert args == [
        "builds",
        "submit",
        "--config=infra/cohort-job/cloudbuild.yaml",
        "--substitutions="
        f"_TAG={SOURCE_COMMIT},_SOURCE_COMMIT={SOURCE_COMMIT},"
        f"_SOURCE_TREE={SOURCE_TREE},_CONTEXT_MANIFEST_SHA256={CONTEXT_SHA}",
        "--format=json(id,status,substitutions,results.images)",
        str(context),
    ]


def _build_wire(
    *,
    status: str = "SUCCESS",
    digest: str = IMAGE_DIGEST,
    name: str | None = None,
    images: list[dict[str, str]] | None = None,
    substitutions: dict[str, str] | None = None,
) -> str:
    fixed_substitutions = {
        "_TAG": SOURCE_COMMIT,
        "_REGION": "us-central1",
        "_REPO": "recall-images",
        "_SOURCE_COMMIT": SOURCE_COMMIT,
        "_SOURCE_TREE": SOURCE_TREE,
        "_CONTEXT_MANIFEST_SHA256": CONTEXT_SHA,
    }
    return json.dumps(
        {
            "id": BUILD_ID,
            "status": status,
            "substitutions": substitutions or fixed_substitutions,
            "results": {
                "images": images
                if images is not None
                else [
                    {
                        "name": name
                        or "us-central1-docker.pkg.dev/<project>/recall-images/"
                        f"recall-cohort-job:{SOURCE_COMMIT}",
                        "digest": digest,
                    }
                ]
            },
        }
    )


def test_build_result_requires_exact_authoritative_image_identity() -> None:
    build = _load_build()

    claim = build.parse_build_result(
        _build_wire(), SOURCE_COMMIT, SOURCE_TREE, CONTEXT_SHA
    )

    assert claim.build_id == BUILD_ID
    assert claim.image_digest == IMAGE_DIGEST

    bad_wires = (
        _build_wire(status="FAILURE"),
        _build_wire(images=[]),
        _build_wire(
            images=[
                {"name": "wrong", "digest": IMAGE_DIGEST},
                {"name": "wrong2", "digest": IMAGE_DIGEST},
            ]
        ),
        _build_wire(name="us-central1-docker.pkg.dev/<project>/other/job:bad"),
        _build_wire(digest="not-a-digest"),
        _build_wire(substitutions={"_SOURCE_COMMIT": SOURCE_COMMIT}),
    )
    for wire in bad_wires:
        try:
            build.parse_build_result(wire, SOURCE_COMMIT, SOURCE_TREE, CONTEXT_SHA)
        except SystemExit as exc:
            assert str(exc).startswith("build_metadata_")
        else:
            raise AssertionError("invalid authoritative build metadata accepted")


def test_build_result_accepts_actual_wrapper_scrub_output() -> None:
    build = _load_build()
    wrapper = sys.modules["gcloud_redacted"]
    raw = _build_wire(
        name=(
            f"us-central1-docker.pkg.dev/{PROJECT}/recall-images/"
            f"recall-cohort-job:{SOURCE_COMMIT}"
        )
    )

    claim = build.parse_build_result(
        wrapper.scrub(raw, PROJECT, None, None),
        SOURCE_COMMIT,
        SOURCE_TREE,
        CONTEXT_SHA,
    )

    assert claim.image_digest == IMAGE_DIGEST


def test_dev_or_mismatched_tag_is_rejected() -> None:
    build = _load_build()

    for tag in ("dev", "d" * 40):
        try:
            build.verify_values(SOURCE_COMMIT, SOURCE_TREE, tag)
        except SystemExit as exc:
            assert str(exc) == "image_tag_not_source_commit"
        else:
            raise AssertionError("mismatched tag accepted")


def test_context_manifest_binds_every_file_and_rejects_mutation(tmp_path: Path) -> None:
    build = _load_build()
    context = tmp_path / "context"
    (context / "src").mkdir(parents=True)
    (context / "src" / "one.py").write_text("one\n", encoding="utf-8")
    (context / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

    manifest = build.write_context_manifest(context, SOURCE_COMMIT, SOURCE_TREE)
    passed = build.verify_context(
        context, manifest, SOURCE_COMMIT, SOURCE_TREE
    )
    (context / "src" / "one.py").write_text("mutated\n", encoding="utf-8")
    failed = build.verify_context(
        context, manifest, SOURCE_COMMIT, SOURCE_TREE
    )

    assert passed["verdict"] == "PASS"
    assert passed["file_count"] == 2
    assert failed["verdict"] == "FAIL"
    assert failed["failures"] == ["build_context_bytes_mismatch"]


def test_context_manifest_rejects_extra_ignored_like_file(tmp_path: Path) -> None:
    build = _load_build()
    context = tmp_path / "context"
    context.mkdir()
    (context / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    manifest = build.write_context_manifest(context, SOURCE_COMMIT, SOURCE_TREE)
    (context / "ignored.pyc").write_bytes(b"ignored")

    report = build.verify_context(context, manifest, SOURCE_COMMIT, SOURCE_TREE)

    assert report["verdict"] == "FAIL"


def test_cloud_build_contract_steps_disable_bytecode_and_preserve_context(
    tmp_path: Path,
) -> None:
    build = _load_build()
    cloudbuild = (ROOT / "infra" / "cohort-job" / "cloudbuild.yaml").read_text(
        encoding="utf-8"
    )
    assert cloudbuild.count("PYTHONDONTWRITEBYTECODE=1") == 2

    context = tmp_path / "context"
    scripts = context / "infra" / "scripts"
    scripts.mkdir(parents=True)
    for name in ("build_cohort_image.py", "repoint_cohort_job.py", "gcloud_redacted.py"):
        shutil.copy2(ROOT / "infra" / "scripts" / name, scripts / name)
    manifest = build.write_context_manifest(context, SOURCE_COMMIT, SOURCE_TREE)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [
            sys.executable,
            str(scripts / "build_cohort_image.py"),
            "verify-values",
            f"--source-commit={SOURCE_COMMIT}",
            f"--source-tree={SOURCE_TREE}",
            f"--tag={SOURCE_COMMIT}",
            f"--context-manifest-sha256={build._sha256_file(manifest)}",
        ],
        cwd=context,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert completed.returncode == 0
    assert not tuple(context.rglob("*.pyc"))
    assert build.verify_context(
        context, manifest, SOURCE_COMMIT, SOURCE_TREE
    )["verdict"] == "PASS"


def test_build_submit_uses_separate_bounded_timeout(monkeypatch) -> None:
    build = _load_build()
    calls: list[tuple[tuple[str, ...], int]] = []

    class Result:
        returncode = 0
        stdout = _build_wire()

    monkeypatch.setattr(build, "verify_checkout", lambda *_args: {"verdict": "PASS"})
    monkeypatch.setattr(build, "_archive_commit", lambda *_args: None)
    monkeypatch.setattr(
        build,
        "write_context_manifest",
        lambda context, *_args: context / build.MANIFEST_RELATIVE,
    )
    monkeypatch.setattr(
        build,
        "verify_context",
        lambda *_args: {"verdict": "PASS", "file_count": 7},
    )
    monkeypatch.setattr(build, "_sha256_file", lambda _path: CONTEXT_SHA)
    monkeypatch.setattr(
        build,
        "verify_authoritative_image",
        lambda *_args, **_kwargs: {
            "verdict": "PASS",
            "build_metadata_matched": True,
            "registry_digest_matched": True,
            "failures": [],
        },
    )
    monkeypatch.setattr(build, "resolve_project", lambda: "project-canary-123")

    def run(*args: str, timeout_seconds: int):
        calls.append((args, timeout_seconds))
        return Result()

    monkeypatch.setattr(build, "_run_redacted", run)

    report = build.submit(SOURCE_COMMIT, SOURCE_TREE)

    assert report["verdict"] == "PASS"
    assert report["context_file_bytes_verified"] == 7
    assert report["pushed_immutable_digest"] == IMAGE_DIGEST
    assert report["build_id"] == BUILD_ID
    assert calls[0][1] == build.BUILD_TIMEOUT_SECONDS


def test_cloudbuild_uses_one_automatic_push_and_no_explicit_push() -> None:
    cloudbuild = (ROOT / "infra" / "cohort-job" / "cloudbuild.yaml").read_text(
        encoding="utf-8"
    )

    assert "\nimages:\n" in cloudbuild
    assert "- id: push" not in cloudbuild
    assert "\n      - push\n" not in cloudbuild
