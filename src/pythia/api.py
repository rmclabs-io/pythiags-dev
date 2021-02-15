# -*- coding: utf-8 -*-
"""Common interface for pythia applications with and without Kivy.

.. seealso:: `pythia.app` and `pythia.perf`

"""

import abc
import atexit
from collections import defaultdict
from datetime import datetime
from queue import Queue
from typing import DefaultDict
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from pythia import Gst
from pythia import logger
from pythia.background import StoppableThread
from pythia.consumer import Consumer
from pythia.events import EventsHandler
from pythia.producer import Producer

# TODO: where to add GObject.threads_init()
# <pwoolvett 2021-01-06T15:08:03>


class PythiaRunner(abc.ABC):
    def __init__(
        self,
        pipeline_string: str,
        metadata_extraction_map: Optional[
            Dict[str, Tuple[Producer, Consumer]]
        ] = None,
    ):

        # TODO: where to add self.mainloop = GObject.MainLoop()
        # <pwoolvett 2021-01-06T15:08:03>

        self.running_since = datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
        self.pipeline_string = pipeline_string

        self.metadata_extraction_map = metadata_extraction_map or {}
        self.handlers: DefaultDict[str, List[EventsHandler]] = defaultdict(
            list
        )
        self.workers: DefaultDict[str, List[StoppableThread]] = defaultdict(
            list
        )

        self.__joining: bool = False

    @abc.abstractmethod
    def __call__(self, control_logs=True, *a, **kw):

        self.control_gst_logs(
            skip=not control_logs,
            keep_default_logger=False,
            use_own_logger=True,
        )
        self.connect_bus()

        self.init_events_handlers()
        atexit.register(self.join)

    def control_gst_logs(
        self,
        skip=False,
        disable_debug_logs=False,
        keep_default_logger=False,
        use_own_logger=True,
    ):
        """Modify default Gst loggers.

        Args:
            skip: If set, function call does nothing. Useful for
                scripting.
            disable_debug_logs: If set, completely disable debug logs.
            keep_default_logger: If set, keeps the default gst logger.
            use_own_logger: If set, attaches own logger to the list of
                available gst loggers.

        Debugging handlers negatively impact performance
        # If activated, debugging messages are sent to the debugging
        # handlers. It makes sense to deactivate it for speed issues.

        """
        if skip:
            return
        logger.info(
            f"PythiaRunner: Taking control of Gst debug logger from now on..."
        )

        if disable_debug_logs:
            Gst.debug_set_active(False)
            return Gst.debug_remove_log_function(None)
        else:
            Gst.debug_set_active(True)

        if not keep_default_logger:
            Gst.debug_remove_log_function(None)

        if use_own_logger:
            Gst.debug_add_log_function(self.on_message)

    def connect_bus(self):
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", self.on_eos)
        bus.connect("message::error", self.on_error)

    def init_events_handlers(self):
        for observer_name, (
            extractor,
            consumer,
        ) in self.metadata_extraction_map.items():
            # FIXME: validate this logic, seems outdated <pwoolvett 2021-01-08T15:39:04>
            if observer_name:
                if not (extractor or consumer):
                    msg = f"PythiaApi: Observer element with name '{observer_name}' supplied, but neither extractor nor consumer provided"
                    logger.warning(msg)
                elif not (extractor and consumer):
                    msg = f"PythiaApi: Observer element  with name '{observer_name}' supplied, you must supply both and extractor and consumer provided"
                    raise RuntimeError(msg)
            else:
                if not (extractor or consumer):
                    msg = f"PythiaApi: None of (observer_name, extractor, consumer) provided. Proceeding without extracting deepstream detections"
                    return logger.warning(msg)
                elif extractor and consumer:
                    observer_name = self.pipeline.children[0].name
                    msg = f"PythiaApi: No name for observer element supplied. As both extractor and consumer provided, pythia will use the element named '{observer_name}'"
                    logger.warning(msg)
                else:
                    msg = f"PythiaApi: No name for observer element supplied. you must supply both and extractor and consumer or none of them."
                    return RuntimeError(msg)

            observer = self.pipeline.get_by_name(observer_name)
            if not observer:
                msg = f"PythiaApi: Cannot find element with name '{observer_name}' in pipeline ```{self.pipeline_string}```"
                raise RuntimeError(msg)

            handler = EventsHandler(
                attach_on=observer,
                producer=extractor,
                consumer=consumer,
            )
            self.handlers[observer_name].append(handler)
            self.workers[observer_name].append(handler.run_in_background())

    @abc.abstractproperty
    def pipeline(self) -> Gst.Pipeline:
        """The low-level Gst.Pipeline Element."""

    @abc.abstractmethod
    def on_eos(self, bus, message):
        logger.info("Gstreamer: End-of-stream")
        self.join()

    @abc.abstractmethod
    def on_error(self, bus, message):
        err, debug = message.parse_error()
        logger.error("Gstreamer: %s: %s" % (err, debug))

    def on_message(
        self, category, level, dfile, dfctn, dline, source, message, *user_data
    ):
        log = getattr(
            logger, level.get_name(level).strip().lower(), logger.info
        )
        try:
            return log(message.get())
        except TypeError:
            return log(repr(message))

    def join(self):
        if self.__joining:
            return

        self.__joining = True

        for observer_name, workers in self.workers.items():
            logger.info(f"PythiaApi: Waiting for {observer_name}'s workers...")
            for worker in workers:
                logger.debug(
                    f"PythiaApi: Stopping queue {worker.queue} from {worker}..."
                )
                worker.queue.join()
                logger.debug(f"PythiaApi: Stopping worker {worker}...")
                worker.external_stop = True
            for worker in workers:
                logger.debug(f"PythiaApi: Joining worker {worker}...")
                worker.join()

        self.workers = defaultdict(list)
