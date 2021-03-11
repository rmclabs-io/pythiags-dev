# -*- coding: utf-8 -*-
"""Utilities and shortcuts to ease pythiags usage."""

import imghdr
import inspect
import re
import struct
from importlib import import_module
from importlib.util import module_from_spec
from importlib.util import spec_from_file_location
from pathlib import Path
from typing import Tuple
from typing import Union

from pythiags import logger


def get_image_size(fname: str) -> Tuple[int, int]:
    """Determine the image type of fhandle and return its size.

    Args:
        fname: Filename to extract the resolution from.

    Raises:
        NotImplementedError: Unable to guess resolution

    Returns:
        The (height, width) resolution tuple.

    """
    with open(fname, "rb") as fhandle:
        head = fhandle.read(24)
        if len(head) != 24:
            raise NotImplementedError
        if imghdr.what(fname) == "png":
            check = struct.unpack(">i", head[4:8])[0]
            if check != 0x0D0A1A0A:
                raise NotImplementedError
            value = struct.unpack(">ii", head[16:24])
            if len(value) == 2:
                return value
            raise NotImplementedError
        if imghdr.what(fname) == "gif":
            value = struct.unpack("<HH", head[6:10])
            if len(value) == 2:
                return value
            raise NotImplementedError
        if imghdr.what(fname) in {"jpeg", "jpg"}:
            fhandle.seek(0)  # Read 0xff next
            size = 2
            ftype = 0
            while not 0xC0 <= ftype <= 0xCF:
                fhandle.seek(size, 1)
                byte = fhandle.read(1)
                while ord(byte) == 0xFF:
                    byte = fhandle.read(1)
                ftype = ord(byte)
                size = struct.unpack(">H", fhandle.read(2))[0] - 2
            # We are at a SOFn block
            fhandle.seek(1, 1)  # Skip `precision' byte.
            return struct.unpack(">HH", fhandle.read(4))

        raise NotImplementedError


def guess_resolution(filesrc_pattern: str) -> Tuple[int, int]:
    """Guess the resolution from a filesource pattern.

    Search the first available picture complying the received pattern
    and return its resolution.

    Args:
        filesrc_pattern: A valid pattern for gstreamer `multifilesrc`
            location property.

    Returns:
        The (height, width) resolution.

    .. seealso:: get_image_size

    """
    path = Path(filesrc_pattern)
    fname = str(next(path.parent.glob(f"*{path.suffix}")))

    return get_image_size(fname)


def module_from_file(name: Union[str, Path]):
    """Import a module from its filepath."""
    try:
        return import_module(name)
    except ImportError as exc:
        pass

    path = Path(name).resolve().with_suffix(".py")
    spec = spec_from_file_location(path.stem, str(path))
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def attribute_as_instance(mod, obj_name):
    """Get an attribute, and instantiate it if its a class."""
    obj = getattr(mod, obj_name)
    if isinstance(obj, type):
        return obj()
    return obj


def instantiated_object_from_importstring(pattern: str):
    """Retrieve and import specified object from module.

    Args:
        pattern: Must have the following syntax:
            "/path/to/module:class_or_obj".

    Returns:
        The instantiated object, after importing the module.

    Example:
      ```console
      $ cat demo.py
      class A:
          pass
      a = A()
      ```

      >>> instantiated_object_from_importstring("demo:A")
      <__main__.A object at 0x7f7d4a25bbb0>
      >>> >>> instantiated_object_from_importstring("demo:a")
      <__main__.A object at 0x7f7d4a25b9d0>

    """
    module_name, obj_name = pattern.split(":")
    return attribute_as_instance(module_from_file(module_name), obj_name)


def clean_pipeline(pipeline: str) -> str:
    no_comments = re.sub(
        r"(^|\s*)#\s*[^\"']*?\n",
        "",
        pipeline,
    )

    clean_caps = re.sub(
        r"caps=(['\"])(.*?)(\1)",
        r"caps=\2",
        no_comments,
    )

    # TODO: Also cleanup caps then used "between" `!` in "element" mode

    return clean_caps


def validate_processor(processor, klass):
    if not isinstance(processor, klass):
        msg = (
            f"ProcessorValidation: Invalid {processor}: must subclass {klass}"
        )
        logger.error(msg)
        raise TypeError(msg)

    for m in klass.__abstractmethods__:
        required_signature = inspect.getfullargspec(getattr(klass, m)).args
        current_signature = inspect.getfullargspec(getattr(processor, m)).args
        if current_signature != required_signature:
            msg = f"ProcessorValidation: {processor} - bad signature for the '{m}' method: must be {required_signature}, not {current_signature}"
            logger.error(msg)
            raise TypeError(msg)
    return processor
