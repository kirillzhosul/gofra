"""Assembler module to assemble programs in Gofra language into executables."""

from __future__ import annotations

import sys
from platform import system as current_platform_system
from shutil import which
from subprocess import CalledProcessError, check_output
from typing import TYPE_CHECKING, Literal

from gofra.cli.output import cli_message
from gofra.codegen import generate_code_for_assembler
from gofra.codegen.get_backend import get_backend_for_target

from .exceptions import (
    NoToolkitForAssemblingError,
    UnsupportedBuilderOperatingSystemError,
)

if TYPE_CHECKING:
    from pathlib import Path

    from gofra.context import ProgramContext
    from gofra.targets import Target

type OUTPUT_FORMAT_T = Literal["library", "executable", "object", "assembly"]


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


def assemble_program(  # noqa: PLR0913
    context: ProgramContext,
    output: Path,
    output_format: OUTPUT_FORMAT_T,
    target: Target,
    *,
    build_cache_dir: Path,
    verbose: bool,
    additional_assembler_flags: list[str],
    delete_build_cache_after_compilation: bool,
) -> list[Path] | None:
    """Convert given program into executable/library/etc using assembly and linker."""
    _validate_toolkit_installation()
    _prepare_build_cache_directory(build_cache_dir)

    assembly_filepath = _generate_assembly_file_with_codegen(
        context,
        target,
        output,
        build_cache_dir=build_cache_dir,
        verbose=verbose,
    )

    if output_format == "assembly":
        assembly_filepath.replace(output)
        return None

    object_filepath = _assemble_object_file(
        target,
        assembly_filepath,
        output,
        additional_assembler_flags=additional_assembler_flags,
        build_cache_dir=build_cache_dir,
        verbose=verbose,
    )
    if output_format == "object":
        object_filepath.replace(output)
        if delete_build_cache_after_compilation:
            assembly_filepath.unlink()
        return None

    if delete_build_cache_after_compilation:
        assembly_filepath.unlink()
        # TODO(@kirillzhosul): After refactoring unlinking object file is not more implemented
        # object_filepath.unlink()  # noqa: ERA001

    return [object_filepath]


def _prepare_build_cache_directory(build_cache_directory: Path) -> None:
    """Try to create and fill cache directory with required files."""
    if build_cache_directory.exists():
        return

    build_cache_directory.mkdir(exist_ok=False)

    with (build_cache_directory / ".gitignore").open("w") as f:
        f.write("# Do not include this newly generated build cache into git VCS\n")
        f.write("*\n")


def _assemble_object_file(  # noqa: PLR0913
    target: Target,
    asm_filepath: Path,
    output: Path,
    *,
    build_cache_dir: Path,
    additional_assembler_flags: list[str],
    verbose: bool,
) -> Path:
    """Call assembler to assemble given assembly file from codegen."""
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
        str(asm_filepath),
        *assembler_flags,
        *additional_assembler_flags,
    ]
    runner.execute(command, description="Running assemble")
    return object_filepath


def _generate_assembly_file_with_codegen(
    context: ProgramContext,
    target: Target,
    output: Path,
    *,
    build_cache_dir: Path,
    verbose: bool,
) -> Path:
    """Call desired codegen backend for requested target and generate file contains assembly."""
    assembly_filepath = (build_cache_dir / output.name).with_suffix(
        target.file_assembly_suffix,
    )

    inferred_backend = get_backend_for_target(target).__name__  # type: ignore  # noqa: PGH003
    cli_message(
        level="INFO",
        text=f"Generating assembly using codegen backend (Inferred codegen for target `{target}` is `{inferred_backend}`)...",
        verbose=verbose,
    )
    generate_code_for_assembler(assembly_filepath, context, target)
    return assembly_filepath


def _validate_toolkit_installation() -> None:
    """Validate that the host system has all requirements installed (linker/assembler)."""
    match current_platform_system():
        case "Darwin":
            required_toolkit = ("as", "ld", "xcrun")
        case "Linux":
            required_toolkit = ("as", "ld")
        case _:
            raise UnsupportedBuilderOperatingSystemError
    toolkit = {(tk, which(tk) is not None) for tk in required_toolkit}
    missing_toolkit = {tk for (tk, tk_is_installed) in toolkit if not tk_is_installed}
    if missing_toolkit:
        raise NoToolkitForAssemblingError(toolkit_required=missing_toolkit)
