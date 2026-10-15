"""The two explicit writes: what to do about the characters ``fold()`` ignores.

:mod:`cjkfold.folding` handles one family -- glyphs that render as a different
character.  This module handles the other two, and it folds nothing:

    normalize()        the NFKC family: full-width letters, compatibility
                       ideographs, ideographic spaces
    strip_invisible()  the characters that carry no glyph at all

Neither is applied to anything automatically.  They exist so that a caller can
decide -- in code, by name -- to rewrite a string.  The command line deliberately
exposes neither: `fold -w` already rewrites files in place, and two more
destructive subcommands would be a loaded gun pointed at a corpus.

The split from :mod:`cjkfold.folding` is not cosmetic.  A function named
``normalize`` cannot live in a module named ``normalize`` without one of the two
losing its name -- and a name that means one thing depending on how it was
imported is worse than either name being taken.
"""

from __future__ import annotations

import unicodedata

from ._classes import is_punctuation, manual_codepoints, strip_codepoints

__all__ = ["normalize", "strip_invisible"]


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
