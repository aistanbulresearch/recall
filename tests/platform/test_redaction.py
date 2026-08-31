from __future__ import annotations

import pytest

from recall.platform.redaction import contains_project_identifier, redact_identifiers

PROJECT_ID = "recall-example-0c3c6ed0"
PROJECT_NUMBER = "123456789012"  # synthetic: never a real project number
ENGINE = "1111222233334444"


def test_resource_path_project_id_is_masked() -> None:
    text = f"projects/{PROJECT_ID}/locations/us-central1/reasoningEngines/{ENGINE}"
    masked = redact_identifiers(text, PROJECT_ID)
    assert PROJECT_ID not in masked
    assert masked.startswith("projects/<project>/locations/us-central1")


def test_registry_urn_project_number_is_masked() -> None:
    # This is the form that leaked before redaction was centralised.
    urn = (
        f"urn:agent:projects-{PROJECT_NUMBER}:projects:{PROJECT_NUMBER}"
        f":locations:us-central1:aiplatform:reasoningEngines:{ENGINE}"
    )
    masked = redact_identifiers(urn, PROJECT_ID)
    assert PROJECT_NUMBER not in masked
    assert "projects-<project>" in masked


def test_bare_project_number_is_masked() -> None:
    masked = redact_identifiers(f"principal number {PROJECT_NUMBER} here", PROJECT_ID)
    assert PROJECT_NUMBER not in masked
    assert "<project-number>" in masked


def test_service_account_address_is_masked() -> None:
    text = f"sa://recall-sa-watcher@{PROJECT_ID}.iam.gserviceaccount.com"
    assert PROJECT_ID not in redact_identifiers(text, PROJECT_ID)


def test_masking_works_without_a_known_project_id() -> None:
    text = f"projects/{PROJECT_ID}/locations/us-central1"
    masked = redact_identifiers(text)
    assert PROJECT_ID not in masked


def test_short_numbers_are_left_alone() -> None:
    text = "revision 2026-08-22 with count 12345 and region us-central1"
    assert redact_identifiers(text, PROJECT_ID) == text


def test_detector_finds_an_unmasked_identifier() -> None:
    assert contains_project_identifier(f"projects/{PROJECT_ID}/x", PROJECT_ID) is True
    assert contains_project_identifier(f"projects-{PROJECT_NUMBER}") is True
    assert contains_project_identifier(PROJECT_NUMBER) is True


def test_detector_accepts_fully_masked_text() -> None:
    urn = (
        f"urn:agent:projects-{PROJECT_NUMBER}:locations:us-central1"
        f":reasoningEngines:{ENGINE}"
    )
    masked = redact_identifiers(
        f"projects/{PROJECT_ID}/locations/us-central1 {urn}", PROJECT_ID
    )
    assert contains_project_identifier(masked, PROJECT_ID) is False


# --- a redacted artifact that cannot be parsed is not a redacted artifact -----
#
# redact_identifiers works on serialised text. Applied to a JSON document it
# rewrote a Unix timestamp inside a float literal on 2026-08-25:
#     "timestamp": 1787610123.44  ->  "timestamp": <project-number>.44
# The evidence file stopped parsing. No committed artifact was affected -- all
# twelve were checked -- but every future --redact JSON run would have been.


def test_text_redaction_breaks_json_and_object_redaction_does_not() -> None:
    import json

    from recall.platform.redaction import redact_json

    doc = {
        "timestamp": 1787610123.44,
        "resource": "projects/807520717526/locations/us-central1",
        "nested": [{"ts": 1787610999}],
    }

    with pytest.raises(json.JSONDecodeError):
        json.loads(redact_identifiers(json.dumps(doc), "recall-example"))

    redacted = json.loads(json.dumps(redact_json(doc, "recall-example")))
    assert redacted["timestamp"] == 1787610123.44, "numbers are never touched"
    assert redacted["nested"][0]["ts"] == 1787610999
    assert "807520717526" not in json.dumps(redacted), "the project is still masked"
    assert redacted["resource"] == "projects/<project>/locations/us-central1"


def test_object_redaction_masks_keys_as_well_as_values() -> None:
    from recall.platform.redaction import redact_json

    redacted = redact_json({"projects/807520717526": "value"}, None)
    assert list(redacted) == ["projects/<project>"]


# The bare-number net once fired INSIDE hex, because its lookarounds excluded
# adjacent digits but not adjacent letters. It spliced <project-number> into an
# image digest and a commit sha -- corrupting the two values a person reads while
# diagnosing a failed deploy, at the one moment they cannot afford a corrupted
# value. Both directions are pinned below: the net must stay off hex, and it must
# still cover every boundary a real project number actually appears at.


def test_digit_run_inside_hex_is_not_masked() -> None:
    """A commit sha and an image digest survive intact."""

    digest = "sha256:6e4d71281349717e08e2388667589137027941adb344d6f40bbc8f7b52b905f9"
    commit = "5bc1c7a2f89731cd4d80827579311cb923dd77a3"
    masked = redact_identifiers(f"{digest} built from {commit}", PROJECT_ID)
    assert digest in masked, "image digest was corrupted by the bare-number net"
    assert commit in masked, "commit sha was corrupted by the bare-number net"
    assert "<project-number>" not in masked


@pytest.mark.parametrize(
    "template",
    [
        "namespace: {n}",
        'namespace: "{n}"',
        "projects/{n}/locations/us-central1",
        "serviceAccount:{n}",
        "{n}-compute@developer.gserviceaccount.com",
        "sa-{n}@example.iam.gserviceaccount.com",
        "value,{n},next",
        "{{'number': {n}}}",
    ],
)
def test_bare_project_number_still_masked_at_every_real_boundary(template: str) -> None:
    """Tightening the lookarounds must not lose coverage where numbers really appear."""

    masked = redact_identifiers(template.format(n=PROJECT_NUMBER), PROJECT_ID)
    assert PROJECT_NUMBER not in masked, f"project number leaked from: {template}"
