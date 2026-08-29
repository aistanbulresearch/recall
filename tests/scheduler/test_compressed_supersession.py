from __future__ import annotations

from types import SimpleNamespace

import pytest

import recall.scheduler.compressed_supersession as supersession_module
from recall.scheduler.compressed_plan import parse_compressed_plan
from recall.scheduler.compressed_supersession import (
    verify_final_only_supersession,
)
from tests.scheduler.test_compressed_plan import _wire_for_final_only


class ReadOnlyLedger:
    def __init__(self, artifacts: dict[str, dict[str, object]]) -> None:
        self.artifacts = artifacts
        self.read_ids: list[str] = []

    def get_artifact(self, artifact_id: str):
        self.read_ids.append(artifact_id)
        return self.artifacts.get(artifact_id)


def _plan_and_ledgers(monkeypatch: pytest.MonkeyPatch):
    plan = parse_compressed_plan(_wire_for_final_only(), sha256="e" * 64)
    ledgers: dict[str, ReadOnlyLedger] = {}
    parsed_by_id = {}
    for binding in plan.supersession.historical_evidence:
        manifest = {
            "artifact_id": binding.manifest_artifact_id,
            "content_hash": binding.manifest_content_hash,
        }
        artifacts = {binding.manifest_artifact_id: manifest}
        parsed_by_id[binding.manifest_artifact_id] = SimpleNamespace(
            schema_name="CohortDayManifest",
            schema_version="3.3.0",
            artifact_id=binding.manifest_artifact_id,
            content_hash=binding.manifest_content_hash,
            status=SimpleNamespace(
                value=(
                    "VALID"
                    if binding.execution_status == "COMPLETE"
                    else "INCOMPLETE"
                )
            ),
            payload=SimpleNamespace(
                cycle_id=binding.cycle_id,
                plan_sha256=binding.plan_sha256,
                execution_history=(
                    {
                        "cycle_id": binding.cycle_id,
                        "source_schema_version": "CohortDayManifest/3.3.0",
                        "execution_status": binding.execution_status,
                    },
                ),
                agent_execution_summary={
                    "halted_runs": (
                        1 if binding.execution_status == "HALTED" else 0
                    )
                },
            ),
        )
        if binding.mode_receipt_artifact_id is not None:
            mode = {
                "artifact_id": binding.mode_receipt_artifact_id,
                "content_hash": binding.mode_receipt_content_hash,
            }
            artifacts[binding.mode_receipt_artifact_id] = mode
            parsed_by_id[binding.mode_receipt_artifact_id] = SimpleNamespace(
                schema_name="DataModeReceipt",
                artifact_id=binding.mode_receipt_artifact_id,
                content_hash=binding.mode_receipt_content_hash,
                status=SimpleNamespace(value="VALID"),
                payload=SimpleNamespace(
                    subject_artifact_ids=(binding.manifest_artifact_id,),
                    propagation_status=SimpleNamespace(value="PASS"),
                ),
            )
        ledger = ledgers.setdefault(
            binding.collection_prefix, ReadOnlyLedger({})
        )
        ledger.artifacts.update(artifacts)

    monkeypatch.setattr(
        supersession_module,
        "parse_artifact",
        lambda wire, **_kwargs: parsed_by_id[str(wire["artifact_id"])],
    )
    return plan, ledgers, parsed_by_id


def test_final_only_supersession_reads_and_verifies_every_declared_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, ledgers, _parsed = _plan_and_ledgers(monkeypatch)

    verified = verify_final_only_supersession(
        plan,
        ledger_for_prefix=lambda prefix: ledgers[prefix],
    )

    expected_ids = tuple(
        artifact_id
        for item in plan.supersession.historical_evidence
        for artifact_id in (
            item.manifest_artifact_id,
            item.mode_receipt_artifact_id,
        )
        if artifact_id is not None
    )
    assert verified.plan_sha256 == plan.sha256
    assert verified.verified_artifact_ids == expected_ids
    assert all(ledger.read_ids for ledger in ledgers.values())


def test_final_only_supersession_hash_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, ledgers, _parsed = _plan_and_ledgers(monkeypatch)
    binding = plan.supersession.historical_evidence[-1]
    ledger = ledgers[binding.collection_prefix]
    ledger.artifacts[binding.manifest_artifact_id] = {
        "artifact_id": binding.manifest_artifact_id,
        "content_hash": "0" * 64,
    }

    with pytest.raises(RuntimeError, match="final_only_history_hash_mismatch"):
        verify_final_only_supersession(
            plan,
            ledger_for_prefix=lambda prefix: ledgers[prefix],
        )


