"""Laboratory-local signing of privacy receipts.

The signing key stays inside the laboratory boundary. A missing key is a loud
failure, never a silently unsigned receipt.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SIGNING_ALGORITHM = "HMAC-SHA256"
KEY_ENVIRONMENT_VARIABLE = "RECALL_PRIVACY_SIGNING_KEY"
DEFAULT_KEY_DIRECTORY = Path("token-vault")


class SigningKeyUnavailable(RuntimeError):
    """Raised when no laboratory-local signing key is configured."""


def canonical_json(payload: Any) -> str:
    """Canonical UTF-8 JSON: sorted keys, no insignificant whitespace."""

    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LocalSigner:
    key_id: str
    key: bytes

    def sign(self, message: str) -> str:
        return hmac.new(self.key, message.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify(self, message: str, signature: str) -> bool:
        return hmac.compare_digest(self.sign(message), signature)

    def signature_ref(self, message: str) -> dict[str, str]:
        return {"key_id": self.key_id, "algorithm": SIGNING_ALGORITHM, "signature": self.sign(message)}

    def span_key(self) -> bytes:
        """Separate derived key so span hashes and receipt signatures differ."""

        return hmac.new(self.key, b"recall/privacy/span-hash/v1", hashlib.sha256).digest()


def load_signer(key_directory: Path | None = None) -> LocalSigner:
    """Load the local signing key from the environment or the ignored key file.

    Raises `SigningKeyUnavailable` rather than generating a throwaway key: an
    unverifiable receipt must never look like a signed one.
    """

    environment_key = os.environ.get(KEY_ENVIRONMENT_VARIABLE)
    if environment_key:
        return LocalSigner(key_id="env-local-key", key=environment_key.encode("utf-8"))

    directory = key_directory or DEFAULT_KEY_DIRECTORY
    key_file = directory / "privacy-signing-key.json"
    if not key_file.exists():
        raise SigningKeyUnavailable(
            f"no signing key in {KEY_ENVIRONMENT_VARIABLE} and no key file at {key_file}"
        )
    material = json.loads(key_file.read_text(encoding="utf-8"))
    if "key_id" not in material or "key" not in material:
        raise SigningKeyUnavailable(f"key file {key_file} is missing key_id or key")
    return LocalSigner(key_id=str(material["key_id"]), key=str(material["key"]).encode("utf-8"))
