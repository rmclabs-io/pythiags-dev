"""Repo and dev-specific checks."""

import pytest
from dotenv import dotenv_values
from tests.paths import PROJECT_DIR


@pytest.mark.parametrize("dotenv_file", [*PROJECT_DIR.glob("**/*.env")])
def test_ensure_dotenv_docummented(dotenv_file):
    dotenv_dist = dotenv_file.with_name(f"{dotenv_file.name}.dist")
    assert (
        dotenv_dist.exists()
    ), "Every dotenv must be documented and contain an .env.dist"
    real = dotenv_values(dotenv_file)
    doc = dotenv_values(dotenv_dist)
    for k in {*real.keys(), *doc.keys()}:
        assert k in real
        assert k in doc
