"""Test imports."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

import pythia
from pythia.utils.ext import import_from_path


def pythia_submodules() -> Iterator[Path]:
    """Get all paths to test using `**/*.py` glob.

    Returns:
        All descendant python files.

    """
    return Path(pythia.__file__).parent.glob("**/*.py")


SUBMODULES = {path.stem: path for path in pythia_submodules()}


@pytest.mark.parametrize("path", SUBMODULES.values(), ids=SUBMODULES.keys())
def test_importable(path: Path):
    """Validate python file syntax by importing it as a module.

    Args:
        path: Python module to be imported

    """
    import_from_path("module_under_test", path)
