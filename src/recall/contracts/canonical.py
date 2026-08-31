from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"unsupported_canonical_type:{type(value).__name__}")


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Encode deterministic UTF-8 JSON with no insignificant whitespace."""

    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def content_hash(value: Mapping[str, Any]) -> str:
    """Hash canonical content while omitting only top-level content_hash."""

    body = {key: item for key, item in value.items() if key != "content_hash"}
    return hashlib.sha256(canonical_json_bytes(body)).hexdigest()
