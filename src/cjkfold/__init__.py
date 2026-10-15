"""cjkfold -- fold look-alike CJK glyphs so extracted text matches again.

    >>> from cjkfold import fold
    >>> fold("⻆⺁⼀") == "角厂一"
    True

See :mod:`cjkfold.normalize` for the background, :mod:`cjkfold.score` for the
retrieval-ranking helper that pairs with it, and :mod:`cjkfold.integrations` for
framework-agnostic adapters that fold a whole document set.
"""

from __future__ import annotations

from ._table import EQUIVALENT_IDEOGRAPH
from .diagnose import Finding, is_punctuation, scan, scan_stats
from .inputs import NotTextFile, read_text
from .integrations import fold_document, fold_documents, rerank, text_of
# ``normalize`` the function shadows ``cjkfold.normalize`` the module as an
# attribute of this package. The module stays importable (``import cjkfold.normalize``
# and ``from cjkfold.normalize import fold`` both work); what changes is that the
# name ``cjkfold.normalize`` now reads as the function. The alternative was making
# every caller type ``from cjkfold.normalize import normalize``, which is worse.
from .normalize import (
    Lookalike,
    fold,
    has_lookalikes,
    iter_lookalikes,
    kind_of,
    normalize,
    strip_invisible,
)
from .score import exact_boost, ngram_overlap, ngrams

__version__ = "0.3.0"

__all__ = [
    "fold",
    "has_lookalikes",
    "iter_lookalikes",
    "Lookalike",
    "kind_of",
    "normalize",
    "strip_invisible",
    "Finding",
    "is_punctuation",
    "scan",
    "scan_stats",
    "ngrams",
    "ngram_overlap",
    "exact_boost",
    "text_of",
    "fold_document",
    "fold_documents",
    "rerank",
    "read_text",
    "NotTextFile",
    "EQUIVALENT_IDEOGRAPH",
    "__version__",
]
