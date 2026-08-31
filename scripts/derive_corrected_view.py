"""Derive the amendment-aligned view of a frozen run manifest. DRAFT, uncommitted.

The frozen run manifest `p1-frozen-001` carries arm-primacy labels written before
`corpus/PREREGISTRATION_AMENDMENT_001.md` promoted `surface_exact_search` to
primary. The measured numbers are unaffected; only the declaration is stale.

This script does not edit the original. It reads the original manifest and the
amendment, rewrites the arm labels alone, and writes a separate file. Every other
byte of content is carried across unchanged, and the script proves that by
comparing the two documents field by field and refusing to write if anything
outside the declared correction set differs.

The corrected view is not authoritative on its own. The authoritative pair is the
original manifest plus the erratum. The output says so in its own body.

Ownership: lane L3. Related: corpus/ERRATUM_001_p1-frozen-001.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "artifacts" / "evidence" / "p1-frozen-001" / "p1-privacy-report.json"
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "evidence" / "p1-frozen-001" / "p1-frozen-001.corrected-view.json"
AMENDMENT_PATH = REPO_ROOT / "corpus" / "PREREGISTRATION_AMENDMENT_001.md"
ERRATUM_PATH = "corpus/ERRATUM_001_p1-frozen-001.md"

ARM_A = "model_offsets"
ARM_B = "surface_exact_search"

# The complete set of paths this script is permitted to change. Anything else
# differing between input and output is a bug, and the script exits rather than
# writing a file that quietly says more than it was authorised to say.
CORRECTABLE_PATHS = frozenset(
    {
        "$.arms.primary.arm",
        "$.arms.primary.status",
        "$.arms.primary.description",
        "$.arms.primary.ambiguity_rule",
        "$.arms.secondary.arm",
        "$.arms.secondary.status",
        "$.arms.secondary.description",
        "$.arms.secondary.ambiguity_rule",
        "$.limitations[4]",
    }
)

CORRECTED_LIMITATION = (
    "Approved residual span counts follow the arm the gate adjudicates, which is "
    "model_offsets, because the gate adjudicates the offsets the model returned. "
    "Under amendment 001 that arm is the secondary arm, so this count does not "
    "describe the primary arm."
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def leaves(node: Any, path: str = "$"):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from leaves(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from leaves(value, f"{path}[{index}]")
    else:
        yield path, node


def amendment_is_present() -> None:
    """The correction has no authority without the amendment that justifies it."""

    if not AMENDMENT_PATH.exists():
        raise SystemExit(f"amendment_missing:{AMENDMENT_PATH}")
    text = AMENDMENT_PATH.read_text(encoding="utf-8")
    for token in (ARM_A, ARM_B, "primary"):
        if token not in text:
            raise SystemExit(f"amendment_unreadable:{token} not found in {AMENDMENT_PATH}")


def correct_arms(original: dict[str, Any]) -> dict[str, Any]:
    """Swap the two arm declarations, carrying each arm's own prose with it."""

    corrected = json.loads(json.dumps(original))
    arms = corrected.get("arms")
    if not isinstance(arms, dict) or "primary" not in arms or "secondary" not in arms:
        raise SystemExit("arms_block_unrecognised")

    stale_primary = dict(arms["primary"])
    stale_secondary = dict(arms["secondary"])
    if stale_primary.get("arm") != ARM_A or stale_secondary.get("arm") != ARM_B:
        raise SystemExit(
            "arms_block_not_stale: the manifest does not carry the pre-amendment labels; "
            "refusing to invent a correction"
        )

    new_primary = dict(stale_secondary)
    new_primary["status"] = "primary under amendment 001"
    new_secondary = dict(stale_primary)
    new_secondary["status"] = "secondary under amendment 001, fully reported"

    corrected["arms"] = {"primary": new_primary, "secondary": new_secondary}

    limitations = corrected.get("limitations")
    if isinstance(limitations, list) and len(limitations) > 4:
        limitations[4] = CORRECTED_LIMITATION

    return corrected


def verify_only_declared_changes(original: dict[str, Any], corrected: dict[str, Any]) -> list[str]:
    before = dict(leaves(original))
    after = dict(leaves(corrected))
    changed = sorted(
        set(before) ^ set(after)
        | {path for path in set(before) & set(after) if before[path] != after[path]}
    )
    unauthorised = [path for path in changed if path not in CORRECTABLE_PATHS]
    if unauthorised:
        raise SystemExit("unauthorised_change:" + ",".join(unauthorised))
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive the amendment-aligned view of a frozen manifest.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    amendment_is_present()

    manifest_path = Path(args.manifest)
    original = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_sha = sha256_file(manifest_path)
    script_sha = sha256_file(Path(__file__))

    corrected = correct_arms(original)
    changed = verify_only_declared_changes(original, corrected)

    corrected["authoritative"] = False
    corrected["derived_from"] = {
        "manifest": str(manifest_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "manifest_sha256": manifest_sha,
        "manifest_content_hash": original.get("content_hash"),
    }
    corrected["derivation_script"] = {
        "path": str(Path(__file__).relative_to(REPO_ROOT)).replace("\\", "/"),
        "sha256": script_sha,
    }
    corrected["corrected_fields"] = changed
    corrected["authority_note"] = (
        "This file is not authoritative on its own. The authoritative pair is the original "
        f"manifest (sha256 {manifest_sha}) plus the erratum at {ERRATUM_PATH}. This view exists "
        "so that published material carries arm labels aligned with "
        "corpus/PREREGISTRATION_AMENDMENT_001.md. Only arm declaration labels were changed. No "
        "measured value, count, hash, timestamp, or approval record was altered, and the frozen "
        "test split was not re-read to produce it."
    )

    output_path = Path(args.out)
    output_path.write_text(
        json.dumps(corrected, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"source manifest      : {manifest_path.name}  sha256 {manifest_sha}")
    print(f"derivation script    : {Path(__file__).name}  sha256 {script_sha}")
    print(f"corrected view       : {output_path.name}  sha256 {sha256_file(output_path)}")
    print(f"fields corrected ({len(changed)}):")
    for path in changed:
        print(f"  {path}")
    print("authoritative        : false, see authority_note")
    return 0


if __name__ == "__main__":
    sys.exit(main())
