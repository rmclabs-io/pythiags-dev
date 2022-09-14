"""Python extensions and decorators."""

from __future__ import annotations

import importlib.util
import platform
import sys
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any
from typing import Iterable
from typing import Optional
from typing import Tuple
from typing import TypeVar

RT = TypeVar("RT", Path, None)  # return type
T = TypeVar("T")


def not_empty(path: Path) -> Path:
    """Raise if receives an empty value.

    Args:
        path: The file to check for emptiness.

    Returns:
        The decorated function.

    Raises:
        EOFError: The received file is empty.

    """
    if path is None:
        return path
    if not path.stat().st_size:
        raise EOFError(f"File {path} is empty")
    return path


def not_none(value: Optional[Any]):
    """Raise if receives `None`.

    Args:
        value: The value which should not be none.

    Returns:
        The received value.

    Raises:
        ValueError: The received value was `None`.

    """

    if value is None:

        raise ValueError("Received disallowed `None`")
    return value


def get_arch() -> str:
    """Return system arch.

    Returns:
        platform, like `uname machine`.

    """
    return platform.uname()[4]


def import_from_path(name: str, path: str | Path) -> ModuleType:
    """Import a module from a filepath.

    Args:
        name: the name to use for the module when importing.
        path: path to the python file to import as a module.

    Returns:
        The imported module.

    Raises:
        ImportError: unable to get spec from location

    See Also:
        `importlib.util.spec_from_file_location`

    """
    spec = importlib.util.spec_from_file_location(name, str(path))
    if not spec or not spec.loader:
        raise ImportError(f"Failed to import from {path=}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def import_from_str(module: str, *, name=None, suffix: str = "") -> ModuleType:
    """Import python file as a module or from its path.

    Args:
        module: name of the python file to import.
        name: ``__name__`` to use when import thing the module. If not
            set, defaults to the file's stem.
        suffix: file suffix. If set, load `name` as a file. Otherwise,

    Returns:
        The improted module.

    """
    if suffix:
        path = Path(module).with_suffix(suffix)
        return import_from_path(name or path.stem, path)
    return import_module(module)


def grouped(iterable: Iterable[T], size=2) -> Iterable[Tuple[T, ...]]:
    """Iterate by groups.

    Args:
        iterable: container for the data to group by.
        size: size of the groups

    Returns:
        zip containing tuples of values.

    Example:
        >>> [*grouped(range(10),3)]
        [(0, 1, 2), (3, 4, 5), (6, 7, 8)]

    """
    return zip(*[iter(iterable)] * size)


def remove_suffix(input_string: str, suffix: str) -> str:
    """Remove trailing substring.

    Args:
        input_string: Input string to look for the suffix.
        suffix: The substring to match at the end of the input string.

    Returns:
        If the string ends with the suffix string and that suffix
            is not empty, return string[:-len(suffix)]. Otherwise, return a
            copy of the original string

    Backport of stdlib@3.9

    """
    if suffix and input_string.endswith(suffix):
        return input_string[: -len(suffix)]
    return input_string


def remove_prefix(input_string: str, prefix: str) -> str:
    """Remove leading substring.

    Args:
        input_string: Input string to look for the suffix.
        prefix: The substring to match at the start of the input string.

    Returns:
        If the string ends with the suffix string and that suffix
            is not empty, return string[:-len(suffix)]. Otherwise, return a
            copy of the original string

    Backport of stdlib@3.9

    """
    if prefix and input_string.startswith(prefix):
        return input_string[len(prefix) :]
    return input_string
