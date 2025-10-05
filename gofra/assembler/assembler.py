"""Assembler module to assemble programs in Gofra language into executables."""

from __future__ import annotations

from pathlib import Path
from platform import system
from subprocess import CompletedProcess, run
from typing import TYPE_CHECKING, assert_never

if TYPE_CHECKING:
    from collections.abc import Iterable

    from gofra.targets import Target


def assemble_object_from_codegen_assembly(
    assembly: Path,
    output: Path,
    target: Target,
    *,
    debug_information: bool,
    additional_assembler_flags: list[str],
) -> CompletedProcess[bytes]:
    """Convert given program into object using assembler for next linkage step."""
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


# Path to binary with clang (e.g `CC`)
# Both Apple Clang / base Clang is allowed
CLANG_EXECUTABLE_PATH = Path("/usr/bin/clang")


def compose_clang_assembler_command(  # noqa: PLR0913
    machine_assembly_file: Path,
    output_object_file: Path,
    target: Target,
    *,
    additional_assembler_flags: Iterable[str],
    debug_information: bool,
    verbose: bool = False,
) -> list[str]:
    """Compose command for clang driver to be used as assembler."""
    command = [str(CLANG_EXECUTABLE_PATH)]

    match target.triplet:
        case "arm64-apple-darwin":
            command.extend(("-target", "arm64-apple-darwin"))
        case "amd64-unknown-linux":
            command.extend(("-target", "arm64-apple-darwin"))
        case "amd64-unknown-windows":
            msg = (
                "Dont know how to assemble with clang for amd64-unknown-windows target"
            )
            raise NotImplementedError(msg)
        case _:
            assert_never(target.triplet)

    # Treat and pass input as an assembly file - we are in assembler module
    # and use Clang only as assembler
    command.extend(("-c", "-x", "assembler", str(machine_assembly_file)))

    # Remove
    command.append("-nostdlib")

    if debug_information:
        command.append("-g")
        dwarf_debug_producer = "Gofra with Clang assembler backend"
        command.extend(("-dwarf-debug-producer", f'"{dwarf_debug_producer}"'))

    # Emit all commands and information that clang runs
    if verbose:
        command.append("-v")

    ### Apple Clang specific
    command.append("-integrated-as")
    # Quite wrong assumption - but stick to that for now
    is_apple_clang = system() == "Darwin"
    if is_apple_clang and target.architecture == "ARM64":
        command.extend(("-arch", "arm64"))

    command.extend(additional_assembler_flags)
    command.extend(("-o", str(output_object_file)))
    return command
