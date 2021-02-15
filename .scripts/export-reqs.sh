#!/usr/bin/env bash
poetry export -vvv \
    --format requirements.txt \
    --without-hashes \
    --with-credentials \
    --extras ds --extras cli \
    --output requirements.txt
