from __future__ import annotations

import sys
from pathlib import Path

from gofra.cli.output import cli_message


def cli_get_executable_program() -> str:
    """Get path to executable which is first argument (e.g `gofra ...`)."""
    return Path(sys.argv[0]).name


def warn_on_improper_installation(executable: str) -> None:
    """Warn if user is calling CLI as Python module, e.g __main__.py."""
    if not executable.endswith(".py"):
        return
    cli_message(
        level="WARNING",
        text=f"Running with prog == '{executable}', consider proper installation!",
        verbose=True,  # Treat as always verbose - as this cannot be inferred from configuration sources.
    )
