from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CLIArguments:
    """Arguments from argument parser provided for whole Gofra testkit process."""

    directory: Path
    build_cache_dir: Path


def parse_cli_arguments() -> CLIArguments:
    """Parse CLI arguments from argparse into custom DTO."""
    args = _construct_argument_parser().parse_args()

    return CLIArguments(
        directory=Path(args.directory),
        build_cache_dir=Path(args.cache_dir),
    )


def _construct_argument_parser() -> ArgumentParser:
    """Get argument parser instance to parse incoming arguments."""
    parser = ArgumentParser(
        description="Gofra Testkit - CLI for testing internals of Gofra programming language",
        add_help=True,
    )

    parser.add_argument(
        "--directory",
        "-d",
        default="./",
        required=False,
        help="Directory from which to search test files for runner. Defaults to `./`",
    )
    parser.add_argument(
        "--cache-dir",
        "-cd",
        type=str,
        default="./.build",
        required=False,
        help="Path to directory where to store cache (defaults `./.build`)",
    )
    return parser
