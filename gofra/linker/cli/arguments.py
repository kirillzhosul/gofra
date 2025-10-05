from __future__ import annotations

import sys
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path

from gofra.cli.helpers import cli_get_executable_program
from gofra.cli.output import cli_message
from gofra.linker.entry_point import LINKER_EXPECTED_ENTRY_POINT


@dataclass(frozen=True)
class CLIArguments:
    """Arguments from argument parser provided for whole Gofra testkit process."""

    files: list[Path]
    output: Path

    executable_entry_point_symbol: str


def parse_cli_arguments() -> CLIArguments:
    """Parse CLI arguments from argparse into custom DTO."""
    parser = _construct_argument_parser()
    args = parser.parse_args()

    files = [Path(path) for path in args.files]
    output = Path(args.output)

    if not files:
        cli_message(
            level="ERROR",
            text="No object files specified, has nothing to link",
        )
        sys.exit(1)

    return CLIArguments(
        files=files,
        output=output,
        executable_entry_point_symbol=args.executable_entry_point_symbol,
    )


def _construct_argument_parser() -> ArgumentParser:
    """Get argument parser instance to parse incoming arguments."""
    prog = cli_get_executable_program(override=None, warn_proper_installation=False)
    parser = ArgumentParser(
        description="Gofra LD - Linker command line interface for Gofra object files. Same linker is used with Gofra toolchain beside it is not called from shell, as `gofra-ld` being only interface for underlying linker API",
        add_help=True,
        usage=f"{prog} files... [options] [-o output_file]",
        allow_abbrev=False,
        prog=prog,
    )

    parser.add_argument(
        "files",
        help="Object files to link",
        nargs="*",
        default=[],
    )

    parser.add_argument(
        "-o",
        dest="output",
        help="Output file that is emitted by linker. Defaults to 'a.out'",
        default="a.out",
        required=False,
    )

    parser.add_argument(
        "-e",
        dest="executable_entry_point_symbol",
        help=f"Entry point symbol for executables. Defaults to '{LINKER_EXPECTED_ENTRY_POINT}'",
        default=LINKER_EXPECTED_ENTRY_POINT,
        required=False,
    )

    return parser
