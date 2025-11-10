import sys
from collections.abc import Generator
from contextlib import contextmanager
from subprocess import CalledProcessError
from typing import NoReturn

from gofra.cli.output import cli_message
from gofra.exceptions import GofraError


@contextmanager
def cli_gofra_error_handler(
    *,
    debug_user_friendly_errors: bool = True,
) -> Generator[None, None, NoReturn]:
    """Wrap function to properly emit Gofra internal errors."""
    try:
        yield
    except GofraError as ge:
        if debug_user_friendly_errors:
            cli_message("ERROR", repr(ge))
            return sys.exit(1)
        raise  # re-throw exception due to unfriendly flag set for debugging
    except CalledProcessError as pe:
        command = " ".join(pe.cmd)
        cli_message(
            "ERROR",
            f"""Command process with cmd: {command} failed with exit code {pe.returncode}""",
        )
        # Propagate exit code from called process
        return sys.exit(pe.returncode)

    # This is unreachable but error wrapper must fail
    cli_message("ERROR", "Bug in a CLI: error handler must has no-return")
    sys.exit(1)
