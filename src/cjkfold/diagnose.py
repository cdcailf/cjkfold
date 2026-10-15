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
from typing import Iterator

from ._classes import classify_invisible
from .normalize import _FOLD, _iter_positions, kind_of

__all__ = ["Finding", "scan", "scan_stats"]


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


def scan(text: str) -> Iterator[Finding]:
    """Yield one :class:`Finding` per problematic character in *text*, in order.

    Classes, and why the order they are tested in matters:

    ``lookalike``
        A foldable glyph, decided by the same table ``fold()`` uses.
    ``invisible``
        On the hand-written list in :mod:`cjkfold._classes`, carrying a
        ``fixable`` of ``strip`` or ``manual``.
    ``compat``
        A character ``NFKC`` would rewrite but ``fold()`` deliberately leaves
        alone, so the caller can decide rather than discover.

    Invisible is tested *before* compat on purpose: the whitelist is this
    package's own judgement, written down with a reason, while what ``NFKC`` does
    to a character depends on the Unicode version of whichever interpreter is
    running.  A character we have looked at should not be reclassified by the
    host Python.

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
                    note=(
                        "NFKC would rewrite this; fold() leaves it alone on "
                        "purpose, so the decision stays with the caller"
                    ),
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
