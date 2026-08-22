"""Protocol P1: laboratory privacy contribution measurement.

Compares the deterministic baseline against the deterministic-plus-local-model
path on a frozen synthetic corpus split, then writes an evidence manifest.

Both of those comparators run under the `SUMMARY_TEXT` egress profile, which
releases a redacted free-text summary. That is where detection quality can
change the outcome, so it is where the local-model contribution is measurable.

A third arm runs the deterministic gate under the demonstrated `STRUCTURED_ONLY`
profile, which declares no free-text field at all. Its acceptance rate is
structural rather than a detector result, and the report says so, but it is
measured on the same records so the two boundaries can be compared honestly.

Four stop points are enforced in code, not by convention:

* the frozen `test` split refuses to run without a recorded preregistration
  approval;
* an oracle stub is labelled as a stub everywhere it appears and can never be
  reported as a local-model result;
* a model-backed run refuses to start unless the model file and the prompt are
  identified by hash, computed here rather than pasted in
  (`corpus/PREREGISTRATION.md` condition 4);
* the frozen split refuses a second run unless the new run explicitly supersedes
  the recorded one (`corpus/PREREGISTRATION.md` condition 5).

Ownership: lane L3. Related tasks: RCL-405; protocol P1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from recall.privacy.detectors import DeterministicDetector  # noqa: E402
from recall.privacy.egress import EGRESS_STRUCTURED_ONLY, EGRESS_SUMMARY_TEXT  # noqa: E402
from recall.privacy.gate import PrivacyGate  # noqa: E402
from recall.privacy.gemma import (  # noqa: E402
    GEMMA_ADAPTER_VERSION,
    SYSTEM_INSTRUCTION,
    GemmaResidualDetector,
    LlamaServerTransport,
)
from recall.privacy.minimizer import LabNote  # noqa: E402
from recall.privacy.receipt import DECISION_ACCEPTED  # noqa: E402
from recall.privacy.signing import LocalSigner, SigningKeyUnavailable, content_hash, load_signer  # noqa: E402
from recall.privacy.spans import DIRECT_IDENTIFIER_CLASSES  # noqa: E402

PROTOCOL_VERSION = "P1/1.0.0"
MODE_DETERMINISTIC = "deterministic_only"
MODE_LOCAL_MODEL = "deterministic_plus_local_model"
MODE_ORACLE_STUB = "deterministic_plus_oracle_stub"
MODE_STRUCTURED_ONLY = "deterministic_structured_only_egress"

STRUCTURED_ONLY_NOTE = (
    "Acceptance under the structured-only egress profile is a property of the "
    "payload shape, not a detection result. The payload declares no free-text "
    "field, so no identifier the detectors missed has a field to travel in. "
    "This number must never be reported as detector or local-model performance."
)

ORACLE_STUB_DISCLAIMER = (
    "The oracle stub replays ground-truth residual spans. It measures the gate's "
    "behaviour when residual spans are supplied. It is not a local model result "
    "and must never be reported as Gemma performance."
)


EVIDENCE_ROOT = REPO_ROOT / "artifacts" / "evidence"
REPORT_FILE_NAME = "p1-privacy-report.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prompt_identity() -> dict[str, Any]:
    """Identify the exact instruction text this run sends to the model.

    Hashed here rather than declared, so a silently edited prompt produces a
    different manifest instead of a comparable one.
    """

    return {
        "adapter_version": GEMMA_ADAPTER_VERSION,
        "instruction_characters": len(SYSTEM_INSTRUCTION),
        "prompt_sha256": hashlib.sha256(
            (GEMMA_ADAPTER_VERSION + "::" + SYSTEM_INSTRUCTION).encode("utf-8")
        ).hexdigest(),
    }


def model_identity(args: argparse.Namespace) -> dict[str, Any] | None:
    """Identify the model file actually loaded, or refuse the run.

    Preregistration condition 4. The file hash is computed from the file on
    disk; a pasted hash is not evidence that this file was the one served.
    """

    if not args.gemma_url:
        return None
    missing = [
        name
        for name, value in (
            ("--model-repo", args.model_repo),
            ("--model-revision", args.model_revision),
            ("--model-quantization", args.model_quantization),
            ("--model-path", args.model_path),
        )
        if not value
    ]
    if missing:
        raise SystemExit(
            "refusing a model-backed run without model identity: missing "
            + ", ".join(missing)
            + " (see corpus/PREREGISTRATION.md condition 4)"
        )
    path = Path(args.model_path)
    if not path.is_file():
        raise SystemExit(f"model file not found, so it cannot be identified: {path}")
    return {
        "repository": args.model_repo,
        "revision": args.model_revision,
        "file_name": path.name,
        "quantization": args.model_quantization,
        "file_sha256": file_sha256(path),
        "file_bytes": path.stat().st_size,
    }


def _display_path(path: Path) -> str:
    """Repository-relative when possible, absolute otherwise."""

    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def recorded_frozen_runs() -> list[dict[str, str]]:
    """Every frozen-split report already written under the evidence root."""

    recorded: list[dict[str, str]] = []
    if not EVIDENCE_ROOT.exists():
        return recorded
    for report_path in sorted(EVIDENCE_ROOT.glob(f"*/{REPORT_FILE_NAME}")):
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):  # pragma: no cover - unreadable evidence
            continue
        if report.get("split") == "test":
            recorded.append(
                {
                    "run_id": str(report.get("run_id")),
                    "frozen_test_run_id": str(report.get("frozen_test_run_id")),
                    "path": _display_path(report_path),
                }
            )
    return recorded


def guard_frozen_split(args: argparse.Namespace) -> None:
    """Preregistration conditions 1 and 5: the frozen split is read once."""

    if not args.preregistration_approved:
        raise SystemExit(
            "refusing to read the frozen test split: pass --preregistration-approved with the auditor approval record "
            "(see corpus/PREREGISTRATION.md stop point 2)"
        )
    if not args.frozen_test_run_id:
        raise SystemExit(
            "refusing to read the frozen test split without --frozen-test-run-id "
            "(see corpus/PREREGISTRATION.md condition 5)"
        )
    recorded = recorded_frozen_runs()
    if not recorded:
        return
    already = ", ".join(f"{entry['frozen_test_run_id']} at {entry['path']}" for entry in recorded)
    if not args.supersedes:
        raise SystemExit(
            f"the frozen test split has already been measured: {already}. A second run requires a new auditor "
            "approval and --supersedes naming the run it replaces (see corpus/PREREGISTRATION.md condition 5)"
        )
    known = {entry["frozen_test_run_id"] for entry in recorded}
    if args.supersedes not in known:
        raise SystemExit(
            f"--supersedes {args.supersedes} does not name a recorded frozen run. Recorded: {already}"
        )
    if args.frozen_test_run_id in known:
        raise SystemExit(
            f"--frozen-test-run-id {args.frozen_test_run_id} is already recorded; a replacement run needs a new id"
        )


def wilson_interval(successes: int, total: int, z: float = 1.96) -> dict[str, float | None]:
    if total == 0:
        return {"point": None, "low": None, "high": None}
    proportion = successes / total
    denominator = 1 + z**2 / total
    centre = proportion + z**2 / (2 * total)
    spread = z * math.sqrt(proportion * (1 - proportion) / total + z**2 / (4 * total**2))
    return {
        "point": round(proportion, 6),
        "low": round((centre - spread) / denominator, 6),
        "high": round((centre + spread) / denominator, 6),
    }


@dataclass
class PathMetrics:
    """Accumulates span-level and document-level counts for one comparator."""

    mode: str
    egress_profile: str = EGRESS_SUMMARY_TEXT
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    overlap_recovered: int = 0
    ground_truth_total: int = 0
    accepted: int = 0
    quarantined: int = 0
    escaped_records: int = 0
    escaped_surfaces: int = 0
    false_quarantine: int = 0
    per_class: dict[str, dict[str, int]] = field(default_factory=dict)
    model_status_counts: dict[str, int] = field(default_factory=dict)
    model_latencies_ms: list[int] = field(default_factory=list)
    approved_residual_spans: int = 0

    def add_class(self, identifier_class: str, key: str) -> None:
        entry = self.per_class.setdefault(identifier_class, {"true_positive": 0, "false_negative": 0, "false_positive": 0})
        entry[key] += 1

    def to_wire(self) -> dict[str, Any]:
        detected_total = self.true_positive + self.false_positive
        return {
            "mode": self.mode,
            "egress_profile": self.egress_profile,
            "span_level": {
                "ground_truth_spans": self.ground_truth_total,
                "detected_spans": detected_total,
                "true_positive": self.true_positive,
                "false_positive": self.false_positive,
                "false_negative": self.false_negative,
                "exact_recall": wilson_interval(self.true_positive, self.ground_truth_total),
                "exact_precision": wilson_interval(self.true_positive, detected_total),
                "overlap_recall": wilson_interval(self.overlap_recovered, self.ground_truth_total),
            },
            "document_level": {
                "records": self.accepted + self.quarantined,
                "accepted": self.accepted,
                "quarantined": self.quarantined,
                "acceptance_rate": wilson_interval(self.accepted, self.accepted + self.quarantined),
                "records_with_escaped_direct_identifier": self.escaped_records,
                "escaped_direct_identifier_surfaces": self.escaped_surfaces,
                "false_quarantine": self.false_quarantine,
            },
            "local_model": {
                "status_counts": dict(sorted(self.model_status_counts.items())),
                "approved_residual_spans": self.approved_residual_spans,
                "latency_ms_p50": _percentile(self.model_latencies_ms, 50),
                "latency_ms_p95": _percentile(self.model_latencies_ms, 95),
                "latency_ms_max": max(self.model_latencies_ms) if self.model_latencies_ms else None,
            },
            "per_class": {
                name: dict(sorted(values.items())) for name, values in sorted(self.per_class.items())
            },
        }


def _percentile(values: list[int], percentile: int) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    quantiles = statistics.quantiles(sorted(values), n=100, method="inclusive")
    return float(quantiles[min(percentile, 100) - 1])


def note_from_record(record: dict[str, Any]) -> LabNote:
    return LabNote.parse(
        {
            "case_key": record["record_id"],
            "note_text": record["text"],
            "tenant_id": "lab-eval",
            "region": "eu-central",
            "gene": record["structured"]["gene"],
            "hgvs_c": record["structured"]["hgvs_c"],
            "hgvs_p": record["structured"]["hgvs_p"],
            "assembly": record["structured"]["assembly"],
            "data_mode": record["data_mode"],
        }
    )


def oracle_stub_transport(record: dict[str, Any], detector: DeterministicDetector) -> Callable[[str, float], str]:
    text = record["text"]
    detected = {(span.start, span.end) for span in detector.detect(text)}
    missing = [span for span in record["spans"] if (span["start"], span["end"]) not in detected]

    def transport(note_text: str, timeout_seconds: float) -> str:
        return json.dumps(
            {
                "spans": [
                    {"start": s["start"], "end": s["end"], "identifier_class": s["identifier_class"]}
                    for s in missing[:8]
                ]
            }
        )

    return transport


def evaluate_record(gate: PrivacyGate, record: dict[str, Any], metrics: PathMetrics) -> None:
    text = record["text"]
    result = gate.process(note_from_record(record))

    ground_truth = {(s["start"], s["end"]): s["identifier_class"] for s in record["spans"]}
    predicted = {
        (span.start, span.end): span.identifier_class
        for span in tuple(result.local_only.deterministic_spans) + tuple(result.local_only.approved_residual_spans)
    }

    metrics.ground_truth_total += len(ground_truth)
    metrics.approved_residual_spans += len(result.local_only.approved_residual_spans)

    for offsets, identifier_class in ground_truth.items():
        if offsets in predicted:
            metrics.true_positive += 1
            metrics.add_class(identifier_class, "true_positive")
        else:
            metrics.false_negative += 1
            metrics.add_class(identifier_class, "false_negative")
        if any(offsets[0] < end and start < offsets[1] for start, end in predicted):
            metrics.overlap_recovered += 1

    for offsets, identifier_class in predicted.items():
        if offsets not in ground_truth:
            metrics.false_positive += 1
            metrics.add_class(identifier_class, "false_positive")

    status = result.gemma.status
    metrics.model_status_counts[status] = metrics.model_status_counts.get(status, 0) + 1
    if result.gemma.latency_ms is not None:
        metrics.model_latencies_ms.append(result.gemma.latency_ms)

    if result.decision == DECISION_ACCEPTED:
        metrics.accepted += 1
        blob = json.dumps(result.cloud_bound_payload, ensure_ascii=False)
        escaped = [
            text[s["start"] : s["end"]]
            for s in record["spans"]
            if s["identifier_class"] in DIRECT_IDENTIFIER_CLASSES and text[s["start"] : s["end"]] in blob
        ]
        if escaped:
            metrics.escaped_records += 1
            metrics.escaped_surfaces += len(escaped)
    else:
        metrics.quarantined += 1
        residual_present = any(
            s["identifier_class"] in DIRECT_IDENTIFIER_CLASSES
            and text[s["start"] : s["end"]] in result.local_only.redacted_summary
            for s in record["spans"]
        )
        if not residual_present:
            metrics.false_quarantine += 1


def build_gate(
    signer: LocalSigner,
    transport: Callable[[str, float], str] | None,
    model_id: str,
    egress_profile: str = EGRESS_SUMMARY_TEXT,
) -> PrivacyGate:
    return PrivacyGate(
        signer=signer,
        gemma=GemmaResidualDetector(transport, model_id=model_id),
        egress_profile=egress_profile,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    split_path = REPO_ROOT / "corpus" / "generated" / f"{args.split}.json"
    if not split_path.exists():
        raise SystemExit(f"corpus split not generated: {split_path}. Run corpus/generator.py first.")
    records = json.loads(split_path.read_text(encoding="utf-8"))

    try:
        signer = load_signer()
    except SigningKeyUnavailable:
        signer = LocalSigner(key_id="ephemeral-eval-key", key=b"evaluation-only-key-material")

    detector = DeterministicDetector()
    baseline = PathMetrics(mode=MODE_DETERMINISTIC, egress_profile=EGRESS_SUMMARY_TEXT)
    for record in records:
        evaluate_record(build_gate(signer, None, "none"), record, baseline)

    structured_only = PathMetrics(mode=MODE_STRUCTURED_ONLY, egress_profile=EGRESS_STRUCTURED_ONLY)
    for record in records:
        evaluate_record(
            build_gate(signer, None, "none", EGRESS_STRUCTURED_ONLY), record, structured_only
        )

    comparison: PathMetrics | None = None
    if args.gemma_url:
        comparison = PathMetrics(mode=MODE_LOCAL_MODEL)
        transport = LlamaServerTransport(base_url=args.gemma_url, model_id=args.model_id)
        for record in records:
            evaluate_record(build_gate(signer, transport, args.model_id), record, comparison)
    elif args.oracle_stub:
        comparison = PathMetrics(mode=MODE_ORACLE_STUB)
        for record in records:
            evaluate_record(build_gate(signer, oracle_stub_transport(record, detector), "oracle-stub"), record, comparison)

    incremental = None
    if comparison is not None:
        incremental = {
            "incremental_true_positive": comparison.true_positive - baseline.true_positive,
            "incremental_false_positive": comparison.false_positive - baseline.false_positive,
            "incremental_accepted_payloads": comparison.accepted - baseline.accepted,
            "incremental_accepted_escapes": comparison.escaped_surfaces - baseline.escaped_surfaces,
        }

    manifest_reference = REPO_ROOT / "corpus" / "PRIVACY_CORPUS_MANIFEST.json"
    corpus_manifest = json.loads(manifest_reference.read_text(encoding="utf-8"))

    result: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": args.run_id,
        "split": args.split,
        "split_sha256": corpus_manifest["splits"][args.split]["sha256"],
        "record_count": len(records),
        "corpus_version": corpus_manifest["corpus_version"],
        "corpus_seed": corpus_manifest["seed"],
        "generator_sha256": corpus_manifest["generator_sha256"],
        "evidence_scope": args.evidence_scope,
        "preregistration_approval": args.preregistration_approved,
        "frozen_test_run_id": args.frozen_test_run_id,
        "supersedes_frozen_test_run_id": args.supersedes,
        "local_model": {
            "mode": comparison.mode if comparison is not None else "not_run",
            "model_id": args.model_id if args.gemma_url else None,
            "endpoint_configured": bool(args.gemma_url),
            "identity": args.model_identity_record,
            "prompt": prompt_identity(),
            "disclaimer": ORACLE_STUB_DISCLAIMER if args.oracle_stub else None,
        },
        "baseline": baseline.to_wire(),
        "structured_only_egress": structured_only.to_wire(),
        "structured_only_egress_note": STRUCTURED_ONLY_NOTE,
        "comparison": comparison.to_wire() if comparison is not None else None,
        "incremental": incremental,
        "mandatory_safety_gate": {
            "rule": "zero seeded direct-identifier spans in accepted payloads",
            "baseline_escapes": baseline.escaped_surfaces,
            "structured_only_escapes": structured_only.escaped_surfaces,
            "comparison_escapes": comparison.escaped_surfaces if comparison is not None else None,
            "result": "PASS"
            if baseline.escaped_surfaces == 0
            and structured_only.escaped_surfaces == 0
            and (comparison is None or comparison.escaped_surfaces == 0)
            else "FAIL",
        },
        "limitations": [
            "Synthetic corpus only. No real, clinical, or regulatory privacy claim is supported.",
            "Residual identifier rate is a property of the committed corpus design, not an estimate for real text.",
            "The outbound allowlist is derived from the training split and reflects the synthetic template vocabulary.",
            STRUCTURED_ONLY_NOTE,
        ],
    }
    result["content_hash"] = content_hash({k: v for k, v in result.items() if k != "content_hash"})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run protocol P1 on a corpus split.")
    parser.add_argument("--split", choices=("train", "dev", "test"), default="dev")
    parser.add_argument("--gemma-url", default=None, help="Base URL of the laboratory-local llama.cpp server.")
    parser.add_argument("--model-id", default="unconfigured")
    parser.add_argument(
        "--oracle-stub",
        action="store_true",
        help="Replay ground-truth residual spans instead of calling a model. Never a model claim.",
    )
    parser.add_argument("--preregistration-approved", default=None, help="Auditor approval record for the frozen split.")
    parser.add_argument("--model-repo", default=None, help="Repository the model file came from.")
    parser.add_argument("--model-revision", default=None, help="Repository revision of the model file.")
    parser.add_argument("--model-quantization", default=None, help="Quantisation of the model file, for example q4_0.")
    parser.add_argument("--model-path", default=None, help="Path to the model file actually served; hashed by this script.")
    parser.add_argument("--frozen-test-run-id", default=None, help="Preregistered identifier of the single frozen-split run.")
    parser.add_argument("--supersedes", default=None, help="Frozen run identifier this run replaces, when re-approved.")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if args.split == "test":
        guard_frozen_split(args)
    if args.gemma_url and args.oracle_stub:
        raise SystemExit("choose either a real local model endpoint or the oracle stub, not both")
    args.model_identity_record = model_identity(args)

    args.evidence_scope = (
        "PREREGISTERED_TEST_RUN" if args.split == "test" else f"DEVELOPMENT_SMOKE_ON_{args.split.upper()}_SPLIT"
    )
    mode = "gemma" if args.gemma_url else ("oracle-stub" if args.oracle_stub else "deterministic-only")
    args.run_id = args.run_id or args.frozen_test_run_id or f"privacy-p1-{args.split}-{mode}"

    report = run(args)
    out_dir = Path(args.out) if args.out else REPO_ROOT / "artifacts" / "evidence" / report["run_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "p1-privacy-report.json"
    manifest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"run_id: {report['run_id']}  scope: {report['evidence_scope']}")
    print(f"records: {report['record_count']}  split sha256: {report['split_sha256'][:16]}")
    baseline = report["baseline"]
    print(
        f"baseline: exact recall {baseline['span_level']['exact_recall']['point']} "
        f"({baseline['span_level']['true_positive']}/{baseline['span_level']['ground_truth_spans']}), "
        f"accepted {baseline['document_level']['accepted']}/{report['record_count']}, "
        f"escapes {baseline['document_level']['escaped_direct_identifier_surfaces']}"
    )
    structured = report["structured_only_egress"]
    print(
        f"structured-only egress: accepted {structured['document_level']['accepted']}/{report['record_count']}, "
        f"escapes {structured['document_level']['escaped_direct_identifier_surfaces']}, "
        f"structural (not a detection result)"
    )
    if report["comparison"]:
        comparison = report["comparison"]
        print(
            f"{comparison['mode']}: exact recall {comparison['span_level']['exact_recall']['point']} "
            f"({comparison['span_level']['true_positive']}/{comparison['span_level']['ground_truth_spans']}), "
            f"accepted {comparison['document_level']['accepted']}/{report['record_count']}, "
            f"escapes {comparison['document_level']['escaped_direct_identifier_surfaces']}"
        )
        print(f"incremental: {json.dumps(report['incremental'])}")
    identity = report["local_model"]["identity"]
    if identity is not None:
        print(
            f"model: {identity['repository']}@{identity['revision']} {identity['file_name']} "
            f"({identity['quantization']}) sha256 {identity['file_sha256'][:16]}"
        )
    print(f"prompt sha256: {report['local_model']['prompt']['prompt_sha256'][:16]}")
    print(f"mandatory safety gate: {report['mandatory_safety_gate']['result']}")
    print(f"manifest: {manifest_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
