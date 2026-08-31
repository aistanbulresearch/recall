"""Emit a non-sensitive contract for the exact built cohort image.

This module is an image-build gate, not a scheduler entrypoint. It intentionally
fails against an unaccepted L2 core: the final image must export the named
two-turn contract and must report the accepted concurrency before it can be
pushed or repointed.
"""

from __future__ import annotations

import json
import platform
import re
import sys
import argparse
from importlib import metadata
from pathlib import Path
from typing import Callable, NamedTuple


EXPECTED_PACKAGES = {
    "google-adk": "2.7.1",
    "google-cloud-aiplatform": "1.165.1",
    "google-cloud-firestore": "2.28.1",
    "pydantic": "2.13.4",
    "google-genai": "2.19.0",
    "opentelemetry-api": "1.42.1",
    "opentelemetry-sdk": "1.42.1",
    "tenacity": "9.1.4",
}
EXPECTED_CONCURRENCY = 2
EXPECTED_MAX_MODEL_TURNS_PER_ROLE = 2
EXPECTED_COST_POLICY_SHA256 = (
    "2c0e664a66707e30b536fade39cf36ce6a7ca556be7633051722fb0ae1312703"
)
EXPECTED_COST_POLICY_FIELDS = {
    "max_request_bytes_per_turn": 16_384,
    "max_output_tokens_per_turn": 2_048,
    "hard_cap_usd_micros": 75_000_000,
}
PROVENANCE_PATH = "/app/infra/cohort-job/build_context_manifest.json"
DEPENDENCY_INVENTORY_PATH = "/app/infra/cohort-job/dependency_inventory.json"
UV_LOCK_PATH = "/app/uv.lock"
EXPECTED_EXECUTABLE = "/app/.venv/bin/python"
COMMIT = re.compile(r"^[0-9a-f]{40}$")


class RuntimeValues(NamedTuple):
    full_audit_concurrency: int | None
    max_model_turns_per_role: int | None
    cost_policy_sha256: str | None
    cost_policy_matches: bool


class BuildProvenance(NamedTuple):
    source_commit: str | None
    source_tree: str | None


class DependencyInventoryValues(NamedTuple):
    matches: bool
    inventory_sha256: str | None
    package_count: int
    interpreter_matches: bool


