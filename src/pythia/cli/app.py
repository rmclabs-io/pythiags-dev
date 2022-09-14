"""Command-line interfact typer application for pythia.

Its a typer application mimmicking `gst-launch`.

"""
from __future__ import annotations

import enum
import re
import sys
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any
from typing import Callable
from typing import cast
from typing import Collection
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import typer
from fire import decorators
from fire.core import _MakeParseFn

from pythia import __version__
from pythia.applications.command_line import CliApplication
from pythia.exceptions import InvalidPipelineError
from pythia.pipelines.base import UNABLE_TO_PLAY_PIPELINE
from pythia.types import PadDirection
from pythia.types import Probes
from pythia.utils.ext import import_from_str
from pythia.utils.gst import GLib
from pythia.utils.gst import Gst
from pythia.utils.gst import gst_init

LOOKS_LIKE_JINJA_WARN = (
    "It looks like you're attemplting to use a pipeline using jinja syntax,"
    " but jinja is not installed."
    " Falling back to native python renderer."
    " Please reinstall pythia with jinja extra"
    " (eg 'pip install pythia[jinja]')"
)


class Exit(enum.Enum):
    """Pythia cli exit wrapper."""

    INVALID_PIPELINE = 2
    INVALID_EXTRACTION = 3
    EXTRACTION_NOT_BOUND = 4
    UNPLAYABLE_PIPELINE = 5

    def __call__(self, exc) -> typer.Exit:

        print(traceback.format_exc())
        typer.secho(
            str(exc),
            fg="red",
        )
        return typer.Exit(self.value)


app = typer.Typer(
    add_completion=False,
)


def version_callback(value: bool) -> None:  # noqa: FBT001
    """Echo pythia version and exit.

    Args:
        value: If set, echos pythia version and exit.

    Raises:
        Exit: when value is passed, to exit the program.

    """
    if value:
        typer.echo(__version__)
        raise typer.Exit()


def pipe_from_file(path: Path) -> str:
    """Read a gst-launch-like pipeline from a file.

    Args:
        path: Location of the pipeline. If set to `Path("-")`, reads
            from stdin instead.

    Returns:
        The pipeline string.

    """
    if path == Path("-"):
        return sys.stdin.read()
    return path.read_text()


def pipe_from_parts(parts: Collection[str]) -> str:
    """Join `sys.argv`-split strings wuith spaces.

    Args:
        parts: Strings to be joined.

    Returns:
        The strings, joined with simple spaces.

    """
    raw = " ".join(parts)
    return raw


class Mode(str, enum.Enum):
    """Pipeline template loading from cli."""

    FILE = "FILE"
    """Pipeline template from file."""

    ARGV = "ARGV"
    """Pipeline template from argv."""


def define_template(
    ctx,
    pipeline_file: Optional[Path],
    pipeline_parts: Optional[List[str]],
) -> Tuple[Mode, str]:
    """Construct a pipeline template wither from a file or its parts.

    Args:
        ctx: click application context - used to print help on incorrect
            usage.
        pipeline_file: path to a nonempty file with a `gst-launch`-like
            pipeline as its contents.
        pipeline_parts: console-split sections of a pipeline, eg as
            received from `sys.argv`.

    Returns:
        The pipeline template as a string.

    Raises:
        Abort: Either both or none of the exclusive (pipeline_file,
            pipeline_parts) was supplied.

    Either `pipeline_file` or `pipeline_parts` must be passed.

    """

    if pipeline_file and not pipeline_parts:
        try:
            return Mode.FILE, pipe_from_file(pipeline_file)
        except FileNotFoundError as exc:
            typer.secho(
                f"Pipeline file '{str(pipeline_file)}' not found.",
                fg="red",
            )
            raise typer.Abort() from exc

    if pipeline_parts and not pipeline_file:
        return Mode.ARGV, pipe_from_parts(pipeline_parts)

    typer.secho(
        "Pass either a pipeline file or use gst-launch syntax, exclusively.",
        fg="red",
    )
    typer.echo(ctx.get_help())
    raise typer.Abort()


def _receive_any_return_kw(*_, **kw):
    return kw


CtxRetType = Tuple[List[str], Dict[str, Any]]


