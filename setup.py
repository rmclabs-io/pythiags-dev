#!/usr/bin/env python
# -*- coding: utf-8 -*-
""""""

from pathlib import Path
from setuptools import find_packages
from setuptools import setup

def readme():
    
    with open(Path(__file__).parent / 'README.md', encoding='utf-8') as f:
        long_description = f.read()
    return long_description

setup(
    name="pythia",
    version="0.1.0",
    url="https://github.com/rmclabs-cl/pythia.git",
    author="Pablo Woolvett",
    author_email="pwoolvett@rmc.cl",
    description="Minimal demo to run Deepstream+Kivy on Jetson",
    long_description=readme(),
    long_description_content_type='text/markdown',
    package_dir={'': 'src'},
    packages=find_packages("src"),
    install_requires=[
        "Cython >= 0.29.9",
        "PyGObject >= 3.36.0",
        "kivy >= 1.11.1",
    ],
    entry_points = {
        'console_scripts': [
            'pythia = pythia.__main__:main',
        ],
    },
)
