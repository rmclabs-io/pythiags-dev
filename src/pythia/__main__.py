"""Module allowing for `python -m pythia ...`."""


import sys

try:
    from pythia.cli.app import app
except ImportError:
    print(
        "pythia must be installed with its cli extra to run this script."
        "please install pythia[cli] and try again."
    )
    sys.exit(1)

if __name__ == "__main__":
    sys.exit(app())
