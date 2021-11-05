Using pythiags
============


Using pythiags CLI - A basic example
------------------------------------

Here's a sample on how to start using pythiags cli::


    $ cat ./pipeline.gstp 
    videotestsrc
      pattern={pattern}
    ! nveglglessink
    $ pygst-launch --file=pipeline.gstp --pattern=snow

* Forget about the `\\`, just write a multiline file and feed it to `pygst-launch`.
* The power of this method (besides feeding kwargs from cli) comes from using a metadata extraction map eg for
  deepstream usage - Check the examples in the README.


Using pythiags API
------------------

Here's a sample on how to start using pythials API::


    #!/usr/bin/env python3
    # -*- coding: utf-8 -*-

    """pythiags-api.py."""

    from pythiags.recorder import VideoRecorder
    from pythiags.headless import Standalone


    pipeline_str = """
    videotestsrc
    ! video/x-raw,framerate=30/1
    ! tee
      name=t1
    t1.
    ! fakesink
    """

    app = Standalone.build_and_run(pipeline_str, background=True)
    ...

* Your application is now running in the background!
* To use a blocking call, just replace `background=True` with `background=False`.


Using video recorder
--------------------

Minimal example
+++++++++++++++

Here's a sample on how to set a simple video recorder using pythia::


    #!/usr/bin/env python3
    # -*- coding: utf-8 -*-

    """single-recorder.py - sample pythiags videorecorder usage."""

    from pathlib import Path
    from uuid import uuid4

    from pythiags.recorder import VideoRecorder
    from pythiags.headless import Standalone

    import shutil

    video_storage = Path("/tmp/pythiagsdemo")
    try:
        shutil.rmtree(video_storage)
    except FileNotFoundError:
        pass
    video_storage.mkdir(exist_ok=True, parents=True)

    pipeline_str = """
    videotestsrc
    ! video/x-raw,framerate=30/1
    ! tee
      name=t1
    t1.
    ! fakesink
    """
    app = Standalone.build_and_run(pipeline_str, background=True)

    recorder = VideoRecorder(
        pipeline=app.pipeline,
        src_tee_name="t1",
        filename_generator=lambda: str(video_storage/f"{uuid4()}.webm"),
        timeout_sec=0.1,
        window_size_sec=2,
    )

    from time import sleep

    sleep(3)
    recorder.record()  # so start at 3-winsize=3-2=1
    sleep(1)
    recorder.record()  # just reset the timer, making it one second longer

    sleep(2)
    # timeout

    sleep(2+1)  # wait 3 to ensure no window clash
    recorder.record()  # record once

    while recorder.busy:
        sleep(.1)

    import subprocess as sp

    for path in video_storage.glob("**/*.webm"):
        sp.run(
            f'ffprobe {path} |& egrep "Input|Duration|start"',
            shell=True,
            executable="/bin/bash",
        )

* you should see a video with length 5, starting from second 1
* you should see a video with length 4, starting from second 7


Using multiple video recorders
++++++++++++++++++++++++++++++

