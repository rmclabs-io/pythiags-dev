#!/usr/bin/env bash
export POETRY_URL=https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py
export POETRY_INSTALL_SCRIPT=/get-poetry.py

wget $POETRY_URL -O $POETRY_INSTALL_SCRIPT \
    && python3 $POETRY_INSTALL_SCRIPT --no-modify-path --yes
