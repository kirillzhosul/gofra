from collections.abc import Generator
from contextlib import contextmanager

from gofra.exceptions import GofraError

from .output import cli_message

DEBUG_UNWRAP_INTERNAL_ERRORS = True


@contextmanager
def cli_gofra_error_handler() -> Generator[None]:
    """Wrap function to properly emit Gofra internal errors."""
    try:
        yield
    except GofraError as ge:
        if DEBUG_UNWRAP_INTERNAL_ERRORS:
            cli_message("ERROR", repr(ge))
        else:
            raise
