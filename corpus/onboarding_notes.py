"""Per-case varied synthetic notes for the compressed-cohort onboarding pool.

Closes the stub-note weakness: the preparation path previously fed the privacy
gate ONE constant six-word note for every case, so no per-case claim about the
local pipeline could be made. This module gives each of the 456 pool cases its
own short synthetic note (3-5 labelled identifier spans, TR/EN balanced),
deterministic per case id.

`corpus/generator.py` is hash-bound to frozen P1 evidence and is NOT modified;
this module imports its building blocks (NoteBuilder, gazetteers, fabricated
identifier helpers) read-only. Note class is deliberately SHORT, distinct from
the P1 corpus class (10-15 spans): these notes exist to exercise the real
pipeline per case, not to re-measure recall.

Case identity mirrors src/recall/scheduler/compressed_cohort.py on core:
450 onboarding ids are uuid5(NAMESPACE_URL, "recall:compressed-onboarding:v1:
NNNN") for NNNN in 0001..0450; the 6 late-due managed cases are carried with
their committed ids. VCV-anchored cases inherit their variant from the case
binding at receipt time; this file never invents a variant for an anchored
case (structured.inherit_case_binding=true instead).

Output: corpus/onboarding/notes.json plus a manifest with sha256, shaped for
the receipt-producing run feeding LockedJsonPrivacyReceiptSource. No real
person data anywhere; every identifier is fabricated by seeded generation.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generator import (  # noqa: E402
    GAZETTEER_PATH,
    GENES,
    HGVS_C,
    HGVS_P,
    NoteBuilder,
    birth_year,
    numeric_date,
    tckn,
)

NOTES_VERSION = "onboarding-notes-v1"
SEED = 20260827
ONBOARDING_CASE_COUNT = 450
OUT_DIR = Path(__file__).resolve().parent / "onboarding"

# The six late-due managed cases, ids as committed in core's cohort.py at
# 740fc36 lineage. Anchored cases carry their VCV; their variant is inherited
# from the case binding by the receipt run, never invented here.
LATE_MANAGED_CASES: tuple[dict[str, Any], ...] = (
    {"case_id": "ddedd554-a08d-5230-b72e-af38f7ad365c", "vcv": "VCV002895953.5"},
    {"case_id": "504db62b-ae4e-5f79-a31e-31c0387ac4a4", "vcv": "VCV000495460.24"},
    {"case_id": "9fc76e08-da69-5871-8d1a-a62dcb2cb85c", "vcv": "VCV000051100.33"},
    {"case_id": "da6252c8-585e-5803-8a2b-ec2e5ec16e41", "vcv": None},
    {"case_id": "a816bc0f-d08c-5dc4-aff9-e5143300ead9", "vcv": None},
    {"case_id": "98f35092-2042-5979-b627-d5bb16f3fd38", "vcv": None},
)


def onboarding_case_ids() -> list[str]:
    return [
        str(uuid5(NAMESPACE_URL, f"recall:compressed-onboarding:v1:{index:04d}"))
        for index in range(1, ONBOARDING_CASE_COUNT + 1)
    ]


def _short_tr(rng: random.Random, gz: dict[str, Any], template: int) -> NoteBuilder:
    tr = gz["tr"]
    first, last = rng.choice(tr["first_names"]), rng.choice(tr["surnames"])
    doc_first, doc_last = rng.choice(tr["first_names"]), rng.choice(tr["surnames"])
    b = NoteBuilder()
    if template == 0:  # 3 spans
        b.lit("Hasta ").ident(f"{first} {last}", "PERSON_NAME")
        b.lit(" icin panel sonucu degerlendirildi. Dosya No: ")
        b.ident(f"MRN-{rng.randint(100000, 999999)}", "MEDICAL_RECORD_NUMBER")
        b.lit(". Sorumlu hekim: Dr. ").ident(f"{doc_first} {doc_last}", "CLINICIAN_NAME")
        b.lit(". Varyant klinik onemi belirsiz olarak izlemede.\n")
    elif template == 1:  # 4 spans
        age = rng.randint(24, 82)
        b.lit("Hasta: ").ident(f"{first} {last}", "PERSON_NAME")
        b.lit(", TC Kimlik No: ").ident(tckn(rng), "NATIONAL_ID")
        b.lit(" (").ident(str(age), "AGE").lit(" yasinda). Kurum: ")
        b.ident(rng.choice(tr["facilities"]), "FACILITY_NAME")
        b.lit(". Yeni kanit izlemi surecek.\n")
    else:  # 5 spans
        age = rng.randint(24, 82)
        born = birth_year(rng, age)
        b.lit("Hasta ").ident(f"{first} {last}", "PERSON_NAME")
        b.lit(", dogum tarihi ").ident(numeric_date(rng, born, born), "DATE_OF_BIRTH")
        b.lit(", Protokol No: ")
        b.ident(f"{rng.randint(2019, 2024)}-{rng.randint(10000, 99999)}", "PROTOCOL_NUMBER")
        b.lit(". Kurum: ").ident(rng.choice(tr["facilities"]), "FACILITY_NAME")
        b.lit(", hekim: Dr. ").ident(f"{doc_first} {doc_last}", "CLINICIAN_NAME")
        b.lit(". Takip planlandi.\n")
    return b


def _short_en(rng: random.Random, gz: dict[str, Any], template: int) -> NoteBuilder:
    en = gz["en"]
    first, last = rng.choice(en["first_names"]), rng.choice(en["surnames"])
    doc_first, doc_last = rng.choice(en["first_names"]), rng.choice(en["surnames"])
    b = NoteBuilder()
    if template == 0:  # 3 spans
        b.lit("Panel result reviewed for ").ident(f"{first} {last}", "PERSON_NAME")
        b.lit(". Record: ").ident(f"MRN-{rng.randint(100000, 999999)}", "MEDICAL_RECORD_NUMBER")
        b.lit(". Attending: Dr. ").ident(f"{doc_first} {doc_last}", "CLINICIAN_NAME")
        b.lit(". Variant remains of uncertain significance; surveillance continues.\n")
    elif template == 1:  # 4 spans
        age = rng.randint(24, 82)
        b.lit("Patient ").ident(f"{first} {last}", "PERSON_NAME")
        b.lit(", aged ").ident(str(age), "AGE")
        b.lit(", email ").ident(
            f"{first.lower()}.{last.lower()}{rng.randint(2, 97)}@example-mail.test", "EMAIL"
        )
        b.lit(". Facility: ").ident(rng.choice(en["facilities"]), "FACILITY_NAME")
        b.lit(". Monitoring for new evidence.\n")
    else:  # 5 spans
        age = rng.randint(24, 82)
        born = birth_year(rng, age)
        b.lit("Patient ").ident(f"{first} {last}", "PERSON_NAME")
        b.lit(", DOB ").ident(numeric_date(rng, born, born), "DATE_OF_BIRTH")
        b.lit(", protocol ").ident(
            f"{rng.randint(2019, 2024)}-{rng.randint(10000, 99999)}", "PROTOCOL_NUMBER"
        )
        b.lit(", phone ").ident(
            f"+1-555-{rng.randint(200, 989)}-{rng.randint(1000, 9999)}", "PHONE"
        )
        b.lit(". Attending: Dr. ").ident(f"{doc_first} {doc_last}", "CLINICIAN_NAME")
        b.lit(". Follow-up scheduled.\n")
    return b


def build_notes() -> dict[str, Any]:
    gz = json.loads(GAZETTEER_PATH.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = []

    pool: list[dict[str, Any]] = [
        {"case_id": case_id, "vcv": None, "origin": "onboarding"}
        for case_id in onboarding_case_ids()
    ] + [{**case, "origin": "managed-late"} for case in LATE_MANAGED_CASES]

    for index, case in enumerate(sorted(pool, key=lambda item: item["case_id"])):
        # Seeded by the case id, so regeneration is deterministic per case and
        # independent of pool ordering.
        rng = random.Random(f"{SEED}:{case['case_id']}")
        language = "tr" if index % 2 == 0 else "en"
        template = rng.randrange(3)
        builder = (
            _short_tr(rng, gz, template) if language == "tr" else _short_en(rng, gz, template)
        )
        if case["vcv"] is not None:
            structured: dict[str, Any] = {"inherit_case_binding": True, "vcv": case["vcv"]}
        else:
            variant_index = rng.randrange(len(HGVS_C))
            structured = {
                "inherit_case_binding": False,
                "gene": rng.choice(GENES),
                "hgvs_c": HGVS_C[variant_index],
                "hgvs_p": HGVS_P[variant_index],
                "assembly": "GRCh38",
            }
        entries.append(
            {
                "case_id": case["case_id"],
                "origin": case["origin"],
                "language": language,
                "template": f"short-{language}-{template}",
                "note_text": builder.text(),
                "spans": [span.to_wire() for span in builder.spans],
                "structured": structured,
            }
        )

    return {
        "schema_version": "1.0.0",
        "notes_version": NOTES_VERSION,
        "seed": SEED,
        "data_mode": "SYNTHETIC",
        "real_data_statement": (
            "Every identifier surface is fabricated by seeded generation. No real "
            "person, address, institution record, or contact detail appears."
        ),
        "notes": entries,
    }


def self_check(bundle: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    notes = bundle["notes"]
    if len(notes) != ONBOARDING_CASE_COUNT + len(LATE_MANAGED_CASES):
        problems.append(f"expected 456 notes, built {len(notes)}")
    if len({n["case_id"] for n in notes}) != len(notes):
        problems.append("case ids are not unique")
    texts = {n["note_text"] for n in notes}
    if len(texts) != len(notes):
        problems.append(f"note texts are not unique: {len(texts)} distinct of {len(notes)}")
    for n in notes:
        count = len(n["spans"])
        if not 3 <= count <= 5:
            problems.append(f"{n['case_id']}: {count} spans, outside 3-5")
        for span in n["spans"]:
            if n["note_text"][span["start"]:span["end"]] == "":
                problems.append(f"{n['case_id']}: empty span surface")
    languages = {lang: sum(1 for n in notes if n["language"] == lang) for lang in ("tr", "en")}
    if abs(languages["tr"] - languages["en"]) > 1:
        problems.append(f"language balance off: {languages}")
    anchored = [n for n in notes if n["structured"].get("inherit_case_binding")]
    if len(anchored) != 3:
        problems.append(f"expected 3 anchored inherit rows, found {len(anchored)}")
    return problems


def main() -> int:
    bundle = build_notes()
    problems = self_check(bundle)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "notes.json"
    payload = json.dumps(bundle, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    out.write_text(payload, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    manifest = {
        "notes_file": "corpus/onboarding/notes.json",
        "notes_sha256": digest,
        "notes_version": NOTES_VERSION,
        "seed": SEED,
        "note_count": len(bundle["notes"]),
        "generator_module": "corpus/onboarding_notes.py",
        "reuses_frozen_generator": "building blocks imported read-only; corpus/generator.py unmodified",
    }
    (OUT_DIR / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    counts = {}
    for n in bundle["notes"]:
        counts[len(n["spans"])] = counts.get(len(n["spans"]), 0) + 1
    print(f"notes: {len(bundle['notes'])}  sha256: {digest}")
    print(f"span distribution: {dict(sorted(counts.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
