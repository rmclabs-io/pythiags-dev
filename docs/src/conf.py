# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import shlex
import subprocess as sp  # noqa: S404
import sys
from datetime import datetime
from pathlib import Path

import importlib_metadata

year = datetime.now().year
version = importlib_metadata.version("pythiags")
# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

project = "pythiags"
copyright = f"{year}, RMC Labs"
author = "Pablo Woolvett"

# The full version, including alpha/beta/rc tags
release = f"{version}"


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.napoleon",
    "sphinx_rtd_theme",
    "m2r2",
]

source_suffix = [".rst", ".md"]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
html_logo = "_static/logo.png"
html_favicon = "_static/logo.png"
# hide sphinx footer
html_show_sphinx = False

# -- sphinx-theme options ---------------------------------------------------

html_theme_options = {
    "logo_only": True,
    "display_version": True,
    "prev_next_buttons_location": "bottom",
    "style_external_links": False,
    "vcs_pageview_mode": "",
    "style_nav_header_background": "white",
    # Toc options
    "collapse_navigation": True,
    "sticky_navigation": True,
    "navigation_depth": 4,
    "includehidden": True,
    "titles_only": False,
}


# -- autodoc config ---------------------------------------------------
autoclass_content = "both"

# -- napoleon config ---------------------------------------------------
# See https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html#getting-started
napoleon_google_docstring = True
# napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
# napoleon_include_special_with_doc = True
# napoleon_use_admonition_for_examples = False
# napoleon_use_admonition_for_notes = False
# napoleon_use_admonition_for_references = False
# napoleon_use_ivar = False
# napoleon_use_param = True
# napoleon_use_rtype = True
# napoleon_type_aliases = None
# napoleon_attr_annotations = True


def run_apidoc(_):
    root_dir = Path(__file__).parents[2].resolve()
    templates = root_dir / "docs/src/templates"
    apidoc = root_dir / "docs/src/apidoc"
    package = root_dir / "src/pythiags"
    sphinx_apidoc = Path(sys.executable).parent / "sphinx-apidoc"

    sp.check_call(  # noqa: S603
        shlex.split(
            f"""
        {sphinx_apidoc}
        --templatedir={templates}
        --separate
        --module-first
        --force
        -o {apidoc}
        {package}
    """
        )
    )


def setup(app):
    app.connect("builder-inited", run_apidoc)
