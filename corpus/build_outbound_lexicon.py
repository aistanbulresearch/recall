"""Build the deterministic outbound allowlist from the training split only.

The outbound gate releases a redacted summary only when every token is either a
redaction placeholder, a registered variant-notation token, or a word on this
allowlist. The allowlist is derived from the committed training split with all
ground-truth identifier surfaces removed, and is frozen before evaluation. The
development and test splits are never read here, so an unseen non-identifier
word in evaluation causes a conservative quarantine rather than a silent pass.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAIN_SPLIT = REPO_ROOT / "corpus" / "generated" / "train.json"
DEFAULT_OUTPUT = REPO_ROOT / "src" / "recall" / "privacy" / "data" / "outbound_lexicon.json"
LEXICON_VERSION = "1.0.0"

TOKEN_PATTERN = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü][A-Za-zÇĞİÖŞÜçğıöşü'\-]*")
SYMBOL_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,9}\b")


def mask_identifier_spans(record: dict[str, Any]) -> str:
    text = record["text"]
    for span in sorted(record["spans"], key=lambda s: s["start"], reverse=True):
        text = text[: span["start"]] + " " + text[span["end"] :]
    return text


def build_lexicon(train_split: Path) -> dict[str, Any]:
    records = json.loads(train_split.read_text(encoding="utf-8"))
    words: set[str] = set()
    symbols: set[str] = set()
    for record in records:
        masked = mask_identifier_spans(record)
        for token in TOKEN_PATTERN.findall(masked):
            words.add(token.lower())
        symbols.update(SYMBOL_PATTERN.findall(masked))
    return {
        "lexicon_version": LEXICON_VERSION,
        "source_split": "train",
        "source_record_count": len(records),
        "derivation": "tokens of the training split after removing every ground-truth identifier surface",
        "limitation": "This allowlist reflects the committed synthetic template vocabulary. A laboratory deployment requires a curated clinical vocabulary; coverage on arbitrary real text is unmeasured.",
        "words": sorted(words),
        "registered_symbols": sorted(symbols),
        "registered_symbols_note": "Uppercase panel and assembly symbols observed in the training split. A laboratory deployment registers its own panel list instead.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the deterministic outbound allowlist.")
    parser.add_argument("--train-split", default=str(DEFAULT_TRAIN_SPLIT))
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    lexicon = build_lexicon(Path(args.train_split))
    Path(args.out).write_text(json.dumps(lexicon, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"lexicon words: {len(lexicon['words'])}, registered symbols: {len(lexicon['registered_symbols'])}, "
        f"from {lexicon['source_record_count']} training records"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
