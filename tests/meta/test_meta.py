"""Repo and dev-specific checks."""

import pytest
from dotenv import dotenv_values
from tests.paths import PROJECT_DIR


@pytest.mark.parametrize("dotenv_file", [*PROJECT_DIR.glob("**/*.env")])
def test_ensure_dotenv_docummented(dotenv_file):
    """Dotenv files must have their `.env.dist` counterparts.

    In CI, there wont probably be .env, so it does not make sense. This
    is intended to be run as part of the test suite from the provided
    pre-commit hook.
    """
    dotenv_dist = dotenv_file.with_name(f"{dotenv_file.name}.dist")
    assert (
        dotenv_dist.exists()
    ), f"{dotenv_file} must have a documented .env.dist counterpart"

    real = dotenv_values(dotenv_file)
    doc = dotenv_values(dotenv_dist)
    for k in {*real.keys(), *doc.keys()}:
        assert k in real, f"`k` in {dotenv_dist} but not in {dotenv_file}"
        assert k in doc, f"`k` in {dotenv_file} but not in {dotenv_dist}"
