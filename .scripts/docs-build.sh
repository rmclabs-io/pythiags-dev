#!/usr/bin/env bash

# exit when any command fails
set -e

export KIVY_DOC=1

# keep track of the last executed command
trap 'last_command=$current_command; current_command=$BASH_COMMAND' DEBUG
# echo an error message before exiting
trap 'echo "\"${last_command}\" command filed with exit code $?."' EXIT

ref=${GITHUB_REF:-`git describe --tags --exact-match 2> /dev/null || git symbolic-ref -q --short HEAD || git rev-parse --short HEAD`}

clean_docs() {
  git clean \
    -fdi \
    docs/src

  rm -rf docs/build/$ref
}


source_docs() {
  sphinx-apidoc \
    --separate \
    --module-first \
    --force \
    -o docs/src \
    src/pythia
}


build_docs() {
  sphinx-build \
    -a \
    -E \
    -j auto \
    docs/src \
    docs/build
}

clean_docs
build_docs
