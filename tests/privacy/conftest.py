"""Shared fixtures for the laboratory privacy tests.

`src` is placed on the path here rather than in a packaging file, because
`pyproject.toml` and `uv.lock` belong to lane L2 in the current split.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from recall.privacy.gate import PrivacyGate  # noqa: E402
from recall.privacy.gemma import GemmaResidualDetector  # noqa: E402
from recall.privacy.minimizer import LabNote  # noqa: E402
from recall.privacy.signing import LocalSigner  # noqa: E402

CORPUS_DIRECTORY = REPO_ROOT / "corpus" / "generated"


@pytest.fixture(scope="session")
def signer() -> LocalSigner:
    return LocalSigner(key_id="test-lab-key", key=b"test-laboratory-key-material")


@pytest.fixture
def fixed_clock():
    return lambda: datetime(2026, 8, 22, 9, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def gate_factory(signer, fixed_clock):
    def build(transport=None, model_id: str = "test-model") -> PrivacyGate:
        gemma = GemmaResidualDetector(transport, model_id=model_id, clock=lambda: 0.0)
        counter = {"value": 0}

        def uuid_factory() -> str:
            counter["value"] += 1
            return f"00000000-0000-4000-8000-{counter['value']:012d}"

        return PrivacyGate(signer=signer, gemma=gemma, clock=fixed_clock, uuid_factory=uuid_factory)

    return build


def load_split(split: str) -> list[dict]:
    path = CORPUS_DIRECTORY / f"{split}.json"
    if not path.exists():
        pytest.skip(f"corpus split {split} is not generated; run corpus/generator.py")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def dev_records() -> list[dict]:
    return load_split("dev")


def note_from_record(record: dict, case_key: str | None = None) -> LabNote:
    return LabNote.parse(
        {
            "case_key": case_key or record["record_id"],
            "note_text": record["text"],
            "tenant_id": "lab-01",
            "region": "eu-central",
            "gene": record["structured"]["gene"],
            "hgvs_c": record["structured"]["hgvs_c"],
            "hgvs_p": record["structured"]["hgvs_p"],
            "assembly": record["structured"]["assembly"],
        }
    )


def residual_transport(record: dict):
    """Stub local model that returns exactly the spans the rule set missed."""

    from recall.privacy.detectors import DeterministicDetector

    detector = DeterministicDetector()
    text = record["text"]
    found = {(span.start, span.end) for span in detector.detect(text)}
    missing = [span for span in record["spans"] if (span["start"], span["end"]) not in found]

    def transport(note_text: str, timeout_seconds: float) -> str:
        return json.dumps(
            {
                "spans": [
                    {
                        "start": span["start"],
                        "end": span["end"],
                        "identifier_class": span["identifier_class"],
                    }
                    for span in missing[:8]
                ]
            }
        )

    return transport
