from __future__ import annotations

from pathlib import Path

from recall.testing.deadline_policy_vectors import (
    VECTOR_PATH,
    render_deadline_policy_vectors,
)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    target = repo_root / VECTOR_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(render_deadline_policy_vectors(repo_root))
    print(target.as_posix())


if __name__ == "__main__":
    main()
