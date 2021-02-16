# -*- coding: utf-8 -*-
"""Main pythiags entrypoint."""
from pythiags import logger

try:
    import fire

    from pythiags import cli
except ImportError as exc:
    msg = (
        "To use pythiags in cli mode, pleas install `fire` first"
        ". Either as an extra for a local install:  `pip install .[cli]`"
        ", or as an extra from a remote repository:  `pip install git+https://github.com/rmclabs-io/pythiags.git@main#egg=main[cli]`"
    )
    logger.error(msg)
    exit(1)

if __name__ == "__main__":
    import sys

    sys.argv[0] = "pythiags"
    cli.main()
