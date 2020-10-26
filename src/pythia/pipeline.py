#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""

TODO: sync GSCameraWidget resolution with pipeline output to avoid yet
another rescaling...
"""

from pathlib import Path
from textwrap import dedent as _
from typing import List
from typing import Optional
from typing import Union

Pathlike = Union[str, Path]

Str = Union[str, int]


def build_camera(
    idx: Str, video_id: Str, input_width: Str, input_height: Str, framerate: str
) -> str:
    """Build a single camera source to connect with the muxer.

    The muxer is not included.

    Args:
    idx: Camera index. Used in muxer pad index and to name the tee.
    video_id: Camera resource location, as appears in `/dev/videoX`.
    input_width: Camera output width (must be supported by the camera).
    input_height: Camera output height (must be supported by the
      camera).
    framerate: Capsfilter-format framerate. For example, "30/1"

    Returns:
    A formatted portion of a pipeline connecting camera to muxer.

    .. example::

       >>> print(build_camera(0, 2, 640, 480, "30/1"))
       v4l2src device=/dev/video2
         ! video/x-raw, width=640, height=480, framerate=30/1, format=YUY2
         ! tee
             name=tee_0
         ! nvvideoconvert
         ! video/x-raw(memory:NVMM),format=NV12
         ! muxer.sink_0

    .. seealso:: `build_cameras`
    """

    # fmt: off
    return _(f"""
        v4l2src device=/dev/video{video_id}
          ! video/x-raw, width={input_width}, height={input_height}, framerate={framerate}, format=YUY2
          ! tee
              name=tee_{idx}
          ! nvvideoconvert
          ! video/x-raw(memory:NVMM),format=NV12
          ! muxer.sink_{idx}
    """).strip()
    # fmt: on


def build_cameras(
    input_width: Str,
    input_height: Str,
    fps: Str,
    dev_video_ids: List[Str],
    joiner: str = "\n",
) -> str:
    """Build several cameras to connect with the muxer.

    The muxer is not included. Camera resolution is the same for all.

    Args:
    input_width: Camera output width (must be supported by the camera).
    input_height: Camera output height (must be supported by the
      camera).
    fps: Required number of frames per second per camera.
    dev_video_ids: Array Camera resource locations, as appearing in
      `/dev/videoX`.
    joiner: which character to use when joniing the cameras.

    Returns:
    A formatted portion of a pipeline connecting cameras to muxer.

    .. example::

       >>> print(build_cameras(640, 480, "30/1", [2, 5, 8]))
       v4l2src device=/dev/video2
         ! video/x-raw, width=640, height=480, framerate=30/1/1, format=YUY2
         ! tee
             name=tee_0
         ! nvvideoconvert
         ! video/x-raw(memory:NVMM),format=NV12
         ! muxer.sink_0
       v4l2src device=/dev/video5
         ! video/x-raw, width=640, height=480, framerate=30/1/1, format=YUY2
         ! tee
             name=tee_1
         ! nvvideoconvert
         ! video/x-raw(memory:NVMM),format=NV12
         ! muxer.sink_1
       v4l2src device=/dev/video8
         ! video/x-raw, width=640, height=480, framerate=30/1/1, format=YUY2
         ! tee
             name=tee_2
         ! nvvideoconvert
         ! video/x-raw(memory:NVMM),format=NV12
         ! muxer.sink_2

    .. seealso:: `build_camera`
    """
    framerate = f"{fps}/1"
    return joiner.join(
        build_camera(idx, video_id, input_width, input_height, framerate)
        for idx, video_id in enumerate(dev_video_ids)
    )


def build_pipeline(
    input_width: Str,
    input_height: Str,
    muxer_width: Str,
    muxer_height: Str,
    output_width: Str,
    output_height: Str,
    fps: Str,
    nvinfer_config_file: Pathlike,
    dev_video_ids: List[Str],
    batched_push_timeout: Optional[int] = None,
):
    """Build Gstreamer pipeline string, to use with `Gst.parse_launch`.

    Args:
    input_width: Camera output width (must be supported by the camera).
    input_height: Camera output height (must be supported by the
      camera).
    muxer_width: Gst element `nvstreammux` property: output width. This
      is the width which will enter the ``nvinfer`` element.
    muxer_height: Gst element `nvstreammux` property: output height.
      This is the height which will enter the ``nvinfer`` element.
    output_width: Gst element `nvmultistreamtiler` property: output
      width. This is the width which will enter kivy.
    output_height: Gst element `nvmultistreamtiler` property: output
      height. This is the height which will enter kivy.
    fps: Required number of frames per second per camera.
    nvinfer_config_file: Gst element `nvinfer` property: configuration
      file.
    dev_video_ids: Camera resource locations, as appearing in
      `/dev/videoX`.
    batched_push_timeout: Gst element `nvstreammux` property: how long
      to wait for a batch to be full before pushingit anyway.

    Returns:
    A formatted pipeline using nvinfer and N cameras, to be used with
      `Gst.parse_launch`

    .. example::

       >>> print(build_pipeline(640,480, 960,544, 1280,720, 30, "/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_infer_primary.txt", [2,5,8]))
       nvstreammux
           name=muxer
           batch-size=3
           width=960
           height=544
           live-source=1
           batched-push-timeout=16666
           enable-padding=1
       ! nvinfer
           config-file-path=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_infer_primary.txt
       ! queue
       ! nvmultistreamtiler
           width=1280
           height=720
           rows=2
           columns=2
           name=tiler
       ! nvvideoconvert
       ! nvdsosd display-text=false
       ! nvvideoconvert name=decoder
       ! videoconvert
       ! appsink
           name=appsink
           emit-signals=True
           caps=video/x-raw,format=RGB        v4l2src device=/dev/video2
         ! video/x-raw, width=640, height=480, framerate=30/1, format=YUY2
         ! tee
             name=tee_0
         ! nvvideoconvert
         ! video/x-raw(memory:NVMM),format=NV12
         ! muxer.sink_0
       v4l2src device=/dev/video5
         ! video/x-raw, width=640, height=480, framerate=30/1, format=YUY2
         ! tee
             name=tee_1
         ! nvvideoconvert
         ! video/x-raw(memory:NVMM),format=NV12
         ! muxer.sink_1
       v4l2src device=/dev/video8
         ! video/x-raw, width=640, height=480, framerate=30/1, format=YUY2
         ! tee
             name=tee_2
         ! nvvideoconvert
         ! video/x-raw(memory:NVMM),format=NV12
         ! muxer.sink_2

    .. seealso:: `build_cameras`
    """

    batched_push_timeout = int(
        batched_push_timeout or 0.5e6 / fps
    )  # wait half a frame or push

    cameras = build_cameras(input_width, input_height, fps, dev_video_ids)

    # fmt: off
    base = _("""\
        nvstreammux
            name=muxer
            batch-size={batch_size}
            width={muxer_width}
            height={muxer_height}
            live-source=1
            batched-push-timeout={batched_push_timeout}
            enable-padding=1
        ! nvinfer
            config-file-path={nvinfer_file} 
        ! queue
        ! nvmultistreamtiler
            width={output_width}
            height={output_height}
            rows=2
            columns=2
            name=tiler
        ! nvvideoconvert
        ! nvdsosd display-text=false
        ! nvvideoconvert name=decoder
        ! videoconvert
        ! appsink
            name=camerasink
            emit-signals=True
            caps=video/x-raw,format=RGB\
        {cameras}\
    """).strip()
    # fmt: on

    pipeline_string = base.format(
        input_width=input_width,
        input_height=input_height,
        muxer_width=muxer_width,
        muxer_height=muxer_height,
        batch_size=len(dev_video_ids),
        output_width=output_width,
        output_height=output_height,
        batched_push_timeout=batched_push_timeout,
        nvinfer_file=nvinfer_config_file,
        cameras=cameras,
    )
    return pipeline_string
