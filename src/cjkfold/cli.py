"""Command line interface for cjkfold.

    cjkfold check FILE...        report look-alike characters
    cjkfold scan  FILE...        report every character that breaks a comparison
    cjkfold fold  FILE...        print (or rewrite) folded text

Exit codes::

    0   clean
    1   look-alike characters found (``check``); findings under ``scan --strict``
    2   the input is not a text file (or not UTF-8) -- nothing was scanned

``check`` exits non-zero when it finds anything, so it can be dropped into a build
or ingest pipeline to catch PDF extraction regressions early. Code 2 is kept separate
from code 1 on purpose: "I found something" and "I could not look" are different
answers, and a pipeline that can only see "non-zero" would report a PDF as a finding.

``scan`` is the other half of the answer and deliberately behaves differently: it
reports every class of finding, including the ones that must *not* be repaired
automatically, so it exits 0 by default. A gate that fails on a load-bearing
zero-width joiner fails on ordinary emoji; scanning is a report, not a gate.
``--strict`` exists for a caller who has read the findings and wants a gate anyway.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from dataclasses import asdict
from pathlib import Path
from typing import Iterator, Sequence

import cjkfold

from .diagnose import Finding, is_punctuation, scan
from .inputs import NotTextFile, read_text
from .normalize import fold, iter_lookalikes

__all__ = ["main"]

PROG = "cjkfold"


def _version_string() -> str:
    """Report the package's version -- read from it, never copied from it.

    This used to be the literal ``"cjkfold 0.1.0"``, one release behind the package
    and one behind the packaging metadata, so ``cjkfold --version`` contradicted
    ``cjkfold.__version__`` in public. A local copy would drift the same way on the
    next bump; an attribute read cannot. ``tests/test_version.py`` proves the
    difference by mutating ``cjkfold.__version__`` and watching this follow.
    """
    return f"{PROG} {cjkfold.__version__}"


def _cmd_check(args: argparse.Namespace) -> int:
    total = 0
    rejected = False
    for name in args.paths:
        path = Path(name)
        try:
            text = read_text(path)
        except NotTextFile as exc:
            print(exc.format(), file=sys.stderr)
            rejected = True
            continue
        found = list(iter_lookalikes(text))
        total += len(found)
        if not found:
            if not args.quiet:
                print(f"{path}: clean")
            continue
        kinds: dict[str, int] = {}
        for item in found:
            kinds[item.kind] = kinds.get(item.kind, 0) + 1
        summary = ", ".join(f"{count} {kind}" for kind, count in sorted(kinds.items()))
        print(f"{path}: {len(found)} look-alike character(s) ({summary})")
        for item in found[: args.max] if args.max else found:
            print(f"    {item}")
        if args.max and len(found) > args.max:
            print(f"    ... and {len(found) - args.max} more (raise --max to see them)")
    if rejected:
        return 2
    if total:
        print(f"\n{total} character(s) would change under `cjkfold fold`.")
        return 1
    return 0


def _cmd_fold(args: argparse.Namespace) -> int:
    rejected = False
    for name in args.paths:
        path = Path(name)
        try:
            text = read_text(path)
        except NotTextFile as exc:
            # Refuse rather than fold: with --write this used to decode binary into
            # mojibake and write it back over the original file.
            print(exc.format(), file=sys.stderr)
            rejected = True
            continue
        folded = fold(text)
        if args.write:
            path.write_text(folded, encoding="utf-8")
            print(f"{path}: rewritten", file=sys.stderr)
        else:
            if len(args.paths) > 1:
                print(f"===== {path} =====", file=sys.stderr)
            sys.stdout.write(folded)
    return 2 if rejected else 0


#: The classes ``scan`` knows about, in the order they are printed.
_SCAN_CLASSES = ("lookalike", "compat", "invisible", "broken")

#: Classes that are a defect rather than a judgement call -- what ``--strict`` gates on.
_SCAN_GATED = ("lookalike", "compat")

#: Printed once per run, not once per file: scanning a corpus is the normal case,
#: and the same two lines repeated a hundred times is noise, not guidance.
_SCAN_FOOTER = (
    "  see also  cjkfold scan --classes invisible\n"
    "            cjkfold fold --help"
)


def _parse_classes(value: str) -> tuple[str, ...]:
    """Parse ``--classes`` as a comma-separated list.

    Deliberately *one* token rather than ``nargs="+"``: with a variadic option next
    to a variadic ``paths``, argparse hands ``--classes invisible file.txt`` both
    the class and the filename, and rejects it. The report then suggests its own
    usage in a form that cannot work.
    """
    classes = tuple(part.strip() for part in value.split(",") if part.strip())
    unknown = [item for item in classes if item not in _SCAN_CLASSES]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown class: {', '.join(unknown)} -- choose from {', '.join(_SCAN_CLASSES)}"
        )
    if not classes:
        raise argparse.ArgumentTypeError(f"expected at least one of: {', '.join(_SCAN_CLASSES)}")
    return classes


_POSITION_WIDTH = 5
_DESCRIPTION_WIDTH = 30
#: Where a finding's reason starts -- under the code point, not under the position.
_NOTE_INDENT = " " * (4 + _POSITION_WIDTH + 2)


def _visual_width(text: str) -> int:
    """Width in terminal columns; CJK glyphs take two, everything else takes one.

    Used only to line the report up.  ``len()`` would be right for the machine and
    wrong for the reader, and this report is for the reader.
    """
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _visual_width(text))


def _finding_head(finding: Finding) -> str:
    """One finding's first line: where it is, what it is, and what to do about it."""
    position = f"{finding.line}:{finding.column}"
    if finding.replacement is None:
        what, source = unicodedata.name(finding.char, "<unnamed>"), ""
    else:
        what = f"-> {finding.replacement} {finding.replacement_label or '...'}"
        source = f"   ({unicodedata.name(finding.char, '<unnamed>')})"
    return (
        f"    {position:>{_POSITION_WIDTH}}  {finding.codepoint_label}  "
        f"{_pad(what, _DESCRIPTION_WIDTH)} {finding.fixable}{source}"
    )


