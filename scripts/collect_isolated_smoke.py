from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from recall.ledger.firestore import FirestoreLedger
from recall.platform.redaction import redact_json
from recall.scheduler.compressed_plan import load_compressed_plan
from recall.scheduler.compressed_preparation import (
    CompressedPreparationVerifier,
    load_compressed_bundle,
)
from recall.scheduler.model_cost import (
    DEFAULT_MODEL_COST_POLICY,
    FirestoreModelCostLedger,
)
from recall.scheduler.smoke import (
    build_smoke_contract,
    smoke_manifest_artifact_id,
    smoke_mode_receipt_artifact_id,
    verify_persisted_smoke_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read and verify one isolated Recall smoke result."
    )
    parser.add_argument("--smoke-mode", required=True)
    parser.add_argument("--smoke-id", required=True)
    parser.add_argument("--smoke-prefix", required=True)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    plan = load_compressed_plan(root)
    bundle = load_compressed_bundle(
        root,
        expected_sha256=_required("RECALL_COMPRESSED_PREPARATION_SHA256"),
        plan=plan,
    )
    contract = build_smoke_contract(
        mode=args.smoke_mode,
        smoke_id=args.smoke_id,
        collection_prefix=args.smoke_prefix,
        source_commit=_required("RECALL_SOURCE_COMMIT"),
        plan_sha256=plan.sha256,
        image_digest=_required("RECALL_IMAGE_DIGEST"),
        expected_plan_sha256=_required("RECALL_SMOKE_EXPECTED_PLAN_SHA256"),
        expected_image_digest=_required("RECALL_SMOKE_EXPECTED_IMAGE_DIGEST"),
        preparation_bundle_sha256=bundle.bundle_sha256,
        job_max_retries=_required("RECALL_SMOKE_JOB_MAX_RETRIES"),
    )
    ledger = FirestoreLedger.from_default_credentials(
        collection_prefix=contract.collection_prefix,
        privacy_receipt_verifier=CompressedPreparationVerifier(bundle),
        expected_project_sha256=_required("RECALL_EXPECTED_PROJECT_SHA256"),
        database="(default)",
        require_live=True,
    )
    manifest_artifact_id = smoke_manifest_artifact_id(
        contract.collection_prefix
    )
    mode_receipt_artifact_id = (
        smoke_mode_receipt_artifact_id(contract.collection_prefix)
        if contract.mode == "positive"
        else None
    )
    cost = FirestoreModelCostLedger(
        ledger.client,
        collection_name=f"{contract.collection_prefix}model_cost",
        hard_cap_usd_micros=DEFAULT_MODEL_COST_POLICY.hard_cap_usd_micros,
    ).snapshot()
    bindings = verify_persisted_smoke_artifacts(
        ledger=ledger,
        contract=contract,
        manifest_artifact_id=manifest_artifact_id,
        mode_receipt_artifact_id=mode_receipt_artifact_id,
        cost_snapshot=cost,
    )
    manifest = ledger.get_artifact(manifest_artifact_id)
    if manifest is None:
        raise RuntimeError("smoke_manifest_missing")
    print(
        json.dumps(
            redact_json(
                {
                    "schema_name": "IsolatedSmokeCollectionVerification",
                    "schema_version": "1.0.0",
                    "verified": True,
                    "writes": 0,
                    "smoke_id": contract.smoke_id,
                    "mode": contract.mode.upper(),
                    "collection_prefix": contract.collection_prefix,
                    "source_commit": contract.source_commit,
                    "plan_sha256": contract.plan_sha256,
                    "preparation_bundle_sha256": (
                        contract.preparation_bundle_sha256
                    ),
                    "image_digest": contract.image_digest,
                    **bindings,
                    "execution_status": manifest["execution_status"],
                    "selected_case_ids": manifest["selected_case_ids"],
                    "run_ids": manifest["run_ids"],
                    "cost": {
                        "reserved_usd_micros": cost.reserved_usd_micros,
                        "reconciled_usd_micros": cost.reconciled_usd_micros,
                    },
                }
            ),
            sort_keys=True,
        )
    )
    return 0


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"smoke_required_environment_missing:{name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
