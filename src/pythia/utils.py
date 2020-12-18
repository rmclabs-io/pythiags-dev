# -*- coding: utf-8 -*-
""""""

import tempfile
import os
import sys

class Capture:
    def start(self):
        self._old_stderr = sys.__stderr__
        self._stderr_fd = self._old_stderr.fileno()
        self._saved_stderr_fd = os.dup(self._stderr_fd)
        self._file_err = sys.stderr = tempfile.TemporaryFile(mode="w+t")
        os.dup2(self._file_err.fileno(), self._stderr_fd)

        self._old_stdout = sys.stdout
        self._stdout_fd = self._old_stdout.fileno()
        self._saved_stdout_fd = os.dup(self._stdout_fd)
        self._file_out = sys.stdout = tempfile.TemporaryFile(mode="w+t")
        os.dup2(self._file_out.fileno(), self._stdout_fd)

    def stop(self):
        os.dup2(self._saved_stdout_fd, self._stdout_fd)
        os.close(self._saved_stdout_fd)
        sys.stdout = self._old_stdout
        self._file_out.seek(0)
        out = self._file_out.readlines()
        self._file_out.close()

        os.dup2(self._saved_stderr_fd, self._stderr_fd)
        os.close(self._saved_stderr_fd)
        sys.stderr = self._old_stderr
        self._file_err.seek(0)
        err = self._file_err.readlines()
        self._file_err.close()
        return out, err

    @classmethod
    def capture_output(cls, callable_, *a, **kw):
        c = cls()
        c.start()
        result = callable_(*a, **kw)
        out, err = c.stop()
        return out, err, result
