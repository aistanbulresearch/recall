from __future__ import annotations

import re
from pathlib import Path

from recall.contracts.ui_registry import GOLDEN_PATH_UI_FIELDS


DERIVED_REGISTRY = (
    Path(__file__).parents[2] / "docs" / "demo" / "DERIVED_VALUE_REGISTRY.md"
)

EXPECTED_IDS = {
    "UI-GLOBAL-RUN-ID",
    "UI-GLOBAL-RUN-STATE",
    "UI-GLOBAL-MODE",
    "UI-AGENT-ROSTER",
    "UI-POLICY-OUTCOME",
    "UI-POLICY-REASONS",
    "UI-POLICY-MISSING",
    "UI-TASK-COUNT-RUN",
    "UI-TASK-DATA-MODE",
    "UI-TOOL-DENIAL",
    "UI-CITATION-STATUS",
    "UI-FAILURE-CODE",
}


def test_golden_path_ui_ids_match_documented_registry() -> None:
    documented = set(
        re.findall(r"^\| (UI-[A-Z0-9-]+) \|", DERIVED_REGISTRY.read_text("utf-8"), re.M)
    )

    assert set(GOLDEN_PATH_UI_FIELDS) == EXPECTED_IDS
    assert EXPECTED_IDS <= documented
    assert GOLDEN_PATH_UI_FIELDS["UI-GLOBAL-RUN-STATE"].source_path == "$.state"
    assert GOLDEN_PATH_UI_FIELDS["UI-GLOBAL-MODE"].source_path == "$.mode_set"
    assert "UI-HALTED" not in GOLDEN_PATH_UI_FIELDS
