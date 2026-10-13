"""The version is written in two places, so pin them together."""
from __future__ import annotations

from importlib.metadata import version

import cjkfold


def test_version_matches_the_packaging_metadata():
    """``__version__`` is hand-written in __init__.py and again in pyproject.

    Two sources of truth drift, and a wrong ``package.__version__`` is a lie
    that nothing else catches. This test is the thing that catches it.
    """
    assert cjkfold.__version__ == version("cjkfold")
