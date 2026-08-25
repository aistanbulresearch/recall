from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..errors import ContractError
from ..validation import non_empty_string, uuid_value


_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_FAILURE_CODE = "previous_cohort_manifest_missing"
_CONTINUATION_POLICY = "RECORD_INCOMPLETE_AND_CONTINUE"


@dataclass(frozen=True, slots=True)
class CohortDayFailureReceiptPayload:
    day_index: int
    selected_for_date: str
    detected_at: str
    failure_code: str
    expected_manifest_id: str
    runs_predicted: int
    runs_created: int
    source_commit: str
    image_digest: str
    continuation_policy: str

    def to_wire(self) -> dict[str, object]:
        return {
            "day_index": self.day_index,
            "selected_for_date": self.selected_for_date,
            "detected_at": self.detected_at,
            "failure_code": self.failure_code,
            "expected_manifest_id": self.expected_manifest_id,
            "runs_predicted": self.runs_predicted,
            "runs_created": self.runs_created,
            "source_commit": self.source_commit,
            "image_digest": self.image_digest,
            "continuation_policy": self.continuation_policy,
        }


def parse_cohort_day_failure_receipt_payload(
    value: Mapping[str, Any],
) -> CohortDayFailureReceiptPayload:
    day_index = _integer(value["day_index"], "day_index", minimum=1)
    selected_for_date = _date(value["selected_for_date"], "selected_for_date")
    detected_at = _timestamp(value["detected_at"], "detected_at")
    if value["created_at"] != detected_at:
        raise ContractError("contract_value_invalid", "detected_at")
    if value["status"] != "INCOMPLETE":
        raise ContractError("contract_value_invalid", "status")
    if value["failure_code"] != _FAILURE_CODE:
        raise ContractError("contract_value_invalid", "failure_code")
    expected_manifest_id = str(
        uuid_value(value["expected_manifest_id"], "expected_manifest_id")
    )
    runs_predicted = _integer(value["runs_predicted"], "runs_predicted")
    runs_created = _integer(value["runs_created"], "runs_created")
    if runs_created != 0:
        raise ContractError("contract_value_invalid", "runs_created")
    source_commit = non_empty_string(value["source_commit"], "source_commit")
    if not _COMMIT.fullmatch(source_commit):
        raise ContractError("contract_hash_invalid", "source_commit")
    image_digest = non_empty_string(value["image_digest"], "image_digest")
    if not _IMAGE_DIGEST.fullmatch(image_digest):
        raise ContractError("contract_hash_invalid", "image_digest")
    if value["continuation_policy"] != _CONTINUATION_POLICY:
        raise ContractError("contract_value_invalid", "continuation_policy")
    return CohortDayFailureReceiptPayload(
        day_index=day_index,
        selected_for_date=selected_for_date,
        detected_at=detected_at,
        failure_code=_FAILURE_CODE,
        expected_manifest_id=expected_manifest_id,
        runs_predicted=runs_predicted,
        runs_created=0,
        source_commit=source_commit,
        image_digest=image_digest,
        continuation_policy=_CONTINUATION_POLICY,
    )


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ContractError("contract_type_invalid", field)
    return value


def _date(value: Any, field: str) -> str:
    from datetime import date

    if not isinstance(value, str):
        raise ContractError("contract_type_invalid", field)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError("contract_date_invalid", field) from exc
    if parsed.isoformat() != value:
        raise ContractError("contract_date_invalid", field)
    return value


def _timestamp(value: Any, field: str) -> str:
    from datetime import datetime

    if not isinstance(value, str) or not value.endswith("Z"):
        raise ContractError("contract_timestamp_invalid", field)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("contract_timestamp_invalid", field) from exc
    return value
