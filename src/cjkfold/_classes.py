"""The invisible characters, and whether deleting each one is safe.

``unicodedata.category(char) == "Cf"`` looks like the test you want, and is not:
half of that category is load-bearing.  ZWJ (U+200D) is what holds an emoji
sequence together -- a family of three renders from five code points, and
deleting the three joiners leaves three separate people.  ZWNJ (U+200C) decides
whether the letters around it join, which matters in Persian and Indic scripts.
A variation selector picks which glyph the *preceding* character gets, so
dropping it changes what is displayed.  A bidi control decides which way the
text around it reads -- the trick behind "Trojan Source".

So the list is hand-written, one entry at a time, each with its reason attached:

    strip   deletion is safe -- the character never shows and carries nothing
    manual  do not delete it without looking: it changes the meaning or the
            rendering of the text around it

The note travels with the finding because "manual" on its own answers nothing.
The question a reader will actually have is *why these three letters of Code
Point alphabet matter*, and a scanner that cannot answer gets ignored.

Ranges are kept in a second table only because variation selectors and bidi
controls are contiguous -- the notes are still written one at a time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__ = [
    "Invisible",
    "classify_invisible",
    "strip_codepoints",
    "manual_codepoints",
]


@dataclass(frozen=True)
class Invisible:
    """One invisible character: how to treat it, and why."""

    #: ``"strip"`` (safe to delete) or ``"manual"`` (do not delete unseen).
    fixable: str
    #: Why it is classified this way, in words a reader can act on.
    note: str


_STRIP: Final[dict[int, Invisible]] = {
    0x00AD: Invisible(
        "strip",
        "a soft hyphen: it only shows where a line happens to break, and there "
        "is no hyphen in the text",
    ),
    0x200B: Invisible(
        "strip",
        "prints as nothing at all -- two strings that differ only by this "
        "character look identical",
    ),
    0x2060: Invisible(
        "strip",
        "invisible; its only job is to stop a line break between its neighbours",
    ),
    0xFEFF: Invisible(
        "strip",
        "a byte order mark at the start of a file, and invisible anywhere else",
    ),
}

_MANUAL: Final[dict[int, Invisible]] = {
    0x200C: Invisible(
        "manual",
        "zero width non-joiner: it decides whether the letters around it join, "
        "which matters in Persian and Indic scripts",
    ),
    0x200D: Invisible(
        "manual",
        "zero width joiner: it holds emoji sequences together -- a family of "
        "three is five code points, and deleting the joiners leaves three "
        "separate people",
    ),
    0x200E: Invisible(
        "manual",
        "a left-to-right mark: removing it can change which way the text around "
        "it reads",
    ),
    0x200F: Invisible(
        "manual",
        "a right-to-left mark: removing it can change which way the text around "
        "it reads",
    ),
}

_MANUAL_RANGES: Final[tuple[tuple[int, int, Invisible], ...]] = (
    (
        0x202A,
        0x202E,
        Invisible(
            "manual",
            "a bidirectional control (the trick behind Trojan Source): removing "
            "it changes the visual order of the text that follows",
        ),
    ),
    (
        0x2066,
        0x2069,
        Invisible(
            "manual",
            "a bidirectional isolate: it changes how the text around it is "
            "displayed",
        ),
    ),
    (
        0xFE00,
        0xFE0F,
        Invisible(
            "manual",
            "a variation selector: it picks which glyph the character before it "
            "gets, so removing it changes what is rendered",
        ),
    ),
    (
        0xE0100,
        0xE01EF,
        Invisible(
            "manual",
            "a variation selector from the supplementary set: it picks which "
            "glyph the character before it gets",
        ),
    ),
)


def classify_invisible(codepoint: int) -> Invisible | None:
    """Return how to treat *codepoint*, or ``None`` when it is not on the list.

    ``None`` is the answer for every character this module has not made a
    judgement about -- including the ones that merely *look* suspicious.  The
    list is the product here; guessing past it is how a scanner starts reporting
    phantoms.
    """
    known = _MANUAL.get(codepoint)
    if known is not None:
        return known
    for low, high, entry in _MANUAL_RANGES:
        if low <= codepoint <= high:
            return entry
    return _STRIP.get(codepoint)


def strip_codepoints() -> frozenset[int]:
    """Every code point whose deletion is safe."""
    return frozenset(_STRIP)


def manual_codepoints() -> frozenset[int]:
    """Every code point that must not be deleted without a human looking."""
    expanded = set(_MANUAL)
    for low, high, _entry in _MANUAL_RANGES:
        expanded.update(range(low, high + 1))
    return frozenset(expanded)
