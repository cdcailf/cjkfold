# Changelog

Releases are cut from `main`. The tests in `tests/` are the contract; the
equivalence table is generated, never hand-edited.

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
