from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from .errors import ContractError


SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def require_exact_fields(
    value: Mapping[str, Any], allowed: frozenset[str], context: str
) -> None:
    unknown = set(value) - allowed
    missing = allowed - set(value)
    if unknown:
        raise ContractError("contract_unknown_field", f"{context}:{sorted(unknown)}")
    if missing:
        raise ContractError(
            "contract_required_field_missing", f"{context}:{sorted(missing)}"
        )


def uuid_value(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ContractError("contract_type_invalid", field)
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise ContractError("contract_uuid_invalid", field) from exc


def tuple_of_strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ContractError("contract_type_invalid", field)
    result = tuple(value)
    if result != tuple(sorted(set(result))):
        raise ContractError("contract_order_or_uniqueness_invalid", field)
    return result


def enum_value(enum_type: type[Any], value: Any, field: str) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ContractError("contract_enum_invalid", field) from exc


def non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError("contract_type_invalid", field)
    return value
