"""The CLI's published output, frozen against fixtures.

``check`` output is a contract -- a pipeline may be parsing it -- so these fixtures
exist to make a change to it impossible to miss.  The roadmap asked for exactly
these three files; ``lookalike.txt`` doubles as the corpus the README's example
output came from.

The fixtures were written with escapes and their bytes checked, because a
look-alike typed literally into a file is the hazard this library exists for.
"""

from __future__ import annotations

from pathlib import Path

from cjkfold.cli import main

FIXTURES = Path(__file__).parent / "fixtures"

CLEAN = FIXTURES / "clean.txt"
LOOKALIKE = FIXTURES / "lookalike.txt"
ZWSP = FIXTURES / "zwsp.txt"


def _run(args, capsys):
    code = main(args)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_a_clean_file(capsys):
    code, out, err = _run(["check", str(CLEAN)], capsys)

    assert code == 0
    assert out == f"{CLEAN}: clean\n"
    assert err == ""


def test_the_lookalike_output_is_frozen_byte_for_byte(capsys):
    """Written out in full on purpose. "Looks about right" is not a regression test."""
    code, out, _ = _run(["check", str(LOOKALIKE)], capsys)

    assert code == 1
    assert out == (
        f"{LOOKALIKE}: 3 look-alike character(s) (1 kangxi, 2 radical-supplement)\n"
        "    1:4  \u2f8a U+2F8A -> \u8272 U+8272  (KANGXI RADICAL COLOR)\n"
        "    1:7  \u2ec6 U+2EC6 -> \u89d2 U+89D2  (CJK RADICAL SIMPLIFIED HORN)\n"
        "    2:5  \u2eae U+2EAE -> \U00025ad7 U+25AD7  (CJK RADICAL BAMBOO)\n"
        "\n"
        "3 character(s) would change under `cjkfold fold`.\n"
    )


def test_the_zero_width_fixture_is_the_file_check_cannot_see(capsys):
    """The fixture that motivates ``scan``: a confident all-clear, and it means it.

    This test records a limitation rather than excusing it -- ``scan`` is what
    answers this file, and the second half of the test proves that it does.
    """
    code, out, _ = _run(["check", str(ZWSP)], capsys)

    assert code == 0
    assert out == f"{ZWSP}: clean\n"

    code, out, _ = _run(["scan", str(ZWSP)], capsys)

    assert code == 0
    assert "U+200B" in out
    assert "invisible" in out


def test_all_three_in_one_run(capsys):
    code, out, _ = _run(["check", str(CLEAN), str(LOOKALIKE), str(ZWSP)], capsys)

    assert code == 1
    assert out.startswith(f"{CLEAN}: clean\n{LOOKALIKE}: 3 look-alike character(s)")
    assert out.endswith("3 character(s) would change under `cjkfold fold`.\n")
