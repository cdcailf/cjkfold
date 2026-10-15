"""Report every character that breaks a comparison without showing up.

:mod:`cjkfold.normalize` answers "which glyphs *look like* a different
character".  This module answers the harder half of the same question: which
characters *do not show up at all*.  They are worse than the look-alikes, because
a look-alike can be caught by staring at the text and this cannot::

    数\u200b据   reads as   数据
    数据

    >>> "数\\u200b据" == "数据"
    False

``NFKC`` does not repair it either, and ``fold()`` is right not to try: a
character that carries no glyph may still carry meaning (see
:mod:`cjkfold._classes` for the load-bearing half of the family).  So this is a
read-only layer.  It reports; it never rewrites.  Deciding what to delete is a
decision the caller makes with the finding in hand -- which is why
:attr:`Finding.fixable` distinguishes the characters that are safe to strip from
the ones that are not.

One pass, one cursor, every class of finding -- ``scan`` is meant to run over a
whole corpus, not over one string at a time.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Final, Iterator

from ._classes import classify_invisible, is_punctuation
from .normalize import _FOLD, _iter_positions, kind_of

__all__ = ["Finding", "is_punctuation", "scan", "scan_stats"]


@dataclass(frozen=True)
class Finding:
    """One character in the text that would break a comparison.

    ``index`` / ``line`` / ``column`` follow the same rule as
    :class:`cjkfold.Lookalike`: a character offset, and 1-based positions.
    ``replacement`` is set only where cjkfold itself can name the fix -- a
    ``fold`` or an ``nfkc``.  An invisible character has no replacement to
    offer, and inventing one would be the same mistake as guessing past the
    whitelist.
    """

    index: int
    line: int
    column: int
    char: str
    codepoint: int
    class_: str
    fixable: str
    replacement: str | None
    note: str

    @property
    def codepoint_label(self) -> str:
        return f"U+{self.codepoint:04X}"

    @property
    def replacement_label(self) -> str | None:
        """``"U+8272"``, or ``None`` when there is no single replacement character.

        Some NFKC expansions produce several characters (ligatures); a label
        only exists when exactly one character comes out.
        """
        if self.replacement is None or len(self.replacement) != 1:
            return None
        return f"U+{ord(self.replacement):04X}"


_REPLACEMENT_CHARACTER = 0xFFFD

#: The three private use areas.  Nothing defines what a code point in here looks
#: like, which is exactly what makes them worth reporting.
_PRIVATE_USE_RANGES: Final[tuple[tuple[int, int], ...]] = (
    (0xE000, 0xF8FF),  # BMP
    (0xF0000, 0xFFFFD),  # plane 15
    (0x100000, 0x10FFFD),  # plane 16
)


def _broken_note(codepoint: int) -> str | None:
    """Why this code point cannot be trusted, or ``None`` if it is an ordinary character.

    Two different kinds of damage, and neither is fixable:

    ``U+FFFD`` is not a character, it is a record of one that could not be read --
    something upstream already failed, and the failure is still visible here.

    A private use code point is the opposite: something upstream *succeeded* in
    writing a character this machine cannot name.  Nothing dictates what it looks
    like, so whichever font is doing the rendering decides -- it can come out as a
    box, as nothing at all, or as a glyph that means something else entirely.
    """
    if codepoint == _REPLACEMENT_CHARACTER:
        return (
            "U+FFFD REPLACEMENT CHARACTER: something already failed to decode here. "
            "This is not a character, it is a record of one that could not be read"
        )
    for low, high in _PRIVATE_USE_RANGES:
        if low <= codepoint <= high:
            return (
                "a private use code point: nothing defines what it looks like, so the "
                "font doing the rendering decides -- it can come out as a box, as "
                "nothing at all, or as a glyph that means something else"
            )
    return None


def _compat_note(char: str) -> str:
    """Why NFKC would rewrite this -- and whether that is a repair or a rewrite.

    A reader told only "NFKC would rewrite this" is one command away from running
    NFKC over a whole corpus and losing its punctuation.  Drawing that line is the
    difference between a report worth reading and a report that gets ignored.
    """
    if is_punctuation(char):
        return (
            "a full-width punctuation mark: NFKC would replace it with ASCII "
            "punctuation -- that rewrites the text rather than repairing it"
        )
    return (
        "NFKC would rewrite this; fold() leaves it alone on purpose, so the "
        "decision stays with the caller"
    )


def scan(text: str) -> Iterator[Finding]:
    """Yield one :class:`Finding` per problematic character in *text*, in order.

    Classes, and why the order they are tested in matters:

    ``lookalike``
        A foldable glyph, decided by the same table ``fold()`` uses.
    ``invisible``
        On the hand-written list in :mod:`cjkfold._classes`, carrying a
        ``fixable`` of ``strip`` or ``manual``.
    ``broken``
        ``U+FFFD``, or a private use code point.  Damage that cannot be repaired,
        only reported -- and worth reporting, because a private use code point
        renders as whatever the local font decides.
    ``compat``
        A character ``NFKC`` would rewrite but ``fold()`` deliberately leaves
        alone, so the caller can decide rather than discover.

    Invisible is tested *before* compat on purpose: the whitelist is this
    package's own judgement, written down with a reason, while what ``NFKC`` does
    to a character depends on the Unicode version of whichever interpreter is
    running.  A character we have looked at should not be reclassified by the
    host Python.  ``broken`` is tested before it for the same reason.

    Nothing is mutated and nothing is decoded -- pass it a string, or an empty
    one.  It is a generator, so it costs one pass over the text and no memory.
    """
    if not text:
        return
    for index, line, column, char in _iter_positions(text):
        codepoint = ord(char)
        replacement = _FOLD.get(codepoint)
        if replacement is not None:
            yield Finding(
                index=index,
                line=line,
                column=column,
                char=char,
                codepoint=codepoint,
                class_="lookalike",
                fixable="fold",
                replacement=replacement,
                note=(
                    f"renders exactly like {replacement}, but sits on a "
                    f"separate {kind_of(codepoint)} code point"
                ),
            )
            continue

        invisible = classify_invisible(codepoint)
        if invisible is not None:
            yield Finding(
                index=index,
                line=line,
                column=column,
                char=char,
                codepoint=codepoint,
                class_="invisible",
                fixable=invisible.fixable,
                replacement=None,
                note=invisible.note,
            )
            continue

        broken = _broken_note(codepoint)
        if broken is not None:
            yield Finding(
                index=index,
                line=line,
                column=column,
                char=char,
                codepoint=codepoint,
                class_="broken",
                fixable="manual",
                replacement=None,
                note=broken,
            )
            continue

        if codepoint > 0x7F:
            folded = unicodedata.normalize("NFKC", char)
            if folded != char:
                yield Finding(
                    index=index,
                    line=line,
                    column=column,
                    char=char,
                    codepoint=codepoint,
                    class_="compat",
                    fixable="nfkc",
                    replacement=folded,
                    note=_compat_note(char),
                )


def scan_stats(text: str) -> dict[str, int]:
    """Count findings by class -- ``{"invisible": 2, "lookalike": 1}``.

    Classes with nothing in them are left out.  Summing the values gives the
    same number as ``len(list(scan(text)))``, which is the invariant the tests
    pin rather than a hand-written expectation.
    """
    counts: dict[str, int] = {}
    for finding in scan(text):
        counts[finding.class_] = counts.get(finding.class_, 0) + 1
    return counts
