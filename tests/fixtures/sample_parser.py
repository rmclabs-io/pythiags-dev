#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pythiags import Consumer
from pythiags import Producer
from pythiags import logger


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


class ExtractorOk(Producer):
    def extract_metadata(self, pad, info):
        pass


class ExtractorBadSignature(Producer):
    def extract_metadata(self):
        pass


class ExtractorBadInheritance:
    def extract_metadata(self, pad, info):
        pass


class ConsumerOk(Consumer):  # noqa: R0903
    def incoming(self, events):
        pass


class ConsumerBadSignature(Consumer):
    def incoming(self):
        pass


class ConsumerBadInheritance:
    def incoming(self, events):
        pass
