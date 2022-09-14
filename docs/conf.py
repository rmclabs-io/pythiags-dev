#!/usr/bin/env python3
import os
import sys
from datetime import date
from pathlib import Path

from pythia import __version__

# region project meta
project = "pythia"
copyright = "{}, RMC Labs".format(date.today().year)
author = "pwoolvett"

version = __version__
release = version
# endregion project meta

# paths
_docs_src = Path(__file__).parent.resolve()
_templates = _docs_src / "templates"
_static_path = _docs_src / "_static"

_root_dir = _docs_src.parent
_package_src = _root_dir / "src/pythia"

# endregion paths

# extensions
extensions = [
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "myst_parser",
]
# endregion extensions

# sphinx setup
templates_path = [str(_templates.relative_to(_docs_src))]
source_suffix = [".rst", ".md"]
root_doc = "index"
language = "en"
exclude_patterns = []
# endregion sphinx setup

# html config
html_show_sphinx = False
html_theme = "furo"
html_static_path = [str(_static_path)]
html_logo = str(_static_path / "img/logo.png")
html_favicon = str(_static_path / "img/logo.png")
# endregion html config


# region autodoc config
autoclass_content = "both"
# endregion autodoc config

# region napoleon config
# See https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html#getting-started
napoleon_google_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = True
napoleon_preprocess_types = True
napoleon_attr_annotations = True
# region napoleon config


def run_apidoc(_) -> None:
    """Runs sphinx-apidoc when the builder is inited."""
    from sphinx.ext.apidoc import main as apidoc_exec

    exclude_patterns = (
        _package_src / "__main__.py",
        _package_src / "version.py",
    )
    apidoc_exec(
        [
            f"--templatedir={_templates}",
            "--separate",
            "--module-first",
            "--force",
            "--private",
            f"-o={_docs_src}",
            f"{_package_src}",
            *map(str, exclude_patterns),
        ]
    )


def setup(app) -> None:
    app.connect("builder-inited", run_apidoc)
