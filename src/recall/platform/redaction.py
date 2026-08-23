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

PROJECT_PLACEHOLDER = "<project>"
PROJECT_PATH = re.compile(r"projects/[^/\"'\s,}\]]+")
PROJECT_NUMBER_URN = re.compile(r"projects-[0-9]+")
BARE_PROJECT_NUMBER = re.compile(r"(?<![0-9])[0-9]{10,14}(?![0-9])")


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
