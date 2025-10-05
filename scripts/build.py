"""Build an distribution for publishing package to PyPi."""

from __future__ import annotations

import subprocess
from pathlib import Path
from platform import system

assert system() in ("Darwin", "Linux")

ROOT = Path() / "../"
LOCAL_LIBRARY_DIRECTORY = ROOT / "lib"
DIST_LIBRARY_DIRECTORY = ROOT / "gofra" / "_distlib"


def exec(*cmd: str | Path) -> None:  # noqa: A001
    subprocess.run(
        list(map(str, cmd)),
        check=True,
    )


exec("cp", "-r", LOCAL_LIBRARY_DIRECTORY, DIST_LIBRARY_DIRECTORY)
exec("poetry", "build")
exec("find", DIST_LIBRARY_DIRECTORY, "-name", "*.gof", "-type", "f", "-delete")
exec("find", DIST_LIBRARY_DIRECTORY, "-type", "d", "-delete")
