# -*- coding: utf-8 -*-
"""Command line interface for pythiags."""

from pathlib import Path
from typing import Dict
from typing import Optional
from typing import Tuple
from typing import Union

import fire

import pythiags
from pythiags import Gst
from pythiags import logger
from pythiags.app import PythiaGsApp
from pythiags.consumer import Consumer
from pythiags.headless import Standalone
from pythiags.producer import Producer
from pythiags.utils import clean_pipeline
from pythiags.utils import instantiated_object_from_importstring
from pythiags.video import GSCameraWidget


def _build_meta_map(
    obs, extractor, consumer
) -> Optional[Dict[str, Tuple[Producer, Consumer]]]:
    return {
        obs: (
            extractor and instantiated_object_from_importstring(extractor),
            consumer and instantiated_object_from_importstring(consumer),
        )
    }


class PythiaGsCli(PythiaGsApp):
    root: GSCameraWidget

    @property
    def pipeline(self) -> Gst.Pipeline:
        return self.root._camera._pipeline

    def build(self) -> GSCameraWidget:
        try:
            camera = GSCameraWidget(pipeline_string=self.pipeline_string)
        except ValueError as err:
            msg = (
                f"PythiaGsApp: Unable to intialize pipeline. Reason: {repr(err)}"
                ". Make sure the last element contains this: `appsink name=pythiags emit-signals=true caps=video/x-raw,format=RGB`"
            )
            logger.error(msg)
            raise
        return camera

    @classmethod
    def cli_run(cls, pipeline, metadata_extraction_map=None):
        self = cls(pipeline, metadata_extraction_map)
        self.__call__()


def video_test_src():
    """Sample Kivy app with minimal gstreamer pipeline."""

    demo_pipeline = """\
        videotestsrc
          num_buffers=100
        ! decodebin name=decoder
        ! videoconvert
        ! appsink
          name=pythiags
          emit-signals=True
          caps=video/x-raw,format=RGB
    """

    PythiaGsCli.cli_run(demo_pipeline)


def launch(
    *pipeline_parts,
    observer: Optional[str] = None,
    extractor: Optional[Producer] = None,
    processor: Optional[Consumer] = None,
):
    """Build and run a gst pipeline with gst-like syntax."""
    PythiaGsCli.cli_run(
        " ".join(pipeline_parts),
        metadata_extraction_map=_build_meta_map(
            observer,
            extractor,
            processor,
        ),
    )


def pipeline_file(
    path: Union[str, Path],
    obs: Optional[str] = None,
    ext: Optional[Producer] = None,
    proc: Optional[Consumer] = None,
    **pipeline_kwargs,
):
    real = Path(path).resolve()
    with open(real) as fp:
        pipeline_string = fp.read()
    try:
        formatted_pipeline = pipeline_string.format_map(pipeline_kwargs)
    except KeyError as exc:
        logger.error(f"PythiaGsApp: Cannot run {real}. Reason: {repr(exc)}")
        raise

    final_pipeline = clean_pipeline(formatted_pipeline)

    PythiaGsCli.cli_run(
        final_pipeline,
        metadata_extraction_map=_build_meta_map(
            obs,
            ext,
            proc,
        ),
    )


def pythiags_launch():
    """Build and run a gst pipeline with gst-like syntax."""

    def cb(
        *pipeline_parts,
        observer: Optional[str] = None,
        extractor: Optional[Producer] = None,
        processor: Optional[Consumer] = None,
    ):
        Standalone(
            " ".join(pipeline_parts),
            metadata_extraction_map=_build_meta_map(
                observer,
                extractor,
                processor,
            ),
        )()

    fire.Fire(cb)


def get_version(name="pythiags"):
    try:
        import importlib.metadata as importlib_metadata
    except ModuleNotFoundError:
        import importlib_metadata

    version = importlib_metadata.version(name)
    logger.info(f"pythiags: version {version}")
    logger.info(f"pythiags: Installed at '{pythiags.__file__}'")
    return version


ALL_CMDS = {
    "videotestsrc": video_test_src,
    "launch": launch,
    "file": pipeline_file,
    "--version": get_version(),
}


def main():
    fire.Fire(ALL_CMDS)
