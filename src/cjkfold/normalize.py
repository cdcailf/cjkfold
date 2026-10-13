"""Fold look-alike CJK glyphs onto their canonical ideograph.

Text extracted from PDFs -- and from some OCR pipelines -- regularly contains
characters that *render* identically to an ordinary Han character while sitting
on a different code point::

    ⼀  U+2F00  KANGXI RADICAL ONE           renders as  一  U+4E00
    ⻆  U+2EC6  CJK RADICAL SIMPLIFIED HORN  renders as  角  U+89D2

Nothing raises.  Comparison simply starts disagreeing::

    >>> "紫色" in extracted_text
    False

and a retriever quietly ranks an unrelated short document above the one that
contains the query verbatim.

NFKC already solves the Kangxi block (U+2F00-U+2FDF): all 214 of its characters
carry compatibility decompositions.  It does *not* solve the CJK Radicals
Supplement (U+2E80-U+2EFF), where 113 of the 115 named characters survive NFKC
untouched -- Unicode withholds compatibility mappings there deliberately, since
those glyphs are distinct encoded radicals rather than compatibility variants.

This module closes that gap using the ``EquivalentUnifiedIdeograph`` property
from the Unicode Character Database (Unicode 15.1+).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Iterator

from ._table import EQUIVALENT_IDEOGRAPH

__all__ = [
    "fold",
    "has_lookalikes",
    "iter_lookalikes",
    "Lookalike",
    "kind_of",
]

# str.translate() mapping: code point -> canonical form
_FOLD: dict[int, str] = {ord(char): target for char, target in EQUIVALENT_IDEOGRAPH.items()}

# Radic supplement: the block NFKC cannot repair.
_RADICAL_SUPPLEMENT = (0x2E80, 0x2EFF)
# Kangxi radicals: NFKC repairs these, included for completeness / older engines.
_KANGXI = (0x2F00, 0x2FDF)
# CJK strokes: stroke glyphs that fold onto a look-alike ideograph.
_CJK_STROKE = (0x31C0, 0x31EF)


def kind_of(codepoint: int) -> str:
    """Classify a code point by the Unicode block that causes the look-alike."""
    if _RADICAL_SUPPLEMENT[0] <= codepoint <= _RADICAL_SUPPLEMENT[1]:
        return "radical-supplement"
    if _KANGXI[0] <= codepoint <= _KANGXI[1]:
        return "kangxi"
    if _CJK_STROKE[0] <= codepoint <= _CJK_STROKE[1]:
        return "cjk-stroke"
    return "other"


@dataclass(frozen=True)
class Lookalike:
    """One character that renders like a different, more common character."""

    index: int
    line: int
    column: int
    char: str
    codepoint: int
    replacement: str
    name: str
    kind: str

    @property
    def codepoint_label(self) -> str:
        return f"U+{self.codepoint:04X}"

    @property
    def replacement_label(self) -> str:
        return f"U+{ord(self.replacement):04X}"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return (
            f"{self.line}:{self.column}  {self.char} {self.codepoint_label} "
            f"-> {self.replacement} {self.replacement_label}  ({self.name})"
        )


def fold(text: str) -> str:
    """Return *text* with every look-alike glyph replaced by its canonical form.

    Purely a character-level fold: it never rewrites full-width punctuation,
    ligatures or other NFKC compatibility characters, so it is safe to apply to
    text that will still be displayed or stored.  Use
    ``unicodedata.normalize("NFKC", ...)`` as well if you also want those.

    Idempotent -- ``fold(fold(s)) == fold(s)`` -- and returns the original
    string object unchanged when there is nothing to fold.
    """
    if not text:
        return text
    for char in text:
        if ord(char) in _FOLD:
            return text.translate(_FOLD)
    return text


def has_lookalikes(text: str) -> bool:
    """True if *text* contains at least one foldable code point."""
    return any(ord(char) in _FOLD for char in text)


def iter_lookalikes(text: str) -> Iterator[Lookalike]:
    """Yield every foldable character in *text*, in order, with 1-based position."""
    line, column = 1, 1
    for index, char in enumerate(text):
        codepoint = ord(char)
        replacement = _FOLD.get(codepoint)
        if replacement is not None:
            yield Lookalike(
                index=index,
                line=line,
                column=column,
                char=char,
                codepoint=codepoint,
                replacement=replacement,
                name=unicodedata.name(char, "<unnamed>"),
                kind=kind_of(codepoint),
            )
        if char == "\n":
            line, column = line + 1, 1
        else:
            column += 1
