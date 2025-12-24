from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from subprocess import TimeoutExpired
from typing import TYPE_CHECKING

from gofra.cli.errors.error_handler import cli_gofra_error_handler
from gofra.cli.is_segmentation_fault import is_segmentation_fault
from gofra.cli.output import cli_fatal_abort, cli_message
from gofra.testkit.cli.matrix import display_test_matrix
from gofra.testkit.test import TestStatus
from libgofra.exceptions import GofraError
from libgofra.targets.infer_host import infer_host_target

from .cli.arguments import CLIArguments, parse_cli_arguments
from .evaluate import evaluate_test_case

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from libgofra.targets.target import Target

    from .test import Test

TESTKIT_CACHE_DIR = "__testkit__"
NANOS_TO_SECONDS = 1_000_000_000


def cli_entry_point() -> None:
    """CLI main entry."""
    with cli_gofra_error_handler(
        debug_user_friendly_errors=False,
    ):
        args = parse_cli_arguments()
        cli_process_testkit_runner(args)
        return sys.exit(0)


def cli_process_testkit_runner(args: CLIArguments) -> None:
    """Process full testkit toolchain."""
    cli_message(level="INFO", text="Searching test files...", verbose=args.verbose)

    test_paths = tuple(
        search_test_case_files(
            args.directory,
            args.test_files_pattern,
            excluded_filenames=args.excluded_test_files,
        ),
    )
    cli_message(
        level="INFO",
        text=f"Found {len(test_paths)} test case files.",
        verbose=args.verbose,
    )

    # TODO(@kirillzhosul): If testkit is being ran first time, it skips proper creation of an build cache directory as it is modified by lines below.
    cache_directory = args.build_cache_dir / TESTKIT_CACHE_DIR
    cache_directory.mkdir(parents=True, exist_ok=True)

    target = infer_host_target()
    if target is None:
        return cli_fatal_abort(
            text="Unable to infer compilation target due to no fallback for current operating system",
        )
    start_time = time.perf_counter_ns()
    test_matrix = evaluate_test_matrix_threaded(
        test_paths,
        args=args,
        target=target,
        cache_directory=cache_directory,
    )

    if args.delete_build_artifacts:
        cli_message(
            level="INFO",
            text="Removing build artifacts...",
            verbose=args.verbose,
        )
        for test in test_matrix:
            if test.artifact_path:
                test.artifact_path.unlink()

    time_taken = (time.perf_counter_ns() - start_time) / NANOS_TO_SECONDS
    cli_message(
        level="INFO",
        text=f"Completed testkit run for target '{target.triplet}' with {len(test_paths)} cases in {time_taken:.2f}s. (avg {(time_taken / len(test_paths)) if test_paths else 0:.2f}s.)",
        verbose=args.verbose,
    )
    display_test_matrix(test_matrix)
    display_test_errors(test_matrix)

    has_failing_tests = any(t.status != TestStatus.SUCCESS for t in test_matrix)
    if has_failing_tests and args.fail_with_abnormal_exit_code:
        # CI mostly:
        print()
        cli_message("ERROR", "Some test(s) failing, exiting abnormally (exit code 1)")
        return sys.exit(1)

    return sys.exit(0)


def evaluate_test_matrix_threaded(
    test_paths: Sequence[Path],
    *,
    args: CLIArguments,
    target: Target,
    cache_directory: Path,
) -> list[Test]:
    def evaluate_single_test(test_path: Path) -> Test:
        return evaluate_test_case(
            test_path,
            args,
            build_target=target,
            cache_directory=cache_directory,
        )

    max_workers = max(1, min(len(test_paths), args.max_thread_workers))

    if max_workers <= 1:
        return [evaluate_single_test(test_path) for test_path in test_paths]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(evaluate_single_test, test_path) for test_path in test_paths
        ]

        return [future.result() for future in futures]


def display_test_errors(matrix: list[Test]) -> None:
    if any(test.error for test in matrix):
        cli_message("ERROR", "While running tests, some errors were occurred:")
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

        exit_code = test.error.returncode
        if is_segmentation_fault(exit_code):
            cli_message(
                "ERROR",
                f"Execution failed with segmentation fault (SIGSEGV, {exit_code})!",
            )
        else:
            cli_message(
                "ERROR",
                f"Execution finished with exit code {exit_code} while expected exit code {test.expected_exit_code}!",
            )


def search_test_case_files(
    directory: Path,
    pattern: str,
    excluded_filenames: list[str],
) -> list[Path]:
    return [
        p
        for p in directory.glob(pattern, case_sensitive=False)
        if p.name not in excluded_filenames
    ]
