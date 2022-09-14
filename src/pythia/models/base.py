"""Model.

A deep learning model used to extract metadata from a video source.
Contains:

    A labels.txt file, containing the list of model labels.
    A pgie.conf file.
    A model.etlt,model.engine or any Deepstream-nvinfer compatible engine file.

"""
from __future__ import annotations

import configparser
import json
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from textwrap import dedent as _
from typing import Collection
from typing import Dict
from typing import Optional
from typing import Type
from typing import TypeVar

from pythia.types import Con
from pythia.types import HasConnections
from pythia.utils.ext import not_empty
from pythia.utils.ext import not_none
from pythia.utils.gst import Gst

IE = TypeVar("IE", bound="InferenceEngine")
T = TypeVar("T", bound="Tracker")
A = TypeVar("A", bound="Analytics")


@dataclass
class InferenceEngine(HasConnections):
    """Pythia wrapper around nvinfer gst element."""

    MODEL_SUFFIXES = {
        ".etlt": "tlt-encoded-model",
        ".caffe": "model-file",
        ".caffemodel": "model-file",
        ".prototxt": "proto-file",
        ".onnx": "onnx-file",
        ".uff": "uff-file",
        # ".engine": "model-engine-file",
    }
    """Supported model extensions (prioritized order).

    Used when an inference engine is to be instantiated by a directory,
    to locate supported models from their extension.

    See Also: :meth:`locate_source_model`.

    """

    MODEL_CONFIG_SUFFIXES = (
        ".conf",
        ".ini",
        ".yml",
        ".yaml",
    )
    """Ordered collection of supported model config file extensions.

    Used when an inference engine is to be instantiated by a directory,
    to locate `config-file-path` from their extension.

    See Also: :meth:`locate_config_file`.

    """

    labels_file: Path
    config_file: Path
    _string: Optional[str] = None
    source_model: Optional[Path] = None
    compiled_model: Optional[Path] = None
    _default_props: Dict[str, str] = field(default_factory=dict)

    CONNECTIONS: Con = field(default_factory=dict)  # noqa: C0103

    def gst(self, name: str, **kw) -> str:
        """Render nvinfer with `gst-launch`-like syntax.

        Args:
            name: nvinfer gstreamer element name property.
            kw: nvinfer gstreamer property name and value.

        Returns:
            Rendered string

        See Also:
            https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_plugin_gst-nvinfer.html#gst-properties

        """
        props = "\n".join(f"{k.replace('_', '-')}={v}" for k, v in kw.items())
        self._string = _(
            f"""\
            nvinfer
              config-file-path={self.config_file}
              name={name}
              {props}
        """
        )
        return self._string

    @classmethod
    def locate_source_model(cls, folder: Path) -> Path | None:
        """Find the first deepstream model file in a folder.

        It iterates over the known nvinfer-compatible model file
        extensions, and returns at the first success.

        Args:
            folder: Directory to search the model.

        Returns:
            Found model, or `None` if not found.

        """
        for suffix in cls.MODEL_SUFFIXES:
            try:
                return not_empty(next(iter(folder.glob(f"*{suffix}"))))
            except StopIteration:
                pass
        return None

    @staticmethod
    def locate_labels_file(folder: Path) -> Path:
        """Find labels file from a directory.

        Args:
            folder: directory to search labels file.

        Returns:
            The first file matching the `*label*` pattern inside the
            directory.

        Raises:
            FileNotFoundError: no file matches the expected labels
                pattern.

        """
        try:
            return not_empty(next(iter(folder.glob("*label*"))))
        except StopIteration as exc:
            raise FileNotFoundError(
                f"No labels file found at {folder}"
            ) from exc

    @classmethod
    def locate_config_file(cls, folder: Path) -> Path:
        """Find the first model config file in a folder.

        Iterate over the known nvinfer-compatible config-file-path file
        extensions, and returns at the first success.

        Args:
            folder: Directory to search the model.

        Returns:
            path to the found configuration file.

        Raises:
            FileNotFoundError: No configuration file found.

        """
        for suffix in cls.MODEL_CONFIG_SUFFIXES:
            try:
                return not_empty(next(iter(folder.glob(f"*{suffix}"))))
            except StopIteration:
                pass
        raise FileNotFoundError(f"No config file found at {folder}")

    @staticmethod
    def locate_compiled_model(
        folder: Path, source_model: Path | None
    ) -> Path | None:
        """Find the first model engine file in a folder.

        Returns a file matching the `*.engine` pattern

        Args:
            folder: Directory to search the model.
            source_model: If set, use this path's stem to try to locate
                the `.engine` file. Otherwise, finds any `*.engine`.

        Returns:
            path to the found configuration file.

        Raises:
            FileNotFoundError: No configuration file found using any of
                the strategies.

        """
        if source_model:
            try:
                return not_empty(
                    next(
                        iter(
                            source_model.parent.glob(
                                f"*{source_model.stem}*.engine"
                            )
                        )
                    )
                )
            except StopIteration:
                pass
        try:
            return next(iter(folder.glob("*.engine")))
        except StopIteration as exc:
            if not source_model:
                raise FileNotFoundError(
                    f"Neither {source_model=} nor its compiled version exist."
                ) from exc
            return None

    @classmethod
    def from_folder(cls: Type[IE], folder: str | Path) -> IE:
        """Factory to instantiate from directories.

        Args:
            folder: Directory where the model files are located.

        Returns:
            Instantiated model.

        Raises:
            FileNotFoundError: empty folder received.

        """
        folder = Path(folder).resolve()
        if not folder.exists():
            raise FileNotFoundError(f"No directory not found at {folder}.")

        source_model = cls.locate_source_model(folder)
        labels_file = cls.locate_labels_file(folder)
        config_file = cls.locate_config_file(folder)
        compiled_model = cls.locate_compiled_model(folder, source_model)

        return cls(
            labels_file=labels_file,
            config_file=config_file,
            source_model=source_model,
            compiled_model=compiled_model,
        )

    @classmethod
    def from_element(cls: Type[IE], element: Gst.Element) -> IE:
        """Factory from nvinfer.

        Args:
            element: The nvinfer to use as source.

        Returns:
            The instantiated nvinfer wrapper.

        """
        skip = ("parent",)
        props = {}
        for prop in element.list_properties():
            name = prop.name
            if name in skip:
                continue

            raw = element.get_property(name)
            try:
                value = raw.value_nick  # enums
            except AttributeError:
                value = str(raw)
                if isinstance(raw, bool):
                    value = value.lower()  # False -> false
            props[name] = value

        config_file = Path(props.pop("config-file-path")).resolve()
        return cls(
            config_file=config_file,
            labels_file=not_none(
                cls.pop_property_or_get_from_nvinfer_conf(  # noqa: C0301
                    config_file,
                    props,
                    property_names=("labelfile-path",),
                )
            ),
            source_model=cls.pop_property_or_get_from_nvinfer_conf(
                config_file,
                props,
                property_names=cls.MODEL_SUFFIXES.values(),
            ),
            compiled_model=cls.pop_property_or_get_from_nvinfer_conf(
                config_file,
                props,
                property_names=("model-engine-file",),
            ),
            _default_props=props,
        )

    @staticmethod
    def pop_property_or_get_from_nvinfer_conf(
        config_file: Path,
        props: dict[str, str],
        *,
        property_names: Collection[str],
    ) -> Path | None:
        """Pop nvinfer property, or get from config_file if not found.

        Args:
            config_file: `nvinfer.conf` ini file. Used to compute
                absolute paths, and default source for property values
                if not found in the props arg.
            props: element properties where to look for the desired
                properties. Note: If the property is found, its popped
                from this dict.
            property_names: possible property names to look for.

        Returns:
            First occurence of the property_names, as found either in
                the props dict or in the nvinfer.conf `[property]`
                section.

        Raises:
            FileNotFoundError: None of the requested names is available
                in the properties, and the config file does not exist.

        """
        # extract from nvinfer's properties
        for prop_name in property_names:
            value = props.get(prop_name, None)
            if value is None:
                continue
            value_path = Path(value)
            if not value_path.is_absolute():
                value_path = value_path.relative_to(config_file).resolve()
            return value_path

        # extract from nvinfer's config file
        if not config_file.exists():
            raise FileNotFoundError(config_file)
        config = configparser.ConfigParser()
        config.read(str(config_file))
        for prop_name in property_names:
            value = config["property"].get(prop_name, None)
            if value is None:
                continue
            value_path = Path(value)
            if not value_path.is_absolute():
                value_path = (config_file.parent / value_path).resolve()
            return value_path

        return None


