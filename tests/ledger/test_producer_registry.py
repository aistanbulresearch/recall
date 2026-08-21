from __future__ import annotations

import re
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

    assert len(documented) == 25
    assert set(PRODUCER_REGISTRY) == set(documented)
    assert {
        schema: PRODUCER_REGISTRY.authority_label(schema)
        for schema in PRODUCER_REGISTRY
    } == documented
    assert all(PRODUCER_REGISTRY[schema] for schema in PRODUCER_REGISTRY)
