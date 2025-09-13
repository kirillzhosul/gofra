"""Execution helpers for filesystem binary files."""

from __future__ import annotations

import sys
from subprocess import run
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


def execute_binary_executable(
    filepath: Path,
    *,
    args: Iterable[str],
    timeout: float | None = None,
) -> int:
    """Execute given binary executable in an shell and return its exit code.

    :param filepath: Path to an executable
    :param args: Sequence of arguments to pass when executing
    :param timeout: Timeout in seconds
    :return: Exit code of an process
    :raises subprocess.TimeoutExpired: Timeout is expired
    """
    executable = filepath.absolute()

    process = run(  # noqa: S602
        (executable, *args),
        timeout=timeout,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        # Mostly, we want to execute with shell as less-abstracted real software
        shell=True,
        # Do not raise, we would do that by itself
        check=False,
        # Perform in current environment
        user=None,
        group=None,
        process_group=None,
    )

    return process.returncode
