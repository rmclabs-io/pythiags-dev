#!/usr/bin/env python3
"""Docker builder and runner."""

import argparse
import datetime
import platform
import subprocess as sp
import sys
from pathlib import Path
from shlex import join
from shlex import split

PROJECT_ROOT = Path(__file__).parents[1]
EPILOG = "Additional arguments are forwarded to the 'docker{cmd}' command"

DOCKER_BUILD = """
{docker_build}
  -t {tag}
  -f {file}
  --build-arg BASE_IMG={BASE_IMG}
  --build-arg BUILD_DATE={BUILD_DATE}
  --build-arg VCS_REF={VCS_REF}
  --build-arg BUILD_VERSION={BUILD_VERSION}
  --build-arg PYTHIA_TAG={PYTHIA_TAG}{extra}
  {path}
"""
# --build-arg PIP_PLATFORM={PIP_PLATFORM}

DOCKER_RUN = """
docker run
  --rm
  -it
  -v /tmp/.X11-unix:/tmp/.X11-unix
  -e DISPLAY{extra}{entrypoint}
  {tag}{cmd}
"""

TRT_OSS = r"""
bash -c "\
docker run \
  -it \
  --rm \
  --gpus=all \
  --name={container} \
  -v {pwd}/docker/trt-oss-install.sh:/tmp/entrypoint \
  -v {pwd}/trt-docker-export:/docker-export \
  --entrypoint /tmp/entrypoint \
  nvcr.io/nvidia/deepstream:6.1.1-devel
"
""".format(
    pwd=PROJECT_ROOT, container="trt-oss-installer"
)

COMMANDS = {
    "build": DOCKER_BUILD,
    "run": DOCKER_RUN,
    "check-ds": DOCKER_RUN,
    "trt": TRT_OSS,
}


GET_VCS_REF_CMD = r"""
  git describe \
    --tags \
    --no-match \
    --always \
    --abbrev=40 \
    --dirty \
  | sed -E 's/^.*-g([0-9a-f]{40}-?.*)$/\1/'
"""

GET_DEFAULT_VERSION_CMD = r"""
  git describe \
    --tags \
    --no-match \
    --always \
    --abbrev=40 \
    --dirty \
  | sed -E 's/(^.*)-[0-9a-f]*-g([0-9a-f]{40}-?.*)$/\1-\2/'
"""

GET_BUILD_REF_CMD = """
  git describe
    --tags
    --match XXXXXXX
    --always
    --abbrev=40
    --dirty
"""

DOCKER_BUILDX_BUILD = """docker buildx build
  --build-arg BUILDKIT_INLINE_CACHE=1
  --load\
"""

CHECK_NVINFER = "gst-inspect-1.0 nvinfer &> /tmp/err.log"

CHECK_PYTHIA = """python -c '
from gi.repository import Gst
import pyds
import pythia
' &> /tmp/err.log"""

CHECK_DS_CMD = f"""
  -c "{CHECK_NVINFER} \
    && {CHECK_PYTHIA} \
    && echo 'Success!' \
    || cat /tmp/err.log"
"""


def _get_arch() -> str:
    return platform.uname()[4]


def _get_vcs_ref():
    return sp.check_output(GET_VCS_REF_CMD, shell=True, text=True).strip()


def _get_default_version():
    return sp.check_output(
        GET_DEFAULT_VERSION_CMD, shell=True, text=True
    ).strip()


def _get_build_ref():
    return sp.check_output(  # noqa: S603
        split(GET_BUILD_REF_CMD), text=True
    ).strip()


