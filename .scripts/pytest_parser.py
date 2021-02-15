#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""""""

import sys
import xml.etree.ElementTree as ET


def parse_pytest(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()
    data = [*root][0].attrib
    try:
        return f"{(int(data['tests']) - (int(data['errors']) + int(data['failures']) + int(data['skipped'])) )/ int(data['tests']):.0%}"
    except:
        return "Failing"


def parse_coverage(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()
    data = root.attrib
    try:
        return f"{float(data['line-rate']):.0%}"
    except:
        return "Failing"


if __name__ == "__main__":
    opts = {
        "coverage": parse_coverage,
        "pytest": parse_pytest,
    }
    print(opts[sys.argv[1]](sys.argv[2]))
