from __future__ import annotations

import hashlib
import json
import secrets
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from recall.contracts import (  # noqa: E402
    ArtifactStatus,
    DataMode,
    build_artifact,
    parse_artifact,
)
from recall.connectors.replay import ReplayConnector  # noqa: E402
from recall.controller import Controller  # noqa: E402
from recall.ledger.memory import InMemoryLedger  # noqa: E402
from recall.ledger.producers import PRODUCER_REGISTRY  # noqa: E402
from recall.privacy.gate import PrivacyGate  # noqa: E402
from recall.privacy.minimizer import LabNote, build_cloud_bound_payload  # noqa: E402
from recall.privacy.receipt import verify_privacy_receipt  # noqa: E402
from recall.privacy.signing import LocalSigner  # noqa: E402
from recall.scheduler.cohort import (  # noqa: E402
    MANAGED_COHORT,
    REPLAY_ANCHORS,
    RIGHTS_NOTE,
)
from recall.scheduler.manifest import COHORT_ID  # noqa: E402
from recall.scheduler.preparation import DEFAULT_BUNDLE_PATH  # noqa: E402


PREPARED_AT = "2026-08-25T20:00:00Z"
DAY1_MANIFEST = Path(
    "artifacts/evidence/day1-manual-20260825-a7f31c9d/manifest.json"
)
SOURCE_MANIFEST = Path("docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json")


class _IdentityVault:
    def case_token(self, case_key: str) -> str:
        return case_key


def main() -> int:
    target = ROOT / DEFAULT_BUNDLE_PATH
    if target.exists():
        raise RuntimeError("cohort_preparation_bundle_exists")
    source_commit = _git("rev-parse", "HEAD")
    signer = LocalSigner(
        key_id="cohort-preparation-20260825-ephemeral",
        key=secrets.token_bytes(32),
    )
    day1 = json.loads((ROOT / DAY1_MANIFEST).read_text(encoding="utf-8"))
    day1_artifacts = {
        artifact_id: item["wire"]
        for artifact_id, item in day1["readback"]["artifacts"].items()
    }
    original_ids = {item.case_id for item in MANAGED_COHORT[:3]}
    cases = []
    for item in sorted(MANAGED_COHORT, key=lambda value: value.case_id):
        cloud_payload = build_cloud_bound_payload(
            _lab_note(item.case_id), item.case_id
        )
        if item.case_id in original_ids:
            watch = next(
                wire
                for wire in day1_artifacts.values()
                if wire["schema_name"] == "WatchCase" and wire["case_id"] == item.case_id
            )
            receipt = day1_artifacts[str(watch["input_artifact_ids"][0])]
        else:
            ledger = InMemoryLedger(
                privacy_receipt_verifier=lambda value: verify_privacy_receipt(
                    dict(value), signer
                )[0]
            )
            gate = PrivacyGate(
                signer=signer,
                vault=_IdentityVault(),
                clock=lambda: datetime.fromisoformat(
                    PREPARED_AT.replace("Z", "+00:00")
                ),
                uuid_factory=lambda item=item: str(
                    uuid5(UUID(item.case_id), "cohort-privacy-receipt-v1")
                ),
            )
            result = gate.process(_lab_note(item.case_id))
            if not result.accepted or result.cloud_bound_payload != cloud_payload:
                raise RuntimeError("cohort_local_privacy_preparation_failed")
            receipt = result.receipt
            ledger.append_artifact(receipt)
            controller = Controller(ledger)
            created = controller.create_watch_case(
                watch_case_id=item.case_id,
                tenant_id="synthetic-contest-lab",
                region="us-central1",
                privacy_receipt_id=str(receipt["artifact_id"]),
                cloud_bound_payload=cloud_payload,
                data_mode=DataMode.SYNTHETIC,
                source_cursors={"synthetic-source": item.cursor},
                pending_observation_hashes=(),
                next_scan_at=item.next_scan_at,
                now=datetime.fromisoformat(PREPARED_AT.replace("Z", "+00:00")),
            )
            watch = ledger.get_artifact(created.record.artifact_id)
            assert watch is not None
        parse_artifact(receipt, authorized_producers=PRODUCER_REGISTRY)
        parse_artifact(watch, authorized_producers=PRODUCER_REGISTRY)
        cases.append(
            {
                "case_id": item.case_id,
                "cloud_bound_payload": cloud_payload,
                "privacy_receipt": receipt,
                "watch_case": watch,
            }
        )
    replay_observations = _build_replay_observations(source_commit)
    bundle = {
        "schema_version": "1.0.0",
        "prepared_at": PREPARED_AT,
        "source_commit": source_commit,
        "rights_note": RIGHTS_NOTE,
        "cases": cases,
        "replay_observations": replay_observations,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(bundle, indent=2, sort_keys=True) + "\n"
    target.write_text(payload, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "path": target.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "cases": len(cases),
                "replay_observations": len(replay_observations),
                "source_commit": source_commit,
                "signing_key_persisted": False,
            },
            sort_keys=True,
        )
    )
    return 0


def _build_replay_observations(source_commit: str) -> list[dict[str, object]]:
    replay = ReplayConnector(ROOT, ROOT / SOURCE_MANIFEST)
    verified = {item["semantic_anchor"]: item for item in replay.verify_manifest()}
    run_id = str(uuid5(NAMESPACE_URL, f"recall:cohort-preparation:{source_commit}"))
    observations = []
    for anchor in sorted(REPLAY_ANCHORS, key=lambda value: value.vcv):
        source = verified[anchor.vcv]
        observations.append(
            build_artifact(
                schema_name="EvidenceObservation",
                schema_version="1.0.0",
                artifact_id=str(uuid5(UUID(run_id), f"cohort-anchor:{anchor.vcv}")),
                case_id=COHORT_ID,
                run_id=run_id,
                producer={
                    "component": "rcl-205-replay-connector",
                    "version": "1.0.1",
                    "identity": "evidence-connector",
                },
                created_at=PREPARED_AT,
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
                    },
                    "retrieval_status": "PASS",
                },
                authorized_producers=PRODUCER_REGISTRY,
            )
        )
    return observations


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
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
