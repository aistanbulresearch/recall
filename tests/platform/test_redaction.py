from __future__ import annotations

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
