"""Check a lane's producer against the contract the integration target registers.

A lane branch can be green while the merge is red, because the lane still carries
an older contract. That happened twice on 2026-08-23: this lane emitted
`RegistryResolutionReceipt` 1.0.0 after core moved to 1.1.0, and the privacy lane
emitted a `PrivacyReceipt` that core's parser rejected. Both were visible before
the merge by running the producer against the target's registered schema.

This helper is deliberately lane-agnostic. It takes any zero-argument producer
that returns an artifact wire dict, plus the contract name and the version and
field set the target registers, and reports whether the target would accept it
and exactly which payload fields differ.

    from cross_contract import ContractExpectation, check_producer_against_contract

    result = check_producer_against_contract(
        lambda: build_my_receipt(...),
        "PrivacyReceipt",
        ContractExpectation("2.0.0", {"decision", "detectors", ...}),
    )
    assert result.ok, result.summary()

Read the expectation from the target branch rather than typing it from memory:

    git show <target-branch>:src/recall/contracts/schemas.py

Nothing here mutates the repository. The registered schema is swapped for the
duration of one call and restored afterwards, including on failure.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from recall.contracts.errors import ContractError
from recall.contracts.models import parse_artifact
from recall.contracts.schemas import SCHEMAS
from recall.ledger.producers import PRODUCER_REGISTRY

# The common envelope from ARTIFACT_CONTRACTS.md. Held here rather than imported
# from any one lane so every lane can use this helper without depending on
# another lane's module.
ENVELOPE_FIELDS = frozenset(
    {
        "schema_name",
        "schema_version",
        "artifact_id",
        "case_id",
        "run_id",
        "producer",
        "created_at",
        "input_artifact_ids",
        "content_hash",
        "data_mode",
        "status",
        "warnings",
        "extensions",
    }
)

ArtifactProducer = Callable[[], Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class ContractExpectation:
    """The version and payload field set a target branch registers."""

    version: str
    payload_fields: frozenset[str]
    run_required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload_fields", frozenset(self.payload_fields))


@dataclass(frozen=True, slots=True)
class CrossContractResult:
    """What the target contract would make of one produced artifact."""

    schema_name: str
    expected_version: str
    emitted_version: str | None
    accepted: bool
    error_code: str | None
    error_detail: str | None
    missing_fields: tuple[str, ...]
    unexpected_fields: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """True only when the target accepts it and no payload field differs."""

        return (
            self.accepted
            and not self.missing_fields
            and not self.unexpected_fields
            and self.emitted_version == self.expected_version
        )

    def summary(self) -> str:
        if self.ok:
            return (
                f"{self.schema_name} accepted at {self.expected_version} "
                "with an exact payload field match"
            )
        parts = [f"{self.schema_name} does not satisfy {self.expected_version}"]
        if self.emitted_version != self.expected_version:
            parts.append(f"emitted version {self.emitted_version}")
        if self.missing_fields:
            parts.append(f"missing {list(self.missing_fields)}")
        if self.unexpected_fields:
            parts.append(f"unexpected {list(self.unexpected_fields)}")
        if self.error_code:
            detail = f":{self.error_detail}" if self.error_detail else ""
            parts.append(f"parser rejected with {self.error_code}{detail}")
        return "; ".join(parts)


class _TargetPayload:
    """Stands in for the target lane's payload object, keeping only its fields."""

    def __init__(self, value: Mapping[str, Any], fields: Collection[str]) -> None:
        self._fields = {key: value[key] for key in fields if key in value}

    def to_wire(self) -> dict[str, Any]:
        return dict(self._fields)


def local_contract(schema_name: str) -> ContractExpectation:
    """Read the expectation this checkout currently registers."""

    version, fields, _parser, run_required = SCHEMAS[schema_name]
    return ContractExpectation(version, frozenset(fields), run_required)


@contextmanager
def registered_as(
    schema_name: str, expectation: ContractExpectation
) -> Iterator[None]:
    """Register the target's contract for the duration of the block."""

    had_entry = schema_name in SCHEMAS
    previous = SCHEMAS.get(schema_name)

    def _parser(value: Mapping[str, Any]) -> _TargetPayload:
        return _TargetPayload(value, expectation.payload_fields)

    SCHEMAS[schema_name] = (
        expectation.version,
        expectation.payload_fields,
        _parser,
        expectation.run_required,
    )
    try:
        yield
    finally:
        if had_entry:
            SCHEMAS[schema_name] = previous  # type: ignore[assignment]
        else:
            SCHEMAS.pop(schema_name, None)


def payload_fields_of(wire: Mapping[str, Any]) -> frozenset[str]:
    """The payload portion of a wire dict, with the common envelope removed."""

    return frozenset(set(wire) - ENVELOPE_FIELDS)


def check_producer_against_contract(
    producer: ArtifactProducer,
    schema_name: str,
    expectation: ContractExpectation,
    *,
    authorized_producers: Mapping[str, Collection[str]] = PRODUCER_REGISTRY,
) -> CrossContractResult:
    """Run `producer` against `expectation` and report what the target would do.

    The producer is called inside the swapped registration, so a producer that
    reads its version from the registry emits the target's version and is checked
    as it would behave after the merge.
    """

    emitted: Mapping[str, Any] | None = None
    accepted = False
    error_code: str | None = None
    error_detail: str | None = None

    with registered_as(schema_name, expectation):
        try:
            emitted = producer()
            parse_artifact(emitted, authorized_producers=authorized_producers)
            accepted = True
        except ContractError as exc:
            error_code, error_detail = exc.code, exc.detail
        except Exception as exc:  # noqa: BLE001 - any failure is a finding
            error_code = type(exc).__name__
            error_detail = str(exc)[:200]

    produced = payload_fields_of(emitted) if emitted is not None else frozenset()
    emitted_version = (
        str(emitted.get("schema_version")) if emitted is not None else None
    )
    return CrossContractResult(
        schema_name=schema_name,
        expected_version=expectation.version,
        emitted_version=emitted_version,
        accepted=accepted,
        error_code=error_code,
        error_detail=error_detail,
        missing_fields=tuple(sorted(expectation.payload_fields - produced)),
        unexpected_fields=tuple(sorted(produced - expectation.payload_fields)),
    )


def check_against_versions(
    producer: ArtifactProducer,
    schema_name: str,
    expectations: Iterable[ContractExpectation],
    *,
    authorized_producers: Mapping[str, Collection[str]] = PRODUCER_REGISTRY,
) -> list[CrossContractResult]:
    """Check one producer against several contract versions in one call."""

    return [
        check_producer_against_contract(
            producer,
            schema_name,
            expectation,
            authorized_producers=authorized_producers,
        )
        for expectation in expectations
    ]
