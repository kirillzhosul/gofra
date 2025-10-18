from __future__ import annotations

import sys
from pathlib import Path

from gofra.cli.output import cli_message


def cli_get_executable_program(
    *,
    override: str | None = None,
    warn_proper_installation: bool,
) -> str:
    executable = _get_executable_program(override=override)

    if warn_proper_installation and executable == "__main__.py":
        cli_message(
            "WARNING",
            "Running with prog == '__main__.py', consider proper installation!",
            verbose=True,  # TODO(@kirillzhosul): Consider proper propagation of verbose warnings.
        )

    return executable


def _get_executable_program(
    *,
    override: str | None = None,
) -> str:
    return override if override else Path(sys.argv[0]).name
