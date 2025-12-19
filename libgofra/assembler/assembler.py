"""Assembler module to assemble programs in Gofra language into executables."""

from __future__ import annotations

from subprocess import CompletedProcess, run
from typing import TYPE_CHECKING

from gofra.cli.output import cli_fatal_abort

from .clang import clang_driver_is_installed, compose_clang_assembler_command

if TYPE_CHECKING:
    from pathlib import Path

    from libgofra.targets import Target


def assemble_object_from_codegen_assembly(
    assembly: Path,
    output: Path,
    target: Target,
    *,
    debug_information: bool,
    additional_assembler_flags: list[str],
) -> CompletedProcess[bytes]:
    """Convert given program into object using assembler for next linkage step."""
    if not clang_driver_is_installed():
        cli_fatal_abort("Clang driver is not installed, cannot assemble, aborting!")

    clang_command = compose_clang_assembler_command(
        assembly,
        output,
        target=target,
        debug_information=debug_information,
        additional_assembler_flags=additional_assembler_flags,
    )
    process = run(
        clang_command,
        check=False,
        capture_output=False,
    )
    process.check_returncode()
    return process
