from __future__ import annotations

from gofra.cli.errors.error_handler import cli_gofra_error_handler
from gofra.cli.goals import perform_desired_toolchain_goal
from gofra.cli.parser.builder import build_cli_parser
from gofra.cli.parser.parser import parse_cli_arguments
from gofra.executable import cli_get_executable_program, warn_on_improper_installation

from .output import cli_fatal_abort, cli_message


def cli_entry_point() -> None:
    """CLI main entry."""
    prog = cli_get_executable_program()
    warn_on_improper_installation(prog)

    parser = build_cli_parser(prog)
    args = parse_cli_arguments(parser.parse_args())
    wrapper = cli_gofra_error_handler(
        debug_user_friendly_errors=args.cli_debug_user_friendly_errors,
    )

    if args.incremental_compilation:
        cli_message(
            "WARNING",
            "Incremental compilation may skip changes in dependant files due to using raw include!",
        )
    with wrapper:
        # Wrap goal into error handler as in unwraps errors into user-friendly ones (except internal ones as bugs)
        perform_desired_toolchain_goal(args)

    # This is unreachable but error wrapper must fail
    cli_fatal_abort("Bug in a CLI: toolchain must perform at least one goal!")


if __name__ == "__main__":
    cli_entry_point()
