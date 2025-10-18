from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast, get_args, get_type_hints

from gofra.cli.output import cli_message
from gofra.cli.parser.arguments import CLIArguments
from gofra.linker.profile import LinkerProfile
from gofra.optimizer.config import (
    OptimizerConfig,
    build_default_optimizer_config_from_level,
    merge_into_optimizer_config,
)
from gofra.preprocessor.include.distribution import (
    infer_distribution_library_paths,
)
from gofra.targets import Target
from gofra.targets.infer_host import infer_host_target
from gofra.targets.target import Triplet

if TYPE_CHECKING:
    from argparse import Namespace


def parse_cli_arguments(args: Namespace) -> CLIArguments:
    """Parse CLI arguments from argparse into custom DTO."""
    _validate_mutually_exclusive_goals(args)
    target = _process_target(args)
    source_filepaths = _process_source_filepaths(args)
    definitions = _process_definitions(args)
    include_paths = _process_include_paths(args)
    optimizer = _process_optimizer_config(args)
    output = _process_output_path(source_filepaths, args, target)
    linker_profile = _process_linker_profile(args)
    linker_libraries_search_paths = _process_linker_libraries_search_paths(args)
    linker_executable = _process_linker_executable(args)
    linker_backend = _process_linker_backend(args)
    output_format = _process_output_format(args)

    return CLIArguments(
        # Goals.
        version=bool(args.version),
        hir=bool(args.hir),
        lir=bool(args.lir),
        preprocess_only=bool(args.preprocess_only),
        # Rest of these are mostly goal-specific
        execute_after_compilation=bool(args.execute),
        delete_build_cache=bool(args.delete_cache),
        debug_symbols=bool(args.debug_symbols),
        skip_typecheck=bool(args.skip_typecheck),
        verbose=bool(args.verbose),
        source_filepaths=source_filepaths,
        output_filepath=output,
        output_file_is_specified=bool(args.output),
        output_format=output_format,
        build_cache_dir=Path(args.cache_dir),
        target=target,
        definitions=definitions,
        include_paths=include_paths,
        assembler_flags=cast("list[str]", args.assembler),
        linker_profile=linker_profile,
        optimizer=optimizer,
        linker_executable=linker_executable,
        linker_libraries=cast("list[str]", args.linker_libraries),
        linker_backend=linker_backend,
        linker_additional_flags=cast("list[str]", args.linker_additional_flags),
        linker_libraries_search_paths=linker_libraries_search_paths,
        linker_resolve_libraries_with_pkgconfig=bool(
            args.linker_resolve_libraries_with_pkgconfig,
        ),
        lexer_debug_emit_lexemes=bool(args.lexer_debug_emit_lexemes),
        cli_debug_user_friendly_errors=bool(args.cli_debug_user_friendly_errors),
    )


def _process_linker_profile(args: Namespace) -> LinkerProfile:
    """Process linker profile into suitable enum."""
    return (
        LinkerProfile.DEBUG
        if args.linker_profile == "debug"
        else LinkerProfile.PRODUCTION
    )


def _process_linker_libraries_search_paths(args: Namespace) -> list[Path]:
    return [Path(f) for f in args.linker_libraries_search_paths]


def _process_linker_backend(
    args: Namespace,
) -> Literal["gnu-ld", "apple-ld"]:
    """Validate and process linker backend as type safe value."""
    allowed_formats = get_args(get_type_hints(CLIArguments)["linker_backend"])
    assert args.linker_backend in (*allowed_formats, None), (
        f"{args.target} not in {allowed_formats}"
    )
    args.linker_backend = cast(
        'Literal["gnu-ld", "apple-ld"]',
        args.linker_backend,
    )

    return args.linker_backend


def _process_output_format(
    args: Namespace,
) -> Literal["library", "object", "executable", "assembly"]:
    """Validate and process output format as type safe value."""
    allowed_formats = get_args(get_type_hints(CLIArguments)["output_format"])
    assert args.output_format in (*allowed_formats, None), (
        f"{args.target} not in {allowed_formats}"
    )
    args.output_format = cast(
        'Literal["library", "object", "executable", "assembly"]',
        args.output_format,
    )

    return args.output_format


