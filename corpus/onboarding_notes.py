"""Per-case varied synthetic notes for the full 462-case portfolio.

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

Case identity and VCV/variant bindings come from an AUTHORITATIVE bindings
file dumped by running core's own portfolio_case_vcv_bindings and
replay_variant_bindings (the same functions the consuming loader uses to
re-verify), so this module never re-derives what the contract owns. Anchored
rows carry inherit_case_binding=true plus the RESOLVED variant, exactly as
LockedJsonLabNoteSource (schema 1.1.0) demands; language derives from the
case id alone, so row content is independent of pool ordering.

Output: corpus/onboarding/notes.json (schema 1.1.0) plus a manifest with
sha256. No real person data anywhere; every identifier is fabricated by
seeded generation.
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

NOTES_VERSION = "portfolio-notes-v2"
SEED = 20260827
ONBOARDING_CASE_COUNT = 450
OUT_DIR = Path(__file__).resolve().parent / "onboarding"

BINDINGS_PATH_ENV = "RECALL_NOTES_BINDINGS"


def load_bindings(path: Path) -> dict:
    """The authoritative case->vcv map and resolved replay variants.

    Produced by running core's portfolio_case_vcv_bindings and
    replay_variant_bindings; the loader on the consuming side re-derives both
    and refuses any mismatch, so a stale bindings file cannot pass silently.
    """

    value = json.loads(path.read_text(encoding="utf-8"))
    if set(value) != {"case_bindings", "replay_variants"}:
        raise RuntimeError("bindings_shape_invalid")
    if len(value["case_bindings"]) != 462:
        raise RuntimeError(f"bindings_count_invalid: {len(value['case_bindings'])}")
    return value


def _language_for(case_id: str) -> str:
    # Derived from the id alone: row content never depends on pool ordering.
    return "tr" if int(hashlib.sha256(case_id.encode()).hexdigest(), 16) % 2 == 0 else "en"


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


def build_notes(bindings: dict) -> dict:
    gz = json.loads(GAZETTEER_PATH.read_text(encoding="utf-8"))
    entries: list[dict] = []
    case_bindings: dict = bindings["case_bindings"]
    replay_variants: dict = bindings["replay_variants"]

    for case_id in sorted(case_bindings):
        vcv = case_bindings[case_id]
        rng = random.Random(f"{SEED}:{case_id}")
        language = _language_for(case_id)
        template = rng.randrange(3)
        builder = (
            _short_tr(rng, gz, template) if language == "tr" else _short_en(rng, gz, template)
        )
        if vcv is not None:
            variant = replay_variants[vcv]
            structured = {
                "inherit_case_binding": True,
                "vcv": vcv,
                "gene": variant["gene"],
                "hgvs_c": variant["hgvs_c"],
                "hgvs_p": variant["hgvs_p"],
                "assembly": variant["assembly"],
            }
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
                "case_id": case_id,
                "origin": "anchored" if vcv else "portfolio",
                "language": language,
                "template": f"short-{language}-{template}",
                "note_text": builder.text(),
                "spans": [span.to_wire() for span in builder.spans],
                "structured": structured,
            }
        )

    return {
        "schema_version": "1.1.0",
        "notes_version": NOTES_VERSION,
        "seed": SEED,
        "data_mode": "SYNTHETIC",
        "tenant_id": "synthetic-contest-lab",
        "region": "us-central1",
        "real_data_statement": (
            "Every identifier surface is fabricated by seeded generation. No real "
            "person, address, institution record, or contact detail appears."
        ),
        "notes": entries,
    }


def self_check(bundle: dict, bindings: dict) -> list[str]:
    problems: list[str] = []
    notes = bundle["notes"]
    case_bindings = bindings["case_bindings"]
    if len(notes) != 462:
        problems.append(f"expected 462 notes, built {len(notes)}")
    if len({n["case_id"] for n in notes}) != len(notes):
        problems.append("case ids are not unique")
    if {n["case_id"] for n in notes} != set(case_bindings):
        problems.append("case set differs from the authoritative bindings")
    if len({n["note_text"] for n in notes}) != len(notes):
        problems.append("note texts are not unique")
    for n in notes:
        count = len(n["spans"])
        if not 3 <= count <= 5:
            problems.append(f"{n['case_id']}: {count} spans, outside 3-5")
        for span in n["spans"]:
            if n["note_text"][span["start"]:span["end"]] == "":
                problems.append(f"{n['case_id']}: empty span surface")
        s = n["structured"]
        vcv = case_bindings[n["case_id"]]
        if (vcv is not None) != bool(s.get("inherit_case_binding")):
            problems.append(f"{n['case_id']}: inherit flag disagrees with binding")
        if vcv is not None and s.get("vcv") != vcv:
            problems.append(f"{n['case_id']}: vcv mismatch")
        for field in ("gene", "hgvs_c", "assembly"):
            if not s.get(field):
                problems.append(f"{n['case_id']}: unresolved variant field {field}")
    anchored = [n for n in notes if n["structured"].get("inherit_case_binding")]
    if len(anchored) != sum(1 for v in case_bindings.values() if v):
        problems.append(f"anchored count {len(anchored)} != bindings")
    languages = {lang: sum(1 for n in notes if n["language"] == lang) for lang in ("tr", "en")}
    if min(languages.values()) < 180:
        problems.append(f"language balance off: {languages}")
    return problems


def main() -> int:
    import os

    bindings_path = os.environ.get(BINDINGS_PATH_ENV)
    if not bindings_path:
        print(f"FAIL: set {BINDINGS_PATH_ENV} to the bindings.json dumped from core")
        return 1
    bindings = load_bindings(Path(bindings_path))
    bundle = build_notes(bindings)
    problems = self_check(bundle, bindings)
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
        "schema_version": "1.1.0",
        "seed": SEED,
        "note_count": len(bundle["notes"]),
        "generator_module": "corpus/onboarding_notes.py",
        "bindings_provenance": "portfolio_case_vcv_bindings + replay_variant_bindings, run from core",
        "reuses_frozen_generator": "building blocks imported read-only; corpus/generator.py unmodified",
    }
    (OUT_DIR / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    counts: dict[int, int] = {}
    for n in bundle["notes"]:
        counts[len(n["spans"])] = counts.get(len(n["spans"]), 0) + 1
    print(f"notes: {len(bundle['notes'])}  sha256: {digest}")
    print(f"span distribution: {dict(sorted(counts.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
