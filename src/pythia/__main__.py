# -*- coding: utf-8 -*-
"""Main pythia entrypoint."""
from pythia import logger

try:
    import fire

    from pythia import cli
except ImportError as exc:
    msg = (
        "To use pythia in cli mode, pleas install `fire` first"
        ". Either as an extra for a local install:  `pip install .[cli]`"
        ", or as an extra from a remote repository:  `pip install git+https://github.com/rmclabs-io/pythia.git@main#egg=main[cli]`"
    )
    logger.error(msg)
    exit(1)

if __name__ == "__main__":
    import sys

    sys.argv[0] = "pythia"
    cli.main()
