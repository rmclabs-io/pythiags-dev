#!/usr/bin/env python

from uuid import uuid4

from pythiags.headless import Standalone
from pythiags.recorder import VideoRecorder

pipeline_str = """videotestsrc
  ! tee
    name=t1
  t1.
  ! xvimagesink
"""
app = Standalone(pipeline_str)
app(background=True)
recorder = VideoRecorder(
    app.pipeline,
    src_tee_name="t1",
    filename_generator=lambda: f"{uuid4()}.webm",
    timeout_sec=0.1,
    window_size_sec=2,
)
from time import sleep

sleep(3)
recorder.record(
    max_delay_sec=1
)  # you should now have a 4-second video from second 1 to second 5
from time import sleep

sleep(1)
recorder.record(
    max_delay_sec=1
)  # you should now have a 4-second video from second 1 to second 5
recorder.record(
    max_delay_sec=1
)  # you should now have a 4-second video from second 1 to second 5
from time import sleep

sleep(3)
