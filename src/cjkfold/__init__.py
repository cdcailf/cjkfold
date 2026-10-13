"""cjkfold -- fold look-alike CJK glyphs so extracted text matches again.

    >>> from cjkfold import fold
    >>> fold("⻆⺁⼀") == "角厂一"
    True

See :mod:`cjkfold.normalize` for the background, and :mod:`cjkfold.score` for
the retrieval-ranking helper that pairs with it.
"""

from __future__ import annotations

from ._table import EQUIVALENT_IDEOGRAPH
from .normalize import Lookalike, fold, has_lookalikes, iter_lookalikes, kind_of
from .score import exact_boost, ngram_overlap, ngrams

__version__ = "0.1.0"

__all__ = [
    "fold",
    "has_lookalikes",
    "iter_lookalikes",
    "Lookalike",
    "kind_of",
    "ngrams",
    "ngram_overlap",
    "exact_boost",
    "EQUIVALENT_IDEOGRAPH",
    "__version__",
]
