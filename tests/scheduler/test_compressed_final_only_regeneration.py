from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from recall.contracts import content_hash
import recall.scheduler.compressed_plan as compressed_plan_module
from recall.scheduler.compressed_plan import PLAN_PATH, parse_compressed_plan
from recall.scheduler.compressed_preparation import load_compressed_bundle
from recall.scheduler.entrypoint import (
    _require_compressed_source_binding,
    execute,
)
from recall.scheduler.history import DAY1_EVIDENCE_PATH
from recall.testing.compressed_final_only_regeneration import (
    FinalOnlyHistoricalInput,
    render_final_only_candidate,
    render_final_only_preparation_candidate,
)


ROOT = Path(__file__).resolve().parents[2]
C6_START = "2026-08-29T16:00:00Z"
C6_END = "2026-08-29T23:43:59Z"


def _candidate_paths() -> tuple[Path, Path]:
    return (
        Path(os.environ.get("RECALL_FINAL_ONLY_PLAN_CANDIDATE", ROOT / PLAN_PATH)),
        Path(
            os.environ.get(
                "RECALL_FINAL_ONLY_BUNDLE_CANDIDATE",
                ROOT
                / "artifacts/evidence/cohort-compression/preparation-bundle-v2.json",
            )
        ),
    )


def _director_checkpoint_history() -> tuple[FinalOnlyHistoricalInput, ...]:
    return (
        FinalOnlyHistoricalInput(
            "c1",
            "IMMUTABLE_EXECUTED",
            "COMPLETE",
            "5f18998f11c17b8feef52f90edd9319532a36d525dbea9e9a40538425a28dfa4",
            "dev_recall_m2_compressed_p5f18998f11c1_c1_20260826_",
            "bd51bd00-fcf4-5d91-a45d-4d203e02127c",
            "372b7e3e64805b1518793d944422bbf35e6f404c2d5b3392c3442c960427c02c",
            "f4c677c8-e927-5ee6-a85f-cdd0c2fe4845",
            "4303d3e75fe88421ea21b8f5c2f353d86abea30ec0c56620c65c35693083694c",
        ),
        FinalOnlyHistoricalInput(
            "c2",
            "IMMUTABLE_EXECUTED",
            "COMPLETE",
            "4c2b5ededcf79472781d0d58eca23b46278dcd0a9cc3fcaeb8c307f7a6c84e89",
            "dev_recall_m2_compressed_p4c2b5ededcf7_c2_20260827_",
            "d89d209e-22f4-5e9e-84ed-329857bb4a27",
            "ba588c3777035bb2d72eecfa8951970472e1127efa1de480b44183aec2823505",
            "d84f6ea0-3e5b-5a2a-b1c6-af632187e661",
            "c615e0c0e34e8a230aacd3d6298fa7d4103a517a4860fb025fc70187bfde4c3b",
        ),
        FinalOnlyHistoricalInput(
            "c3",
            "HISTORICAL_ATTEMPT",
            "INCOMPLETE",
            "fe3a1d5650daf27fd72b31030d5f7e26cf75b7ffd6cb1f7220c5c86f4c869b61",
            "dev_recall_m2_compressed_pfe3a1d5650da_c3_20260828_",
            "7fa158a0-e868-5c08-9825-c3abb69165ec",
            "1234259c322d970587c93a8eaae096c082b19f54870ea3953a32d84423b42f09",
            None,
            None,
        ),
        FinalOnlyHistoricalInput(
            "c3",
            "HISTORICAL_ATTEMPT",
            "INCOMPLETE",
            "c3e454c1b593c98a558c3f03c67b7de6f5d0e2d1e3c98efdfb91d4c5530a9791",
            "dev_recall_m2_compressed_pc3e454c1b593_c3_20260828_",
            "eccd1eee-126b-5cb6-8e48-96adbd10a137",
            "a17161bf65bbb95b6b4db1ef2521ee5ba7897a697fd6cbf0817a509a2cfc0471",
            None,
            None,
        ),
    )


def test_final_only_candidate_uses_checkpoint_history_and_owner_window() -> None:
    source = (ROOT / PLAN_PATH).read_bytes()

    result = render_final_only_candidate(
        source,
        # Owner-designated PREVIOUSLY_RECORDED values; no new live claim.
        historical_evidence=_director_checkpoint_history(),
        c6_window_start=C6_START,
        c6_window_end=C6_END,
    )
    plan = parse_compressed_plan(
        json.loads(result.plan_bytes),
        sha256=result.plan_sha256,
    )

    assert (ROOT / PLAN_PATH).read_bytes() == source
    assert plan.schema_version == "2.8.0"
    assert plan.by_id("c6").schedule_epoch == C6_START
    assert plan.by_id("c6").window_end.isoformat().replace("+00:00", "Z") == C6_END
    assert plan.by_id("c6").predecessor is None
    assert [item.activation for item in plan.cycles] == [
        "IMMUTABLE_EXECUTED",
        "IMMUTABLE_EXECUTED",
        "HISTORICAL_ATTEMPTS_PRESERVED",
        "RETIRED_TIMEBOX",
        "RETIRED_TIMEBOX",
        "ACTIVE",
    ]
    assert plan.supersession is not None
    assert [item.manifest_content_hash for item in plan.supersession.historical_evidence] == [
        item.manifest_content_hash for item in _director_checkpoint_history()
    ]


