"""Python entry point for development environment run with `python -m gofra.testkit`.

Should be exported as something like `gofra-testkit` system-wide.
"""

from .entry_point import cli_entry_point

if __name__ == "__main__":
    cli_entry_point()
