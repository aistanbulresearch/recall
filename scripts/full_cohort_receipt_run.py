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
from recall.privacy.receipt import verify_privacy_receipt  # noqa: E402
from recall.privacy.signing import content_hash  # noqa: E402
from recall.privacy.minimizer import build_cloud_bound_payload  # noqa: E402
from recall.privacy.signing import (  # noqa: E402
    LocalSigner,
    load_signer,
    signer_fingerprint_sha256,
)

NOTES_PATH = ROOT / "corpus" / "onboarding" / "notes.json"
NOTES_SHA256 = "ce71a0b7b50601148c49b65457bc603efca929b3569ed37179902424c8d36af6"
OUT_DIR = ROOT / "artifacts" / "evidence" / "full-cohort-receipts"

# Pinned to core's FULL_AUDIT_MODEL_ID (compressed_preparation.py:24) and the
# P1 evidence identity block; the prep gate rejects any other id.
MODEL_ID = "gemma4:e4b-it-qat"
MODEL_REVISION = "sha256:e8b6a059ba86947a44ace84d6e5679795bc41862c25c30513142588f0e9dba1d"
# The one Vertex endpoint approved to receive the access token (L1 deploy,
# 2026-08-27). A different endpoint id is a refusal, not a parameter.
APPROVED_VERTEX_ENDPOINT_ID = "9183372353592098816"


