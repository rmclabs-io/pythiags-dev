import re
import warnings
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep

from behave import fixture
from behave import given
from behave import then
from behave import use_fixture
from behave import when
from tests import video_stats

from pythiags import Gst
from pythiags.headless import Standalone
from pythiags.recorder import VideoRecorder
from pythiags.utils import get_by_name
from pythiags.utils import get_static_pad

START_ALLOWED_ERROR_SEC = 2 * 0.033  # 2 frame at 30fps
"""Maximum time difference between expected and generated video start time"""
DURATION_ALLOWED_ERROR_SEC = 2 * 0.033  # 2 frame at 30fps
"""Maximum time difference between expected and generated video duration"""


def delay_with_offset(offset_getter, delay):

    pre = datetime.now()
    while True:
        try:
            until = offset_getter() + timedelta(seconds=float(delay))
            break
        except AttributeError:
            sleep(1e-4)

    while datetime.now() < until:
        sleep(1e-4)

    post = datetime.now()
    delta = post - pre
    print(f"delay_with_offset took {delta} instead of {delay} ")
    return


INTER_WINDOW_DELAY = 2.1
"""window size multiplier for a delay to ensure two record calls produce different videos"""

INTRA_WINDOW_DELAY = 0.5
"""window size multiplier for a delay to ensure two record calls produce same videos"""


def wait_between_record_signals(num, within_or_outside, window):
    if within_or_outside == "within":
        delay = window * INTRA_WINDOW_DELAY
    elif within_or_outside == "outside":
        delay = window * INTER_WINDOW_DELAY
    else:
        raise NotImplementedError(
            f"Unsuppoerted `{within_or_outside}` events. Must be `within` or `outside`"
        )

    yield 0
    if num == 1:
        return

    for _ in range(num - 1):
        sleep(delay)
        yield delay


class AppUnderTest(Standalone):
    def __init__(
        self,
        pipeline,
        mem,
        on_first_frame_out=None,
        **recorder_kw,
    ):
        super().__init__(pipeline, mem)

        self.recorder = VideoRecorder(self.pipeline, **recorder_kw)

        self.on_first_frame_out = on_first_frame_out
        self._offo_called = False

    def __call__(self, *a, **kw):
        self.inject_cb_on_first_frame_out()
        return super().__call__(*a, **kw)

    def inject_cb_on_first_frame_out(self):
        if not self.on_first_frame_out:
            return
        element_name, pad_name, callback = self.on_first_frame_out

        def call_and_drop_buffer_probe(*a, **kw):
            if self._offo_called:
                print(f"ASDF\n" * 10)
                raise ValueError(self._offo_called)
            self._offo_called = True
            callback(*a, **kw)
            return Gst.PadProbeReturn.REMOVE

        element = get_by_name(self.pipeline, element_name)
        get_static_pad(element, pad_name).add_probe(
            Gst.PadProbeType.BUFFER, call_and_drop_buffer_probe
        )


@fixture
def standalone_background(context, wait, control_logs):
    context.app_thread = context.app(
        control_logs=control_logs,
        background=True,
    )
    if wait:
        sleep(wait)
    yield context.app_thread
    t0 = datetime.now()
    while context.app.recorder.busy:
        if (
            datetime.now() - t0
        ).total_seconds() > 2.1 * context.app.recorder.ring_buffer.window_size_sec:
            warnings.warn("TIMEOUT REACHED AWAITNG RECORDER!")
            break
        sleep(0.01)

    context.app.stop()


@given("a recorder application running")
@given(
    "a recorder application running with {window:float} seconds of past video storage"
)
@given("a recorder application running for {wait:float} seconds")
@given(
    "a recorder application running for {wait:float} seconds, with {window:float} seconds of past video storage"
)
def run_bg(context, wait=1, window=0.5):
    context.tmpdir = TemporaryDirectory(prefix="pythiagstest-")
    context.wait = float(wait)
    context.window = float(window)

    def on_first_frame_out(pad, info):
        context.first_frame = {
            "now": datetime.now(),
            "pts": info.get_buffer().pts,
        }

    context.app = AppUnderTest(
        context.pipeline,
        None,
        src_tee_name="t1",
        filename_generator=lambda: f'{context.tmpdir.name}/{datetime.now().isoformat(timespec="milliseconds")}.webm',
        timeout_sec=1,
        on_first_frame_out=("videotestsrc", "src", on_first_frame_out),
        window_size_sec=float(window),
    )

    use_fixture(
        standalone_background,
        context,
        wait=wait,
        control_logs=False,
    )


