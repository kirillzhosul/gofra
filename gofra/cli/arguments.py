from __future__ import annotations

import sys
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from platform import system as current_platform_system
from typing import TYPE_CHECKING

from gofra.cli.output import cli_message

if TYPE_CHECKING:
    from gofra.assembler.assembler import OUTPUT_FORMAT_T
    from gofra.codegen.targets import TARGET_T


@dataclass(frozen=True)
class CLIArguments:
    """Arguments from argument parser provided for whole Gofra toolchain process."""

    source_filepaths: list[Path]
    output_filepath: Path
    output_format: OUTPUT_FORMAT_T

    execute_after_compilation: bool
    debug_symbols: bool

    include_paths: list[Path]

    ir: bool

    linker_flags: list[str]
    assembler_flags: list[str]

    verbose: bool

    target: TARGET_T

    disable_optimizations: bool
    skip_typecheck: bool

    build_cache_dir: Path
    delete_build_cache: bool


def parse_cli_arguments(prog: str) -> CLIArguments:
    """Parse CLI arguments from argparse into custom DTO."""

    args = _construct_argument_parser(prog=prog).parse_args()
    if len(args.source_files) > 1:
        cli_message(
            level="ERROR",
            text="Compiling several files not implemented.",
        )
        sys.exit(1)

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

    target: TARGET_T = args.target or infer_target()
    assert target in ("x86_64-linux", "aarch64-darwin")

    source_filepaths = [Path(f) for f in args.source_files]
    output_filepath = (
        Path(args.output)
        if args.output
        else infer_output_filename(source_filepaths, output_format=args.output_format)
    )
    include_paths = [
        Path("./"),
        *[f.parent for f in source_filepaths],
        *map(Path, [include for include in args.include if include]),
    ]

    assembler_flags = args.assembler
    if bool(args.debug_symbols):
        assembler_flags += ["-g"]

    return CLIArguments(
        debug_symbols=bool(args.debug_symbols),
        ir=bool(args.ir),
        source_filepaths=source_filepaths,
        output_filepath=output_filepath,
        output_format=args.output_format,
        execute_after_compilation=bool(args.execute),
        delete_build_cache=bool(args.delete_cache),
        build_cache_dir=Path(args.cache_dir),
        target=target,
        disable_optimizations=bool(args.disable_optimizations),
        skip_typecheck=bool(args.skip_typecheck),
        include_paths=include_paths,
        verbose=bool(args.verbose),
        linker_flags=args.linker,
        assembler_flags=assembler_flags,
    )


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
        help="Source code files in Gofra (`.gof` files)",
        nargs="+",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        required=False,
        help="Path to output file to generate, by default will be infered from first input filename, also infers build cache filenames from that",
    )

    parser.add_argument(
        "--target",
        "-t",
        type=str,
        required=False,
        help="Compilation target. Infers codegen to use from that.",
        choices=["x86_64-linux", "aarch64-darwin"],
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
        "-ir",
        required=False,
        action="store_true",
        help="If passed will just emit IR of provided file(s) into stdin.",
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
        help="Additional directories to search for include files. Default: ['./', './lib']",
        action="append",
        nargs="?",
        default=["./", "./lib"],
    )

    parser.add_argument(
        "--linker",
        "-Lf",
        required=False,
        help="Additional flags passed to linker (`ld`)",
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
        "--disable-optimizations",
        "-no",
        action="store_true",
        required=False,
        help="If passed, all optimizations will be disable (DCE, CF)",
    )

    parser.add_argument(
        "--skip-typecheck",
        "-nt",
        action="store_true",
        required=False,
        help="If passed, will disable type safety checking",
    )

    return parser


def infer_output_filename(  # noqa: PLR0911
    source_filepaths: list[Path],
    output_format: OUTPUT_FORMAT_T,
) -> Path:
    """Try to infer filename for output from input source files."""
    assert source_filepaths

    source_filepath = source_filepaths[0]

    match output_format:
        case "library":
            return source_filepath.with_suffix(".dylib")
        case "object":
            return source_filepath.with_suffix(".o")
        case "assembly":
            return source_filepath.with_suffix(".s")
        case _:
            ...
    match current_platform_system():
        case "Darwin":
            match output_format:
                case "executable":
                    if source_filepath.suffix == "":
                        return source_filepath.with_suffix("._")
                    return source_filepath.with_suffix("")
        case "Linux":
            match output_format:
                case "executable":
                    if source_filepath.suffix == "":
                        return source_filepath.with_suffix(source_filepath.suffix + "_")
                    return source_filepath.with_suffix("")
        case _:
            cli_message(
                level="ERROR",
                text="Unable to infer output filepath due to no fallback for current operating system",
            )
            sys.exit(1)


def infer_target() -> TARGET_T:
    """Try to infer target from current system."""
    assert current_platform_system() in ["Darwin", "Linux"]

    match current_platform_system():
        case "Darwin":
            return "aarch64-darwin"
        case "Linux":
            return "x86_64-linux"
        case _:
            cli_message(
                level="ERROR",
                text="Unable to infer compilation target due to no fallback for current operating system",
            )
            sys.exit(1)
