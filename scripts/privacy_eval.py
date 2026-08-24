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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from recall.privacy.detectors import DeterministicDetector  # noqa: E402
from recall.privacy.egress import EGRESS_STRUCTURED_ONLY, EGRESS_SUMMARY_TEXT  # noqa: E402
from recall.privacy.gate import PrivacyGate  # noqa: E402
from recall.privacy.gemma import (  # noqa: E402
    GEMMA_ADAPTER_VERSION,
    LOCATOR_STRATEGY,
    LOCATOR_VERSION,
    GemmaOutcome,
    MAX_PROPOSALS,
    OLLAMA_DEFAULT_KEEP_ALIVE,
    OLLAMA_DEFAULT_OPTIONS,
    SYSTEM_INSTRUCTION,
    GemmaResidualDetector,
    LlamaServerTransport,
    OllamaChatTransport,
    locate_surfaces,
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

# The adapter default suits a GPU-served model. A quantised model on CPU needs
# a far longer deadline, and a deadline that is too short turns a working model
# into a wall of timeouts, so the value used is recorded with the results.
DEFAULT_TIMEOUT_SECONDS = 8.0

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
CHECKPOINT_FILE_NAME = "records.jsonl"

ARM_A = "model_offsets"
ARM_B = "surface_exact_search"

ARM_DECLARATION = {
    "primary": {
        "arm": ARM_A,
        "status": "preregistered primary",
        "description": (
            "The offsets the model returned are scored directly against the ground truth, "
            "exact boundary."
        ),
    },
    "secondary": {
        "arm": ARM_B,
        "status": "declared secondary, exploratory",
        "description": (
            "Each returned surface string is placed by deterministic exact search over the note, "
            "then scored exact boundary. Same model call, same tokens, no additional run."
        ),
        "ambiguity_rule": (
            "Fixed before the run: one occurrence gives that position; several occurrences each "
            "become their own candidate proposal; no occurrence refuses that proposal with "
            "model_response_surface_not_found."
        ),
    },
}

MAX_PROPOSALS_RATIONALE = (
    "Denial-of-service bound only, never a recall bound. The development split carries 10 to 15 "
    "seeded spans per note, so a cap below that floor would make a complete answer impossible to "
    "accept and would measure the cap instead of the model. The prompt states no number."
)
PREREGISTERED_ACCEPTANCE_THRESHOLDS = {
    "source": "corpus/PREREGISTRATION.md section 6",
    "status": (
        "unchanged from section 6; amendment 001 changes which arm is measured, "
        "not these thresholds"
    ),
    "rules": {
        "1_mandatory_safety_gate": (
            "Zero seeded direct-identifier spans in accepted payloads. A single escape fails "
            "the protocol regardless of every other result."
        ),
        "2_model_demo_claim": (
            "The local model earns a demo claim only if it contributes at least one incremental "
            "true positive on the frozen test split and does not increase accepted escapes."
        ),
        "3_failure_handling": (
            "Every invalid JSON, timeout, unavailable model, or uncertain span must quarantine "
            "or remain blocked by the deterministic outbound gate."
        ),
        "4_removal_rule": (
            "If the model contributes no incremental true positive, increases escapes, or "
            "cannot complete inside the allocated privacy segment, it is removed from the demo "
            "critical path. The deterministic Privacy Gate stays."
        ),
    },
    "gate_decision_rule": (
        "ACCEPTED requires all three of: the deterministic outbound scan returns CLEAR over "
        "every declared free-text field and every structured leaf; the candidate payload "
        "carries no free-text field the egress profile did not declare; and, on a free-text "
        "profile only, the local model did not fail after being invoked. Anything else is "
        "QUARANTINED and no payload is released."
    ),
}

REASONING_EFFORT_RATIONALE = (
    "A reasoning budget is not viable at this CPU throughput: the model spent its entire "
    "completion budget on reasoning and returned empty content. This is a limit of the local CPU "
    "deployment, not of the model."
)


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
                    {
                        "surface": text[s["start"] : s["end"]],
                        "start": s["start"],
                        "end": s["end"],
                        "identifier_class": s["identifier_class"],
                    }
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


def extra_body(args: argparse.Namespace) -> dict[str, Any]:
    """Server-side generation controls that change what the run measures.

    A thinking model spends its whole token budget on reasoning and returns an
    empty answer, so the reasoning control is part of the measured
    configuration and is recorded with the results rather than tuned quietly.
    """

    body: dict[str, Any] = {}
    if args.reasoning_effort:
        body["reasoning_effort"] = args.reasoning_effort
    return body


def build_transport(args: argparse.Namespace):
    """The configured local-server client, plus exactly what it sends."""

    if args.server_kind == "ollama":
        options = dict(OLLAMA_DEFAULT_OPTIONS)
        options["num_ctx"] = args.num_ctx
        options["num_thread"] = args.num_thread
        options["num_predict"] = args.num_predict
        transport = OllamaChatTransport(
            base_url=args.gemma_url,
            model_id=args.model_id,
            options=options,
            keep_alive=args.keep_alive,
            response_format=args.response_format,
        )
        return transport, transport.request_settings()
    transport = LlamaServerTransport(
        base_url=args.gemma_url,
        model_id=args.model_id,
        extra_body=extra_body(args),
    )
    return transport, {
        "server_kind": "openai",
        "endpoint": "/v1/chat/completions",
        "extra_body": extra_body(args),
    }


def transport_for_record(args: argparse.Namespace, detector: DeterministicDetector):
    """Per-record transport factory. The oracle stub needs one; a server does not."""

    if args.gemma_url:
        shared, settings = build_transport(args)
        return (lambda record: shared), settings
    if args.oracle_stub:
        return (lambda record: oracle_stub_transport(record, detector)), {"server_kind": "oracle_stub"}
    return None, {}


@dataclass(frozen=True)
class ReplayDetector:
    """Feeds an already-obtained model outcome back through the gate.

    Arm B needs the same deterministic adjudication, redaction, and outbound
    decision as arm A, applied to the same proposals placed a different way.
    Replaying the outcome gives that without a second model call.
    """

    outcome: GemmaOutcome

    def propose(self, note_text: str) -> GemmaOutcome:
        return self.outcome


def arm_outcome(result, record: dict[str, Any]) -> dict[str, Any]:
    """Document-level facts for one arm, with no raw text in the result."""

    text = record["text"]
    escaped = 0
    if result.decision == DECISION_ACCEPTED and result.cloud_bound_payload is not None:
        blob = json.dumps(result.cloud_bound_payload, ensure_ascii=False)
        escaped = sum(
            1
            for s in record["spans"]
            if s["identifier_class"] in DIRECT_IDENTIFIER_CLASSES and text[s["start"] : s["end"]] in blob
        )
    residual_present = any(
        s["identifier_class"] in DIRECT_IDENTIFIER_CLASSES
        and text[s["start"] : s["end"]] in result.local_only.redacted_summary
        for s in record["spans"]
    )
    predicted = tuple(result.local_only.deterministic_spans) + tuple(result.local_only.approved_residual_spans)
    return {
        "spans": [[span.start, span.end, span.identifier_class] for span in predicted],
        "approved_residual_count": len(result.local_only.approved_residual_spans),
        "decision": result.decision,
        "escaped_surface_count": escaped,
        "residual_present": residual_present,
    }


def build_record_row(
    signer: LocalSigner,
    args: argparse.Namespace,
    transport: Callable[[str, float], str],
    record: dict[str, Any],
) -> dict[str, Any]:
    """One model call, adjudicated twice, scored two ways.

    The row is the checkpoint unit. It carries offsets, counts, and status
    only: `artifacts/evidence/` is committed evidence, so an identifier surface
    must never be written into it.
    """

    text = record["text"]
    note = note_from_record(record)
    gate_a = build_gate(
        signer,
        transport,
        args.model_id,
        EGRESS_SUMMARY_TEXT,
        timeout_seconds=args.timeout_seconds,
    )
    result_a = gate_a.process(note)
    outcome = result_a.gemma

    located, surface_reason_codes = locate_surfaces(text, outcome.proposals)
    gate_b = PrivacyGate(
        signer=signer,
        gemma=ReplayDetector(replace(outcome, proposals=located)),
        egress_profile=EGRESS_SUMMARY_TEXT,
    )
    result_b = gate_b.process(note)

    return {
        "record_id": record["record_id"],
        "language": record["language"],
        "status": outcome.status,
        "schema_valid": outcome.schema_valid,
        "latency_ms": outcome.latency_ms,
        "reason_codes": list(outcome.reason_codes) + list(surface_reason_codes),
        "proposal_count": len(outcome.proposals),
        "located_count": len(located),
        "arms": {ARM_A: arm_outcome(result_a, record), ARM_B: arm_outcome(result_b, record)},
    }


def load_checkpoint(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows[row["record_id"]] = row
    return rows


def run_model_arm(
    records: list[dict[str, Any]],
    args: argparse.Namespace,
    signer: LocalSigner,
    transport_for: Callable[[dict[str, Any]], Callable[[str, float], str]],
    checkpoint_path: Path,
) -> list[dict[str, Any]]:
    """Score every record through the model, appending each result as it lands.

    A stopped run loses nothing: `--resume` with the same run identifier reads
    the checkpoint back and only processes what is missing.
    """

    done = load_checkpoint(checkpoint_path) if args.resume else {}
    if done:
        print(f"resuming: {len(done)} records already recorded in {_display_path(checkpoint_path)}")
    pending = [record for record in records if record["record_id"] not in done]
    rows = list(done.values())

    if pending:
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        completed = 0
        with checkpoint_path.open("a", encoding="utf-8") as handle:
            with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
                futures = {
                    pool.submit(build_record_row, signer, args, transport_for(record), record): record
                    for record in pending
                }
                for future in as_completed(futures):
                    row = future.result()
                    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    handle.flush()
                    rows.append(row)
                    completed += 1
                    print(
                        f"  [{completed}/{len(pending)}] {row['record_id']} {row['status']} "
                        f"{row['latency_ms']}ms proposals={row['proposal_count']} located={row['located_count']}",
                        flush=True,
                    )
    rows.sort(key=lambda row: row["record_id"])
    return rows


def score_rows(
    rows: list[dict[str, Any]],
    records_by_id: dict[str, dict[str, Any]],
    mode: str,
    arm: str,
) -> PathMetrics:
    """Recompute one arm's metrics from stored rows and the corpus ground truth."""

    metrics = PathMetrics(mode=mode, egress_profile=EGRESS_SUMMARY_TEXT)
    for row in rows:
        record = records_by_id[row["record_id"]]
        entry = row["arms"][arm]
        ground_truth = {(s["start"], s["end"]): s["identifier_class"] for s in record["spans"]}
        predicted = {(start, end): name for start, end, name in entry["spans"]}

        metrics.ground_truth_total += len(ground_truth)
        metrics.approved_residual_spans += entry["approved_residual_count"]

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

        metrics.model_status_counts[row["status"]] = metrics.model_status_counts.get(row["status"], 0) + 1
        if row["latency_ms"] is not None:
            metrics.model_latencies_ms.append(row["latency_ms"])

        if entry["decision"] == DECISION_ACCEPTED:
            metrics.accepted += 1
            if entry["escaped_surface_count"]:
                metrics.escaped_records += 1
                metrics.escaped_surfaces += entry["escaped_surface_count"]
        else:
            metrics.quarantined += 1
            if not entry["residual_present"]:
                metrics.false_quarantine += 1
    return metrics


def deterministic_metrics(
    records: list[dict[str, Any]],
    signer: LocalSigner,
    mode: str,
    egress_profile: str,
) -> PathMetrics:
    metrics = PathMetrics(mode=mode, egress_profile=egress_profile)
    for record in records:
        evaluate_record(build_gate(signer, None, "none", egress_profile), record, metrics)
    return metrics


def split_languages(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "combined": records,
        "tr": [record for record in records if record["language"] == "tr"],
        "en": [record for record in records if record["language"] == "en"],
    }


def pick_smoke(records: list[dict[str, Any]], per_language: int = 3) -> list[dict[str, Any]]:
    """A balanced handful, used to decide whether the full run is worth starting."""

    chosen: list[dict[str, Any]] = []
    for language in ("tr", "en"):
        chosen.extend([r for r in records if r["language"] == language][:per_language])
    return chosen


def build_gate(
    signer: LocalSigner,
    transport: Callable[[str, float], str] | None,
    model_id: str,
    egress_profile: str = EGRESS_SUMMARY_TEXT,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> PrivacyGate:
    return PrivacyGate(
        signer=signer,
        gemma=GemmaResidualDetector(transport, model_id=model_id, timeout_seconds=timeout_seconds),
        egress_profile=egress_profile,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    split_path = REPO_ROOT / "corpus" / "generated" / f"{args.split}.json"
    if not split_path.exists():
        raise SystemExit(f"corpus split not generated: {split_path}. Run corpus/generator.py first.")
    records = json.loads(split_path.read_text(encoding="utf-8"))
    if args.smoke:
        records = pick_smoke(records)
    records_by_id = {record["record_id"]: record for record in records}
    groups = {name: group for name, group in split_languages(records).items() if group}

    try:
        signer = load_signer()
    except SigningKeyUnavailable:
        signer = LocalSigner(key_id="ephemeral-eval-key", key=b"evaluation-only-key-material")

    detector = DeterministicDetector()

    baseline = {
        name: deterministic_metrics(group, signer, MODE_DETERMINISTIC, EGRESS_SUMMARY_TEXT)
        for name, group in groups.items()
    }
    structured_only = {
        name: deterministic_metrics(group, signer, MODE_STRUCTURED_ONLY, EGRESS_STRUCTURED_ONLY)
        for name, group in groups.items()
    }

    transport_for, transport_settings = transport_for_record(args, detector)
    arm_a: dict[str, PathMetrics] = {}
    arm_b: dict[str, PathMetrics] = {}
    rows: list[dict[str, Any]] = []
    mode = MODE_LOCAL_MODEL if args.gemma_url else MODE_ORACLE_STUB

    if transport_for is not None:
        rows = run_model_arm(records, args, signer, transport_for, args.out_dir / CHECKPOINT_FILE_NAME)
        rows_by_language = {
            "combined": rows,
            "tr": [row for row in rows if row["language"] == "tr"],
            "en": [row for row in rows if row["language"] == "en"],
        }
        for name, group_rows in rows_by_language.items():
            if not group_rows:
                continue
            arm_a[name] = score_rows(group_rows, records_by_id, f"{mode}/{ARM_A}", ARM_A)
            arm_b[name] = score_rows(group_rows, records_by_id, f"{mode}/{ARM_B}", ARM_B)

    def incremental_for(arm: dict[str, PathMetrics]) -> dict[str, int] | None:
        if "combined" not in arm:
            return None
        combined, base = arm["combined"], baseline["combined"]
        return {
            "incremental_true_positive": combined.true_positive - base.true_positive,
            "incremental_false_positive": combined.false_positive - base.false_positive,
            "incremental_accepted_payloads": combined.accepted - base.accepted,
            "incremental_accepted_escapes": combined.escaped_surfaces - base.escaped_surfaces,
        }

    manifest_reference = REPO_ROOT / "corpus" / "PRIVACY_CORPUS_MANIFEST.json"
    corpus_manifest = json.loads(manifest_reference.read_text(encoding="utf-8"))

    def wire(metrics: dict[str, PathMetrics]) -> dict[str, Any] | None:
        return {name: value.to_wire() for name, value in metrics.items()} or None

    comparison_escapes = arm_a["combined"].escaped_surfaces if "combined" in arm_a else None

    result: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": args.run_id,
        "split": args.split,
        "split_sha256": corpus_manifest["splits"][args.split]["sha256"],
        "corpus_split_sha256": {
            name: corpus_manifest["splits"][name]["sha256"] for name in ("dev", "test", "train")
        },
        "record_count": len(records),
        "record_selection": "balanced smoke subset" if args.smoke else "full split",
        "corpus_version": corpus_manifest["corpus_version"],
        "corpus_seed": corpus_manifest["seed"],
        "generator_sha256": corpus_manifest["generator_sha256"],
        "evidence_scope": args.evidence_scope,
        "preregistration_approval": args.preregistration_approved,
        "frozen_test_run_id": args.frozen_test_run_id,
        "supersedes_frozen_test_run_id": args.supersedes,
        "arms": ARM_DECLARATION,
        "local_model": {
            "mode": mode if transport_for is not None else "not_run",
            "model_id": args.model_id if args.gemma_url else None,
            "endpoint_configured": bool(args.gemma_url),
            "identity": args.model_identity_record,
            "prompt": prompt_identity(),
            "disclaimer": ORACLE_STUB_DISCLAIMER if args.oracle_stub else None,
        },
        "measurement_constraints": {
            "max_proposals": {"value": MAX_PROPOSALS, "rationale": MAX_PROPOSALS_RATIONALE},
            "reasoning_effort": {
                "value": args.reasoning_effort if args.server_kind == "openai" else "think=false",
                "rationale": REASONING_EFFORT_RATIONALE,
            },
            "locator_version": LOCATOR_VERSION,
            "locator_strategy": LOCATOR_STRATEGY,
            "acceptance_thresholds": PREREGISTERED_ACCEPTANCE_THRESHOLDS,
            "transport": transport_settings,
            "concurrency": args.concurrency,
            "timeout_seconds": args.timeout_seconds,
            "resumed": bool(args.resume),
        },
        "baseline": wire(baseline),
        "structured_only_egress": wire(structured_only),
        "structured_only_egress_note": STRUCTURED_ONLY_NOTE,
        "comparison_arm_a": wire(arm_a),
        "comparison_arm_b": wire(arm_b),
        "incremental_arm_a": incremental_for(arm_a),
        "incremental_arm_b": incremental_for(arm_b),
        "mandatory_safety_gate": {
            "rule": "zero seeded direct-identifier spans in accepted payloads",
            "baseline_escapes": baseline["combined"].escaped_surfaces,
            "structured_only_escapes": structured_only["combined"].escaped_surfaces,
            "comparison_escapes": comparison_escapes,
            "result": "PASS"
            if baseline["combined"].escaped_surfaces == 0
            and structured_only["combined"].escaped_surfaces == 0
            and (comparison_escapes is None or comparison_escapes == 0)
            else "FAIL",
        },
        "limitations": [
            "Synthetic corpus only. No real, clinical, or regulatory privacy claim is supported.",
            "Residual identifier rate is a property of the committed corpus design, not an estimate for real text.",
            "The outbound allowlist is derived from the training split and reflects the synthetic template vocabulary.",
            STRUCTURED_ONLY_NOTE,
            "Approved residual span counts follow the primary arm, because the gate adjudicates the offsets the model returned.",
        ],
    }
    result["content_hash"] = content_hash({k: v for k, v in result.items() if k != "content_hash"})
    return result


def summarise(report: dict[str, Any]) -> None:
    print(f"run_id: {report['run_id']}  scope: {report['evidence_scope']}  {report['record_selection']}")
    print(f"records: {report['record_count']}  split sha256: {report['split_sha256'][:16]}")
    for name in ("combined", "tr", "en"):
        entry = (report["baseline"] or {}).get(name)
        if entry is None:
            continue
        span, doc = entry["span_level"], entry["document_level"]
        print(
            f"baseline[{name}]: exact recall {span['exact_recall']['point']} "
            f"({span['true_positive']}/{span['ground_truth_spans']}), "
            f"accepted {doc['accepted']}/{doc['records']}, escapes {doc['escaped_direct_identifier_surfaces']}"
        )
    structured = (report["structured_only_egress"] or {}).get("combined")
    if structured:
        doc = structured["document_level"]
        print(
            f"structured-only egress: accepted {doc['accepted']}/{doc['records']}, "
            f"escapes {doc['escaped_direct_identifier_surfaces']}, structural (not a detection result)"
        )
    for label, key in (("arm A (primary, model offsets)", "comparison_arm_a"), ("arm B (secondary, surface search)", "comparison_arm_b")):
        arm = report[key]
        if not arm:
            continue
        for name in ("combined", "tr", "en"):
            entry = arm.get(name)
            if entry is None:
                continue
            span, doc = entry["span_level"], entry["document_level"]
            print(
                f"{label} [{name}]: exact TP {span['true_positive']}/{span['ground_truth_spans']} "
                f"recall {span['exact_recall']['point']}, FP {span['false_positive']}, "
                f"accepted {doc['accepted']}/{doc['records']}, escapes {doc['escaped_direct_identifier_surfaces']}"
            )
        model = arm["combined"]["local_model"]
        print(f"   status {model['status_counts']} latency p50 {model['latency_ms_p50']} p95 {model['latency_ms_p95']}")
    for key in ("incremental_arm_a", "incremental_arm_b"):
        if report[key]:
            print(f"{key}: {json.dumps(report[key])}")
    identity = report["local_model"]["identity"]
    if identity is not None:
        print(
            f"model: {identity['repository']}@{identity['revision']} {identity['file_name']} "
            f"({identity['quantization']}) sha256 {identity['file_sha256'][:16]}"
        )
    print(f"prompt sha256: {report['local_model']['prompt']['prompt_sha256'][:16]}")
    constraints = report["measurement_constraints"]
    print(f"max proposals: {constraints['max_proposals']['value']}  concurrency: {constraints['concurrency']}")
    print(f"locator: {constraints['locator_version']}  adapter: {report['local_model']['prompt']['adapter_version']}")
    print(f"split hashes: " + "  ".join(f"{k}={v[:12]}" for k, v in sorted(report["corpus_split_sha256"].items())))
    print(f"mandatory safety gate: {report['mandatory_safety_gate']['result']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run protocol P1 on a corpus split.")
    parser.add_argument("--split", choices=("train", "dev", "test"), default="dev")
    parser.add_argument("--gemma-url", default=None, help="Base URL of the laboratory-local model server.")
    parser.add_argument("--model-id", default="unconfigured")
    parser.add_argument(
        "--server-kind",
        choices=("ollama", "openai"),
        default="ollama",
        help="Ollama native route, which carries generation options, or an OpenAI-compatible route.",
    )
    parser.add_argument("--num-ctx", type=int, default=OLLAMA_DEFAULT_OPTIONS["num_ctx"])
    parser.add_argument("--num-thread", type=int, default=OLLAMA_DEFAULT_OPTIONS["num_thread"])
    parser.add_argument("--num-predict", type=int, default=OLLAMA_DEFAULT_OPTIONS["num_predict"])
    parser.add_argument("--keep-alive", default=OLLAMA_DEFAULT_KEEP_ALIVE)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument(
        "--response-format",
        default=None,
        help="Server-side response format constraint, for example 'json'. Recorded with the results.",
    )
    parser.add_argument("--resume", action="store_true", help="Continue a run of the same identifier from its checkpoint.")
    parser.add_argument("--smoke", action="store_true", help="Balanced six-record subset used to decide whether the full run is worth starting.")
    parser.add_argument(
        "--reasoning-effort",
        default=None,
        help="Passed through to an OpenAI-compatible server, for example 'none' to stop a thinking model consuming the answer budget.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-note deadline for the local model. Retry stays fixed at zero.",
    )
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
        if args.smoke:
            raise SystemExit("the frozen split is measured in full, never as a smoke subset")
    if args.gemma_url and args.oracle_stub:
        raise SystemExit("choose either a real local model endpoint or the oracle stub, not both")
    args.model_identity_record = model_identity(args)

    args.evidence_scope = (
        "PREREGISTERED_TEST_RUN" if args.split == "test" else f"DEVELOPMENT_SMOKE_ON_{args.split.upper()}_SPLIT"
    )
    mode = "gemma" if args.gemma_url else ("oracle-stub" if args.oracle_stub else "deterministic-only")
    args.run_id = args.run_id or args.frozen_test_run_id or f"privacy-p1-{args.split}-{mode}"
    args.out_dir = Path(args.out) if args.out else EVIDENCE_ROOT / args.run_id
    args.out_dir.mkdir(parents=True, exist_ok=True)

    report = run(args)
    manifest_path = args.out_dir / REPORT_FILE_NAME
    manifest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summarise(report)
    print(f"manifest: {_display_path(manifest_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
