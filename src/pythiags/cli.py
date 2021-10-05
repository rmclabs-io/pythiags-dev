# -*- coding: utf-8 -*-
"""Command line interface for pythiags."""

import time
from functools import partial
from pathlib import Path
from threading import Thread
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional
from typing import Tuple
from typing import Union

import fire

import pythiags
from pythiags import PYTHIAGS_APPSINK_NAME
from pythiags import Gst
from pythiags import logger
from pythiags.consumer import Consumer
from pythiags.headless import Standalone
from pythiags.producer import Producer
from pythiags.types import MetadataExtractionMap
from pythiags.utils import clean_pipeline
from pythiags.utils import instantiated_object_from_importstring
from pythiags.utils import validate_processor


def info(txt):
    logger.info(f"PyGstLaunch: {txt}")


def pipe_from_file(path: Union[str, Path], **pipeline_kwargs) -> str:
    info(f"Loading pipeline from {path}")

    real = Path(path).resolve()
    with open(real) as fp:
        pipeline_string = fp.read()
    try:
        formatted_pipeline = pipeline_string.format_map(pipeline_kwargs)
    except KeyError as exc:
        logger.error(f"Cannot run {real}. Reason: {repr(exc)}")
        raise

    return clean_pipeline(formatted_pipeline)


def _define_pipeline(
    file: Optional[Union[str, Path]],
    *pipeline_parts: str,
    **pipeline_kwargs: str,
):

    if (file or pipeline_kwargs) and pipeline_parts:
        raise ValueError(
            "Either supply a pipeline like gst-launch, or use the --file flag, not both"
        )

    if pipeline_kwargs.pop("help", False):
        import subprocess as sp
        import sys
        from shlex import split

        sys.exit(sp.call(split(f"pygst-launch -- --help")))

    if not any((file, pipeline_parts)):
        msg = "Must suply either a pipeline like gst-launch, or use the --file flag."
        logger.error(msg)
        raise ValueError(msg)

    if file:
        return pipe_from_file(file, **pipeline_kwargs)

    stdin = " ".join(pipeline_parts)
    info(f"Loading pipeline from stdin: ({stdin})")
    return clean_pipeline(stdin)


def _define_runtime_from_pipeline_string(
    pipeline_string,
) -> Callable[[str, MetadataExtractionMap], Any]:
    if PYTHIAGS_APPSINK_NAME in pipeline_string:
        if pythiags.KIVY_INSTALLED:
            from pythiags.kivy_app import PythiaGsCli

            return PythiaGsCli.cli_run
        raise ValueError(
            "Unable to use PythiaGsCli because kivy is not installed."
            " You should install pythiags with the kivy extra."
        )
    return partial(Standalone.cli_run, background=False)


def _build_meta_map(obs, extractor, consumer) -> MetadataExtractionMap:
    return {
        obs: (
            extractor
            and validate_processor(
                instantiated_object_from_importstring(extractor), Producer
            ),
            consumer
            and validate_processor(
                instantiated_object_from_importstring(consumer), Consumer
            ),
        )
    }


def pygst_launch(
    *pipeline_parts,
    file=None,
    obs: Optional[str] = None,
    ext: Optional[Producer] = None,
    proc: Optional[Consumer] = None,
    **pipeline_kwargs,
):

    pipeline = _define_pipeline(file, *pipeline_parts, **pipeline_kwargs)
    runtime = _define_runtime_from_pipeline_string(pipeline)
    mem = _build_meta_map(obs, ext, proc)

    return runtime(pipeline=pipeline, metadata_extraction_map=mem)


# def kivy_mwe():
#     """Sample Kivy app with minimal gstreamer pipeline."""

#     demo_pipeline = """\
#         videotestsrc
#           num_buffers=100
#         ! decodebin
#         ! videoconvert
#         ! appsink
#           name=pythiags
#           emit-signals=True
#           caps=video/x-raw,format=RGB
#     """

#     PythiaGsCli.cli_run(demo_pipeline)


# def launch(
#     *pipeline_parts,
#     observer: Optional[str] = None,
#     extractor: Optional[Producer] = None,
#     processor: Optional[Consumer] = None,
# ):
#     """Build and run a gst pipeline with gst-like syntax."""
#     PythiaGsCli.cli_run(
#         " ".join(pipeline_parts),
#         metadata_extraction_map=_build_meta_map(
#             observer,
#             extractor,
#             processor,
#         ),
#     )


# def pipeline_file(
#     path: Union[str, Path],
#     obs: Optional[str] = None,
#     ext: Optional[Producer] = None,
#     proc: Optional[Consumer] = None,
#     **pipeline_kwargs,
# ):
#     real = Path(path).resolve()
#     with open(real) as fp:
#         pipeline_string = fp.read()
#     try:
#         formatted_pipeline = pipeline_string.format_map(pipeline_kwargs)
#     except KeyError as exc:
#         logger.error(f"PythiaGsApp: Cannot run {real}. Reason: {repr(exc)}")
#         raise

#     final_pipeline = clean_pipeline(formatted_pipeline)

#     PythiaGsCli.cli_run(
#         final_pipeline,
#         metadata_extraction_map=_build_meta_map(
#             obs,
#             ext,
#             proc,
#         ),
#     )


# def pythiags_launch():
#     """Build and run a gst pipeline with gst-like syntax."""

#     def cb(
#         *pipeline_parts,
#         observer: Optional[str] = None,
#         extractor: Optional[Producer] = None,
#         processor: Optional[Consumer] = None,
#     ):
#         Standalone(
#             " ".join(pipeline_parts),
#             metadata_extraction_map=_build_meta_map(
#                 observer,
#                 extractor,
#                 processor,
#             ),
#         )()

#     fire.Fire(cb)


def get_version(name="pythiags"):
    try:
        import importlib.metadata as importlib_metadata
    except ModuleNotFoundError:
        import importlib_metadata

    version = importlib_metadata.version(name)
    logger.info(f"PythiaGs: version {version}")
    logger.info(f"PythiaGs: Installed at '{Path(pythiags.__file__).parent}'")
    return version


# ALL_CMDS = {
#     "--version": get_version,
#     "videotestsrc": kivy_mwe,
#     "launch": launch,
#     "file": pipeline_file,
# }


def main():
    # get_version()
    fire.Fire(pygst_launch)


if __name__ == "__main__":
    main()
