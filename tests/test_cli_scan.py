"""``cjkfold scan`` -- and the promise that adding it moved nothing else.

Escapes, not literal characters, for the same reason as the other test modules.
"""

from __future__ import annotations

import io
import json

import pytest

from cjkfold.cli import main

ZWSP = "\u200b"  # ZERO WIDTH SPACE
ZWJ = "\u200d"  # ZERO WIDTH JOINER
KANGXI_COLOR = "\u2f8a"  # KANGXI RADICAL COLOR, folds to 色
SHU = "\u6570"  # 数
JU = "\u636e"  # 据
FAMILY = "\U0001f468\u200d\U0001f469\u200d\U0001f467"  # 一家三口


@pytest.fixture
def lookalike_file(tmp_path):
    path = tmp_path / "lookalike.txt"
    path.write_text("\u6807\u51c6\u989c" + KANGXI_COLOR + "\n", encoding="utf-8")  # 标准颜⾊
    return path


@pytest.fixture
def zwsp_file(tmp_path):
    path = tmp_path / "zwsp.txt"
    path.write_text(SHU + ZWSP + JU + "\n", encoding="utf-8")  # 数<ZWSP>据
    return path


@pytest.fixture
def family_file(tmp_path):
    path = tmp_path / "family.txt"
    path.write_text(FAMILY + "\n", encoding="utf-8")
    return path


def test_scan_exits_zero_even_when_it_finds_something(lookalike_file, capsys):
    """scan is a report, not a gate."""
    assert main(["scan", str(lookalike_file)]) == 0

    out = capsys.readouterr().out
    assert "lookalike" in out
    assert "finding" in out


def test_strict_turns_a_real_defect_into_a_failure(lookalike_file):
    assert main(["scan", "--strict", str(lookalike_file)]) == 1


def test_strict_does_not_fail_on_a_load_bearing_character(family_file, capsys):
    """The reason scan is not a gate by default: ordinary emoji must not break a build."""
    assert main(["scan", "--strict", str(family_file)]) == 0

    out = capsys.readouterr().out
    assert "manual" in out
    assert "U+200D" in out


def test_a_zero_width_space_is_reported_and_named_strippable(zwsp_file, capsys):
    assert main(["scan", str(zwsp_file)]) == 0

    out = capsys.readouterr().out
    assert "U+200B" in out
    assert "strip" in out
    assert "ZERO WIDTH SPACE" in out


def test_the_reason_is_printed_once_per_character(family_file, capsys):
    """Two joiners in one emoji, one explanation -- the second points back at the first."""
    assert main(["scan", str(family_file)]) == 0

    out = capsys.readouterr().out
    assert out.count("zero width joiner:") == 1
    assert "(same character as 1:2)" in out


def test_classes_limits_the_report(zwsp_file, capsys):
    assert main(["scan", "--classes", "invisible", str(zwsp_file)]) == 0
    assert "invisible" in capsys.readouterr().out

    assert main(["scan", "--classes", "lookalike", str(zwsp_file)]) == 0
    assert "clean" in capsys.readouterr().out


def test_classes_accepts_a_list_and_still_takes_a_filename(zwsp_file, capsys):
    """One token, so a variadic option cannot swallow the path that follows it."""
    assert main(["scan", "--classes", "invisible,compat", str(zwsp_file)]) == 0
    assert "U+200B" in capsys.readouterr().out


def test_an_unknown_class_is_rejected(zwsp_file, capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["scan", "--classes", "colour", str(zwsp_file)])

    assert excinfo.value.code == 2
    assert "unknown class" in capsys.readouterr().err


def test_json_is_one_object_per_file_with_every_field(zwsp_file, capsys):
    assert main(["scan", "--json", str(zwsp_file)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["path"] == str(zwsp_file)
    assert payload["characters"] == 4  # 数 + ZWSP + 据 + newline

    finding = payload["findings"][0]
    assert finding["codepoint"] == 0x200B
    assert finding["class_"] == "invisible"
    assert finding["fixable"] == "strip"
    assert finding["line"] == 1 and finding["column"] == 2
    assert set(finding) == {
        "index",
        "line",
        "column",
        "char",
        "codepoint",
        "class_",
        "fixable",
        "replacement",
        "note",
    }


def test_a_clean_file_says_clean(tmp_path, capsys):
    path = tmp_path / "clean.txt"
    path.write_text("\u6570\u636e\n", encoding="utf-8")

    assert main(["scan", str(path)]) == 0
    assert "clean" in capsys.readouterr().out


def test_stdin_is_accepted(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(SHU + ZWSP + JU))

    assert main(["scan", "-"]) == 0
    out = capsys.readouterr().out
    assert "<stdin>" in out
    assert "U+200B" in out


def test_scan_refuses_a_non_text_file(tmp_path, capsys):
    """The same guard read_text() gives check -- a PDF is not silently scanned."""
    path = tmp_path / "document.pdf"
    path.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    assert main(["scan", str(path)]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""  # nothing was scanned, so nothing is reported as a finding
    assert "pdf" in captured.err.lower()
    assert "pdftotext" in captured.err


def test_scan_and_check_agree_about_lookalikes(lookalike_file, capsys):
    """Asserted across two APIs, not against a hand-written expectation."""
    main(["check", str(lookalike_file)])
    check_out = capsys.readouterr().out

    main(["scan", "--json", str(lookalike_file)])
    payload = json.loads(capsys.readouterr().out)

    found = [item for item in payload["findings"] if item["class_"] == "lookalike"]
    assert f"{len(found)} look-alike character(s)" in check_out
    assert len(found) == 1


def test_check_output_is_byte_for_byte_unchanged(lookalike_file, capsys):
    """scan was added around check. check is a published contract; it must not have moved.

    Written out in full on purpose: a regression here is a change to output that a
    pipeline may already be parsing, and "looks about right" is not a test.
    """
    assert main(["check", str(lookalike_file)]) == 1

    assert capsys.readouterr().out == (
        f"{lookalike_file}: 1 look-alike character(s) (1 kangxi)\n"
        "    1:4  \u2f8a U+2F8A -> \u8272 U+8272  (KANGXI RADICAL COLOR)\n"
        "\n"
        "1 character(s) would change under `cjkfold fold`.\n"
    )
