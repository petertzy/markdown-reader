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


def test_closing_quote_stays_with_its_sentence():
    units = split_text_into_translation_units('He said "Stop." Then ran.')
    assert units == ['He said "Stop."', "Then ran."]


def test_closing_single_quote_stays_with_its_sentence():
    units = split_text_into_translation_units("She asked 'Why?' He answered.")
    assert units == ["She asked 'Why?'", "He answered."]


def test_exclamation_before_closing_quote_stays_with_sentence():
    units = split_text_into_translation_units('He yelled "Help!" She came.')
    assert units == ['He yelled "Help!"', "She came."]


def test_closing_bracket_absorbed_into_finished_sentence():
    # "(Stop.)" is a complete quoted unit; the closing bracket must not
    # be orphaned onto the next unit.
    units = split_text_into_translation_units("The guard called (Stop.) Then left.")
    assert units == ["The guard called (Stop.)", "Then left."]


def test_quoted_fragment_with_lowercase_follow_does_not_split():
    # "after" starts lowercase, so "quote." is not a real sentence end —
    # the quote must stay inline with the rest of the line.
    units = split_text_into_translation_units('Single "quote." after.')
    assert units == ['Single "quote." after.']


def test_chinese_sentences_split_without_spaces():
    # 。！？ are followed directly by the next character in CJK text, so the
    # "next char must be a space/quote/bracket" rule kept the whole paragraph as
    # one unit.
    assert split_text_into_translation_units(
        "今天天气很好。我们去公园吧。明天再说。"
    ) == [
        "今天天气很好。",
        "我们去公园吧。",
        "明天再说。",
    ]


def test_fullwidth_question_and_exclamation_split():
    assert split_text_into_translation_units("你去吗？我不知道！真的。") == [
        "你去吗？",
        "我不知道！",
        "真的。",
    ]


def test_japanese_sentences_split():
    assert split_text_into_translation_units("これは本です。それはペンです。") == [
        "これは本です。",
        "それはペンです。",
    ]


def test_cjk_closing_quote_stays_with_its_sentence():
    # 「停。」 is one unit; the closing bracket must not be orphaned onto the
    # next unit the way ASCII closing quotes are guarded against.
    assert split_text_into_translation_units("然后他说「停。」接着走了。") == [
        "然后他说「停。」",
        "接着走了。",
    ]


def test_cjk_closing_parenthesis_stays_with_its_sentence():
    assert split_text_into_translation_units("看这个（好。）然后呢？") == [
        "看这个（好。）",
        "然后呢？",
    ]


def test_mixed_cjk_and_ascii_text_splits():
    assert split_text_into_translation_units("Hello world. 你好。世界。") == [
        "Hello world. 你好。",
        "世界。",
    ]


def test_single_cjk_sentence_is_unchanged():
    assert split_text_into_translation_units("结束。") == ["结束。"]


def test_ascii_sentence_splitting_is_unchanged():
    # The full-width rule must not relax the ASCII rule. These are the exact
    # results on main before this change.
    assert split_text_into_translation_units("One. Two. Three.") == [
        "One.",
        "Two.",
        "Three.",
    ]
    assert split_text_into_translation_units("Version 1.2. Next") == [
        "Version 1.2.",
        "Next",
    ]
    assert split_text_into_translation_units("Dr. Smith went home. Then he slept.") == [
        "Dr. Smith went home.",
        "Then he slept.",
    ]
    assert split_text_into_translation_units('He said "Stop." Then ran.') == [
        'He said "Stop."',
        "Then ran.",
    ]
