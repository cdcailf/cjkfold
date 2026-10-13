"""Command line interface for cjkfold.

    cjkfold check FILE...        report look-alike characters
    cjkfold fold  FILE...        print (or rewrite) folded text

``check`` exits non-zero when it finds anything, so it can be dropped into a
build or ingest pipeline to catch PDF extraction regressions early.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .normalize import fold, iter_lookalikes

__all__ = ["main"]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _cmd_check(args: argparse.Namespace) -> int:
    total = 0
    for name in args.paths:
        path = Path(name)
        text = _read(path)
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
    if total:
        print(f"\n{total} character(s) would change under `cjkfold fold`.")
        return 1
    return 0


def _cmd_fold(args: argparse.Namespace) -> int:
    for name in args.paths:
        path = Path(name)
        folded = fold(_read(path))
        if args.write:
            path.write_text(folded, encoding="utf-8")
            print(f"{path}: rewritten", file=sys.stderr)
        else:
            if len(args.paths) > 1:
                print(f"===== {path} =====", file=sys.stderr)
            sys.stdout.write(folded)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cjkfold",
        description="Fold look-alike CJK glyphs onto their canonical ideograph.",
    )
    parser.add_argument("--version", action="version", version="cjkfold 0.1.0")
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
