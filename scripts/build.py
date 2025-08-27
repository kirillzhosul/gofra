# noqa: INP001
"""Build an distrubution for publishing package to PyPi."""

import subprocess
from pathlib import Path

ROOT = Path() / "../"
LOCAL_LIBRARY_DIRECTORY = ROOT / "lib"
DIST_LIBRARY_DIRECTORY = ROOT / "gofra" / "_distlib"


subprocess.run(  # noqa: S603
    ["cp", "-r", str(LOCAL_LIBRARY_DIRECTORY), str(DIST_LIBRARY_DIRECTORY)],  # noqa: S607
    check=True,
)
subprocess.run(  # noqa: S603
    ["poetry", "build"],  # noqa: S607
    check=True,
)
