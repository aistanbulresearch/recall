from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import re
from typing import Callable
from types import MappingProxyType
from uuid import UUID

from recall.agents.config import ROLE_TOOL_IDS
from recall.contracts import (
    AgentRole,
    DataMode,
    ReplayStage,
    canonical_json_bytes,
)


CAPABILITY_STATE_KEY = "recall.tool_capability"
CAPABILITY_VERSION = "1"
MAX_CAPABILITY_TTL = timedelta(minutes=15)
ROLE_ARTIFACT_SCHEMA_NAMES = MappingProxyType(
    {
        AgentRole.EVIDENCE_WATCHER: frozenset(),
        AgentRole.EVIDENCE_ASSESSOR: frozenset(
            {"CandidateDeltaReceipt", "EvidenceObservation", "EvidenceSnapshot"}
        ),
        AgentRole.CITATION_AUDITOR: frozenset(
            {
                "AssessmentReceipt",
                "CandidateDeltaReceipt",
                "EvidenceDelta",
                "EvidenceObservation",
            }
        ),
        AgentRole.FLEET_COORDINATOR: frozenset(),
    }
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CAPABILITY_FIELDS = frozenset(
    {
        "capability_id",
        "role",
        "case_id",
        "run_id",
        "data_mode",
        "allowed_tool_ids",
        "allowed_artifact_ids",
        "allowed_artifact_schema_names",
        "allowed_replay_stages",
        "refetch_grants",
        "issued_at",
        "expires_at",
    }
)
_REFETCH_GRANT_FIELDS = frozenset(
    {
        "claim_id",
        "source_artifact_id",
        "source_artifact_content_hash",
        "identifier",
        "title",
        "locator",
        "content_hash",
        "data_mode",
    }
)


def _stamp(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("tool_capability_timestamp_naive")
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_stamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"tool_capability_{field}_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"tool_capability_{field}_invalid") from exc
    return parsed.astimezone(UTC)


def _closed_strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ValueError(f"tool_capability_{field}_invalid")
    result = tuple(value)
    if result != tuple(sorted(set(result))):
        raise ValueError(f"tool_capability_{field}_not_canonical")
    return result


@dataclass(frozen=True, slots=True)
class RefetchGrant:
    claim_id: str
    source_artifact_id: str
    source_artifact_content_hash: str
    identifier: str
    title: str
    locator: str
    content_hash: str
    data_mode: DataMode

    def __post_init__(self) -> None:
        if not all((self.claim_id, self.identifier, self.title, self.locator)):
            raise ValueError("refetch_grant_field_required")
        UUID(self.source_artifact_id)
        if not _SHA256.fullmatch(self.source_artifact_content_hash):
            raise ValueError("refetch_grant_source_artifact_hash_invalid")
        if not _SHA256.fullmatch(self.content_hash):
            raise ValueError("refetch_grant_content_hash_invalid")
        if self.data_mode not in {
            DataMode.CAPTURED_REPLAY,
            DataMode.LIVE_PUBLIC,
        }:
            raise ValueError("refetch_grant_data_mode_invalid")

    def to_wire(self) -> dict[str, str]:
        return {
            "claim_id": self.claim_id,
            "source_artifact_id": self.source_artifact_id,
            "source_artifact_content_hash": self.source_artifact_content_hash,
            "identifier": self.identifier,
            "title": self.title,
            "locator": self.locator,
            "content_hash": self.content_hash,
            "data_mode": self.data_mode.value,
        }

    @classmethod
    def from_wire(cls, value: object) -> RefetchGrant:
        if not isinstance(value, Mapping) or set(value) != _REFETCH_GRANT_FIELDS:
            raise ValueError("refetch_grant_fields_invalid")
        if any(not isinstance(value[field], str) for field in value):
            raise ValueError("refetch_grant_type_invalid")
        try:
            return cls(
                claim_id=value["claim_id"],
                source_artifact_id=value["source_artifact_id"],
                source_artifact_content_hash=value[
                    "source_artifact_content_hash"
                ],
                identifier=value["identifier"],
                title=value["title"],
                locator=value["locator"],
                content_hash=value["content_hash"],
                data_mode=DataMode(value["data_mode"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("refetch_grant_invalid") from exc


@dataclass(frozen=True, slots=True)
class RunToolCapability:
    capability_id: str
    role: AgentRole
    case_id: str
    run_id: str
    data_mode: DataMode
    allowed_tool_ids: tuple[str, ...]
    allowed_artifact_ids: tuple[str, ...]
    allowed_artifact_schema_names: tuple[str, ...]
    allowed_replay_stages: tuple[str, ...]
    refetch_grants: tuple[RefetchGrant, ...]
    issued_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        UUID(self.capability_id)
        UUID(self.case_id)
        UUID(self.run_id)
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("tool_capability_timestamp_naive")
        if not self.issued_at < self.expires_at:
            raise ValueError("tool_capability_expiry_invalid")
        if self.expires_at - self.issued_at > MAX_CAPABILITY_TTL:
            raise ValueError("tool_capability_ttl_exceeded")
        for field in (
            "allowed_tool_ids",
            "allowed_artifact_ids",
            "allowed_artifact_schema_names",
            "allowed_replay_stages",
        ):
            values = getattr(self, field)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"tool_capability_{field}_not_canonical")
        if set(self.allowed_tool_ids) - set(ROLE_TOOL_IDS[self.role]):
            raise ValueError("tool_capability_tool_not_role_allowed")
        if set(self.allowed_artifact_schema_names) - set(
            ROLE_ARTIFACT_SCHEMA_NAMES[self.role]
        ):
            raise ValueError("tool_capability_schema_not_role_allowed")
        for artifact_id in self.allowed_artifact_ids:
            UUID(artifact_id)
        for stage in self.allowed_replay_stages:
            ReplayStage(stage)
        if self.allowed_replay_stages and (
            self.role is not AgentRole.EVIDENCE_WATCHER
            or self.data_mode is not DataMode.CAPTURED_REPLAY
        ):
            raise ValueError("tool_capability_replay_scope_invalid")
        if (
            self.role is AgentRole.EVIDENCE_WATCHER
            and self.data_mode is not DataMode.CAPTURED_REPLAY
        ):
            raise ValueError("tool_capability_watcher_mode_invalid")
        claim_ids = tuple(grant.claim_id for grant in self.refetch_grants)
        if claim_ids != tuple(sorted(set(claim_ids))):
            raise ValueError("tool_capability_refetch_grants_not_canonical")
        if self.refetch_grants and (
            self.role is not AgentRole.CITATION_AUDITOR
            or "EvidenceObservation" not in self.allowed_artifact_schema_names
        ):
            raise ValueError("tool_capability_refetch_scope_invalid")
        for grant in self.refetch_grants:
            if grant.source_artifact_id not in self.allowed_artifact_ids:
                raise ValueError("tool_capability_refetch_artifact_not_granted")
            if grant.data_mode is not self.data_mode:
                raise ValueError("tool_capability_refetch_mode_mismatch")

    def to_wire(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "role": self.role.value,
            "case_id": self.case_id,
            "run_id": self.run_id,
            "data_mode": self.data_mode.value,
            "allowed_tool_ids": list(self.allowed_tool_ids),
            "allowed_artifact_ids": list(self.allowed_artifact_ids),
            "allowed_artifact_schema_names": list(
                self.allowed_artifact_schema_names
            ),
            "allowed_replay_stages": list(self.allowed_replay_stages),
            "refetch_grants": [grant.to_wire() for grant in self.refetch_grants],
            "issued_at": _stamp(self.issued_at),
            "expires_at": _stamp(self.expires_at),
        }

    @classmethod
    def from_wire(cls, value: object) -> RunToolCapability:
        if not isinstance(value, Mapping) or set(value) != _CAPABILITY_FIELDS:
            raise ValueError("tool_capability_fields_invalid")
        scalar_fields = (
            "capability_id",
            "role",
            "case_id",
            "run_id",
            "data_mode",
            "issued_at",
            "expires_at",
        )
        if any(not isinstance(value[field], str) for field in scalar_fields):
            raise ValueError("tool_capability_type_invalid")
        raw_grants = value["refetch_grants"]
        if not isinstance(raw_grants, list):
            raise ValueError("tool_capability_refetch_grants_invalid")
        try:
            return cls(
                capability_id=value["capability_id"],
                role=AgentRole(value["role"]),
                case_id=value["case_id"],
                run_id=value["run_id"],
                data_mode=DataMode(value["data_mode"]),
                allowed_tool_ids=_closed_strings(
                    value["allowed_tool_ids"], "allowed_tool_ids"
                ),
                allowed_artifact_ids=_closed_strings(
                    value["allowed_artifact_ids"], "allowed_artifact_ids"
                ),
                allowed_artifact_schema_names=_closed_strings(
                    value["allowed_artifact_schema_names"],
                    "allowed_artifact_schema_names",
                ),
                allowed_replay_stages=_closed_strings(
                    value["allowed_replay_stages"], "allowed_replay_stages"
                ),
                refetch_grants=tuple(
                    RefetchGrant.from_wire(item) for item in raw_grants
                ),
                issued_at=_parse_stamp(value["issued_at"], "issued_at"),
                expires_at=_parse_stamp(value["expires_at"], "expires_at"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith("tool_capability_"):
                raise
            raise ValueError("tool_capability_invalid") from exc


class ToolCapabilityCodec:
    def __init__(self, secret: bytes, *, clock: Callable[[], datetime]) -> None:
        if len(secret) < 32:
            raise ValueError("tool_capability_secret_too_short")
        self._secret = secret
        self._clock = clock

    def issue(self, capability: RunToolCapability) -> str:
        payload = canonical_json_bytes(capability.to_wire())
        signature = hmac.new(self._secret, payload, hashlib.sha256).digest()
        return ".".join(
            (
                CAPABILITY_VERSION,
                _b64encode(payload),
                _b64encode(signature),
            )
        )

    def now(self) -> datetime:
        return self._clock().astimezone(UTC)

    def verify(self, token: str) -> RunToolCapability:
        try:
            version, payload_text, signature_text = token.split(".")
            if version != CAPABILITY_VERSION:
                raise ValueError("tool_capability_version_invalid")
            payload = _b64decode(payload_text)
            supplied = _b64decode(signature_text)
        except (TypeError, ValueError) as exc:
            if str(exc).startswith("tool_capability_"):
                raise
            raise ValueError("tool_capability_format_invalid") from exc
        expected = hmac.new(self._secret, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied, expected):
            raise ValueError("tool_capability_signature_invalid")
        try:
            wire = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("tool_capability_payload_invalid") from exc
        capability = RunToolCapability.from_wire(wire)
        now = self.now()
        if now >= capability.expires_at:
            raise ValueError("tool_capability_expired")
        if capability.issued_at > now + timedelta(seconds=30):
            raise ValueError("tool_capability_not_yet_valid")
        return capability


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        decoded = base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("tool_capability_format_invalid") from exc
    if _b64encode(decoded) != value:
        raise ValueError("tool_capability_format_invalid")
    return decoded
