"""Regenerate ``src/cjkfold/_table.py`` from the Unicode Character Database.

The shipped table is generated, never hand-edited.  Re-run this when a new
Unicode version lands::

    python scripts/build_table.py                       # download from unicode.org
    python scripts/build_table.py CJKRadicals.txt ...   # use a local copy

The source of truth is the ``EquivalentUnifiedIdeograph`` property introduced
in Unicode 15.1 (file ``EquivalentUnifiedIdeograph.txt``).  It maps code points
that *look like* a unified ideograph onto that ideograph.
"""

from __future__ import annotations

import sys
import unicodedata
import urllib.request
from pathlib import Path

URL = "https://www.unicode.org/Public/UCD/latest/ucd/EquivalentUnifiedIdeograph.txt"
DEST = Path(__file__).resolve().parent.parent / "src" / "cjkfold" / "_table.py"

HEADER = '''"""Glyph equivalence table. GENERATED — do not edit by hand.

Regenerate:  python scripts/build_table.py
Source:      Unicode Character Database, EquivalentUnifiedIdeograph.txt
             https://www.unicode.org/Public/UCD/latest/ucd/EquivalentUnifiedIdeograph.txt
"""

from __future__ import annotations

# Characters that are visually identical to a unified ideograph but carry a
# different code point.  NFKC does NOT fold most of these (see README).
EQUIVALENT_IDEOGRAPH: dict[str, str] = {'''


def load(source: str | None) -> str:
    if source:
        return Path(source).read_text(encoding="utf-8")
    with urllib.request.urlopen(URL, timeout=30) as response:  # noqa: S310
        return response.read().decode("utf-8")


def expand(field: str) -> list[int]:
    """Expand ``2E8C`` or ``2E8C..2E8D`` into code points."""
    field = field.strip()
    if ".." in field:
        start, end = field.split("..")
        return list(range(int(start, 16), int(end, 16) + 1))
    return [int(field, 16)]


def parse(text: str) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ";" not in line:
            continue
        left, right = (part.strip() for part in line.split(";")[:2])
        sources, targets = expand(left), expand(right)
        if len(targets) == 1:
            # Many-to-one: every source folds onto the same ideograph.
            pairs.extend((source, targets[0]) for source in sources)
        elif len(sources) == len(targets):
            pairs.extend(zip(sources, targets))
        else:
            raise SystemExit(f"cannot parse mapping: {line}")
    pairs.sort()
    return pairs


def render(pairs: list[tuple[int, int]]) -> str:
    lines = [HEADER]
    for source, target in pairs:
        name = unicodedata.name(chr(source), "UNNAMED")
        lines.append(
            f'    "\\u{source:04x}": "\\u{target:04x}",'
            f"  # {chr(source)} {name} -> {chr(target)}"
        )
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    text = load(argv[1] if len(argv) > 1 else None)
    pairs = parse(text)
    DEST.write_text(render(pairs), encoding="utf-8")
    print(f"wrote {len(pairs)} mappings to {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
