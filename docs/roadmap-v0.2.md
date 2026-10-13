# cjkfold v0.2 — 从「形近」扩到「看不见」

> 设计稿 / 范围 / 验收标准。代码由本人实现，本文只定契约。
> 所有事实都附了可复现的命令，不是推测。

---

## 0. 现状盘点（0.1.1，实测）

| 层 | 内容 |
|---|---|
| 字符表 | `_table.py`，348 条：康熙部首 214 + 部首补充 114 + CJK 笔画 20 |
| 折叠 | `fold` / `has_lookalikes` / `iter_lookalikes` / `Lookalike` / `kind_of` |
| 排序 | `ngrams` / `ngram_overlap` / `exact_boost` |
| 管线适配 | `text_of` / `fold_document` / `fold_documents` / `rerank` |
| CLI | `check` / `fold`，支持 `-` 读 stdin、`--quiet`、`--max`，找到即 exit 1 |
| 测试 | **59 条**（`pytest -q`：`59 passed`），全绿 |

**表的时效性已核**：拉取当前 UCD（`EquivalentUnifiedIdeograph-18.0.0.txt`，2026-02-03）
按 `build_table.py` 的解析逻辑重新比对，**348 对 348，新增 0 / 消失 0 / 改指 0**。
表是新的，解析器是对的。

---

## 1. 四个缺口（均已实测确认）

### G1. CJK 笔画区：已声明支持的块里有 28 个报不出来

```python
from cjkfold import EQUIVALENT_IDEOGRAPH
block = [chr(c) for c in range(0x31C0, 0x31F0)]   # 48 个码位
len([c for c in block if c in EQUIVALENT_IDEOGRAPH])  # 20
```

`kind_of()` 已经返回 `"cjk-stroke"`，即**对外声称认识这个块**，但 `_FOLD` 里只有 20 个，
另外 28 个 `iter_lookalikes()` 永远不报。

**查证结论：这不是 bug。** 拆开看：

| 分类 | 数量 | 依据 |
|---|---|---|
| 有映射 | 20 | UCD 映射区 |
| Unicode 明说「无等价汉字」 | 18 | UCD 注释区（`# 31C0; CJK STROKE T` …） |
| 未分配码位 | 10 | `U+31E6`–`U+31EF` |

UCD 文件开头写得很明白：*"CJK radicals and CJK strokes for which no reasonably equivalent
CJK unified ideographs exist are listed as comments at the end of the file."*

所以要做的是**把边界写下来并用测试锁住**，不是自己编映射。`U+31C0` 长什么样、该折叠到谁，
Unicode 说没有答案，我们就不回答。

### G2. 不可见字符族：完全没人管，NFKC 也不管

```python
clean = "\u6570\u636e"        # 数据
dirty = "\u6570\u200b\u636e"  # 数<ZWSP>据

clean == dirty                                    # False
print(clean, dirty)                               # 数据 数据   ← 一模一样
unicodedata.normalize("NFKC", dirty) == clean     # False
fold(dirty) == clean                              # False
has_lookalikes(dirty)                             # False
len(list(iter_lookalikes(dirty)))                 # 0
```

**两个探测器全瞎。** 这一族比形近字符更毒：形近字符至少你盯着看能看出不对，这个
打印出来和正常字符串**完全无法区分**，`repr()` 才能看见。

这一族天然构成 v0.2 的叙事主线——它与 `fold()` 的命题是同一个：
**长得一样 / 看不见，但码位不同，于是比对悄悄失败。** 不是加一个新功能，是把同一个命题推到底。

> **但有个陷阱，必须写进设计：ZWJ 是承重的。**
> ```python
> family = "\U0001F468\u200D\U0001F469\u200D\U0001F467"  # 一家三口，5 个码位，渲染成一个字形
> family.replace("\u200d", "")                            # 3 个码位 —— 一个人变三个人
> ```
> 所以「删掉所有 Cf 字符」是错的。零宽字符里有一半可以删，另一半删了就改语义。

### G3. 「NFKC 才管」的那一族，没有诊断入口

`fold()` 故意不碰它们（README 有承诺，`docs/why-cjk-text-breaks.md` 也解释了
`NFKC('，；（）') == ',;()'` —— 中文标点变英文标点，对要展示/存储的文本是破坏性的）。
设计是对的。**但用户不知道自己踩了这些**，工具也不告诉他。

实测 `NFKC` 会改而 `fold` 不动的：全角字母数字 `U+FF21`、表意空格 `U+3000`、
兼容汉字 `U+F900`、不换行空格 `U+00A0`、谚文 `U+318D`。