@when("I send a record event")
@when("I send {num:int} record events {within_or_outside} the time window")
def rec_delayed(context, num=1, within_or_outside="within"):

    context.video_record_requests = defaultdict(list)
    for delay in wait_between_record_signals(
        num, within_or_outside, context.window
    ):
        pre = datetime.now()
        path = context.app.recorder.record()
        post = datetime.now()
        context.video_record_requests[path].append((pre, post, delay))


@when("the time window closes")
@when("the last time window closes")
def wait_time_window(context):
    sleep(2 * context.window)
    context.post_window = datetime.now()

    # delay = float(delay_str)
    # if delay:
    #     sleep(delay)

    # recs = getattr(
    #     context,
    #     "record_signals",
    #     {}
    # )

    # pre = datetime.now()
    # context.record_path = context.app.recorder.record()
    # post = datetime.now()

    # recs[delay] = pre, post, (post-pre).total_seconds()
    # context.record_signals = recs


@when("the application runs completely after {timeout} seconds")
@when("the application runs completely")
def bg_app_wait(context, timeout=10):
    context.app.loop.run()
    context.app_thread.join(timeout=float(timeout), raise_on_timeout=True)


@then("I see a video containing a time window around the event")
@then("I see a video containing a time window around the events")
@then(
    "I see {num_videos:int} videos containing a time window around each event"
)
def check_stats(
    context,
    num_videos=1,
):

    existing_videos = {
        str(path): path for path in Path(context.tmpdir.name).glob("**/*.webm")
    }
    requested_videos = {*context.video_record_requests.keys()}
    len_existing_videos = len(existing_videos)
    len_requested_videos = len(requested_videos)

    assert (
        len_existing_videos == num_videos
    ), f"Found {len_existing_videos}, but {num_videos} videos were required by the user"
    assert (
        len_existing_videos == len_requested_videos
    ), f"Found {len_existing_videos}, but {len_requested_videos} videos were requested by the API"

    previous_start = context.wait - context.window
    for path_str, timings in sorted(
        context.video_record_requests.items(), key=lambda tupl: tupl[0]
    ):
        videopath = existing_videos[path_str]
        timings = context.video_record_requests[str(videopath)]
        time_before_first_record_signal = timings[0][0]
        time_before_last_record_signal = timings[-1][0]

        assert videopath.stat().st_size != 0, f"{videopath} is empty"

        stats = video_stats(videopath)
        if "duration" not in stats:
            for _ in range(20):
                sleep(0.1)
                stats = video_stats(videopath)
                if "duration" in stats:
                    break
            else:
                raise KeyError("duration")

        start_time = float(stats["start_time"])

        start_should_be = previous_start + sum(
            timing[2] for timing in timings if timing[2] > 2 * context.window
        )  # TODO: avoid repeating logic with wait_between_record_signals
        previous_start = start_should_be
        start_error = abs(start_time - float(start_should_be))
        assert (
            start_error < START_ALLOWED_ERROR_SEC
        ), f"Video starting time ({start_time} [s]) is too different from required ({start_should_be} [s]): Difference={start_error:.02f} [s]. Max allowed={START_ALLOWED_ERROR_SEC} [s])"

        duration = float(stats["duration"])

        first_buffer_should_be = time_before_first_record_signal - timedelta(
            seconds=context.window
        )
        last_buffer_should_be = time_before_last_record_signal + timedelta(
            seconds=context.window
        )
        duration_should_be = last_buffer_should_be - first_buffer_should_be
        duration_error = abs(
            duration - float(duration_should_be.total_seconds())
        )
        # duration_should_be = (
        #     time_before_last_record_signal - time_before_first_record_signal
        # ) + 2 * timedelta(seconds=context.window)
        # duration_error = abs(
        #     duration - float(duration_should_be.total_seconds())
        # )
        assert (
            duration_error < DURATION_ALLOWED_ERROR_SEC
        ), f"Video duration ({duration} [s]) is too different from required ({duration_should_be} [s]): Difference={duration_error:.02f} [s]. Max allowed={DURATION_ALLOWED_ERROR_SEC} [s])"
