# -*- coding: utf-8 -*-
"""Nvidia ini-style configparser utilities."""

# -*- coding: utf-8 -*-
"""Nvidia ini-style configparser utilities."""

import configparser
from pathlib import Path
from typing import Union
from typing import Union

from pythia import logger
from pythia import Gst

class ConfigParser(configparser.ConfigParser):
    __source_file__: Path

def build_conf(path: Union[str, Path]) -> ConfigParser:
    config_file_path = str(path.resolve()) if isinstance(path, Path) else path
    config = ConfigParser()
    config.optionxform = str
    config.read(config_file_path)
    config.__source_file__ = Path(config_file_path)
    return config

def get_key(
    conf: ConfigParser, *keyspath:str, on_error="raise"
) -> Union[str, ConfigParser, configparser.SectionProxy]:
    """Walk down a dict-like obj until the end of the path or invalid path.

    Args:
        conf: configuration object. If it contains `__source_file__`
            attr, it is used to report the exception for increased
            verbosity.
        keyspath: Sequence of keys to walk from root.
        on_error: Control to raise or warn on error. If set to "raise"
            (default), raises exception on error.

    Returns:
        The extracted element value

    Raises:
        ValueError: If the path is not walk-able.

    """
    out = conf
    road = ""
    for part in keyspath:
        try:
            road += f"->{str(part)}"
            out = out[part]
        except KeyError as exc:
            road = road.lstrip("->")
            src = getattr(conf, "__source_file__", conf)
            error_message = f"Cannot read property {road} in `{src}`"
            if on_error == "raise":
                raise ValueError(error_message) from exc
            logger.warning(error_message)
            return ""
    return out


def gen_classname_mapper(config_file_path: str):
    """Generate a dictionary to convert integers to classnames.

    The mapping is constructed by looking into the configfiles
    `labelfile-path`.

    Args:
        config_file_path: The INI configuration file with a `property`
            section, containig a `labelsfile-path`.

    Returns:
        An int -> str mapping for the classes and their names.
    """

    def _build_dict(labels_file):
        with open(labels_file, "r") as labelsfile:
            mapper = {
                lineno: kind.rstrip("\n")
                for lineno, kind in enumerate(labelsfile.readlines())
            }
        return mapper

    config = build_conf(config_file_path)
    labels_str = get_key(config, "property", "labelfile-path")
    if not isinstance(labels_str, str):
        raise ValueError(f"labelfile-path in {config_file_path} must be a string!")
    labels_file = Path(labels_str)
    if not labels_file.is_absolute():
        labels_file = (Path(config_file_path).parent / labels_file).resolve()
    mapper = _build_dict(labels_file)

    return mapper


def classname_mapper_from_pipeline(pipeline, classname_mapper):
    if not classname_mapper:
        return {}
    if isinstance(classname_mapper, str):
        it = pipeline.iterate_elements()
        while True:
            result, el = it.next()
            if result != Gst.IteratorResult.OK:
                msg = f"Completed searching the pipeline but found no nvinfer containing {classname_mapper}"
                raise ValueError(msg)
            if type(el).__name__ != "GstNvInfer":
                continue
            path = el.get_property("config-file-path")
            if path.endswith(classname_mapper):
                return gen_classname_mapper(path)
    if isinstance(classname_mapper, dict):
        return classname_mapper
    raise ValueError(f"Invalid classname_mapper=`{classname_mapper}`")


def get_file_param(config:ConfigParser, *keyspath, on_error="raise", check_existence=False):
    if check_existence and on_error != "raise" :
        raise ValueError("Either raise if file not found or dont check file existence.")

    config_file_path = config.__source_file__
    value = get_key(config, *keyspath, on_error=on_error)
    if not isinstance(value, str):
        raise ValueError(f"{keyspath} in {config_file_path} must be a string!")
    if not value:
        return None

    file_path = Path(value)
    if not file_path.is_absolute():
        file_path = (Path(config_file_path).parent / file_path).resolve()

    if check_existence and not file_path.exists():
        raise FileNotFoundError(file_path)
    return file_path
