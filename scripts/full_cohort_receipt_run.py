"""Full-cohort Gemma receipt run: 456 notes through the real local pipeline.

Input:  corpus/onboarding/notes.json (sha256 pinned below).
Output: the LockedJsonPrivacyReceiptSource wire: {"schema_version":"1.0.0",
        "receipts":[...]} with PrivacyReceipt 1.1.0 entries, plus a manifest
        carrying the output sha256, the signer's verifier-lock fingerprint,
        transport request settings, and per-run counters.

The locus declaration is EXPLICIT CONFIG, not inference, and this script is
fail-closed on honesty: it refuses to start unless the declared posture
matches how the transport is actually wired (a cloud base_url with a
LOCAL_PROCESS declaration, or the reverse, is a refusal, not a warning).
Both postures are contract-registered as of core 982f6e3a: the all-local
trio and the cloud trio (LAB_LOCAL, PRIVATE_SERVICE, OLLAMA_CLOUD_RUN).
The cloud run waits only on the deploy signal for its base_url.

Usage:
  python scripts/full_cohort_receipt_run.py --posture local \
      [--base-url http://127.0.0.1:11434] [--limit N] [--concurrency K]
  python scripts/full_cohort_receipt_run.py --posture cloud \
      --base-url https://<gpu-service>   # refuses until the contract accepts it
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from recall.privacy.gate import PrivacyGate  # noqa: E402
from recall.privacy.gemma import (  # noqa: E402
    GemmaResidualDetector,
    OllamaChatTransport,
)
from recall.privacy.minimizer import LabNote  # noqa: E402
from recall.privacy.signing import LocalSigner, signer_fingerprint_sha256  # noqa: E402

NOTES_PATH = ROOT / "corpus" / "onboarding" / "notes.json"
NOTES_SHA256 = "ec0fa8d4aa9182d6b93564b782209ef7bb441924eefe964b5d8f1385f435c73e"
OUT_DIR = ROOT / "artifacts" / "evidence" / "full-cohort-receipts"

# Pinned to core's FULL_AUDIT_MODEL_ID (compressed_preparation.py:24) and the
# P1 evidence identity block; the prep gate rejects any other id.
MODEL_ID = "gemma4:e4b-it-qat"
MODEL_REVISION = "sha256:e8b6a059ba86947a44ace84d6e5679795bc41862c25c30513142588f0e9dba1d"

POSTURES: dict[str, dict[str, str]] = {
    # How the model leg actually runs today: Ollama as a local process.
    "local": {
        "execution_locus": "LAB_LOCAL",
        "transport_class": "LOCAL_PROCESS",
        "endpoint_class": "OLLAMA_LOCAL",
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
    },
    # Vertex pivot (owner, 2026-08-27 13:05): same bit-identical image served
    # from a Vertex endpoint. base_url is the FULL rawPredict URL (api_path
    # empty; Vertex forwards the body to the container's chat route), auth is
    # an ACCESS token.
    "cloud": {
        "execution_locus": "LAB_LOCAL",
        "transport_class": "PRIVATE_SERVICE",
        "endpoint_class": "OLLAMA_VERTEX_ENDPOINT",
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
    },
}

# EndpointClass values registered in the shipped contract, last verified from
# source at core abfdde1 (enums.py OLLAMA_VERTEX_ENDPOINT present; prep gate
# accepts the LAB_LOCAL + PRIVATE_SERVICE + OLLAMA_VERTEX_ENDPOINT trio at
# compressed_preparation.py accepted_paths). Refusal stays for any value not
# in this source-verified set.
REGISTERED_ENDPOINT_CLASSES = frozenset(
    {"OLLAMA_LOCAL", "OLLAMA_CLOUD_RUN", "OLLAMA_VERTEX_ENDPOINT", "VERTEX_AI_GLOBAL"}
)


class _IdentityVault:
    def case_token(self, case_key: str) -> str:
        return case_key


def _fail(message: str) -> int:
    print(f"REFUSED: {message}")
    return 1


def _load_notes() -> list[dict]:
    raw = NOTES_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != NOTES_SHA256:
        raise RuntimeError(f"notes_sha256_mismatch: {digest}")
    return json.loads(raw.decode("utf-8"))["notes"]


def _lab_note(entry: dict) -> LabNote:
    s = entry["structured"]
    if s.get("inherit_case_binding"):
        # The three VCV-anchored cases resolve their variant from the case
        # binding on the consuming side; the receipt run must not invent one.
        # Until the consuming-side resolution lands, these cases are held out
        # and reported, never silently defaulted.
        raise KeyError("inherit_case_binding")
    return LabNote(
        case_key=entry["case_id"],
        note_text=entry["note_text"],
        tenant_id="synthetic-contest-lab",
        region="us-central1",
        gene=s["gene"],
        hgvs_c=s["hgvs_c"],
        hgvs_p=s["hgvs_p"],
        assembly=s["assembly"],
        data_mode="SYNTHETIC",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--posture", choices=sorted(POSTURES), required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--limit", type=int, default=None, help="smoke: first N notes")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    args = parser.parse_args()

    locus = dict(POSTURES[args.posture])
    is_cloud_url = args.base_url.startswith("https://")

    # Honesty gate: the declaration must match the wiring, both directions.
    if args.posture == "cloud" and not is_cloud_url:
        return _fail("cloud posture declared but base_url is not https")
    if args.posture == "local" and is_cloud_url:
        return _fail("local posture declared but base_url is a cloud endpoint")
    if locus["endpoint_class"] not in REGISTERED_ENDPOINT_CLASSES:
        return _fail(
            f"endpoint_class {locus['endpoint_class']} is not registered in the "
            "shipped contract (verified from source); running now would either "
            "lie in the receipt or fail the preparation gate. Blocked on the "
            "contract landing, then verify-and-add here."
        )

    auth_provider = None
    if is_cloud_url:
        from gcloud_identity_provider import access_token_header

        auth_provider = access_token_header

    transport = OllamaChatTransport(
        base_url=args.base_url,
        model_id=MODEL_ID,
        response_format="json",
        auth_header_provider=auth_provider,
        # A Vertex rawPredict base_url IS the full invoke URL; a direct Ollama
        # server takes the chat route suffix.
        api_path="" if is_cloud_url else "/api/chat",
    )
    signer = LocalSigner(
        key_id="full-cohort-receipt-run-v1", key=secrets.token_bytes(32)
    )
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Preflight: a missing model fails every call identically; find that out in
    # one request, not 456. A direct Ollama server exposes /api/tags; a managed
    # rawPredict frontend does not, so there the first note runs SERIALLY as
    # the preflight and the pool starts only after it succeeds.
    if not is_cloud_url:
        import urllib.request

        tags_request = urllib.request.Request(f"{args.base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(tags_request, timeout=15) as response:
            served = [m["name"] for m in json.loads(response.read())["models"]]
        if MODEL_ID not in served:
            return _fail(f"model {MODEL_ID} not served at {args.base_url}; served: {served}")

    notes = _load_notes()
    if args.limit:
        notes = notes[: args.limit]

    held_out: list[str] = []
    receipts: list[dict] = []
    failures: list[dict] = []
    t0 = time.monotonic()

    def run_one(entry: dict) -> tuple[str, dict | None, str | None]:
        try:
            note = _lab_note(entry)
        except KeyError:
            return entry["case_id"], None, "inherit_case_binding"
        gate = PrivacyGate(
            signer=signer,
            vault=_IdentityVault(),
            gemma=GemmaResidualDetector(
                transport, model_id=MODEL_ID, timeout_seconds=args.timeout_seconds
            ),
            execution_locus_block=dict(locus),
            uuid_factory=lambda cid=entry["case_id"]: str(
                uuid5(uuid5(NAMESPACE_URL, cid), "full-cohort-receipt-v1")
            ),
        )
        result = gate.process(note)
        if not result.accepted:
            return entry["case_id"], None, "not_accepted"
        receipt = result.receipt
        gemma_block = receipt["detectors"]["gemma"]
        # BOTH flags, matching the prep gate exactly. invoked alone passed a
        # missing-model transport error as success in the first smoke: the
        # attempt was recorded as invoked=true, schema_valid=false, and this
        # script said DONE over receipts prep would reject.
        if gemma_block.get("invoked") is not True or gemma_block.get("schema_valid") is not True:
            return entry["case_id"], None, "gemma_leg_failed"
        return entry["case_id"], receipt, None

    if is_cloud_url and notes:
        first_id, first_receipt, first_error = run_one(notes[0])
        if first_error not in (None, "inherit_case_binding"):
            return _fail(f"cloud preflight failed on first note {first_id}: {first_error}")
        if first_error is None:
            receipts.append(first_receipt)
        else:
            held_out.append(first_id)
        notes = notes[1:]
        print(f"cloud preflight OK ({(time.monotonic() - t0)/60:.1f} min), pool starting")

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for case_id, receipt, error in pool.map(run_one, notes):
            if error == "inherit_case_binding":
                held_out.append(case_id)
            elif error is not None:
                failures.append({"case_id": case_id, "error": error})
            else:
                receipts.append(receipt)
            done = len(receipts) + len(failures) + len(held_out)
            if done % 25 == 0:
                elapsed = time.monotonic() - t0
                print(
                    f"{done}/{len(notes)} elapsed={elapsed/60:.1f}min "
                    f"ok={len(receipts)} fail={len(failures)} heldout={len(held_out)}"
                )

    elapsed_minutes = (time.monotonic() - t0) / 60
    if failures:
        print(f"RUN INCOMPLETE: {len(failures)} failures, first: {failures[:3]}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wire = {"schema_version": "1.0.0", "receipts": receipts}
    out_path = OUT_DIR / "privacy-receipts.json"
    payload = json.dumps(wire, ensure_ascii=False, sort_keys=True, indent=1) + "\n"
    out_path.write_text(payload, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()

    manifest = {
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "elapsed_minutes": round(elapsed_minutes, 1),
        "posture": args.posture,
        "locus": locus,
        "notes_sha256": NOTES_SHA256,
        "receipts_file": str(out_path.relative_to(ROOT)),
        "receipts_sha256": digest,
        "receipt_count": len(receipts),
        "held_out_inherit_binding": sorted(held_out),
        "signer_key_id": signer.key_id,
        "verifier_lock_fingerprint_sha256": signer_fingerprint_sha256(signer),
        "transport": transport.request_settings(),
        "concurrency": args.concurrency,
    }
    (OUT_DIR / "RUN_MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        f"DONE: {len(receipts)} receipts in {elapsed_minutes:.1f}min, "
        f"sha256 {digest}, held out {len(held_out)} (inherit_case_binding)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
