"""The preregistered surface-placement rule, and the cap that must not shrink.

`corpus/PREREGISTRATION.md` fixes the arm B ambiguity rule before any
measurement runs. A rule that only exists in prose can drift; these tests hold
it to what was declared.
"""

from __future__ import annotations

from recall.privacy.gemma import (
    MAX_PROPOSALS,
    OLLAMA_DEFAULT_OPTIONS,
    SURFACE_NOT_FOUND,
    GemmaProposal,
    all_occurrences,
    locate_surfaces,
)

NOTE = "Ad: Duygu Turan, es: Duygu Turan, tel: 0555 274 41 85"


def proposal(surface: str, identifier_class: str = "PERSON_NAME") -> GemmaProposal:
    """A proposal whose offsets are deliberately wrong, as the model's are."""

    return GemmaProposal(start=0, end=0, identifier_class=identifier_class, surface=surface)


def test_one_occurrence_places_the_span_there() -> None:
    located, reasons = locate_surfaces(NOTE, [proposal("0555 274 41 85", "PHONE")])
    assert reasons == ()
    assert len(located) == 1
    assert NOTE[located[0].start : located[0].end] == "0555 274 41 85"


def test_several_occurrences_each_become_their_own_proposal() -> None:
    located, reasons = locate_surfaces(NOTE, [proposal("Duygu Turan")])
    assert reasons == ()
    assert len(located) == 2
    assert [NOTE[span.start : span.end] for span in located] == ["Duygu Turan", "Duygu Turan"]
    assert located[0].start != located[1].start
    assert all(span.identifier_class == "PERSON_NAME" for span in located)


def test_a_surface_that_is_not_in_the_note_is_refused() -> None:
    located, reasons = locate_surfaces(NOTE, [proposal("Ahmet Yilmaz")])
    assert located == ()
    assert reasons == (SURFACE_NOT_FOUND,)


def test_one_refusal_does_not_discard_the_other_proposals() -> None:
    located, reasons = locate_surfaces(
        NOTE, [proposal("Ahmet Yilmaz"), proposal("0555 274 41 85", "PHONE")]
    )
    assert reasons == (SURFACE_NOT_FOUND,)
    assert len(located) == 1
    assert NOTE[located[0].start : located[0].end] == "0555 274 41 85"


def test_placement_keeps_the_class_and_ignores_the_model_offsets() -> None:
    located, _ = locate_surfaces(NOTE, [proposal("0555 274 41 85", "PHONE")])
    span = located[0]
    assert span.identifier_class == "PHONE"
    assert (span.start, span.end) != (0, 0)


def test_overlapping_occurrences_are_all_reported() -> None:
    assert all_occurrences("aaaa", "aaa") == (0, 1)


def test_an_empty_surface_is_never_placed() -> None:
    assert all_occurrences(NOTE, "") == ()


def test_the_proposal_cap_sits_above_the_corpus_span_count(dev_records) -> None:
    """The cap is a denial-of-service bound, never a recall bound.

    An earlier cap of 8 sat below the corpus floor of 10 spans per note, so no
    complete response could be accepted and the measurement described the cap
    rather than the model. This is the regression lock for that defect.
    """

    per_note = [len(record["spans"]) for record in dev_records]
    assert MAX_PROPOSALS > max(per_note), (
        f"cap {MAX_PROPOSALS} is not above the corpus maximum of {max(per_note)} spans per note"
    )


def test_the_prompt_states_no_numeric_span_limit() -> None:
    """Telling the model a number constrains recall by construction."""

    from recall.privacy.gemma import SYSTEM_INSTRUCTION

    assert str(MAX_PROPOSALS) not in SYSTEM_INSTRUCTION
    assert "at most" not in SYSTEM_INSTRUCTION
    assert "every identifier" in SYSTEM_INSTRUCTION


def test_the_completion_budget_default_stays_above_the_corpus_floor() -> None:
    """A 15-span note needs 578 completion tokens; 512 truncated every one.

    The correction lived only in a command-line argument, so a forgotten flag
    would have restored the defect silently. This holds the code default, which
    is what a run inherits when nobody passes the flag.
    """

    assert OLLAMA_DEFAULT_OPTIONS["num_predict"] == 1024
