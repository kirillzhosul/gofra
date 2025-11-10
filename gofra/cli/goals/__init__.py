"""Goals for CLI (e.g compile, show version) as different goals that output different result."""

import sys
from time import perf_counter_ns
from typing import NoReturn

from gofra.cli.goals.compile import cli_perform_compile_goal
from gofra.cli.goals.hir import cli_perform_hir_goal
from gofra.cli.goals.preprocessor import cli_perform_preprocess_goal
from gofra.cli.goals.repl import cli_perform_repl_goal
from gofra.cli.goals.version import cli_perform_version_goal
from gofra.cli.output import cli_message
from gofra.cli.parser.arguments import CLIArguments

NANOS_TO_SECONDS = 1_000_000_000


def perform_desired_toolchain_goal(args: CLIArguments) -> NoReturn:
    """Perform toolchain goal base on CLI arguments, by default fall into compile goal."""
    start = perf_counter_ns()
    try:
        if args.version:
            return cli_perform_version_goal(args)

        if args.repl:
            return cli_perform_repl_goal(args)

        if args.preprocess_only:
            return cli_perform_preprocess_goal(args)

        if args.hir:
            return cli_perform_hir_goal(args)

        if args.lir:
            return cli_perform_hir_goal(args)

        return cli_perform_compile_goal(args)
    except SystemExit as e:
        end = perf_counter_ns()
        time_taken = (end - start) / NANOS_TO_SECONDS
        cli_message(
            "INFO",
            f"Performing an goal took {time_taken:.2f} seconds!",
            verbose=args.verbose,
        )
        sys.exit(e.code)
