from __future__ import annotations

import time
from subprocess import TimeoutExpired
from typing import TYPE_CHECKING

from gofra.cli.arguments import infer_target
from gofra.cli.errors import cli_gofra_error_handler
from gofra.cli.output import cli_message
from gofra.exceptions import GofraError
from gofra.testkit.cli.matrix import display_test_matrix

from .cli.arguments import CLIArguments, parse_cli_arguments
from .evaluate import evaluate_test_case

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from .test import Test

TEST_CASE_PATTERN = "test_*.gof"
TESTKIT_CACHE_DIR = "__testkit__"
NANOS_TO_SECONDS = 1_000_000_000


def cli_entry_point() -> None:
    """CLI main entry."""
    with cli_gofra_error_handler():
        args = parse_cli_arguments()
        cli_process_testkit_runner(args)


def cli_process_testkit_runner(args: CLIArguments) -> None:
    """Process full testkit toolchain."""
    cli_message(level="INFO", text="Searching test files...", verbose=args.verbose)

    test_paths = tuple(search_test_case_files(args.directory))
    cli_message(
        level="INFO",
        text=f"Found {len(test_paths)} test case files.",
        verbose=args.verbose,
    )

    # TODO(@kirillzhosul): If testkit is being ran first time, it skips proper creation of an build cache directory as it is modified by lines below.
    cache_directory = args.build_cache_dir / TESTKIT_CACHE_DIR
    cache_directory.mkdir(parents=True, exist_ok=True)

    target = infer_target()
    start_time = time.monotonic_ns()
    test_matrix: list[Test] = []
    for test_path in test_paths:
        result = evaluate_test_case(
            test_path,
            args,
            build_target=target,
            build_format="executable",
            cache_directory=cache_directory,
        )
        test_matrix.append(result)

    if args.delete_build_artifacts:
        cli_message(
            level="INFO",
            text="Removing build artifacts...",
            verbose=args.verbose,
        )
        [test.artifact_path.unlink() for test in test_matrix if test.artifact_path]
    time_taken = (time.monotonic_ns() - start_time) / NANOS_TO_SECONDS
    cli_message(
        level="SUCCESS",
        text=f"Completed testkit run for target '{target}' with {len(test_paths)} cases in {time_taken:.2f}s. (avg {time_taken / len(test_paths):.2f}s.)",
    )
    display_test_matrix(test_matrix)
    display_test_errors(test_matrix)


def display_test_errors(matrix: list[Test]) -> None:
    if any(test.error for test in matrix):
        cli_message("ERROR", "While running tests, some errors were occured:")
    for test in matrix:
        if test.error is None:
            continue
        cli_message("INFO", f"While testing `{test.path}`:")
        if isinstance(test.error, GofraError):
            cli_message("ERROR", repr(test.error))
            continue
        if isinstance(test.error, TimeoutExpired):
            cli_message("ERROR", "Execution timed out (compile OK!)")
            continue
        cli_message(
            "ERROR",
            f"Execution finished with exit code {test.error.returncode} while expected exit code 0!",
        )


def search_test_case_files(directory: Path) -> Generator[Path]:
    return directory.glob(TEST_CASE_PATTERN, case_sensitive=False)