def _process_linker_executable(args: Namespace) -> Path | None:
    executable = Path(args.linker_executable) if args.linker_executable else None
    if executable is not None and not executable.exists():
        cli_message("ERROR", "Specified linker executable does not exists!")
        return sys.exit(1)
    return executable


def _validate_mutually_exclusive_goals(args: Namespace) -> None:
    """Validate that goal flags is not present as mutually exclusive."""
    if sum([args.version, args.preprocess_only, args.hir, args.lir]) in (0, 1):
        return None

    cli_message("ERROR", "Goal flags is mutually exclusive!")
    return sys.exit(1)


def _process_target(args: Namespace) -> Target:
    """Process target arguments as only allowed triplets and auto inference if not specified."""
    if args.target:
        # Expect only type literal triplets.
        assert args.target in get_args(Triplet.__value__)
        args.target = cast("Triplet", args.target)

        return Target.from_triplet(args.target)
    target = infer_host_target()
    if target is None:
        cli_message(
            level="ERROR",
            text="Unable to infer compilation target due to no fallback for current operating system",
        )
        return sys.exit(1)
    return target


def _process_definitions(args: Namespace) -> dict[str, str]:
    """Process CLI propagated definitions as raw macro source text that requires lexing / parsing."""
    user_definitions: dict[str, str] = {}

    raw_definitions = cast("list[str]", args.definitions)
    for cli_definition in raw_definitions:
        if "=" in cli_definition:
            name, value = cli_definition.split("=", maxsplit=1)
            user_definitions[name] = value

            continue
        user_definitions[cli_definition] = "1"

    return user_definitions


def _process_source_filepaths(args: Namespace) -> list[Path]:
    """Process input source files as paths and validate it."""
    goal_requires_source = not args.version
    paths = [Path(f) for f in args.source_files]
    if not goal_requires_source:
        return paths

    if len(args.source_files) == 0:
        cli_message("ERROR", "Expected source files to compile!")
        return sys.exit(1)

    if any(not p.exists(follow_symlinks=True) for p in paths):
        cli_message(
            level="ERROR",
            text="One of input source file is not exists, aborting compilation as safe mechanism.",
        )
        return sys.exit(1)
    return paths


def _process_include_paths(args: Namespace) -> list[Path]:
    """Process user propagated include paths."""
    user_includes = [Path(include) for include in args.include]
    # Last one as we want additional include paths to override default distribution search
    include_paths = user_includes + infer_distribution_library_paths()

    if any(not p.exists(follow_symlinks=True) or not p.is_dir() for p in user_includes):
        cli_message(
            level="ERROR",
            text="One of user include path is not exists or is not an directory, aborting compilation as safe mechanism.",
        )
        return sys.exit(1)

    return include_paths


def _process_optimizer_config(args: Namespace) -> OptimizerConfig:
    """Process whole configuration of optimizer from CLI into config."""
    config = build_default_optimizer_config_from_level(level=args.optimizer_level)
    return merge_into_optimizer_config(config, args, prefix="optimizer")


def _process_output_path(
    source_filepaths: list[Path],
    args: Namespace,
    target: Target,
) -> Path:
    """Process output path with auto inference if not passed."""
    inferred_output_path = (
        Path(args.output)
        if args.output
        else _infer_output_filename(
            source_filepaths,
            output_format=args.output_format,
            target=target,
        )
    )
    if inferred_output_path in source_filepaths:
        msg = "Inferred/specified output file path will rewrite existing input file, please specify another output path."
        raise ValueError(msg)
    return inferred_output_path


def _infer_output_filename(
    source_filepaths: list[Path],
    output_format: Literal["library", "object", "executable", "assembly"],
    target: Target,
) -> Path:
    """Try to infer filename for output from input source files."""
    suffix: str
    match output_format:
        case "library":
            is_dynamic = False
            suffix = [
                target.file_library_static_suffix,
                target.file_library_dynamic_suffix,
            ][is_dynamic]
        case "object":
            suffix = target.file_object_suffix
        case "assembly":
            suffix = target.file_assembly_suffix
        case "executable":
            suffix = target.file_executable_suffix

    if not source_filepaths:
        return Path("out").with_suffix(suffix)

    source_filepath = source_filepaths[0]

    if source_filepath.suffix == suffix:
        suffix = source_filepath.suffix + suffix
    return source_filepath.with_suffix(suffix)
