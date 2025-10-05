from __future__ import annotations

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from gofra.cli.distribution import infer_distribution_library_paths
from gofra.cli.infer import infer_output_filename, infer_target
from gofra.optimizer.config import (
    OptimizerConfig,
    build_default_optimizer_config_from_level,
    merge_into_optimizer_config,
)
from gofra.targets import Target

from .output import cli_message

if TYPE_CHECKING:
    from gofra.assembler.assembler import OUTPUT_FORMAT_T


@dataclass(frozen=True)
class CLIArguments:
    """Arguments from argument parser provided for whole Gofra toolchain process."""

    source_filepaths: list[Path]
    output_filepath: Path
    output_format: OUTPUT_FORMAT_T

    execute_after_compilation: bool
    debug_symbols: bool

    include_paths: list[Path]
    definitions: dict[str, str]

    version: bool

    hir: bool
    lir: bool
    preprocess_only: bool

    assembler_flags: list[str]

    verbose: bool

    target: Target

    skip_typecheck: bool

    build_cache_dir: Path
    delete_build_cache: bool

    profile: Literal["debug", "production"]

    linker_additional_flags: list[str]
    linker_libraries: list[str]
    linker_libraries_search_paths: list[Path]
    linker_backend: Literal["gnu-ld", "apple-ld"] | None
    linker_resolve_libraries_with_pkconfig: bool
    linker_executable: Path | None

    optimizer: OptimizerConfig


def parse_cli_arguments(prog: str) -> CLIArguments:
    """Parse CLI arguments from argparse into custom DTO."""
    args = _construct_argument_parser(prog=prog).parse_args()

    if None in args.include:
        cli_message(
            level="WARNING",
            text="One of the include search directories is empty, it will be skipped!",
        )
    if args.skip_typecheck:
        cli_message(
            level="WARNING",
            text="Skipping typecheck is unsafe, ensure that you know what you doing",
        )

    assert args.linker_backend in ("gnu-ld", "apple-ld", None)
    assert args.profile in ("debug", "production")

    assert args.target in (
        "amd64-unknown-linux",
        "arm64-apple-darwin",
        "amd64-unknown-windows",
        None,
    )
    target: Target = Target.from_triplet(args.target) if args.target else infer_target()

    source_filepaths = [Path(f) for f in args.source_files]
    output_filepath = process_output_path(source_filepaths, args, target)
    include_paths = process_include_paths(args)
    definitions = process_definitions(args)

    assembler_flags = args.assembler
    if bool(args.debug_symbols):
        assembler_flags += ["-g"]

    linker_executable = Path(args.linker_executable) if args.linker_executable else None
    linker_libraries_search_paths = [
        Path(f) for f in args.linker_libraries_search_paths
    ]

    optimizer = build_default_optimizer_config_from_level(level=args.optimizer_level)
    optimizer = merge_into_optimizer_config(optimizer, args, prefix="optimizer")
    return CLIArguments(
        debug_symbols=bool(args.debug_symbols),
        hir=bool(args.hir),
        lir=bool(args.lir),
        source_filepaths=source_filepaths,
        output_filepath=output_filepath,
        output_format=args.output_format,
        version=bool(args.version),
        execute_after_compilation=bool(args.execute),
        delete_build_cache=bool(args.delete_cache),
        build_cache_dir=Path(args.cache_dir),
        linker_resolve_libraries_with_pkconfig=args.linker_resolve_libraries_with_pkconfig,
        target=target,
        definitions=definitions,
        preprocess_only=bool(args.preprocess_only),
        skip_typecheck=bool(args.skip_typecheck),
        include_paths=include_paths,
        verbose=bool(args.verbose),
        assembler_flags=assembler_flags,
        profile=args.profile,
        # Optimizer
        optimizer=optimizer,
        # Linker
        linker_libraries=args.linker_libraries,
        linker_backend=args.linker_backend,
        linker_additional_flags=args.linker_additional_flags,
        linker_executable=linker_executable,
        linker_libraries_search_paths=linker_libraries_search_paths,
    )


def process_definitions(args: Namespace) -> dict[str, str]:
    user_definitions: dict[str, str] = {}

    for cli_definition in cast("list[str]", args.definitions):
        if "=" in cli_definition:
            name, value = cli_definition.split("=", maxsplit=1)
            user_definitions[name] = value

            continue
        user_definitions[cli_definition] = "1"

    return user_definitions


