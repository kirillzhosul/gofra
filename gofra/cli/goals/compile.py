from __future__ import annotations

import sys
from typing import TYPE_CHECKING, NoReturn

from gofra.assembler.assembler import (
    assemble_object_from_codegen_assembly,
)
from gofra.cache.directory import prepare_build_cache_directory
from gofra.cli.goals._optimization_pipeline import cli_process_optimization_pipeline
from gofra.cli.output import cli_message
from gofra.codegen.generator import generate_code_for_assembler
from gofra.execution.execution import execute_binary_executable
from gofra.execution.permissions import apply_file_executable_permissions
from gofra.gofra import process_input_file
from gofra.lexer.tokens import TokenLocation
from gofra.linker.apple.command_composer import compose_apple_linker_command
from gofra.linker.command_composer import get_linker_command_composer_backend
from gofra.linker.gnu.command_composer import compose_gnu_linker_command
from gofra.linker.linker import link_object_files
from gofra.linker.output_format import LinkerOutputFormat
from gofra.linker.pkgconfig.pkgconfig import pkgconfig_get_library_search_paths
from gofra.preprocessor.macros.registry import registry_from_raw_definitions
from gofra.typecheck import validate_type_safety

if TYPE_CHECKING:
    from gofra.cli.parser.arguments import CLIArguments


def cli_perform_compile_goal(args: CLIArguments) -> NoReturn:
    """Process full toolchain onto input source files."""
    if len(args.source_filepaths) > 1:
        cli_message(
            level="ERROR",
            text="Compiling several files not implemented.",
        )
        return sys.exit(1)
    cli_message(level="INFO", text="Parsing input files...", verbose=args.verbose)

    macros_registry = registry_from_raw_definitions(
        location=TokenLocation.cli(),
        definitions=args.definitions,
    ).inject_propagated_defaults(target=args.target)

    module = process_input_file(
        args.source_filepaths[0],
        args.include_paths,
        macros=macros_registry,
        _debug_emit_lexemes=args.lexer_debug_emit_lexemes,
    )

    if not args.skip_typecheck:
        cli_message(
            level="INFO",
            text="Validating type safety...",
            verbose=args.verbose,
        )
        validate_type_safety(module)

    cli_process_optimization_pipeline(module, args)

    cli_message(
        level="INFO",
        text="Assembling object file(s)...",
        verbose=args.verbose,
    )

    cache_dir = args.build_cache_dir
    prepare_build_cache_directory(cache_dir)

    output = args.output_filepath
    assembly_filepath = (cache_dir / output.name).with_suffix(
        args.target.file_assembly_suffix,
    )

    generate_code_for_assembler(assembly_filepath, module, args.target)

    object_filepath = (cache_dir / output.name).with_suffix(
        args.target.file_object_suffix,
    )

    assemble_object_from_codegen_assembly(
        assembly=assembly_filepath,
        output=object_filepath,
        target=args.target,
        additional_assembler_flags=args.assembler_flags,
        debug_information=args.debug_symbols,
    )

    if args.delete_build_cache:
        assembly_filepath.unlink()

    if args.output_format in ("library", "executable"):
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

        output_format = (
            LinkerOutputFormat.EXECUTABLE
            if args.output_format == "executable"
            else LinkerOutputFormat.LIBRARY
        )

        libraries_search_paths = args.linker_libraries_search_paths
        if args.linker_resolve_libraries_with_pkgconfig:
            for library in args.linker_libraries:
                paths = pkgconfig_get_library_search_paths(library)
                if paths:
                    libraries_search_paths += paths
        linker_process = link_object_files(
            objects=[object_filepath],
            target=args.target,
            output=args.output_filepath,
            libraries=args.linker_libraries,
            output_format=output_format,
            additional_flags=args.linker_additional_flags,
            libraries_search_paths=args.linker_libraries_search_paths,
            profile=args.linker_profile,
            linker_backend=linker_backend,
            linker_executable=args.linker_executable,
            cache_directory=args.build_cache_dir,
        )
        linker_process.check_returncode()

    if args.delete_build_cache:
        object_filepath.unlink()

    if args.output_format == "executable":
        apply_file_executable_permissions(args.output_filepath)

    cli_message(
        level="INFO",
        text=f"Compiled input file down to {args.output_format} `{args.output_filepath.name}`!",
        verbose=args.verbose,
    )

    if args.execute_after_compilation:
        if args.output_format != "executable":
            cli_message(
                level="ERROR",
                text="Cannot execute after compilation due to output format is not set to an executable!",
            )
            sys.exit(1)
        cli_execute_after_compilation(args)

    return sys.exit(0)


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

    if exit_code == 0:
        cli_message(
            "INFO",
            f"Program finished with exit code {exit_code}!",
            verbose=args.verbose,
        )
    else:
        cli_message(
            "ERROR",
            f"Program finished with fail exit code {exit_code}!",
            verbose=args.verbose,
        )
