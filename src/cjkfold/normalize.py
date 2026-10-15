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

Three explicit operations live here, and none of them calls another:

    fold()             look-alike glyphs -> their canonical ideograph
    normalize()        the NFKC family -- full-width letters, compatibility
                       characters -- which fold() refuses to touch on purpose
    strip_invisible()  the characters that carry no glyph at all

Every rewrite happens because a caller asked for that rewrite, by name, in code.
Nothing here quietly "tidies up" a string on its way somewhere else.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Iterator

from ._classes import is_punctuation, manual_codepoints, strip_codepoints
from ._table import EQUIVALENT_IDEOGRAPH

__all__ = [
    "fold",
    "has_lookalikes",
    "iter_lookalikes",
    "Lookalike",
    "kind_of",
    "normalize",
    "strip_invisible",
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


def normalize(text: str, *, keep_punctuation: bool = True) -> str:
    """Rewrite the NFKC family: the characters ``fold()`` deliberately leaves alone.

    Two different things live in that family, and ``keep_punctuation`` is where the
    difference shows:

    * a full-width letter (``Ａ`` U+FF21) or an ideographic space (``U+3000``) is a
      compatibility character -- rewriting it is a repair;
    * a full-width comma (``，`` U+FF0C) is punctuation -- NFKC turns it into ASCII
      ``,``, and that rewrites the sentence rather than repairing it.

    The default protects the second, because the alternative is a corpus that
    quietly loses its punctuation.  ``keep_punctuation=False`` gives you the whole
    NFKC pass, consequences included -- a decision worth having to type out.

    Applied one character at a time, so no cross-character composition happens:
    this rewrites compatibility characters and touches nothing else.  Returns the
    original object when there is nothing to change.
    """
    if not text:
        return text
    out: list[str] = []
    changed = False
    for char in text:
        if keep_punctuation and is_punctuation(char):
            out.append(char)
            continue
        replacement = unicodedata.normalize("NFKC", char)
        out.append(replacement)
        if replacement != char:
            changed = True
    return "".join(out) if changed else text


def strip_invisible(text: str, *, policy: str = "safe") -> str:
    """Delete invisible characters from *text*.

    ``policy="safe"`` (the default) removes only the ones whose deletion carries
    nothing: zero-width space, byte order mark, soft hyphen, word joiner.

    ``policy="all"`` removes everything on the list, including the load-bearing
    half -- ZWJ, ZWNJ, variation selectors, bidi controls.  **That breaks emoji
    sequences and Indic conjuncts**: a family of three becomes three separate
    people.  The name is the warning, and there is no option called "smart",
    because no such thing exists.

    Returns the original object when nothing was removed.
    """
    if policy == "safe":
        doomed = strip_codepoints()
    elif policy == "all":
        doomed = strip_codepoints() | manual_codepoints()
    else:
        raise ValueError(f"policy must be 'safe' or 'all', not {policy!r}")

    if not text:
        return text
    for char in text:
        if ord(char) in doomed:
            return "".join(item for item in text if ord(item) not in doomed)
    return text


def has_lookalikes(text: str) -> bool:
    """True if *text* contains at least one foldable code point."""
    return any(ord(char) in _FOLD for char in text)


def _iter_positions(text: str) -> Iterator[tuple[int, int, int, str]]:
    """Yield ``(index, line, column, char)`` for each character, 1-based positions.

    The only place in the package that decides what "line 3, column 4" means.
    ``iter_lookalikes`` and :func:`cjkfold.diagnose.scan` both walk text through
    this cursor rather than carrying one each: two cursors are two chances to
    drift, and a finding whose position is off by one is a finding the reader
    cannot go and check.
    """
    line, column = 1, 1
    for index, char in enumerate(text):
        yield index, line, column, char
        if char == "\n":
            line, column = line + 1, 1
        else:
            column += 1


def iter_lookalikes(text: str) -> Iterator[Lookalike]:
    """Yield every foldable character in *text*, in order, with 1-based position."""
    for index, line, column, char in _iter_positions(text):
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
