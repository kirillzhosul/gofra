from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path

from gofra.cli.distribution import infer_distribution_library_paths
from gofra.cli.helpers import cli_get_executable_program


@dataclass(frozen=True)
class CLIArguments:
    """Arguments from argument parser provided for whole Gofra testkit process."""

    directory: Path
    build_cache_dir: Path
    verbose: bool
    include_paths: list[Path]

    delete_build_cache: bool = True
    delete_build_artifacts: bool = True


def parse_cli_arguments() -> CLIArguments:
    """Parse CLI arguments from argparse into custom DTO."""
    parser = _construct_argument_parser()
    args = parser.parse_args()

    return CLIArguments(
        include_paths=infer_distribution_library_paths(),
        verbose=not bool(args.silent),
        directory=Path(args.directory),
        build_cache_dir=Path(args.cache_dir),
    )


def _construct_argument_parser() -> ArgumentParser:
    """Get argument parser instance to parse incoming arguments."""
    parser = ArgumentParser(
        description="Gofra Testkit - CLI for testing internals of Gofra programming language",
        add_help=True,
        prog=cli_get_executable_program(override=None, warn_proper_installation=False),
    )

    parser.add_argument(
        "--silent",
        "-s",
        default=False,
        action="store_true",
        help="Silence all verbose output, defaults to false (verbose)",
    )
    parser.add_argument(
        "--directory",
        "-d",
        default="./",
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
