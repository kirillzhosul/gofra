from __future__ import annotations

import sys
from subprocess import CalledProcessError, run
from typing import TYPE_CHECKING

from gofra.assembler import assemble_program
from gofra.cli.definitions import construct_propagated_toolchain_definitions
from gofra.consts import GOFRA_ENTRY_POINT
from gofra.gofra import process_input_file
from gofra.lexer import tokenize_from_raw
from gofra.lexer.io.io import open_source_file_line_stream
from gofra.lexer.tokens import TokenLocation
from gofra.optimizer import create_optimizer_pipeline
from gofra.preprocessor.macros.registry import registry_from_raw_definitions
from gofra.preprocessor.preprocessor import preprocess_file
from gofra.typecheck import validate_type_safety

from .arguments import CLIArguments, parse_cli_arguments
from .errors import cli_gofra_error_handler
from .helpers import cli_get_executable_program
from .ir import emit_ir_into_stdout
from .output import cli_message

if TYPE_CHECKING:
    from gofra.context import ProgramContext


def cli_entry_point(prog: str | None = None) -> None:
    """CLI main entry."""
    prog = cli_get_executable_program(override=prog, warn_proper_installation=True)
    with cli_gofra_error_handler():
        args = parse_cli_arguments(prog)

        assert len(args.source_filepaths) == 1

        cli_process_toolchain_on_input_files(args)

        if args.execute_after_compilation and not args.preprocess_only and not args.ir:
            if args.output_format != "executable":
                cli_message(
                    level="ERROR",
                    text="Cannot execute after compilation due to output format is not set to an executable!",
                )
                sys.exit(1)
            cli_execute_after_compilation(args)


def cli_process_optimization_pipeline(
    program: ProgramContext,
    args: CLIArguments,
) -> None:
    """Apply optimization pipeline for program according to CLI arguments."""
    cli_message(
        level="INFO",
        text=f"Applying optimizer pipeline (From base optimization level: {args.optimizer.level})",
        verbose=args.verbose,
    )

    pipeline = create_optimizer_pipeline(args.optimizer)
    for optimizer_pass, optimizer_pass_name in pipeline:
        cli_message(
            level="INFO",
            text=f"Applying optimizer '{optimizer_pass_name}' pass",
            verbose=args.verbose,
        )
        optimizer_pass(program)


def cli_process_toolchain_on_input_files(args: CLIArguments) -> None:
    """Process full toolchain onto input source files."""
    cli_message(level="INFO", text="Parsing input files...", verbose=args.verbose)

    macros_registry = registry_from_raw_definitions(
        location=TokenLocation.cli(),
        definitions=args.definitions,
    )

    macros_registry.update(
        registry_from_raw_definitions(
            location=TokenLocation.toolchain(),
            definitions=construct_propagated_toolchain_definitions(
                target=args.target,
            ),
        ),
    )

    if args.preprocess_only:
        path = args.source_filepaths[0]
        io = open_source_file_line_stream(path)
        lexer = tokenize_from_raw(path, io)
        preprocessor = preprocess_file(
            args.source_filepaths[0],
            lexer,
            args.include_paths,
            macros=macros_registry,
        )
        for token in preprocessor:
            print(str(token.text), end=" ")
        return

    context = process_input_file(
        args.source_filepaths[0],
        args.include_paths,
        macros=macros_registry,
    )

    if not args.skip_typecheck:
        cli_message(
            level="INFO",
            text="Validating type safety...",
            verbose=args.verbose,
        )
        validate_type_safety(
            functions={**context.functions, GOFRA_ENTRY_POINT: context.entry_point},
        )

    cli_process_optimization_pipeline(context, args)

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
        link_with_system_libraries=args.link_with_system_libraries,
    )

    cli_message(
        level="INFO",
        text=f"Compiled input file down to {args.output_format} `{args.output_filepath.name}`!",
        verbose=args.verbose,
    )


PERMISSION_CHMOD_EXECUTABLE = 0o755


def cli_execute_after_compilation(args: CLIArguments) -> None:
    """Run executable after compilation if user requested."""
    cli_message(
        "INFO",
        "Trying to execute compiled file due to execute flag...",
        verbose=args.verbose,
    )
    exit_code = 0

    assert args.output_filepath.exists()
    args.output_filepath.chmod(PERMISSION_CHMOD_EXECUTABLE)

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