def _format_scan(path: Path, text: str, findings: Sequence[Finding], *, limit: int) -> str:
    """Render one file's report. Grouped by class, because the classes differ in kind.

    Truncated per class rather than per file: the three classes are three different
    questions, and one noisy class should not hide the other two.

    The reason for a classification is printed once per character, not once per
    occurrence: an emoji-heavy document can hold hundreds of joiners, and saying
    the same sentence hundreds of times buries the two lines that differ.
    """
    counted = f"{len(text):,} characters"
    if not findings:
        return f"{path}  {counted}  clean"

    plural = "" if len(findings) == 1 else "s"
    lines = [f"{path}  {counted}  {len(findings)} finding{plural}"]

    explained: dict[int, str] = {}
    for class_ in _SCAN_CLASSES:
        group = [item for item in findings if item.class_ == class_]
        if not group:
            continue
        if class_ == "compat":
            # A compat finding can be a defect (a full-width letter) or merely
            # punctuation NFKC would swap out. sorted() is stable, so the reading
            # order inside each half is preserved -- what changes is which half
            # gets the first screenful.
            group = sorted(group, key=lambda item: is_punctuation(item.char))
        shown = group if limit <= 0 else group[:limit]

        lines.append("")
        lines.append(f"  {class_}  {len(group)}")
        for finding in shown:
            lines.append(_finding_head(finding))
            first_seen = explained.get(finding.codepoint)
            if first_seen is None:
                explained[finding.codepoint] = f"{finding.line}:{finding.column}"
                lines.append(f"{_NOTE_INDENT}{finding.note}")
            else:
                lines.append(f"{_NOTE_INDENT}(same character as {first_seen})")
        if len(shown) < len(group):
            lines.append(
                f"{_NOTE_INDENT}... and {len(group) - len(shown)} more (raise --max to see them)"
            )

    summaries = []
    for class_ in _SCAN_CLASSES:
        fixes = list(dict.fromkeys(item.fixable for item in findings if item.class_ == class_))
        if fixes:
            summaries.append(f"{class_}: {', '.join(fixes)}")

    lines.append("")
    lines.append(f"  fixable   {'    '.join(summaries)}")
    return "\n".join(lines)


