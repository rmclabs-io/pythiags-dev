"""Testing utilities."""
from __future__ import annotations

import contextlib
import os
import re
import subprocess as sp
import sys
from datetime import datetime
from difflib import unified_diff
from pathlib import Path
from shlex import split
from threading import Thread
from time import sleep
from typing import Callable
from typing import Literal

from typer.testing import CliRunner

from pythia.cli.app import app
from pythia.utils.ext import get_arch

from tests.paths import DOCKER


def cleanup(string: str) -> str:
    """Replace multiple spaces (and newlines) with single spaces.

    Args:
        string: The string to clean

    Returns:
        The input string but with only single spaces.

    """
    return re.sub(r"\s+", " ", string)


def diff(real: str, expected: str) -> str:
    """Compare two strings."""  # noqa: DAR101,DAR201
    return "".join(
        unified_diff(
            cleanup(real).strip().replace(" ", "\n").splitlines(keepends=True),
            cleanup(expected)
            .strip()
            .replace(" ", "\n")
            .splitlines(keepends=True),
            fromfile="real",
            tofile="expected",
            n=0,
        )
    )


def roundup(target: list | dict | float | str, digits=2):
    """Round floats iteratively.

    Args:
        target: wither a 'roundable', or a collection of roundables.
        digits: round precision.

    Returns:
        Same datatype as input but with every 'roundable' rounded

    Raises:
        NotImplementedError: unsuported data type

    """
    if isinstance(target, list):
        return list(map(roundup, target))
    if isinstance(target, dict):
        return {k: roundup(v) for k, v in target.items()}
    if isinstance(target, (float, int)):
        return round(target, digits)
    if isinstance(target, str):
        return target
    raise NotImplementedError


@contextlib.contextmanager
def timer(timeout: int, callback: Callable):
    """Run callback in secondary thread after a specified timeout.

    Args:
        timeout: Seconds to wait before executing the callback.
        callback: Function to execute once the timeout has passed.

    Yields:
        nothing.

    """

    cancel = False

    def wrapper():
        sleep(timeout)
        if not cancel:
            callback()

    timer_ = Thread(target=wrapper, daemon=True)
    try:
        timer_.start()
        yield
    finally:
        cancel = True


def _no_deepstream_or_hardware_available() -> bool:
    return (
        sp.run(  # noqa: S603
            ["gst-inspect-1.0", "nvinfer"],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
            check=False,
        ).returncode
        != 0
    )


def __run_setup(pipeline_file: Path, **kw):
    cmd = f"gst-pylaunch -p {pipeline_file}"
    env = {
        **{
            "GST_DEBUG": "3",
            **os.environ,
        },
        **kw.get("env", {}),
    }
    return split(cmd), env


def _run_pipeline(monkeypatch, pipeline_file: Path, **kw) -> str:
    runner = CliRunner(
        echo_stdin=True,
        mix_stderr=True,
    )
    cmd, env = __run_setup(pipeline_file, **kw)
    with monkeypatch.context() as ctx:
        ctx.setattr(sys, "argv", cmd)
        for name, value in env.items():
            ctx.setenv(name, value)
        result = runner.invoke(app, cmd)
    assert result.exit_code == 0
    return result.stdout


def _run_pipeline_sp(pipeline_file: Path, **kw) -> str:
    cmd, env = __run_setup(pipeline_file, **kw)
    try:
        return sp.check_output(  # noqa: S603
            cmd,
            text=True,
            stderr=sp.PIPE,
            env=env,
        )
    except sp.CalledProcessError as exc:
        raise AssertionError(f"cmd=\n```\n{cmd}\n``` failed") from exc


COMPOSE_CMD = """
  docker-compose -f {compose_file}
  {command}
  {service}
"""


def docker_compose(
    command: Literal["up -d", "down", "kill"],
    service: Literal["redis", "kafka", ""] = "",
    timeout_sec: int = 10,
    poll_sec: float = 0.1,
) -> str:
    """Run a docker-compose command.

    Args:
        command: the compose command to run. If its not 'down' or
            'kill', will also await for the specified service to be
            healthy.
        service: optional target service.
        timeout_sec: Maximum wait time for service healthiness.
        poll_sec: Delay between consecutive service healthiness checks.

    Returns:
        The command's stdout

    Raises:
        TimeoutError: healthcheck not passing after max timeout.

    """
    compose_file = DOCKER / "docker-compose.yml"
    cmd = COMPOSE_CMD.format(
        compose_file=compose_file,
        command=command,
        service=service if command == "up -d" else "",
    )
    cmd_response = sp.check_output(split(cmd), text=True)  # noqa: S603
    if command in ("down", "kill"):
        return cmd_response

    ps_cmd = COMPOSE_CMD.format(
        compose_file=compose_file,
        command="ps",
        service=service if command == "up -d" else "",
    )

    start = datetime.now()
    while True:
        ps_response = sp.check_output(split(ps_cmd), text=True)  # noqa: S603
        if "Up (healthy)" in ps_response:
            break
        sleep(poll_sec)
        if (datetime.now() - start).total_seconds() >= timeout_sec:
            docker_compose("kill", service)
            docker_compose("down")
            raise TimeoutError(
                f"Service {service} not healthy after {timeout_sec} [s]"
            )
    return cmd_response


NO_NVIDIA = _no_deepstream_or_hardware_available()
IS_JETSON = get_arch() == "aarch64"
