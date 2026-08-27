from __future__ import annotations

import hashlib
import argparse
import json
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from recall.contracts import ArtifactStatus, DataMode, build_artifact  # noqa: E402
from recall.connectors.replay import ReplayConnector  # noqa: E402
from recall.contracts.enums import WatchCaseState  # noqa: E402
from recall.ledger.memory import InMemoryLedger  # noqa: E402
from recall.ledger.producers import PRODUCER_REGISTRY  # noqa: E402
from recall.privacy.gate import PrivacyGate  # noqa: E402
from recall.privacy.minimizer import LabNote, build_cloud_bound_payload  # noqa: E402
from recall.privacy.receipt import verify_privacy_receipt  # noqa: E402
from recall.privacy.signing import LocalSigner, load_signer  # noqa: E402
from recall.policy import POLICY_VERSION  # noqa: E402
from recall.scheduler.cohort import REPLAY_ANCHORS, RIGHTS_NOTE  # noqa: E402
from recall.scheduler.compressed_cohort import all_compressed_cases  # noqa: E402
from recall.scheduler.compressed_identity import (  # noqa: E402
    evidence_legacy_failure_receipt_id,
    prepared_watch_artifact_id,
)
from recall.scheduler.compressed_plan import (  # noqa: E402
    DECISION_REFERENCE,
    load_compressed_plan,
)
from recall.scheduler.compressed_preparation import (  # noqa: E402
    DEFAULT_COMPRESSED_BUNDLE_PATH,
)
from recall.scheduler.manifest import COHORT_ID  # noqa: E402
from recall.scheduler.privacy_receipt_source import (  # noqa: E402
    LockedJsonPrivacyReceiptSource,
)


SOURCE_MANIFEST = Path("docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json")


class _IdentityVault:
    def case_token(self, case_key: str) -> str:
        return case_key


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--source-commit")
    parser.add_argument("--privacy-receipts", type=Path)
    parser.add_argument("--privacy-receipts-sha256")
    parser.add_argument("--privacy-key-fingerprint-sha256")
    parser.add_argument("--privacy-key-directory", type=Path)
    args = parser.parse_args()
    target = ROOT / DEFAULT_COMPRESSED_BUNDLE_PATH
    if target.exists() and not args.replace_existing:
        raise RuntimeError("compressed_preparation_bundle_exists")
    source_commit = args.source_commit or _git("rev-parse", "HEAD")
    if len(source_commit) != 40 or any(item not in "0123456789abcdef" for item in source_commit):
        raise RuntimeError("compressed_preparation_source_commit_invalid")
    plan = load_compressed_plan(ROOT)
    prepared_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if args.privacy_receipts is None:
        signer = LocalSigner(
            key_id="compressed-cohort-preparation-ephemeral",
            key=secrets.token_bytes(32),
        )
        receipt_source = None
    else:
        if (
            args.privacy_receipts_sha256 is None
            or args.privacy_key_fingerprint_sha256 is None
        ):
            raise RuntimeError("privacy_receipt_source_lock_required")
        signer = load_signer(args.privacy_key_directory)
        receipt_source = LockedJsonPrivacyReceiptSource(
            args.privacy_receipts,
            expected_sha256=args.privacy_receipts_sha256,
            signer=signer,
            expected_key_fingerprint_sha256=(
                args.privacy_key_fingerprint_sha256
            ),
        )
    all_cases = all_compressed_cases(plan.cycles)
    if (
        any(item.execution_profile == "FULL_AUDIT_V1" for item in plan.cycles)
        and receipt_source is None
    ):
        raise RuntimeError("full_audit_privacy_receipt_source_required")
    if receipt_source is not None:
        receipt_source.assert_exact_case_set({item.case_id for item in all_cases})
    cases = []
    for item in all_cases:
        cloud = build_cloud_bound_payload(_lab_note(item.case_id), item.case_id)
        if receipt_source is None:
            ledger = InMemoryLedger(
                privacy_receipt_verifier=lambda value: verify_privacy_receipt(
                    dict(value), signer
                )[0]
            )
            gate = PrivacyGate(
                signer=signer,
                vault=_IdentityVault(),
                clock=lambda: datetime.fromisoformat(prepared_at.replace("Z", "+00:00")),
                uuid_factory=lambda item=item: str(
                    uuid5(UUID(item.case_id), "compressed-privacy-receipt-v2")
                ),
            )
            result = gate.process(_lab_note(item.case_id))
            if not result.accepted or result.cloud_bound_payload != cloud:
                raise RuntimeError("compressed_local_privacy_preparation_failed")
            receipt = result.receipt
        else:
            receipt = dict(receipt_source.receipt_for(item.case_id, cloud))
        cycle = None if item.cycle_id == "historical-day1" else plan.by_id(item.cycle_id)
        watch_id = (
            str(uuid5(UUID(item.case_id), f"compressed-watch-case:historical-day1:{item.next_scan_at}"))
            if cycle is None
            else prepared_watch_artifact_id(item.case_id, cycle)
        )
        watch = build_artifact(
            schema_name="WatchCase",
            schema_version="2.0.0",
            artifact_id=watch_id,
            case_id=item.case_id,
            run_id=None,
            producer={"component": "workflow-controller", "version": "0.1.0", "identity": "controller"},
            created_at=prepared_at,
            input_artifact_ids=(str(receipt["artifact_id"]),),
            data_mode=DataMode.SYNTHETIC,
            status=ArtifactStatus.VALID,
            payload={
                "tenant_id": "synthetic-contest-lab",
                "region": "us-central1",
                "state": WatchCaseState.ACTIVE.value,
                "monitoring_started_at": prepared_at,
                "monitoring_policy": {"policy_version": POLICY_VERSION},
                "next_scan_at": item.next_scan_at,
                "source_cursors": {"synthetic-source": item.cursor},
                "last_verified_snapshot_id": None,
                "last_verified_scan": {"run_id": None, "completed_at": None},
                "pending_observation_hashes": [],
                "attention_marker": None,
                "open_review_task_id": None,
                "retention_policy": {"class": "contest-synthetic"},
            },
            authorized_producers=PRODUCER_REGISTRY,
        )
        cases.append(
            {
                "case_id": item.case_id,
                "cycle_id": item.cycle_id,
                "cloud_bound_payload": cloud,
                "privacy_receipt": receipt,
                "watch_case": watch,
            }
        )
    bundle = {
        "schema_version": "2.0.0" if receipt_source is None else "2.1.0",
        "prepared_at": prepared_at,
        "source_commit": source_commit,
        "plan_sha256": plan.sha256,
        "rights_note": RIGHTS_NOTE,
        "cases": sorted(cases, key=lambda item: (item["case_id"], item["cycle_id"])),
        "replay_observations": _build_replay_observations(source_commit, prepared_at),
        "legacy_failure_receipt": _build_failure_receipt(plan, source_commit, prepared_at),
    }
    if receipt_source is not None:
        bundle["privacy_receipt_source_lock"] = dict(
            receipt_source.source_lock
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "path": target.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "cases": len(cases),
                "replay_observations": len(bundle["replay_observations"]),
                "source_commit": source_commit,
                "signing_key_persisted": False,
                "privacy_receipt_source": (
                    "LEGACY_SYNTHETIC_LOCAL_GATE"
                    if receipt_source is None
                    else "EXTERNAL_LOCKED_GEMMA_RECEIPTS"
                ),
            },
            sort_keys=True,
        )
    )
    return 0


