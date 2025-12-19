# Path to binary with clang (e.g `CC`)
# Both Apple Clang / base Clang is allowed
from collections.abc import Iterable
from pathlib import Path
from platform import system
from shutil import which
from typing import assert_never

from libgofra.targets.target import Target

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
        case "arm64-apple-darwin" | "amd64-unknown-linux" | "amd64-unknown-windows":
            clang_target = target.triplet
        case _:
            assert_never(target.triplet)

    command.extend(("-target", clang_target))

    # Treat and pass input as an assembly file - we are in assembler module
    # and use Clang only as assembler
    command.extend(("-c", "-x", "assembler", str(machine_assembly_file)))

    # Remove
    command.append("-nostdlib")

    if debug_information:
        command.append("-g")

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


def clang_driver_is_installed() -> bool:
    return which(CLANG_EXECUTABLE_PATH) is not None
