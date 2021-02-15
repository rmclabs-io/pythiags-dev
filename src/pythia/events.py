# -*- coding: utf-8 -*-
"""Events handling."""

import datetime
from queue import Queue

from pythia import Gst
from pythia import logger
from pythia.background import EventsWorker
from pythia.consumer import Consumer
from pythia.models import Events
from pythia.producer import Producer


def validate_processor(producer, klass):
    if not isinstance(producer, klass):
        msg = f"DetectionsHandler: Invalid {producer}: must subclass {klass}"
        logger.error(msg)
        raise ValueError(msg)
    return producer


class EventsHandler:
    """Internal event handling system - Minimal Implementation."""

    def __init__(
        self,
        attach_on,
        producer: Producer,
        consumer: Consumer,
    ):
        self.running_since_dt = datetime.datetime.now()
        self.events_queue: Queue[Events] = Queue()

        self.producer = validate_processor(producer, Producer)
        self.consumer = validate_processor(consumer, Consumer)
        if attach_on.get_metadata("long-name") == "AppSink":
            logger.warning(
                f"Sink element detected at {attach_on}."
                " Attaching to sink pad instead."
            )
            self.attach_buffer_probe(attach_on.get_static_pad("sink"))
        else:
            self.attach_buffer_probe(attach_on.get_static_pad("src"))

    def attach_buffer_probe(self, pad: Gst.Pad):
        """Attach `buffer_probe_cb` as a buffer probe.

        Args:
            pad: Source or sink pad to attach the callback.

        """

        pad.add_probe(Gst.PadProbeType.BUFFER, self.buffer_probe_cb)

    def buffer_probe_cb(
        self, pad: Gst.Pad, info: Gst.PadProbeInfo
    ) -> Gst.PadProbeReturn:
        """Store the output of the producers callback in a queue."""
        self.events_queue.put(self.producer.extract_metadata(pad, info))
        return Gst.PadProbeReturn.OK

    def run_in_background(self):
        self.worker = EventsWorker(
            callback=self.consumer.incoming, queue=self.events_queue
        )
        self.worker.start()
        return self.worker
