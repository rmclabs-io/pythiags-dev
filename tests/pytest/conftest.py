"""Pytest setup."""

from __future__ import annotations

import json
from pathlib import Path
from time import sleep
from types import SimpleNamespace
from typing import Generator
from typing import Generic
from typing import Literal
from typing import Optional
from typing import TypeVar

import pytest

from tests.paths import PEOPLESEGNET
from tests.utils import docker_compose
from tests.utils import IS_JETSON

R = TypeVar("R")


class Result(Generic[R]):  # noqa: C0115,R0903
    def get_result(self) -> R:  # noqa: C0116
        ...


class Item(Generic[R]):  # noqa: C0115,R0903
    report: Optional[R] = None


Outcome = Literal["skipped", "passed", "failed"]


@pytest.fixture
def peoplesegnet() -> Path:
    """Return directory where the peoplesegnet model is located.

    Returns:
        Path to the peoplesegnet directory.

    Raises:
        AssertionError: peoplesegnet model not downloadded.

    """
    assert PEOPLESEGNET.exists(), (
        f"PeopleSegNet not found at {PEOPLESEGNET}."
        " Please ensure the path is correct or download the model."
    )
    return PEOPLESEGNET


def _listen_memory(backend) -> list:
    return [*backend.deque]


def _listen_redis(backend) -> list:
    raw = backend.client.xread({backend.stream: 0})
    data = raw[0][1]  # single stream, keep values only
    return [json.loads(v[b"data"].decode()) for v in dict(data).values()]


def _listen_kafka(backend) -> list:
    from kafka import KafkaConsumer

    consumer = KafkaConsumer(
        backend.stream,
        bootstrap_servers=backend.bootstrap_servers,
        auto_offset_reset="earliest",
        consumer_timeout_ms=1000,
        value_deserializer=lambda m: json.loads(m.decode("ascii")),
    )
    return [message.value for message in consumer]


LISTENERS = {
    "memory": _listen_memory,
    "redis": _listen_redis,
    "kafka": _listen_kafka,
}


@pytest.fixture
def setup_backend(request):
    """Ensure docker-compose service is runnning given its schema.

    Args:
        request: provided by indirect pytest parametrization. Its single
            'param' attribute contains the connection string to connect
            to the remote backend service, which is setup via
            docker-compose.

    Yields:
        Simple namespace containing the uri and a function to read data
            from the backend.

    """
    uri, timeout_sec = request.param
    backend = uri.split("://")[0]

    listen = LISTENERS[backend]
    if backend != "memory":
        docker_compose("up -d", backend, timeout_sec=timeout_sec)
    namespace = SimpleNamespace()
    namespace.uri = uri
    namespace.listen = listen
    try:
        yield namespace
    finally:
        if backend != "memory":
            docker_compose("kill")
            docker_compose("down")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(
    item: Item[Outcome],
    call: pytest.CallInfo[None],  # noqa: W0613
) -> Generator[None, Result[Outcome], None]:
    """Inject test result to item node so its accesable by fixtures.

    Args:
        item: the current test invocation item.
        call: Result/Exception info of a function invocation.

    Yields:
        Execute all other hooks to obtain the report object

    See Also:
        `_pytest.hookspec.pytest_runtest_makereport`
        https://docs.pytest.org/en/7.1.x/reference/reference.html#pytest.hookspec.pytest_runtest_makereport
        https://docs.pytest.org/en/7.1.x/example/simple.html?highlight=pytest_runtest_makereport#making-test-result-information-available-in-fixtures

    """
    outcome = yield
    item.report = outcome.get_result()


def _do_cooldown():
    sleep(1)
    if IS_JETSON:
        sleep(5)


@pytest.fixture
def _nvidia_cooldown(request) -> Generator[None, None, None]:
    """Force wait time to avoid segfault.

    Args:
        request: pytest fixture.

    Yields:
        None

    Raises:
        NotImplementedError: test outcome not handled.

    """
    yield
    outcome = request.node.report.outcome
    if outcome in ("skipped",):
        return
    if outcome in ("passed", "failed"):
        _do_cooldown()
        return
    raise NotImplementedError
