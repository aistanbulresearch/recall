from __future__ import annotations

import json
import re
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from recall.contracts import (
    ArtifactStatus,
    ContractError,
    DataMode,
    ReplayStage,
    build_artifact,
    canonical_json_bytes,
)
from recall.ledger.producers import PRODUCER_REGISTRY

from .live import canonical_pubmed_metadata_hash


_STAGE_SOURCES: Mapping[ReplayStage, tuple[str, ...]] = {
    ReplayStage.STAGE_0: ("clinvar_positive_v1",),
    ReplayStage.STAGE_1: (
        "clinvar_positive_v1",
        "sahu_pubmed_esummary",
        "geo_gse248438_results_xlsx",
    ),
    ReplayStage.STAGE_2: (
        "clinvar_positive_v1",
        "sahu_pubmed_esummary",
        "geo_gse248438_results_xlsx",
        "clinvar_positive_v4",
        "clinvar_positive_v5",
    ),
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ReplayConnector:
    """Read the RCL-205 frozen package without network access or inference."""

    def __init__(self, repository_root: Path, manifest_path: Path) -> None:
        self._repository_root = repository_root.resolve()
        self._manifest_path = manifest_path.resolve()
        try:
            self._manifest = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContractError("source_schema_drift", "manifest") from exc
        self._validate_manifest_shape()

    def verify_manifest(self) -> tuple[dict[str, object], ...]:
        verified: list[dict[str, object]] = []
        for source in self._sources_by_id().values():
            capture = self._resolve_capture(source)
            try:
                body = capture.read_bytes()
            except OSError as exc:
                raise ContractError("source_schema_drift", "capture_read") from exc
            if len(body) != source["bytes"]:
                raise ContractError(
                    "artifact_integrity_failed", str(source["source_id"])
                )
            digest = sha256(body).hexdigest()
            if digest != source["sha256"]:
                raise ContractError(
                    "artifact_integrity_failed", str(source["source_id"])
                )
            verified.append(dict(source))
        expected = self._manifest["integrity"]["expected_capture_count"]
        if len(verified) != expected:
            raise ContractError("source_schema_drift", "capture_count")
        return tuple(verified)

    def build_observations(
        self,
        *,
        stage: ReplayStage,
        case_id: str,
        run_id: str,
        created_at: str,
    ) -> tuple[dict[str, object], ...]:
        verified = {item["source_id"]: item for item in self.verify_manifest()}
        return tuple(
            self._build_observation(
                verified[source_id],
                stage=stage,
                case_id=case_id,
                run_id=run_id,
                created_at=created_at,
            )
            for source_id in _STAGE_SOURCES[stage]
        )

    def tool_result(self, stage: str) -> dict[str, object]:
        """Return a bounded JSON-serializable result for an ADK FunctionTool."""
        replay_stage = ReplayStage(stage)
        sources = self._sources_by_id()
        visible: list[dict[str, object]] = []
        verified_ids = {
            str(item["source_id"]) for item in self.verify_manifest()
        }
        for source_id in _STAGE_SOURCES[replay_stage]:
            if source_id not in verified_ids:
                raise ContractError("source_schema_drift", source_id)
            source = sources[source_id]
            visible.append(
                {
                    "source_id": source_id,
                    "source_locator": source["source_locator"],
                    "source_content_hash": source["sha256"],
                    "semantic_anchor": source["semantic_anchor"],
                    "structured_fields": self._structured_fields(source),
                    "data_mode": DataMode.CAPTURED_REPLAY.value,
                }
            )
        snapshot_basis = {
            "replay_stage": replay_stage.value,
            "sources": [
                {
                    "source_id": item["source_id"],
                    "source_content_hash": item["source_content_hash"],
                }
                for item in visible
            ],
        }
        snapshot_payload = {
            "effective_at": max(
                str(sources[source_id]["retrieved_at"])
                for source_id in _STAGE_SOURCES[replay_stage]
            ),
            "observation_ids": [],
            "coverage_status": "PASS",
            "source_cursors": {"captured-replay": replay_stage.value},
            "normalized_facts": {
                "observation_count": len(visible),
                "scope": "BRCA2-exons-15-26",
            },
            "conflicts": [],
            "snapshot_hash": sha256(canonical_json_bytes(snapshot_basis)).hexdigest(),
        }
        return {
            "protocol_id": self._manifest["protocol_id"],
            "manifest_version": self._manifest["manifest_version"],
            "replay_stage": replay_stage.value,
            "observations": visible,
            "snapshot_payload": snapshot_payload,
        }

    def _build_observation(
        self,
        source: Mapping[str, Any],
        *,
        stage: ReplayStage,
        case_id: str,
        run_id: str,
        created_at: str,
    ) -> dict[str, object]:
        source_id = str(source["source_id"])
        return build_artifact(
            schema_name="EvidenceObservation",
            schema_version="1.0.0",
            artifact_id=str(uuid5(UUID(run_id), f"replay:{source_id}")),
            case_id=case_id,
            run_id=run_id,
            producer={
                "component": "rcl-205-replay-connector",
                "version": "1.0.1",
                "identity": "evidence-connector",
            },
            created_at=created_at,
            input_artifact_ids=(),
            data_mode=DataMode.CAPTURED_REPLAY,
            status=ArtifactStatus.VALID,
            payload={
                "source": self._source_family(source_id),
                "source_record_id": source_id,
                "retrieved_at": source["retrieved_at"],
                "source_version": f"rcl-205:{stage.value}:1.0.1",
                "source_locator": source["source_locator"],
                "source_content_hash": source["sha256"],
                "structured_fields": self._structured_fields(source),
                "retrieval_status": "PASS",
            },
            authorized_producers=PRODUCER_REGISTRY,
        )

    def _validate_manifest_shape(self) -> None:
        if self._manifest.get("manifest_version") != "1.0.1":
            raise ContractError("source_schema_drift", "manifest_version")
        if self._manifest.get("protocol_id") != "RCL-205":
            raise ContractError("source_schema_drift", "protocol_id")
        if not isinstance(self._manifest.get("capture_root"), str):
            raise ContractError("source_schema_drift", "capture_root")
        integrity = self._manifest.get("integrity")
        if not isinstance(integrity, Mapping) or not isinstance(
            integrity.get("expected_capture_count"), int
        ):
            raise ContractError("source_schema_drift", "integrity")
        if not isinstance(self._manifest.get("exact_functional_row"), Mapping):
            raise ContractError("source_schema_drift", "exact_functional_row")
        if not isinstance(self._manifest.get("positive_case"), Mapping):
            raise ContractError("source_schema_drift", "positive_case")
        sources = self._manifest.get("captured_sources")
        if not isinstance(sources, list) or not sources:
            raise ContractError("source_schema_drift", "captured_sources")
        if len(self._sources_by_id()) != len(sources):
            raise ContractError("source_schema_drift", "source_id")

    def _sources_by_id(self) -> dict[str, Mapping[str, Any]]:
        result: dict[str, Mapping[str, Any]] = {}
        for source in self._manifest.get("captured_sources", []):
            if not isinstance(source, Mapping):
                raise ContractError("source_schema_drift", "captured_sources")
            required = {
                "source_id",
                "data_mode",
                "capture_path",
                "retrieved_at",
                "bytes",
                "sha256",
                "source_locator",
                "semantic_anchor",
            }
            if not required.issubset(source):
                raise ContractError("source_schema_drift", "captured_source")
            source_id = source["source_id"]
            if not isinstance(source_id, str) or source_id in result:
                raise ContractError("source_schema_drift", "source_id")
            if source["data_mode"] != DataMode.CAPTURED_REPLAY.value:
                raise ContractError("source_schema_drift", "data_mode")
            if not isinstance(source["bytes"], int) or source["bytes"] < 1:
                raise ContractError("source_schema_drift", "bytes")
            if not isinstance(source["sha256"], str) or not _SHA256.fullmatch(
                source["sha256"]
            ):
                raise ContractError("source_schema_drift", "sha256")
            for field in ("retrieved_at", "source_locator", "semantic_anchor"):
                if not isinstance(source[field], str) or not source[field]:
                    raise ContractError("source_schema_drift", field)
            result[source_id] = source
        return result

    def _resolve_capture(self, source: Mapping[str, Any]) -> Path:
        raw_path = source["capture_path"]
        if not isinstance(raw_path, str):
            raise ContractError("source_schema_drift", "capture_path")
        capture = (self._repository_root / raw_path).resolve()
        capture_root = (
            self._repository_root / str(self._manifest["capture_root"])
        ).resolve()
        if not capture.is_relative_to(capture_root):
            raise ContractError("source_schema_drift", "capture_path")
        if not capture.is_file():
            raise ContractError("source_schema_drift", "capture_missing")
        return capture

    def _structured_fields(self, source: Mapping[str, Any]) -> dict[str, object]:
        fields: dict[str, object] = {
            "role": source["role"],
            "semantic_anchor": source["semantic_anchor"],
            "manifest_version": self._manifest["manifest_version"],
        }
        if str(source["source_id"]).endswith("_pubmed_esummary"):
            fields["citation_metadata"] = self._pubmed_citation_metadata(source)
        if source["source_id"] == "geo_gse248438_results_xlsx":
            row = self._manifest["exact_functional_row"]
            fields.update(
                {
                    "gene": self._manifest["positive_case"]["gene"],
                    "transcript_hgvs": row["transcript_hgvs"],
                    "genomic_hgvs": row["genomic_hgvs"],
                    "exon": row["exon"],
                    "source_scope": {
                        "gene": "BRCA2",
                        "exon_min": 15,
                        "exon_max": 26,
                    },
                    "temporal_status": row["status"],
                }
            )
        return fields

    def _pubmed_citation_metadata(
        self, source: Mapping[str, Any]
    ) -> dict[str, str]:
        try:
            document = json.loads(self._resolve_capture(source).read_bytes())
            result = document["result"]
            identifier = result["uids"][0]
            record = result[identifier]
            title = record["title"].strip()
            returned_identifier = record["uid"]
        except (
            AttributeError,
            IndexError,
            KeyError,
            OSError,
            TypeError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ContractError("source_schema_drift", "pubmed_metadata") from exc
        if (
            not isinstance(returned_identifier, str)
            or returned_identifier != identifier
            or not title
        ):
            raise ContractError("source_schema_drift", "pubmed_metadata")
        locator = f"https://pubmed.ncbi.nlm.nih.gov/{returned_identifier}/"
        return {
            "identifier": returned_identifier,
            "title": title,
            "locator": locator,
            "content_hash": canonical_pubmed_metadata_hash(
                returned_identifier, title, locator
            ),
        }

    @staticmethod
    def _source_family(source_id: str) -> str:
        return source_id.split("_", maxsplit=1)[0]
