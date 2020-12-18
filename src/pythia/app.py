#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Camera Example

This example demonstrates a simple use of the camera. It shows a window
with a buttoned labelled 'play' to turn the camera on and off. Note that
not finding a camera, perhaps because gstreamer is not installed, will
throw an exception during the kv language processing.

Taken from kivy camera example https://kivy.org/doc/stable/examples/gen__camera__main__py.html. 

Modified by RMCLabs @ Q4 2020 for demonstration purposes.

"""
from datetime import datetime

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivy.uix.floatlayout import FloatLayout

from pythia.detections import DetectionLogger
from pythia.detections import Storage


Builder.load_string(
    """
#:import GSCameraWidget pythia.video.GSCameraWidget
<Box>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: 0, 1, 0, .5
        Rectangle:
            # self here refers to the widget i.e FloatLayout
            pos: self.pos
            size: self.size
    GSCameraWidget:
        canvas.before:
            Color:
                rgba: 1, 0, 0, .5
            Rectangle:
                pos: self.pos
                size: self.size
        pipeline_string: root.pipeline_string
        id: camera
        # resolution: (640, 480)
        resolution: (-1, -1)
        play: True
"""
)


class Box(FloatLayout):
    pipeline_string = StringProperty()
    """Pipeline_string to build Gstreamer Pipeline."""


class PythiaApp(App):
    def __init__(self, pipeline_string, **kwargs):
        self.running_since = datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
        self.pipeline_string = pipeline_string
        self.storage = Storage(self.running_since)
        self.detection_logger = DetectionLogger()
        super().__init__(**kwargs)

    def build(self):
        box = Box(pipeline_string=self.pipeline_string)
        return box

    def monitor_detections(self, element):
        from pythia.detections import DetectionsHandler

        self.handler = DetectionsHandler(
            element, [self.storage, self.detection_logger,],
        )
