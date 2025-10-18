from __future__ import annotations

import os
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path

from gofra.cli.executable import cli_get_executable_program
from gofra.preprocessor.include.distribution import infer_distribution_library_paths

THREAD_OPTIMAL_WORKERS_COUNT = (os.cpu_count() or 1) * 2


@dataclass(frozen=True)
class CLIArguments:
    """Arguments from argument parser provided for whole Gofra testkit process."""

    directory: Path
    build_cache_dir: Path
    verbose: bool
    include_paths: list[Path]

    test_files_pattern: str
    excluded_test_files: list[str]

    fail_with_abnormal_exit_code: bool
    build_only_no_execute: bool
    max_thread_workers: int
    delete_build_artifacts: bool
    delete_build_cache: bool = True


def parse_cli_arguments() -> CLIArguments:
    """Parse CLI arguments from argparse into custom DTO."""
    parser = _construct_argument_parser()
    args = parser.parse_args()

    return CLIArguments(
        include_paths=infer_distribution_library_paths(),
        verbose=not bool(args.silent),
        directory=Path(args.directory),
        max_thread_workers=args.max_thread_workers,
        build_cache_dir=Path(args.cache_dir),
        build_only_no_execute=bool(args.build_only_no_execute),
        delete_build_artifacts=bool(args.delete_build_artifacts),
        excluded_test_files=args.excluded_test_files,
        test_files_pattern=args.test_files_pattern,
        fail_with_abnormal_exit_code=bool(args.fail_with_abnormal_exit_code),
    )


def _construct_argument_parser() -> ArgumentParser:
    """Get argument parser instance to parse incoming arguments."""
    parser = ArgumentParser(
        description="Gofra Testkit - CLI for testing internals of Gofra programming language",
        add_help=True,
        prog=cli_get_executable_program(override=None, warn_proper_installation=False),
    )

    parser.add_argument(
        "--pattern",
        "-p",
        dest="test_files_pattern",
        default="test_*.gof",
        help="Pattern for file that is treated as test cases, defaults to `test_*.gof`",
    )

    parser.add_argument(
        "--exclude",
        "-e",
        dest="excluded_test_files",
        default=[],
        nargs="?",
    )

    parser.add_argument(
        "--fail-with-abnormal-exit-code",
        dest="fail_with_abnormal_exit_code",
        default=False,
        action="store_true",
        help="If passed will exit abnormally if any test is failing",
    )

    parser.add_argument(
        "--silent",
        "-s",
        default=False,
        action="store_true",
        help="Silence all verbose output, defaults to false (verbose)",
    )

    parser.add_argument(
        "--no-delete-artifacts",
        "--keep-artifacts",
        dest="delete_build_artifacts",
        default=True,
        action="store_false",
        help="If true will not delete build cache artifacts within testkit sub directory.",
    )

    parser.add_argument(
        "--directory",
        "-d",
        default="./tests",
        help="Directory from which to search test files for runner. Defaults to `./tests`",
    )

    parser.add_argument(
        "--cache-dir",
        "-cd",
        type=str,
        default="./.build",
        required=False,
        help="Path to directory where to store cache (defaults `./.build`)",
    )

    parser.add_argument(
        "--build-only",
        "--build-test",
        dest="build_only_no_execute",
        action="store_true",
        help="If specified, will not execute binaries, only tries to build it (e.g suitable for applications build testing)",
    )

    parser.add_argument(
        "--threads",
        type=int,
        dest="max_thread_workers",
        default=THREAD_OPTIMAL_WORKERS_COUNT,
        help=f"Max thread workers (defaults to {THREAD_OPTIMAL_WORKERS_COUNT} for your host)",
    )
    return parser