def parse_arbitrary_argv(
    component: Callable,
    args: List[str],
) -> CtxRetType:
    """Parse arguments into positional and named according to a function.

    Args:
        component: function to supply param spec and metadata.
        args: list of positional arguments to parse.

    Returns:
        Positional arguments.
        Named value pairs dictionary extracted from the input arg list.

    Examples:
        >>> def asdf()

    See Also:
        :func:`fire.core._Fire` and its call to
        :func:`fire.core._CallAndUpdateTrace`

    """
    parse = _MakeParseFn(component, decorators.GetMetadata(component))
    (parts, kwargs), *_ = parse(args)
    return parts, kwargs


def _ctx_cb() -> CtxRetType:
    return parse_arbitrary_argv(_receive_any_return_kw, sys.argv[1:])


Renderer = Callable[[str, Dict[str, Any]], str]


def _native_renderer(pipeline_template: str, context: dict) -> str:
    ret = pipeline_template
    found = {}
    for required in re.findall(r"(?<=\{).*?(?=\})", pipeline_template):

        found[required] = context.pop(
            required, context.pop(required.replace("-", "_"))
        )

    ret = ret.format_map(found)
    return ret


def _jinja_renderer(pipeline_template: str, context: dict) -> str:
    from jinja2 import meta  # noqa: C0415
    from jinja2 import Template  # noqa: C0415

    jinja_template = Template(pipeline_template)
    all_required = meta.find_undeclared_variables(
        jinja_template.environment.parse(pipeline_template)
    )

    found = {}
    for required in all_required:
        found[required] = context.pop(required)

    return jinja_template.render(found)


def choose_renderer(pipeline_template: str) -> Renderer:
    """Decide wether to use jinja or vanilla python template.

    If the syntax is detected as jinja but its not installed, issue a
    warning and fall back to native python.

    Args:
        pipeline_template: Inspected to decide its underlying syntax.

    Returns:
        One of the available template renderers - :func:`_native_renderer`
            or :func:`_jinja_renderer`.

    """
    looks_like_jinja = "{{" in pipeline_template
    try:
        import jinja2  # noqa: F401
    except ImportError:
        if looks_like_jinja:
            typer.secho(LOOKS_LIKE_JINJA_WARN, fg="yellow")
        return _native_renderer
    else:
        return _jinja_renderer if looks_like_jinja else _native_renderer


def build_pipeline(
    pipeline_parts: Optional[List[str]],
    pipeline_file: Optional[Path],
    ctx: typer.Context,
    *,
    extra_ctx: Optional[CtxRetType],
) -> str:
    """Construct a pipeline either from args or file.

    Args:
        pipeline_parts: console-split sections of a pipeline, eg as
            received from `sys.argv`.
        pipeline_file: Location to read the template pipieline from.
        ctx: typer context - used to print app help in case of problems.
        extra_ctx: Additional context to render the pipeline template.

    Returns:
        The pipeline (either args or from file), parsed as a template,
        then injected with the additional context (if any).

    """
    if extra_ctx is None:
        template_context: Dict[str, Any] = {}
    else:
        pipeline_parts, template_context = extra_ctx
    _, pipeline_template = define_template(ctx, pipeline_file, pipeline_parts)
    render_backend = choose_renderer(pipeline_template)

    return render_backend(pipeline_template, template_context)


def _validate_pipeline(pipeline_string: str, *, check: bool = True) -> int:
    typer.echo(f"Pipeline:\n```gst\n{pipeline_string}\n```")

    if not check:
        return 0

    gst_init()

    try:
        Gst.parse_launch(pipeline_string)
    except GLib.Error as exc:
        typer.secho(
            f"Invalid pipeline - reason: {exc}",
            fg="red",
        )
        return 1
    else:
        typer.secho(
            "Pipeline syntax looks good",
            fg="green",
        )
        return 0


EXTRACTOR_PARSER = (
    r"^(?P<module>\/?\w[\w_-]*(?:[\.\/]\w[\w_-]*)*?(?P<suffix>\.py)?)"
    r":"
    r"(?P<probe>\w[\w_]*)"
    r"@"
    r"(?P<element>\w[\w_-]*)"
    r"\."
    r"(?P<direction>src|sink)"
    r"$"
)


