# -*- coding: utf-8 -*-
"""Events handling."""

import datetime
from queue import Queue

from pythiags import Gst
from pythiags import logger
from pythiags.background import EventsWorker
from pythiags.consumer import Consumer
from pythiags.models import Events
from pythiags.producer import Producer
from pythiags.utils import validate_processor


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
        meta = self.producer.extract_metadata(pad, info)
        if meta:
            self.events_queue.put(meta)
        return Gst.PadProbeReturn.OK

    def run_in_background(self):
        self.worker = EventsWorker(
            callback=self.consumer.incoming,
            queue=self.events_queue,
            name=f"{type(self.producer).__name__} -> {type(self.consumer).__name__}",
        )
        self.worker.start()
        return self.worker