def add_common_args(parser) -> None:
    default_arch = _get_arch()
    default_target = "prod"

    dummy = argparse.ArgumentParser(
        description="dummy",
        add_help=False,
    )
    for parser_ in (parser, dummy):
        parser_.add_argument(
            "--arch",
            default=default_arch,
            choices=["aarch64", "x86_64"],
            help=(
                "Set the target build stage to build."
                f" Defaults to '{default_arch}'"
                " (varies depending on architecture)"
            ),
        )
        parser_.add_argument(
            "--target",
            default=default_target,
            choices=["prod", "dev", "build", "dev-code", "common"],
            help=(
                "Set the target build stage to build."
                f" Defaults to '{default_target}'"
            ),
        )
    aux_args, _ = dummy.parse_known_args()

    default_tag = "ghcr.io/rmclabs-io/pythia{arch}{target}:{version}".format(  # noqa: C0209, C0301
        version=_get_default_version(),
        target=(aux_args.target != "prod") and f"-{aux_args.target}" or "",
        arch=(aux_args.arch != "x86_64") and "-l4t" or "",
    )

    parser.add_argument(
        "--tag",
        default=default_tag,
        help=(
            "Name and optionally a tag in the 'name:tag' format. "
            f"Default: '{default_tag}'"
            " (varies depending on architecture and git status)"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the docker command instead of running it",
    )


def _entrypoint(entrypoint: str) -> str:
    if not entrypoint:
        return ""
    return f"\n  --entrypoint {entrypoint}"


def _cmd(cmd: str) -> str:
    if not cmd:
        return ""
    return f"\n  {cmd}"


def get_args() -> argparse.Namespace:
    default_dockerfile = PROJECT_ROOT / "docker/Dockerfile"
    default_path = PROJECT_ROOT

    parser = argparse.ArgumentParser(
        description="pythia docker build and run script",
        epilog=EPILOG.format(cmd=""),
    )
    subparsers = parser.add_subparsers(
        help="which command to run",
        dest="command",
    )

    build_parser = subparsers.add_parser(
        "build",
        help="Build  the pythia docker image",
        epilog=EPILOG.format(cmd=" build"),
    )
    add_common_args(build_parser)
    build_parser.add_argument(
        "--file",
        "-f",
        default=default_dockerfile,
        type=Path,
        help=f"Name of the Dockerfile. Default: '{default_dockerfile}'",
    )
    build_parser.add_argument(
        "--path",
        default=default_path,
        type=Path,
        help=(
            "PATH to use for context when building docker image."
            f" Default: '{default_path}'."
        ),
    )
    build_parser.add_argument(
        "--buildx",
        "-x",
        action="store_true",
        default=False,
        help="Use docker buildx backend",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Run a command in a new pythia container",
        epilog=EPILOG.format(cmd=" run"),
    )
    run_parser.add_argument(
        "--entrypoint",
        default="",
        type=_entrypoint,
        help="Overwrite the default ENTRYPOINT.",
    )
    run_parser.add_argument(
        "cmd",
        default="",
        nargs="?",
        type=_cmd,
        help="Overwrite the default CMD.",
    )
    add_common_args(run_parser)

    check_parser = subparsers.add_parser(
        "check-ds",
        help="Check deepstream and python usability",
        epilog=EPILOG.format(cmd=" run"),
    )
    add_common_args(check_parser)

    _ = subparsers.add_parser(
        "trt",
        help="Build trt-oss for x86-64",
    )
    add_common_args(_)

    args, extra = parser.parse_known_args()

    args.BASE_IMG = (
        "nvcr.io/nvidia/deepstream{arch}:6.1.1-samples".format(  # noqa: C0209
            arch=(args.arch != "x86_64") and "-l4t" or ""
        )
    )

    args.extra = ("\n  " + "\n  ".join(extra)) if extra else ""
    if args.command == "build":
        if args.buildx:
            args.docker_build = DOCKER_BUILDX_BUILD
        else:
            args.docker_build = "docker build"

        args.BUILD_DATE = (
            datetime.datetime.now().replace(microsecond=0).isoformat()
        )
        args.VCS_REF = _get_vcs_ref()
        args.BUILD_VERSION = _get_build_ref()
        args.PYTHIA_TAG = args.tag
        args.extra += "\n  --platform=linux/{arch}".format(  # noqa: C0209
            arch=(args.arch != "x86_64") and "arm64" or "amd64",
        )
        args.extra += f"\n  --target={args.target}"
    elif args.command == "check-ds":
        args.extra += "\n  --gpus=all"
        args.entrypoint = "\n  --entrypoint=bash"
        args.cmd = f" {join(split(CHECK_DS_CMD))}"
    return args


def main() -> int:
    args = get_args()
    try:
        template = COMMANDS[args.command].strip("\n")
    except KeyError:
        print(f"Command must be one of: {list(COMMANDS)}")
        return 1

    args_dict = vars(args)
    dry_run = args_dict.pop("dry_run")
    command = template.format(**args_dict)

    if dry_run:
        print(command)
        return 0

    # command whitelisted via COMMANDS
    ret = sp.run(split(command), check=False).returncode  # noqa: S603
    Path(".CURRENT_TAG").write_text(args.tag, encoding="utf-8")
    return ret


if __name__ == "__main__":
    sys.exit(main())
