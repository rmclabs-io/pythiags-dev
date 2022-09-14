"""Pipeline.

A Gstreamer pipeline, used to process video/image input.
Contains:

    A source: video/image.
    A sink: display/file.
    At least one PythIA model.

"""

from __future__ import annotations

import abc
import re
from collections import defaultdict
from pathlib import Path
from textwrap import dedent as _
from typing import Collection
from typing import Dict
from typing import Iterator
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union
from urllib.parse import parse_qs
from urllib.parse import urlparse
from urllib.parse import urlunparse

from pythia.exceptions import IncompatiblePipelineError
from pythia.exceptions import InvalidPipelineError
from pythia.models.base import Analytics
from pythia.models.base import InferenceEngine
from pythia.models.base import Tracker
from pythia.types import Con
from pythia.types import HasConnections
from pythia.types import SinkUri
from pythia.types import SourceUri
from pythia.utils.ext import get_arch
from pythia.utils.gst import GLib
from pythia.utils.gst import Gst
from pythia.utils.gst import gst_init
from pythia.utils.str2pythia import find_analytics
from pythia.utils.str2pythia import find_models
from pythia.utils.str2pythia import find_tracker

PSB = Union["PythiaTestSource", "PythiaSource", "PythiaMultiSource"]
PS = Union[
    "PythiaFakesink", "PythiaFilesink", "PythiaMultifileSink", "PythiaLiveSink"
]

UNABLE_TO_PLAY_PIPELINE = "Unable to play the pipeline."


class PythiaSourceBase(abc.ABC, HasConnections):
    """Base class wrapper for Gstreamer sources.

    The main goal is to define a skeleton for quickly building sources,
    and subclasses must implement their rendering logic in the `gst`
    method.

    """

    CONNECTIONS: Con = {}

    def __init__(self, *uris: SourceUri) -> None:
        """Construct an instance from `SourceUri` s.

        Args:
            uris: Collection of `SourceUri` s.

        """
        self.pythia_params, self.uris = self.pop_pythia_args_from_uris(uris)

    def __iter__(self) -> Iterator[SourceUri]:
        """Iterate over the configured uris.

        Yields:
            Own `SourceUri`s.

        """
        yield from self.uris

    def __len__(self) -> int:
        """Get the number of sources.

        Returns:
            The number of configured uris.

        """

        return len(self.uris)

    @abc.abstractmethod
    def gst(self) -> str:
        """Render as string with `gst-launch`-like syntax."""

    @classmethod
    def from_uris(cls, *uris: SourceUri) -> PSB:
        """Factory to build a concrete source from a collection of uris.

        Depending on the received uris, instantiates a concrete
        :class:`PythiaSourceBase`.

        Args:
            uris: Collection of uris to build the source from.

        Returns:
            The instantiated source object.

        Raises:
            ValueError: No source uris received

        """
        num_uris = len(uris)
        if num_uris == 1:
            if uris[0].startswith("test"):
                return PythiaTestSource(*uris)
            return PythiaSource(*uris)
        if num_uris >= 1:
            return PythiaMultiSource(*uris)
        raise ValueError("No source uris")

    @staticmethod
    @abc.abstractmethod
    def pop_pythia_args_from_uris(
        uris: Tuple[SourceUri, ...],
    ) -> Tuple[dict, List[SourceUri]]:
        """Pop pythia-related query params from source uri.

        Args:
            uris: input uris to filter

        """


def clean_single_uri(uri: SourceUri) -> Tuple[dict, SourceUri]:
    """Extract muxer width and height.

    Args:
        uri: input uris to parse.

    Returns:
        extracted: dictionary containing popped params.
        list containing the single uri wihtout its pythia query params.

    Examples:
        >>> clean_single_uri("file://video.mp4?muxer_width=1280&muxer_height=720")
        ({'muxer_width': 1280, 'muxer_height': 720}, ['file://video.mp4'])

    """  # noqa: C0301
    parsed = urlparse(uri)
    data = parsed._asdict()
    query = parse_qs(data["query"], strict_parsing=False)
    extracted = {
        "muxer_width": int(query["muxer_width"][0]),
        "muxer_height": int(query["muxer_height"][0]),
        "num_buffers": int(query.get("num_buffers", ["-1"])[0]),
    }
    clean_query = parsed.query
    for name, value in extracted.items():
        clean_query = clean_query.replace(f"{name}={value}", "")
    clean_query = re.sub(r"\&+", "&", clean_query).strip("&").strip("?")
    parts = [*parsed[:4], clean_query, *parsed[5:]]
    clean_uri = urlunparse(parts)
    return extracted, clean_uri


