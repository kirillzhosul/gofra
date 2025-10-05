from collections.abc import Iterable, MutableSequence
from pathlib import Path

from gofra.linker.entry_point import LINKER_EXPECTED_ENTRY_POINT
from gofra.linker.gnu.target_formats import GNU_LINKERTARGET_FORMAT
from gofra.linker.output_format import LinkerOutputFormat
from gofra.linker.profile import LinkerProfile
from gofra.targets.target import Target

GNU_LD_DEFAULT_PATH = Path("ld")


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
    cache_directory: Path,
) -> list[str]:
    """General driver for GNU linker."""
    if target.operating_system not in ("Linux", "Windows"):
        msg = f"Cannot compose GNU linker driver command for non {target.operating_system} operating system! GNU linker may link only Linux / Windows objects (ELF/PE only)"
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
        _linker_executable=linker_executable or GNU_LD_DEFAULT_PATH,
    )


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
    target_format: GNU_LINKERTARGET_FORMAT,
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
