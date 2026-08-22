"""Strict laboratory input schema and minimisation.

Unknown or missing fields fail loudly. Only the registered minimal field set
can ever reach a cloud-bound payload, and the raw note is never one of them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MINIMIZER_VERSION = "local-minimizer@1.0.0"
CLOUD_PAYLOAD_KIND = "recall.privacy.cloud_bound_payload"
CLOUD_PAYLOAD_VERSION = "1.0.0"
SUMMARY_FIELD_PATH = "$.deidentified_summary"
REQUIRED_FIELDS = ("case_key", "note_text", "tenant_id", "region", "gene", "hgvs_c", "hgvs_p", "assembly")
ALLOWED_DATA_MODES = ("SYNTHETIC", "CAPTURED_REPLAY", "LIVE_PUBLIC", "MOCK")


class LabInputRejected(ValueError):
    """Raised when laboratory input does not match the strict local schema."""


@dataclass(frozen=True)
class LabNote:
    """One laboratory-local record. `note_text` never leaves the boundary."""

    case_key: str
    note_text: str
    tenant_id: str
    region: str
    gene: str
    hgvs_c: str
    hgvs_p: str
    assembly: str
    data_mode: str = "SYNTHETIC"

    @classmethod
    def parse(cls, payload: dict[str, Any]) -> "LabNote":
        if not isinstance(payload, dict):
            raise LabInputRejected("lab_input_not_object")
        known = set(REQUIRED_FIELDS) | {"data_mode"}
        unknown = sorted(set(payload) - known)
        if unknown:
            raise LabInputRejected(f"lab_input_unknown_field: {', '.join(unknown)}")
        missing = [name for name in REQUIRED_FIELDS if not payload.get(name)]
        if missing:
            raise LabInputRejected(f"lab_input_required_field_missing: {', '.join(sorted(missing))}")
        for name in known:
            if name in payload and not isinstance(payload[name], str):
                raise LabInputRejected(f"lab_input_field_not_text: {name}")
        data_mode = payload.get("data_mode", "SYNTHETIC")
        if data_mode not in ALLOWED_DATA_MODES:
            raise LabInputRejected(f"lab_input_unregistered_data_mode: {data_mode}")
        return cls(
            case_key=payload["case_key"],
            note_text=payload["note_text"],
            tenant_id=payload["tenant_id"],
            region=payload["region"],
            gene=payload["gene"],
            hgvs_c=payload["hgvs_c"],
            hgvs_p=payload["hgvs_p"],
            assembly=payload["assembly"],
            data_mode=data_mode,
        )


def build_cloud_bound_payload(
    note: LabNote,
    case_token: str,
    deidentified_summary: str | None = None,
) -> dict[str, Any]:
    """Minimal pseudonymous payload proposed to the cloud intake.

    `deidentified_summary` is omitted entirely when it is `None`. That is the
    structured-only egress shape: the payload has no free-text field to carry
    laboratory prose, so nothing prose-shaped can leave even if every detector
    missed something.

    This is a laboratory-side wire shape, not a registered artifact contract.
    Lane L2 owns the executable schema that parses it.
    """

    payload: dict[str, Any] = {
        "payload_kind": CLOUD_PAYLOAD_KIND,
        "payload_version": CLOUD_PAYLOAD_VERSION,
        "case_token": case_token,
        "tenant_id": note.tenant_id,
        "region": note.region,
        "data_mode": note.data_mode,
        "variant": {
            "gene": note.gene,
            "hgvs_c": note.hgvs_c,
            "hgvs_p": note.hgvs_p,
            "assembly": note.assembly,
        },
    }
    if deidentified_summary is not None:
        payload["deidentified_summary"] = deidentified_summary
    return payload
