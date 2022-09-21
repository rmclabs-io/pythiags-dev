"""Test pipeline fixutres have same contents for gpu and jetson.

Mainly requirede because jetson nveglglessink requires nvegltransform.

"""

from __future__ import annotations

from difflib import unified_diff
from pathlib import Path

from tests.pytest.c_integration.gst_pylaunch_test import ALL_PIPELINES


def _compare_by_lines(left: str, right: str, key: str):
    for delta in unified_diff(
        left.splitlines(keepends=True),
        right.splitlines(keepends=True),
        fromfile="left",
        tofile="right",
        n=0,
    ):
        if any(
            delta.startswith(pattern)
            for pattern in (
                "--- left\n",
                "+++ left\n",
                "+++ right\n",
                "--- right\n",
                "--- right\n",
                "@@",
            )
        ):
            continue
        assert delta.strip().replace(" ", "") in (
            "+!nvegltransform",
            "-!nvegltransform",
        ), (
            f"'{Path(key).stem}' fixture: "
            f"the .jetson and .gpu are too different. "
            "Only 'nvegltransform' is allowed"
        )


def test_consistent_pipelines():
    """Ensure the pipeline fixtures have equivalent between jetson and gpu."""
    matched = {}
    for pipeline in ALL_PIPELINES:
        if any(pipeline.suffix == suffix for suffix in (".jetson", ".gpu")):
            key = pipeline.stem
            try:
                other = matched.pop(key)
                left = pipeline.read_text(encoding="utf-8")
                right = other.read_text(encoding="utf-8")
                _compare_by_lines(left, right, key)
            except KeyError:
                matched[key] = pipeline

    assert not matched, f"Unmatched tests: {matched}"