@dataclass
class Tracker(HasConnections):
    """Pythia wrapper around nvtracker gst element."""

    config_file: Path
    low_level_library: Path = Path(
        "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so"
    ).resolve()
    _string: Optional[str] = None
    _default_props: Dict[str, str] = field(default_factory=dict)
    CONNECTIONS: Con = field(default_factory=dict)  # noqa: C0103

    @classmethod
    def from_file(
        cls: Type[T],
        config_file: Path,
        low_level_library: Path = low_level_library,
    ) -> T:
        """Factory to create `Tracker` s from configuration file.

        Args:
            config_file: path for the `nvtracker` gstreamer element
                'll-config-file' property.
            low_level_library: path for the `nvtracker` gstreamer element
                'll-lib-file' property (shared object).

        Returns:
            Instantiated `Tracker`.

        Raises:
            FileNotFoundError: Tracker config file does not exist.

        """
        config_file = Path(config_file).resolve()
        if not config_file.exists():
            raise FileNotFoundError(
                f"No Tracker configuration file found at {config_file}."
            )
        return cls(
            config_file=config_file,
            low_level_library=low_level_library,
        )

    @classmethod
    def from_element(cls: Type[T], element: Gst.Element) -> T:
        """Factory from nvtracker.

        Args:
            element: The nvtracker to use as source.

        Returns:
            The instantiated nvtracker wrapper.

        """
        skip = ("parent",)
        props = {}
        for prop in element.list_properties():
            name = prop.name
            if name in skip:
                continue

            raw = element.get_property(name)
            try:
                value = raw.value_nick  # enums
            except AttributeError:
                value = str(raw)
                if isinstance(raw, bool):
                    value = value.lower()  # False -> false
            props[name] = value

        return cls(
            config_file=props.pop("ll-config-file"),
            low_level_library=props.pop("ll-lib-file"),
            _default_props=props,
        )

    def gst(self, name: str, **kw: str) -> str:
        """Render nvtracker element with `gst-launch`-like syntax.

        Args:
            name: gst element name
            kw: property name and value for the gst element

        Returns:
            Rendered string.

        Raises:
            FileNotFoundError: Tracker ll-config-file not found.

        See Also:
            https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_plugin_gst-nvtracker.html#gst-properties

        """
        inline_props = json.loads(json.dumps(self._default_props))
        inline_props.update(kw)
        props = "\n".join(
            f"{k.replace('_', '-')}={v}" for k, v in inline_props.items()
        )

        if not self.low_level_library.exists():
            raise FileNotFoundError(
                "Could not find Tracker implementation"
                f" at {self.low_level_library}"
            )
        self._string = _(
            f"""\
            nvtracker
              ll-config-file={self.config_file}
              ll-lib-file={self.low_level_library}
              name={name}
              {props}
        """
        )
        return self._string


