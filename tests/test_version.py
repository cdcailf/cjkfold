"""The version is written in three places, so pin them together.

``cjkfold/__init__.py``, the packaging metadata, and ``cjkfold --version``. The CLI
used to disagree with both of the others -- it printed ``cjkfold 0.1.0`` while the
package and the metadata said ``0.1.1`` -- so one test here mutates
``cjkfold.__version__`` instead of asserting today's value. A test that only pins the
current string passes on a hard-coded literal too, and would miss the next bump, which
is exactly how the 0.1.0/0.1.1 split survived.
"""
from __future__ import annotations

import subprocess
import sys
from importlib.metadata import version

import pytest

import cjkfold
from cjkfold.cli import main


def test_version_matches_the_packaging_metadata():
    """``__version__`` is hand-written in __init__.py and again in pyproject.

    Two sources of truth drift, and a wrong ``package.__version__`` is a lie
    that nothing else catches. This test is the thing that catches it.
    """
    assert cjkfold.__version__ == version("cjkfold")


def test_cli_version_equals_the_package_version(capsys):
    """The third place: ``cjkfold --version`` must agree with the package."""
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"cjkfold {cjkfold.__version__}"


def test_cli_version_follows_the_package_attribute(monkeypatch, capsys):
    """Mutation test: move the package version, the CLI must move with it.

    This is the only assertion here that distinguishes "reads the package" from
    "happens to hold the same string today". Restore a literal -- or bind the value
    at import time -- and this test goes red while the two above stay green.
    """
    monkeypatch.setattr(cjkfold, "__version__", "999.0.0-sentinel")
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == "cjkfold 999.0.0-sentinel"


def test_module_entry_point_reports_the_package_version():
    """End-to-end through ``python -m cjkfold``, in a fresh interpreter.

    Covers the path the two tests above cannot: __main__.py, argument parsing and all.
    """
    result = subprocess.run(
        [sys.executable, "-m", "cjkfold", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == f"cjkfold {cjkfold.__version__}"
