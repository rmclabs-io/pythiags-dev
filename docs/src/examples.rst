Using pythiags
============


Simple video pipeline
------------------


Using video recorder
--------------------

Here's a sample on how to set a simple video recorder using pythia::

    import shutil
    from datetime import datetime
    from pathlib import Path

    from pythiags.headless import Standalone
    from pythiags.recorder import VideoRecorder

    SAMPLE_PIPELINE = """
        videotestsrc
        num-buffers=30000
        name=videotestsrc
        ! video/x-raw,width=320,height=240
        ! timeoverlay
        halignment=right
        valignment=bottom
        text="Stream time:"
        shaded-background=true
        font-desc="Sans, 24"
        ! tee
        name=t1

        t1.
        ! queue
        ! xvimagesink
        """

    class FunctionalApp(Standalone):
        def __init__(
            self,
            pipeline,
            mem,
            on_first_frame_out = None,
            **recorder_kw,
        ):
            super().__init__(pipeline, mem)

            self.recorder = VideoRecorder(self.pipeline, **recorder_kw)

        def __call__(self, *a, **kw):
            return super().__call__(*a, **kw)


    def set_experiment_path():
        """Build the video destination path. All present files in this folder will be erased."""
        experiment_path = Path("/mnt/nvme/functional_tests/").resolve()
        shutil.rmtree(str(experiment_path))
        if experiment_path.exists():
            experiment_path.rmdir()
        experiment_path.mkdir()
        return experiment_path


    def get_key():
        """Receive available keys from keyboard."""
        inp = print("Press r to send a record signal, or q to quit: ",)
        if inp not in ("q", "r"):
            print(f"Unhandled key. Press r to record or q")
        return inp

    def main(
        window=1
    ):
        experiment_path = set_experiment_path()

        app = FunctionalApp(
            CAMERA_TEST_PIPELINE,
            None,
            src_tee_name="t1",
            filename_generator=lambda: f'{experiment_path}/{datetime.now().isoformat(timespec="milliseconds")}.webm',
            timeout_sec=1,
            window_size_sec=float(window)
        )

        app(background=True)

        stopped = False
        while not stopped:
            

    if __name__=="__main__":
        main()

.. code-block:: rst

   A bit of **rst** which should be *highlighted* properly.