from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from google.adk.tools.function_tool import FunctionTool

from recall.connectors.live import canonical_pubmed_metadata_hash
from recall.connectors.replay import ReplayConnector
from recall.contracts import ContractError, ReplayStage


REPO_ROOT = Path(__file__).parents[2]
MANIFEST = REPO_ROOT / "docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json"
CASE_ID = "728d6e23-5ee4-4bd4-9319-4304f55628f3"
RUN_ID = "b1d74cb8-25ac-4a84-ab9d-5a71a366c2da"


def test_manifest_1_0_1_verifies_all_frozen_captures() -> None:
    connector = ReplayConnector(REPO_ROOT, MANIFEST)

    verified = connector.verify_manifest()

    assert len(verified) == 10
    assert {item["data_mode"] for item in verified} == {"CAPTURED_REPLAY"}


@pytest.mark.parametrize(
    ("stage", "expected_ids"),
    [
        (ReplayStage.STAGE_0, {"clinvar_positive_v1"}),
        (
            ReplayStage.STAGE_1,
            {
                "clinvar_positive_v1",
                "sahu_pubmed_esummary",
                "geo_gse248438_results_xlsx",
            },
        ),
        (
            ReplayStage.STAGE_2,
            {
                "clinvar_positive_v1",
                "sahu_pubmed_esummary",
                "geo_gse248438_results_xlsx",
                "clinvar_positive_v4",
                "clinvar_positive_v5",
            },
        ),
    ],
)
def test_replay_stage_visibility_is_closed_and_cumulative(
    stage: ReplayStage, expected_ids: set[str]
) -> None:
    connector = ReplayConnector(REPO_ROOT, MANIFEST)

    observations = connector.build_observations(
        stage=stage,
        case_id=CASE_ID,
        run_id=RUN_ID,
        created_at="2026-08-22T06:30:00Z",
    )

    assert {item["source_record_id"] for item in observations} == expected_ids
    assert {item["data_mode"] for item in observations} == {"CAPTURED_REPLAY"}
    assert {item["producer"]["identity"] for item in observations} == {
        "evidence-connector"
    }


def test_geo_observation_exposes_only_manifest_bound_exact_row() -> None:
    connector = ReplayConnector(REPO_ROOT, MANIFEST)

    observations = connector.build_observations(
        stage=ReplayStage.STAGE_1,
        case_id=CASE_ID,
        run_id=RUN_ID,
        created_at="2026-08-22T06:30:00Z",
    )
    geo = next(
        item
        for item in observations
        if item["source_record_id"] == "geo_gse248438_results_xlsx"
    )

    assert geo["structured_fields"]["transcript_hgvs"] == (
        "NM_000059.4(BRCA2):c.7522G>C"
    )
    assert geo["structured_fields"]["source_scope"] == {
        "gene": "BRCA2",
        "exon_min": 15,
        "exon_max": 26,
    }
    assert geo["structured_fields"]["temporal_status"].startswith("AS_CAPTURED_")


def test_pubmed_observation_derives_refetch_metadata_from_frozen_capture() -> None:
    connector = ReplayConnector(REPO_ROOT, MANIFEST)

    observations = connector.build_observations(
        stage=ReplayStage.STAGE_1,
        case_id=CASE_ID,
        run_id=RUN_ID,
        created_at="2026-08-22T06:30:00Z",
    )
    pubmed = next(
        item
        for item in observations
        if item["source_record_id"] == "sahu_pubmed_esummary"
    )

    assert pubmed["structured_fields"]["citation_metadata"] == {
        "identifier": "39779848",
        "title": (
            "Saturation genome editing-based clinical classification of "
            "BRCA2 variants."
        ),
        "locator": "https://pubmed.ncbi.nlm.nih.gov/39779848/",
        "content_hash": canonical_pubmed_metadata_hash(
            "39779848",
            "Saturation genome editing-based clinical classification of "
            "BRCA2 variants.",
            "https://pubmed.ncbi.nlm.nih.gov/39779848/",
        ),
    }


def test_function_tool_result_is_json_serializable_and_hash_derived() -> None:
    result = ReplayConnector(REPO_ROOT, MANIFEST).tool_result("stage-1")

    encoded = json.dumps(result, sort_keys=True)
    assert "stage-1" in encoded
    assert result["snapshot_payload"]["normalized_facts"] == {
        "observation_count": 3,
        "scope": "BRCA2-exons-15-26",
    }
    assert len(result["snapshot_payload"]["snapshot_hash"]) == 64


def test_adk_function_tool_accepts_sync_replay_connector() -> None:
    connector = ReplayConnector(REPO_ROOT, MANIFEST)

    result = asyncio.run(
        FunctionTool(connector.tool_result).run_async(
            args={"stage": "stage-1"}, tool_context=object()
        )
    )

    assert result["replay_stage"] == "stage-1"
    assert len(result["observations"]) == 3


def test_adk_function_tool_accepts_async_replay_wrapper() -> None:
    connector = ReplayConnector(REPO_ROOT, MANIFEST)

    async def replay_tool(stage: str) -> dict[str, object]:
        return connector.tool_result(stage)

    result = asyncio.run(
        FunctionTool(replay_tool).run_async(
            args={"stage": "stage-1"}, tool_context=object()
        )
    )

    assert result["snapshot_payload"]["coverage_status"] == "PASS"


def test_mutated_capture_fails_loudly(tmp_path: Path) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source = manifest["captured_sources"][0]
    source_path = tmp_path / source["capture_path"]
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"mutated")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ContractError, match="artifact_integrity_failed"):
        ReplayConnector(tmp_path, manifest_path).verify_manifest()


def test_capture_path_cannot_escape_repository(tmp_path: Path) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["captured_sources"][0]["capture_path"] = "../escape.bin"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ContractError, match="source_schema_drift:capture_path"):
        ReplayConnector(tmp_path, manifest_path).verify_manifest()