### G4. `--version` 硬编码，与真实版本不符

```
$ cjkfold --version
cjkfold 0.1.0          ← cli.py:71 硬编码
$ python -c "import cjkfold; print(cjkfold.__version__)"
0.1.1
$ python -c "import importlib.metadata as m; print(m.version('cjkfold'))"
0.1.1
```

`tests/test_version.py` 把 `__init__.py` 和打包元数据钉在了一起——**但版本有三处，测试只盖了两处。**
测试写了，没盖到 CLI 那一处。对外打脸的那种小错，必须修，且修完要能证明修住了（见验收 A6）。

### G5. 非文本输入不设防：指向 PDF 会产出「自信的假阳性」

实测（真实文件，不是构造的）：

```
$ cjkfold check 作文急救-修错对照与安全骨架.pdf
作文急救-修错对照与安全骨架.pdf: 3 look-alike character(s) (3 radical-supplement)
    87:166   ⻱ U+2EF1 -> 龜 U+9F9C  (CJK RADICAL TURTLE)
    3193:13  ⻀ U+2EC0 -> 艹 U+8279  (CJK RADICAL GRASS THREE)
    4349:13  ⻀ U+2EC0 -> 艹 U+8279  (CJK RADICAL GRASS THREE)
```

**三条全是假的。** 该文件是 `PDF document, version 1.4, 2 pages`，335,682 字节。
`cli._read()` 是 `path.read_text(encoding="utf-8", errors="replace")`——**没有文件类型识别**，
把二进制当文本读了。

三条独立证据：

| 证据 | 内容 |
|---|---|
| 上下文是二进制垃圾 | `⻱` 偏移 13368 周围是 `\xfd\x17f\\…\x81\xf5\x89\x0b\x1d\x86*` |
| 同结构重复出现 | 两处 `⻀` 的 ±10 字节上下文**逐字节完全相同**（嵌入字体 / 共享对象）。散文不会这样重复，压缩流会 |
| 行列号本身也是假的 | 程序说 87 / 3193 / 4349 行，按字节扫是 67 / 2756 / 3761 行。`errors="replace"` 把无效字节序列塌缩成单个 `�`，字符位置与字节位置脱钩 |

**危险之处在于它长得像成功**：格式工整、退出码 1、看着就是"发现"。
而 `docs/why-cjk-text-breaks.md` 紧接着写「如果报了一堆 `U+2Fxx`/`U+2Exx`，那你现在的检索就是坏的」——
读者照做就会去追一个不存在的鬼。这就是 §5 里「误报是这类工具的头号死因」的活标本。

**顺带一个必须一起修的文档 bug**：`docs/why-cjk-text-breaks.md:246` 写的是

```bash
cjkfold check 你的资料.pdf            # 或者先把 PDF 抽成 txt
```

把 PDF 直接喂给它。全文只此一处（README 用的是 `.txt`，没这问题）。

**修法（判据已实测）**：

| 判据 | 该 PDF | 真文本（extracted.txt / zwsp.txt / README.md） |
|---|---|---|
| 含 NUL 字节 | **475** | 0 |
| 严格 UTF-8 解码 | **失败 @ 偏移 11** | 通过 |
| 已知二进制魔数 | **`%PDF-`** | 无 |

三条建议全用，各司其职：**NUL 兜底 → 严格解码负责"非 UTF-8 的文本" → 魔数负责给出人类可读的错因**。
命中时不要静默跳过，要报错并说明下一步：

```
extracted.pdf: 这看起来不是文本文件（PDF）。cjkfold 只读文本。
               先把 PDF 抽成 txt：pdftotext extracted.pdf extracted.txt
```

**验收**：
- G5-1 对上述 PDF，`check` 必须**拒绝**并 exit 2（区别于"发现"的 exit 1），不打印任何 finding。
- G5-2 对 extracted.txt / zwsp.txt / README.md 三个对照，行为与现在**逐字节一致**（这是防误伤）。
- G5-3 三个判据各自单独命中时都能拦住（写三条用例，别只测"三个一起"）。
- G5-4 非 UTF-8 的**真文本**（如 GBK 编码的 .txt）走的是"严格解码失败"那条，报错文案要说清
  是编码问题，而不是"这是二进制"——两者对用户的下一步动作完全不同。
- G5-5 文章第 246 行改掉：先抽文本再 check，别再让人喂 PDF。
- G5-6 （可选，但推荐）`errors="replace"` 换成显式策略：既然报出来的行列号在非 UTF-8 输入上
  本就无意义，不如在解码阶段就拒绝，而不是产出一份坐标不可信的报告。

