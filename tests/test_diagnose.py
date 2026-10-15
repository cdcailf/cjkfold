"""The characters that break a comparison without ever showing up.

Same rule as tests/test_normalize.py: the interesting characters are written as
escapes.  A literal zero-width space in a source file is exactly the hazard this
library exists for, and nothing -- not a formatter, not a copy-paste -- can
silently "correct" an escape.
"""

from __future__ import annotations

import unicodedata

import pytest

from cjkfold import iter_lookalikes, scan, scan_stats

# Reaching into a private module is deliberate: the strip/manual split is an
# invariant of the whitelist itself, and testing it through scan() alone would
# only ever check the characters a test happened to name.
from cjkfold._classes import manual_codepoints, strip_codepoints

ZWSP = "\u200b"  # ZERO WIDTH SPACE            prints as nothing
ZWJ = "\u200d"  # ZERO WIDTH JOINER           holds emoji sequences together
ZWNJ = "\u200c"  # ZERO WIDTH NON-JOINER       decides whether letters join
WORD_JOINER = "\u2060"  # WORD JOINER          invisible, blocks a line break
LRM = "\u200e"  # LEFT-TO-RIGHT MARK          bidi mark
RLO = "\u202e"  # RIGHT-TO-LEFT OVERRIDE      bidi control (Trojan Source family)
VS16 = "\ufe0f"  # VARIATION SELECTOR-16      picks a glyph for the char before it
BOM = "\ufeff"  # ZERO WIDTH NO-BREAK SPACE   a byte order mark at file start
SOFT_HYPHEN = "\u00ad"  # SOFT HYPHEN         shows only where a line breaks
FULLWIDTH_A = "\uff21"  # FULLWIDTH LATIN CAPITAL LETTER A  -> A U+0041
FULLWIDTH_COMMA = "\uff0c"  # FULLWIDTH COMMA               -> , U+002C
KANGXI_COLOR = "\u2f8a"  # KANGXI RADICAL COLOR  looks like 色
SHU = "\u6570"  # 数
JU = "\u636e"  # 据
FAMILY = "\U0001f468\u200d\U0001f469\u200d\U0001f467"  # 一家三口: 5 code points


def test_a_zero_width_space_inside_a_word():
    """The whole point: the two strings are different, and look the same."""
    dirty = SHU + ZWSP + JU
    clean = SHU + JU

    assert dirty != clean
    assert len(dirty) == 3  # the invisible one is really there
    assert unicodedata.normalize("NFKC", dirty) == dirty  # NFKC does not fix it

    found = list(scan(dirty))
    assert len(found) == 1
    only = found[0]
    assert only.class_ == "invisible"
    assert only.fixable == "strip"
    assert only.codepoint == 0x200B
    assert only.codepoint_label == "U+200B"
    assert only.replacement is None  # nothing to replace it with -- it is deleted
    assert (only.line, only.column) == (1, 2)
    assert only.note


def test_the_family_emoji_keeps_its_joiners():
    """The gate test: red here means "ZWJ is load-bearing" stopped being true.

    A family of three is five code points rendered as one glyph.  Deleting the
    joiners does not clean the text up, it changes it into three people -- so
    ZWJ must never be filed as something safe to strip.
    """
    assert len(FAMILY) == 5

    found = list(scan(FAMILY))
    assert len(found) == 2
    assert {item.codepoint for item in found} == {0x200D}
    assert all(item.class_ == "invisible" for item in found)
    assert all(item.fixable == "manual" for item in found)

    # The counter-example the design turns on, asserted rather than described.
    assert FAMILY.replace(ZWJ, "") != FAMILY
    assert len(FAMILY.replace(ZWJ, "")) == 3


@pytest.mark.parametrize("char", [ZWJ, ZWNJ, LRM, RLO, VS16])
def test_load_bearing_characters_are_manual(char):
    found = list(scan(char))
    assert len(found) == 1
    assert found[0].class_ == "invisible"
    assert found[0].fixable == "manual"


