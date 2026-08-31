"""Token vault interface for laboratory-local pseudonymisation.

The vault maps a laboratory case key to a stable opaque case token. The mapping
is laboratory-local state: it is never included in a receipt, a cloud payload,
a log line, or a repository artifact.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from pathlib import Path
from typing import Protocol


class TokenVault(Protocol):
    def case_token(self, case_key: str) -> str:
        """Return the stable opaque token for a laboratory case key."""


class DerivedTokenVault:
    """Keyed, deterministic, in-memory vault.

    The token is derived from the laboratory-local key, so the same case key
    always yields the same token without persisting a reversible mapping.
    """

    def __init__(self, key: bytes) -> None:
        if not key:
            raise ValueError("token vault requires a laboratory-local key")
        self._key = key

    def case_token(self, case_key: str) -> str:
        digest = hmac.new(self._key, case_key.encode("utf-8"), hashlib.sha256).digest()
        return str(uuid.UUID(bytes=digest[:16], version=5))


class FileTokenVault:
    """File-backed vault for laboratory operation.

    The backing file lives under the ignored `token-vault/` directory. It is a
    laboratory artifact and must never be committed or transmitted.
    """

    def __init__(self, path: Path, key: bytes) -> None:
        self._path = path
        self._derived = DerivedTokenVault(key)

    def case_token(self, case_key: str) -> str:
        mapping = {}
        if self._path.exists():
            mapping = json.loads(self._path.read_text(encoding="utf-8"))
        if case_key in mapping:
            return str(mapping[case_key])
        token = self._derived.case_token(case_key)
        mapping[case_key] = token
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(mapping, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return token
