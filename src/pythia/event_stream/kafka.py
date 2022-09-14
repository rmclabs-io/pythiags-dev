"""kafka-backed event stream storage."""
from __future__ import annotations

import json
from typing import List

from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient
from kafka.admin import NewTopic

from pythia.event_stream.base import Backend as Base


class Backend(Base):
    """Simple backend to post messages using :class:`KafkaProducer`."""

    _client: KafkaProducer | None = None

    @property
    def host(self) -> str:
        """Exctract the 'host' from the netloc in the uri.

        Returns:
            The host contained in the uri's netloc.

        """
        return self.netloc["host"]

    @property
    def port(self) -> int:
        """Exctract the 'port' from the netloc in the uri.

        Returns:
            The port contained in the uri's netloc.

        """
        return int(self.netloc["port"])

    @property
    def client(self) -> KafkaProducer:
        """Kafka producer lazy-loader.

        Returns:
            Initialized producer, guaranteed to be both connected and
                have the stream created as a topic.

        """
        if not self._client:
            self.connect()
        return self._client  # type: ignore

    @property
    def bootstrap_servers(self) -> List[str]:
        """Singular list containing 'host:port'.

        Returns:
            Single-element list containing a connection of the form
                'host:port'

        """
        return [f"{self.host}:{self.port}"]

    def connect(self) -> None:
        """Instantiate a topic connected kafkaproducer.

        This method is in charge of creating the producer, making sure
        it is properly connected, and ensure the topic which is used to
        post messages actually exists, creating it otherwise.

        Raises:
            ConnectionError: kafka producer is not 'bootstrap_connected'

        """
        self._client = KafkaProducer(bootstrap_servers=self.bootstrap_servers)
        print("Checking kafka connection...")
        if not self._client.bootstrap_connected():
            raise ConnectionError
        print("kafka connection OK")

        print("Checking kafka topic...")
        admin = KafkaAdminClient(
            bootstrap_servers=self.bootstrap_servers, api_version=(0, 9)
        )
        if self.stream not in admin.list_topics():
            admin.create_topics(
                new_topics=[
                    NewTopic(
                        name=self.stream,
                        num_partitions=1,
                        replication_factor=1,
                    )
                ],
                validate_only=False,
            )
            print("kafka topic created")
        print("kafka topic OK")

    def post(self, data) -> None:
        """Make the kafka producer send serialized data.

        Args:
            data: the data to append. Can be any python object.

        """

        self.client.send(self.stream, json.dumps(data).encode())
