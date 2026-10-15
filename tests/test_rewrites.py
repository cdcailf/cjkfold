"""The two explicit writes: ``normalize()`` and ``strip_invisible()``.

Neither of them calls ``fold()``, and ``fold()`` does not call them. Deciding to
rewrite text is a decision, and these tests are here to keep each decision where
the caller put it. Escapes rather than literal characters, as everywhere else.
"""

from __future__ import annotations

import pytest

from cjkfold import fold, normalize, strip_invisible

ZWSP = "\u200b"  # ZERO WIDTH SPACE
ZWJ = "\u200d"  # ZERO WIDTH JOINER
BOM = "\ufeff"  # ZERO WIDTH NO-BREAK SPACE
SOFT_HYPHEN = "\u00ad"  # SOFT HYPHEN
WORD_JOINER = "\u2060"  # WORD JOINER
FAMILY = "\U0001f468\u200d\U0001f469\u200d\U0001f467"  # 一家三口
FULLWIDTH_A = "\uff21"  # Ａ -> A
FULLWIDTH_COMMA = "\uff0c"  # ， -> ,
IDEOGRAPHIC_SPACE = "\u3000"  # -> " "
KANGXI_COLOR = "\u2f8a"  # ⾊ KANGXI RADICAL COLOR -- NFKC repairs this block
RADICAL_HORN = "\u2ec6"  # ⻆ CJK RADICAL SIMPLIFIED HORN -- NFKC does not
SHU = "\u6570"  # 数
JU = "\u636e"  # 据


def test_fullwidth_letters_are_rewritten_to_ascii():
    assert normalize(FULLWIDTH_A) == "A"


def test_an_ideographic_space_becomes_an_ordinary_space():
    assert normalize("a" + IDEOGRAPHIC_SPACE + "b") == "a b"


def test_punctuation_is_protected_by_default():
    """Why keep_punctuation exists: NFKC would empty a Chinese sentence of its commas."""
    text = "\u554a" + FULLWIDTH_COMMA + "\u554a"  # 啊，啊

    assert normalize(text) == text
    assert normalize(text, keep_punctuation=False) == "\u554a,\u554a"


def test_a_kangxi_radical_is_repaired_by_nfkc_too():
    """NFKC handles the Kangxi block completely, so normalize() gets those for free."""
    assert normalize(KANGXI_COLOR) == "\u8272"


def test_the_radical_supplement_is_fold_only():
    """The block NFKC cannot repair stays where it belongs: with fold()."""
    assert normalize(RADICAL_HORN) == RADICAL_HORN
    assert fold(RADICAL_HORN) == "\u89d2"


def test_normalize_returns_the_same_object_when_there_is_nothing_to_do():
    text = SHU + JU
    assert normalize(text) is text


def test_normalize_is_idempotent():
    once = normalize(FULLWIDTH_A + FULLWIDTH_COMMA + IDEOGRAPHIC_SPACE)
    assert normalize(once) == once


def test_normalize_accepts_an_empty_string():
    assert normalize("") == ""


@pytest.mark.parametrize("char", [ZWSP, BOM, SOFT_HYPHEN, WORD_JOINER])
def test_safe_policy_removes_the_harmless_ones(char):
    assert strip_invisible(SHU + char + JU) == SHU + JU


def test_safe_policy_leaves_the_family_together():
    """The default must not turn one family into three people."""
    assert strip_invisible(FAMILY) == FAMILY
    assert len(strip_invisible(FAMILY)) == 5


def test_all_policy_is_exactly_what_its_name_warns_about():
    stripped = strip_invisible(FAMILY, policy="all")

    assert stripped != FAMILY
    assert len(stripped) == 3


def test_strip_invisible_returns_the_same_object_when_there_is_nothing_to_do():
    text = SHU + JU
    assert strip_invisible(text) is text
    assert strip_invisible("") == ""


def test_an_unknown_policy_is_refused_rather_than_guessed():
    """There is no option called "smart", because no such thing exists."""
    with pytest.raises(ValueError, match="policy"):
        strip_invisible(SHU, policy="smart")


def test_fold_did_not_grow_the_other_two_operations():
    """fold() stays a glyph fold: no NFKC, no invisible handling, unchanged."""
    text = FULLWIDTH_COMMA + ZWSP + KANGXI_COLOR

    assert fold(text) == FULLWIDTH_COMMA + ZWSP + "\u8272"
