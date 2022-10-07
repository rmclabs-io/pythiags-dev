"""Annotation applications."""
from __future__ import annotations

import abc
import json
import logging
import sys
from functools import partial
from pathlib import Path
from typing import Any
from typing import Callable
from typing import List
from typing import Literal
from typing import Optional
from typing import Union

import pyds

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore[assignment]
import numpy as np

from pythia.applications.base import Application
from pythia.applications.base import BoundSupportedCb
from pythia.iterators import analytics_per_obj
from pythia.iterators import objects_per_batch
from pythia.models.base import Analytics
from pythia.models.base import InferenceEngine
from pythia.models.base import Tracker
from pythia.pipelines.base import Pipeline
from pythia.types import SourceUri
from pythia.types import SupportedCb
from pythia.utils.gst import Gst
from pythia.utils.gst import gst_init
from pythia.utils.gst import gst_iter
from pythia.utils.maskrcnn import extract_maskrcnn_mask
from pythia.utils.message_handlers import on_message_error


class _DumpLogger(logging.Logger):  # noqa: C0115
    def json(self, msg, *args, **kwargs):  # noqa: C0116
        logging.Logger._log(  # noqa: W0212
            self, logging.INFO, json.dumps(msg), args, **kwargs
        )


def _make_handler(
    dst: Path | Literal["stdout", "stderr"]
) -> logging.StreamHandler:
    if not isinstance(dst, Path):
        return logging.StreamHandler(getattr(sys, dst))
    if dst.is_dir():
        logfile = dst / "detections.jsonl"
        logfile.unlink(missing_ok=True)
    else:
        logfile = dst
    return logging.FileHandler(str(logfile))


def _make_logger(
    name: str, dst: Path | Literal["stdout", "stderr"]
) -> _DumpLogger:
    logging.setLoggerClass(_DumpLogger)
    try:
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        handler = _make_handler(dst)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    finally:
        logging.setLoggerClass(logging.Logger)
    return logger  # type: ignore[return-value]


class AnnotateFramesBase(Application, abc.ABC):
    """Base class for creating dataset / annotations."""

    nvds_frame_meta_parser: Optional[Callable[[pyds.NvDsFrameMeta], Any]]

    on_message_error = on_message_error

    @abc.abstractmethod
    def annotator_probe(
        self,
        pad: Gst.Pad,
        info: Gst.PadProbeInfo,
        batch_meta: pyds.NvDsBatchMeta,
    ) -> Gst.PadProbeReturn:
        """Implement this to process incoming batch metadata.

        Args:
            pad: gstreamer pad where the probe was attached.
            info: gstreamer pad probe info.
            batch_meta: deepstream metadata (batched!).

        """

    def __init__(self, pipeline, dst_folder: Path, *args, **kwargs) -> None:
        """Construct a Frame annotator.

        Args:
            pipeline: forwarded to pythia application constructor.
            dst_folder: location for the annotations.
            args: forwarded to pythia application constructor.
            kwargs: forwarded to pythia application constructor.

        """
        super().__init__(pipeline, *args, **kwargs)
        self._dst_folder = dst_folder
        self.logger = _make_logger(type(self).__name__, dst_folder)

    @staticmethod
    def _extract_common(
        pad, frame, detection, *, extract_analytics: bool = False
    ):
        frame_num = frame.frame_num
        box = detection.rect_params
        base = {
            "frame_num": frame_num,
            "id": detection.object_id,
            "engine_id": detection.unique_component_id,
            "engine": pad.parent.name,
            "pad_index": frame.pad_index,
            "label": detection.obj_label,
            "left": box.left,
            "top": box.top,
            "width": box.width,
            "height": box.height,
            "confidence": detection.confidence,
        }
        if not extract_analytics:
            return base
        try:
            analytics = next(iter(analytics_per_obj(detection)))
        except StopIteration:
            return base
        base["analytics"] = {
            attr: getattr(analytics, attr)
            for attr in (
                "dirStatus",
                "lcStatus",
                "ocStatus",
                "roiStatus",
                "unique_id",
            )
        }
        return base

    @classmethod
    def run(  # noqa: R0913
        cls,
        src: SourceUri,
        model: Union[str, Path, InferenceEngine],
        dst_folder: str | Path,
        *args,
        suffix: str = ".jpg",
        analytics: Union[Path, Analytics] | None = None,
        tracker: Union[Path, Tracker] | None = None,
        **kwargs,
    ) -> None:
        """Run an annotation application.

        Args:
            src: Source uri used for frames/video input.
            model: Deepstream inference model.
            dst_folder: Path to store annotations and frames.
            args: Forwarded to class constructor.
            suffix: output frames suffix.
            analytics: optional analytics for the pipline.
            tracker: optional tracker for the pipline.
            kwargs: Forwarded to class constructor.

        Raises:
            FileExistsError: Non-empty dst_folder

        """
        gst_init()
        dst_folder = Path(dst_folder)
        if not dst_folder.exists():
            dst_folder.mkdir(parents=True, exist_ok=False)
        frames = dst_folder / f"frames/%012d{suffix}"
        frames_folder = frames.parent

        frames_folder.mkdir(parents=True, exist_ok=True)
        try:
            next(iter(frames_folder.glob("**/*")))
        except StopIteration:
            pass
        else:
            raise FileExistsError(frames_folder)

        if isinstance(model, str):
            model = Path(model)
        pipeline = Pipeline(
            sources=[src],
            models=[model],
            sink=str(frames),
            analytics=analytics,
            tracker=tracker,
        )
        app = cls(pipeline, dst_folder, *args, **kwargs)

        target = cls.default_probe_target(pipeline)
        app.probe(target, "src")(app.annotator_probe)

        app()

    @staticmethod
    def default_probe_target(pipeline: Pipeline) -> str:
        """Retreive an element name to attach the probe to.

        Args:
            pipeline: Pythia Pipeline containing the elements.

        Returns:
            The name of the most downstream element contained in the
                pipeline. The precedence order is: analytics, tracker,
                nvinfer.

        Raises:
            LookupError: none of the required deepstream elements was
                found.

        """
        for element in gst_iter(pipeline.pipeline.iterate_sorted()):
            factory_name = element.get_factory().name
            if factory_name == "nvdsanalytics":
                return element.name
            if factory_name == "nvtracker":
                return element.name
            if factory_name == "nvinfer":
                return element.name
        raise LookupError("Unable to find analyrtics, tracker, nvinfer")

    @classmethod
    def run_with_probe(
        cls,
        *args,
        probe: SupportedCb | BoundSupportedCb | None = None,
        **kwargs,
    ) -> None:
        """Run an annotator with a custom probe.

        Args:
            args: forwarded to :meth:`run`.
            probe: annotator_probe to use.
            kwargs: forwarded to :meth:`run`.

        """
        import inspect

        signature = inspect.getfullargspec(probe)
        if signature.args[0] != "self":
            probe = staticmethod(probe)  # type: ignore[arg-type, assignment]
        klass = type("Annotator", (cls,), {"annotator_probe": probe})
        klass.run(*args, **kwargs)  # type: ignore[attr-defined]


