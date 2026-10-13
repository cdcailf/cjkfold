"""Framework-agnostic adapters -- no framework is imported by this test module."""

from __future__ import annotations

import pytest

from cjkfold import fold, fold_documents, rerank, text_of

RADICAL_HORN = "\u2ec6"  # ⻆ looks like 角
KANGXI_COLOR = "\u2f8a"  # ⾊ looks like 色


class LangChainDocument:
    """Stands in for langchain_core.documents.Document."""

    def __init__(self, page_content: str, metadata: dict | None = None):
        self.page_content = page_content
        self.metadata = metadata or {}


class LlamaIndexNode:
    """Stands in for llama_index TextNode."""

    def __init__(self, text: str, metadata: dict | None = None):
        self.text = text
        self.metadata = metadata or {}


def test_text_of_recognises_strings():
    assert text_of("hello") == "hello"


def test_text_of_recognises_langchain_and_llamaindex_shapes():
    assert text_of(LangChainDocument("abc")) == "abc"
    assert text_of(LlamaIndexNode("def")) == "def"


def test_text_of_rejects_objects_without_text():
    class Opaque:
        pass

    with pytest.raises(TypeError, match="cannot find text"):
        text_of(Opaque())


def test_fold_documents_folds_page_content():
    docs = [LangChainDocument(f"标准颜{KANGXI_COLOR}值"), LangChainDocument("干净文本")]
    result = fold_documents(docs)

    assert [d.page_content for d in result] == ["标准颜色值", "干净文本"]


def test_fold_documents_handles_llamaindex_nodes():
    nodes = [LlamaIndexNode(f"三{RADICAL_HORN}形")]
    assert fold_documents(nodes)[0].text == "三角形"


def test_fold_documents_leaves_metadata_alone():
    docs = [LangChainDocument(f"颜{KANGXI_COLOR}", metadata={"source": f"颜{KANGXI_COLOR}.pdf"})]
    result = fold_documents(docs)

    assert result[0].page_content == "颜色"
    assert result[0].metadata == {"source": f"颜{KANGXI_COLOR}.pdf"}  # untouched on purpose


def test_fold_documents_does_not_mutate_by_default():
    original = LangChainDocument(f"颜{KANGXI_COLOR}")
    fold_documents([original])

    assert original.page_content == f"颜{KANGXI_COLOR}"


def test_fold_documents_can_mutate_in_place():
    original = LangChainDocument(f"颜{KANGXI_COLOR}")
    fold_documents([original], inplace=True)

    assert original.page_content == "颜色"


def test_fold_documents_accepts_plain_strings():
    assert fold_documents(["ab", "cd"]) == ["ab", "cd"]


def test_fold_documents_is_idempotent():
    docs = [LangChainDocument(f"颜{KANGXI_COLOR}")]
    once = fold_documents(docs)
    twice = fold_documents(once)
    assert [d.page_content for d in twice] == ["颜色"]


def test_rerank_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        rerank("q", ["a", "b"], [0.1])


def test_rerank_promotes_the_document_that_matches_verbatim():
    """The ranking inversion: a short decoy outscores the real hit on vectors alone."""
    # A look-alike character sits inside the relevant passage, so the vector
    # store never saw the query literally -- and the decoy is short, so its
    # cosine similarity is inflated.
    relevant = (
        f"本文档定义了紫色独角兽协议的编号规则，编号形如 PU-7788-ZX，"
        f"并给出侧{RADICAL_HORN}命名约定。"
    ) * 4
    decoy = "紫色"

    query = "紫色独角兽协议编号"
    documents = [decoy, relevant]
    vector_scores = [0.41, 0.29]  # decoy wins on vectors alone

    ranked = rerank(query, documents, vector_scores)

    assert ranked[0][0] is relevant          # promoted above the decoy
    assert ranked[0][1] > vector_scores[1]   # because the boost was added
    assert ranked[1][0] is decoy
    assert ranked[1][1] == pytest.approx(vector_scores[0])  # decoy gained nothing


def test_rerank_keeps_vector_scores_when_nothing_matches():
    documents = ["完全无关的文本", "另一段无关的话"]
    scores = [0.5, 0.4]
    combined = rerank("紫色独角兽协议编号", documents, scores)

    assert [round(s, 6) for _, s in combined] == [0.5, 0.4]


def test_rerank_works_on_plain_strings_and_object_documents():
    doc = LangChainDocument(f"标准颜{KANGXI_COLOR}值")
    combined = rerank("颜色", [doc, "standard"], [0.1, 0.2])

    assert combined[0][0] is doc
    assert combined[0][1] == pytest.approx(0.35)  # 0.1 + the full cap
    assert combined[1] == ("standard", 0.2)


def test_rerank_query_is_folded():
    """A query typed with a look-alike must still hit ordinary document text."""
    doc = "本文档给出角色表的编号规则"
    combined = rerank(f"角{RADICAL_HORN}表的编号", [doc], [0.0])
    assert combined[0][1] > 0.0


def test_fold_is_reexported_for_convenience():
    assert fold(f"颜{KANGXI_COLOR}") == "颜色"
