"""The behaviour that motivates the whole library."""

from __future__ import annotations

import unicodedata

import pytest

from cjkfold import fold, has_lookalikes, iter_lookalikes, kind_of

# Look-alikes are written as escapes on purpose: a character typed literally
# into a source file is exactly the hazard this library exists for, and an
# editor, formatter or copy-paste can silently replace it with the common
# character without anyone noticing.  Escapes cannot be "corrected".
KANGXI_ONE = "\u2f00"  # ⼀ KANGXI RADICAL ONE            looks like 一 U+4E00
KANGXI_TWO = "\u2f06"  # ⼆ KANGXI RADICAL TWO
KANGXI_MAN = "\u2f08"  # ⼈ KANGXI RADICAL MAN
KANGXI_COLOR = "\u2f8a"  # ⾊ KANGXI RADICAL COLOR         looks like 色
RADICAL_CLIFF = "\u2e81"  # ⺁ CJK RADICAL CLIFF            looks like 厂
RADICAL_HORN = "\u2ec6"  # ⻆ CJK RADICAL SIMPLIFIED HORN  looks like 角
RADICAL_BAMBOO = "\u2eae"  # ⺮ CJK RADICAL BAMBOO         folds to U+25AD7


def test_the_bug_this_library_exists_for():
    """Text that reads as 角 does not compare equal to 角, and NFKC won't fix it."""
    extracted = f"\u5899{RADICAL_HORN}\u8fb9\u7684\u4e66"  # 墙⻆边的书

    assert "\u89d2" not in extracted  # no real 角 anywhere in it
    # NFKC does not repair this block.
    assert unicodedata.normalize("NFKC", extracted) == extracted
    # Folding does.
    assert "\u89d2" in fold(extracted)


def test_kangxi_radicals_are_folded():
    assert fold(KANGXI_ONE + KANGXI_TWO + KANGXI_MAN) == "\u4e00\u4e8c\u4eba"


def test_radical_supplement_is_folded():
    assert fold(RADICAL_CLIFF + RADICAL_HORN) == "\u5382\u89d2"


def test_mixed_text_folds_only_the_lookalikes():
    text = f"\u7d2b{KANGXI_COLOR}\u7684{RADICAL_HORN}\u843d"  # 紫⾊的⻆落
    assert fold(text) == "\u7d2b\u8272\u7684\u89d2\u843d"


def test_targets_above_the_bmp_round_trip():
    """Bamboo folds to U+25AD7, outside the BMP -- one character, not two."""
    folded = fold(RADICAL_BAMBOO)
    assert len(folded) == 1
    assert ord(folded) == 0x25AD7


def test_fold_leaves_ordinary_text_alone():
    text = "\u8fd9\u662f\u4e00\u6bb5\u666e\u901a\u7684\u4e2d\u6587\u6587\u672c\uff0c\u542b\u6807\u70b9\u3002"
    assert fold(text) == text
    assert fold(text) is text  # fast path returns the same object


@pytest.mark.parametrize("punct", ["\uff0c", "\uff1b", "\uff08", "\uff09"])
def test_does_not_rewrite_fullwidth_punctuation(punct):
    """fold() is a glyph fold, not a full NFKC pass -- punctuation must survive."""
    assert fold(punct) == punct
    assert unicodedata.normalize("NFKC", punct) != punct  # NFKC would rewrite these


@pytest.mark.parametrize("text", ["", "hello", "abc 123", "\u0647\u0630\u0627 \u0646\u0635"])
def test_non_cjk_input_is_untouched(text):
    assert fold(text) == text


def test_fold_is_idempotent():
    once = fold(RADICAL_CLIFF + RADICAL_HORN + KANGXI_ONE)
    assert fold(once) == once


def test_fold_accepts_empty_and_returns_it():
    assert fold("") == ""


def test_has_lookalikes():
    assert has_lookalikes(RADICAL_HORN)
    assert not has_lookalikes("\u89d2")
    assert has_lookalikes("\u666e\u901a\u6587\u672c" + RADICAL_CLIFF + "\u666e\u901a\u6587\u672c")


def test_iter_lookalikes_reports_position_and_replacement():
    text = f"\u7b2c\u4e00\u884c\n\u7b2c{KANGXI_TWO}\u884c{RADICAL_HORN}"  # 第一行\n第⼆行⻆
    found = list(iter_lookalikes(text))

    assert len(found) == 2
    first, second = found

    assert first.char == KANGXI_TWO
    assert first.codepoint == 0x2F06
    assert first.replacement == "\u4e8c"
    assert (first.line, first.column) == (2, 2)
    assert first.kind == "kangxi"

    assert second.char == RADICAL_HORN
    assert second.codepoint == 0x2EC6
    assert second.replacement == "\u89d2"
    assert (second.line, second.column) == (2, 4)
    assert second.kind == "radical-supplement"
    assert second.codepoint_label == "U+2EC6"
    assert second.replacement_label == "U+89D2"


def test_iter_lookalikes_on_clean_text():
    assert list(iter_lookalikes("\u5e72\u51c0\u6587\u672c")) == []


def test_index_is_a_character_offset():
    text = "ab" + RADICAL_HORN
    item = next(iter_lookalikes(text))
    assert text[item.index] == RADICAL_HORN


def test_kind_of():
    assert kind_of(0x2E81) == "radical-supplement"
    assert kind_of(0x2F00) == "kangxi"
    assert kind_of(0x4E00) == "other"
