"""Pytest setup."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.paths import PEOPLESEGNET
from tests.utils import docker_compose


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
