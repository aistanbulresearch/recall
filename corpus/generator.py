"""Deterministic bilingual synthetic clinical-note generator for privacy evaluation.

The generator produces Turkish and English institutional notes that contain
fabricated identifiers with exact character spans. No real person, address,
facility, record, or clinical case is represented, and no real data source is
read. Output is reproducible from the committed seed and template set.

Ownership: lane L3. Related tasks: RCL-404, protocol P1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

CORPUS_VERSION = "1.0.0"
DEFAULT_SEED = 20260822
DATA_MODE = "SYNTHETIC"

REPO_ROOT = Path(__file__).resolve().parents[1]
GAZETTEER_PATH = Path(__file__).resolve().parent / "data" / "gazetteers.json"

DIRECT_CLASSES = (
    "PERSON_NAME",
    "RELATIVE_NAME",
    "CLINICIAN_NAME",
    "NATIONAL_ID",
    "MEDICAL_RECORD_NUMBER",
    "PROTOCOL_NUMBER",
    "PHONE",
    "EMAIL",
    "ADDRESS",
    "FACILITY_NAME",
    "DATE_OF_BIRTH",
    "EVENT_DATE",
)
QUASI_CLASSES = ("AGE", "OCCUPATION")
IDENTIFIER_CLASSES = DIRECT_CLASSES + QUASI_CLASSES

GENES = ("BRCA1", "BRCA2", "MLH1", "MSH2", "PALB2", "ATM", "TP53", "CHEK2")
HGVS_C = ("c.5266dupC", "c.68_69delAG", "c.7397C>T", "c.1114C>A", "c.3113A>G", "c.2T>C")
HGVS_P = ("p.Gln1756fs", "p.Glu23fs", "p.Ala2466Val", "p.Pro372Thr", "p.Asn1038Ser", "p.Met1Thr")
ASSEMBLIES = ("GRCh37", "GRCh38")
REFERENCE_YEAR = 2026


@dataclass
class Span:
    start: int
    end: int
    identifier_class: str
    surface_kind: str

    def to_wire(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "identifier_class": self.identifier_class,
            "surface_kind": self.surface_kind,
        }


@dataclass
class NoteBuilder:
    """Appends literal text and labelled identifier surfaces, tracking offsets."""

    parts: list[str] = field(default_factory=list)
    spans: list[Span] = field(default_factory=list)
    length: int = 0

    def lit(self, text: str) -> "NoteBuilder":
        self.parts.append(text)
        self.length += len(text)
        return self

    def ident(self, text: str, identifier_class: str) -> "NoteBuilder":
        if identifier_class not in IDENTIFIER_CLASSES:
            raise ValueError(f"unregistered identifier class: {identifier_class}")
        start = self.length
        self.parts.append(text)
        self.length += len(text)
        kind = "quasi" if identifier_class in QUASI_CLASSES else "direct"
        self.spans.append(Span(start, self.length, identifier_class, kind))
        return self

    def text(self) -> str:
        return "".join(self.parts)


def tckn(rng: random.Random) -> str:
    """Fabricated Turkish national-identifier-shaped number with valid checksum.

    The checksum rule is public arithmetic. The digits are drawn from the seeded
    generator and are not looked up against any registry.
    """

    digits = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(8)]
    odd_sum = sum(digits[0:9:2])
    even_sum = sum(digits[1:8:2])
    tenth = (odd_sum * 7 - even_sum) % 10
    digits.append(tenth)
    digits.append(sum(digits) % 10)
    return "".join(str(d) for d in digits)


def ssn_like(rng: random.Random) -> str:
    return f"{rng.randint(100, 899)}-{rng.randint(10, 99)}-{rng.randint(1000, 9999)}"


def tr_phone(rng: random.Random) -> str:
    return f"0{rng.choice(['532', '533', '541', '505', '555'])} {rng.randint(100, 999)} {rng.randint(10, 99)} {rng.randint(10, 99)}"


def en_phone(rng: random.Random) -> str:
    return f"({rng.randint(200, 989)}) {rng.randint(200, 999)}-{rng.randint(1000, 9999)}"


TR_MONTHS = ("Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran", "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik")
EN_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


def birth_year(rng: random.Random, age: int) -> int:
    return REFERENCE_YEAR - age


def numeric_date(rng: random.Random, year_low: int, year_high: int) -> str:
    return f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(year_low, year_high)}"


def iso_date(rng: random.Random, year_low: int, year_high: int) -> str:
    return f"{rng.randint(year_low, year_high)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"


def tr_long_date(rng: random.Random, year_low: int, year_high: int) -> str:
    return f"{rng.randint(1, 28)} {rng.choice(TR_MONTHS)} {rng.randint(year_low, year_high)}"


def en_long_date(rng: random.Random, year_low: int, year_high: int) -> str:
    return f"{rng.choice(EN_MONTHS)} {rng.randint(1, 28)}, {rng.randint(year_low, year_high)}"


def short_year_date(rng: random.Random, year_low: int, year_high: int) -> str:
    """Non-canonical two-digit-year date, used only inside free prose."""

    return f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{rng.randint(year_low, year_high) % 100:02d}"


def email_for(rng: random.Random, first: str, last: str) -> str:
    domain = rng.choice(("ornekposta.example", "mailbox.example", "kurumsal.example", "inbox.example"))
    return f"{first.lower()}.{last.lower()}@{domain}"


def build_tr_note(rng: random.Random, gz: dict[str, Any], template_id: str) -> NoteBuilder:
    tr = gz["tr"]
    first, last = rng.choice(tr["first_names"]), rng.choice(tr["surnames"])
    rel_first, rel_last = rng.choice(tr["first_names"]), rng.choice(tr["surnames"])
    doc_first, doc_last = rng.choice(tr["first_names"]), rng.choice(tr["surnames"])
    gene = rng.choice(GENES)
    idx = rng.randrange(len(HGVS_C))
    b = NoteBuilder()

    if template_id == "tr-note-1":
        age = rng.randint(28, 79)
        born = birth_year(rng, age)
        b.lit("Hasta: ").ident(f"{first} {last}", "PERSON_NAME")
        b.lit(", TC Kimlik No: ").ident(tckn(rng), "NATIONAL_ID")
        b.lit(", Dogum tarihi: ").ident(numeric_date(rng, born, born), "DATE_OF_BIRTH")
        b.lit(" (").ident(str(age), "AGE").lit(" yasinda).\n")
        b.lit("Dosya No: ").ident(f"MRN-{rng.randint(100000, 999999)}", "MEDICAL_RECORD_NUMBER")
        b.lit(", Protokol No: ").ident(f"{rng.randint(2019, 2024)}-{rng.randint(10000, 99999)}", "PROTOCOL_NUMBER").lit(".\n")
        b.lit("Kurum: ").ident(rng.choice(tr["facilities"]), "FACILITY_NAME")
        b.lit(", Sorumlu hekim: Dr. ").ident(f"{doc_first} {doc_last}", "CLINICIAN_NAME").lit(".\n")
        b.lit("Kalitsal kanser paneli sonucunda ").lit(gene).lit(" geninde ").lit(HGVS_C[idx])
        b.lit(" (").lit(HGVS_P[idx]).lit(") varyanti saptandi. Referans dizi ").lit(rng.choice(ASSEMBLIES)).lit(".\n")
        b.lit("Varyant su an klinik onemi belirsiz olarak raporlandi. Aile oykusu anlamli.\n")
        b.lit("Iletisim: ").ident(tr_phone(rng), "PHONE").lit(" / ").ident(email_for(rng, first, last), "EMAIL").lit("\n")
        b.lit("Adres: ").ident(f"{rng.choice(tr['streets'])} No {rng.randint(2, 88)}, {rng.choice(tr['districts'])}", "ADDRESS").lit(".\n")
        b.lit("Ornek alim tarihi: ").ident(tr_long_date(rng, 2019, 2024), "EVENT_DATE").lit(".")
        append_tr_prose(b, rng, tr)
        return b
    elif template_id == "tr-note-2":
        b.lit("Genetik danisma notu\n")
        b.lit("Danisan ").ident(f"{first} {last}", "PERSON_NAME").lit(", ")
        b.ident(str(rng.randint(31, 74)), "AGE").lit(" yasinda, meslegi ")
        b.ident(rng.choice(tr["occupations"]), "OCCUPATION").lit(".\n")
        b.lit("Annesi ").ident(f"{rel_first} {rel_last}", "RELATIVE_NAME")
        b.lit(" ayni merkezde ").ident(tr_long_date(rng, 2015, 2021), "EVENT_DATE").lit(" tarihinde takip edilmisti.\n")
        b.lit("Basvuru kurumu ").ident(rng.choice(tr["facilities"]), "FACILITY_NAME")
        b.lit(", protokol ").ident(f"{rng.randint(2019, 2024)}-{rng.randint(10000, 99999)}", "PROTOCOL_NUMBER").lit(".\n")
        b.lit(gene).lit(" ").lit(HGVS_C[idx]).lit(" varyanti icin yeniden degerlendirme talep edildi. ")
        b.lit("Kanit durumu degisirse uzman incelemesi istenecek.\n")
        b.lit("Geri bildirim adresi: ").ident(email_for(rng, rel_first, rel_last), "EMAIL").lit(".")
        append_tr_prose(b, rng, tr)
        return b
    else:
        b.lit("Laboratuvar istem formu\n")
        b.lit("Ad Soyad: ").ident(f"{first} {last}", "PERSON_NAME").lit("\n")
        b.lit("Kimlik: ").ident(tckn(rng), "NATIONAL_ID").lit("\n")
        b.lit("Telefon: ").ident(tr_phone(rng), "PHONE").lit("\n")
        b.lit("Istem tarihi: ").ident(iso_date(rng, 2020, 2024), "EVENT_DATE").lit("\n")
        b.lit("Klinik: ").ident(rng.choice(tr["facilities"]), "FACILITY_NAME").lit("\n")
        b.lit("Hekim: Dr. ").ident(f"{doc_first} {doc_last}", "CLINICIAN_NAME").lit("\n")
        b.lit("Istenen test: kalitsal kanser paneli. Onceki rapor ").lit(gene).lit(" ").lit(HGVS_C[idx])
        b.lit(" varyanti icin klinik onemi belirsiz sonucu vermistir.\n")
        b.lit("Not: hasta ").ident(rng.choice(tr["districts"]), "ADDRESS").lit(" bolgesinde ikamet etmektedir.")
    append_tr_prose(b, rng, tr)
    return b


def append_tr_prose(b: NoteBuilder, rng: random.Random, tr: dict[str, Any]) -> None:
    """Free prose paragraph whose identifiers carry no field label.

    Prose identifiers are drawn from the full gazetteer and from a
    non-canonical date format, so a record may contain identifier surfaces
    that the frozen deterministic rule set does not recognise.
    """

    prose_first, prose_last = rng.choice(tr["first_names"]), rng.choice(tr["surnames"])
    b.lit("\nRapor kopyasi ").ident(f"{prose_first} {prose_last}", "PERSON_NAME")
    b.lit(" ile paylasildi ve ").ident(rng.choice(tr["facilities"]), "FACILITY_NAME")
    b.lit(" arsivine gonderildi. Kontrol randevusu ")
    b.ident(short_year_date(rng, 2024, 2026), "EVENT_DATE").lit(" tarihine verildi.")


def build_en_note(rng: random.Random, gz: dict[str, Any], template_id: str) -> NoteBuilder:
    en = gz["en"]
    first, last = rng.choice(en["first_names"]), rng.choice(en["surnames"])
    rel_first, rel_last = rng.choice(en["first_names"]), rng.choice(en["surnames"])
    doc_first, doc_last = rng.choice(en["first_names"]), rng.choice(en["surnames"])
    gene = rng.choice(GENES)
    idx = rng.randrange(len(HGVS_C))
    b = NoteBuilder()

    if template_id == "en-note-1":
        age = rng.randint(28, 79)
        born = birth_year(rng, age)
        b.lit("Patient: ").ident(f"{first} {last}", "PERSON_NAME")
        b.lit(", national identifier: ").ident(ssn_like(rng), "NATIONAL_ID")
        b.lit(", date of birth: ").ident(en_long_date(rng, born, born), "DATE_OF_BIRTH")
        b.lit(" (age ").ident(str(age), "AGE").lit(").\n")
        b.lit("Record number: ").ident(f"MRN-{rng.randint(100000, 999999)}", "MEDICAL_RECORD_NUMBER")
        b.lit(", protocol number: ").ident(f"{rng.randint(2019, 2024)}-{rng.randint(10000, 99999)}", "PROTOCOL_NUMBER").lit(".\n")
        b.lit("Institution: ").ident(rng.choice(en["facilities"]), "FACILITY_NAME")
        b.lit(", responsible clinician: Dr. ").ident(f"{doc_first} {doc_last}", "CLINICIAN_NAME").lit(".\n")
        b.lit("The hereditary cancer panel reported ").lit(gene).lit(" ").lit(HGVS_C[idx])
        b.lit(" (").lit(HGVS_P[idx]).lit(") on assembly ").lit(rng.choice(ASSEMBLIES)).lit(".\n")
        b.lit("The variant is currently reported as of uncertain clinical significance. Family history is notable.\n")
        b.lit("Contact: ").ident(en_phone(rng), "PHONE").lit(" / ").ident(email_for(rng, first, last), "EMAIL").lit("\n")
        b.lit("Address: ").ident(f"{rng.randint(2, 88)} {rng.choice(en['streets'])}, {rng.choice(en['districts'])}", "ADDRESS").lit(".\n")
        b.lit("Sample collection date: ").ident(en_long_date(rng, 2019, 2024), "EVENT_DATE").lit(".")
        append_en_prose(b, rng, en)
        return b
    elif template_id == "en-note-2":
        b.lit("Genetic counselling note\n")
        b.lit("Counsellee ").ident(f"{first} {last}", "PERSON_NAME").lit(", age ")
        b.ident(str(rng.randint(31, 74)), "AGE").lit(", occupation ")
        b.ident(rng.choice(en["occupations"]), "OCCUPATION").lit(".\n")
        b.lit("Her mother ").ident(f"{rel_first} {rel_last}", "RELATIVE_NAME")
        b.lit(" was followed at the same centre on ").ident(en_long_date(rng, 2015, 2021), "EVENT_DATE").lit(".\n")
        b.lit("Referring institution ").ident(rng.choice(en["facilities"]), "FACILITY_NAME")
        b.lit(", protocol ").ident(f"{rng.randint(2019, 2024)}-{rng.randint(10000, 99999)}", "PROTOCOL_NUMBER").lit(".\n")
        b.lit("Reassessment was requested for ").lit(gene).lit(" ").lit(HGVS_C[idx])
        b.lit(". A specialist review will be requested only if the evidence state changes.\n")
        b.lit("Reply address: ").ident(email_for(rng, rel_first, rel_last), "EMAIL").lit(".")
        append_en_prose(b, rng, en)
        return b
    else:
        b.lit("Laboratory request form\n")
        b.lit("Full name: ").ident(f"{first} {last}", "PERSON_NAME").lit("\n")
        b.lit("Identifier: ").ident(ssn_like(rng), "NATIONAL_ID").lit("\n")
        b.lit("Telephone: ").ident(en_phone(rng), "PHONE").lit("\n")
        b.lit("Request date: ").ident(iso_date(rng, 2020, 2024), "EVENT_DATE").lit("\n")
        b.lit("Clinic: ").ident(rng.choice(en["facilities"]), "FACILITY_NAME").lit("\n")
        b.lit("Clinician: Dr. ").ident(f"{doc_first} {doc_last}", "CLINICIAN_NAME").lit("\n")
        b.lit("Requested test: hereditary cancer panel. The previous report returned a variant of uncertain significance for ")
        b.lit(gene).lit(" ").lit(HGVS_C[idx]).lit(".\n")
        b.lit("Note: the patient resides in the ").ident(rng.choice(en["districts"]), "ADDRESS").lit(" district.")
    append_en_prose(b, rng, en)
    return b


def append_en_prose(b: NoteBuilder, rng: random.Random, en: dict[str, Any]) -> None:
    """Free prose paragraph whose identifiers carry no field label."""

    prose_first, prose_last = rng.choice(en["first_names"]), rng.choice(en["surnames"])
    b.lit("\nA copy of the report was shared with ").ident(f"{prose_first} {prose_last}", "PERSON_NAME")
    b.lit(" and archived at ").ident(rng.choice(en["facilities"]), "FACILITY_NAME")
    b.lit(". The follow-up appointment was booked for ")
    b.ident(short_year_date(rng, 2024, 2026), "EVENT_DATE").lit(".")


TR_TEMPLATES = ("tr-note-1", "tr-note-2", "tr-note-3")
EN_TEMPLATES = ("en-note-1", "en-note-2", "en-note-3")


def generate_records(count: int, seed: int, gazetteers: dict[str, Any]) -> list[dict[str, Any]]:
    if count % 2 != 0:
        raise ValueError("count must be even so both languages stay balanced")
    records: list[dict[str, Any]] = []
    for index in range(count):
        rng = random.Random(f"{seed}:{index}")
        language = "tr" if index % 2 == 0 else "en"
        if language == "tr":
            template_id = TR_TEMPLATES[index % len(TR_TEMPLATES)]
            builder = build_tr_note(rng, gazetteers, template_id)
        else:
            template_id = EN_TEMPLATES[index % len(EN_TEMPLATES)]
            builder = build_en_note(rng, gazetteers, template_id)
        text = builder.text()
        variant_rng = random.Random(f"{seed}:variant:{index}")
        variant_index = variant_rng.randrange(len(HGVS_C))
        records.append(
            {
                "record_id": f"SYNTH-{language.upper()}-{index:05d}",
                "corpus_version": CORPUS_VERSION,
                "data_mode": DATA_MODE,
                "language": language,
                "template_id": template_id,
                "seed": seed,
                "text": text,
                "spans": [s.to_wire() for s in builder.spans],
                "structured": {
                    "gene": variant_rng.choice(GENES),
                    "hgvs_c": HGVS_C[variant_index],
                    "hgvs_p": HGVS_P[variant_index],
                    "assembly": variant_rng.choice(ASSEMBLIES),
                },
            }
        )
    return records


def split_records(records: list[dict[str, Any]], ratios: tuple[int, int, int]) -> dict[str, list[dict[str, Any]]]:
    train_count, dev_count, test_count = ratios
    if train_count + dev_count + test_count != len(records):
        raise ValueError("split sizes must sum to the record count")
    return {
        "train": records[:train_count],
        "dev": records[train_count : train_count + dev_count],
        "test": records[train_count + dev_count :],
    }


def relative_to_repo(path: Path) -> str:
    """Repository-relative path when possible, otherwise the file name only."""

    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def canonical_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def class_counts(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        for span in record["spans"]:
            counts[span["identifier_class"]] = counts.get(span["identifier_class"], 0) + 1
    return dict(sorted(counts.items()))


def write_corpus(out_dir: Path, seed: int, count: int, ratios: tuple[int, int, int]) -> dict[str, Any]:
    gazetteers = json.loads(GAZETTEER_PATH.read_text(encoding="utf-8"))
    records = generate_records(count, seed, gazetteers)
    splits = split_records(records, ratios)
    out_dir.mkdir(parents=True, exist_ok=True)

    split_manifest: dict[str, Any] = {}
    for split_name, split_records_list in splits.items():
        path = out_dir / f"{split_name}.json"
        data = canonical_bytes(split_records_list)
        path.write_bytes(data)
        split_manifest[split_name] = {
            "file": relative_to_repo(path),
            "record_count": len(split_records_list),
            "language_counts": {
                "tr": sum(1 for r in split_records_list if r["language"] == "tr"),
                "en": sum(1 for r in split_records_list if r["language"] == "en"),
            },
            "identifier_span_counts": class_counts(split_records_list),
            "sha256": sha256_hex(data),
        }

    manifest = {
        "corpus_name": "recall-privacy-synthetic",
        "corpus_version": CORPUS_VERSION,
        "data_mode": DATA_MODE,
        "generator": "corpus/generator.py",
        "generator_sha256": sha256_hex(Path(__file__).read_bytes()),
        "gazetteer_sha256": sha256_hex(GAZETTEER_PATH.read_bytes()),
        "seed": seed,
        "record_count": count,
        "identifier_classes": {"direct": list(DIRECT_CLASSES), "quasi": list(QUASI_CLASSES)},
        "real_data_statement": "No real person, address, facility, record, or clinical case is represented. No external data source is read.",
        "splits": split_manifest,
    }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Recall synthetic privacy corpus.")
    parser.add_argument("--out", default=str(REPO_ROOT / "corpus" / "generated"))
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--count", type=int, default=360)
    parser.add_argument("--train", type=int, default=108)
    parser.add_argument("--dev", type=int, default=72)
    parser.add_argument("--test", type=int, default=180)
    parser.add_argument("--manifest", default=str(REPO_ROOT / "corpus" / "PRIVACY_CORPUS_MANIFEST.json"))
    args = parser.parse_args()

    manifest = write_corpus(Path(args.out), args.seed, args.count, (args.train, args.dev, args.test))
    Path(args.manifest).write_bytes(canonical_bytes(manifest))
    print(json.dumps({k: manifest[k] for k in ("corpus_version", "seed", "record_count")}, indent=2))
    for name, entry in manifest["splits"].items():
        print(f"{name}: {entry['record_count']} records sha256={entry['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
