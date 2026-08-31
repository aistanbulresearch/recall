from __future__ import annotations

import hashlib
import json
from pathlib import Path

from recall.contracts import parse_artifact
from recall.ledger.firestore import FirestoreLedger
from recall.ledger.producers import PRODUCER_REGISTRY
from recall.scheduler.compressed_plan import load_compressed_plan


OUTPUT_DIRECTORY = Path(
    "artifacts/evidence/cohort-compression/executed-manifests"
)


def main() -> int:
    root = Path.cwd()
    plan = load_compressed_plan(root)
    bindings = {
        "c1": plan.by_id("c2").predecessor,
        "c2": plan.by_id("c3").predecessor,
    }
    output = root / OUTPUT_DIRECTORY
    output.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {}
    for cycle_id, binding in bindings.items():
        if (
            binding is None
            or binding.binding != "EXTERNAL_PLAN"
            or binding.collection_prefix is None
            or binding.manifest_artifact_id is None
            or binding.manifest_content_hash is None
        ):
            raise RuntimeError(f"executed_manifest_binding_missing:{cycle_id}")
        ledger = FirestoreLedger.from_default_credentials(
            collection_prefix=binding.collection_prefix,
            database="(default)",
            require_live=True,
        )
        wire = ledger.get_artifact(binding.manifest_artifact_id)
        if wire is None:
            raise RuntimeError(f"executed_manifest_missing:{cycle_id}")
        parsed = parse_artifact(wire, authorized_producers=PRODUCER_REGISTRY)
        if (
            parsed.schema_name != "CohortDayManifest"
            or parsed.artifact_id != binding.manifest_artifact_id
            or parsed.content_hash != binding.manifest_content_hash
        ):
            raise RuntimeError(f"executed_manifest_binding_invalid:{cycle_id}")
        path = output / f"{cycle_id}-manifest.json"
        encoded = (
            json.dumps(
                parsed.to_wire(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        path.write_bytes(encoded)
        report[cycle_id] = {
            "artifact_id": parsed.artifact_id,
            "content_hash": parsed.content_hash,
            "file": path.relative_to(root).as_posix(),
            "file_sha256": hashlib.sha256(encoded).hexdigest(),
            "source_collection_prefix": binding.collection_prefix,
        }
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