def _load_build_provenance() -> BuildProvenance:
    from pathlib import Path

    try:
        value = json.loads(Path(PROVENANCE_PATH).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return BuildProvenance(None, None)
    except (OSError, json.JSONDecodeError, TypeError):
        return BuildProvenance(None, None)
    commit = value.get("source_commit")
    tree = value.get("source_tree")
    return BuildProvenance(
        commit if isinstance(commit, str) and COMMIT.fullmatch(commit) else None,
        tree if isinstance(tree, str) and COMMIT.fullmatch(tree) else None,
    )


def _load_runtime_values() -> RuntimeValues:
    from recall.agents import full_audit_models
    from recall.scheduler.full_audit_phase import FULL_AUDIT_CONCURRENCY
    from recall.scheduler.model_cost import DEFAULT_MODEL_COST_POLICY

    turns = getattr(full_audit_models, "MAX_MODEL_TURNS_PER_ROLE", None)
    policy = DEFAULT_MODEL_COST_POLICY
    policy_matches = (
        policy.sha256 == EXPECTED_COST_POLICY_SHA256
        and all(
            getattr(policy, name, None) == expected
            for name, expected in EXPECTED_COST_POLICY_FIELDS.items()
        )
    )
    return RuntimeValues(
        full_audit_concurrency=FULL_AUDIT_CONCURRENCY,
        max_model_turns_per_role=turns,
        cost_policy_sha256=policy.sha256,
        cost_policy_matches=policy_matches,
    )


def _load_dependency_inventory() -> DependencyInventoryValues:
    import dependency_inventory

    value = dependency_inventory.verify_inventory(
        Path(UV_LOCK_PATH),
        Path(DEPENDENCY_INVENTORY_PATH),
        expected_executable=EXPECTED_EXECUTABLE,
        executable=sys.executable.replace("\\", "/"),
        python_version=platform.python_version(),
        packages={
            distribution.metadata["Name"]: distribution.version
            for distribution in metadata.distributions()
            if distribution.metadata.get("Name")
        },
    )
    return DependencyInventoryValues(
        matches=bool(value["matches"]),
        inventory_sha256=(
            str(value["inventory_sha256"])
            if value["inventory_sha256"] is not None
            else None
        ),
        package_count=int(value["package_count"]),
        interpreter_matches=bool(value["interpreter_matches"]),
    )


def collect_contract(
    *,
    version_getter: Callable[[str], str] = metadata.version,
    runtime_loader: Callable[[], RuntimeValues] = _load_runtime_values,
    provenance_loader: Callable[[], BuildProvenance] = _load_build_provenance,
    inventory_loader: Callable[[], DependencyInventoryValues] = (
        _load_dependency_inventory
    ),
    expected_source_commit: str | None = None,
    expected_source_tree: str | None = None,
) -> dict[str, object]:
    """Collect only allowlisted versions, booleans, constants, and failure codes."""

    failures: list[str] = []
    packages: dict[str, str | None] = {}
    package_checks: dict[str, bool] = {}
    for name, expected in EXPECTED_PACKAGES.items():
        try:
            observed = version_getter(name)
        except metadata.PackageNotFoundError:
            observed = None
        packages[name] = observed
        package_checks[name] = observed == expected
        if observed is None:
            failures.append(f"package_missing:{name}")
        elif observed != expected:
            failures.append(f"package_version_mismatch:{name}")

    try:
        runtime = runtime_loader()
    except Exception:  # noqa: BLE001 - emit a typed, non-sensitive build failure
        runtime = RuntimeValues(None, None, None, False)
        failures.append("runtime_contract_load_failed")

    if runtime.full_audit_concurrency != EXPECTED_CONCURRENCY:
        failures.append("full_audit_concurrency_mismatch")
    if runtime.max_model_turns_per_role is None:
        failures.append("max_model_turns_contract_missing")
    elif runtime.max_model_turns_per_role != EXPECTED_MAX_MODEL_TURNS_PER_ROLE:
        failures.append("max_model_turns_mismatch")
    if not runtime.cost_policy_matches:
        failures.append("cost_policy_mismatch")

    provenance = provenance_loader()
    provenance_matches = (
        expected_source_commit is not None
        and expected_source_tree is not None
        and COMMIT.fullmatch(expected_source_commit) is not None
        and COMMIT.fullmatch(expected_source_tree) is not None
        and provenance.source_commit == expected_source_commit
        and provenance.source_tree == expected_source_tree
    )
    if not provenance_matches:
        failures.append("build_provenance_mismatch")

    try:
        inventory = inventory_loader()
    except Exception:  # noqa: BLE001 - typed, non-sensitive image-build failure
        inventory = DependencyInventoryValues(False, None, 0, False)
    if not inventory.matches:
        failures.append("dependency_inventory_mismatch")
    if not inventory.interpreter_matches:
        failures.append("runtime_interpreter_mismatch")

    checks = {
        "package_versions": all(package_checks.values()),
        "full_audit_concurrency": (
            runtime.full_audit_concurrency == EXPECTED_CONCURRENCY
        ),
        "max_model_turns_per_role": (
            runtime.max_model_turns_per_role == EXPECTED_MAX_MODEL_TURNS_PER_ROLE
        ),
        "cost_policy": runtime.cost_policy_matches,
        "build_provenance": provenance_matches,
        "dependency_inventory": inventory.matches,
        "runtime_interpreter": inventory.interpreter_matches,
    }
    verdict = "PASS" if not failures else "FAIL"
    return {
        "schema_version": "1.0.0",
        "verdict": verdict,
        "evidence_status": (
            "STRUCTURALLY_VERIFIED" if verdict == "PASS" else "NOT_VERIFIED"
        ),
        "packages": packages,
        "runtime": {
            "full_audit_concurrency": runtime.full_audit_concurrency,
            "max_model_turns_per_role": runtime.max_model_turns_per_role,
            "cost_policy_sha256": (
                EXPECTED_COST_POLICY_SHA256
                if runtime.cost_policy_sha256 == EXPECTED_COST_POLICY_SHA256
                else None
            ),
            "cost_policy_matches": runtime.cost_policy_matches,
            "source_commit": (
                expected_source_commit if provenance_matches else None
            ),
            "source_tree": expected_source_tree if provenance_matches else None,
            "dependency_inventory_sha256": (
                inventory.inventory_sha256 if inventory.matches else None
            ),
            "dependency_package_count": inventory.package_count,
            "runtime_interpreter_matches": inventory.interpreter_matches,
        },
        "checks": checks,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect-source-commit", required=True)
    parser.add_argument("--expect-source-tree", required=True)
    args = parser.parse_args()
    report = collect_contract(
        expected_source_commit=args.expect_source_commit,
        expected_source_tree=args.expect_source_tree,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
