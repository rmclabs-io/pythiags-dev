# -*- coding: utf-8 -*-
"""Utilities and shortcuts to ease pythiags usage."""

import imghdr
import inspect
import re
import struct
import subprocess as sp
from datetime import datetime
from functools import singledispatch
from functools import wraps
from importlib import import_module
from importlib.util import module_from_spec
from importlib.util import spec_from_file_location
from pathlib import Path
from typing import Callable
from typing import Optional
from typing import Tuple
from typing import Union
from uuid import uuid4

from pythiags import GLib
from pythiags import Gst
from pythiags import logger

SENTINEL = str(object())


def _build_info(func, *a, **kw):
    name = getattr(func, "__qualname__", getattr(func, "__name__", str(func)))

    if a:
        args = ", ".join(str(arg) for arg in a)
        if kw:
            args += ", "
    else:
        args = ""
    if kw:
        kwargs = ", ".join(f"{k}={v}" for k, v in kw.items())
    else:
        kwargs = ""
    return name, f"{name}({args}{kwargs})"


def noop_when(condition, ret=None):

    if not condition:
        return lambda func: func

    def wrapper(func):
        @wraps(func)
        def wrapped(*a, **kw):
            return ret

        return wrapped

    return wrapper


def raise_when_returns(*invalids):

    invalids = set(invalids)

    def wrapper(func):
        @wraps(func)
        def wrapped(*a, **kw):
            name, repred = _build_info(func, *a, **kw)
            ret = func(*a, **kw)
            if ret in invalids:
                raise ValueError(f"{repred} returned {ret}")
            return ret

        return wrapped

    return wrapper


def traced(
    logging_function: Callable,
    log_time: bool = False,
    log_pre: bool = True,
    log_post: bool = True,
    log_exc: bool = True,
):

    any_log = log_pre or log_post or log_exc

    # if any_log:
    #     def build_info(func, *a, **kw):
    #         uuid = str(uuid4())
    #         name, repred = _build_info(func, *a, **kw)
    #         pre = datetime.now()
    #         return name, repred, pre, uuid
    # else:
    #     def build_info(func, *a, **kw):
    #         return None, None, None, None

    @noop_when(not any_log, ret=(None, None, None, None))
    def build_info(func, *a, **kw):
        uuid = str(uuid4())
        name, repred = _build_info(func, *a, **kw)
        pre = datetime.now()
        return name, repred, pre, uuid

    # if log_pre:
    #     def log_before(uuid, repred, pre):
    #         if log_time:
    #             time_ex = f" @ {pre}"
    #         else:
    #             time_ex = ""
    #         logging_function(f"{'CALL':<8} [{uuid}]: {repred}{time_ex}")
    # else:
    #     def log_before(uuid, repred, pre):
    #         pass

    @noop_when(not log_time, ret="")
    def time_before(pre):
        return f" @ {pre}"

    @noop_when(not log_pre)
    def log_before(name, repred, pre, uuid):
        logging_function(f"{'CALL':<8} [{uuid}]: {repred}{time_before(pre)}")

    # if log_post:
    #     def log_after(uuid, name, ret, pre):
    #         if log_time:
    #             time_ex = f" - took {datetime.now()-pre} [s]"
    #         else:
    #             time_ex = ""

    #         logging_function(f"{'RETURN':<8} [{uuid}]: {name} => {ret}{time_ex}")
    # else:
    #     def log_after(uuid, name, ret, pre):
    #         pass

    @noop_when(not log_time, ret="")
    def time_after(pre):
        post = datetime.now()
        return f" @ {post} (took {post-pre} [s])"

    @noop_when(not log_post)
    def log_after(name, repred, pre, uuid, ret):
        logging_function(
            f"{'RETURN':<8} [{uuid}]: {name} => {ret}{time_after(pre)}"
        )

    @noop_when(not log_time, ret="")
    def time_exc(pre):
        post = datetime.now()
        return f" @ {post} (after {post-pre} [s])"

    @noop_when(not log_post)
    def log_exception(name, repred, pre, uuid, exc):
        # logging_function(f"{'RETURN':<8} [{uuid}]: {name} => {ret}{time_after(pre)}")
        logger.error(
            f"{'ERROR':<8} [{uuid}]: {name} - {type(exc).__name__} ({exc}){time_exc(pre)}"
        )

    # import pdb;pdb.set_trace()
    def factory(func):
        @wraps(func)
        def wrapper(*a, **kw):

            info = build_info(func, *a, **kw)
            log_before(*info)
            try:
                ret = func(*a, **kw)
            except Exception as exc:
                log_exception(*info, exc=exc)
                raise
            else:
                log_after(*info, ret=ret)
            return ret

        return wrapper

    return factory


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


def parse_launch(gstlaunch_pipeline: str) -> str:
    try:
        pipeline = Gst.parse_launch(gstlaunch_pipeline)
    except GLib.GError as exc:
        msg = str(exc)
        if "{" in msg:
            msg += ". Maybe you forgot to add pipeline kwargs?"
        logger.error(msg)
        raise RuntimeError(msg) from exc

    if not pipeline:
        msg = f"Unable to initialize Gstreamer Pipeline"
        logger.error(msg)
        raise RuntimeError(msg)
    return pipeline


