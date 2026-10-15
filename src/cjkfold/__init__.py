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
from .normalize import Lookalike, fold, has_lookalikes, iter_lookalikes, kind_of
from .score import exact_boost, ngram_overlap, ngrams

__version__ = "0.1.2"

__all__ = [
    "fold",
    "has_lookalikes",
    "iter_lookalikes",
    "Lookalike",
    "kind_of",
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