def test_final_only_supersession_rejects_incomplete_claim_with_valid_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, ledgers, parsed_by_id = _plan_and_ledgers(monkeypatch)
    binding = plan.supersession.historical_evidence[-1]
    wire = ledgers[binding.collection_prefix].artifacts[
        binding.manifest_artifact_id
    ]
    parsed = parsed_by_id[binding.manifest_artifact_id]
    parsed_by_id[binding.manifest_artifact_id] = SimpleNamespace(
        schema_name=parsed.schema_name,
        schema_version=parsed.schema_version,
        artifact_id=parsed.artifact_id,
        content_hash=parsed.content_hash,
        status=SimpleNamespace(value="VALID"),
        payload=SimpleNamespace(
            cycle_id=binding.cycle_id,
            plan_sha256=binding.plan_sha256,
            execution_history=(
                {
                    "cycle_id": binding.cycle_id,
                    "source_schema_version": "CohortDayManifest/3.3.0",
                    "execution_status": "COMPLETE",
                },
            ),
        ),
    )
    monkeypatch.setattr(
        supersession_module,
        "parse_artifact",
        lambda artifact, **_kwargs: parsed_by_id[str(artifact["artifact_id"])],
    )

    with pytest.raises(RuntimeError, match="final_only_history_status_mismatch"):
        verify_final_only_supersession(
            plan,
            ledger_for_prefix=lambda prefix: ledgers[prefix],
        )


def test_final_only_supersession_rejects_mode_receipt_identity_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, ledgers, parsed_by_id = _plan_and_ledgers(monkeypatch)
    binding = plan.supersession.historical_evidence[0]
    assert binding.mode_receipt_artifact_id is not None
    mode = parsed_by_id[binding.mode_receipt_artifact_id]
    parsed_by_id[binding.mode_receipt_artifact_id] = SimpleNamespace(
        schema_name=mode.schema_name,
        artifact_id="00000000-0000-0000-0000-000000000000",
        content_hash=mode.content_hash,
        status=mode.status,
        payload=mode.payload,
    )

    with pytest.raises(
        RuntimeError, match="final_only_history_mode_binding_invalid"
    ):
        verify_final_only_supersession(
            plan,
            ledger_for_prefix=lambda prefix: ledgers[prefix],
        )


def test_final_only_supersession_rejects_incomplete_mode_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, ledgers, parsed_by_id = _plan_and_ledgers(monkeypatch)
    binding = plan.supersession.historical_evidence[0]
    assert binding.mode_receipt_artifact_id is not None
    mode = parsed_by_id[binding.mode_receipt_artifact_id]
    parsed_by_id[binding.mode_receipt_artifact_id] = SimpleNamespace(
        schema_name=mode.schema_name,
        artifact_id=mode.artifact_id,
        content_hash=mode.content_hash,
        status=SimpleNamespace(value="INCOMPLETE"),
        payload=mode.payload,
    )

    with pytest.raises(
        RuntimeError, match="final_only_history_mode_binding_invalid"
    ):
        verify_final_only_supersession(
            plan,
            ledger_for_prefix=lambda prefix: ledgers[prefix],
        )


def test_final_only_supersession_rejects_failed_mode_propagation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, ledgers, parsed_by_id = _plan_and_ledgers(monkeypatch)
    binding = plan.supersession.historical_evidence[0]
    assert binding.mode_receipt_artifact_id is not None
    mode = parsed_by_id[binding.mode_receipt_artifact_id]
    parsed_by_id[binding.mode_receipt_artifact_id] = SimpleNamespace(
        schema_name=mode.schema_name,
        artifact_id=mode.artifact_id,
        content_hash=mode.content_hash,
        status=mode.status,
        payload=SimpleNamespace(
            subject_artifact_ids=mode.payload.subject_artifact_ids,
            propagation_status=SimpleNamespace(value="FAIL"),
        ),
    )

    with pytest.raises(
        RuntimeError, match="final_only_history_mode_binding_invalid"
    ):
        verify_final_only_supersession(
            plan,
            ledger_for_prefix=lambda prefix: ledgers[prefix],
        )


def test_final_only_supersession_rejects_manifest_internal_cycle_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, ledgers, parsed_by_id = _plan_and_ledgers(monkeypatch)
    binding = plan.supersession.historical_evidence[-1]
    parsed = parsed_by_id[binding.manifest_artifact_id]
    parsed_by_id[binding.manifest_artifact_id] = SimpleNamespace(
        schema_name=parsed.schema_name,
        schema_version=parsed.schema_version,
        artifact_id=parsed.artifact_id,
        content_hash=parsed.content_hash,
        status=parsed.status,
        payload=SimpleNamespace(
            cycle_id=parsed.payload.cycle_id,
            plan_sha256=parsed.payload.plan_sha256,
            execution_history=(
                {
                    "cycle_id": "c4",
                    "source_schema_version": "CohortDayManifest/3.3.0",
                    "execution_status": "INCOMPLETE",
                },
            ),
        ),
    )

    with pytest.raises(
        RuntimeError, match="final_only_history_manifest_binding_invalid"
    ):
        verify_final_only_supersession(
            plan,
            ledger_for_prefix=lambda prefix: ledgers[prefix],
        )
