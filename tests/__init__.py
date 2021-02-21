import shlex
import subprocess as sp


def run_read_console(cmd, timeout=10):
    cmdarg = shlex.split(cmd)
    with sp.Popen(cmdarg, stdout=sp.PIPE, stderr=sp.PIPE) as p:
        try:
            code = p.wait(timeout=timeout)
            stdout = p.stdout
            stderr = p.stderr
            return code, stdout, stderr
        except:
            p.kill()
            p.wait()
            raise
