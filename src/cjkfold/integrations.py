"""Framework-agnostic adapters for the two places folding has to happen.

Folding belongs on *both* sides of a retrieval pipeline -- on documents as they
go into the index, and on the query as it comes out -- and a dense score should
not be trusted until the exact-match boost is added to it.  That is three touch
points, and none of them is specific to any framework.

These helpers therefore import nothing.  A LangChain ``Document`` carries
``page_content``; a LlamaIndex node carries ``text``; both are ordinary
attribute lookups, so a duck-typed adapter covers them.  Making the caller
install a whole framework in order to fold a string would be a bad trade --
framework APIs move, string folding does not.
"""

from __future__ import annotations

import copy
from typing import Any, Iterable, Sequence, TypeVar

from .normalize import fold
from .score import exact_boost

__all__ = ["fold_documents", "rerank", "text_of"]

T = TypeVar("T")

# Attributes that carry the text, in priority order.  ``page_content`` is
# LangChain, ``text`` is LlamaIndex; ``content`` catches the rest.
_TEXT_ATTRIBUTES = ("page_content", "text", "content")


def text_of(document: Any) -> str:
    """Return the text carried by *document*, or raise ``TypeError``.

    Recognises plain strings and objects exposing ``page_content``, ``text`` or
    ``content`` -- which covers LangChain documents, LlamaIndex nodes, and most
    home-grown record types.
    """
    if isinstance(document, str):
        return document
    for attribute in _TEXT_ATTRIBUTES:
        value = getattr(document, attribute, None)
        if isinstance(value, str):
            return value
    raise TypeError(
        "cannot find text on "
        f"{type(document).__name__}: expected a str or one of {_TEXT_ATTRIBUTES}"
    )


def _shallow_copy(document: Any) -> Any:
    try:
        return copy.copy(document)
    except Exception:  # pragma: no cover - exotic objects without copy support
        return document


def fold_document(document: T, *, inplace: bool = False) -> T:
    """Fold the text of one document.

    Returns a shallow copy by default, so callers can use it in a comprehension
    without mutating the objects they were handed.  Pass ``inplace=True`` when
    the original is disposable.
    """
    target = document if inplace else _shallow_copy(document)

    if isinstance(target, str):
        return fold(target)  # type: ignore[return-value]

    for attribute in _TEXT_ATTRIBUTES:
        value = getattr(target, attribute, None)
        if isinstance(value, str):
            folded = fold(value)
            if folded is not value:
                setattr(target, attribute, folded)
            return target

    raise TypeError(
        "cannot find text on "
        f"{type(document).__name__}: expected a str or one of {_TEXT_ATTRIBUTES}"
    )


def fold_documents(documents: Iterable[T], *, inplace: bool = False) -> list[T]:
    """Fold the text of every document -- the ingestion-side pass.

    Only the text attribute is touched; ``metadata`` and everything else is left
    exactly as it was.
    """
    return [fold_document(document, inplace=inplace) for document in documents]


def rerank(
    query: str,
    documents: Sequence[T],
    scores: Sequence[float],
    *,
    cap: float = 0.25,
    n: int = 4,
) -> list[tuple[T, float]]:
    """Add the exact-match boost to *scores* and return results best-first.

    This is the fix for the ranking inversion described in :mod:`cjkfold.score`:
    a short, unrelated document out-scores a long document that contains the
    query verbatim, purely because its embedding is tighter.  Give this the same
    query, documents and vector scores your store returned::

        hits = vectorstore.similarity_search_with_score(query, k=20)
        docs, scores = zip(*hits)
        for document, score in rerank(query, docs, scores):
            ...

    The query is folded internally, so it does not matter whether it was typed
    with ordinary characters or with look-alikes.
    """
    if len(documents) != len(scores):
        raise ValueError(
            f"documents and scores must be the same length "
            f"(got {len(documents)} and {len(scores)})"
        )
    combined = [
        (document, float(score) + exact_boost(query, text_of(document), n=n, cap=cap))
        for document, score in zip(documents, scores)
    ]
    combined.sort(key=lambda pair: pair[1], reverse=True)
    return combined
