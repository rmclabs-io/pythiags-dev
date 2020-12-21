#!/usr/bin/env python
# -*- coding: utf-8 -*-
""""""

from pathlib import Path
from setuptools import find_packages
from setuptools import setup
from setuptools.command.install import install
from setuptools.command.develop import develop
from setuptools.command.egg_info import egg_info


def readme():

    with open(Path(__file__).parent / "README.md", encoding="utf-8") as f:
        long_description = f.read()
    return long_description


def install_pyds():
    try:
        from pip._internal import main
    except ImportError:
        from pip import main
    main(["install", "/opt/nvidia/deepstream/deepstream/lib/"])


class Install(install):
    def run(self):
        install_pyds()
        install.run(self)


class Develop(develop):
    def run(self):
        install_pyds()
        develop.run(self)


class EggInfo(egg_info):
    def run(self):
        install_pyds()
        egg_info.run(self)


setup(
    name="pythia",
    version="0.3.2",
    url="https://github.com/rmclabs-cl/pythia.git",
    author="Pablo Woolvett",
    author_email="pwoolvett@rmc.cl",
    description="Minimal demo to run Deepstream+Kivy on Jetson",
    long_description=readme(),
    long_description_content_type="text/markdown",
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=[
        "Cython >= 0.29.9",
        "PyGObject >= 3.36.0",
        "kivy >= 1.11.1",
        "pyds >= 1.0",
        "tqdm >= 4.54.1",
    ],
    setup_requires=[
        "setuptools >= 50",
    ],
    cmdclass={
        "install": Install,
        "develop": Develop,
        "egg_info": EggInfo,
    },
    entry_points={
        "console_scripts": [
            "pythia = pythia.__main__:main",
        ],
    },
)
