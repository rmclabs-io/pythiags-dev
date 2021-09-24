import json
import re
import shlex
import subprocess as sp
from pathlib import Path


def run_read_console(cmd, timeout=10):
    cmdarg = shlex.split(cmd)
    with sp.Popen(
        cmdarg, stdout=sp.PIPE, stderr=sp.PIPE
    ) as p:  # FIXME use redirect instead
        try:
            code = p.wait(timeout=timeout)
            stdout = p.stdout
            stderr = p.stderr
            return (
                code,
                stdout.read().decode("utf8"),
                stderr.read().decode("utf8"),
            )
        except:
            p.kill()
            p.wait()
            raise


def video_stats(videopath: Path):
    """Requires ffprobe."""
    code, stdout, stderr = run_read_console(
        f"ffprobe -v quiet -print_format json -show_format {videopath}"
    )
    assert not code, f"ffprobe exited with code != 0.\n{stderr}\n{stdout}"
    data = json.loads(stdout)
    return data["format"]
