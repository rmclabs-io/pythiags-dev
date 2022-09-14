"""Verify cli exctractors."""
import re

import pytest

from pythia.cli.app import EXTRACTOR_PARSER

test_strings = [
    "my_module:my_function@pgie.src",
    "my_module.py:my_function@pgie.sink",
    "my.module:my_function@pgie.src",
    "my/module.py:my_function@pgie.src",
]


@pytest.fixture(name="extractor_parser_re")
def extractor_parser_re_() -> re.Pattern:
    """Parse extractor from cli.

    Returns:
        The compiled pattern, available as a pytest fixture.

    """
    return re.compile(EXTRACTOR_PARSER, flags=re.MULTILINE)


@pytest.mark.parametrize("test_str", test_strings)
def test_parse_extractors_good_from_cli(extractor_parser_re, test_str) -> None:
    """Check correctly defined cli extractors.

    Args:
        extractor_parser_re: pytest fixture - see
            :func:`extractor_parser_re_`
        test_str: pytest parametrized arg - from :obj:`test_strings`.

    """
    match = extractor_parser_re.match(test_str)
    assert match, f"Pattern not found for '{test_str}'"
