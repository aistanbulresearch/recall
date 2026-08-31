from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "infra" / "cohort-job" / "Dockerfile"
CONTRACT_PATH = ROOT / "infra" / "cohort-job" / "runtime_contract.py"
INVENTORY_PATH = ROOT / "infra" / "cohort-job" / "dependency_inventory.py"
SOURCE_COMMIT = "b" * 40
SOURCE_TREE = "c" * 40


def _load_contract():
    spec = importlib.util.spec_from_file_location("cohort_runtime_contract", CONTRACT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_inventory():
    spec = importlib.util.spec_from_file_location(
        "cohort_dependency_inventory", INVENTORY_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dockerfile_locks_critical_runtime_and_runs_contract_before_push() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    cloudbuild = (ROOT / "infra" / "cohort-job" / "cloudbuild.yaml").read_text(
        encoding="utf-8"
    )
    uv_wheel = (
        "uv-0.12.3-py3-none-manylinux_2_17_x86_64."
        "manylinux2014_x86_64.whl"
    )
    uv_sha256 = "1482d1462b1aecd18ee33627363fe1c63d6a194f12d40d37efc446d9e0d800a1"
    assert uv_wheel in dockerfile
    assert f"#sha256={uv_sha256}" in dockerfile
    assert "pip install --no-cache-dir --no-deps" in dockerfile
    assert "uv sync --locked --no-dev --no-install-project" in dockerfile
    assert "/app/.venv/bin/python -m pip check" in dockerfile
    assert "VIRTUAL_ENV=/app/.venv" in dockerfile
    assert "PATH=/app/.venv/bin" in dockerfile
    assert "COPY infra/cohort-job/runtime_contract.py" in dockerfile
    assert "COPY infra/cohort-job/dependency_inventory.py" in dockerfile
    assert "COPY infra/cohort-job/build_context_manifest.json" in dockerfile
    assert (
        'ENTRYPOINT ["/app/.venv/bin/python", "-m", '
        '"recall.scheduler.entrypoint"]' in dockerfile
    )
    assert "--entrypoint=/app/.venv/bin/python" in cloudbuild
    assert "/app/infra/cohort-job/runtime_contract.py" in cloudbuild
    assert "\nimages:\n" in cloudbuild
    assert "id: push" not in cloudbuild
    assert "gcloud builds submit" not in cloudbuild
    assert "SET_EXACT_SOURCE_COMMIT" in cloudbuild
    assert "--build-arg=RECALL_SOURCE_COMMIT=${_SOURCE_COMMIT}" in cloudbuild
    assert "--build-arg=RECALL_SOURCE_TREE=${_SOURCE_TREE}" in cloudbuild


def test_runtime_contract_passes_only_for_exact_candidate() -> None:
    contract = _load_contract()

    report = contract.collect_contract(
        version_getter=lambda name: contract.EXPECTED_PACKAGES[name],
        runtime_loader=lambda: contract.RuntimeValues(
            full_audit_concurrency=2,
            max_model_turns_per_role=2,
            cost_policy_sha256=contract.EXPECTED_COST_POLICY_SHA256,
            cost_policy_matches=True,
        ),
        provenance_loader=lambda: contract.BuildProvenance(SOURCE_COMMIT, SOURCE_TREE),
        inventory_loader=lambda: contract.DependencyInventoryValues(
            matches=True,
            inventory_sha256="d" * 64,
            package_count=88,
            interpreter_matches=True,
        ),
        expected_source_commit=SOURCE_COMMIT,
        expected_source_tree=SOURCE_TREE,
    )

    assert report["verdict"] == "PASS"
    assert report["evidence_status"] == "STRUCTURALLY_VERIFIED"
    assert report["runtime"]["full_audit_concurrency"] == 2
    assert report["runtime"]["max_model_turns_per_role"] == 2
    assert report["runtime"]["cost_policy_matches"] is True
    assert report["failures"] == []


def test_runtime_contract_output_is_allowlisted_and_contains_no_canaries() -> None:
    contract = _load_contract()
    canaries = (
        "project-canary-123",
        "123456789012",
        "owner@example.invalid",
        "runtime@example.invalid",
        "billing-canary-456",
        "secret-canary-789",
        "token-canary-abc",
    )

    report = contract.collect_contract(
        version_getter=lambda name: contract.EXPECTED_PACKAGES[name],
        runtime_loader=lambda: contract.RuntimeValues(2, 2, "wrong-policy", False),
        provenance_loader=lambda: contract.BuildProvenance(SOURCE_COMMIT, SOURCE_TREE),
        inventory_loader=lambda: contract.DependencyInventoryValues(
            True, "d" * 64, 88, True
        ),
        expected_source_commit=SOURCE_COMMIT,
        expected_source_tree=SOURCE_TREE,
    )
    rendered = json.dumps(report, sort_keys=True)

    assert set(report) == {
        "schema_version",
        "verdict",
        "evidence_status",
        "packages",
        "runtime",
        "checks",
        "failures",
    }
    assert all(canary not in rendered for canary in canaries)
    assert "hard_cap_usd_micros" not in rendered
    assert report["verdict"] == "FAIL"
    assert report["failures"] == ["cost_policy_mismatch"]


def test_current_accepted_integrated_core_passes_contract() -> None:
    contract = _load_contract()

    report = contract.collect_contract(
        provenance_loader=lambda: contract.BuildProvenance(SOURCE_COMMIT, SOURCE_TREE),
        inventory_loader=lambda: contract.DependencyInventoryValues(
            True, "d" * 64, 88, True
        ),
        expected_source_commit=SOURCE_COMMIT,
        expected_source_tree=SOURCE_TREE,
    )

    assert report["verdict"] == "PASS"
    assert report["failures"] == []
    assert report["checks"] == {
        "package_versions": True,
        "full_audit_concurrency": True,
        "max_model_turns_per_role": True,
        "cost_policy": True,
        "build_provenance": True,
        "dependency_inventory": True,
        "runtime_interpreter": True,
    }


def test_runtime_contract_rejects_mismatched_build_provenance_without_leak() -> None:
    contract = _load_contract()

    report = contract.collect_contract(
        version_getter=lambda name: contract.EXPECTED_PACKAGES[name],
        runtime_loader=lambda: contract.RuntimeValues(
            2, 2, contract.EXPECTED_COST_POLICY_SHA256, True
        ),
        provenance_loader=lambda: contract.BuildProvenance(
            "secret-canary-789", "project-canary-123"
        ),
        inventory_loader=lambda: contract.DependencyInventoryValues(
            True, "d" * 64, 88, True
        ),
        expected_source_commit=SOURCE_COMMIT,
        expected_source_tree=SOURCE_TREE,
    )
    rendered = json.dumps(report, sort_keys=True)

    assert report["failures"] == ["build_provenance_mismatch"]
    assert "secret-canary-789" not in rendered
    assert "project-canary-123" not in rendered


def test_runtime_contract_rejects_dependency_or_interpreter_drift() -> None:
    contract = _load_contract()

    report = contract.collect_contract(
        version_getter=lambda name: contract.EXPECTED_PACKAGES[name],
        runtime_loader=lambda: contract.RuntimeValues(
            2, 2, contract.EXPECTED_COST_POLICY_SHA256, True
        ),
        provenance_loader=lambda: contract.BuildProvenance(
            SOURCE_COMMIT, SOURCE_TREE
        ),
        inventory_loader=lambda: contract.DependencyInventoryValues(
            False, None, 89, False
        ),
        expected_source_commit=SOURCE_COMMIT,
        expected_source_tree=SOURCE_TREE,
    )

    assert report["verdict"] == "FAIL"
    assert report["failures"] == [
        "dependency_inventory_mismatch",
        "runtime_interpreter_mismatch",
    ]
    assert report["runtime"]["dependency_inventory_sha256"] is None


def test_malformed_provenance_root_is_typed_missing(tmp_path: Path) -> None:
    contract = _load_contract()
    path = tmp_path / "manifest.json"
    path.write_text('["secret-canary-789"]', encoding="utf-8")
    original = contract.PROVENANCE_PATH
    contract.PROVENANCE_PATH = str(path)
    try:
        assert contract._load_build_provenance() == contract.BuildProvenance(None, None)
    finally:
        contract.PROVENANCE_PATH = original


def test_dependency_inventory_binds_lock_interpreter_and_every_distribution(
    tmp_path: Path,
) -> None:
    inventory = _load_inventory()
    lock = tmp_path / "uv.lock"
    manifest = tmp_path / "inventory.json"
    lock.write_text("locked\n", encoding="utf-8")
    packages = {"alpha": "1.0", "beta": "2.0"}

    value = inventory.write_inventory(
        lock,
        manifest,
        executable="/app/.venv/bin/python",
        python_version="3.12.0",
        packages=packages,
    )
    verified = inventory.verify_inventory(
        lock,
        manifest,
        expected_executable="/app/.venv/bin/python",
        executable="/app/.venv/bin/python",
        python_version="3.12.0",
        packages=packages,
    )

    assert value["package_count"] == 2
    assert verified["matches"] is True
    assert verified["inventory_sha256"] == value["inventory_sha256"]

    variants = (
        ({"alpha": "1.1", "beta": "2.0"}, "/app/.venv/bin/python"),
        ({"alpha": "1.0"}, "/app/.venv/bin/python"),
        ({"alpha": "1.0", "beta": "2.0", "gamma": "3.0"}, "/app/.venv/bin/python"),
        (packages, "/usr/local/bin/python"),
    )
    for changed_packages, executable in variants:
        report = inventory.verify_inventory(
            lock,
            manifest,
            expected_executable="/app/.venv/bin/python",
            executable=executable,
            python_version="3.12.0",
            packages=changed_packages,
        )
        assert report["matches"] is False

    lock.write_text("drifted\n", encoding="utf-8")
    assert inventory.verify_inventory(
        lock,
        manifest,
        expected_executable="/app/.venv/bin/python",
        executable="/app/.venv/bin/python",
        python_version="3.12.0",
        packages=packages,
    )["matches"] is False
