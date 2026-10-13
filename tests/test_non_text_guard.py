"""Non-text input must be refused, not scanned (roadmap v0.2, G5).

The bug this locks down:

    $ cjkfold check 作文急救-修错对照与安全骨架.pdf
    作文急救-修错对照与安全骨架.pdf: 3 look-alike character(s) (3 radical-supplement)

Three findings, all phantoms -- the file is a PDF and `read_text(errors="replace")`
decoded embedded-font bytes into a string. Acceptance criteria are the G5-* list in
`docs/roadmap-v0.2.md`; each test names the one it covers.
"""

from __future__ import annotations

import pytest

from cjkfold import NotTextFile, read_text
from cjkfold.cli import main

# A PDF header with no NUL byte: isolates "magic number" from "NUL byte".
PDF_NO_NUL = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n"
# Invalid UTF-8, no NUL, no magic: isolates "strict decoding" from both others.
LATIN1_TEXT = "número de serie".encode("latin-1")
# GBK-encoded real Chinese text: the case that must NOT be called "binary" (G5-4).
GBK_TEXT = "紫色独角兽协议的编号是 PU-7788-ZX".encode("gbk")


def _write(tmp_path, name, data: bytes):
    path = tmp_path / name
    path.write_bytes(data)
    return path


# --------------------------------------------------------------- G5-3: 三个判据各自单独命中


def test_magic_number_alone_is_refused(tmp_path, capsys):
    """No NUL byte anywhere -- only the `%PDF-` magic catches this one."""
    path = _write(tmp_path, "report.pdf", PDF_NO_NUL)
    assert main(["check", str(path)]) == 2
    out = capsys.readouterr()
    assert "look-alike" not in out.out  # 不许产出任何 finding
    assert "PDF" in out.err


def test_nul_bytes_alone_are_refused(tmp_path, capsys):
    """No magic number, no invalid encoding -- only the NUL check catches this one."""
    path = _write(tmp_path, "blob.bin", b"abc\x00def\x00ghi")
    assert main(["check", str(path)]) == 2
    out = capsys.readouterr()
    assert "NUL" in out.err
    assert "look-alike" not in out.out


def test_invalid_encoding_alone_is_refused(tmp_path, capsys):
    """No magic, no NUL, but not UTF-8 -- only strict decoding catches this one."""
    path = _write(tmp_path, "latin1.txt", LATIN1_TEXT)
    assert main(["check", str(path)]) == 2
    out = capsys.readouterr()
    assert "UTF-8" in out.err
    assert "look-alike" not in out.out


# --------------------------------------------------------------- G5-1: 真实 PDF 形状


def test_pdf_shaped_input_exits_2_and_suggests_pdftotext(tmp_path, capsys):
    path = _write(tmp_path, "essay.pdf", b"%PDF-1.4\n" + b"\x00" * 32 + PDF_NO_NUL)
    assert main(["check", str(path)]) == 2
    err = capsys.readouterr().err
    assert "pdftotext" in err  # 报错必须给下一步
    assert str(path) in err


def test_exit_code_2_is_not_1(tmp_path):
    """「我找到了」和「我没法看」必须是两个答案。"""
    text_with_lookalike = _write(tmp_path, "dirty.txt", "⻆色".encode())
    assert main(["check", str(text_with_lookalike)]) == 1, "真 finding 仍旧是 1"


# --------------------------------------------------------------- G5-4: 编码问题 ≠ 二进制


def test_gbk_text_is_reported_as_encoding_not_binary(tmp_path, capsys):
    path = _write(tmp_path, "gbk.txt", GBK_TEXT)
    assert main(["check", str(path)]) == 2
    err = capsys.readouterr().err
    assert "GBK" in err, "要说清下一步是转编码"
    assert "binary" not in err.lower(), "把 GBK 文本叫二进制会把人带错方向"
    assert "iconv" in err


def test_read_text_raises_nottextfile_with_both_parts(tmp_path):
    path = _write(tmp_path, "gbk.txt", GBK_TEXT)
    with pytest.raises(NotTextFile) as caught:
        read_text(path)
    exc = caught.value
    assert "not valid UTF-8" in exc.problem
    assert "iconv" in exc.hint
    assert str(path) in exc.format()


# --------------------------------------------------------------- G5-2: 防误伤（对照不许变）


def test_plain_utf8_text_is_read_byte_identically(tmp_path):
    """对照：真文本的行为与修前逐字节一致（含形近字符、含 ZWSP 的都不许被拦）。"""
    dirty = "⻆色 ⾊彩 数据\u200b库"
    path = _write(tmp_path, "dirty.txt", dirty.encode())
    assert read_text(path) == dirty


def test_clean_file_still_exits_0(tmp_path, capsys):
    path = _write(tmp_path, "clean.txt", "陈得才 · 高级后端工程师".encode())
    assert main(["check", str(path)]) == 0
    assert "clean" in capsys.readouterr().out


def test_check_reports_findings_for_text_as_before(tmp_path, capsys):
    path = _write(tmp_path, "dirty.txt", "⻆色方案".encode())
    assert main(["check", str(path)]) == 1
    out = capsys.readouterr().out
    assert "look-alike character(s)" in out
    assert "U+2EC6" in out


def test_mixed_inputs_report_each_and_exit_2(tmp_path, capsys):
    """一个坏文件不许把好文件的结果吞掉，但退出码取更严重的那个。"""
    bad = _write(tmp_path, "report.pdf", PDF_NO_NUL)
    good = _write(tmp_path, "dirty.txt", "⻆色".encode())
    assert main(["check", str(bad), str(good)]) == 2
    out = capsys.readouterr()
    assert "U+2EC6" in out.out  # 好文件照常报
    assert "PDF" in out.err  # 坏文件报了原因


# --------------------------------------------------------------- fold --write 的数据安全

def test_fold_write_refuses_binary_and_leaves_the_file_alone(tmp_path, capsys):
    """修前 `fold -w` 会把二进制解码成乱码再写回原文件 —— 等于毁掉输入。

    这条不是 roadmap 里的验收项，是补 G5 时顺带发现的：`_read()` 的 errors="replace"
    配上 `-w`，对 PDF 这类文件是一次静默的数据破坏。
    """
    original = b"%PDF-1.4\n" + bytes(range(256)) * 4
    path = _write(tmp_path, "report.pdf", original)
    assert main(["fold", "-w", str(path)]) == 2
    assert path.read_bytes() == original, "拒绝执行时必须原样保留文件"
    assert "PDF" in capsys.readouterr().err


def test_fold_prints_text_as_before(tmp_path, capsys):
    path = _write(tmp_path, "dirty.txt", "⻆色".encode())
    assert main(["fold", str(path)]) == 0
    assert capsys.readouterr().out == "角色"


# --------------------------------------------------------------- 已知二进制魔数

@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"%PDF-1.7\n", "PDF"),
        (b"PK\x03\x04\x14\x00", "ZIP"),
        (b"\x1f\x8b\x08\x00", "gzip"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1", "legacy Office"),
        (b"\x89PNG\r\n\x1a\n", "PNG"),
        (b"\xff\xd8\xff\xe0", "JPEG"),
    ],
)
def test_known_binary_formats_are_named(tmp_path, capsys, data, expected):
    path = _write(tmp_path, "thing.dat", data)
    assert main(["check", str(path)]) == 2
    assert expected in capsys.readouterr().err
