from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from recall.contracts import Artifact, content_hash
from recall.scheduler.compressed_plan import (
    ManifestDeadlinePlanMismatch,
    verify_manifest_against_plan,
)
from recall.testing.deadline_policy_vectors import (
    VECTOR_PATH,
    render_deadline_policy_vectors,
)
from tests.support.compressed_v33_manifest import build_valid_c3_manifest


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_committed_deadline_vectors_are_generated_by_core() -> None:
    assert (REPO_ROOT / VECTOR_PATH).read_bytes() == render_deadline_policy_vectors(
        REPO_ROOT
    )


def test_production_plan_verifier_matches_every_deadline_golden_vector() -> None:
    fixture = json.loads((REPO_ROOT / VECTOR_PATH).read_text(encoding="utf-8"))
    plan, seed, legacy_failure_id = build_valid_c3_manifest()
    observed: dict[str, str] = {}
    for vector in fixture["vectors"]:
        artifact = _artifact_with_vector(seed, vector)
        try:
            verify_manifest_against_plan(
                artifact,
                plan,
                expected_legacy_failure_receipt_id=legacy_failure_id,
            )
        except RuntimeError:
            observed[vector["vector_id"]] = "REJECT"
        else:
            observed[vector["vector_id"]] = "ACCEPT"

    expected = {
        vector["vector_id"]: vector["expected"] for vector in fixture["vectors"]
    }
    assert observed == expected


def test_valid_vector_retains_sub_microsecond_cross_runtime_boundary() -> None:
    fixture = json.loads((REPO_ROOT / VECTOR_PATH).read_text(encoding="utf-8"))
    valid = next(
        item
        for item in fixture["vectors"]
        if item["vector_id"] == "valid_c3_fractional_microseconds"
    )
    fraction = valid["deadline_policy"]["trigger_started_at"].split(".")[1][:-1]
    assert len(fraction) == 7


@pytest.mark.parametrize(
    "vector_id",
    [
        "legacy_20_00_plus_3600_to_23_00",
        "plan_valid_authoritative_deadline_only_mismatch",
    ],
)
def test_authoritative_deadline_regressions_have_one_field_defect(
    vector_id: str,
) -> None:
    fixture = json.loads((REPO_ROOT / VECTOR_PATH).read_text(encoding="utf-8"))
    valid = next(
        item
        for item in fixture["vectors"]
        if item["vector_id"] == "valid_c3_fractional_microseconds"
    )
    rejected = next(
        item for item in fixture["vectors"] if item["vector_id"] == vector_id
    )
    valid_policy = dict(valid["deadline_policy"])
    rejected_policy = dict(rejected["deadline_policy"])

    assert rejected["manifest_context"] == valid["manifest_context"]
    assert rejected_policy.pop("authoritative_end_to_end_deadline") != (
        valid_policy.pop("authoritative_end_to_end_deadline")
    )
    assert rejected_policy == valid_policy
    assert (
        rejected_policy["execution_timeout_seconds"],
        rejected_policy["write_timeout_seconds"],
        rejected_policy["agent_timeout_seconds"],
    ) == (3600, 600, 3000)


@pytest.mark.parametrize(
    "vector_id",
    [
        "legacy_20_00_plus_3600_to_23_00",
        "plan_valid_authoritative_deadline_only_mismatch",
    ],
)
def test_authoritative_deadline_regressions_use_plan_mismatch_reason(
    vector_id: str,
) -> None:
    fixture = json.loads((REPO_ROOT / VECTOR_PATH).read_text(encoding="utf-8"))
    vector = next(
        item for item in fixture["vectors"] if item["vector_id"] == vector_id
    )
    plan, seed, legacy_failure_id = build_valid_c3_manifest()

    with pytest.raises(
        ManifestDeadlinePlanMismatch,
        match="^compressed_manifest_deadline_plan_mismatch$",
    ):
        verify_manifest_against_plan(
            _artifact_with_vector(seed, vector),
            plan,
            expected_legacy_failure_receipt_id=legacy_failure_id,
        )


@pytest.mark.parametrize(
    "vector_id",
    [
        "legacy_20_00_plus_3600_to_23_00",
        "plan_valid_authoritative_deadline_only_mismatch",
        "coherent_phase_repartition",
        "unknown_plan_hash",
    ],
)
def test_required_no_ship_regressions_stay_rejected(vector_id: str) -> None:
    fixture = json.loads((REPO_ROOT / VECTOR_PATH).read_text(encoding="utf-8"))
    vector = next(item for item in fixture["vectors"] if item["vector_id"] == vector_id)
    assert vector["expected"] == "REJECT"


def _artifact_with_vector(
    seed: Artifact,
    vector: Mapping[str, Any],
) -> Artifact:
    context = vector["manifest_context"]
    v33 = seed.payload
    v32 = v33.base
    v31 = v32.base
    v3 = replace(
        v31.base,
        cycle_id=context["cycle_id"],
        plan_version=context["plan_version"],
        plan_sha256=context["plan_sha256"],
        window_start=context["window_start"],
        window_end=context["window_end"],
        scheduled_for=context["scheduled_for"],
    )
    v31 = replace(v31, base=v3)
    v32 = replace(v32, base=v31, plan_sha256=context["plan_sha256"])
    v33 = replace(
        v33,
        base=v32,
        deadline_policy=MappingProxyType(deepcopy(vector["deadline_policy"])),
    )
    artifact = replace(seed, created_at=context["created_at"], payload=v33)
    return replace(artifact, content_hash=content_hash(artifact.to_wire()))
