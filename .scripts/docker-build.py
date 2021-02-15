#!/usr/bin/env python3

import re
import shlex
import subprocess as sp
import sys

CLEANER = re.compile(r"\s+", re.MULTILINE)


def simple_spaces(multiline: str) -> str:
    return CLEANER.sub(" ", multiline)


def maybe_qoute(text: str) -> str:
    clean = text.strip()
    if " " not in clean:
        return clean
    return f"'{clean}'"


def yamlarray2bashkw(yaml_array: str, joiner, sep="\n"):
    return " ".join(
        f"{joiner} {maybe_qoute(element)}" for element in yaml_array.split(sep)
    )


def yamlarray2labels(labels: str, sep="\n"):
    return yamlarray2bashkw(labels, "--label", sep=sep)


def yamlarray2tags(tags: str, sep="\n"):
    return yamlarray2bashkw(tags, "--tag", sep=sep)


def maybe_target(target):
    if target:
        return f"--target {target}"
    return ""


def build_cmd(
    labels,
    tags,
    dockerfile="Dockerfile",
    context=".",
    target="",
):
    return simple_spaces(
        f"""docker build {yamlarray2labels(labels)} {yamlarray2tags(tags)}
        {maybe_target(target)}
        --file {dockerfile}
        {context}
    """
    )


if __name__ == "__main__":
    sys.exit(sp.call(shlex.split(build_cmd(*sys.argv[1:]))))
