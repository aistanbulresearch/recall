"""Deterministic outbound gate.

Nothing leaves the laboratory because a detector stayed silent. Two independent
rules decide:

* a declared free-text field is released only when every token in it is
  positively recognised: a redaction placeholder, a registered panel or assembly
  symbol, registered variant notation, or a word on the frozen allowlist;
* every structured leaf is released only when its path is registered in
  `egress.STRUCTURED_FIELD_RULES` and its value matches the registered shape.

The structured rule matters most under the structured-only egress profile, where
the whole payload is structured and no free-text field is declared at all.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from recall.privacy.egress import validate_structured_leaf

OUTBOUND_SCANNER_VERSION = "outbound-allowlist-scanner@1.1.0"
DEFAULT_LEXICON_PATH = Path(__file__).resolve().parent / "data" / "outbound_lexicon.json"

SCAN_STATUS_CLEAR = "CLEAR"
SCAN_STATUS_BLOCKED = "BLOCKED"

PLACEHOLDER_PATTERN = re.compile(r"^\[[A-Z_]+\]$")
CODING_VARIANT_PATTERN = re.compile(r"^c\.[0-9][0-9A-Za-z_>+\-]*$")
PROTEIN_VARIANT_PATTERN = re.compile(r"^p\.[A-Za-z]{3}[0-9]+[A-Za-z]*$")
ASSEMBLY_PATTERN = re.compile(r"^GRCh3[78]$")
STRIPPABLE = " \t\r\n.,;:()<>\"'!?/\\"
DIGIT_PATTERN = re.compile(r"[0-9]")


@dataclass(frozen=True)
class FieldScan:
    field_path: str
    released: bool
    unknown_token_count: int
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class OutboundScanResult:
    scan_status: str
    allowed_field_paths: tuple[str, ...]
    blocked_field_paths: tuple[str, ...]
    raw_text_field_count: int
    unknown_token_count: int
    reason_codes: tuple[str, ...]
    field_scans: tuple[FieldScan, ...]
    blocked_structured_field_paths: tuple[str, ...] = ()
    scanner_version: str = OUTBOUND_SCANNER_VERSION


class OutboundScanner:
    """Positive-allowlist scanner for every field bound for the cloud."""

    version = OUTBOUND_SCANNER_VERSION

    def __init__(self, lexicon: dict[str, Any] | None = None) -> None:
        payload = lexicon if lexicon is not None else json.loads(DEFAULT_LEXICON_PATH.read_text(encoding="utf-8"))
        self.lexicon_version = str(payload.get("lexicon_version", "unversioned"))
        self.words = frozenset(word.lower() for word in payload.get("words", []))
        self.symbols = frozenset(payload.get("registered_symbols", []))

    def token_allowed(self, token: str) -> bool:
        stripped = token.strip(STRIPPABLE)
        if not stripped:
            return True
        if PLACEHOLDER_PATTERN.match(stripped):
            return True
        stripped = stripped.strip("[]{}")
        if not stripped:
            return True
        if stripped in self.symbols:
            return True
        if ASSEMBLY_PATTERN.match(stripped) or CODING_VARIANT_PATTERN.match(stripped) or PROTEIN_VARIANT_PATTERN.match(stripped):
            return True
        if DIGIT_PATTERN.search(stripped):
            return False
        return stripped.lower() in self.words

    def scan_text(self, value: str) -> tuple[int, tuple[str, ...]]:
        unknown = [token for token in value.split() if not self.token_allowed(token)]
        if not unknown:
            return 0, ()
        return len(unknown), ("outbound_unknown_token_present",)

    def scan_payload(self, payload: dict[str, Any], text_field_paths: tuple[str, ...]) -> OutboundScanResult:
        """Scan every declared free-text field and every structured leaf.

        `raw_text_field_count` counts declared free-text fields that the token
        allowlist refused. Under the structured-only profile no free-text field
        is declared, so the count is zero by construction rather than by a
        detector's silence.
        """

        field_scans: list[FieldScan] = []
        allowed: list[str] = []
        blocked_text: list[str] = []
        blocked_structured: list[str] = []
        reason_codes: set[str] = set()
        unknown_total = 0

        for field_path in text_field_paths:
            value = _resolve_path(payload, field_path)
            if value is None:
                field_scans.append(FieldScan(field_path, False, 0, ("outbound_field_missing",)))
                blocked_text.append(field_path)
                reason_codes.add("outbound_field_missing")
                continue
            if not isinstance(value, str):
                field_scans.append(FieldScan(field_path, False, 0, ("outbound_field_not_text",)))
                blocked_text.append(field_path)
                reason_codes.add("outbound_field_not_text")
                continue
            unknown_count, field_reasons = self.scan_text(value)
            unknown_total += unknown_count
            if field_reasons:
                blocked_text.append(field_path)
                reason_codes.update(field_reasons)
                field_scans.append(FieldScan(field_path, False, unknown_count, field_reasons))
            else:
                allowed.append(field_path)
                field_scans.append(FieldScan(field_path, True, 0, ()))

        for field_path in sorted(_leaf_paths(payload) - set(text_field_paths)):
            accepted, reason_code = validate_structured_leaf(field_path, _resolve_path(payload, field_path))
            if accepted:
                allowed.append(field_path)
                field_scans.append(FieldScan(field_path, True, 0, ()))
            else:
                blocked_structured.append(field_path)
                reason_codes.add(reason_code)
                field_scans.append(FieldScan(field_path, False, 0, (reason_code,)))

        blocked = blocked_text + blocked_structured
        return OutboundScanResult(
            scan_status=SCAN_STATUS_BLOCKED if blocked else SCAN_STATUS_CLEAR,
            allowed_field_paths=tuple(sorted(allowed)),
            blocked_field_paths=tuple(sorted(blocked)),
            raw_text_field_count=len(blocked_text),
            unknown_token_count=unknown_total,
            reason_codes=tuple(sorted(reason_codes)),
            field_scans=tuple(field_scans),
            blocked_structured_field_paths=tuple(sorted(blocked_structured)),
        )


def _resolve_path(payload: dict[str, Any], field_path: str) -> Any:
    current: Any = payload
    for part in field_path.lstrip("$").strip(".").split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _leaf_paths(payload: Any, prefix: str = "$") -> set[str]:
    if isinstance(payload, dict):
        paths: set[str] = set()
        for key, value in payload.items():
            paths.update(_leaf_paths(value, f"{prefix}.{key}"))
        return paths
    return {prefix}