def _gcloud_project() -> str:
    import subprocess

    from gcloud_identity_provider import _gcloud_executable

    completed = subprocess.run(
        [_gcloud_executable(), "config", "get-value", "project"],
        capture_output=True, text=True, timeout=30,
    )
    project = completed.stdout.strip()
    if completed.returncode != 0 or not project:
        raise RuntimeError("gcloud_project_unresolved")
    return project

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
    # Since portfolio-notes-v2 every row, anchored included, carries a RESOLVED
    # variant (anchored ones from the hash-verified replay manifest, re-checked
    # by the consuming loader), so no case is held out any more.
    s = entry["structured"]
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
    parser.add_argument(
        "--key-dir",
        type=Path,
        required=True,
        help=(
            "Directory to persist the signing key (privacy-signing-key.json, "
            "the load_signer format). MANDATORY: the preparation loads this "
            "key to check every HMAC, so a discarded key makes all 456 "
            "receipts unverifiable while looking signed. Outside the repo; a "
            "fresh run refuses a directory that already holds a key, a resume "
            "requires the existing key to match the checkpoint fingerprint. "
            "The manifest records the fingerprint only, never the key."
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue from the checkpoint: skip receipted cases, retry failures.",
    )
    args = parser.parse_args()

    locus = dict(POSTURES[args.posture])
    is_cloud_url = args.base_url.startswith("https://")

    if args.posture == "cloud":
        # CREDENTIAL GUARD. The access token goes wherever base_url points, so
        # "starts with https" is not a check, it is an invitation: any https
        # host would receive the token. The URL must be EXACTLY the approved
        # Vertex rawPredict invoke URL for this project and endpoint; userinfo,
        # query, fragment, port and any other host, region, project, endpoint
        # or path are refusals, before any token is minted.
        from urllib.parse import urlsplit

        parts = urlsplit(args.base_url)
        expected_host = "us-central1-aiplatform.googleapis.com"
        project = _gcloud_project()
        expected_path = (
            f"/v1/projects/{project}/locations/us-central1/endpoints/"
            f"{APPROVED_VERTEX_ENDPOINT_ID}:rawPredict"
        )
        problems = []
        if parts.scheme != "https":
            problems.append("scheme is not https")
        if parts.hostname != expected_host:
            problems.append(f"host is not {expected_host}")
        if parts.port is not None:
            problems.append("explicit port is not allowed")
        if parts.username is not None or parts.password is not None:
            problems.append("userinfo is not allowed")
        if parts.query or parts.fragment:
            problems.append("query/fragment are not allowed")
        if parts.path != expected_path:
            problems.append("path is not the approved rawPredict invoke path")
        if problems:
            return _fail(
                "base_url failed the credential guard: " + "; ".join(problems)
            )

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
    if ROOT in args.key_dir.resolve().parents or args.key_dir.resolve() == ROOT:
        return _fail("key-dir must be OUTSIDE the repository")
    args.key_dir.mkdir(parents=True, exist_ok=True)
    key_file = args.key_dir / "privacy-signing-key.json"

    if args.resume:
        if not key_file.exists():
            return _fail("resume requested but no key file in key-dir")
        signer = load_signer(args.key_dir)
    else:
        if key_file.exists():
            return _fail(
                "key-dir already holds a key; a fresh run never overwrites one "
                "(pass --resume to continue that run, or use a new directory)"
            )
        # Generated AS TEXT (hex): load_signer round-trips the key through JSON
        # as a utf-8 string, and raw random bytes would not survive that — the
        # persisted file would hold something that is not the signing key.
        signer = LocalSigner(
            key_id="full-cohort-receipt-run-v1",
            key=secrets.token_hex(32).encode("utf-8"),
        )
        # Atomic persist, then PROVE the round-trip before any model request:
        # reload from disk and require an identical signature on a probe
        # message. A key that fails this check would produce 456 receipts that
        # look signed and verify nowhere.
        tmp = key_file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"key_id": signer.key_id, "key": signer.key.decode("utf-8")}),
            encoding="utf-8",
        )
        tmp.replace(key_file)
    reloaded = load_signer(args.key_dir)
    probe = "recall/full-cohort-run/key-roundtrip-probe"
    if reloaded.sign(probe) != signer.sign(probe) or reloaded.key_id != signer.key_id:
        return _fail("persisted key failed the signature round-trip; refusing to run")
    fingerprint = signer_fingerprint_sha256(signer)
    print(f"signing key at {key_file}, round-trip verified, fingerprint {fingerprint[:16]}...")
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

    # OS-level exclusive run lease: two concurrent processes on the same output
    # directory would each pay for the same model calls and interleave the
    # checkpoint. The lease file is created with O_EXCL; a leftover lease from
    # a crashed run (its PID no longer alive) is taken over, a live one refuses.
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lease_path = OUT_DIR / "run.lease"
    import os as _os

    def _pid_alive(pid: int) -> bool:
        try:
            _os.kill(pid, 0)
        except OSError:
            return False
        return True

    if lease_path.exists():
        try:
            lease = json.loads(lease_path.read_text(encoding="utf-8"))
            holder = int(lease.get("pid", -1))
        except (ValueError, json.JSONDecodeError):
            holder = -1
        if holder > 0 and _pid_alive(holder):
            return _fail(f"another run holds the lease (pid {holder}); refusing to duplicate paid calls")
        lease_path.unlink()
    run_id = secrets.token_hex(8)
    fd = _os.open(str(lease_path), _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY)
    with _os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"pid": _os.getpid(), "run_id": run_id}, handle)

    # Append-only checkpoint: one JSONL line per finished case, header bound to
    # everything that makes receipts mixable-or-not. A crash at case 455 costs
    # one retry, not 455 paid calls; a resume against DIFFERENT notes, posture,
    # model or key refuses instead of silently mixing incompatible receipts.
    checkpoint_path = OUT_DIR / "checkpoint.jsonl"
    context = {
        "notes_sha256": NOTES_SHA256,
        "posture": args.posture,
        "model_revision": MODEL_REVISION,
        "signer_fingerprint": fingerprint,
        "key_id": signer.key_id,
    }
    done: dict[str, dict] = {}
    if checkpoint_path.exists():
        if not args.resume:
            return _fail(
                "a checkpoint exists; pass --resume to continue it or remove "
                "the output directory to start over (never silently mixed)"
            )
        lines = checkpoint_path.read_text(encoding="utf-8").splitlines()
        try:
            header = json.loads(lines[0])
        except (json.JSONDecodeError, IndexError):
            return _fail("checkpoint header unreadable; not recoverable")
        if header != context:
            return _fail(f"checkpoint context mismatch: {header} != {context}")
        # Torn-tail tolerance: a crash mid-append can leave EXACTLY ONE partial
        # final line. That one is dropped and the file atomically rewritten
        # without it; any other malformed line is corruption and refuses.
        parsed_entries: list[dict] = []
        torn = False
        for index, line in enumerate(lines[1:], start=2):
            try:
                parsed_entries.append(json.loads(line))
            except json.JSONDecodeError:
                if index == len(lines):
                    torn = True
                else:
                    return _fail(f"checkpoint line {index} malformed mid-file; not a torn tail")
        if torn:
            repaired = "\n".join(lines[:-1]) + "\n"
            tmp = checkpoint_path.with_suffix(".repair")
            tmp.write_text(repaired, encoding="utf-8", newline="\n")
            tmp.replace(checkpoint_path)
            print("torn checkpoint tail dropped (one partial final line), file rewritten")

        # Every resumed receipt is VERIFIED, never trusted: signature against
        # the persisted signer, case identity, accepted decision, gemma leg
        # success, the exact locus of this run, and payload binding recomputed
        # from the notes. A checkpoint is input, and input gets the same
        # treatment as any other wire.
        notes_by_id = {n["case_id"]: n for n in _load_notes()}
        seen_ids: set[str] = set()
        for entry in parsed_entries:
            case_id = entry.get("case_id")
            if "receipt" not in entry:
                continue
            receipt = entry["receipt"]
            if case_id in seen_ids:
                return _fail(f"checkpoint holds duplicate case {case_id}")
            seen_ids.add(case_id)
            note_entry = notes_by_id.get(case_id)
            if note_entry is None:
                return _fail(f"checkpoint holds unknown case {case_id}")
            valid, reasons = verify_privacy_receipt(dict(receipt), signer)
            gemma_block = receipt.get("detectors", {}).get("gemma", {})
            expected_payload = build_cloud_bound_payload(_lab_note(note_entry), case_id)
            payload_hash = content_hash(expected_payload)
            if (
                not valid
                or receipt.get("case_id") != case_id
                or receipt.get("schema_version") != "1.1.0"
                or receipt.get("decision") != "ACCEPTED"
                or gemma_block.get("invoked") is not True
                or gemma_block.get("schema_valid") is not True
                or any(receipt.get(f) != locus[f] for f in locus)
                or receipt.get("payload_hash") != payload_hash
            ):
                return _fail(
                    f"checkpoint receipt for {case_id} failed verification "
                    f"(signature_ok={valid} reasons={reasons}); refusing to resume over it"
                )
            done[case_id] = receipt
        print(f"resume: {len(done)} receipted cases verified and skipped")
    else:
        if args.resume:
            return _fail("resume requested but no checkpoint exists")
        checkpoint_path.write_text(
            json.dumps(context, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )

    import threading

    checkpoint_lock = threading.Lock()

    def checkpoint(entry: dict) -> None:
        with checkpoint_lock:
            with checkpoint_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

    held_out: list[str] = []
    receipts: list[dict] = list(done.values())
    failures: list[dict] = []
    t0 = time.monotonic()
    notes = [n for n in notes if n["case_id"] not in done]

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
            checkpoint({"case_id": first_id, "receipt": first_receipt})
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
                checkpoint({"case_id": case_id, "error": error, "at": time.time()})
            else:
                receipts.append(receipt)
                checkpoint({"case_id": case_id, "receipt": receipt})
            done = len(receipts) + len(failures) + len(held_out)
            if done % 25 == 0:
                elapsed = time.monotonic() - t0
                print(
                    f"{done}/{len(notes)} elapsed={elapsed/60:.1f}min "
                    f"ok={len(receipts)} fail={len(failures)} heldout={len(held_out)}"
                )

    elapsed_minutes = (time.monotonic() - t0) / 60
    if failures:
        # The checkpoint holds every paid receipt; the FINAL files are not
        # touched, so no previous output can masquerade as this run's result.
        print(
            f"RUN INCOMPLETE: {len(failures)} failures (checkpointed; --resume "
            f"retries them), first: {failures[:3]}"
        )
        return 1

    wire = {
        "schema_version": "1.0.0",
        "receipts": sorted(receipts, key=lambda r: r["case_id"]),
    }
    out_path = OUT_DIR / "privacy-receipts.json"
    payload = json.dumps(wire, ensure_ascii=False, sort_keys=True, indent=1) + "\n"
    tmp_out = out_path.with_suffix(f".{run_id}.tmp")
    tmp_out.write_text(payload, encoding="utf-8", newline="\n")
    tmp_out.replace(out_path)
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
        "verifier_lock_fingerprint_sha256": fingerprint,
        "transport": transport.request_settings(),
        "concurrency": args.concurrency,
        "final_publish_run_id": run_id,
    }
    manifest_path = OUT_DIR / "RUN_MANIFEST.json"
    tmp_manifest = manifest_path.with_suffix(f".{run_id}.tmp")
    tmp_manifest.write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    tmp_manifest.replace(manifest_path)
    lease_path.unlink(missing_ok=True)
    print(
        f"DONE: {len(receipts)} receipts in {elapsed_minutes:.1f}min, "
        f"sha256 {digest}, held out {len(held_out)} (inherit_case_binding)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
