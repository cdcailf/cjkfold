"""Read text from disk -- and refuse to read anything that is not text.

Why this module exists (2026-10-13)::

    $ cjkfold check 作文急救-修错对照与安全骨架.pdf
    作文急救-修错对照与安全骨架.pdf: 3 look-alike character(s) (3 radical-supplement)
        87:166   ⻱ U+2EF1 -> 龜 U+9F9C  (CJK RADICAL TURTLE)

All three findings were phantoms. The file is a PDF; ``read_text(errors="replace")``
decoded 335 KB of binary into a string, and three byte sequences happened to land on
CJK radical-supplement codepoints. The report was *wrong in form and confident in
tone* -- readable line/column numbers, exit code 1, everything a real finding looks
like. A scanner that produces confident false positives is worse than one that
produces nothing: the reader goes hunting for a ghost.

Three checks, in order, each catching a different thing:

1. **Known binary magic numbers** -- the only check that can *name* the format,
   and therefore the only one that can suggest the right next command.
2. **NUL bytes** -- a text file has none. Catches binaries whose format we do not
   know; blunt but reliable.
3. **Strict decoding** -- catches "a real text file in another encoding" (GBK,
   Shift-JIS, ...). That needs a *different* fix from "this is a PDF", so it gets a
   different message: telling a GBK user their file is "binary" sends them the wrong way.

``errors="replace"`` is deliberately not used any more. It was not just noisy: it
made the reported line and column numbers meaningless (invalid byte sequences collapse
into one ``U+FFFD``, so character offsets stop corresponding to byte offsets), and with
``fold --write`` it would have overwritten the input with mojibake.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

__all__ = ["NotTextFile", "binary_kind", "read_text"]

#: How much of the file is inspected for magic numbers and NUL bytes. Binaries announce
#: themselves at the front, and this keeps the guard free on very large inputs.
SCAN_LIMIT: Final[int] = 1 << 20  # 1 MiB

#: (prefix, what it is, how to turn it into text). The third field is the reason this
#: check exists at all -- an error the user cannot act on is just noise.
_MAGIC: Final[tuple[tuple[bytes, str, str], ...]] = (
    (b"%PDF-", "a PDF", "pdftotext {path} {stem}.txt"),
    (b"PK\x03\x04", "a ZIP container (docx / xlsx / pptx / odt)", "convert it with libreoffice --convert-to txt"),
    (b"\x1f\x8b", "a gzip stream", "gunzip {path}"),
    (b"\xd0\xcf\x11\xe0", "a legacy Office file (doc / xls / ppt)", "convert it with libreoffice --convert-to txt"),
    (b"\x89PNG\r\n\x1a\n", "a PNG image", "OCR it, then check the text"),
    (b"\xff\xd8\xff", "a JPEG image", "OCR it, then check the text"),
    (b"\x7fELF", "a program", "-- this is not a document"),
    (b"\x1a\x45\xdf\xa3", "a Matroska / WebM video", "-- this is not a document"),
)


class NotTextFile(Exception):
    """Raised when a path is not a text file.

    Carries *what it is* (``problem``) and *what to do about it* (``hint``) separately,
    because callers and users need both and they are not the same sentence.
    """

    def __init__(self, path: Path | str, problem: str, hint: str) -> None:
        super().__init__(f"{path}: {problem}")
        self.path = Path(path)
        self.problem = problem
        self.hint = hint

    def format(self, indent: str = "  ") -> str:
        return f"{self.path}: {self.problem} -- cjkfold only reads text.\n{indent}{self.hint}"


def binary_kind(data: bytes, path: Path | str = "input") -> tuple[str, str] | None:
    """Return ``(what it is, how to convert it)`` when ``data`` starts with a known
    binary magic number, else ``None``."""
    stem = Path(path).stem
    for prefix, what, how in _MAGIC:
        if data.startswith(prefix):
            return what, how.format(path=path, stem=stem)
    return None


def _probe(data: bytes, path: Path | str) -> tuple[str, str] | None:
    """Return ``(problem, hint)`` when the bytes cannot be text, else ``None``."""
    head = data[:SCAN_LIMIT]
    named = binary_kind(head, path)
    if named is not None:
        what, how = named
        return f"this looks like {what}, not a text file", how

    if b"\x00" in head:
        return (
            "this looks like a binary file (it contains NUL bytes), not a text file",
            "extract the text first, then check the extracted .txt",
        )
    return None


def read_text(path: Path | str, *, encoding: str = "utf-8") -> str:
    """Read ``path`` as text.

    Raises :class:`NotTextFile` when the file is binary *or* when it is text in an
    encoding we were not told about -- two failures with two different fixes.
    """
    path = Path(path)
    data = path.read_bytes()

    probed = _probe(data, path)
    if probed is not None:
        problem, hint = probed
        raise NotTextFile(path, problem, hint)

    try:
        return data.decode(encoding)
    except UnicodeDecodeError as exc:
        raise NotTextFile(
            path,
            f"this is a text file, but not valid {encoding.upper()} "
            f"(byte {exc.start} is not part of a {encoding.upper()} character)",
            f"convert it first, e.g. iconv -f GBK -t UTF-8 {path} > {path.stem}.utf8.txt",
        ) from exc
