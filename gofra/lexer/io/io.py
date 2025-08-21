from collections.abc import Generator
from pathlib import Path
from typing import IO

from .exceptions import IOFileDoesNotExistsError, IOFileNotAnFileError


def open_source_file_line_stream(path: Path) -> Generator[str]:
    """Open IO for an text file with Gofra source code and yield each line from it until it ends.

    :raises IOFileDoesNotExistsError: File does not exists
    :raises IOFileNotAnFileError: File is not an file
    """
    with open_source_file(path) as io:
        while line := io.readline(-1):
            yield line


def open_source_file(path: Path) -> IO[str]:
    """Open IO for an text file with Gofra source code.

    :raises IOFileDoesNotExistsError: File does not exists
    :raises IOFileNotAnFileError: File is not an file
    """
    if not path.exists(follow_symlinks=True):
        raise IOFileDoesNotExistsError(path=path)

    if not path.is_file():
        raise IOFileNotAnFileError(path=path)

    return path.open(
        mode="rt",
        buffering=-1,
        encoding="utf-8",
        errors="strict",
        newline=None,
    )
