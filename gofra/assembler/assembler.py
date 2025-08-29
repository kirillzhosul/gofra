"""Assembler module to assemble programs in Gofra language into executables."""

from __future__ import annotations

import sys
from pathlib import Path
from platform import system as current_platform_system
from shutil import which
from subprocess import CalledProcessError, check_output
from typing import TYPE_CHECKING, Literal

from gofra.cli.output import cli_message
from gofra.codegen import generate_code_for_assembler
from gofra.codegen.backends.general import CODEGEN_ENTRY_POINT_SYMBOL
from gofra.codegen.get_backend import get_backend_for_target

from .exceptions import (
    NoToolkitForAssemblingError,
    UnsupportedBuilderOperatingSystemError,
)

if TYPE_CHECKING:
    from gofra.codegen.targets import TARGET_T
    from gofra.context import ProgramContext

type OUTPUT_FORMAT_T = Literal["library", "executable", "object", "assembly"]


def assemble_program(  # noqa: PLR0913
    context: ProgramContext,
    output: Path,
    output_format: OUTPUT_FORMAT_T,
    target: TARGET_T,
    *,
    build_cache_dir: Path,
    verbose: bool,
    additional_linker_flags: list[str],
    additional_assembler_flags: list[str],
    delete_build_cache_after_compilation: bool,
    link_with_system_libraries: bool,
) -> None:
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
        return

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
        return

    assert output_format in ("executable", "library")
    _link_final_output(
        output,
        target,
        object_filepath,
        output_format=output_format,
        link_with_system_libraries=link_with_system_libraries,
        additional_linker_flags=additional_linker_flags,
        verbose=verbose,
    )

    if delete_build_cache_after_compilation:
        assembly_filepath.unlink()
        object_filepath.unlink()


def _prepare_build_cache_directory(build_cache_directory: Path) -> None:
    """Try to create and fill cache directory with required files."""
    if build_cache_directory.exists():
        return

    build_cache_directory.mkdir(exist_ok=False)

    with (build_cache_directory / ".gitignore").open("w") as f:
        f.write("# Do not include this newly generated build cache into git VCS\n")
        f.write("*\n")


def _link_final_output(  # noqa: PLR0913
    output: Path,
    target: TARGET_T,
    o_filepath: Path,
    output_format: Literal["executable", "library"],
    additional_linker_flags: list[str],
    link_with_system_libraries: bool,
    *,
    verbose: bool,
) -> None:
    """Use linker to link object file into executable."""
    match current_platform_system():
        case "Darwin":
            assert target == "aarch64-darwin"
            target_linker_flags = ["-arch", "arm64"]

            # TODO(@kirillzhosul): Review default linkage with system library (libc by default)
            if link_with_system_libraries:
                system_sdk = Path(
                    check_output(  # noqa: S603
                        ["/usr/bin/xcrun", "-sdk", "macosx", "--show-sdk-path"],
                        text=True,
                    ).strip(),
                )
                target_linker_flags += ["-lSystem", "-syslibroot", str(system_sdk)]

            if output_format == "library":
                target_linker_flags += ["-dylib"]
        case "Linux":
            assert target == "x86_64-linux"
            assert not link_with_system_libraries, (
                "`--link-system is not supported on Linux target, consider removing that flag for now."
            )
            target_linker_flags = []
            assert output_format == "executable", (
                "Libraries on Linux is not implemented"
            )
        case _:
            raise UnsupportedBuilderOperatingSystemError

    linker_flags = [
        *target_linker_flags,
        *additional_linker_flags,
    ]

    if output_format == "executable":
        linker_flags += ["-e", CODEGEN_ENTRY_POINT_SYMBOL]

    command = ["/usr/bin/ld", "-o", str(output), str(o_filepath), *linker_flags]
    cli_message(
        level="INFO",
        text=f"Running linker command: `{' '.join(command)}`",
        verbose=verbose,
    )
    check_output(command)  # noqa: S603


def _assemble_object_file(  # noqa: PLR0913
    target: TARGET_T,
    asm_filepath: Path,
    output: Path,
    *,
    build_cache_dir: Path,
    additional_assembler_flags: list[str],
    verbose: bool,
) -> Path:
    """Call assembler to assemble given assembly file from codegen."""
    object_filepath = (build_cache_dir / output.name).with_suffix(".o")

    # Assembler is not crossplatform so we expect host has same architecture
    match current_platform_system():
        case "Darwin":
            if target != "aarch64-darwin":
                raise UnsupportedBuilderOperatingSystemError
            assembler_flags = ["-arch", "arm64"]
        case "Linux":
            if target != "x86_64-linux":
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
    cli_message(
        level="INFO",
        text=f"Running command: `{' '.join(command)}`",
        verbose=verbose,
    )
    try:
        check_output(command)  # noqa: S603
    except CalledProcessError as e:
        cli_message(
            "ERROR",
            "Failed to generate binary from output assembly, "
            f"error code: {e.returncode}",
        )
        sys.exit(1)

    return object_filepath


def _generate_assembly_file_with_codegen(
    context: ProgramContext,
    target: TARGET_T,
    output: Path,
    *,
    build_cache_dir: Path,
    verbose: bool,
) -> Path:
    """Call desired codegen backend for requested target and generate file contains assembly."""
    assembly_filepath = (build_cache_dir / output.name).with_suffix(".s")

    infered_backend = get_backend_for_target(target).__name__  # type: ignore  # noqa: PGH003
    cli_message(
        level="INFO",
        text=f"Generating assembly using codegen backend (Infered codegen for target `{target}` is `{infered_backend}`)...",
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
