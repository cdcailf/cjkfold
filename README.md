# cjkfold

Text pulled out of a PDF often contains characters that **look** like ordinary
Han characters but are not them. Comparison against them quietly fails.

```
⻆  U+2EC6  CJK RADICAL SIMPLIFIED HORN   renders as  角  U+89D2
⾊  U+2F8A  KANGXI RADICAL COLOR          renders as  色  U+8272
⺮  U+2EAE  CJK RADICAL BAMBOO            folds to    𥫗  U+25AD7
```

`cjkfold` folds them back onto the characters you meant:

```python
from cjkfold import fold

fold("标准颜⾊值与⻆色按钮")
# '标准颜色值与角色按钮'

"颜色" in "标准颜⾊值"          # False  ← the bug
"颜色" in fold("标准颜⾊值")     # True
```

Zero runtime dependencies. Pure functions. Python 3.9+.

---

**背景阅读 / Background:** [PDF 抽出来的中文，为什么搜不到](docs/why-cjk-text-breaks.md)
—— 完整的排查经过（中文），包括我自己踩的四个坑。
社区版：[掘金](https://juejin.cn/post/7695671592383807542)

**Built on this:** [corpusfold](https://github.com/cdcailf/corpusfold) — this
character layer wired into a full PDF → knowledge-base pipeline (抽取 / 分栏 /
表格 / 分块 / 混合检索).

## The problem

Nothing raises. The text displays correctly, because the glyphs really are
identical. What breaks is everything downstream that compares characters:

- `"紫色" in text` returns `False` for a document that shows 紫色
- a keyword search misses
- a vector retriever ranks an unrelated *short* document above the one that
  contains the query verbatim, because a short document's embedding is tighter
  and scores a higher cosine — measured on a real corpus, the relevant document
  scored **0.29** against a decoy's **0.36**
- deduplication, caching and ground-truth checks all start disagreeing

## Why NFKC is not enough

The reflex is `unicodedata.normalize("NFKC", text)`. It handles the **Kangxi
Radicals** block completely — all 214 characters carry compatibility
decompositions — and then stops:

| Block | Characters | Repaired by NFKC | Repaired by cjkfold |
|---|---|---|---|
| Kangxi Radicals `U+2F00–U+2FDF` | 214 | **214** | 214 |
| CJK Radicals Supplement `U+2E80–U+2EFF` | 115 | **2** | **114** |

Unicode withholds compatibility mappings in the supplement block *on purpose*:
those glyphs are distinct encoded radicals, not compatibility variants of an
existing character. So NFKC leaves 113 of the 115 standing.

`cjkfold` closes that gap with the `EquivalentUnifiedIdeograph` property from
the Unicode Character Database (Unicode 15.1+), which maps 114 of them onto a
unified ideograph. The one remainder, `⺀ U+2E80 CJK RADICAL REPEAT`, has no
ideograph equivalent and is left alone.

## Install

```bash
pip install cjkfold
```

## Usage

```python
from cjkfold import fold, has_lookalikes, iter_lookalikes

fold("紫⾊的⻆落")            # '紫色的角落'
fold("普通文本")              # unchanged; returns the same object

has_lookalikes("⻆")           # True
has_lookalikes("角")           # False

for item in iter_lookalikes("第一行\n第⼆行⻆"):
    print(item)
# 2:2  ⼆ U+2F06 -> 二 U+4E8C  (KANGXI RADICAL TWO)
# 2:4  ⻆ U+2EC6 -> 角 U+89D2  (CJK RADICAL SIMPLIFIED HORN)
```

`fold()` is idempotent, and it is deliberately **not** an NFKC pass: it will
not touch full-width punctuation (`，` `；` `（` `）`), compatibility characters
or ligatures, so it is safe to apply to text that is still going to be stored or
displayed. Combine with NFKC yourself if you want both:

```python
import unicodedata
clean = fold(unicodedata.normalize("NFKC", text))
```

### Command line

```bash
cjkfold check document.txt      # report look-alikes, exit 1 if any (CI-friendly)
cjkfold check --quiet docs/*.txt
cjkfold fold document.txt       # print the folded text
cjkfold fold -w document.txt    # rewrite in place
cat document.txt | cjkfold check -
```

Exit codes: `0` clean, `1` look-alike characters found, `2` the input is not a text
file (or not UTF-8) and nothing was scanned. `2` is separate from `1` on purpose —
"I found something" and "I could not look" are different answers. Pass a PDF and it
will say so and hand you the `pdftotext` command, instead of reporting phantom
findings from binary data.

```
$ cjkfold check extracted.txt
extracted.txt: 3 look-alike character(s) (1 kangxi, 2 radical-supplement)
    1:4  ⾊ U+2F8A -> 色 U+8272  (KANGXI RADICAL COLOR)
    1:7  ⻆ U+2EC6 -> 角 U+89D2  (CJK RADICAL SIMPLIFIED HORN)
    2:5  ⺮ U+2EAE -> 𥫗 U+25AD7  (CJK RADICAL BAMBOO)
```

Drop `cjkfold check` into an ingest pipeline to catch extraction regressions
before they reach the index.

## Retrieval helper

Folding is the fix; ranking is the follow-up. Dense retrieval is bad at literal
tokens, so `exact_boost` adds a bonus for query n-grams that appear verbatim in a
document:

```python
from cjkfold import exact_boost

score = vector_similarity(query, document) + exact_boost(query, document)
```

Both sides are folded inside the helper. That is not a convenience — folding the
index but not the query (or the reverse) silently disables the whole mechanism,
because nothing ever matches. The API gives you no way to get it wrong.

Queries shorter than the shingle size fall back to a containment test, so a
two-character query is not silently scored zero.

## Wiring it into a pipeline

Three touch points, zero framework dependencies:

```python
from cjkfold import fold, fold_documents, rerank

# 1. on the way in -- clean the corpus before it is embedded
documents = fold_documents(loader.load())

# 2. on the way out -- fold the query so it can match
hits = vectorstore.similarity_search_with_score(fold(question), k=20)

# 3. before you trust the order -- restore the verbatim matches
documents, scores = zip(*hits)
for document, score in rerank(question, documents, scores):
    ...
```

`fold_documents` and `rerank` recognise LangChain documents (`page_content`),
LlamaIndex nodes (`text`) and plain strings -- and import none of them. Making
you install a framework in order to fold a string would be a bad trade:
framework APIs move, string folding does not.

## Caveats

- **Glyph folding only.** No traditional⇄simplified conversion, no z-variant
  normalisation. Those are different problems with different trade-offs.
- **Table follows the latest UCD**, which can run ahead of the `unicodedata`
  database bundled with an older Python — 3.9 ships Unicode 13, where one target
  (`U+2B739`) is not yet assigned. Folding is unaffected (it is a plain code point
  substitution), but `unicodedata.name()` on that result will come up empty.
- **Existing stored text is not retroactively repaired.** Fold on write; if you
  have already indexed unfolded text, re-ingest or re-fold it.
- Characters above the BMP are written as `\U000xxxxx` in the table. A `\uXXXX`
  escape silently truncates there and turns one character into two — the table
  test suite guards against exactly that regression.

## Regenerating the table

`src/cjkfold/_table.py` is generated, never hand-edited:

```bash
python scripts/build_table.py                  # fetch from unicode.org
python scripts/build_table.py CJKRadicals.txt  # or use a local copy
```

## Development

```bash
uv venv .venv --python 3.9
uv pip install -e ".[dev]"
.venv/bin/python -m pytest
```

## 中文简述

PDF 抽出来的中文常常混着**形近异码**字符：`⻆` 和 `角` 长得一样、码位不同，于是
`"颜色" in 文本` 返回 `False`，检索排错、去重失效、缓存打不中。

`unicodedata.normalize("NFKC", ...)` 只能解决康熙部首区（214 个全都能还原），
**解决不了 CJK 部首补充区**——那个区 115 个字符里 NFKC 只救得了 2 个。

`cjkfold` 用 Unicode 官方的 `EquivalentUnifiedIdeograph` 属性补上这个缺口，
115 个里能还原 114 个。同时提供 `exact_boost()`，把"查询片段在文档里逐字命中"
补进向量相似度，避免短文档靠余弦虚高把真正命中的长文档挤下去。

## License

MIT
