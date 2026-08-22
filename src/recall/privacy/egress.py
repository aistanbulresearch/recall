"""Registered egress profiles and the structured-field allowlist.

The outbound decision does not depend on a detector staying silent. A
cloud-bound payload may carry only registered field paths whose values match a
registered shape, and the default profile declares **no free-text field at
all**. Under that profile laboratory prose cannot leave even if every detector,
deterministic or model-backed, misses every identifier in it.

The second profile keeps the redacted-summary path available so protocol P1 can
still measure what deterministic detection plus local-model proposals achieve on
free text. It is a measurement comparator, not the demonstrated egress path.

Ownership: lane L3. Related tasks: RCL-403, RCL-405.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from recall.privacy.minimizer import (
    ALLOWED_DATA_MODES,
    CLOUD_PAYLOAD_KIND,
    SUMMARY_FIELD_PATH,
)

EGRESS_PROFILE_VERSION = "1.0.0"
EGRESS_STRUCTURED_ONLY = "STRUCTURED_ONLY"
EGRESS_SUMMARY_TEXT = "SUMMARY_TEXT"

REASON_UNREGISTERED_FIELD = "outbound_structured_field_unregistered"
REASON_VALUE_REJECTED = "outbound_structured_value_rejected"
REASON_FREE_TEXT_PRESENT = "egress_free_text_field_present"
REASON_MODEL_FAILURE_BLOCKS_TEXT = "local_model_failure_blocks_free_text_egress"


@dataclass(frozen=True)
class EgressProfile:
    """One registered answer to the question of what may leave the laboratory."""

    name: str
    text_field_paths: tuple[str, ...]
    version: str = EGRESS_PROFILE_VERSION

    @property
    def releases_free_text(self) -> bool:
        return bool(self.text_field_paths)

    @property
    def identifier(self) -> str:
        """Value recorded in `PrivacyReceipt.detector_versions.egress_profile`."""

        return f"{self.name}@{self.version}"


STRUCTURED_ONLY_PROFILE = EgressProfile(name=EGRESS_STRUCTURED_ONLY, text_field_paths=())
SUMMARY_TEXT_PROFILE = EgressProfile(name=EGRESS_SUMMARY_TEXT, text_field_paths=(SUMMARY_FIELD_PATH,))

EGRESS_PROFILES: dict[str, EgressProfile] = {
    STRUCTURED_ONLY_PROFILE.name: STRUCTURED_ONLY_PROFILE,
    SUMMARY_TEXT_PROFILE.name: SUMMARY_TEXT_PROFILE,
}


class UnregisteredEgressProfile(ValueError):
    """Raised when a caller asks for an egress profile that is not registered."""


def resolve_profile(profile: EgressProfile | str) -> EgressProfile:
    if isinstance(profile, EgressProfile):
        return profile
    try:
        return EGRESS_PROFILES[profile]
    except KeyError as error:
        raise UnregisteredEgressProfile(f"unregistered egress profile: {profile}") from error


@dataclass(frozen=True)
class StructuredFieldRule:
    """Registered shape of one structured leaf of the cloud-bound payload."""

    field_path: str
    pattern: re.Pattern[str]
    max_length: int

    def accepts(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        if not value or len(value) > self.max_length:
            return False
        return self.pattern.fullmatch(value) is not None


def _literal(value: str) -> re.Pattern[str]:
    return re.compile(re.escape(value))


def _one_of(values: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile("|".join(re.escape(value) for value in values))


STRUCTURED_FIELD_RULES: dict[str, StructuredFieldRule] = {
    rule.field_path: rule
    for rule in (
        StructuredFieldRule("$.payload_kind", _literal(CLOUD_PAYLOAD_KIND), 64),
        StructuredFieldRule("$.payload_version", re.compile(r"[0-9]+\.[0-9]+\.[0-9]+"), 16),
        # Opaque vault token: a UUID string, never the laboratory case key.
        StructuredFieldRule("$.case_token", re.compile(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}"), 36),
        StructuredFieldRule("$.tenant_id", re.compile(r"[a-z0-9][a-z0-9-]{1,62}"), 63),
        StructuredFieldRule("$.region", re.compile(r"[a-z0-9][a-z0-9-]{1,31}"), 32),
        StructuredFieldRule("$.data_mode", _one_of(ALLOWED_DATA_MODES), 16),
        StructuredFieldRule("$.variant.gene", re.compile(r"[A-Z][A-Z0-9-]{0,15}"), 16),
        StructuredFieldRule("$.variant.hgvs_c", re.compile(r"c\.[0-9][0-9A-Za-z_>+\-]{0,63}"), 64),
        StructuredFieldRule("$.variant.hgvs_p", re.compile(r"p\.[A-Za-z]{3}[0-9]+[A-Za-z]*"), 64),
        StructuredFieldRule("$.variant.assembly", re.compile(r"GRCh3[78]"), 8),
    )
}


def validate_structured_leaf(field_path: str, value: Any) -> tuple[bool, str]:
    """Return acceptance and, on refusal, the reason code to record.

    An unregistered path is refused rather than passed through: a field nobody
    registered is a field nobody reviewed.
    """

    rule = STRUCTURED_FIELD_RULES.get(field_path)
    if rule is None:
        return False, REASON_UNREGISTERED_FIELD
    if not rule.accepts(value):
        return False, REASON_VALUE_REJECTED
    return True, ""


def free_text_fields_present(payload: dict[str, Any], profile: EgressProfile) -> tuple[str, ...]:
    """Free-text paths present in a payload that the profile does not declare.

    This is the released-payload invariant check. It exists so that a future
    change to the minimiser cannot quietly reintroduce prose egress under the
    structured-only profile.
    """

    declared = set(profile.text_field_paths)
    return tuple(sorted(path for path in _leaf_paths(payload) if path not in STRUCTURED_FIELD_RULES and path not in declared))


def _leaf_paths(payload: Any, prefix: str = "$") -> set[str]:
    if isinstance(payload, dict):
        paths: set[str] = set()
        for key, value in payload.items():
            paths.update(_leaf_paths(value, f"{prefix}.{key}"))
        return paths
    return {prefix}
