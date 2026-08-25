from __future__ import annotations

import hashlib

import pytest

from recall.ledger import FirestoreLedger
from recall.ledger import firestore as firestore_module


class _Credentials:
    quota_project_id = None


def _default_project(monkeypatch, project: str = "recall-test-project") -> None:
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    monkeypatch.delenv("RECALL_GCP_PROJECT", raising=False)
    monkeypatch.setattr(
        firestore_module.google.auth,
        "default",
        lambda: (_Credentials(), project),
    )


def test_live_firestore_rejects_emulator_environment(monkeypatch) -> None:
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")

    with pytest.raises(ValueError, match="live_firestore_emulator_forbidden"):
        FirestoreLedger.from_default_credentials(require_live=True)


def test_live_firestore_rejects_wrong_project_hash(monkeypatch) -> None:
    _default_project(monkeypatch)

    with pytest.raises(ValueError, match="firestore_project_mismatch"):
        FirestoreLedger.from_default_credentials(
            collection_prefix="dev_recall_guard_test_",
            expected_project_sha256="0" * 64,
            require_live=True,
        )


def test_live_firestore_rejects_nondefault_database(monkeypatch) -> None:
    project = "recall-test-project"
    _default_project(monkeypatch, project)

    with pytest.raises(ValueError, match="firestore_database_mismatch"):
        FirestoreLedger.from_default_credentials(
            collection_prefix="dev_recall_guard_test_",
            expected_project_sha256=hashlib.sha256(
                project.encode("utf-8")
            ).hexdigest(),
            database="named-database",
            require_live=True,
        )
