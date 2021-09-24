import atexit
import shutil
import sys
import tempfile
from pathlib import Path

from behave import given
from behave import then
from behave import when
from tests import run_read_console
from tests.paths import FIXTURES

NUM_FRAMES = 10


def create_images_path():
    temp = Path(
        str(
            tempfile.TemporaryDirectory(
                suffix=None, prefix="pythia.", dir=None
            ).name
        )
    )
    temp.mkdir(exist_ok=True, parents=True)
    atexit.register(lambda: shutil.rmtree(str(temp)))

    src = "/opt/nvidia/deepstream/deepstream/samples/streams/sample_720p.jpg"

    for index in range(NUM_FRAMES):
        dst = temp / f"{index}.jpg"
        shutil.copyfile(src, str(dst))
    return temp


@given("a bunch of images with people and cars")
def create_tmp_copy(context):
    context.images_path = create_images_path()


@given("a parsing module which logs detections to console")
def create_printer_module(context):
    context.module = str(FIXTURES / "sample_parser.py") + ":Process"


@when("I run a pipeline with pygst-launch")
def run_pipeline(context):
    pipeline = f"""
        multifilesrc location={context.images_path}/%d.jpg
        ! nvjpegdec
        ! nvvideoconvert
        ! queue
        ! muxer.sink_0 nvstreammux
            width=1280
           height=720
           batch-size=1
           name=muxer
       ! nvinfer
            config-file-path=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_infer_primary.txt
            batch-size=1
            name=nvinfer_observer
        ! queue
        ! nvvideoconvert
        ! nvdsosd
        ! nvvideoconvert
        ! videoconvert
        ! appsink
          name=pythiags
          emit-signals=true
          caps=video/x-raw,format=RGB"""

    cmd = f"""pygst-launch {pipeline}
        --obs=nvinfer_observer
        --proc={context.module}
        --ext=pythiags:DetectorMetadataExtractor
    """
    context.exit_code, context.stdout, context.stderr = run_read_console(
        cmd, timeout=30
    )


@then("I see the detections in the console")
def read_detections_from_console(context):
    text = (context.stdout + context.stderr).lower()
    if context.exit_code != 0:
        print(context.stdout)
        print(context.stderr, file=sys.stderr)
        raise RuntimeError
    for index in range(NUM_FRAMES):
        for klass in ("car", "person"):
            assert (
                f"found {klass} in frame {index}" in text
            ), f"{klass}-frame {index} not found in {text}"
