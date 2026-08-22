"""Shared fixtures for the laboratory privacy tests.

`src` is placed on the path here rather than in a packaging file, because
`pyproject.toml` and `uv.lock` belong to lane L2 in the current split.

The corpus is generated, never skipped. `corpus/generated/` is deliberately not
committed, so a fresh checkout has no splits; a skipped privacy suite would
report green while measuring nothing. The session fixture regenerates the splits
from the committed seed and then checks them against the committed manifest
hashes, so a silently drifted generator fails loudly instead of disappearing.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from recall.privacy.egress import EGRESS_STRUCTURED_ONLY  # noqa: E402
from recall.privacy.gate import PrivacyGate  # noqa: E402
from recall.privacy.gemma import GemmaResidualDetector  # noqa: E402
from recall.privacy.minimizer import LabNote  # noqa: E402
from recall.privacy.signing import LocalSigner  # noqa: E402

CORPUS_DIRECTORY = REPO_ROOT / "corpus" / "generated"
GENERATOR_PATH = REPO_ROOT / "corpus" / "generator.py"
MANIFEST_PATH = REPO_ROOT / "corpus" / "PRIVACY_CORPUS_MANIFEST.json"
SPLIT_NAMES = ("train", "dev", "test")


def load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("recall_corpus_generator", GENERATOR_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - packaging accident
        raise RuntimeError(f"cannot load the corpus generator from {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    # Registered before execution so dataclass field resolution can find the
    # module by name while the module body is still running.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def generate_corpus() -> None:
    """Write every split from the committed seed and verify the split hashes."""

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    generator = load_generator()
    ratios = tuple(manifest["splits"][name]["record_count"] for name in SPLIT_NAMES)
    generator.write_corpus(CORPUS_DIRECTORY, manifest["seed"], manifest["record_count"], ratios)

    drifted = []
    for name in SPLIT_NAMES:
        produced = generator.sha256_hex((CORPUS_DIRECTORY / f"{name}.json").read_bytes())
        recorded = manifest["splits"][name]["sha256"]
        if produced != recorded:
            drifted.append(f"{name}: produced {produced[:16]} recorded {recorded[:16]}")
    if drifted:
        raise AssertionError(
            "regenerated corpus does not match corpus/PRIVACY_CORPUS_MANIFEST.json: " + "; ".join(drifted)
        )


@pytest.fixture(scope="session", autouse=True)
def corpus() -> None:
    if all((CORPUS_DIRECTORY / f"{name}.json").exists() for name in SPLIT_NAMES):
        return
    generate_corpus()


@pytest.fixture(scope="session")
def signer() -> LocalSigner:
    return LocalSigner(key_id="test-lab-key", key=b"test-laboratory-key-material")


@pytest.fixture
def fixed_clock():
    return lambda: datetime(2026, 8, 22, 9, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def gate_factory(signer, fixed_clock):
    def build(
        transport=None,
        model_id: str = "test-model",
        egress_profile: str = EGRESS_STRUCTURED_ONLY,
    ) -> PrivacyGate:
        gemma = GemmaResidualDetector(transport, model_id=model_id, clock=lambda: 0.0)
        counter = {"value": 0}

        def uuid_factory() -> str:
            counter["value"] += 1
            return f"00000000-0000-4000-8000-{counter['value']:012d}"

        return PrivacyGate(
            signer=signer,
            gemma=gemma,
            egress_profile=egress_profile,
            clock=fixed_clock,
            uuid_factory=uuid_factory,
        )

    return build


def load_split(split: str) -> list[dict]:
    path = CORPUS_DIRECTORY / f"{split}.json"
    if not path.exists():
        generate_corpus()
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
