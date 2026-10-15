# cjkfold

[![tests](https://github.com/cdcailf/cjkfold/actions/workflows/tests.yml/badge.svg)](https://github.com/cdcailf/cjkfold/actions/workflows/tests.yml)

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

## The characters that never show up

There is a second family, and it is harder to catch. A zero-width space leaves no
glyph at all, so two strings that differ only by it look identical:

    数据
    数\u200b据

```python
"数\u200b据" == "数据"                                  # False
unicodedata.normalize("NFKC", "数\u200b据") == "数据"     # False as well
```

`fold()` does not repair these, deliberately: half the family is load-bearing. ZWJ
`U+200D` is what holds an emoji sequence together — 👨‍👩‍👧 is five code points rendered as
one glyph, and deleting the joiners does not tidy the text up, it turns one family
into three people.

`check` looks for the first family only, so a file full of zero-width spaces comes
back `clean`. `scan` looks at every family and says what to do with each finding:

```
$ cjkfold scan document.txt
document.txt  21 characters  5 findings

  lookalike  1
      1:4  U+2F8A  -> 色 U+8272                   fold   (KANGXI RADICAL COLOR)
           renders exactly like 色, but sits on a separate kangxi code point

  compat  1
      2:5  U+FF21  -> A U+0041                    nfkc   (FULLWIDTH LATIN CAPITAL LETTER A)
           NFKC would rewrite this; fold() leaves it alone on purpose, so the decision stays with the caller

  invisible  3
      3:2  U+200B  ZERO WIDTH SPACE               strip
           prints as nothing at all -- two strings that differ only by this character look identical
      4:2  U+200D  ZERO WIDTH JOINER              manual
           zero width joiner: it holds emoji sequences together -- a family of three is five code points, and deleting the joiners leaves three separate people
      4:4  U+200D  ZERO WIDTH JOINER              manual
           (same character as 4:2)

  fixable   lookalike: fold    compat: nfkc    invisible: strip, manual
  see also  cjkfold scan --classes invisible
            cjkfold fold --help
```

The reason is printed once per character rather than once per occurrence: an
emoji-heavy document can hold hundreds of joiners, and repeating the same sentence
hundreds of times buries the lines that differ.

The `fixable` column is the point of the design:

| | |
|---|---|
| `fold` | cjkfold can replace it: a look-alike glyph |
| `nfkc` | NFKC would rewrite it, and `fold()` deliberately leaves that decision to the caller |
| `strip` | safe to delete — it never shows and carries nothing |
| `manual` | **do not delete it without looking.** ZWJ, ZWNJ, variation selectors and bidi controls change the meaning or the rendering of the text around them |

There is a fourth class, and it is damage rather than a difference. `U+FFFD` is not
a character, it is a record of one that could not be read — something upstream
already failed, and the failure is still sitting in your text. A private use code
point is the opposite: something upstream *succeeded* in writing a character this
machine cannot name, and nothing defines what it looks like, so whichever font is
doing the rendering decides — it can come out as a box, as nothing at all, or as a
glyph that means something else entirely. Both are reported; neither can be
repaired.

So `scan` exits `0` even when it finds something: it is a report, not a gate. It has
to be — a gate that fails on a load-bearing joiner fails on ordinary emoji. Pass
`--strict` if you have read the findings and want a gate anyway.

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

### The other two rewrites

`fold()` is no longer the only write, but it is still the only one the command line
will do for you. The other two are explicit API calls, and that is on purpose:
`fold -w` already rewrites files in place, and two more destructive operations
behind flags would be a loaded gun pointed at a corpus.

```python
from cjkfold import fold, normalize, strip_invisible

fold("标准颜⾊值")                          # '标准颜色值'  the look-alike layer
normalize("Ａ，b")                          # 'A，b'        NFKC, punctuation spared
normalize("Ａ，b", keep_punctuation=False)   # 'A,b'         ...or not spared

FAMILY = "\U0001F468\u200D\U0001F469\u200D\U0001F467"   # 5 code points, one glyph

strip_invisible("数\u200b据")               # '数据'        safe: ZWSP, BOM, soft hyphen, word joiner
strip_invisible(FAMILY)                    # unchanged     -- the joiners carry meaning
strip_invisible(FAMILY, policy="all")      # 3 code points -- three separate people
```

`normalize()` spares full-width punctuation by default, because NFKC turns `，`
into `,` — that rewrites the sentence rather than repairing it. `strip_invisible()`
defaults to `safe`, because the other half of the invisible family is load-bearing;
there is no `policy="smart"`, because no such thing exists.

The modules are `cjkfold.folding` and `cjkfold.rewrite`, so that every name means
exactly one thing: `cjkfold.normalize` is the function, `cjkfold.folding` is the
module. Until 0.4.0 both were called `normalize`, which made
`import cjkfold.normalize as m` hand you a function instead of the module — and
`import a.b as c` means `c = a.b`, so `m.fold` raised `AttributeError`. Renaming
the module is what fixed it.

### Command line

```bash
cjkfold check document.txt      # report look-alikes, exit 1 if any (CI-friendly)
cjkfold check --quiet docs/*.txt
cjkfold scan document.txt       # report every class of finding, exit 0 (it is a report)
cjkfold scan corpus/            # walk a directory; non-text files are skipped and counted
cjkfold scan --strict corpus.txt    # ...or exit 1 when a foldable/compat character is found
cjkfold scan --json corpus.txt  # one JSON object per file
cjkfold fold document.txt       # print the folded text
cjkfold fold -w document.txt    # rewrite in place
cat document.txt | cjkfold check -
```

Exit codes: `0` clean, `1` look-alike characters found (`check`), or findings under
`scan --strict`, `2` the input is not a text file (or not UTF-8) and nothing was
scanned. `2` is separate from `1` on purpose — "I found something" and "I could not
look" are different answers. Pass a PDF and it will say so and hand you the
`pdftotext` command, instead of reporting phantom findings from binary data. `scan`
finds things and still exits `0`; the section above is why.

```
$ cjkfold check extracted.txt
extracted.txt: 3 look-alike character(s) (1 kangxi, 2 radical-supplement)
    1:4  ⾊ U+2F8A -> 色 U+8272  (KANGXI RADICAL COLOR)
    1:7  ⻆ U+2EC6 -> 角 U+89D2  (CJK RADICAL SIMPLIFIED HORN)
    2:5  ⺮ U+2EAE -> 𥫗 U+25AD7  (CJK RADICAL BAMBOO)

3 character(s) would change under `cjkfold fold`.
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

`pytest` tests the source tree. `scripts/acceptance.py` tests a *release* — the
things a wheel can break that the source tree cannot show you. Install from PyPI
into a throwaway environment, run it there, and it exercises every name in
`__all__`, every subcommand, the import paths and the dependency list:

```bash
uv venv /tmp/accept --python 3.9
uv pip install --python /tmp/accept/bin/python cjkfold
/tmp/accept/bin/python scripts/acceptance.py
```

## 中文简述

PDF 抽出来的中文常常混着**形近异码**字符：`⻆` 和 `角` 长得一样、码位不同，于是
`"颜色" in 文本` 返回 `False`，检索排错、去重失效、缓存打不中。

`unicodedata.normalize("NFKC", ...)` 只能解决康熙部首区（214 个全都能还原），
**解决不了 CJK 部首补充区**——那个区 115 个字符里 NFKC 只救得了 2 个。

`cjkfold` 用 Unicode 官方的 `EquivalentUnifiedIdeograph` 属性补上这个缺口，
115 个里能还原 114 个。同时提供 `exact_boost()`，把"查询片段在文档里逐字命中"
补进向量相似度，避免短文档靠余弦虚高把真正命中的长文档挤下去。

还有第二族，比形近更难发现：**看不见的字符**——零宽空格、bidi 控制符、变体选择符。
它们打印出来和正常文本一模一样，`fold()` 不碰（这一族一半是承重的：emoji 序列里的
ZWJ 删掉，一家三口就变成三个人），`NFKC` 也管不着。

`cjkfold check` 只找第一族，给它一个塞满零宽空格的文件，它会说 `clean`；
`cjkfold scan` 三类都看，并对每条标注处置：`fold`（可以替换）/ `nfkc`（NFKC 才管，
`fold()` 故意不做）/ `strip`（删掉安全）/ `manual`（**不许自动改，你自己看**）。
`scan` 默认退出码是 `0`：它是体检报告，不是门禁——正常语料里一个 emoji 就带两个 ZWJ，
拿它拦 CI 会把好文档判死；确实想要门禁就加 `--strict`。它也能直接吃目录
（`cjkfold scan corpus/`），非文本文件跳过并计数。

第四类不是"不一样"而是"坏了"：`U+FFFD` 是"有一个字没能读出来"的记录，
私用区则相反——上游**成功**写进了一个这台机器叫不出名字的字，而它长什么样由读它的
字体决定，可以是个方框、可以是空白、也可以长得像别的字。两类都只能报，不能修。

三个写操作各管一件事，互不调用：`fold()` 管形近、`normalize()` 管 NFKC 那一族
（默认护住全角标点，否则一句中文的逗号全变英文）、`strip_invisible()` 管看不见的那一族
（默认 `safe`，只删删了不心疼的；`policy="all"` 连 ZWJ 一起删，一家三口就变三个人）。
后两个只走 Python API，不给命令行入口——`fold -w` 已经是就地改写，再递两把更狠的扳机不合算。

子模块叫 `cjkfold.folding` 和 `cjkfold.rewrite`，这样每个名字只指一样东西：
`cjkfold.normalize` 是函数，`cjkfold.folding` 是模块。0.4.0 之前两者同名，
于是 `import cjkfold.normalize as m` 拿到的是函数而不是模块（`import a.b as c`
等价于 `c = a.b`），`m.fold` 直接 AttributeError。把子模块改名才算真修好。

## License

MIT
