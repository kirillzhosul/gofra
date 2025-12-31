"""Execution helpers for filesystem binary files."""

from __future__ import annotations

import sys
from subprocess import CompletedProcess, run
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


def execute_binary_executable(  # noqa: PLR0913
    filepath: Path,
    *,
    args: Iterable[str],
    timeout: float | None = None,
    stdin: TextIO | int = sys.stdin,
    stdout: TextIO | int = sys.stdout,
    stderr: TextIO | int = sys.stderr,
) -> CompletedProcess[bytes]:
    """Execute given binary executable in an shell and return its exit code.

    :param filepath: Path to an executable
    :param args: Sequence of arguments to pass when executing
    :param timeout: Timeout in seconds
    :return: Exit code of an process
    :raises subprocess.TimeoutExpired: Timeout is expired
    """
    executable = filepath.absolute()

    return run(  # noqa: S602
        (executable, *args),
        timeout=timeout,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        # Mostly, we want to execute with shell as less-abstracted real software
        shell=True,
        # Do not raise, we would do that ourselves
        check=False,
        # Perform in current environment
        user=None,
        group=None,
        process_group=None,
    )
