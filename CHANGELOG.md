# Changelog

Releases are cut from `main`. The tests in `tests/` are the contract; the
equivalence table is generated, never hand-edited.

## 0.4.0 — 2026-10-15

No new features. One structural fix, and it breaks an import path.

### Changed

- **The fold family moved from `cjkfold.normalize` to `cjkfold.folding`; the two
  writes moved to `cjkfold.rewrite`.** Nothing about the *functions* changed —
  `from cjkfold import fold, normalize, strip_invisible` behaves exactly as it did.

  Why: a function named `normalize` cannot live in a module named `normalize` without
  one of the two losing its name, and `import a.b as c` means `c = a.b`. So
  `import cjkfold.normalize as m` handed you the *function*, and `m.fold` raised
  `AttributeError`. Every name now means one thing: `cjkfold.normalize` is the
  function, `cjkfold.folding` is the module. (`af57ad7`)

  What breaks: `from cjkfold.normalize import fold` — a path nothing ever
  documented, and it now fails with a plain `ModuleNotFoundError` instead of an
  `AttributeError` from something that was never a module. Every documented import
  is untouched.

### Tests

- `scripts/acceptance.py` gained import-path checks, including one that the old
  path is gone. (`af57ad7`)

## 0.3.0 — 2026-10-15

### Added

- **The `broken` class.** `scan` now reports `U+FFFD` and the private use areas
  alongside look-alikes, compat characters and invisible ones — damage that cannot
  be repaired, only reported. A private use code point earns its place in the
  report precisely because nothing defines what it looks like: the font doing the
  rendering decides, and it can come out as a box, as nothing at all, or as a
  glyph that means something else. (`b17902d`)
- **`scan` walks directories.** A corpus is a tree, not an argument list.
  Dot-entries stay out, so `.git` does not end up in the report; a non-text file
  found by walking is skipped and counted, while a non-text file you *named* is
  still an error — pointing at a PDF is a mistake, walking past one is not.
  (`b17902d`)
- The `scan` footer prints once per run instead of once per file, which starts to
  matter the moment you point it at a directory. (`b17902d`)

### Tests

- The four compat characters the roadmap named are pinned with measured values:
  full-width `Ａ` → `A`, ideographic space → space, `U+F900` → 豈, NBSP → space.
  (`b17902d`)

No change to `fold()`, to `check`, or to the equivalence table. Exit codes and
`check` output are unchanged.

## 0.2.0 — 2026-10-15

### Added

- **`cjkfold scan`** — every character that breaks a comparison, in one read-only
  pass: the look-alikes, the NFKC family `fold()` refuses to touch, and the
  invisible family. Each finding says what to do with it — `fold`, `nfkc`,
  `strip`, or `manual`, where `manual` means *do not touch this without looking*.
  It exits `0` by default, because it is a report and not a gate: a gate that fails
  on a load-bearing joiner fails on ordinary emoji. `--strict` gates anyway,
  `--json` feeds a pipeline, `--classes` narrows the report. (`c5be88a`, `5835dbf`)
- **`normalize()`** and **`strip_invisible()`** — the two explicit writes. The
  first applies the NFKC family with full-width punctuation spared by default; the
  second deletes invisible characters, `safe` by default, because half of that
  family carries meaning — a family of three is five code points, and deleting the
  joiners leaves three separate people. Neither is exposed as a subcommand: `fold -w`
  is already an in-place rewrite, and two more destructive commands would be a gun
  pointed at a corpus. (`a733ef5`)
- `Finding`, `scan_stats()` and `is_punctuation()` in the public API.
  (`2bd05e6`, `5835dbf`)

### Changed

- `scan`'s whitelist lookup is now a single set test instead of a dict lookup plus
  four range comparisons: 0.42s → 0.29s over 640,000 characters. (`f6c5f4f`)

### Docs

- README: **"The characters that never show up"** and **"The other two rewrites"**,
  both carrying output from real runs rather than hand-copied examples; the 中文简述
  follows. The `check` example also gained the summary line it had been missing —
  the reason it was missing is that it had been copied by hand, which is exactly
  what the new section refuses to do. (`e9c4d68`, and this release)
- `tests/fixtures/` — the three files the roadmap asked for, with `check`'s output
  frozen byte for byte. (`1a468e5`)

No change to `fold()`, to `check`, or to the equivalence table. Text that folded
correctly under 0.1.2 folds identically under 0.2.0.

## 0.1.2 — 2026-10-14

### Fixes

- **`cjkfold check` refuses non-text input instead of scanning it.** A PDF used to
  report three phantom look-alikes, because its compressed stream was read as if it
  were text. Non-text input now exits `2` with a note instead of producing findings.
  (`aa86107`)
- **`cjkfold --version` reports the installed version.** It read a literal that had
  drifted to `0.1.0` while the package was at `0.1.1`. (`724e9a9`)

### Tooling

- The test suite runs on GitHub Actions for Python 3.9–3.13, with the status badge
  in the README. (`5b3e50b`)

### Docs

- `docs/roadmap-v0.2.md` — invisible characters and non-text input, with acceptance
  criteria. (`6696f7a`)

No change to the folding logic or to the equivalence table.

## 0.1.1 — 2026-10-13

The README stopped requiring a source checkout: the package installs from PyPI.
(`5e86028`)

## 0.1.0 — 2026-10-13

First release: `fold()`, the equivalence table generated from the Unicode UCD, the
exact n-gram rerank helper, and framework-agnostic adapters for folding documents
and reranking retrieval results.