class PythiaSource(PythiaSourceBase):
    """Uridecodebin wrapper building block for a single source."""

    @staticmethod
    def pop_pythia_args_from_uris(
        uris: Tuple[SourceUri, ...],
    ) -> Tuple[dict, List[SourceUri]]:
        """Extract muxer width and height.

        Args:
            uris: input uris to filter

        Returns:
            extracted: dictionary containing popped params.
            list containing the single uri wihtout its pythia query params.

        Examples:
            >>> uris = ["file://video.mp4?muxer_width=1280&muxer_height=720"]
            >>> PythiaSource.pop_pythia_args_from_uris(uris)
            ({'muxer_width': 1280, 'muxer_height': 720}, ['file://video.mp4'])

        """
        extracted, clean_uri = clean_single_uri(uris[0])
        return extracted, [clean_uri]

    CONNECTIONS: Con = {}

    def gst(self) -> str:
        """Render from single uridecodebin up to nvmuxer.

        Returns:
            Rendered string

        """

        return _(
            f"""\
        uridecodebin
          uri={self.uris[0]}
        ! queue
        ! nvvideoconvert
        ! video/x-raw(memory:NVMM)
        ! m.sink_0
        nvstreammux
          name=m
          batch-size={len(self)}
          width={self.pythia_params['muxer_width']}
          height={self.pythia_params['muxer_height']}
        """
        )


class PythiaMultiSource(PythiaSourceBase):
    """Uridecodebin wrapper building block for multiple sources."""

    @staticmethod
    def pop_pythia_args_from_uris(
        uris: Tuple[SourceUri, ...],
    ) -> Tuple[dict, List[SourceUri]]:
        """Extract muxer width and height.

        Args:
            uris: input uris to filter

        Returns:
            extracted: dictionary containing popped params.
            list containing the single uri wihtout its pythia query params.

        Examples:
            >>> uris = [
            ...     "./frames/%04d.jpg?muxer_width=320&muxer_height=240",
            ...     "./annotations/%04d.jpg?muxer_width=1280&muxer_height=100",
            ... ]
            >>> PythiaMultiSource.pop_pythia_args_from_uris(uris)
            ({'muxer_width': 1280, 'muxer_height': 240}, ['./frames/%04d.jpg', './annotations/%04d.jpg'])

        """  # noqa: C0301
        extrema = {
            "muxer_width": 0,
            "muxer_height": 0,
        }
        uris_out = []
        for uri in uris:
            extracted, clean_uri = clean_single_uri(uri)
            uris_out.append(clean_uri)
            for key in extrema:
                extrema[key] = max(extrema[key], extracted[key])
        return extrema, uris_out

    def gst(self) -> str:
        """Render from several uridecodebin up to nvmuxer.

        Returns:
            Rendered string

        """
        suffix = _(
            f"""\
            nvstreammux
              name=m
              batch-size={len(self.uris)}
        """
        )
        text = "\n".join(
            f"""\
            uridecodebin
              uri={self.uris[idx]}
            ! queue
            ! nvvideoconvert
            ! video/x-raw(memory:NVMM)
            ! m.sink_{idx}
            nvstreammux
              name=m
              batch-size=1
            """
            for idx in range(len(self.uris))
        )
        return f"{text}\n{suffix}"