---

## 2. 设计稿

### 2.1 核心决策：`fold()` 一个字符都不改，另开一层「只诊断」

理由三条，按重要性排：

1. **`fold()` 的契约已经对外承诺过了。** README：「deliberately not an NFKC pass… safe to
   apply to text that is still going to be stored or displayed」。改它 = 破坏兼容 + 悄悄改动用户数据。
2. **三种字符，三种命运，一个函数干不了。**

   | 族 | 该做什么 | 为什么不能混进 `fold()` |
   |---|---|---|
   | 形近（康熙/部首补充/笔画） | 替换成对应汉字 | 已经是 `fold()` 在做的事 |
   | NFKC 族（全角/兼容/空格族） | 折叠，但**会连带改中文标点** | 必须由调用方显式决定 |
   | 不可见族 | 一半可删、一半删了改语义（ZWJ/VS/bidi） | 自动处理必然出错 |

3. **工具要能说「我不确定，你来判断」。** 假装全自动，比承认边界更伤信誉。

因此 v0.2 增加的是**读**的能力（`scan`）加**两个显式、独立的写操作**（`normalize` / `strip_invisible`），
而不是把 `fold()` 撑大。

### 2.2 新增模块 `cjkfold/diagnose.py`

```python
Finding                      # frozen dataclass
    index: int               # 0-based，与 Lookalike.index 同义
    line: int                # 1-based
    column: int              # 1-based
    char: str
    codepoint: int
    class_: str              # "lookalike" | "compat" | "invisible" | "broken"
    fixable: str             # "fold" | "nfkc" | "strip" | "manual"
    replacement: str | None  # 只有 fixable 为 fold/nfkc 时非 None
    note: str                # 人话，说明为什么这么判

    codepoint_label -> "U+200B"      # 跟 Lookalike 保持一致
    replacement_label -> "U+8272" | None

scan(text) -> Iterator[Finding]
scan_stats(text) -> dict[str, int]       # 按 class_ 计数，给 CLI 和测试用
```

**`fixable` 的语义是这份设计的骨**：

| 值 | 含义 | 出现在哪些字符上 |
|---|---|---|
| `fold` | cjkfold 能安全修 | 形近字符（复用现有表） |
| `nfkc` | 需要 NFKC；`fold` 故意不做 | 全角/兼容/空格族 |
| `strip` | 删掉是安全的 | ZWSP `U+200B`、BOM `U+FEFF`、软连字符 `U+00AD`、词连接符 `U+2060` |
| `manual` | **不能自动修，必须人看** | ZWJ `U+200D`、ZWNJ `U+200C`、变体选择符 `U+FE00–FE0F`/`U+E0100–E01EF`、bidi 控制符 `U+200E/200F/202A–202E/2066–2069`、`U+FFFD`、私用区 |

`manual` 这一类是重点：明确表达「我不确定」，而不是假装能全自动。

### 2.3 分类判定的实现原则

- **`lookalike` 复用 `iter_lookalikes()`，不要重写游标。**
  行/列推进逻辑只在 `normalize.py` 里存在一份。两份游标 = 一定会漂。
- **`compat` 用实时 NFKC 判定，不建表**：
  ```python
  if unicodedata.normalize("NFKC", char) != char and char not in _FOLD:
      # class_="compat", fixable="nfkc"
  ```
  理由：NFKC 的答案跟着宿主 Python 的 Unicode 版本走。硬编码一张 compat 表，
  就会重演 README 里已记录的那个坑（Python 3.9 只带 Unicode 13）。
- **`invisible` 用显式白名单 + note**，不用「category 是 Cf 就报」。
  因为 `Cf` 里恰好混着 ZWJ/ZWNJ 这种删不得的；而且白名单能把「为什么」写进 `note`。
- **顺序**：一次遍历产出全部，不按族各扫一遍（`scan` 要能跑 1MB 文本）。

### 2.4 CLI

```
cjkfold check   FILE...    [冻结] 行为不许变，output 逐字节冻结
cjkfold scan    FILE...    [新增] 全类体检，只读
cjkfold fold    FILE...    [冻结]
```

**`normalize` / `strip_invisible` 不暴露成子命令。** 理由：`fold -w` 已经是就地改写，
再给两个破坏性更强的命令，等于给用户一把能一条命令毁掉整个语料的枪。
这两个能力只走 Python API，让调用方在代码里显式写下自己的决定。