def _report_scan(args: argparse.Namespace, path: Path, text: str) -> tuple[bool, int]:
    """Print one file's report; return ``(--strict should fail, findings printed)``."""
    findings = [item for item in scan(text) if item.class_ in args.classes]
    if args.json:
        payload = {
            "path": str(path),
            "characters": len(text),
            "findings": [asdict(finding) for finding in findings],
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(_format_scan(path, text, findings, limit=args.max))
    gated = args.strict and any(item.class_ in _SCAN_GATED for item in findings)
    return gated, len(findings)


def _expand_paths(names: Sequence[str]) -> Iterator[tuple[Path, bool]]:
    """Yield ``(path, was_named)`` for every file to scan.

    A directory is expanded into the files under it, skipping dot-entries so that
    ``.git`` and friends stay out of the report.

    ``was_named`` carries the distinction the caller cares about: a file they
    pointed at is *the* file, and failing to read it is news; files found by
    walking a directory are a sample, and one image sitting among them is not.
    Both can be true at once -- a named file and a directory in the same command.
    """
    for name in names:
        path = Path(name)
        if not path.is_dir():
            yield path, True
            continue
        for child in sorted(path.rglob("*")):
            if not child.is_file():
                continue
            if any(part.startswith(".") for part in child.relative_to(path).parts):
                continue
            yield child, False


def _cmd_scan(args: argparse.Namespace) -> int:
    rejected = False
    gated = False
    skipped = 0
    total = 0
    for path, named in _expand_paths(args.paths):
        try:
            text = read_text(path)
        except NotTextFile as exc:
            if named:
                print(exc.format(), file=sys.stderr)
                rejected = True
            else:
                # Expected, but not silent: the count is reported at the end, so a
                # directory full of unreadable files does not look like a clean one.
                skipped += 1
            continue
        except OSError as exc:
            # A named path that cannot be opened at all -- a typo, a permission, a
            # broken symlink.  A traceback is not a diagnostic.
            print(f"{path}: {exc.strerror or exc}", file=sys.stderr)
            rejected = True
            continue
        gate, printed = _report_scan(args, path, text)
        gated = gate or gated
        total += printed
    if skipped:
        print(f"{skipped} non-text file(s) skipped", file=sys.stderr)
    if total and not args.json:
        print(_SCAN_FOOTER)
    if rejected:
        return 2
    return 1 if gated else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Fold look-alike CJK glyphs onto their canonical ideograph.",
    )
    parser.add_argument("--version", action="version", version=_version_string())
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser(
        "check",
        help="report look-alike characters (exit 1 if any are found)",
    )
    check.add_argument("paths", nargs="+", help="files to inspect, or - for stdin")
    check.add_argument("--quiet", action="store_true", help="only report files with findings")
    check.add_argument("--max", type=int, default=20, help="max findings to print per file (0 = all)")
    check.set_defaults(func=_cmd_check)

    scan_cmd = sub.add_parser(
        "scan",
        help="report every character that breaks a comparison (read-only; exit 0 by default)",
    )
    scan_cmd.add_argument("paths", nargs="+", help="files or directories to scan, or - for stdin")
    scan_cmd.add_argument(
        "--classes",
        type=_parse_classes,
        default=_SCAN_CLASSES,
        metavar="CLASSES",
        help=f"comma-separated classes to report: {', '.join(_SCAN_CLASSES)} (default: all)",
    )
    scan_cmd.add_argument("--json", action="store_true", help="one JSON object per file")
    scan_cmd.add_argument(
        "--max",
        type=int,
        default=20,
        help="max findings to print per class (0 = all)",
    )
    scan_cmd.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when a foldable or compat character is present",
    )
    scan_cmd.set_defaults(func=_cmd_scan)

    fold_cmd = sub.add_parser("fold", help="write folded text to stdout")
    fold_cmd.add_argument("paths", nargs="+", help="files to fold, or - for stdin")
    fold_cmd.add_argument("-w", "--write", action="store_true", help="rewrite the files in place")
    fold_cmd.set_defaults(func=_cmd_fold)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "paths", None) and "-" in args.paths:
        text = sys.stdin.read()
        args.paths = [p for p in args.paths if p != "-"]
        if args.command == "fold":
            sys.stdout.write(fold(text))
            return 0
        if args.command == "scan":
            gate, printed = _report_scan(args, Path("<stdin>"), text)
            if printed and not args.json:
                print(_SCAN_FOOTER)
            return 1 if gate else 0
        found = list(iter_lookalikes(text))
        for item in found[: args.max] if args.max else found:
            print(f"     <stdin> {item}")
        if args.max and len(found) > args.max:
            print(f"     ... and {len(found) - args.max} more")
        print(f"<stdin>: {len(found)} look-alike character(s)")
        return 1 if found else 0
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
