"""Entry point for CLI.

Only for calling via `python -m gofra`, which is considered as bad practice.
"""

from gofra.cli.main import cli_entry_point

if __name__ == "__main__":
    cli_entry_point()
