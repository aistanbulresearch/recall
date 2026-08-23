from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .enums import DataMode
from .errors import ContractError
from .validation import enum_value, non_empty_string, require_exact_fields, uuid_value


_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_TENANT = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
_REGION = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")
_GENE = re.compile(r"^[A-Z][A-Z0-9-]{0,15}$")
_HGVS_C = re.compile(r"^c\.[0-9][0-9A-Za-z_>+\-]{0,63}$")
_HGVS_P = re.compile(r"^p\.[A-Za-z]{3}[0-9]+[A-Za-z]*$")
_ASSEMBLY = re.compile(r"^GRCh3[78]$")


@dataclass(frozen=True, slots=True)
class CloudBoundPayload:
    payload_kind: str
    payload_version: str
    case_token: str
    tenant_id: str
    region: str
    data_mode: DataMode
    variant: Mapping[str, str]
    deidentified_summary: str | None = None

    def to_wire(self) -> dict[str, object]:
        wire: dict[str, object] = {
            "payload_kind": self.payload_kind,
            "payload_version": self.payload_version,
            "case_token": self.case_token,
            "tenant_id": self.tenant_id,
            "region": self.region,
            "data_mode": self.data_mode.value,
            "variant": dict(self.variant),
        }
        if self.deidentified_summary is not None:
            wire["deidentified_summary"] = self.deidentified_summary
        return wire


def parse_cloud_bound_payload(value: Mapping[str, Any]) -> CloudBoundPayload:
    if not isinstance(value, Mapping):
        raise ContractError("contract_type_invalid", "cloud_bound_payload")
    required = {
        "payload_kind",
        "payload_version",
        "case_token",
        "tenant_id",
        "region",
        "data_mode",
        "variant",
    }
    allowed = required | {"deidentified_summary"}
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        raise ContractError(
            "contract_unknown_field", f"cloud_bound_payload:{sorted(unknown)}"
        )
    if missing:
        raise ContractError(
            "contract_required_field_missing",
            f"cloud_bound_payload:{sorted(missing)}",
        )
    if value["payload_kind"] != "recall.privacy.cloud_bound_payload":
        raise ContractError("contract_value_invalid", "payload_kind")
    version = non_empty_string(value["payload_version"], "payload_version")
    if version != "1.0.0" or not _VERSION.fullmatch(version):
        raise ContractError("contract_major_unsupported", "cloud_bound_payload")
    variant = value["variant"]
    if not isinstance(variant, Mapping):
        raise ContractError("contract_type_invalid", "variant")
    require_exact_fields(
        variant, frozenset({"gene", "hgvs_c", "hgvs_p", "assembly"}), "variant"
    )
    validators = {
        "gene": _GENE,
        "hgvs_c": _HGVS_C,
        "hgvs_p": _HGVS_P,
        "assembly": _ASSEMBLY,
    }
    parsed_variant: dict[str, str] = {}
    for field, pattern in validators.items():
        item = non_empty_string(variant[field], f"variant.{field}")
        if not pattern.fullmatch(item):
            raise ContractError("contract_value_invalid", f"variant.{field}")
        parsed_variant[field] = item
    tenant_id = non_empty_string(value["tenant_id"], "tenant_id")
    region = non_empty_string(value["region"], "region")
    if not _TENANT.fullmatch(tenant_id):
        raise ContractError("contract_value_invalid", "tenant_id")
    if not _REGION.fullmatch(region):
        raise ContractError("contract_value_invalid", "region")
    summary = value.get("deidentified_summary")
    if summary is not None:
        summary = non_empty_string(summary, "deidentified_summary")
    return CloudBoundPayload(
        payload_kind="recall.privacy.cloud_bound_payload",
        payload_version=version,
        case_token=str(uuid_value(value["case_token"], "case_token")),
        tenant_id=tenant_id,
        region=region,
        data_mode=enum_value(DataMode, value["data_mode"], "data_mode"),
        variant=MappingProxyType(parsed_variant),
        deidentified_summary=summary,
    )
