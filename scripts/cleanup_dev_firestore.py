from __future__ import annotations

import argparse
import json

from recall.ledger import FirestoreLedger


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete one exact dev_recall_* Firestore test namespace."
    )
    parser.add_argument("--prefix", required=True)
    args = parser.parse_args()
    if not args.prefix.startswith("dev_recall_") or not args.prefix.endswith("_"):
        parser.error("prefix must start with dev_recall_ and end with underscore")

    ledger = FirestoreLedger.from_default_credentials(
        collection_prefix=args.prefix
    )
    before = {
        name: ledger.read_back_count(name) for name in ledger.collection_names
    }
    ledger.cleanup_collections()
    after = {
        name: ledger.read_back_count(name) for name in ledger.collection_names
    }
    print(json.dumps({"prefix": args.prefix, "before": before, "after": after}))
    return 0 if all(value == 0 for value in after.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
