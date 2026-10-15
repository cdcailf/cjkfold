"""cjkfold -- fold look-alike CJK glyphs so extracted text matches again.

    >>> from cjkfold import fold
    >>> fold("⻆⺁⼀") == "角厂一"
    True

See :mod:`cjkfold.folding` for the background, :mod:`cjkfold.rewrite` for the two
explicit writes, :mod:`cjkfold.diagnose` for the read-only report, and
:mod:`cjkfold.score` for the retrieval-ranking helper that pairs with folding.
"""

from __future__ import annotations

from ._table import EQUIVALENT_IDEOGRAPH
from .diagnose import Finding, is_punctuation, scan, scan_stats
from .folding import Lookalike, fold, has_lookalikes, iter_lookalikes, kind_of
from .inputs import NotTextFile, read_text
from .integrations import fold_document, fold_documents, rerank, text_of
from .rewrite import normalize, strip_invisible
from .score import exact_boost, ngram_overlap, ngrams

__version__ = "0.4.0"

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