`scan` 的退出码：**默认 0**，有 findings 也返回 0；加 `--strict` 才在发现 `lookalike`/`compat`
时返回 1。理由：`scan` 是体检报告，不是门禁；里面混着 `manual` 项（ZWJ 等），
拿它拦 CI 会把正常语料判死。要门禁请用 `check`。

`scan` 输出设计（**这块要能截图，是 README 的素材**）：

```
$ cjkfold scan corpus.txt
corpus.txt  2,046 characters  4 findings

  invisible  2
    4:17  U+200B ZERO WIDTH SPACE             strip
          「数​据」 prints exactly like 「数据」
   19:1   U+FEFF ZERO WIDTH NO-BREAK SPACE    strip
  lookalike  1
   12:4  U+2F8A -> 色 U+8272                  fold    (KANGXI RADICAL COLOR)
  compat      1
   31:8  U+FF21 -> A U+0041                  nfkc

  fixable   invisible: strip    lookalike: fold    compat: nfkc
  see also  cjkfold scan --classes invisible
            cjkfold fold --help
```

新增选项：`--classes {lookalike,compat,invisible,broken}`（可多选）、`--json`。

### 2.5 两个显式的写操作（仅 API）

```python
normalize(text, *, keep_punctuation=True)
    # NFKC 那族。keep_punctuation=True 时保护 ，。；：（）「」等全角标点不被改成 ASCII
    # —— 这是在替调用方挡一个已知的坑，不是替他做决定

strip_invisible(text, *, policy="safe")
    # policy="safe"   只删 fixable="strip" 那批（ZWSP/BOM/软连字符/词连接符）
    # policy="all"    连 ZWJ/ZWNJ/VS/bidi 一起删 —— 名字里带 all 就是警告：
    #                 会破坏 emoji 序列与印度文连写
    # 默认 safe。默认值的选择本身就是文档。
```

---

## 3. 范围

### 做

1. `diagnose.py`：`Finding` / `scan` / `scan_stats`
2. `_classes.py`：不可见字符白名单 + note 文案（手写，不是生成的）
3. CLI `scan`（含 `--classes` / `--json` / `--strict`）
4. 修 G4：版本单一来源
5. 把 G1 的边界写进文档 + 测试锁住
6. 文档：README 新增「看不见的那一类」、中文简述同步、`docs/` 新增一节记 G1 的查证过程
7. 版本 → 0.2.0，发 PyPI

### 不做（写下来是为了防止范围膨胀）

- **不改 `fold()` 的语义与签名**，一个字都不改
- 不做繁简转换（README 已声明是另一个问题）
- 不做异体字 / IVS 字形选择（`U+2F800` 区 NFKC 已管）
- 不为笔画区那 18 个「无等价」字符自己编映射
- 不把 `normalize` / `strip_invisible` 做成 CLI 子命令
- 不自动「修复整个语料库」（危险；留给用户组合 scan + 管道）
- 不引入任何运行时依赖（零依赖是卖点，`requires` 必须保持空）
- 不改 `exact_boost` / `rerank` 的签名
- 不做 GUI / Web / 服务端

---

## 4. 验收标准

每条都能跑、能看结果，不靠「应该好了」。

### A. 回归（先证明没弄坏旧的）

| # | 验收项 | 怎么验 |
|---|---|---|
| A1 | 59 条测试全绿，**一条断言都不许改** | `.venv/bin/python -m pytest -q` → `59 passed` |
| A2 | `check` 输出逐字节不变 | **先建 `tests/fixtures/`**（当前不存在），放三个文件：`clean.txt`、`lookalike.txt`、`zwsp.txt`。改前改后各跑一次存盘，`diff` 为空。参照物：`lookalike.txt` 用 `标准颜⾊按钮⻆色` / `第一节的⺮字头` 两行，`check` 应报 3 条（1 kangxi, 2 radical-supplement），位置 1:4 / 1:7 / 2:5 —— 与 README 文档块逐字节一致（已实测）。 |
| A3 | `fold("标准颜⾊值与⻆色按钮") == "标准颜色值与角色按钮"` | 写进测试 |
| A4 | `fold(fold(s)) == fold(s)`，且无可折叠字符时返回原对象 | 写进测试 |
| A5 | 零依赖 | 干净 venv 里 `pip install cjkfold` 后 `import cjkfold` 成功；`importlib.metadata.requires("cjkfold")` 为空 |
| A6 | **版本三处一致，且测试真的盖住 CLI** | 把 `cli.py` 的版本改回硬编码 `0.1.0`，**测试必须变红**；改回来自动绿 |