Here's another sample, this time a little bit more involved as we're attaching multiple
recorders to a single pipeline::

    #!/usr/bin/env python3
    # -*- coding: utf-8 -*-

    """mutli-recorder.py - a pythiags recipe to record several videos in a gst pipeline."""

    from pathlib import Path
    from typing import Dict
    from typing import Union
    from uuid import uuid4

    from pythiags.recorder import VideoRecorder as VideoRecorderBase
    from pythiags.headless import Standalone


    class VideoRecorder(VideoRecorderBase):
        def __init__(
            self,
            filename_suffix: str,
            video_storage: Union[Path, str],
            *a,
            **kw,
        ):
            video_storage = Path(video_storage)
            video_storage.mkdir(exist_ok=True, parents=True)
            super().__init__(
                *a,
                filename_generator=lambda: f"{video_storage}/{uuid4()}_{filename_suffix}.webm",
                **kw,
            )


    class MultiVideoRecorder:
        def __init__(
            self,
            src_tee_prefix: str,
            pad_number_to_file_suffix: Dict[int, str],
            video_storage: Union[Path, str],
            recorder_cls=VideoRecorder,
            **recorder_kw,
        ):
            self.recorders = {}
            for pad_number, filename_suffix in pad_number_to_file_suffix.items():
                self.recorders[pad_number] = recorder_cls(
                    filename_suffix=filename_suffix,
                    video_storage=video_storage,
                    src_tee_name=f"{src_tee_prefix}_{pad_number}",
                    **recorder_kw,
                )

        def record(self, source_id, *a, **kw):
            recorder = self.recorders[int(source_id)]
            return recorder.record(*a, **kw)

        @property
        def busy(self) -> bool:
            return any(recorder.busy for recorder in self.recorders.values())

    import shutil

    video_storage = Path("/tmp/pythiagsdemo")
    try:
        shutil.rmtree(video_storage)
    except FileNotFoundError:
        pass

    pipeline_str = """
    videotestsrc
    ! video/x-raw,framerate=30/1
    ! tee
      name=tee_0
    tee_0.
    ! fakesink

    videotestsrc
      pattern=ball
    ! video/x-raw,framerate=30/1
    ! tee
        name=tee_1
    tee_1.
      ! fakesink
    """
    app = Standalone.cli_run(pipeline_str, background=True)

    recorder = MultiVideoRecorder(
        pipeline=app.pipeline,
        src_tee_prefix="tee",
        pad_number_to_file_suffix={0: "first", 1: "second"},
        video_storage=video_storage,
        timeout_sec=0.1,
        window_size_sec=2,
    )


    from time import sleep

    sleep(3)
    recorder.record(0, max_delay_sec=1)
    from time import sleep

    sleep(1)
    recorder.record(1, max_delay_sec=1)
    sleep(1)
    recorder.record(1, max_delay_sec=1)
    from time import sleep


    while recorder.busy:
        sleep(.1)

    import subprocess as sp

    for path in video_storage.glob("**/*.webm"):
        sp.run(
            f'ffprobe {path} |& egrep "Input|Duration|start"',
            shell=True,
            executable="/bin/bash",
        )

* you should see a video with length 4, starting from second 1
* you should see a video with length 5, starting from second 2

Customizing video recorder's ringbuffer
+++++++++++++++++++++++++++++++++++++++

If you want to customize either the ringbuffer bin or record bin, here's an example for
deesptream, where the recorder requires a different ringbuffer bin (specifically, using
the `nvvideoconvert` element). This is because, by default, the decodebin element will
choose to use nv hw decoder elements which allocate buffers in gpu memory::


    #!/usr/bin/env python3
    # -*- coding: utf-8 -*-

    """custom-ringbuffer.py - sample pythiags videorecorder usage."""

    from pathlib import Path
    import shutil
    from uuid import uuid4

    from pythiags.recorder import VideoRecorder
    from pythiags.recorder.ring_buffer import RingBuffer
    from pythiags.headless import Standalone


    class GPU2CPURingBuffer(RingBuffer):
        RINGBUFFER_BIN_STRING = """
                queue
                  name=ringbuffer_input_queue
                ! nvvideoconvert
                ! capsfilter
                  name=ringbuffer_input_capsfilter
                  caps=video/x-raw,format=I420
                ! appsink
                  name=ringbuffer_appsink
                  emit-signals=true
                  async=false
            """

    video_storage = Path("/tmp/pythiagsdemo")
    try:
        shutil.rmtree(video_storage)
    except FileNotFoundError:
        pass
    video_storage.mkdir(exist_ok=True, parents=True)

    pipeline_str = """
    filesrc
      location=sample_720p.mp4
    ! decodebin
    ! tee
      name=t1
    
    t1.
    ! queue
    ! nvvideoconvert
    ! nveglglessink

    """
    app = Standalone.build_and_run(pipeline_str, background=True)

    recorder = VideoRecorder(
        pipeline=app.pipeline,
        src_tee_name="t1",
        filename_generator=lambda: str(video_storage/f"{uuid4()}.webm"),
        timeout_sec=0.1,
        window_size_sec=2,
        ring_buffer_cls=GPU2CPURingBuffer,
    )

    from time import sleep

    sleep(3)
    recorder.record()  # so start at 3-winsize=3-2=1
    sleep(1)
    recorder.record()  # just reset the timer, making it one second longer

    sleep(2)
    # timeout

    sleep(2+1)  # wait 3 to ensure no window clash
    recorder.record()  # record once

    while recorder.busy:
        sleep(.1)

    import subprocess as sp

    for path in video_storage.glob("**/*.webm"):
        sp.run(
            f'ffprobe {path} |& egrep "Input|Duration|start"',
            shell=True,
            executable="/bin/bash",
        )

* you should see a video with length 5, starting from second 1
* you should see a video with length 4, starting from second 7
