# noqa: INP001
"""Script for aliasing `gofra` (or whatever name) to gofra module for correct resolution.

This is probably at sometime migrate to package managers.
"""

import sys
from pathlib import Path

# Add the project root (gofra) to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from gofra.cli.entry_point import cli_entry_point  # noqa: E402

if __name__ == "__main__":
    cli_entry_point(prog="gofra")
