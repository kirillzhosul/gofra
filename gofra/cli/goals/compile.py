from __future__ import annotations

import sys
from contextlib import contextmanager
from time import perf_counter_ns
from typing import TYPE_CHECKING, NoReturn

from gofra.cache.directory import prepare_build_cache_directory
from gofra.cli.goals._optimization_pipeline import cli_process_optimization_pipeline
from gofra.cli.is_segmentation_fault import is_segmentation_fault
from gofra.cli.mod_hashing import (
    get_module_hash,
    is_module_needs_rebuild,
)
from gofra.cli.output import cli_fatal_abort, cli_linter_warning, cli_message
from gofra.execution.execution import execute_native_binary_executable
from gofra.execution.permissions import apply_file_executable_permissions
from libgofra.assembler.assembler import assemble_object_file
from libgofra.codegen.generator import generate_code_for_assembler
from libgofra.gofra import process_input_file
from libgofra.lexer.tokens import TokenLocation
from libgofra.linker.apple.command_composer import compose_apple_linker_command
from libgofra.linker.command_composer import get_linker_command_composer_backend
from libgofra.linker.gnu.command_composer import compose_gnu_linker_command
from libgofra.linker.linker import link_object_files
from libgofra.linker.output_format import LinkerOutputFormat
from libgofra.linker.pkgconfig.pkgconfig import pkgconfig_get_library_search_paths
from libgofra.preprocessor.macros.registry import registry_from_raw_definitions
from libgofra.targets.infer_host import infer_host_target
from libgofra.typecheck import validate_type_safety
from libgofra.typecheck.typechecker import on_lint_warning_suppressed

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, MutableSequence, Sequence
    from pathlib import Path
    from subprocess import CompletedProcess

    from gofra.cli.parser.arguments import CLIArguments
    from libgofra.hir.module import Module

# Must refactor and move somewhere else?
NANOS_TO_SECONDS = 1_000_000_000


@contextmanager
def wrap_with_perf_time_taken(message: str, *, verbose: bool) -> Generator[None]:
    start_time = perf_counter_ns()
    yield
    time_taken = (perf_counter_ns() - start_time) / NANOS_TO_SECONDS
    cli_message(
        level="INFO",
        text=f"{message} took {time_taken:.2f}s",
        verbose=verbose,
    )


def on_warning_wrapper(*, verbose: bool) -> Callable[[str], None]:
    return lambda text: cli_message(
        level="WARNING",
        text=text,
        verbose=verbose,
    )