def _validate_extractors(extractor: Optional[List[str]]) -> Probes:
    if not extractor:
        return {}
    parser_re = re.compile(EXTRACTOR_PARSER, flags=re.MULTILINE)
    probes: Probes = defaultdict(lambda: defaultdict(list))
    for extractor_string in extractor:
        match = parser_re.match(extractor_string)
        if not match:
            raise ValueError(
                f"Unable to parse extractor '{extractor_string}'."
                " Make sure it has the form "
                "'my_module:my_function@element-name.pad-direction'."
            )
        data = match.groupdict()
        try:
            module = import_from_str(data["module"], suffix=data["suffix"])
        except ImportError as exc:
            raise ValueError(
                f"Unable to import module from extractor '{extractor_string}'."
                " Make sure it exists, and is importable."
            ) from exc
        try:
            raw_probe = getattr(module, data["probe"])
        except (KeyError, NameError) as exc:
            raise ValueError(
                "Unable to get probe from imported module: "
                f"'{extractor_string}'."
                " Make sure the function is available in the it's namespace."
            ) from exc
        direction = cast(PadDirection, data["direction"])
        probes[data["element"]][direction].append(raw_probe)
    return probes


@app.command(
    context_settings={
        "ignore_unknown_options": True,
    },
    help="gst-launch on steroids - use without caution.",
)
def main(  # noqa: C0116, R0913
    ctx: typer.Context,
    extra_ctx: Optional[str] = typer.Option(  # noqa: B008
        None,
        callback=_ctx_cb,
        is_eager=True,
        help="extra kw.",
    ),
    pipeline_parts: Optional[List[str]] = typer.Argument(  # noqa: B008
        None,
        help=(
            "A gstreamer pipeline, as used with vanilla gst-launch. For "
            "example: `videotestsrc ! identity eos-after=5 ! fakesink`."
            " Can be empty, in which case the `-p` flag *must* be passed"
            " to load a pipeline form file."
        ),
    ),
    pipeline_file: Optional[Path] = typer.Option(  # noqa: B008
        None,
        "--pipeline-file",
        "-p",
        help=(
            "Load pipeline from a path instead."
            " You can use '-' to read from stdin."
        ),
        envvar="PYTHIA_PIPELINE_FILE",
    ),
    extractor: Optional[List[str]] = typer.Option(  # noqa: B008
        None,
        "--probe",
        "-x",
        help=(
            "Install metadata extraction buffer probe in a gst pad."
            " The syntax must be: 'my_module:my_function@pgie.src'."
        ),
        envvar="PYTHIA_EXTRACTOR",
    ),
    _: Optional[bool] = typer.Option(  # noqa: B008
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
    dry_run: bool = typer.Option(  # noqa: B008,FBT001
        False,
        "--dry-run",
        help="Show the resulting pipeline and exit.",
    ),
    check: bool = typer.Option(  # noqa: B008,FBT001
        False,
        "--check",
        help=(
            "If set, validates the pipeline with Gst."
            " Only used with '--dry-run', otherwise ignored."
        ),
    ),
) -> None:

    pipeline_string = build_pipeline(
        pipeline_parts,
        pipeline_file,
        ctx,
        extra_ctx=cast(CtxRetType, extra_ctx),
    )

    if dry_run:
        retcode = _validate_pipeline(pipeline_string, check=check)
        raise typer.Exit(retcode)

    try:
        extractors = _validate_extractors(extractor)
    except (ImportError, ValueError, AttributeError) as exc:
        raise Exit.INVALID_EXTRACTION(exc) from exc

    try:
        gst_init()
        run = CliApplication.from_pipeline_string(pipeline_string, extractors)
    except NameError as exc:
        raise Exit.EXTRACTION_NOT_BOUND(exc) from exc
    except InvalidPipelineError as exc:
        raise Exit.INVALID_PIPELINE(exc) from exc
    try:
        run()
    except RuntimeError as exc:
        if UNABLE_TO_PLAY_PIPELINE in str(exc):
            raise Exit.UNPLAYABLE_PIPELINE(exc) from exc
        raise


if __name__ == "__main__":
    app()