def _build_failure_receipt(plan, source_commit: str, prepared_at: str):
    cycle = plan.by_id("c1")
    return build_artifact(
        schema_name="CompressedCycleFailureReceipt",
        schema_version="1.0.0",
        artifact_id=evidence_legacy_failure_receipt_id(plan),
        case_id=COHORT_ID,
        run_id=str(uuid5(NAMESPACE_URL, f"recall:legacy-day2-failure:{source_commit}")),
        producer={"component": "managed-cohort-scheduler", "version": "3.0.0", "identity": "cohort-scheduler"},
        created_at=prepared_at,
        input_artifact_ids=(),
        data_mode=DataMode.SYNTHETIC,
        status=ArtifactStatus.INCOMPLETE,
        payload={
            "cohort_due_date": "2026-08-26",
            "scheduled_for": "2026-08-26T16:00:00Z",
            "failure_code": "previous_cohort_manifest_missing",
            "runs_predicted": 3,
            "runs_created": 0,
            "evidence_state": "OWNER_REPORTED",
            "decision_reference": DECISION_REFERENCE,
            "continuation_policy": "COMPRESSED_RECOVERY",
        },
        authorized_producers=PRODUCER_REGISTRY,
    )


def _build_replay_observations(source_commit: str, prepared_at: str):
    replay = ReplayConnector(ROOT, ROOT / SOURCE_MANIFEST)
    verified = {item["semantic_anchor"]: item for item in replay.verify_manifest()}
    run_id = str(uuid5(NAMESPACE_URL, f"recall:compressed-preparation:{source_commit}"))
    values = []
    for anchor in sorted(REPLAY_ANCHORS, key=lambda item: item.vcv):
        source = verified[anchor.vcv]
        values.append(
            build_artifact(
                schema_name="EvidenceObservation",
                schema_version="1.0.0",
                artifact_id=str(uuid5(UUID(run_id), f"cohort-anchor:{anchor.vcv}")),
                case_id=COHORT_ID,
                run_id=run_id,
                producer={"component": "rcl-205-replay-connector", "version": "1.0.1", "identity": "evidence-connector"},
                created_at=prepared_at,
                input_artifact_ids=(),
                data_mode=DataMode.CAPTURED_REPLAY,
                status=ArtifactStatus.VALID,
                payload={
                    "source": "NCBI ClinVar",
                    "source_record_id": str(source["source_id"]),
                    "retrieved_at": str(source["retrieved_at"]),
                    "source_version": "rcl-205:1.0.1",
                    "source_locator": str(source["source_locator"]),
                    "source_content_hash": str(source["sha256"]),
                    "structured_fields": {
                        "semantic_anchor": anchor.vcv,
                        "capture_path": anchor.capture_path,
                        "rights_profile": str(source["rights_profile"]),
                        "attribution_text": str(source["attribution_text"]),
                        "redistribution_boundary": str(source["redistribution_boundary"]),
                        **replay.source_projection(str(source["source_id"])),
                    },
                    "retrieval_status": "PASS",
                },
                authorized_producers=PRODUCER_REGISTRY,
            )
        )
    return values


def _lab_note(case_id: str) -> LabNote:
    return LabNote(
        case_key=case_id,
        note_text="Synthetic research record. No person identifiers.",
        tenant_id="synthetic-contest-lab",
        region="us-central1",
        gene="BRCA2",
        hgvs_c="c.7522G>C",
        hgvs_p="p.Gly2508Arg",
        assembly="GRCh38",
        data_mode="SYNTHETIC",
    )


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