class PythiaTestSource(PythiaSourceBase):
    """videotestsrc wrapper building block."""

    @staticmethod
    def pop_pythia_args_from_uris(
        uris: Tuple[SourceUri, ...],
    ) -> Tuple[dict, List[SourceUri]]:
        """Extract muxer width and height.

        Args:
            uris: input uris to filter

        Returns:
            extracted: dictionary containing popped params.
            list containing the single uri wihtout its pythia query params.

        Examples:
            >>> uris = ["test://?muxer_width=320&muxer_height=240"]
            >>> PythiaTestSource.pop_pythia_args_from_uris(uris)
            ({'muxer_width': 320, 'muxer_height': 240}, ['test:'])

        """
        extracted, clean_uri = clean_single_uri(uris[0])
        return extracted, [clean_uri]

    def gst(self) -> str:
        """Render from single videotestsrc up to nvmuxer.

        Returns:
            Rendered string.

        """
        return _(
            f"""
        videotestsrc
          num-buffers={self.pythia_params['num_buffers']}
        ! queue
        ! nvvideoconvert
        ! video/x-raw(memory:NVMM)
        ! m.sink_0
        nvstreammux
          name=m
          batch-size={len(self)}
          nvbuf-memory-type=0
          width={self.pythia_params['muxer_width']}
          height={self.pythia_params['muxer_height']}
        """
        )


class PythiaSink(abc.ABC, HasConnections):
    """Class used to construct sink from uris."""

    CONNECTIONS: Con = {}
    VIDEO_EXTENSIONS = [
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".webm",
        ".flv",
        ".wmv",
        ".mpg",
        ".mpeg",
        ".m4v",
    ]

    def __init__(self, uri: SinkUri) -> None:
        """Instantiate sink wrapper with one of the available uris.

        Args:
            uri: the uri to build a gst sink and finish the pipeline.

        """
        self.uri = uri

    @classmethod
    def from_uri(cls, uri: SinkUri) -> PS:
        """Factory constructor from `SinkUri` .

        Args:
            uri: the uri to use. Must fulfill one of the following
                conditions:

                * be one of ('live', 'fakesink'). If set to 'live', the
                  output will be the screen. If set to 'fakesink', use
                  the fakesing `Gst.Element` .
                * If a string containing a `%` , the underlying element
                  will be a `multifilesink` .
                * Otherwise, it mus be a string pointing to a path, and
                  have a valid and supported video extension.

        Returns:
            The instantiated `PythiaSink` , depending on its uri.

        Raises:
            ValueError: unsupported sink uri.

        """
        if uri == "live":
            return PythiaLiveSink(uri)

        if uri == "fakesink":
            return PythiaFakesink(uri)

        if "%" in Path(uri).stem:
            return PythiaMultifileSink(uri)

        if Path(uri).suffix in cls.VIDEO_EXTENSIONS:
            return PythiaFilesink(uri)

        raise ValueError(f"Unknown sink uri: {uri}")

    @abc.abstractmethod
    def gst(self) -> str:
        """Render as string with `gst-launch`-like syntax."""


class PythiaFakesink(PythiaSink):
    """fakesink wrapper building block for a single sink."""

    def gst(self) -> str:
        """Simple fakesink.

        Returns:
            Rendered string

        """
        return "fakesink"


class PythiaFilesink(PythiaSink):
    """filesink wrapper building block for a single sink.

    Uses `encodebin` to attempt to properly parse upstream buffers.

    """

    def gst(self) -> str:
        """Render from single encodebin up to filesink.

        Returns:
            Rendered string

        """

        return _(
            f"""\
            encodebin
            ! filesink
              location="{self.uri}"
            """
        )


class PythiaMultifileSink(PythiaSink):
    """multifilesink building block for a single multioutput sink.

    Uses `encodebin` to attempt to properly parse upstream buffers.

    """

    SUPPORTED_FORMATS = {
        ".jpg": """
            nvvideoconvert
            ! jpegenc
              quality=100
              idct-method=float
        """,
        ".png": """
            nvvideoconvert
            ! avenc_png
        """,
        ".webp": """
            nvvideoconvert
            ! webpenc
              lossless=true
              quality=100
              speed=6
        """,
    }

    def gst(self) -> str:
        """Render from single encodebin up to multifilesink.

        Returns:
            Rendered string

        """
        encode = self.SUPPORTED_FORMATS[Path(self.uri).suffix]
        return _(
            f"""\
            {encode}
            ! multifilesink
              location="{self.uri}"
            """
        )


