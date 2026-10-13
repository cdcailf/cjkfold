"""Score bonuses that restore exact-token ranking in dense retrieval.

Embeddings are bad at literal tokens.  A rare identifier or short code sits
almost nowhere useful in vector space, and a *short*, unrelated document can
easily out-score the long document that contains the token verbatim -- short
documents have tighter embeddings and therefore inflated cosine similarity.

Measured on a real corpus, the document that literally contained the query
string scored 0.29 while an unrelated short document scored 0.36: the ranking
was simply inverted.

:func:`exact_boost` restores the ordering by rewarding character n-grams of the
query that occur verbatim in the document.  Add the result to your vector score
and re-rank.

Both sides are folded through :func:`cjkfold.fold` internally.  Folding only the
index, or only the query, silently disables the whole mechanism -- so the
helper does it for you and the API gives you no way to get it wrong.
"""

from __future__ import annotations

from typing import Iterable

from .normalize import fold

__all__ = ["ngram_overlap", "exact_boost", "ngrams"]


def ngrams(text: str, n: int = 4) -> set[str]:
    """Return the set of character *n*-grams of *text*.

    Text shorter than *n* yields the whole string (or nothing, if empty), so a
    two-character query still produces one comparison unit.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    folded = fold(text)
    if not folded:
        return set()
    if len(folded) <= n:
        return {folded}
    return {folded[i : i + n] for i in range(len(folded) - n + 1)}


def ngram_overlap(query: str, document: str, *, n: int = 4) -> float:
    """Fraction of the query's n-grams that appear verbatim in *document* (0..1).

    Queries shorter than *n* degrade to a containment test, because a query of
    two or three characters yields no shingle to compare.  Without that branch
    every short query scores 0.0 -- the mechanism silently does nothing for
    exactly the queries users type most.
    """
    query_folded = fold(query)
    if not query_folded:
        return 0.0
    document_folded = fold(document)

    if len(query_folded) <= n:
        return 1.0 if query_folded in document_folded else 0.0

    query_grams = ngrams(query_folded, n)
    if not query_grams:
        return 0.0
    document_grams = ngrams(document_folded, n)
    return len(query_grams & document_grams) / len(query_grams)


def exact_boost(
    query: str,
    document: str,
    *,
    n: int = 4,
    cap: float = 0.25,
) -> float:
    """Bonus in ``[0, cap]`` for literal n-gram overlap between query and document.

    Scales linearly with :func:`ngram_overlap`, so a document containing the
    entire query earns the full ``cap`` while one sharing half of it earns half.

    Typical use::

        score = vector_similarity(query, document) + exact_boost(query, document)
    """
    if cap < 0:
        raise ValueError("cap must be >= 0")
    return cap * ngram_overlap(query, document, n=n)