def process_output_path(
    source_filepaths: list[Path],
    args: Namespace,
    target: Target,
) -> Path:
    infered_output_path = (
        Path(args.output)
        if args.output
        else infer_output_filename(
            source_filepaths,
            output_format=args.output_format,
            target=target,
        )
    )
    if infered_output_path in source_filepaths:
        msg = "Infered/specified output file path will rewrite existing input file, please specify another output path."
        raise ValueError(msg)
    return infered_output_path


def process_include_paths(args: Namespace) -> list[Path]:
    return [
        *map(Path, [include for include in args.include if include]),
        # Last one as we want additional include paths to override default distribution search
        *infer_distribution_library_paths(),
    ]


def _construct_argument_parser(prog: str) -> ArgumentParser:
    """Get argument parser instance to parse incoming arguments."""
    parser = ArgumentParser(
        description="Gofra Toolkit - CLI for working with Gofra programming language",
        add_help=True,
        prog=prog,
    )

    parser.add_argument(
        "source_files",
        type=str,
        help="Input source code files in Gofra to process (`.gof` files)",
        nargs="*",
        default=[],
    )

    parser.add_argument(
        "--version",
        default=False,
        action="store_true",
        help="If passed will just emit system and toolchain information",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        required=False,
        help="Output file path to generate, by default will be infered from first input filename",
    )

    parser.add_argument(
        "--target",
        "-t",
        type=str,
        required=False,
        help="Target compilation triplet. By default target is infered from host system. Cross-compilation is not supported so that argument is a bit odd and cannot properly be used.",
        choices=["amd64-unknown-linux", "arm64-apple-darwin", "amd64-unknown-windows"],
    )

    parser.add_argument(
        "--output-format",
        "-of",
        type=str,
        required=False,
        help="Compilation output format. Useful if you want to emit '.o' object-file.",
        default="executable",
        choices=["object", "executable", "library", "assembly"],
    )

    parser.add_argument(
        "-hir",
        required=False,
        action="store_true",
        help="If passed will just emit IR (high-level) of provided file(s) into stdin.",
    )

    parser.add_argument(
        "--display-lir",
        dest="lir",
        required=False,
        action="store_true",
        help="If passed will just emit IR (low-level, codegen specific) of provided file(s) into stdin.",
    )

    parser.add_argument(
        "--debug-symbols",
        "-g",
        required=False,
        action="store_true",
        help="If passed will provide debug symbols into final target output.",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        required=False,
        action="store_true",
        help="If passed will enable INFO level logs from compiler.",
    )

    parser.add_argument(
        "--execute",
        "-e",
        required=False,
        action="store_true",
        help="If provided, will execute output executable file after compilation. Expects output format to be executable",
    )

    parser.add_argument(
        "--include",
        "-i",
        required=False,
        help="Additional directories to search for include files.",
        action="append",
        nargs="?",
        default=[],
    )

    parser.add_argument(
        "--assembler",
        "-Af",
        required=False,
        help="Additional flags passed to assembler (`as`)",
        action="append",
        nargs="?",
        default=[],
    )

    parser.add_argument(
        "--cache-dir",
        "-cd",
        type=str,
        default="./.build",
        required=False,
        help="Path to directory where to store cache (defaults to current directory)",
    )
    parser.add_argument(
        "--delete-cache",
        "-dc",
        action="store_true",
        required=False,
        help="If passed, will delete cache after run",
    )

    parser.add_argument(
        "--skip-typecheck",
        "-nt",
        action="store_true",
        required=False,
        help="If passed, will disable type safety checking",
    )

    parser.add_argument(
        "--profile",
        dest="profile",
        required=False,
        default="debug",
        choices=["debug", "production"],
        help="Configures some underlying tools to use that profile. TBD",
    )

    _inject_preprocessor_group(parser)
    _inject_linker_group(parser)
    _inject_optimizer_group(parser)
    return parser


def _inject_preprocessor_group(parser: ArgumentParser) -> None:
    """Construct and inject argument group with preprocessor options into given parser."""
    group = parser.add_argument_group(
        title="Preprocessor",
        description="Flags for the preprocessor.",
    )
    group.add_argument(
        "--preprocess-only",
        "--pp",
        "-P",
        default=False,
        action="store_true",
        help="If passed will emit preprocessed text of an source",
    )
    group.add_argument(
        "--define",
        "-D",
        required=False,
        help="Define an macro (default value is '1') and propagate to all input source files",
        action="append",
        nargs="?",
        dest="definitions",
        default=[],
    )


