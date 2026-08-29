"""Mask project identifiers before lane output reaches a report.

Google Cloud exposes the project under two identifiers, and both must be masked:

- the project id, in `projects/<id>/locations/...` resource names;
- the project number, in Agent Registry URNs such as
  `urn:agent:projects-<number>:projects:<number>:locations:...`.

Masking only the first form leaks the second, which is what happened before this
module existed. Scripts share one implementation so a new output path cannot
quietly reintroduce the gap.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

PROJECT_PLACEHOLDER = "<project>"
PROJECT_PATH = re.compile(r"projects/[^/\"'\s,}\]]+")
PROJECT_NUMBER_URN = re.compile(r"projects-[0-9]+")
# The lookarounds exclude adjacent LETTERS as well as digits. Excluding only
# digits let the net fire inside hex: an image digest or a commit sha contains
# long digit runs bounded by hex letters, and masking one corrupts the value at
# exactly the moment somebody is reading it to diagnose a failed deploy. A real
# project number is always a standalone token -- bounded by / " ' : , @ - or
# whitespace -- so an alphanumeric-free boundary loses no coverage. projects/<n>
# and projects-<n> have their own patterns above and do not depend on this one.
BARE_PROJECT_NUMBER = re.compile(r"(?<![0-9A-Za-z])[0-9]{10,14}(?![0-9A-Za-z])")


def redact_identifiers(text: str, project_id: str | None = None) -> str:
    """Replace every project identifier in `text` with a placeholder."""

    masked = PROJECT_PATH.sub(f"projects/{PROJECT_PLACEHOLDER}", text)
    masked = PROJECT_NUMBER_URN.sub(f"projects-{PROJECT_PLACEHOLDER}", masked)
    masked = BARE_PROJECT_NUMBER.sub("<project-number>", masked)
    if project_id:
        masked = masked.replace(project_id, PROJECT_PLACEHOLDER)
    return masked


def contains_project_identifier(text: str, project_id: str | None = None) -> bool:
    """Report whether any unmasked project identifier remains."""

    if project_id and project_id in text:
        return True
    return bool(
        PROJECT_PATH.search(text.replace(f"projects/{PROJECT_PLACEHOLDER}", ""))
        or PROJECT_NUMBER_URN.search(text)
        or BARE_PROJECT_NUMBER.search(text)
    )


def redact_json(value: Any, project_id: str | None = None) -> Any:
    """Redact a JSON-able structure by masking STRING VALUES only.

    redact_identifiers works on serialised text, which is correct for logs and
    wrong for JSON documents: on 2026-08-25 it rewrote a Unix timestamp inside a
    float literal --

        "timestamp": 1787610123.44   ->   "timestamp": <project-number>.44

    -- producing an evidence file that would not parse. A redacted artifact that
    cannot be read is not a redacted artifact.

    Numbers, booleans and nulls are never touched here, because a project
    identifier is a string and a ten-digit number is far more often a timestamp.
    Keys are masked as well as values: an identifier is no safer for appearing
    on the left of a colon.
    """

    if isinstance(value, str):
        return redact_identifiers(value, project_id)
    if isinstance(value, Mapping):
        return {
            redact_identifiers(str(key), project_id): redact_json(item, project_id)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_json(item, project_id) for item in value]
    return value
