from __future__ import annotations

import sys
from platform import platform, python_implementation, python_version
from typing import TYPE_CHECKING

from gofra.assembler import assemble_program
from gofra.cli.definitions import construct_propagated_toolchain_definitions
from gofra.consts import GOFRA_ENTRY_POINT
from gofra.execution.execution import execute_binary_executable
from gofra.execution.permissions import apply_file_executable_permissions
from gofra.gofra import process_input_file
from gofra.lexer import tokenize_from_raw
from gofra.lexer.io.io import open_source_file_line_stream
from gofra.lexer.tokens import TokenLocation
from gofra.linker.apple.command_composer import compose_apple_linker_command
from gofra.linker.command_composer import get_linker_command_composer_backend
from gofra.linker.gnu.command_composer import compose_gnu_linker_command
from gofra.linker.linker import link_object_files
from gofra.linker.output_format import LinkerOutputFormat
from gofra.linker.pkconfig.pkgconfig import pkgconfig_get_library_search_paths
from gofra.linker.profile import LinkerProfile
from gofra.optimizer import create_optimizer_pipeline
from gofra.preprocessor.macros.registry import registry_from_raw_definitions
from gofra.preprocessor.preprocessor import preprocess_file
from gofra.typecheck import validate_type_safety

from .arguments import CLIArguments, parse_cli_arguments
from .errors import cli_gofra_error_handler
from .helpers import cli_get_executable_program
from .ir import emit_hir_into_stdout, emit_lir_into_stdout
from .output import cli_message

if TYPE_CHECKING:
    from gofra.context import ProgramContext


def cli_entry_point(prog: str | None = None) -> None:
    """CLI main entry."""
    prog = cli_get_executable_program(override=prog, warn_proper_installation=True)
    with cli_gofra_error_handler():
        args = parse_cli_arguments(prog)

        if len(args.source_filepaths) == 0 and not args.version:
            cli_message("ERROR", "Expected atleast one source files given!")
            sys.exit(1)

        if len(args.source_filepaths) > 1 and not args.version:
            cli_message(
                level="ERROR",
                text="Compiling several files not implemented.",
            )
            sys.exit(1)
        if args.version:
            cli_emit_system_host_version(args)
            sys.exit(0)

        assert len(args.source_filepaths) == 1
        cli_process_toolchain_on_input_files(args)

        has_artifact = not args.preprocess_only and not args.hir and not args.lir
        if args.execute_after_compilation and has_artifact:
            if args.output_format != "executable":
                cli_message(
                    level="ERROR",
                    text="Cannot execute after compilation due to output format is not set to an executable!",
                )
                sys.exit(1)
            cli_execute_after_compilation(args)


def cli_emit_system_host_version(args: CLIArguments) -> None:
    print("[Gofra toolchain]")
    print()
    print("Toolchain target (may be unavailable on host machine):")
    print(f"\tTriplet: {args.target.triplet}")
    print(f"\tArchitecture: {args.target.architecture}")
    print(f"\tOS: {args.target.operating_system}")
    print()
    print("Host machine:")
    print(f"\tPlatform: {platform()}")
    print(f"\tPython: {python_implementation()} {python_version()}")
    print()


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

    if args.hir:
        emit_hir_into_stdout(context)
        sys.exit(0)

    if args.lir:
        emit_lir_into_stdout(context)
        sys.exit(0)

    cli_message(
        level="INFO",
        text="Assemblying object file(s)...",
        verbose=args.verbose,
    )
    objects = assemble_program(
        verbose=args.verbose,
        output_format=args.output_format,
        context=context,
        output=args.output_filepath,
        target=args.target,
        additional_assembler_flags=args.assembler_flags,
        build_cache_dir=args.build_cache_dir,
        delete_build_cache_after_compilation=args.delete_build_cache,
    )

    if (objects and args.output_format in ("library", "executable")) or (
        objects and len(objects) > 1 and args.output_format == "object"
    ):
        cli_message(
            level="INFO",
            text=f"Linking final {args.output_format} from object file(s)...",
            verbose=args.verbose,
        )

        if args.linker_backend is None:
            linker_backend = get_linker_command_composer_backend(args.target)
        else:
            match args.linker_backend:
                case "apple-ld":
                    linker_backend = compose_apple_linker_command
                case "gnu-ld":
                    linker_backend = compose_gnu_linker_command

        profile = (
            LinkerProfile.DEBUG if args.profile == "debug" else LinkerProfile.PRODUCTION
        )

        output_format = (
            LinkerOutputFormat.EXECUTABLE
            if args.output_format == "executable"
            else LinkerOutputFormat.LIBRARY
        )

        libraries_search_paths = args.linker_libraries_search_paths
        if args.linker_resolve_libraries_with_pkconfig:
            for library in args.linker_libraries:
                paths = pkgconfig_get_library_search_paths(library)
                if paths:
                    libraries_search_paths += paths
        linker_proccess = link_object_files(
            objects=objects,
            target=args.target,
            output=args.output_filepath,
            libraries=args.linker_libraries,
            output_format=output_format,
            additional_flags=args.linker_additional_flags,
            libraries_search_paths=args.linker_libraries_search_paths,
            profile=profile,
            linker_backend=linker_backend,
            linker_executable=args.linker_executable,
            cache_directory=args.build_cache_dir,
        )
        linker_proccess.check_returncode()

    apply_file_executable_permissions(args.output_filepath)

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

    try:
        exit_code = execute_binary_executable(args.output_filepath, args=[])
    except KeyboardInterrupt:
        cli_message("WARNING", "Execution was interrupted by user!")
        sys.exit(0)

    level = "INFO" if exit_code == 0 else "ERROR"
    cli_message(
        level,
        f"Program finished with exit code {exit_code}!",
        verbose=args.verbose,
    )
