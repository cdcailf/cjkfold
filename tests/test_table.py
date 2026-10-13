"""Guards on the generated table itself."""

from __future__ import annotations

import unicodedata

from cjkfold import EQUIVALENT_IDEOGRAPH, fold


def test_table_is_not_empty():
    assert len(EQUIVALENT_IDEOGRAPH) > 300


def test_every_value_is_exactly_one_character():
    """Regression guard.

    Escapes above the BMP must be written ``\\U000xxxxx`` -- a plain ``\\uXXXX``
    silently truncates to four digits, turning one character into two and
    corrupting the text it was supposed to repair.  This caught 23 such rows.
    """
    for source, target in EQUIVALENT_IDEOGRAPH.items():
        assert len(target) == 1, f"U+{ord(source):04X} maps to {target!r}"


def test_every_key_is_exactly_one_character():
    for source in EQUIVALENT_IDEOGRAPH:
        assert len(source) == 1, repr(source)


def test_table_covers_the_radical_supplement_block():
    """NFKC repairs 2 of the 115 named characters here; the table must repair ~all."""
    block = range(0x2E80, 0x2F00)
    named = [chr(cp) for cp in block if unicodedata.name(chr(cp), "")]
    repaired_by_nfkc = [c for c in named if unicodedata.normalize("NFKC", c) != c]
    repaired_by_table = [c for c in named if fold(c) != c]

    assert len(named) == 115
    assert len(repaired_by_nfkc) <= 5, "if NFKC now covers this block, revisit the README"
    assert len(repaired_by_table) >= 110


def test_every_target_is_an_ideograph():
    """Targets must be ideographs.

    A handful may read as unassigned (``Cn``) on an older interpreter: the table
    tracks the latest UCD, which can run ahead of the ``unicodedata`` database
    bundled with a given Python release (3.9 ships Unicode 13, where U+2B739
    does not exist yet).  Folding is unaffected -- it is a plain code point
    substitution -- but callers that ask ``unicodedata`` about the result should
    know.  Regenerate the table, or upgrade Python, to close the gap.
    """
    unassigned = []
    for source, target in EQUIVALENT_IDEOGRAPH.items():
        category = unicodedata.category(target)
        if category == "Cn":
            unassigned.append(f"U+{ord(target):04X}")
            continue
        assert category == "Lo", f"U+{ord(source):04X} -> {target!r} is {category}"
    assert len(unassigned) < 10, unassigned


def test_no_target_is_itself_a_source():
    """Folding must reach a fixed point in one pass (keeps fold() idempotent)."""
    assert set(EQUIVALENT_IDEOGRAPH.values()).isdisjoint(EQUIVALENT_IDEOGRAPH)


def test_multi_to_one_entries_exist():
    """Distinct encoded radicals legitimately fold onto one ideograph."""
    targets = list(EQUIVALENT_IDEOGRAPH.values())
    assert len(targets) != len(set(targets))


def test_spot_check_known_mappings():
    assert EQUIVALENT_IDEOGRAPH["\u2ec6"] == "\u89d2"
    assert EQUIVALENT_IDEOGRAPH["\u2e81"] == "\u5382"
    assert EQUIVALENT_IDEOGRAPH["\u2f00"] == "\u4e00"


def test_the_one_unmapped_character_is_the_repeat_sign():
    """U+2E80 CJK RADICAL REPEAT has no unified ideograph equivalent."""
    assert "\u2e80" not in EQUIVALENT_IDEOGRAPH