def cli_perform_compile_goal(args: CLIArguments) -> NoReturn:
    """Process full toolchain onto input source files."""
    cache_gc: MutableSequence[Path] = []

    if len(args.source_filepaths) > 1:
        return cli_fatal_abort(
            "Compiling several files not implemented, you may want to use modules system.",
        )
    cli_message(level="INFO", text="Parsing input files...", verbose=args.verbose)

    macros_registry = registry_from_raw_definitions(
        location=TokenLocation.cli(),
        definitions=args.definitions,
    ).inject_propagated_defaults(target=args.target)

    with wrap_with_perf_time_taken("Core (lex/parse/pp)", verbose=args.verbose):
        # That module may have dependencies that is compiled separately from root
        root_module = process_input_file(
            args.source_filepaths[0],
            args.include_paths,
            macros=macros_registry,
            _debug_emit_lexemes=args.lexer_debug_emit_lexemes,
            rt_array_oob_check=args.runtime_array_oob_checks,
        )

    if root_module.dependencies and args.output_format not in ("executable", "library"):
        cli_message(
            "WARNING",
            "Output format is set to non library/executable and root module is dependant on others - only root symbols are compiled for you, please checkout cache",
        )

    cli_message(
        "INFO",
        f"Collected {len(root_module.flatten_dependencies_paths(include_self=False))} + 1 modules to compile.",
        verbose=args.verbose,
    )

    # Actually this can be skipped if we identify that some modules does not needs rebuild
    _perform_typechecker(args, root_module)
    _perform_optimizer(args, root_module)

    cache_dir = args.build_cache_dir
    prepare_build_cache_directory(cache_dir)

    output = args.output_filepath
    assembly_filepath = (cache_dir / output.name).with_suffix(
        args.target.file_assembly_suffix,
    )

    modules_dependencies_dir = assembly_filepath.parent / (
        f"{root_module.path.name}" + "$mod_dependencies"
    )
    modules_assembly: dict[Path, Path] = {}
    cli_message(
        level="INFO",
        text="Assembling object file(s)...",
        verbose=args.verbose,
    )
    with wrap_with_perf_time_taken("Codegen", verbose=args.verbose):
        if is_module_needs_rebuild(
            args,
            root_module,
            rebuild_artifact=assembly_filepath,
        ):
            generate_code_for_assembler(
                assembly_filepath,
                root_module,
                args.target,
                on_warning=on_warning_wrapper(verbose=args.verbose),
            )

        for mod in root_module.visit_dependencies(include_self=False):
            mod_assembly_path = (
                modules_dependencies_dir / get_module_hash(mod)
            ).with_suffix(args.target.file_assembly_suffix)
            if not is_module_needs_rebuild(
                args,
                mod,
                rebuild_artifact=mod_assembly_path,
            ):
                modules_assembly[mod.path] = mod_assembly_path
                continue
            generate_code_for_assembler(
                mod_assembly_path,
                mod,
                args.target,
                on_warning=on_warning_wrapper(verbose=args.verbose),
            )
            modules_assembly[mod.path] = mod_assembly_path

    if args.output_format == "assembly":
        assembly_filepath.replace(args.output_filepath)

    object_filepath = (cache_dir / output.name).with_suffix(
        args.target.file_object_suffix,
    )

    modules_objects = _perform_assembler(
        args,
        root_module,
        modules_dependencies_dir,
        modules_assembly,
        assembly_filepath,
        object_filepath,
    )

    cache_gc.append(assembly_filepath)
    cache_gc.extend(modules_assembly.values())

    # We may skip this part also if identify that final build artifact is not needs rebuild
    # e.g if dependant object files is already linked against this artifact (modify time, hash)
    _perform_linker_bundle(
        args,
        object_filepath,
        modules_objects=list(modules_objects.values()),
    )

    if args.delete_build_cache:
        cache_gc.append(object_filepath)
        cache_gc.extend(modules_objects.values())

    if args.output_format == "executable":
        apply_file_executable_permissions(args.output_filepath)

    if args.output_format == "object":
        object_filepath.replace(args.output_filepath)

    cli_message(
        level="INFO",
        text=f"Compiled input file down to {args.output_format} `{args.output_filepath.name}`!",
        verbose=args.verbose,
    )

    # Parent may also exit with children exit code?
    _execute_after_compilation(args)
    _cleanup_cache_gc(cache_gc, args)
    return sys.exit(0)


def _perform_assembler(  # noqa: PLR0913
    args: CLIArguments,
    root_module: Module,
    modules_dependencies_dir: Path,
    modules_assembly: dict[Path, Path],
    assembly_filepath: Path,
    object_filepath: Path,
) -> dict[Path, Path]:
    if args.output_format not in ("library", "object", "executable"):
        return {}

    modules_objects: dict[Path, Path] = {}

    with wrap_with_perf_time_taken("Assembler", verbose=args.verbose):

        def _perform_assembler_driver(in_path: Path, out_path: Path) -> None:
            process = assemble_object_file(
                in_assembly_file=in_path,
                out_object_file=out_path,
                target=args.target,
                extra_flags=args.assembler_flags,
                debug_information=args.debug_symbols,
            )
            process.check_returncode()
            log_command(args, process)

        if is_module_needs_rebuild(args, root_module, rebuild_artifact=object_filepath):
            _perform_assembler_driver(
                in_path=assembly_filepath,
                out_path=object_filepath,
            )
        for mod in root_module.visit_dependencies(include_self=False):
            mod_object_path = (
                modules_dependencies_dir / get_module_hash(mod)
            ).with_suffix(args.target.file_object_suffix)
            if not is_module_needs_rebuild(args, mod, rebuild_artifact=mod_object_path):
                modules_objects[mod.path] = mod_object_path
                continue
            _perform_assembler_driver(
                in_path=modules_assembly[mod.path],
                out_path=mod_object_path,
            )
            modules_objects[mod.path] = mod_object_path

    if args.target.architecture == "WASM32":
        cli_message(
            level="WARNING",
            text="WASM target requires loader with env respectfully!",
        )

    return modules_objects


