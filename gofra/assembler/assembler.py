"""Assembler module to assemble programs in Gofra language into executables."""

from __future__ import annotations

import sys
from platform import system as current_platform_system
from shutil import which
from subprocess import CalledProcessError, check_output
from typing import TYPE_CHECKING

from gofra.cli.output import cli_message

from .exceptions import (
    NoToolkitForAssemblingError,
    UnsupportedBuilderOperatingSystemError,
)

if TYPE_CHECKING:
    from pathlib import Path

    from gofra.targets import Target


class CommandExecutor:
    verbose: bool

    def __init__(self, *, verbose: bool) -> None:
        self.verbose = verbose

    def execute(self, command: list[str], description: str) -> None:
        cli_message(
            level="INFO",
            text=f"{description}: `{' '.join(command)}`...",
            verbose=self.verbose,
        )
        try:
            check_output(command)
        except CalledProcessError as e:
            error_msg = f"Command failed with code {e.returncode}"
            if description:
                error_msg = f"{description} failed: {error_msg}"
            cli_message("ERROR", error_msg)
            sys.exit(1)


def assemble_object(  # noqa: PLR0913
    assembly_file: Path,
    output: Path,
    target: Target,
    *,
    build_cache_dir: Path,
    verbose: bool,
    additional_assembler_flags: list[str],
) -> None:
    """Convert given program into executable/library/etc using assembly and linker."""
    _validate_toolkit_installation()

    object_filepath = (build_cache_dir / output.name).with_suffix(
        target.file_object_suffix,
    )

    runner = CommandExecutor(verbose=verbose)

    # Assembler is not cross-platform so we expect host has same architecture
    match current_platform_system():
        case "Darwin":
            if target.triplet != "arm64-apple-darwin":
                raise UnsupportedBuilderOperatingSystemError
            assembler_flags = ["-arch", "arm64"]
        case "Linux":
            if target.triplet != "amd64-unknown-linux":
                raise UnsupportedBuilderOperatingSystemError
            assembler_flags = []
        case _:
            raise UnsupportedBuilderOperatingSystemError

    command = [
        "/usr/bin/as",
        "-o",
        str(object_filepath),
        str(assembly_file),
        *assembler_flags,
        *additional_assembler_flags,
    ]
    runner.execute(command, description="Running assemble")


def _validate_toolkit_installation() -> None:
    """Validate that the host system has all requirements installed (linker/assembler)."""
    required_toolkit = ("as",)
    toolkit = {(tk, which(tk) is not None) for tk in required_toolkit}
    missing_toolkit = {tk for (tk, tk_is_installed) in toolkit if not tk_is_installed}
    if missing_toolkit:
        raise NoToolkitForAssemblingError(toolkit_required=missing_toolkit)


def prepare_build_cache_directory(build_cache_directory: Path) -> None:
    """Try to create and fill cache directory with required files."""
    if build_cache_directory.exists():
        return

    build_cache_directory.mkdir(exist_ok=False)

    with (build_cache_directory / ".gitignore").open("w") as f:
        f.write("# Do not include this newly generated build cache into git VCS\n")
        f.write("*\n")
