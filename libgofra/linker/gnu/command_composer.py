import platform
from collections.abc import Iterable, MutableSequence
from pathlib import Path
from shutil import which

from gofra.cli.output import cli_message
from libgofra.linker.entry_point import LINKER_EXPECTED_ENTRY_POINT
from libgofra.linker.gnu.target_formats import GNU_LINKER_TARGET_FORMAT
from libgofra.linker.output_format import LinkerOutputFormat
from libgofra.linker.profile import LinkerProfile
from libgofra.targets.target import Target


def compose_gnu_linker_command(  # noqa: PLR0913
    objects: Iterable[Path],
    output: Path,
    target: Target,
    output_format: LinkerOutputFormat,
    libraries: MutableSequence[str],
    additional_flags: list[str],
    libraries_search_paths: list[Path],
    profile: LinkerProfile,
    executable_entry_point_symbol: str = LINKER_EXPECTED_ENTRY_POINT,
    *,
    linker_executable: Path | None = None,
    cache_directory: Path | None = None,
) -> list[str]:
    """General driver for GNU linker."""
    _ = cache_directory
    if target.operating_system not in ("Linux", "Windows"):
        msg = f"Cannot compose GNU linker driver command for {target.operating_system} operating system! GNU linker may link only Linux / Windows objects (ELF/PE only)"
        raise ValueError(msg)

    if output_format != LinkerOutputFormat.EXECUTABLE:
        # TODO(@kirillzhosul, @stepanzubkov): -shared / -dll
        msg = "GNU linker non-executables format is not implemented yet"
        raise NotImplementedError(msg)

    strip_debug_symbols = profile == LinkerProfile.PRODUCTION
    return _compose_raw_gnu_linker_command(
        executable_entry_point_symbol=executable_entry_point_symbol,
        libraries_search_paths=libraries_search_paths,
        strip_debug_symbols=strip_debug_symbols,
        additional_flags=additional_flags,
        libraries=libraries,
        output=output,
        objects=objects,
        target_format="elf64-x86-64",
        _linker_executable=linker_executable or _get_linker_backend_executable_path(),
    )


def _get_linker_backend_executable_path() -> Path:
    """Acquire executable of GNU linker that is installed and suitable on that host system."""
    if platform.system() == "Darwin" and (
        ld := _try_find_macos_cross_compilation_driver()
    ):
        return ld

    # Default
    return Path("ld")


def _try_find_macos_cross_compilation_driver(
    brew_installation_bin: Path = Path("/opt/homebrew/bin/"),
) -> Path | None:
    # MacOS brew workaround for cross-compilation
    gnu_ld = Path("x86_64-linux-gnu-ld")
    brew_macos_gnu_ld = Path(which(gnu_ld) or brew_installation_bin / gnu_ld)
    if brew_macos_gnu_ld.resolve().exists():
        return brew_macos_gnu_ld

    elf_ld = Path("x86_64-elf-ld")
    brew_macos_elf_ld = Path(which(elf_ld) or brew_installation_bin / elf_ld)
    if brew_macos_elf_ld.resolve().exists():
        # Bare metal ELF linker may be unstable for linux
        cli_message("WARNING", "Using ELF linker as no suitable linker backend found!")
        return brew_macos_elf_ld

    return None


def _compose_raw_gnu_linker_command(  # noqa: PLR0913
    objects: Iterable[Path],
    output: Path,
    *,
    libraries: MutableSequence[str] | None = None,
    libraries_search_paths: Iterable[Path] | None = None,
    executable_entry_point_symbol: str | None = LINKER_EXPECTED_ENTRY_POINT,
    executable_dynamic_libraries: bool = False,
    strip_debug_symbols: bool = False,
    additional_flags: Iterable[str] | None = None,
    target_format: GNU_LINKER_TARGET_FORMAT,
    _linker_executable: Path,
    _absolute_paths: bool = False,
) -> list[str]:
    """Compose command to GNU Linker CLI tool.

    Taken from `man ld`
    DOES NOT raise any validation errors - as it is work of GNU Linker itself and its command result
    """
    command: list[str] = [
        str(_linker_executable.absolute())
        if _absolute_paths
        else str(_linker_executable),
    ]  # Call to an GNU LD

    # Architecture and file format
    command.extend(("-b", target_format))

    # TODO(@kirillzhosul, @stepanzubkov): -nostdlib

    # Specify input object files
    if _absolute_paths:
        command.extend(str(p.absolute()) for p in objects)
    else:
        command.extend(map(str, objects))

    # Where to search libraries
    if libraries_search_paths:
        command.extend(f"-L{p}" for p in libraries_search_paths)

    # Libraries to link with
    if libraries:
        command.extend(f"-l{library}" for library in libraries)

    # Main executable entry point
    if executable_entry_point_symbol:
        command.extend(("-e", executable_entry_point_symbol))

    # Make executable an dynamic executable
    if executable_dynamic_libraries:
        command.append("--export-dynamic")
    else:
        command.append("--no-export-dynamic")

    # Remove debug symbols for production builds
    if strip_debug_symbols:
        command.append("--strip-debug")

    # Treat warnings as errors
    command.append("--fatal-warnings")

    # Do not insert legacy (or not so) fields
    command.append("--disable-linker-version")

    # Propagated linker flags from above.
    if additional_flags:
        command.extend(additional_flags)

    # Actual output path
    path = str(output.absolute()) if _absolute_paths else str(output)
    command.extend(("-o", path))

    return command
