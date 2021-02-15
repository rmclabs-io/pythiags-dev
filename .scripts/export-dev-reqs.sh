#!/usr/bin/env bash
poetry export -vvv \
    --dev \
    --format requirements.txt \
    --without-hashes \
    --with-credentials \
    --extras ds --extras cli \
    --output requirements.dev.txt