def _inject_linker_group(parser: ArgumentParser) -> None:
    """Construct and inject argument group with linker options into given parser."""
    group = parser.add_argument_group(
        title="Linker",
        description="Flags for the linker, granually control how linker links your objects.",
    )

    group.add_argument(
        "--library-search-path",
        "-L",
        dest="linker_libraries_search_paths",
        required=False,
        help="Paths where to search for linker libraries",
        action="append",
        nargs="?",
        default=[],
    )

    group.add_argument(
        "--linker-flag",
        "-alf",
        dest="linker_additional_flags",
        required=False,
        help="Additional flags passed to specified linker",
        action="append",
        nargs="?",
        default=[],
    )

    group.add_argument(
        "--no-pkgconfig",
        dest="linker_resolve_libraries_with_pkconfig",
        default=True,
        action="store_false",
        help="Disable usage of `pkg-confg` to resolve linker search paths if possible",
    )
    group.add_argument(
        "--library",
        "--lib",
        "-l",
        dest="linker_libraries",
        required=False,
        help="Libraries against which to link",
        action="append",
        nargs="?",
        default=[],
    )

    group.add_argument(
        "--linker-backend",
        type=str,
        required=False,
        default=None,
        dest="linker_backend",
        help="Linker backend to use (e.g linker)",
        choices=["gnu-ld", "apple-ld"],
    )

    group.add_argument(
        "--linker-executable",
        type=str,
        required=False,
        default=None,
        dest="linker_executable",
        help="Linker backend executable path to use",
    )


def _inject_optimizer_group(parser: ArgumentParser) -> None:
    """Construct and inject argument group with optimizer options into given parser."""
    group = parser.add_argument_group(
        title="Optimizations",
        description="Flags for the optimizer, granually control how compiler optimize your code.",
    )

    ###
    # Optimization level.
    ###
    group_optimization_level = group.add_mutually_exclusive_group()
    group_optimization_level.add_argument(
        "-O0",
        dest="optimizer_level",
        action="store_const",
        default=0,
        const=0,
        help="Disable all optimizations (default).",
    )
    group_optimization_level.add_argument(
        "-O1",
        dest="optimizer_level",
        action="store_const",
        const=1,
        help="Apply basic optimizations.",
    )

    ###
    # DCE (dead-code-elimination).
    ###
    group_dce = group.add_mutually_exclusive_group()
    group_dce.add_argument(
        "-fdce",
        dest="optimizer_do_dead_code_elimination",
        action="store_const",
        const=True,
        help="[Enabled at -O1 and above] Force enable DCE (dead-code-elimination) optimization. Removes unused functions (no calls to them inside final program), except explicit 'global' ones.",
    )
    group_dce.add_argument(
        "-fno-dce",
        action="store_const",
        const=False,
        dest="optimizer_do_dead_code_elimination",
        help="[Enabled at -O1 and above] Force disable DCE (dead-code-eliminiation) optimization, see '-fdce' flag for more information.",
    )
    group_dce.add_argument(
        "--dce-max-iterations",
        metavar="<N>",
        dest="optimizer_dead_code_elimination_max_iterations",
        help="Max iterations limit for DCE optimization. Low limit may result into not all functions are being removed due to their reference to each in cascade.",
    )

    ###
    # Function inlining
    ###
    group_inline = group.add_mutually_exclusive_group()
    group_inline.add_argument(
        "-finline-functions",
        dest="optimizer_do_function_inlining",
        action="store_const",
        const=True,
        help="[Enabled at -O1 and above] Force enable function inlining optimization. Marks small functions as 'inline' (size is controlled with '--inline-functions-threshold') to reduce function overhead.",
    )
    group_inline.add_argument(
        "-fno-inline-functions",
        action="store_const",
        const=False,
        dest="optimizer_do_function_inlining",
        help="[Enabled at -O1 and above] Force disable function inlining optimization, see '-finline-functions' flag for more information.",
    )
    group_inline.add_argument(
        "--inline-functions-max-operators",
        metavar="<N>",
        dest="optimizer_function_inlining_max_operators",
        help="Max size of an function to be inlined with function inlining optimization in operators",
    )
    group_inline.add_argument(
        "--inline-functions-max-iterations",
        metavar="<N>",
        dest="optimizer_function_inlining_max_iterations",
        help="Max iterations for function inlining to search for new inlined function usage in other functions. Low limit will result into unknown function call at assembler stage. This may slightly increase finaly binary size",
    )
