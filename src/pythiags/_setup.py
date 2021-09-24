import logging
import os
import sys
from functools import partial
from pathlib import Path
from random import randint

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = list(range(8))

# These are the sequences need to get colored ouput
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"

COLORS = {
    "TRACE": MAGENTA,
    "WARNING": YELLOW,
    "INFO": GREEN,
    "DEBUG": CYAN,
    "CRITICAL": RED,
    "ERROR": RED,
}


def formatter_message(message, use_color=True):
    if use_color:
        message = message.replace("$RESET", RESET_SEQ)
        message = message.replace("$BOLD", BOLD_SEQ)
    else:
        message = message.replace("$RESET", "").replace("$BOLD", "")
    return message


use_color = (
    os.environ.get("WT_SESSION")
    or os.environ.get("COLORTERM") == "truecolor"
    or os.environ.get("PYCHARM_HOSTED") == "1"
    or os.environ.get("TERM")
    in (
        "rxvt",
        "rxvt-256color",
        "rxvt-unicode",
        "rxvt-unicode-256color",
        "xterm",
        "xterm-256color",
    )
) and os.environ.get("KIVY_BUILD") not in ("android", "ios")

# No additional control characters will be inserted inside the
# levelname field, 7 chars will fit "WARNING"
# levelname field width need to take into account the length of the
# color control codes (7+4 chars for bold+color, and reset)
bracket_len = 7 if not use_color else 18

color_fmt = formatter_message(
    f"[%(levelname)-{bracket_len}s] %(message)s", use_color
)


class ColoredFormatter(logging.Formatter):
    def __init__(self, msg, use_color=True):
        logging.Formatter.__init__(self, msg)
        self.use_color = use_color

    def format(self, record):
        try:
            msg = record.msg.split(":", 1)
            msglen = len(msg)
            if msglen == 1:
                path = record.pathname
                info = record.module
                try:
                    info = {
                        getattr(module, "__file__", None): name
                        for name, module in sys.modules.items()
                    }[record.pathname]
                except:
                    pass
                record.msg = "[%-12s] %s" % (info, msg[0])
            if msglen == 2:
                record.msg = "[%-12s]%s" % (msg[0], msg[1])
        except:
            pass
        levelname = record.levelname
        if record.levelno == logging.TRACE:
            levelname = "TRACE"
            record.levelname = levelname
        if self.use_color and levelname in COLORS:
            levelname_color = (
                COLOR_SEQ % (30 + COLORS[levelname]) + levelname + RESET_SEQ
            )
            record.levelname = levelname_color
        return logging.Formatter.format(self, record)


FORMATTER = ColoredFormatter(color_fmt, use_color=use_color)


def build_logger(log_level):
    """Logger object.

    Taken from kivy.logger, without files support.

    """

    previous_stderr = sys.stderr

    logging.TRACE = 9
    LOG_LEVELS = {
        "trace": logging.TRACE,
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    class ConsoleHandler(logging.StreamHandler):
        def filter(self, record):
            try:
                msg = record.msg
                k = msg.split(":", 1)
                if k[0] == "stderr" and len(k) == 2:
                    previous_stderr.write(k[1] + "\n")
                    return False
            except:
                pass
            return True

    def logger_config_update(section, key, value):
        if LOG_LEVELS.get(value) is None:
            raise AttributeError("Loglevel {0!r} doesn't exists".format(value))
        Logger.setLevel(level=LOG_LEVELS.get(value))

    #: Pythiags default logger instance
    Logger = logging.getLogger("pythiags")
    Logger.trace = partial(Logger.log, logging.TRACE)
    Logger.fixme = partial(Logger.log, logging.DEBUG)

    # set the Pythiags logger as the default
    logging.root = Logger

    console = ConsoleHandler()
    console.setFormatter(FORMATTER)
    Logger.addHandler(console)

    Logger.setLevel(level=LOG_LEVELS.get(log_level))

    return Logger


def patch_kivy_no_args():
    try:
        import kivy

        # HACK: until https://github.com/kivy/kivy/pull/7326 lands
        # Although here we revert it by default to shush kivy
        # <pwoolvett 2021-01-12T16:31>
        TRUTHY = {"true", "1", "yes"}
        os.environ.setdefault("KIVY_NO_ARGS", "true")
        if os.environ["KIVY_NO_ARGS"] not in TRUTHY:
            del os.environ["KIVY_NO_ARGS"]
        # END HACK
    except ImportError:
        pass


def set_log_level():

    _pythia_env_log_level = os.environ.get("PYTHIAGS_LOG_LEVEL", None)
    if _pythia_env_log_level:
        os.environ["KCFG_KIVY_LOG_LEVEL"] = _pythia_env_log_level
    else:
        os.environ.setdefault("KCFG_KIVY_LOG_LEVEL", "info")

    pythiags_log_level = os.environ["KCFG_KIVY_LOG_LEVEL"]
    return pythiags_log_level


def get_kivy_logger_or_build(log_level):
    try:
        import kivy

        try:
            console_handler = dict(
                map(
                    lambda handler: (type(handler), handler),
                    kivy.Logger.handlers,
                )
            )[kivy.logger.ConsoleHandler]

            console_handler.setFormatter(FORMATTER)
        except:
            pass
        logger = kivy.Logger
    except ImportError:
        logger = build_logger(log_level)
        logger.debug("Using custom pyds logger based on kivy's.")
    return logger


PYTHIAGS_LOG_LEVEL = set_log_level()
logger = get_kivy_logger_or_build(PYTHIAGS_LOG_LEVEL)


# try:
#     import kivy

#     try:
#         console_handler = dict(
#             map(lambda handler: (type(handler), handler), kivy.Logger.handlers)
#         )[kivy.logger.ConsoleHandler]

#         console_handler.setFormatter(FORMATTER)
#     except:
#         pass
#     logger = kivy.Logger
# except ImportError:
#     logger = build_logger()
#     logger.debug("Using custom pyds logger based on kivy.")


try:
    import importlib.metadata as importlib_metadata
except ModuleNotFoundError:
    import importlib_metadata

import pythiags

version = importlib_metadata.version(__package__)
logger.info(f"PythiaGs: version {version}")
logger.info(f"PythiaGs: Installed at '{Path(pythiags.__file__).parent}'")
