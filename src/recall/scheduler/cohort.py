from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from recall.contracts import DataMode
from recall.contracts.enums import DataComposition

from .config import COHORT as FROZEN_DAY1_COHORT


COHORT_ID = str(uuid5(NAMESPACE_URL, "recall:m2:staged-cohort:v1"))
SOURCE_MANIFEST = Path("docs/evaluation/HISTORICAL_REPLAY_SOURCE_MANIFEST.json")
RIGHTS_NOTE = (
    "NCBI ClinVar captures are retained with attribution under the reviewed "
    "RCL-205 public-record rights profile; re-review before public release."
)


@dataclass(frozen=True, slots=True)
class ReplayAnchor:
    vcv: str
    capture_path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ManagedCohortCase:
    case_id: str
    next_scan_at: str
    cursor: str
    data_mode: DataMode
    declared_composition: DataComposition
    vcv: str | None = None

    @property
    def due_date(self) -> date:
        return date.fromisoformat(self.next_scan_at[:10])


REPLAY_ANCHORS = (
    ReplayAnchor(
        "VCV002895953.1",
        "artifacts/evidence/rcl-205/clinvar/VCV002895953.1.printable.html",
        "f26600a16912d4473a4dd9af2af2628fa8feb5be3d037e1da02b482824a034aa",
    ),
    ReplayAnchor(
        "VCV002895953.4",
        "artifacts/evidence/rcl-205/clinvar/VCV002895953.4.printable.html",
        "a7b670532215705d2106ce9ffdf252341468d3f0fe34dbe9134ddd3e8582ddf6",
    ),
    ReplayAnchor(
        "VCV002895953.5",
        "artifacts/evidence/rcl-205/clinvar/VCV002895953.5.printable.html",
        "d8d4eb4b9ab0a6bd3be9d740a0fb4aebb5911a8384113e6a037728f0688b7fbc",
    ),
    ReplayAnchor(
        "VCV000495460.24",
        "artifacts/evidence/rcl-205/clinvar/VCV000495460.24.printable.html",
        "7c5122b67ff0808d9d0aa300a089b12160d100a8a3f59739c74bae837974889c",
    ),
    ReplayAnchor(
        "VCV000051100.33",
        "artifacts/evidence/rcl-205/clinvar/VCV000051100.33.printable.html",
        "1d413a022d63aa68bf87a314f4beb6ac2fbed73a86d888784c18e3af55f9033d",
    ),
)


_ORIGINAL_THREE = tuple(
    ManagedCohortCase(
        case_id=item.case_id,
        next_scan_at=item.next_scan_at,
        cursor=item.cursor,
        data_mode=DataMode.SYNTHETIC,
        declared_composition=DataComposition.SYNTHETIC_ONLY,
    )
    for item in FROZEN_DAY1_COHORT
)


MANAGED_COHORT = _ORIGINAL_THREE + (
    ManagedCohortCase(
        "c4e45bde-971b-52ee-9ba3-f182432146fa",
        "2026-08-26T15:00:00Z",
        "cohort-day2-replay-v1",
        DataMode.SYNTHETIC,
        DataComposition.SYNTHETIC_WITH_CAPTURED_REPLAY,
        "VCV002895953.1",
    ),
    ManagedCohortCase(
        "420c82a9-c37d-5d40-826a-bda26184ae34",
        "2026-08-26T15:00:00Z",
        "cohort-day2-synthetic-002",
        DataMode.SYNTHETIC,
        DataComposition.SYNTHETIC_ONLY,
    ),
    ManagedCohortCase(
        "f453187b-b739-598d-a266-604dba66b6e5",
        "2026-08-27T15:00:00Z",
        "cohort-day3-replay-v4",
        DataMode.SYNTHETIC,
        DataComposition.SYNTHETIC_WITH_CAPTURED_REPLAY,
        "VCV002895953.4",
    ),
    ManagedCohortCase(
        "ddedd554-a08d-5230-b72e-af38f7ad365c",
        "2026-08-28T15:00:00Z",
        "cohort-day4-replay-v5",
        DataMode.SYNTHETIC,
        DataComposition.SYNTHETIC_WITH_CAPTURED_REPLAY,
        "VCV002895953.5",
    ),
    ManagedCohortCase(
        "504db62b-ae4e-5f79-a31e-31c0387ac4a4",
        "2026-08-28T15:00:00Z",
        "cohort-day4-replay-negative-splice",
        DataMode.SYNTHETIC,
        DataComposition.SYNTHETIC_WITH_CAPTURED_REPLAY,
        "VCV000495460.24",
    ),
    ManagedCohortCase(
        "9fc76e08-da69-5871-8d1a-a62dcb2cb85c",
        "2026-08-28T15:00:00Z",
        "cohort-day4-replay-negative-missense",
        DataMode.SYNTHETIC,
        DataComposition.SYNTHETIC_WITH_CAPTURED_REPLAY,
        "VCV000051100.33",
    ),
    ManagedCohortCase(
        "da6252c8-585e-5803-8a2b-ec2e5ec16e41",
        "2026-08-28T15:00:00Z",
        "cohort-day4-synthetic-002",
        DataMode.SYNTHETIC,
        DataComposition.SYNTHETIC_ONLY,
    ),
    ManagedCohortCase(
        "a816bc0f-d08c-5dc4-aff9-e5143300ead9",
        "2026-08-29T15:00:00Z",
        "cohort-day5-synthetic-001",
        DataMode.SYNTHETIC,
        DataComposition.SYNTHETIC_ONLY,
    ),
    ManagedCohortCase(
        "98f35092-2042-5979-b627-d5bb16f3fd38",
        "2026-08-30T15:00:00Z",
        "cohort-day6-synthetic-001",
        DataMode.SYNTHETIC,
        DataComposition.SYNTHETIC_ONLY,
    ),
)


RUN_PREDICTIONS = {
    date(2026, 8, 25): 1,
    date(2026, 8, 26): 3,
    date(2026, 8, 27): 2,
    date(2026, 8, 28): 4,
    date(2026, 8, 29): 1,
    date(2026, 8, 30): 1,
}


def cases_for_date(selected_for_date: date) -> tuple[ManagedCohortCase, ...]:
    return tuple(
        item for item in MANAGED_COHORT if item.due_date == selected_for_date
    )


def verify_replay_anchors(repo_root: Path) -> None:
    manifest = json.loads((repo_root / SOURCE_MANIFEST).read_text(encoding="utf-8"))
    registered = {
        item["semantic_anchor"]: (item["capture_path"], item["sha256"])
        for item in manifest["captured_sources"]
        if item.get("semantic_anchor") in {anchor.vcv for anchor in REPLAY_ANCHORS}
    }
    expected = {
        anchor.vcv: (anchor.capture_path, anchor.sha256)
        for anchor in REPLAY_ANCHORS
    }
    if registered != expected:
        raise RuntimeError("cohort_anchor_manifest_mismatch")
    for anchor in REPLAY_ANCHORS:
        path = (repo_root / anchor.capture_path).resolve()
        if not path.is_relative_to(repo_root.resolve()):
            raise RuntimeError("cohort_capture_path_escape")
        if hashlib.sha256(path.read_bytes()).hexdigest() != anchor.sha256:
            raise RuntimeError(f"cohort_capture_hash_mismatch:{anchor.vcv}")
