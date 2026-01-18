"""Assembler module to assemble programs in Gofra language into executables."""

from __future__ import annotations

from typing import TYPE_CHECKING

from libgofra.assembler.drivers import AssemblerDriverProtocol, get_assembler_driver
from libgofra.assembler.errors import NoAssemblerDriverError

if TYPE_CHECKING:
    from pathlib import Path
    from subprocess import CompletedProcess

    from libgofra.targets import Target


def assemble_object_file(  # noqa: PLR0913
    in_assembly_file: Path,
    out_object_file: Path,
    target: Target,
    *,
    debug_information: bool,
    extra_flags: list[str] | None = None,
    driver: AssemblerDriverProtocol | None = None,
) -> CompletedProcess[bytes]:
    """Assemble given assembly file into object file using assembler driver.

    You supposed to handle errors by assembler via returned process information

    :param target: Compilation target
    :param in_assembly_file: Path to assembly file as input
    :param out_object_file: Path to object file as output
    :param debug_information: If specified, will pass debug info flag to assembler and specify its version
    :param extra_flags: Any additional flags

    :raises NoAssemblerDriverError: If no suitable driver found
    """
    driver = driver or get_assembler_driver(target)
    if driver is None:
        raise NoAssemblerDriverError(target)

    return driver.assemble(
        target=target,
        in_assembly_file=in_assembly_file,
        out_object_file=out_object_file,
        debug_information=debug_information,
        flags=extra_flags or [],
    )