@pytest.mark.parametrize("char", [ZWSP, BOM, SOFT_HYPHEN, WORD_JOINER])
def test_safe_to_delete_characters_are_strip(char):
    found = list(scan(char))
    assert len(found) == 1
    assert found[0].class_ == "invisible"
    assert found[0].fixable == "strip"


def test_a_byte_order_mark_is_invisible_not_compat():
    """A byte order mark is invisible, and NFKC does not classify it either.

    Measured rather than assumed: NFKC leaves U+FEFF alone, because it carries no
    compatibility mapping.  So nothing in the normalisation machinery will ever
    name this character -- the whitelist is the only thing that can, which is
    why "invisible" is tested before "compat" instead of falling through to it.
    """
    assert unicodedata.normalize("NFKC", BOM) == BOM

    only = list(scan(BOM))[0]
    assert only.class_ == "invisible"
    assert only.fixable == "strip"


def test_fullwidth_letters_are_reported_as_compat():
    """fold() refuses these on purpose; scan's job is to say so out loud."""
    only = list(scan(FULLWIDTH_A))[0]

    assert only.class_ == "compat"
    assert only.fixable == "nfkc"
    assert only.replacement == "A"
    assert only.replacement_label == "U+0041"
    assert only.codepoint == 0xFF21


def test_fullwidth_punctuation_says_what_nfkc_would_actually_do():
    """The note has to draw the line between repairing text and rewriting it.

    A full-width comma is not a defect to be fixed -- NFKC would turn it into an
    ASCII comma, which rewrites the sentence. A report that files it under the same
    sentence as a full-width letter invites the reader to lose their punctuation.
    """
    punctuation = list(scan(FULLWIDTH_COMMA))[0]
    letter = list(scan(FULLWIDTH_A))[0]

    assert punctuation.class_ == "compat"
    assert punctuation.replacement == ","
    assert "ASCII" in punctuation.note
    assert "rather than repairing" in punctuation.note
    assert punctuation.note != letter.note


def test_a_kangxi_radical_is_reported_as_foldable_not_as_compat():
    """A character both NFKC and the fold table can handle belongs to fold()."""
    only = list(scan(KANGXI_COLOR))[0]

    assert only.class_ == "lookalike"
    assert only.fixable == "fold"
    assert only.replacement == "\u8272"


def test_a_ligature_reports_no_single_replacement_label():
    """replacement_label is a U+... string only when one character comes out."""
    only = list(scan("\ufdfa"))[0]  # ARABIC LIGATURE SALLALLAHOU ALAYHE WASALLAM

    assert only.class_ == "compat"
    assert only.replacement is not None
    assert len(only.replacement) > 1
    assert only.replacement_label is None


@pytest.mark.parametrize("text", [SHU + JU, "", "hello", "abc 123"])
def test_clean_text_produces_nothing(text):
    """False positives are how a diagnostic tool loses its users."""
    assert list(scan(text)) == []
    assert scan_stats(text) == {}


def test_lookalike_findings_agree_with_iter_lookalikes():
    """Asserted against the other API, not against hand-written expectations.

    Two cursors drift; one cursor cannot.  If this ever goes red, the position
    logic was duplicated rather than shared.
    """
    text = "\u7b2c\u4e00\u884c\n\u7b2c\u2f06\u884c\u2ec6"  # 第一行\n第⼆行⻆

    from_iter = [(item.line, item.column, item.codepoint, item.replacement) for item in iter_lookalikes(text)]
    from_scan = [
        (item.line, item.column, item.codepoint, item.replacement)
        for item in scan(text)
        if item.class_ == "lookalike"
    ]

    assert from_scan == from_iter
    assert len(from_scan) == 2


def test_positions_are_line_and_column_not_offsets():
    text = "\u7b2c\u4e00\u884c\n\u7b2c" + ZWSP + "\u4e8c\u884c"
    only = next(iter(scan(text)))

    assert (only.line, only.column) == (2, 2)
    assert text[only.index] == ZWSP


