from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

from recall.demo import parse_fixture_spec, run_fixture
from recall.ledger import FirestoreLedger, InMemoryLedger


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _paths(arguments: argparse.Namespace) -> list[Path]:
    if arguments.all:
        return sorted(FIXTURE_DIR.glob("*.json"))
    if not arguments.fixture:
        raise SystemExit("fixture_required:use_--fixture_or_--all")
    return [Path(arguments.fixture).resolve()]


def _run(path: Path, backend: str) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    spec = parse_fixture_spec(raw)
    execution_id = uuid4().hex
    if backend == "memory":
        return {"run": run_fixture(InMemoryLedger(), spec, execution_id=execution_id)}
    prefix = f"dev_recall_3e_{uuid4().hex}_"
    ledger = FirestoreLedger.from_default_credentials(collection_prefix=prefix)
    result: dict[str, object] = {"collection_prefix": prefix}
    try:
        result["run"] = run_fixture(ledger, spec, execution_id=execution_id)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}:{exc}"
    finally:
        ledger.cleanup_collections()
        result["post_cleanup_counts"] = {
            name: ledger.read_back_count(name) for name in ledger.collection_names
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--backend", choices=("memory", "firestore"), default="memory")
    arguments = parser.parse_args()
    failed = False
    for path in _paths(arguments):
        result = _run(path, arguments.backend)
        print(json.dumps(result, sort_keys=True))
        failed = failed or "error" in result
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
