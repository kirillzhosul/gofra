from __future__ import annotations

import sys
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from gofra.cli.output import cli_message
from gofra.executable import cli_get_executable_program, warn_on_improper_installation
from libgofra.linker.apple.libraries import APPLE_LINKER_DEFAULT_LIBRARIES_SEARCH_PATHS
from libgofra.linker.entry_point import LINKER_EXPECTED_ENTRY_POINT
from libgofra.linker.output_format import LinkerOutputFormat
from libgofra.linker.profile import LinkerProfile
from libgofra.targets.infer_host import infer_host_target
from libgofra.targets.target import Target


@dataclass(frozen=True)
class CLIArguments:
    """Arguments from argument parser provided for whole Gofra testkit process."""

    files: list[Path]

    output: Path
    output_format: LinkerOutputFormat

    libraries: list[str]
    libraries_search_paths: list[Path]

    executable_entry_point_symbol: str

    profile: LinkerProfile

    linker_backend: Literal["gnu-ld", "apple-ld"] | None
    linker_executable: Path | None
    additional_flags: list[str]
    target: Target


def parse_cli_arguments() -> CLIArguments:
    """Parse CLI arguments from argparse into custom DTO."""
    parser = _construct_argument_parser()
    args = parser.parse_args()

    files = [Path(path) for path in args.files]
    output = Path(args.output)

    libraries_search_paths = [Path(path) for path in args.libraries_search_paths]

    assert args.target in (
        "amd64-unknown-linux",
        "arm64-apple-darwin",
        "amd64-unknown-windows",
        None,
    )
    target = Target.from_triplet(args.target) if args.target else infer_host_target()
    if target is None:
        cli_message(
            level="ERROR",
            text="Unable to infer compilation target due to no fallback for current operating system",
        )
        sys.exit(1)

    if not files:
        cli_message(
            level="ERROR",
            text="No object files specified, has nothing to link",
        )
        sys.exit(1)

    output_format = {
        "executable": LinkerOutputFormat.EXECUTABLE,
        "library": LinkerOutputFormat.LIBRARY,
        "object": LinkerOutputFormat.OBJECT,
    }[args.output_format]

    profile = {"debug": LinkerProfile.DEBUG, "production": LinkerProfile.PRODUCTION}[
        args.profile
    ]

    linker_executable = Path(args.linker_executable) if args.linker_executable else None

    return CLIArguments(
        files=files,
        output=output,
        output_format=output_format,
        additional_flags=args.additional_flags,
        linker_executable=linker_executable,
        libraries_search_paths=libraries_search_paths,
        libraries=args.libraries,
        linker_backend=args.linker_backend,
        target=target,
        profile=profile,
        executable_entry_point_symbol=args.executable_entry_point_symbol,
    )


def _construct_argument_parser() -> ArgumentParser:
    """Get argument parser instance to parse incoming arguments."""
    prog = cli_get_executable_program()
    warn_on_improper_installation(prog)

    parser = ArgumentParser(
        description="Gofra LD - Linker command line interface for Gofra object files. Same linker is used with Gofra toolchain beside it is not called from shell, as `gofra-ld` being only interface for underlying linker API",
        add_help=True,
        usage=f"{prog} files... [options] [-o output_file]",
        allow_abbrev=False,
        prog=prog,
    )

    parser.add_argument(
        "files",
        help="Object files to link",
        nargs="*",
        default=[],
    )

    parser.add_argument(
        "-o",
        dest="output",
        help="Output file that is emitted by linker. Defaults to 'a.out'",
        default="a.out",
        required=False,
    )

    backend_group = parser.add_argument_group("Linker backend")
    backend_group.add_argument(
        "-t",
        required=False,
        dest="target",
        help="Target for inferring linker backend to use, omitted when used with --backend flag",
        choices=["arm64-apple-darwin", "amd64-unknown-linux"],
    )
    backend_group.add_argument(
        "--profile",
        dest="profile",
        required=False,
        default="debug",
        choices=["debug", "production"],
        help="Configures some underlying tools to use that profile. TBD",
    )
    backend_group.add_argument(
        "--linker-executable",
        type=str,
        required=False,
        default=None,
        dest="linker_executable",
        help="Linker backend executable path to use",
    )
    backend_group.add_argument(
        "--linker-backend",
        type=str,
        required=False,
        default=None,
        dest="linker_backend",
        help="Linker backend to use (e.g linker)",
        choices=["gnu-ld", "apple-ld"],
    )

    backend_group.add_argument(
        "-af",
        dest="additional_flags",
        help="Additional flags propagated into linker backend",
    )

    format_group = parser.add_argument_group("Output format")
    format_argument_group = format_group.add_mutually_exclusive_group(required=False)
    format_argument_group.add_argument(
        "-f",
        dest="output_format",
        default="executable",
        help="Output format. By default is executable",
        choices=["library", "object", "executable"],
    )

    format_argument_group.add_argument(
        "-executable",
        dest="output_format",
        const="executable",
        help="Same as -f executable",
        action="store_const",
    )
    format_argument_group.add_argument(
        "-library",
        dest="output_format",
        help="Same as -f library",
        const="library",
        action="store_const",
    )
    format_argument_group.add_argument(
        "-object",
        dest="output_format",
        help="Same as -f object",
        const="object",
        action="store_const",
    )

    libraries_group = parser.add_argument_group(title="Libraries linkage")
    libraries_group.add_argument(
        "-l",
        "--library",
        dest="libraries",
        metavar="library_name",
        nargs="?",
        default=[],
        required=False,
        help="Libraries to link with. Search paths is specified via -L flag",
    )
    libraries_group.add_argument(
        "-L",
        nargs="?",
        required=False,
        dest="libraries_search_paths",
        help="Search for libraries specified in -l flag. When using Apple LD backend",
        default=APPLE_LINKER_DEFAULT_LIBRARIES_SEARCH_PATHS,
    )

    executables_group = parser.add_argument_group(title="Executable format")
    executables_group.add_argument(
        "-e",
        dest="executable_entry_point_symbol",
        help=f"Entry point symbol for executables. Defaults to '{LINKER_EXPECTED_ENTRY_POINT}'",
        default=LINKER_EXPECTED_ENTRY_POINT,
        required=False,
    )

    return parser
