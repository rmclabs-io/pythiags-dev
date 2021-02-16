# -*- coding: utf-8 -*-
"""Nvidia ini-style configparser utilities.

The Gst-nvinfer configuration file uses a “Key File” format described in:
https://specifications.freedesktop.org/desktop-entry-spec/latest

"""

import configparser
from pathlib import Path
from typing import Dict
from typing import Optional
from typing import Union

from pythia import logger


class ConfigParser(configparser.ConfigParser):  # noqa: R0901
    __source_file__: Path


def build_conf(path: Union[str, Path]) -> ConfigParser:
    config_file_path = str(path.resolve()) if isinstance(path, Path) else path
    config = ConfigParser()
    config.optionxform = str
    config.read(config_file_path)
    config.__source_file__ = Path(config_file_path)
    return config


def get_key(
    conf: ConfigParser, *keyspath: str, on_error="raise"
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


def gen_classname_mapper(config_file_path: str) -> Dict[int, str]:
    """Generate a dictionary to convert integers to classnames.

    The mapping is constructed by looking into the configfiles
    `labelfile-path`.

    Args:
        config_file_path: The INI configuration file with a `property`
            section, containig a `labelsfile-path`.

    Returns:
        An int -> str mapping for the classes and their names.

    Raises:
        ValueError: received `labelfile-path` in `config_file_path` is not a string.

    """

    def _build_dict(labels_file):
        with open(labels_file, "r") as labelsfile:
            mapper_ = {
                lineno: kind.rstrip("\n")
                for lineno, kind in enumerate(labelsfile.readlines())
            }
        return mapper_

    config = build_conf(config_file_path)
    labels_str = get_key(config, "property", "labelfile-path")
    if not isinstance(labels_str, str):
        raise ValueError(
            f"labelfile-path in {config_file_path} must be a string!"
        )
    labels_file = Path(labels_str)
    if not labels_file.is_absolute():
        labels_file = (Path(config_file_path).parent / labels_file).resolve()
    mapper = _build_dict(labels_file)

    return mapper


def get_file_param(
    config: ConfigParser, *keyspath, on_error="raise", check_existence=False
) -> Optional[Path]:
    """Get a filepath from a sequence of getittem-feedable keys.

    Args:
        config: The source configparser instance from where to read the
            configuration.
        keyspath: Sequence of keys used to find the requested value.
        on_error: Whether to raise if the sequence of keys is not found.
        check_existence: Validate file existence.

    Raises:
        ValueError: Key found but its value is not a string.
        FileNotFoundError: Key found but resolved path is nonexistent.

    Returns:
        Absolute path of the requested value. Can be none if not found
            and not validated.

    """

    config_file_path = config.__source_file__
    value = get_key(
        config,
        *keyspath,
        on_error=on_error if not check_existence else "raise",
    )
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
