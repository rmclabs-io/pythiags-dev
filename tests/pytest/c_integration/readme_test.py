"""Make sure the examples in the readme are in sync and working.

Each time the README changes, these tests should be outdated, to make
sure code samples still make sense.

README.md needs to have the following structure:

```md
<!-- section name -->
* <instruction>:

<code fence start>
...
<code fence end>
```

Where `<instruction>` mus be one of:


```md
Create a file `<file name>` with:
```

or

```md
run the application with:
```

"""
from __future__ import annotations

import re
import subprocess as sp
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from typing import Literal

import pytest
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from pythia.utils.ext import remove_prefix
from pythia.utils.ext import remove_suffix

from tests.paths import README
from tests.pytest.c_integration.producers_test import BackendChecker


@pytest.fixture(name="readme_tree")
def readme_tree_() -> SyntaxTreeNode:
    """Parse README markdown into markdown tree.

    Returns:
        Tree representation of the readme file.

    """
    text = README.read_text(encoding="utf-8")
    tokens = MarkdownIt().parse(text)
    return SyntaxTreeNode(tokens)


@pytest.fixture(name="readme_examples")
def readme_examples_(
    readme_tree,
) -> dict[str, dict[Literal["instruction", "fence"], str]]:
    """Parse README markdown into markdown tree.

    Args:
        readme_tree: pytest fixture for the readme markdown tree.

    Returns:
        Code examples in the README

    """
    examples = {}
    for i, node in enumerate(readme_tree):
        if node.type != "fence":
            continue
        instruction: str = (
            readme_tree[i - 1].children[0].children[0].children[0].content
        )
        key = remove_suffix(
            remove_prefix(readme_tree[i - 2].content, "<!-- "), " -->\n"
        )
        data: dict[Literal["instruction", "fence"], str] = {
            "instruction": instruction,
            "fence": cast(str, node.content),
        }
        examples[key] = data
    return examples


def _dump_fence(example, tmpdir):
    instruction = example["instruction"]
    probe_txt = example["fence"]
    probe_filename = re.match(
        r"Create a file `(?P<name>.*?\.[pytxt]+)` with:", instruction
    ).groupdict()["name"]
    dst = tmpdir / probe_filename
    Path(dst).write_text(probe_txt, encoding="utf-8")
    return dst


def _run_fence(example, tmpdir):
    instruction = example["instruction"]
    assert instruction == "run the application with:"
    command = example["fence"].lstrip("$ ").rstrip("\n ")

    proc = sp.run(
        command,
        text=True,
        stderr=sp.STDOUT,
        stdout=sp.PIPE,
        shell=True,  # noqa: S602
        cwd=tmpdir,
        check=False,
    )

    if proc.returncode:
        raise RuntimeError(proc.stdout)
    return command, proc


def test_gst_pylaunch(readme_examples, tmpdir):
    """Parse gst-pylaunch example in the README.

    Args:
        readme_examples: Dictionary containing named examples of the
            readme, which in turn contain 'instruction' and 'fence' keys
            containing parsed makrdown contents. It is a pytest fixture.
        tmpdir: pytest temporary directory fixture.

    """
    _dump_fence(readme_examples["gst-pylaunch probe"], tmpdir)
    _dump_fence(readme_examples["gst-pylaunch pipeline"], tmpdir)
    command, proc = _run_fence(readme_examples["gst-pylaunch console"], tmpdir)

    dst = Path(command.split("--output")[1].split()[0].lstrip("="))
    assert dst.exists(), "Output file not found"
    assert dst.stat().st_size, "Empty output file"
    assert '{"frame_num": 0, "label": "Person"' in proc.stdout


DETECTIONS_STREAM_URI = ("kafka:9092", "raw_detections")
EVENTS_STREAM_URI = ("kafka:9092", "app_events")
BACKEND_TIMEOUT = {
    "kafka": (
        "kafka://",
        30,
    ),
}


@dataclass
class _MockKafkaBackend:
    bootstrap_servers: list[str]
    stream: str


@pytest.mark.parametrize(
    "setup_backend",
    BACKEND_TIMEOUT.values(),
    ids=BACKEND_TIMEOUT.keys(),
    indirect=True,
)
def test_decorator(
    readme_examples,
    setup_backend: BackendChecker,
    tmpdir,
):
    """Parse api example in the README.

    Args:
        readme_examples: Dictionary containing named examples of the
            readme, which in turn contain 'instruction' and 'fence' keys
            containing parsed makrdown contents. It is a pytest fixture.
        setup_backend: pytest fixture, required for the kafka messaging.
        tmpdir: pytest temporary directory fixture.

    Raises:
        RuntimeError: The api console command failed.

    """

    _dump_fence(readme_examples["gst-pylaunch pipeline"], tmpdir)
    _dump_fence(readme_examples["api application"], tmpdir)

    _, proc = _run_fence(readme_examples["api console"], tmpdir)

    if proc.returncode:
        raise RuntimeError(proc.stdout)

    dst = Path("/tmp/overlayed.mp4")  # noqa: S108
    assert dst.exists(), "Output file not found"
    assert dst.stat().st_size, "Empty output file"

    received_detections = setup_backend.listen(
        _MockKafkaBackend([DETECTIONS_STREAM_URI[0]], DETECTIONS_STREAM_URI[1])
    )
    assert received_detections[0]["frame_num"] == 0
    assert received_detections[0]["label"] == "Person"
    received_events = setup_backend.listen(
        _MockKafkaBackend([EVENTS_STREAM_URI[0]], EVENTS_STREAM_URI[1])
    )
    assert len(received_events) == 2
    assert received_events[0]["CONDITION"] == "STARTED"
    assert received_events[1]["CONDITION"] == "EOS"
