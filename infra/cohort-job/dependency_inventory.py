"""Bind an image's installed Python environment to its exact lock bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sys
from importlib import metadata
from pathlib import Path
from typing import Mapping


SCHEMA_VERSION = "1.0.0"
NAME_SEPARATOR = re.compile(r"[-_.]+")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_name(value: str) -> str:
    return NAME_SEPARATOR.sub("-", value).lower()


def _installed_packages() -> dict[str, str]:
    packages: dict[str, str] = {}
    for distribution in metadata.distributions():
        name = distribution.metadata.get("Name")
        if not isinstance(name, str) or not name:
            continue
        canonical = _canonical_name(name)
        if canonical in packages and packages[canonical] != distribution.version:
            raise SystemExit("installed_distribution_duplicate")
        packages[canonical] = distribution.version
    return packages


def _identity(
    lock_path: Path,
    *,
    executable: str,
    python_version: str,
    packages: Mapping[str, str],
) -> dict[str, object]:
    try:
        lock_sha256 = _sha256_bytes(lock_path.read_bytes())
    except OSError:
        raise SystemExit("dependency_lock_unreadable") from None
    canonical_packages = {
        _canonical_name(str(name)): str(version)
        for name, version in packages.items()
    }
    if len(canonical_packages) != len(packages):
        raise SystemExit("installed_distribution_duplicate")
    return {
        "schema_version": SCHEMA_VERSION,
        "lock_sha256": lock_sha256,
        "executable": executable.replace("\\", "/"),
        "python_version": python_version,
        "packages": dict(sorted(canonical_packages.items())),
    }


def _inventory_sha256(identity: Mapping[str, object]) -> str:
    wire = json.dumps(
        identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return _sha256_bytes(wire)


def write_inventory(
    lock_path: Path,
    manifest_path: Path,
    *,
    executable: str,
    python_version: str,
    packages: Mapping[str, str],
) -> dict[str, object]:
    identity = _identity(
        lock_path,
        executable=executable,
        python_version=python_version,
        packages=packages,
    )
    value = {
        **identity,
        "package_count": len(identity["packages"]),
        "inventory_sha256": _inventory_sha256(identity),
    }
    manifest_path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return value


def verify_inventory(
    lock_path: Path,
    manifest_path: Path,
    *,
    expected_executable: str,
    executable: str,
    python_version: str,
    packages: Mapping[str, str],
) -> dict[str, object]:
    interpreter_matches = executable.replace("\\", "/") == expected_executable
    try:
        stored = json.loads(manifest_path.read_text(encoding="utf-8"))
        observed = _identity(
            lock_path,
            executable=executable,
            python_version=python_version,
            packages=packages,
        )
    except (OSError, json.JSONDecodeError, TypeError, SystemExit):
        return {
            "matches": False,
            "inventory_sha256": None,
            "package_count": 0,
            "interpreter_matches": interpreter_matches,
        }
    expected_hash = _inventory_sha256(observed)
    matches = (
        isinstance(stored, dict)
        and stored.get("schema_version") == SCHEMA_VERSION
        and stored.get("lock_sha256") == observed["lock_sha256"]
        and stored.get("executable") == observed["executable"]
        and stored.get("python_version") == observed["python_version"]
        and stored.get("packages") == observed["packages"]
        and stored.get("package_count") == len(observed["packages"])
        and stored.get("inventory_sha256") == expected_hash
        and interpreter_matches
    )
    return {
        "matches": matches,
        "inventory_sha256": expected_hash if matches else None,
        "package_count": len(observed["packages"]),
        "interpreter_matches": interpreter_matches,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("write", "verify"))
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expect-executable", default="/app/.venv/bin/python")
    args = parser.parse_args()
    packages = _installed_packages()
    executable = sys.executable.replace("\\", "/")
    if args.command == "write":
        value = write_inventory(
            args.lock,
            args.manifest,
            executable=executable,
            python_version=platform.python_version(),
            packages=packages,
        )
        report = {
            "verdict": "PASS",
            "inventory_sha256": value["inventory_sha256"],
            "package_count": value["package_count"],
        }
    else:
        value = verify_inventory(
            args.lock,
            args.manifest,
            expected_executable=args.expect_executable,
            executable=executable,
            python_version=platform.python_version(),
            packages=packages,
        )
        report = {
            "verdict": "PASS" if value["matches"] else "FAIL",
            **value,
        }
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