@dataclass
class Analytics(HasConnections):
    """Pythia wrapper around nvdsanalytics gst element."""

    config_file: Path
    _string: Optional[str] = None
    _default_props: Dict[str, str] = field(default_factory=dict)
    CONNECTIONS: Con = field(default_factory=dict)  # noqa: C0103

    def gst(self, name: str = "analytics", **kw: str) -> str:
        """Render string as `gst-launch`-like parseable string.

        Args:
            name: Gst element name.
            kw: Mapping to define additional properties.

        Returns:
            Rendered `nvdsanalytics`.

        See Also:
            https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_plugin_gst-nvdsanalytics.html#gst-properties

        """
        inline_props = json.loads(json.dumps(self._default_props))
        inline_props.update(kw)
        props = "\n".join(
            f"{k.replace('_', '-')}={v}" for k, v in inline_props.items()
        )
        self._string = _(
            f"""\
            nvdsanalytics
              config-file={self.config_file}
              name={name}
              {props}
        """
        )
        return self._string

    def requires_tracker(self) -> bool:
        """Return `True` if its `nvdsanalytics` requires `nvtracker`.

        Returns:
            `True` if its `nvdsanalytics` contains line crossing or
                direction andata.

        """
        return True

    @classmethod
    def from_file(cls: Type[A], config_file: Path) -> A:
        """Factory from configuration file.

        Args:
            config_file: location of the nvdsanalytics `config-file`
                property.

        Returns:
            The instantiated `nvdsanalytics` wrapper class.

        Raises:
            FileNotFoundError: The `nvdsanalytics` `config-file`
                property is not found.

        """
        config_file = Path(config_file).resolve()
        if not config_file.exists():
            raise FileNotFoundError(
                f"No Analytics configuration file found at {config_file}."
            )
        return cls(config_file=config_file)

    @classmethod
    def from_element(cls: Type[A], element: Gst.Element) -> A:
        """Factory from nvdsanalytics.

        Args:
            element: The nvdsanalytics to use as source.

        Returns:
            The instantiated nvdsanalytics wrapper.

        """
        skip = ("parent",)
        props = {}
        for prop in element.list_properties():
            name = prop.name
            if name in skip:
                continue

            raw = element.get_property(name)
            try:
                value = raw.value_nick  # enums
            except AttributeError:
                value = str(raw)
                if isinstance(raw, bool):
                    value = value.lower()  # False -> false
            props[name] = value

        return cls(
            config_file=props.pop("config-file"),
            _default_props=props,
        )