class AnnotateFramesBbox(AnnotateFramesBase):
    """Annotate frames with boundingboxes."""

    def annotator_probe(
        self,
        pad: Gst.Pad,
        info: Gst.PadProbeInfo,
        batch_meta: pyds.NvDsBatchMeta,
    ) -> Gst.PadProbeReturn:
        for frame, detection in objects_per_batch(batch_meta):
            data = self._extract_common(pad, frame, detection)
            self.logger.json(data)
        return Gst.PadProbeReturn.OK


class AnnotateFramesMaskRcnn(AnnotateFramesBase):
    """Annotate frames with maskrcnn."""

    def __init__(
        self,
        pipeline,
        dst_folder: Path,
        *args,
        contour_kw: Optional[dict] = None,
        **kwargs,
    ) -> None:
        """Run an maskrcnn annotation application.

        Args:
            pipeline: forwarded to the annotator constructor.
            dst_folder: forwarded to the annotator constructor.
            args: forwarded to the annotator constructor.
            contour_kw: arbitrary dict containing kwargs for 'cv2.findContours'
            kwargs: forwarded to the annotator constructor.

        Raises:
            ImportError: opencv missing

        See Also:
            https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html#gadf1ad6a0b82947fa1fe3c3d497f260e0

        """
        if cv2 is None:
            raise ImportError(
                "Unable to initialize MaskRcnn annotator."
                " Reason: opencv-python not installed."
                " Reinstall with 'opencv' extra,"
                " eg 'pip install pythia[opencv]'."
            )
        self._countour_kw = contour_kw or {}
        self._countour_kw.setdefault("mode", cv2.RETR_TREE)  # noqa: E1101
        self._countour_kw.setdefault(
            "method", cv2.CHAIN_APPROX_SIMPLE  # noqa: E1101
        )  # noqa: E1101
        self.find_contours = partial(
            cv2.findContours,  # noqa: E1101
            **self._countour_kw,
        )
        super().__init__(pipeline, dst_folder, *args, **kwargs)

    def generate_mask_polygon(self, mask: np.ndarray) -> List[List[int]]:
        """Convert 2d numpy array mask into coco-"segmentation".

        Args:
            mask: used to convert to polygon as a matrix.

        Returns:
            mask in polygon form.

        See Also:
            https://learnopencv.com/deep-learning-based-object-detection-and-instance-segmentation-using-mask-rcnn-in-opencv-python-c/

        """

        contours, _ = self.find_contours(mask)
        return [[int(i) for i in c.flatten()] for c in contours]

    def annotator_probe(
        self,
        pad: Gst.Pad,
        info: Gst.PadProbeInfo,
        batch_meta: pyds.NvDsBatchMeta,
    ) -> Gst.PadProbeReturn:
        for frame, detection in objects_per_batch(batch_meta):
            bbox_data = self._extract_common(
                pad,
                frame,
                detection,
                extract_analytics=self.pipeline.analytics is not None,
            )
            mask_mtx = extract_maskrcnn_mask(detection)
            mask_poly = self.generate_mask_polygon(mask_mtx)
            self.logger.json(
                {
                    "mask": mask_poly,
                    **bbox_data,
                }
            )
        return Gst.PadProbeReturn.OK
