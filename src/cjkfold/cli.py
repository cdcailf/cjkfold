"""Command line interface for cjkfold.

    cjkfold check FILE...        report look-alike characters
    cjkfold fold  FILE...        print (or rewrite) folded text

Exit codes::

    0   clean
    1   look-alike characters found
    2   the input is not a text file (or not UTF-8) -- nothing was scanned

``check`` exits non-zero when it finds anything, so it can be dropped into a build
or ingest pipeline to catch PDF extraction regressions early. Code 2 is kept separate
from code 1 on purpose: "I found something" and "I could not look" are different
answers, and a pipeline that can only see "non-zero" would report a PDF as a finding.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import cjkfold

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