class PythiaLiveSink(PythiaSink):
    """nveglglessink wrapper."""

    def __init__(self, uri: SinkUri, arch: str = "") -> None:
        """Construct nveglglessink wrapper.

        Args:
            uri: uri for `PythiaSink`'s constructor.
            arch: platform architecture, to differentiate GPU and
                jetson devices. If not set, automatically computed by
                :func:`get_arch`. In jetson devices, injects an
                additional `nvegltransform`.

        See Also:
            https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_FAQ.html#why-is-a-gst-nvegltransform-plugin-required-on-a-jetson-platform-upstream-from-gst-nveglglessink

        """
        super().__init__(uri)
        self.arch = arch or get_arch()
        self.transform = "! nvegltransform" if get_arch() == "aarch64" else ""

    def gst(self) -> str:
        """Render from nvvideoconvert to nveglglessink.

        Returns:
            Rendered string

        """
        return _(
            f"""\
            nvvideoconvert
            {self.transform}
            ! nveglglessink
            """
        )


class BasePipeline(HasConnections, abc.ABC):
    """Common abstraction wrapper for pythia pipelines."""

    _pipeline: Optional[Gst.Pipeline] = None
    models: Collection[InferenceEngine]
    analytics: Optional[Analytics]
    tracker: Optional[Tracker]

    @abc.abstractmethod
    def gst(self) -> str:
        """Render its string for to use in `gst-launch`-like syntax."""

    @property
    @abc.abstractmethod
    def CONNECTIONS(self) -> Con:  # type: ignore[override] # noqa: C0103,C0116
        ...

    def validate(
        self,
    ) -> None:
        """Checks for internal compliance of specified elements.

        > Tracker requires at least one InferenceEngine > Analytics
        requires at least one InferenceEngine, and Tracker if it has
        Direction Detection or Line Crossing. > SecondaryInference
        Engine requires at least a PrimaryInferenceEngine

        Raises:
            IncompatiblePipelineError: `Analytics` requires `Tracker`
                but none supplied.
            IncompatiblePipelineError: `Tracker` requires `Model` but
                none supplied.

        """
        if self.analytics:
            if len(self.models) < 1:
                raise IncompatiblePipelineError(
                    f"Analytics requires at least 1 InferenceEngine."
                    f" Found {len(self.models)}."
                )
            if self.analytics.requires_tracker and (self.tracker is None):
                raise IncompatiblePipelineError(
                    "Current Analytics spec requires at least Tracker, "
                    "but none found."
                )
        if self.tracker:
            if len(self.models) < 1:
                raise IncompatiblePipelineError(
                    "Tracker requires at least 1 InferenceEngine."
                    f" Found {len(self.models)}."
                )

    @property
    def pipeline(self) -> Gst.Pipeline:
        """Gstreamer pipeline lazy property.

        Returns:
            The only Gstremaer pipeline on this app, instantiated.

        """
        if not self._pipeline:
            self._pipeline = self.parse_launch()
        return self._pipeline

    def parse_launch(self) -> Gst.Pipeline:
        """Instantiate the internal `Gst.Pipeline`.

        Returns:
            The instantiated :class:`Gst.Pipeline`.

        Raises:
            NotImplementedError: pipeline already instantiated.
            InvalidPipelineError: Unable to parse pipeline because of a
                syntax error in the pipeline string.
            GLib.Error: Syntax unrelated error - unable to parse
                pipeline.

        """
        gst_init()
        if self._pipeline:
            raise NotImplementedError(
                "TODO: make a copy of the pipeline,"
                " this one is already in use"
            )
        try:
            return Gst.parse_launch(self.gst())
        except GLib.Error as exc:
            if "syntax error" in str(exc):
                raise InvalidPipelineError from exc
            raise

    def start(self) -> Gst.StateChangeReturn:
        """Start the pipeline by setting it to PLAYING state.

        Returns:
            The state change result enum.

        Raises:
            RuntimeError: Unable to play the pipeline.

        """
        result = self.pipeline.set_state(Gst.State.PLAYING)
        if result is Gst.StateChangeReturn.FAILURE:
            self.stop()
            raise RuntimeError(f"ERROR: {UNABLE_TO_PLAY_PIPELINE}")
        return result

    def stop(self) -> None:
        """Set the pipeline to null state."""
        self.pipeline.set_state(Gst.State.NULL)

    def send_eos(self) -> None:
        """Send a gstreamer 'end of stream' signal."""

        self.pipeline.send_event(Gst.Event.new_eos())


ModelType = Union[
    Collection[Union[Path, InferenceEngine]], Path, InferenceEngine, None
]


