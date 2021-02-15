#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pythia import Consumer
from pythia import logger


class Process(Consumer):  # noqa: R0903
    def incoming(self, events):
        for detection in events:
            log = logger.warning if detection.label == "Car" else logger.info
            log(
                "Detection: Found %s in frame %s, located at %s (camera %s)",
                detection.label,
                detection.frame_num,
                detection.detector_bbox,
                detection.source_id,
            )
