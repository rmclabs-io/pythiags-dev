#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""""""
import os
import sys
from contextlib import contextmanager
from ftplib import FTP
from ftplib import error_perm
from pathlib import Path


def mkdir_p(path, ftp):
    try:
        ftp.mkd(path)
    except error_perm as e:
        if not e.args[0].startswith(
            "550"
        ):  # ignore "directory already exists"
            raise


def upload(child, rel, ftp):
    cmd = f"STOR {rel}"
    print(cmd)
    with open(child, "rb") as fp:
        ftp.storbinary(cmd, fp)


def placeFiles(ftp: FTP, path: Path, root):

    mkdir_p(root, ftp)

    for child in path.glob("**/*"):
        rel = f"{root}/{child.relative_to(path)}"

        if child.is_dir():
            mkdir_p(rel, ftp)

        elif child.is_file():
            upload(child, rel, ftp)


def to_subfolder(image_name):
    return (
        image_name.replace("ghcr.io/rmclabs-io/pythia", "pythia")
        .replace("-arm64", "")  # eventually we-ll include non-jetson builds?
        .replace("-dev", "")  # we-re always publishing using the dev image
        .replace(":", "/")  # repo:tag => folder/subfolder
    )


def main(docs_build_root, image_name, passwd):
    host = "dev.rmclabs.io"
    user = "dev.pwoolvett@rmclabs.io"

    with FTP(
        host=host,
        user=user,
        passwd=passwd,
    ) as ftp:
        placeFiles(
            ftp,
            Path(docs_build_root).resolve(),
            to_subfolder(image_name),
        )


if __name__ == "__main__":
    main(*sys.argv[1:])