def _perform_linker_bundle(
    args: CLIArguments,
    root_object: Path,
    modules_objects: list[Path],
) -> None:
    if args.output_format not in ("library", "executable"):
        return
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

    with wrap_with_perf_time_taken("Linker", verbose=args.verbose):
        if args.target.architecture == "WASM32":
            cli_fatal_abort(
                text="Cannot link executable for WASM32, use object output format (`-of object`)",
            )
        libraries_search_paths = args.linker_libraries_search_paths
        if args.linker_resolve_libraries_with_pkgconfig:
            for library in args.linker_libraries:
                paths = pkgconfig_get_library_search_paths(library)
                if paths:
                    libraries_search_paths += paths
        assert all(isinstance(x, str) for x in args.linker_additional_flags)
        linker_process = link_object_files(
            objects=[root_object, *modules_objects],
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
        log_command(args, linker_process)
        linker_process.check_returncode()


def _cleanup_cache_gc(cache_gc: Sequence[Path], args: CLIArguments) -> None:
    if not args.delete_build_cache:
        return
    cli_message(
        level="INFO",
        text=f"Cleaning up {len(cache_gc)} cache files...",
        verbose=args.verbose,
    )
    for item in cache_gc:
        item.unlink(missing_ok=True)


def log_command(args: CLIArguments, process: CompletedProcess[bytes]) -> None:
    if not args.show_commands:
        return
    cli_message("CMD", " ".join(map(str, process.args)))


def _execute_after_compilation(args: CLIArguments) -> None:
    """Run executable after compilation if user requested."""
    if not args.execute_after_compilation:
        return None
    if args.output_format != "executable":
        return cli_fatal_abort(
            text="Cannot execute after compilation due to output format is not set to an executable!",
        )

    host_target = infer_host_target()
    assert host_target
    host_compliance = (
        args.target.architecture == host_target.architecture
        and args.target.operating_system == host_target.operating_system
    )

    if not host_compliance:
        cli_fatal_abort(
            "Target differs from host target, cannot execute on current host without emulation layer, please execute on your own!\nFile was compiled, please remove execute flag!",
        )

    cli_message(
        "INFO",
        "Trying to execute compiled file due to execute flag...",
        verbose=args.verbose,
    )

    with wrap_with_perf_time_taken("Execution", verbose=args.verbose):
        try:
            process = execute_native_binary_executable(args.output_filepath, args=[])
            log_command(args, process)
            exit_code = process.returncode
        except KeyboardInterrupt:
            cli_message("WARNING", "Execution was interrupted by user!")
            sys.exit(0)
        _log_child_exit_code(args, exit_code)
    return None


def _perform_typechecker(args: CLIArguments, root_module: Module) -> None:
    if args.skip_typecheck:
        return
    cli_message(
        level="INFO",
        text="Validating type safety...",
        verbose=args.verbose,
    )
    is_executable = args.output_format == "executable"
    with wrap_with_perf_time_taken("Typecheck and lint", verbose=args.verbose):
        for mod in root_module.visit_dependencies(include_self=True):
            is_root = mod == root_module
            must_has_entry_point = (
                is_root and is_executable
            )  # Main required for root module and only if executable
            validate_type_safety(
                mod,
                on_lint_warning=cli_linter_warning
                if args.display_lint_warnings
                else on_lint_warning_suppressed,
                strict_expect_entry_point=must_has_entry_point,
            )


def _perform_optimizer(args: CLIArguments, root_module: Module) -> None:
    with wrap_with_perf_time_taken("Optimizer", verbose=args.verbose):
        cli_message(
            level="INFO",
            text=f"Applying optimizer pipeline (From base optimization level: {args.optimizer.level})",
            verbose=args.verbose,
        )
        for mod in root_module.visit_dependencies(include_self=False):
            cli_process_optimization_pipeline(mod, args)

        # Perform root optimizations last - high level optimizations after dependencies
        cli_process_optimization_pipeline(root_module, args)


def _log_child_exit_code(args: CLIArguments, exit_code: int) -> None:
    if exit_code == 0:
        return cli_message(
            "INFO",
            f"Program finished with exit code {exit_code}!",
            verbose=args.verbose,
        )

    if is_segmentation_fault(exit_code):
        return cli_message(
            "ERROR",
            f"Program finished with segmentation fault exit code (SIGSEGV, {exit_code})!",
        )

    return cli_message(
        "ERROR",
        f"Program finished with fail exit code {exit_code}!",
        verbose=args.verbose,
    )