class Pipeline(BasePipeline):
    """Wrapper to ease pipeline creation from simple building blocks."""

    def __init__(  # noqa: R0913
        self,
        sources: SourceUri | list[SourceUri] | tuple[SourceUri],
        models: ModelType = None,
        sink: SinkUri = "fakesink",
        analytics: Union[Path, Analytics] | None = None,
        tracker: Union[Path, Tracker] | None = None,
    ) -> None:
        """Initialize pipeline wrapper to incrementally build pipeline.

        Args:
            sources: Collection of uri sources to join in `nvstreammux`.
            models: Collection of models to insert in the pipeline.
            sink: Final element of the pipeline.
            analytics: Optional `nvdsanalytics`.
            tracker: Optional `nvtracker`.

        Raises:
            ValueError: invalid analytics or tracker object.

        """
        super().__init__()
        if isinstance(sources, SourceUri):
            sources = [sources]
        self.source = PythiaSourceBase.from_uris(*sources)

        if isinstance(models, (Path, InferenceEngine)):
            models = [models]
        self.models = (
            [
                model
                if isinstance(model, InferenceEngine)
                else InferenceEngine.from_folder(model)
                for model in models
            ]
            if models
            else []
        )
        self._model_map: dict[str, InferenceEngine] = {}

        if analytics is None:
            self.analytics = analytics
        elif isinstance(analytics, Analytics):
            self.analytics = analytics
        elif isinstance(analytics, Path):
            self.analytics = Analytics.from_file(analytics)
        else:
            raise ValueError(f"Unhandled {analytics=}")

        if tracker is None:
            self.tracker = tracker
        elif isinstance(tracker, Tracker):
            self.tracker = tracker
        elif isinstance(tracker, Path):
            self.tracker = Tracker.from_file(tracker)
        else:
            raise ValueError(f"Unhandled {tracker=}")

        self.sink = PythiaSink.from_uri(sink)

    @property
    def CONNECTIONS(self) -> Con:  # type: ignore[override] # noqa: C0103
        cons: Con = defaultdict(dict)
        for connectable in (self.source, *self.models, self.sink):
            for element_name, connections in connectable.CONNECTIONS.items():
                for signal, callback in connections.items():
                    cons[element_name][signal] = callback

        return cons

    @property
    def model_map(self) -> Dict[str, InferenceEngine]:
        """Lazyproperty mapping from model names to inference engines.

        Returns:
            A dictionary whose keys are nvinfer names and their values
                are their respective :class:`InferenceEngine` wrappers.

        """
        if not self._model_map:
            self.gst()
        return self._model_map

    def gst(self) -> str:
        """Render its string for to use in `gst-launch`-like syntax.

        Returns:
            The pipeline as it would be used when calling `gst-launch`.

        """
        source = self.source.gst()
        models = ""
        for idx, model in enumerate(self.models):
            name = f"model_{idx}"
            self._model_map[name] = model
            models += model.gst(
                name=name,
                unique_id=idx + 1,
            )

        sink = self.sink.gst()
        return _(
            f"""
            {source}
            {'! '+models if models else ''}
            ! {sink}
        """
        )


class StringPipeline(BasePipeline):
    """Pythia pipeline wrapper to construct from pipeline strings."""

    CONNECTIONS: Con = {}

    def __init__(self, pipeline_string: str) -> None:
        """Initialize pipeline wrapper using a pipeline string.

        Args:
            pipeline_string: A `gst-launch`-like pipeline string.

        Raises:
            InvalidPipelineError: Unable to parse pipeline because of a
                syntax error in the pipeline string.
            GLib.Error: Syntax unrelated error - unable to parse
                pipeline.

        """
        super().__init__()
        self.pipeline_string = pipeline_string
        try:
            self.pipeline
        except GLib.Error as exc:
            if "gst_parse_error" not in str(exc):
                raise
            raise InvalidPipelineError(
                f"Unable to parse pipeline:\n```gst\n{pipeline_string}\n```"
            ) from exc
        self.models = find_models(self.pipeline)
        self.analytics = find_analytics(self.pipeline)
        self.tracker = find_tracker(self.pipeline)

    def gst(self) -> str:
        return self.pipeline_string
