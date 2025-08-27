from __future__ import annotations

import sys
from pathlib import Path
from subprocess import CalledProcessError, run

from gofra.assembler import assemble_program
from gofra.cli.ir import emit_ir_into_stdout
from gofra.consts import GOFRA_ENTRY_POINT
from gofra.gofra import process_input_file
from gofra.optimizer import optimize_program
from gofra.typecheck import validate_type_safety

from .arguments import CLIArguments, parse_cli_arguments
from .errors import cli_gofra_error_handler
from .output import cli_message

WARN_ON_CONFUSING_PROG = False


def cli_entry_point(prog: str | None = None) -> None:
    """CLI main entry."""
    prog = prog if prog else Path(sys.argv[0]).name
    with cli_gofra_error_handler():
        if prog == "__main__.py" and WARN_ON_CONFUSING_PROG:
            cli_message("WARNING", "Running with prog == '__main__.py'")
        args = parse_cli_arguments(prog)

        assert len(args.source_filepaths) == 1

        cli_process_toolchain_on_input_files(args)

        if args.execute_after_compilation:
            if args.output_format != "executable":
                cli_message(
                    level="ERROR",
                    text="Cannot execute after compilation due to output format is not set to an executable!",
                )
                sys.exit(1)
            cli_execute_after_compilation(args)


def cli_process_toolchain_on_input_files(args: CLIArguments) -> None:
    """Process full toolchain onto input source files."""
    cli_message(level="INFO", text="Parsing input files...", verbose=args.verbose)
    context = process_input_file(args.source_filepaths[0], args.include_paths)

    if not args.skip_typecheck:
        cli_message(
            level="INFO",
            text="Validating type safety...",
            verbose=args.verbose,
        )
        validate_type_safety(
            functions={**context.functions, GOFRA_ENTRY_POINT: context.entry_point},
        )

    if not args.disable_optimizations:
        cli_message(
            level="INFO",
            text="Applying optimizations...",
            verbose=args.verbose,
        )
        optimize_program(context)

    if args.ir:
        emit_ir_into_stdout(context)
        sys.exit(0)

    cli_message(
        level="INFO",
        text=f"Assemblying final {args.output_format}...",
        verbose=args.verbose,
    )
    assemble_program(
        verbose=args.verbose,
        output_format=args.output_format,
        context=context,
        output=args.output_filepath,
        target=args.target,
        additional_linker_flags=args.linker_flags,
        additional_assembler_flags=args.assembler_flags,
        build_cache_dir=args.build_cache_dir,
        delete_build_cache_after_compilation=args.delete_build_cache,
    )

    cli_message(
        level="INFO",
        text=f"Compiled input file down to {args.output_format} `{args.output_filepath.name}`!",
        verbose=args.verbose,
    )


def cli_execute_after_compilation(args: CLIArguments) -> None:
    """Run executable after compilation if user requested."""
    cli_message(
        "INFO",
        "Trying to execute compiled file due to execute flag...",
        verbose=args.verbose,
    )
    exit_code = 0
    try:
        run(  # noqa: S602
            [args.output_filepath.absolute()],
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
            check=True,
            shell=True,
        )
    except CalledProcessError as e:
        exit_code = e.returncode
    except KeyboardInterrupt:
        cli_message("WARNING", "Execution was interrupted by user!")
        sys.exit(0)

    level = "INFO" if exit_code == 0 else "ERROR"
    cli_message(
        level,
        f"Program finished with exit code {exit_code}!",
        verbose=args.verbose,
    )
