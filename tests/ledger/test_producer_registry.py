from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from recall.ledger.producers import PRODUCER_REGISTRY


CONTRACT_DOC = (
    Path(__file__).parents[2] / "docs" / "contracts" / "ARTIFACT_CONTRACTS.md"
)


def test_producer_registry_matches_authoritative_producer_column() -> None:
    document = CONTRACT_DOC.read_text("utf-8")
    catalog = document.split("## Contract catalog", 1)[1].split(
        "## Normative nested value shapes", 1
    )[0]
    rows = re.findall(
        r"^\| `([^`]+)` \| .*? \| ([^|]+?) \|",
        catalog,
        re.MULTILINE,
    )
    documented = {schema: producer.strip() for schema, producer in rows}

    assert len(documented) == 26
    assert set(PRODUCER_REGISTRY) == set(documented)
    assert {
        schema: PRODUCER_REGISTRY.authority_label(schema)
        for schema in PRODUCER_REGISTRY
    } == documented
    assert all(PRODUCER_REGISTRY[schema] for schema in PRODUCER_REGISTRY)


def test_producer_registry_import_does_not_require_firestore_distribution() -> None:
    """Core contracts remain importable in an environment without cloud extras."""

    project_root = Path(__file__).parents[2]
    command = (
        "import sys; "
        f"sys.path.insert(0, {str(project_root / 'src')!r}); "
        "from recall.ledger.producers import PRODUCER_REGISTRY; "
        "assert len(PRODUCER_REGISTRY) == 26"
    )

    completed = subprocess.run(
        [sys.executable, "-S", "-c", command],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
