"""
tests/test_translation_units.py
================================
Unit tests for ``split_text_into_translation_units`` in ``backend/ai_logic``.

These tests cover:
- Abbreviations (``Dr.``, ``e.g.``, ``U.S.``) kept together with the next word
- Single-letter initials kept together (``J. R.``)
- Real sentence boundaries still split (``1994. That``)
- ``!`` and ``?`` still terminate sentences
"""

from __future__ import annotations

from backend.ai_logic import split_text_into_translation_units


def test_abbreviation_keeps_sentence_together():
    assert split_text_into_translation_units("Dr. Smith went home. Then he slept.") == [
        "Dr. Smith went home.",
        "Then he slept.",
    ]


def test_dotted_acronym_not_split():
    assert split_text_into_translation_units("The U.S. Army won. Really.") == [
        "The U.S. Army won.",
        "Really.",
    ]


def test_eg_kept_with_next_word():
    units = split_text_into_translation_units("Please send it e.g. tomorrow.")
    assert units == ["Please send it e.g. tomorrow."]


def test_fig_reference_not_split():
    units = split_text_into_translation_units("See fig. 3 and fig. 4 at 5p.m.")
    assert units == ["See fig. 3 and fig. 4 at 5p.m."]


def test_numbered_sentence_still_splits():
    assert split_text_into_translation_units("In 1994. That was the year.") == [
        "In 1994.",
        "That was the year.",
    ]


def test_single_letter_initials_kept_together():
    units = split_text_into_translation_units("J. R. Trailing ends now. Next part.")
    assert units == [
        "J. R. Trailing ends now.",
        "Next part.",
    ]


def test_exclamation_and_question_marks_still_split():
    assert split_text_into_translation_units("Hello world? Yes! Bye.") == [
        "Hello world?",
        "Yes!",
        "Bye.",
    ]
