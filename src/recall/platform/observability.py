"""Managed-path health aggregation and Cloud Trace correlation.

`ManagedPathReceipt` is declared in `docs/contracts/ARTIFACT_CONTRACTS.md` but is
not registered in `recall.contracts.schemas`, so it is emitted through
`build_platform_receipt` with the same envelope and canonical hash the registered
parser will later produce.

Aggregation never defaults to healthy. A component nobody observed is
`UNAVAILABLE`, a component that answered with a failure is `DEGRADED`, and only a
fully observed path is `MANAGED`. A receipt claiming `MANAGED` must carry the
trace id that proves the path was exercised.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from recall.contracts.enums import ArtifactStatus, DataMode

from .config import PlatformConfig
from .errors import PlatformError
from .receipts import build_platform_receipt

logger = logging.getLogger(__name__)

MANAGED_PATH_RECEIPT_FIELDS = frozenset(
    {"managed_status", "component_statuses", "reason_codes", "trace_id"}
)
MANAGED_PATH_RECEIPT_VERSION = "1.0.0"
TRACEPARENT_VERSION = "00"
SAMPLED_FLAGS = "01"


class ComponentState(StrEnum):
    OBSERVED = "OBSERVED"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class ManagedStatus(StrEnum):
    MANAGED = "MANAGED"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class ComponentStatus:
    component: str
    state: ComponentState
    reason_code: str | None

    def to_wire(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "state": self.state.value,
            "reason_code": self.reason_code,
        }


def aggregate_managed_status(
    statuses: Sequence[ComponentStatus],
) -> tuple[ManagedStatus, tuple[str, ...]]:
    """Fold component states into one managed status and its reason codes."""

    if not statuses:
        return ManagedStatus.UNAVAILABLE, ("managed_path_no_component_observed",)
    reasons = {
        status.reason_code for status in statuses if status.reason_code
    }
    states = {status.state for status in statuses}
    if ComponentState.UNAVAILABLE in states:
        reasons.add("managed_path_component_unavailable")
        return ManagedStatus.UNAVAILABLE, tuple(sorted(reasons))
    if ComponentState.DEGRADED in states:
        reasons.add("managed_path_component_degraded")
        return ManagedStatus.DEGRADED, tuple(sorted(reasons))
    return ManagedStatus.MANAGED, tuple(sorted(reasons))


def new_trace_id() -> str:
    """Generate a 32 hex character W3C trace id."""

    return secrets.token_hex(16)


def new_span_id() -> str:
    return secrets.token_hex(8)


def traceparent(trace_id: str, span_id: str) -> str:
    """Render the W3C header the Controller sends to the managed runtime."""

    if len(trace_id) != 32 or not all(c in "0123456789abcdef" for c in trace_id):
        raise PlatformError("trace_id_invalid", trace_id)
    if len(span_id) != 16 or not all(c in "0123456789abcdef" for c in span_id):
        raise PlatformError("span_id_invalid", span_id)
    return f"{TRACEPARENT_VERSION}-{trace_id}-{span_id}-{SAMPLED_FLAGS}"


def parse_traceparent(header: str) -> tuple[str, str]:
    """Read a traceparent back, so propagation can be asserted rather than assumed."""

    parts = header.split("-")
    if len(parts) != 4 or parts[0] != TRACEPARENT_VERSION:
        raise PlatformError("traceparent_malformed", header)
    trace_id, span_id = parts[1], parts[2]
    traceparent(trace_id, span_id)
    return trace_id, span_id


class TraceClient(Protocol):
    """Cloud Trace read surface used to confirm a trace actually landed."""

    def get_trace(self, trace_id: str) -> Mapping[str, Any]: ...


def read_back_trace(client: TraceClient, trace_id: str) -> dict[str, Any]:
    """Confirm a trace exists and report its spans.

    A trace that cannot be fetched is `UNAVAILABLE`; a trace with no spans is
    `DEGRADED`. Neither is treated as a working managed path.
    """

    try:
        payload = client.get_trace(trace_id)
    except PlatformError as exc:
        return {
            "trace_id": trace_id,
            "state": ComponentState.UNAVAILABLE.value,
            "reason_code": exc.code,
            "span_count": 0,
        }
    spans = payload.get("spans")
    listed = spans if isinstance(spans, list) else []
    return {
        "trace_id": trace_id,
        "state": (
            ComponentState.OBSERVED.value if listed else ComponentState.DEGRADED.value
        ),
        "reason_code": None if listed else "trace_has_no_spans",
        "span_count": len(listed),
        "span_names": sorted(
            str(span.get("name", "")) for span in listed if isinstance(span, Mapping)
        ),
    }


def managed_path_receipt(
    *,
    artifact_id: str,
    producer_version: str,
    created_at: str,
    statuses: Sequence[ComponentStatus],
    trace_id: str | None,
    data_mode: DataMode = DataMode.SYNTHETIC,
) -> dict[str, Any]:
    """Emit a `ManagedPathReceipt` wire dict from observed component states."""

    managed_status, reason_codes = aggregate_managed_status(statuses)
    if managed_status is ManagedStatus.MANAGED and not trace_id:
        raise PlatformError("managed_path_trace_missing")
    status = (
        ArtifactStatus.VALID
        if managed_status is ManagedStatus.MANAGED
        else ArtifactStatus.DEGRADED
    )
    ordered = sorted(statuses, key=lambda item: item.component)
    return build_platform_receipt(
        schema_name="ManagedPathReceipt",
        schema_version=MANAGED_PATH_RECEIPT_VERSION,
        payload_fields=MANAGED_PATH_RECEIPT_FIELDS,
        artifact_id=artifact_id,
        case_id=None,
        run_id=None,
        producer={
            "component": "Deterministic health aggregator",
            "version": producer_version,
            "identity": "health-aggregator",
        },
        created_at=created_at,
        input_artifact_ids=(),
        data_mode=data_mode,
        status=status,
        payload={
            "managed_status": managed_status.value,
            "component_statuses": [item.to_wire() for item in ordered],
            "reason_codes": list(reason_codes),
            "trace_id": trace_id,
        },
    )


class RestTraceClient:
    """Cloud Trace v1 client over REST with application default credentials."""

    BASE = "https://cloudtrace.googleapis.com/v1"

    def __init__(self, config: PlatformConfig) -> None:
        self._project = config.project_id
        self._session = self._authorised_session()

    @staticmethod
    def _authorised_session() -> Any:
        try:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise PlatformError("trace_sdk_unavailable", str(exc)) from exc
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return AuthorizedSession(credentials)

    def get_trace(self, trace_id: str) -> Mapping[str, Any]:
        url = f"{self.BASE}/projects/{self._project}/traces/{trace_id}"
        response = self._session.get(url, timeout=30)
        if response.status_code != 200:
            raise PlatformError("trace_fetch_failed", f"{trace_id}:{response.status_code}")
        return response.json()

    # There is deliberately no list or search method here. Cloud Trace v1
    # projects.traces.list returned zero results for a trace that
    # projects.traces.get returned immediately and correctly, so searching is
    # not a usable way to find a trace. The caller mints the trace id, so it
    # always knows which id to fetch.


@dataclass(frozen=True, slots=True)
class SpanRecord:
    """One span the Controller records for a step it orchestrated."""

    span_id: str
    display_name: str
    start_time: str
    end_time: str
    parent_span_id: str | None = None
    attributes: Mapping[str, str] = field(default_factory=dict)

    def to_wire(self, project_id: str, trace_id: str) -> dict[str, Any]:
        wire: dict[str, Any] = {
            "name": f"projects/{project_id}/traces/{trace_id}/spans/{self.span_id}",
            "spanId": self.span_id,
            "displayName": {"value": self.display_name},
            "startTime": self.start_time,
            "endTime": self.end_time,
        }
        if self.parent_span_id:
            wire["parentSpanId"] = self.parent_span_id
        if self.attributes:
            wire["attributes"] = {
                "attributeMap": {
                    key: {"stringValue": {"value": str(value)}}
                    for key, value in sorted(self.attributes.items())
                }
            }
        return wire


class TraceWriter(Protocol):
    def batch_write(self, spans: Sequence[Mapping[str, Any]]) -> None: ...


class TraceRecorder:
    """Record the Controller's own view of a fleet run under one trace id.

    The managed runtime terminates the caller's request at the API frontend and
    makes its own internal call, so a `traceparent` sent to `:streamQuery` does
    not reach the agent container and agent-internal spans cannot join the
    caller's trace. What the Controller orchestrates, it can record itself: one
    span per agent call, all under a trace id it minted, written with
    `traces:batchWrite` and read back with `traces.get`.

    Attributes carry role, region and outcome. They never carry prompt or
    response text.
    """

    def __init__(self, project_id: str, trace_id: str | None = None) -> None:
        if not project_id:
            raise PlatformError("trace_project_missing")
        self._project_id = project_id
        self.trace_id = trace_id or new_trace_id()
        if len(self.trace_id) != 32:
            raise PlatformError("trace_id_invalid", self.trace_id)
        self._spans: list[SpanRecord] = []

    @property
    def spans(self) -> tuple[SpanRecord, ...]:
        return tuple(self._spans)

    def record(
        self,
        display_name: str,
        *,
        start: datetime,
        end: datetime,
        parent_span_id: str | None = None,
        attributes: Mapping[str, str] | None = None,
        span_id: str | None = None,
    ) -> SpanRecord:
        if end < start:
            raise PlatformError("span_time_inverted", display_name)
        record = SpanRecord(
            span_id=span_id or new_span_id(),
            display_name=display_name,
            start_time=_span_timestamp(start),
            end_time=_span_timestamp(end),
            parent_span_id=parent_span_id,
            attributes=dict(attributes or {}),
        )
        self._spans.append(record)
        return record

    def flush(self, writer: TraceWriter) -> int:
        """Write the recorded spans. Returns how many were written."""

        if not self._spans:
            raise PlatformError("trace_no_spans_recorded", self.trace_id)
        writer.batch_write(
            [span.to_wire(self._project_id, self.trace_id) for span in self._spans]
        )
        return len(self._spans)


def _span_timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


class RestTraceWriter:
    """Cloud Trace v2 span writer with application default credentials."""

    BASE = "https://cloudtrace.googleapis.com/v2"

    def __init__(self, config: PlatformConfig) -> None:
        self._project = config.project_id
        self._session = RestTraceClient._authorised_session()

    def batch_write(self, spans: Sequence[Mapping[str, Any]]) -> None:
        url = f"{self.BASE}/projects/{self._project}/traces:batchWrite"
        response = self._session.post(url, json={"spans": list(spans)}, timeout=30)
        if response.status_code != 200:
            raise PlatformError("trace_write_failed", str(response.status_code))
