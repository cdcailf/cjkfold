"""Acceptance run: every public name and every subcommand, from a PyPI install.

Run this with a Python that has cjkfold installed *from PyPI* -- not from the
source tree.  Anything that passes here works for a stranger who just ran
`pip install cjkfold`.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}")
    if not condition:
        FAILURES.append(label)
        if detail:
            print(f"         {detail}")


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "cjkfold", *args], capture_output=True, text=True
    )


# Written as escapes, always.
KANGXI_COLOR = "\u2f8a"  # ⾊
RADICAL_HORN = "\u2ec6"  # ⻆
ZWSP = "\u200b"
ZWSP_JOINER = "\u200d"
FAMILY = "\U0001f468\u200d\U0001f469\u200d\U0001f467"
SHU = "\u6570"  # 数
JU = "\u636e"  # 据
FULLWIDTH_A = "\uff21"
FULLWIDTH_COMMA = "\uff0c"

print(f"python  : {sys.version.split()[0]}  ({sys.executable})")

import cjkfold  # noqa: E402  (after the banner, on purpose)

print(f"cjkfold : {cjkfold.__version__}")
print(f"installed at: {Path(cjkfold.__file__).parent}")
print()

# ---------------------------------------------------------------- public surface
print("-- the public surface --")
missing = [name for name in cjkfold.__all__ if not hasattr(cjkfold, name)]
check(f"all {len(cjkfold.__all__)} names in __all__ exist", not missing, str(missing))

# ---------------------------------------------------------------- the functions
print()
print("-- every function, called for real --")

check("fold", cjkfold.fold("\u6807\u51c6\u989c" + KANGXI_COLOR + "\u503c") == "\u6807\u51c6\u989c\u8272\u503c")
check("has_lookalikes", cjkfold.has_lookalikes(RADICAL_HORN) is True)
check("has_lookalikes (clean)", cjkfold.has_lookalikes(SHU) is False)
found = list(cjkfold.iter_lookalikes("\u7b2c\u4e00\u884c\n\u7b2c" + RADICAL_HORN))
check("iter_lookalikes position", [(f.line, f.column) for f in found] == [(2, 2)] and found[0].kind == "radical-supplement")
check("kind_of", cjkfold.kind_of(0x2EC6) == "radical-supplement")

check("normalize spares punctuation", cjkfold.normalize(FULLWIDTH_A + FULLWIDTH_COMMA + "b") == "A" + FULLWIDTH_COMMA + "b")
check("normalize (keep_punctuation=False)", cjkfold.normalize(FULLWIDTH_A + FULLWIDTH_COMMA + "b", keep_punctuation=False) == "A,b")
check("strip_invisible default", cjkfold.strip_invisible(SHU + ZWSP + JU) == SHU + JU)
check("strip_invisible keeps the family", cjkfold.strip_invisible(FAMILY) == FAMILY)
check("strip_invisible policy=all", len(cjkfold.strip_invisible(FAMILY, policy="all")) == 3)

findings = list(cjkfold.scan(SHU + ZWSP + JU + KANGXI_COLOR + FULLWIDTH_A))
check("scan finds three classes", {f.class_ for f in findings} == {"invisible", "lookalike", "compat"})
check("scan_stats agrees", sum(cjkfold.scan_stats(SHU + ZWSP + JU).values()) == 1)
check("is_punctuation", cjkfold.is_punctuation(FULLWIDTH_COMMA) is True and cjkfold.is_punctuation(FULLWIDTH_A) is False)
check("Finding has the documented fields", set(findings[0].__dataclass_fields__) == {
    "index", "line", "column", "char", "codepoint", "class_", "fixable", "replacement", "note"})

check("ngrams", cjkfold.ngrams("\u6807\u51c6\u989c\u8272") == {"\u6807\u51c6\u989c\u8272"})
check("ngram_overlap", cjkfold.ngram_overlap("\u7d2b\u8272", "\u6807\u51c6\u7d2b" + KANGXI_COLOR) == 1.0)
check("exact_boost", cjkfold.exact_boost("\u7d2b\u8272", "\u6807\u51c6\u7d2b" + KANGXI_COLOR) == 0.25)

check("text_of(str)", cjkfold.text_of("abc") == "abc")


class Doc:
    def __init__(self, page_content: str) -> None:
        self.page_content = page_content


check("fold_document", cjkfold.fold_document(Doc("\u6807\u51c6\u989c" + KANGXI_COLOR)).page_content == "\u6807\u51c6\u989c\u8272")
check("fold_documents", len(cjkfold.fold_documents(["a", "b"])) == 2)
order = cjkfold.rerank("\u7d2b\u8272", ["\u6807\u51c6\u7d2b" + KANGXI_COLOR, "\u7eff\u8272"], [0.29, 0.36])
check("rerank flips the inversion", order[0][0].startswith("\u6807\u51c6\u7d2b") and order[0][1] > order[1][1])

check("EQUIVALENT_IDEOGRAPH is a table", isinstance(cjkfold.EQUIVALENT_IDEOGRAPH, dict) and len(cjkfold.EQUIVALENT_IDEOGRAPH) > 300)

# ---------------------------------------------------------------- import paths
print()
print("-- import paths --")
import importlib  # noqa: E402

from cjkfold.normalize import fold as fold_from_submodule  # noqa: E402

check("`from cjkfold.normalize import fold` works", fold_from_submodule("\u2f8a") == "\u8272")
check("`from cjkfold import normalize` is the callable", callable(cjkfold.normalize))
submodule = importlib.import_module("cjkfold.normalize")
check("`importlib.import_module('cjkfold.normalize')` returns the module", callable(submodule.fold))
check(
    "`cjkfold.normalize` is the function, not the module (a declared consequence)",
    not hasattr(cjkfold.normalize, "fold"),
)

# ---------------------------------------------------------------- dependencies
print()
print("-- dependencies --")
import importlib.metadata as metadata  # noqa: E402

requires = metadata.requires("cjkfold") or []
runtime = [r for r in requires if "extra ==" not in r]
check("zero runtime dependencies", not runtime, str(runtime))
check("metadata version matches the package", metadata.version("cjkfold") == cjkfold.__version__)

# ---------------------------------------------------------------- CLI
print()
print("-- command line --")
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "clean.txt").write_text(SHU + JU + "\n", encoding="utf-8")
    (root / "lookalike.txt").write_text("\u6807\u51c6\u989c" + KANGXI_COLOR + "\n", encoding="utf-8")
    (root / "zwsp.txt").write_text(SHU + ZWSP + JU + "\n", encoding="utf-8")
    (root / "corpus").mkdir()
    (root / "corpus" / "a.txt").write_text(KANGXI_COLOR, encoding="utf-8")
    (root / "corpus" / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

    check("--version", run_cli("--version").stdout.strip() == f"cjkfold {cjkfold.__version__}")
    check("--help", run_cli("--help").returncode == 0)
    for command in ("check", "scan", "fold"):
        check(f"{command} --help", run_cli(command, "--help").returncode == 0)

    result = run_cli("check", str(root / "clean.txt"))
    check("check on a clean file exits 0", result.returncode == 0 and "clean" in result.stdout)
    result = run_cli("check", str(root / "lookalike.txt"))
    check("check on a look-alike exits 1", result.returncode == 1 and "look-alike" in result.stdout)

    result = run_cli("scan", str(root / "zwsp.txt"))
    check("scan finds the zero-width space", result.returncode == 0 and "U+200B" in result.stdout)
    result = run_cli("scan", "--json", str(root / "zwsp.txt"))
    payload = json.loads(result.stdout)
    check("scan --json parses", payload["findings"][0]["codepoint"] == 0x200B)
    result = run_cli("scan", "--classes", "invisible", str(root / "lookalike.txt"))
    check("scan --classes filters", "clean" in result.stdout)
    result = run_cli("scan", "--max", "1", str(root / "zwsp.txt"))
    check("scan --max accepted", result.returncode == 0)
    result = run_cli("scan", "--strict", str(root / "lookalike.txt"))
    check("scan --strict exits 1 on a defect", result.returncode == 1)
    result = run_cli("scan", str(root / "corpus"))
    check("scan walks a directory", result.returncode == 0 and "a.txt" in result.stdout)
    check("...and reports the file it skipped", "1 non-text file(s) skipped" in result.stderr)

    result = run_cli("fold", str(root / "lookalike.txt"))
    check("fold prints folded text", KANGXI_COLOR not in result.stdout and "\u8272" in result.stdout)

    target = root / "rewrite.txt"
    target.write_text("\u6807\u51c6\u989c" + KANGXI_COLOR + "\n", encoding="utf-8")
    result = run_cli("fold", "-w", str(target))
    check("fold -w rewrites in place", KANGXI_COLOR not in target.read_text(encoding="utf-8"))

    result = run_cli("check", str(root / "corpus" / "image.png"))
    check("check refuses a non-text file (exit 2)", result.returncode == 2 and "pdftotext" in result.stderr or "not a text file" in result.stderr)

# stdio plumbing for stdin needs its own call (input=).
# The input carries a look-alike, not a zero-width space: `check` reports the first
# family only, so handing it an invisible character gets a passing exit code --
# which is correct behaviour, and exactly the limitation `scan` exists to answer.
stdin_run = subprocess.run(
    [sys.executable, "-m", "cjkfold", "check", "-"],
    input="\u6807\u51c6\u989c" + KANGXI_COLOR + "\u503c",
    capture_output=True,
    text=True,
)
check(
    "check - reads stdin and reports",
    stdin_run.returncode == 1 and "look-alike" in stdin_run.stdout,
    stdin_run.stdout + stdin_run.stderr,
)

invisible_stdin = subprocess.run(
    [sys.executable, "-m", "cjkfold", "check", "-"],
    input=SHU + ZWSP + JU,
    capture_output=True,
    text=True,
)
check(
    "check - cannot see a zero-width space (exit 0, by design)",
    invisible_stdin.returncode == 0,
    invisible_stdin.stdout,
)

console_script = Path(sys.executable).parent / "cjkfold"
check("the console script is installed", console_script.exists())
if console_script.exists():
    out = subprocess.run([str(console_script), "--version"], capture_output=True, text=True)
    check("the console script runs", out.stdout.strip() == f"cjkfold {cjkfold.__version__}")

# ---------------------------------------------------------------- verdict
print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} check(s):")
    for name in FAILURES:
        print(f"  - {name}")
    sys.exit(1)
print("ALL CHECKS PASSED")