@raise_when_returns(None)
def parse_bin(gstlaunch_bin: str, *a, **kw) -> Gst.Bin:
    try:
        return Gst.parse_bin_from_description(gstlaunch_bin, *a, **kw)
    except GLib.GError as exc:
        logger.error(f"{exc}: {gstlaunch_bin}")
        raise


@raise_when_returns(None)
def get_by_name(gst_bin: Gst.Bin, name: str) -> Gst.Element:
    return gst_bin.get_by_name(name)


@raise_when_returns(False)
def gst_add(gst_bin: Gst.Bin, element: Gst.Element) -> bool:
    return gst_bin.add(element)


@raise_when_returns(False)
def gst_remove(gst_bin: Gst.Bin, element: Gst.Element) -> bool:
    return gst_bin.remove(element)


@raise_when_returns(False)
def link_elements(left: Gst.Element, right: Gst.Element) -> bool:
    return left.link(right)


@raise_when_returns(False)
def get_fraction(struct: Gst.Structure, name: str) -> float:
    success, *framerate = struct.get_fraction(name)
    if success is False:
        return success
    return float(framerate[0] / framerate[1])


@traced(logger.info)
def unlink_elements(left: Gst.Element, right: Gst.Element) -> None:
    logger.debug("Unlinking elements")
    result = left.unlink(right)
    # if not result:
    #     raise ValueError(f"{left}.unlink('{right}') returned None")
    return result


@raise_when_returns(
    Gst.PadLinkReturn.WRONG_HIERARCHY,
    Gst.PadLinkReturn.WAS_LINKED,
    Gst.PadLinkReturn.WRONG_DIRECTION,
    Gst.PadLinkReturn.NOFORMAT,
    Gst.PadLinkReturn.NOSCHED,
    Gst.PadLinkReturn.REFUSED,
)
def link_pads(left: Gst.Pad, right: Gst.Pad) -> None:
    return left.link(right)


@raise_when_returns(None)
def get_static_pad(element: Gst.Element, padname: str) -> Gst.Pad:
    pad = element.get_static_pad(padname)
    if not pad:
        raise ValueError(
            f"{element}.get_static_pad('{padname}') returned None"
        )
    return pad


def sync_state_with_parent(
    element: Gst.Element,
):
    sync = element.sync_state_with_parent()
    if not sync:
        raise ValueError(f"{element}.sync_state_with_parent() returned False")
    return sync


def sync_children_states(
    gst_bin: Gst.Bin,
):
    sync = gst_bin.sync_children_states()
    if not sync:
        raise ValueError(f"{gst_bin}.sync_children_states() returned {sync}")
    return sync


def add_probe(pad: Gst.Pad, probe_type, callback, *cb_args):
    probe_id = pad.add_probe(probe_type, callback, *cb_args)
    if not probe_id:
        raise RuntimeError(f"f{pad}.add_probe failed")
    return probe_id


def send_event(
    element: Gst.Element,
    event: Gst.Event,
):
    result = element.send_event(event)
    if not result:
        raise RuntimeError(f"f{element}.send_event({event}) failed")
    return result


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


png_count = 0
from threading import Lock

png_count_lock = Lock()


def pipe_to_png(pipeline, name_):

    dir_ = Path(
        os.environ.get("GST_DEBUG_DUMP_DOT_DIR", os.getcwd())
    ).resolve()
    dir_.mkdir(parents=True, exist_ok=True)

    def _pipe_to_png():
        global png_count
        with png_count_lock:
            png_count += 1
            current = png_count
        name = f"{current}_{name_}"
        dot = Gst.debug_bin_to_dot_file(
            pipeline, Gst.DebugGraphDetails.ALL, name
        )
        name = str(dir_ / f"{current}_{name_}")
        sp.check_call(["dot", "-Tpng", f"-o{name}.png", f"{name}.dot"])
        return dot

    from pythiags.background import run_later

    run_later(
        _pipe_to_png,
        delay=0,
    )


def dotted(func):

    name = getattr(func, "__qualname__", getattr(func, "__name__", str(func)))

    @wraps(func)
    def wrapper(self, *a, **kw):
        pipe_to_png(self.pipeline, f"pre_{name}")
        try:
            ret = func(self, *a, **kw)
        except:
            pipe_to_png(self.pipeline, f"exc_{name}")
            raise
        finally:
            pipe_to_png(self.pipeline, f"ret_{name}")
        return ret

    return wrapper


@traced(logger.trace)
def appsrc_emit(appsrc: Gst.Element, signal: str, *a, **kw):
    ret = appsrc.emit(signal, *a, **kw)
    return ret


def set_state(
    element: Gst.Element,
    state: Gst.State,
    async_timeout: Optional[int] = Gst.CLOCK_TIME_NONE,
    raise_on_error: bool = True,
):
    response = element.set_state(state)

    if (async_timeout is not None) and (
        response == Gst.StateChangeReturn.ASYNC
    ):
        response = element.get_state(async_timeout)

    if raise_on_error and (response == Gst.StateChangeReturn.FAILURE):
        raise RuntimeError(f"FAILED changing {element.name} to {state}")
    return response


def profile(func):
    import cProfile
    import pstats

    @wraps(func)
    def wrapped(*a, **kw):
        profiler = cProfile.Profile()
        profiler.enable()
        ret = func(*a, **kw)
        profiler.disable()
        stats = pstats.Stats(profiler).sort_stats("tottime")
        stats.print_stats()
        return ret

    return wrapped