def test_stats_match_the_findings():
    text = SHU + ZWSP + JU + KANGXI_COLOR + FULLWIDTH_A
    stats = scan_stats(text)

    assert sum(stats.values()) == len(list(scan(text)))
    assert stats == {"invisible": 1, "lookalike": 1, "compat": 1}


def test_the_strip_set_and_the_manual_set_do_not_overlap():
    """C4 as an assertion, not a comment: nothing load-bearing is strippable."""
    safe = strip_codepoints()
    manual = manual_codepoints()

    assert not (safe & manual)
    for codepoint in (0x200C, 0x200D, 0x200E, 0x200F, 0x202E, 0x2066, 0xFE0F, 0xE0100):
        assert codepoint in manual
        assert codepoint not in safe


def test_the_fast_lookup_answers_exactly_what_the_tables_say():
    """``_KNOWN`` is a derived index, and a derived index can drift.

    ``classify_invisible`` short-circuits on ``_KNOWN`` before consulting the
    tables, so if that set ever falls out of sync the classifier starts answering
    ``None`` for characters it has an opinion about -- silently, and only for the
    ones nobody happened to test. This is the test that catches that.
    """
    from cjkfold import _classes

    listed = set(_classes.strip_codepoints()) | set(_classes.manual_codepoints())

    assert _classes._KNOWN == listed
    for codepoint in sorted(listed):
        assert _classes.classify_invisible(codepoint) is not None

    # Characters that are on no list at all, including one that is a compat
    # finding -- a different class, and not this one's business.
    assert _classes.classify_invisible(0x4E00) is None  # 一
    assert _classes.classify_invisible(0xFF0C) is None  # ，FULLWIDTH COMMA


def test_a_replacement_character_is_broken_and_cannot_be_fixed():
    """U+FFFD is a record of a failure, not a character to repair."""
    only = list(scan("\ufffd"))[0]

    assert only.class_ == "broken"
    assert only.fixable == "manual"
    assert only.replacement is None
    assert "failed to decode" in only.note


@pytest.mark.parametrize("codepoint", [0xE000, 0xF8FF, 0xF0000, 0x10FFFD])
def test_private_use_code_points_are_broken_and_say_why(codepoint):
    """Private use: what it looks like is the font's decision, not Unicode's."""
    only = list(scan(chr(codepoint)))[0]

    assert only.class_ == "broken"
    assert only.fixable == "manual"
    assert "private use" in only.note


def test_ordinary_characters_are_not_broken():
    for text in ("\u4e00", "A", "\u3000", "\u00a0"):
        assert all(item.class_ != "broken" for item in scan(text))


@pytest.mark.parametrize(
    ("char", "replacement"),
    [
        ("\uff21", "A"),  # FULLWIDTH LATIN CAPITAL LETTER A
        ("\u3000", " "),  # IDEOGRAPHIC SPACE
        ("\uf900", "\u8c48"),  # CJK COMPATIBILITY IDEOGRAPH-F900 -> 豈
        ("\u00a0", " "),  # NO-BREAK SPACE
    ],
    ids=["fullwidth-letter", "ideographic-space", "compat-ideograph", "nbsp"],
)
def test_the_compat_family_covers_the_four_the_roadmap_named(char, replacement):
    """G3: the NFKC family needs a diagnostic entry, and these four are the test.

    Measured rather than guessed -- each expected value is what the running
    interpreter's own NFKC produces, checked before this test was written.
    """
    only = list(scan(char))[0]

    assert only.class_ == "compat"
    assert only.fixable == "nfkc"
    assert only.replacement == replacement


@pytest.mark.parametrize(
    "text",
    ["", "abc", "\ufffd", "\ue000", "\U0001f600", "\U00020000"],
    ids=["empty", "ascii", "replacement-char", "private-use", "emoji", "bmp-outer"],
)
def test_odd_input_does_not_raise(text):
    list(scan(text))
    scan_stats(text)


def test_scan_does_not_modify_its_input():
    """Read-only by contract: scan reports, the caller decides."""
    text = SHU + ZWSP + JU
    before = str(text)

    list(scan(text))

    assert text == before