> A6 是这条的验收关键。只断言「输出等于 0.1.1」不够——那只是把硬编码换了个值。
> 要证明 `cli.py` 是从单一来源读的，得靠一次变异测试。

### B. 新能力

| # | 验收项 | 期望 |
|---|---|---|
| B1 | `scan("数\u200b据")` | 1 条，`class_="invisible"`、`fixable="strip"`、`codepoint=0x200B` |
| B2 | `scan("数据")` | **0 条**（误报比漏报更伤工具信誉） |
| B3 | `scan("\uff21")` | `class_="compat"`、`fixable="nfkc"`、`replacement="A"` |
| B4 | `scan("⾊")` | `class_="lookalike"`、`fixable="fold"`，与 `check` 结论一致 |
| B5 | **`scan` 对一家三口 emoji 报 ZWJ 为 `manual`，不是 `strip`** | 这条是设计的守门测试。它红了说明「ZWJ 承重」这个判断被打破了 |
| B6 | 位置信息与 `iter_lookalikes` 同规则 | 同一个输入的 line/column 必须逐条相等（断言两者一致，而不是各写各的期望值） |
| B7 | `scan` 在 1MB 中文文本上 < 1s | 记基线，防 O(n²) |
| B8 | `scan_stats` 的计数与 `len(list(scan(...)))` 相等 | 写进测试 |

### C. 边界与健壮

| # | 验收项 |
|---|---|
| C1 | 空串、纯 ASCII、非 BMP 字符、`U+FFFD`、私用区 → 不抛异常 |
| C2 | `scan` 对干净文件 exit 0；`--strict` 只在 `lookalike`/`compat` 存在时 exit 1 |
| C3 | `scan` 与 `check` 对同一文件，`lookalike` 类结论完全一致 |
| C4 | 类级不变量：`fixable="strip"` 的字符集合里**不含** ZWJ/ZWNJ/VS/bidi（写成断言，不是注释） |

### D. 文档

| # | 验收项 |
|---|---|
| D1 | README 新增「看不见的那一类」，含 ZWSP 那个例子和 `'数据' == '数\u200b据'` 的结果 |
| D1b | **修 README 那段示例输出**：`cjkfold check extracted.txt` 的代码块漏了程序真正打印的最后一行 `3 character(s) would change under \`cjkfold fold\`.`。真跑一遍整段复制过去，别手抄——手抄正是它当初漏掉这一行的原因。 |
| D2 | `docs/` 新文或新节：记 G1 的查证过程——**怀疑是 bug → 查 UCD → 结论是边界** |
| D3 | 中文简述同步 |
| D4 | `scan` 的实际输出贴进 README（截图或代码块） |

> D2 值得单独做。那条「先查证再下结论」的过程比修一个 bug 值钱：
> 它展示的是判断力，而且**没人会去查的东西你去查了**。

### E. 发布

| # | 验收项 |
|---|---|
| E1 | 版本 0.2.0；CHANGELOG 三条：新增 `scan`、新增 `normalize`/`strip_invisible`、修 `--version` |
| E2 | 全新 venv：`pip install cjkfold==0.2.0` → `cjkfold scan 任意文件` 可用 |
| E3 | PyPI 页面 description 更新（keywords 加 `zero-width`, `invisible-characters`, `watermark`） |

---

## 5. 测试策略（不做 PDF 语料也能测）

- 样本**写死在测试里，用 `\u` 转义**，不依赖外部文件。理由：转义写法让「看不见的字符」
  在源码里看得见——这正是这个库的命题，测试本身也该遵守。
- 每个族至少一条正例 + **一条干净字符串的负例**。误报是这类工具的头号死因：
  一个把正常中文标点报成问题的工具，用户会当场卸载。
- B6 那条要横向断言（两个 API 对同一输入一致），而不是分别对期望值断言——
  否则两份游标各自漂了，测试还是绿的。
- 变异测试（A6）是唯一能证明「真的从单一来源读」的手段。

---

## 6. 建议的提交顺序

一条一提交，每条都能独立回滚：

1. `fix: read --version from the package, not a literal` + 变异测试（先修这个，独立、零风险）
2. `docs: record the CJK Strokes boundary (18 chars Unicode says have no equivalent)`
3. `feat: diagnose.py — Finding / scan / scan_stats`（只加，不接线）
4. `feat: cli scan`（接上 CLI）
5. `feat: normalize() / strip_invisible()`（两个显式写操作）
6. `docs: README — the invisible twin`
7. `release: 0.2.0`
