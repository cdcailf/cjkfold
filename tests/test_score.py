"""Retrieval-ranking helper."""

from __future__ import annotations

import pytest

from cjkfold import exact_boost, ngram_overlap, ngrams

RADICAL_HORN = "\u2ec6"  # ⻆ looks like 角


def test_ngrams_of_short_text():
    assert ngrams("ab", 4) == {"ab"}
    assert ngrams("", 4) == set()


def test_ngrams_of_longer_text():
    assert ngrams("abcd", 2) == {"ab", "bc", "cd"}


def test_ngrams_rejects_bad_n():
    with pytest.raises(ValueError):
        ngrams("abcd", 0)


def test_full_overlap_scores_the_cap():
    text = "\u7d2b\u8272\u72ec\u89d2\u517d\u534f\u8bae\u7684\u7f16\u53f7\u662f PU-7788-ZX"
    assert ngram_overlap(text, text) == 1.0
    assert exact_boost(text, text, cap=0.25) == pytest.approx(0.25)


def test_no_overlap_scores_zero():
    assert exact_boost("\u7d2b\u8272\u72ec\u89d2\u517d", "\u5b8c\u5168\u65e0\u5173\u7684\u53e6\u4e00\u6bb5\u6587\u672c", cap=0.25) == 0.0


def test_partial_overlap_lands_in_between():
    query = "\u7d2b\u8272\u72ec\u89d2\u517d\u534f\u8bae\u7684\u7f16\u53f7"
    document = "\u7d2b\u8272\u72ec\u89d2\u517d\u534f\u8bae"
    score = exact_boost(query, document, cap=0.25)
    assert 0.0 < score < 0.25


def test_short_query_uses_containment():
    """A query shorter than n has no shingles -- it must not silently score zero."""
    assert ngram_overlap("\u989c\u8272", "\u6807\u51c6\u989c\u8272\u503c\u4e0e\u89d2\u8272\u6309\u94ae") == 1.0
    assert ngram_overlap("\u989c\u8272", "\u5b8c\u5168\u65e0\u5173") == 0.0


def test_short_query_matches_a_folded_document():
    """The README scenario in miniature: a two-character query, a look-alike doc."""
    document = "\u6807\u51c6\u989c\u2F8a\u503c"  # 标准颜⾊值
    assert "\u989c\u8272" not in document
    assert exact_boost("\u989c\u8272", document, cap=0.25) == pytest.approx(0.25)


def test_boost_never_exceeds_the_cap():
    text = "abcdefghij" * 20
    assert exact_boost(text, text, cap=0.1) <= 0.1


def test_negative_cap_is_rejected():
    with pytest.raises(ValueError):
        exact_boost("a", "a", cap=-1)


def test_folding_is_applied_to_both_sides():
    """A folded document must still match a plain query.

    Folding the index but not the query -- or the reverse -- silently disables
    the whole mechanism, because nothing ever matches.  Both sides are folded
    inside the helper so the API gives the caller no way to get it wrong.
    """
    # Document side carries the look-alike, query side is ordinary text.
    document = "\u672c\u6587\u6863\u7ed9\u51fa" + RADICAL_HORN + "\u8272\u8868\u7684\u7f16\u53f7\u89c4\u5219"
    query = "\u89d2\u8272\u8868\u7684\u7f16\u53f7"  # 角色表的编号

    assert query not in document  # the raw strings really do not match
    assert ngram_overlap(query, document) == 1.0
    assert exact_boost(query, document) > 0


def test_boost_is_usable_as_a_reranker():
    """The scenario from the README: verbatim match must outrank a short decoy."""
    query = "\u7d2b\u8272\u72ec\u89d2\u517d\u534f\u8bae\u7f16\u53f7"
    relevant = (
        "\u672c\u6587\u6863\u5b9a\u4e49\u4e86\u7d2b\u8272\u72ec\u89d2\u517d\u534f\u8bae"
        "\u7f16\u53f7\u7684\u53d6\u503c\u89c4\u5219\uff0c\u7f16\u53f7\u5f62\u5982 PU-7788-ZX\uff0c"
    ) * 6
    decoy = "\u7d2b\u8272"  # 紫色

    assert ngram_overlap(query, relevant) > ngram_overlap(query, decoy)