def test_final_only_candidate_rejects_missing_c3_history() -> None:
    with pytest.raises(RuntimeError, match="final_only_evidence_topology_invalid"):
        render_final_only_candidate(
            (ROOT / PLAN_PATH).read_bytes(),
            historical_evidence=_director_checkpoint_history()[:2],
            c6_window_start=C6_START,
            c6_window_end=C6_END,
        )


def test_final_only_candidate_rejects_legacy_full_eight_hour_window() -> None:
    with pytest.raises(RuntimeError, match="final_only_c6_window_duration_invalid"):
        render_final_only_candidate(
            (ROOT / PLAN_PATH).read_bytes(),
            historical_evidence=_director_checkpoint_history(),
            c6_window_start=C6_START,
            c6_window_end="2026-08-29T23:59:59Z",
        )


def test_final_only_preparation_rejects_unaccepted_source_bundle() -> None:
    plan = render_final_only_candidate(
        (ROOT / PLAN_PATH).read_bytes(),
        historical_evidence=_director_checkpoint_history(),
        c6_window_start=C6_START,
        c6_window_end=C6_END,
    )

    with pytest.raises(RuntimeError, match="final_only_source_bundle_sha_invalid"):
        render_final_only_preparation_candidate(
            b"{}",
            plan_candidate=plan,
            prepared_at="2026-08-29T12:00:00Z",
        )


def test_final_only_runtime_commit_is_not_input_preparation_commit() -> None:
    bundle = SimpleNamespace(schema_version="2.3.0", source_commit=None)

    _require_compressed_source_binding(bundle, "f" * 40)


@pytest.mark.parametrize("schema_version", ("2.0.0", "2.1.0", "2.2.0"))
def test_legacy_runtime_commit_equality_guard_remains_fail_closed(
    schema_version: str,
) -> None:
    bundle = SimpleNamespace(schema_version=schema_version, source_commit="a" * 40)

    with pytest.raises(RuntimeError, match="source_commit_mismatch"):
        _require_compressed_source_binding(bundle, "b" * 40)


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("state", "PAUSED"),
        ("tenant_id", "different-synthetic-tenant"),
        ("monitoring_policy", {"policy_version": "1.0.2"}),
    ),
)
def test_final_only_bundle_rejects_watch_case_invariant_drift_before_writes(
    tmp_path: Path,
    field: str,
    replacement: object,
) -> None:
    plan_path, bundle_path = _candidate_paths()
    plan_bytes = plan_path.read_bytes()
    plan = parse_compressed_plan(
        json.loads(plan_bytes),
        sha256=hashlib.sha256(plan_bytes).hexdigest(),
    )
    candidate = json.loads(bundle_path.read_bytes())
    watch_case = candidate["cases"][0]["watch_case"]
    watch_case[field] = deepcopy(replacement)
    watch_case["content_hash"] = content_hash(watch_case)
    rendered = (
        json.dumps(candidate, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    history_target = tmp_path / DAY1_EVIDENCE_PATH
    history_target.parent.mkdir(parents=True)
    history_target.write_bytes((ROOT / DAY1_EVIDENCE_PATH).read_bytes())
    mutated = tmp_path / "preparation-bundle-v2.json"
    mutated.write_bytes(rendered)

    with pytest.raises(
        RuntimeError, match="compressed_final_only_source_material_mismatch"
    ):
        load_compressed_bundle(
            tmp_path,
            expected_sha256=hashlib.sha256(rendered).hexdigest(),
            plan=plan,
            path=Path("preparation-bundle-v2.json"),
        )


def test_final_only_entrypoint_preview_uses_logical_due_date_for_c6(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_path, bundle_path = _candidate_paths()
    cohort_root = tmp_path / "artifacts/evidence/cohort-compression"
    cohort_root.mkdir(parents=True)
    target_plan = cohort_root / "COMPRESSED_PREDICTION_PLAN_V2.json"
    target_bundle = cohort_root / "preparation-bundle-v2.json"
    target_plan.write_bytes(plan_path.read_bytes())
    target_bundle.write_bytes(bundle_path.read_bytes())
    history_target = tmp_path / DAY1_EVIDENCE_PATH
    history_target.parent.mkdir(parents=True)
    history_target.write_bytes((ROOT / DAY1_EVIDENCE_PATH).read_bytes())
    plan_sha = hashlib.sha256(target_plan.read_bytes()).hexdigest()
    bundle_sha = hashlib.sha256(target_bundle.read_bytes()).hexdigest()
    plan = parse_compressed_plan(
        json.loads(target_plan.read_bytes()), sha256=plan_sha
    )
    assert plan.by_id("c6").schedule_epoch == "2026-08-29T16:00:00Z"
    assert plan.by_id("c6").cohort_due_date.isoformat() == "2026-08-31"
    monkeypatch.setattr(
        compressed_plan_module, "EXPECTED_PLAN_SHA256", plan_sha
    )

    result = execute(
        ["--preview-date", "2026-08-31"],
        environment={
            "RECALL_SCHEDULER_MODE": "COMPRESSED_V3",
            "RECALL_COMPRESSED_PREPARATION_SHA256": bundle_sha,
            "RECALL_SOURCE_COMMIT": "f" * 40,
            "RECALL_IMAGE_DIGEST": "sha256:" + "0" * 64,
            "RECALL_PROVIDER_RPM": "8",
        },
        repo_root=tmp_path,
    )

    assert result["cycle_id"] == "c6"
    assert result["cohort_due_date"] == "2026-08-31"
    assert result["runs_predicted"] == 456
    assert len(result["selected_case_ids"]) == 456
    assert result["writes"] == 0
