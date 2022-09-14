"""Class defeinitions from pythia apps deisgned to be run from the cli."""
from typing import NoReturn

from pythia.applications.base import Application
from pythia.utils.message_handlers import on_message_eos
from pythia.utils.message_handlers import on_message_error


class CliApplication(Application):
    """Command-line application."""

    on_message_eos = on_message_eos

    def on_message_error(self, *args, **kwargs) -> NoReturn:
        """Print error and exit.

        Args:
            args: forwarded to :func:`on_message_error`.
            kwargs: forwarded to :func:`on_message_error`.

        Raises:
            RuntimeError: Always raises this error. You can wrap this in
                a try/except block to handle.

        """
        on_message_error(self, *args, **kwargs)
        self.stop()
        raise RuntimeError("Unhandled pipeline error")
