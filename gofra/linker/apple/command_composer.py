from collections.abc import Iterable, MutableSequence
from pathlib import Path
from typing import Literal, assert_never

from gofra.linker.apple.architectures import (
    APPLE_LINKER_ARCHITECTURES,
    apple_linker_architecture_from_target,
)
from gofra.linker.apple.libraries import (
    APPLE_LINKER_DEFAULT_LIBRARIES_SEARCH_PATHS,
    get_syslibroot_path,
    syslibroot_is_required,
)
from gofra.linker.apple.output_format import (
    AppleLinkerOutputFormat,
    AppleLinkerOutputFormatKindFlag,
)
from gofra.linker.apple.platforms import APPLE_LINKER_PLATFORMS
from gofra.linker.entry_point import LINKER_EXPECTED_ENTRY_POINT
from gofra.linker.output_format import LinkerOutputFormat
from gofra.linker.profile import LinkerProfile
from gofra.targets.target import Target

# TODO(@kirillzhosul): Research `lipo` tool and maybe other ones for Mach-O workflow (nm, otool, lipo, arch, dyld, strip, rebase, dyld_info, as, ar)
# TODO(@kirillzhosul): Add potential use of `-version_details` flag to check for supported architectures

APPLE_LD_DEFAULT_PATH = Path("ld")


def compose_apple_linker_command(  # noqa: PLR0913
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
    """General driver for Apple linker."""
    if target.operating_system != "Darwin":
        msg = "Cannot compose Apple linker driver command for non Darwin target! Apple linker may link only Darwin objects (Mach-O only)"
        raise ValueError(msg)

    macho_format = {
        LinkerOutputFormat.LIBRARY: AppleLinkerOutputFormat.SHARED_LIBRARY,
        LinkerOutputFormat.EXECUTABLE: AppleLinkerOutputFormat.EXECUTABLE,
        LinkerOutputFormat.OBJECT: AppleLinkerOutputFormat.OBJECT_FILE,
    }[output_format]

    if macho_format == AppleLinkerOutputFormat.EXECUTABLE:
        libraries.append("System")

    syslibroot = None
    if syslibroot_is_required(libraries, macho_format):
        syslibroot = get_syslibroot_path()

    strip_debug_symbols = profile == LinkerProfile.PRODUCTION
    debug_do_not_optimize = profile == LinkerProfile.DEBUG

    architecture = apple_linker_architecture_from_target(target)
    return compose_raw_apple_linker_command(
        objects=objects,
        output=output,
        architecture=architecture,
        system_library_root=syslibroot,
        output_format=macho_format,
        additional_flags=additional_flags,
        executable_entry_point_symbol=executable_entry_point_symbol,
        # Libraries and frameworks
        libraries=set(libraries),
        libraries_search_paths={
            *APPLE_LINKER_DEFAULT_LIBRARIES_SEARCH_PATHS,
            *libraries_search_paths,
        },
        # Cache
        cache_path_lto=cache_directory,
        # Debug
        debug_do_not_optimize=debug_do_not_optimize,
        strip_debug_symbols=strip_debug_symbols,
        # TODO(@kirillzhosul): Implement platform_version
        _linker_executable=linker_executable or APPLE_LD_DEFAULT_PATH,
    )


def compose_raw_apple_linker_command(  # noqa: PLR0913
    objects: Iterable[Path],
    output: Path,
    *,
    system_library_root: Path | None = None,
    architecture: APPLE_LINKER_ARCHITECTURES | None = None,
    output_format_kinds: Iterable[AppleLinkerOutputFormatKindFlag] | None = None,
    output_format: AppleLinkerOutputFormat = AppleLinkerOutputFormat.EXECUTABLE,
    libraries: Iterable[str] | None = None,
    libraries_search_paths: Iterable[Path] | None = None,
    frameworks_search_paths: Iterable[Path] | None = None,
    dtrace_script: Path | None = None,
    debug_do_not_optimize: bool = False,
    strip_debug_symbols: bool = False,
    optim_dead_strip: bool = True,
    additional_flags: Iterable[str] | None = None,
    macos_version_min: float | None = None,
    ios_version_min: float | None = None,
    executable_entry_point_symbol: str | None = LINKER_EXPECTED_ENTRY_POINT,
    cache_path_lto: Path | None = None,
    platform_version: tuple[APPLE_LINKER_PLATFORMS, float, float] | None = None,
    _linker_executable: Path = Path("ld"),
    _absolute_paths: bool = False,
) -> list[str]:
    """Compose command to Apple Linker CLI tool.

    Taken from `man ld`
    DOES NOT raise any validation errors - as it is work of Apple Linker itself and its command result

    :param system_library_root: Path to system library SDK
        Required for EXECUTABLE and DYNAMIC, but may be omitted for others
        Obtained via xcrun (`xcrun -sdk macosx --show-sdk-path`) or located in `SYSTEM_LIBRARY_ROOT_DIRECTORY` constant

    :param architecture: Arch of the final output, inferred by default from object files but explicit is better than implicit
    :param output_format_kinds: Additional KIND for output, according to current implementation must not be passed or default one (DYNAMIC)
    :param output_format: Format of output, usable ones is EXECUTABLE, SHARED_LIBRARY, OBJECT_FILE
    :param libraries: List of libraries to link with
    :param libraries_search_paths: Paths to search for libraries
    :param debug_do_not_optimize: If passed will skip some internal optimizations
    :param debug_remove_info: If passed, will strip all debug information
    :param optim_dead_strip: If passed, will perform DCE on LTO pass
    :param additional_flags: Any arbitrary linker flags to pass (as not all listed here, beside obscured ones)
    :param executable_entry_point_symbol: Executable format name of symbol for runtime execution startup (_start is default as in crt1.0)
    :param cache_path_lto: Path of cache directory for LTO
    :param frameworks_search_paths:
    :param dtrace_script:
    :param platform_version:
    :param ios_version_min:
    :param macos_version_min:
    :param _linker_executable: Path to executable of Apple Linker to use
    :param _absolute_paths: If true, will always make all paths absolute
    """
    command: list[str] = [
        str(_linker_executable.absolute())
        if _absolute_paths
        else str(_linker_executable),
    ]  # Call to an Apple LD

    # Specify input object files
    if _absolute_paths:
        command.extend(str(p.absolute()) for p in objects)
    else:
        command.extend(map(str, objects))

    # Libraries to link with
    if libraries:
        command.extend(f"-l{library}" for library in libraries)

    # Maybe removed later, as we may use some plugins
    command.append("-no_exported_symbols")

    if system_library_root:
        path = (
            str(system_library_root.absolute())
            if _absolute_paths
            else str(system_library_root)
        )
        command.extend(("-syslibroot", path))

    # Do not search standard directories, we will propagate them by own
    command.append("-Z")

    # Treat warnings as errors and additional warnings
    command.extend(("-fatal_warnings", "-arch_errors_fatal"))
    command.extend(("-warn_duplicate_libraries",))

    # Architecture, may be inferred but we explicitly specify that
    # there is possibility of passing multiple architectures for *thin* output but we step away from that at current moment
    if architecture:
        command.extend(("-arch", architecture))

    # Main executable entry point
    if executable_entry_point_symbol:
        command.extend(("-e", executable_entry_point_symbol))

    # Output format
    format_kind_flags = _get_output_format_kind_flags(
        output_format_kinds or [AppleLinkerOutputFormatKindFlag.DYNAMIC],
    )
    command.append(_get_output_format_flag(output_format))
    command.extend(format_kind_flags)

    # Libraries and frameworks search paths
    if libraries_search_paths:
        command.extend(f"-L{p}" for p in libraries_search_paths)
    if frameworks_search_paths:
        command.extend(f"-F{p}" for p in frameworks_search_paths)

    # Actual output path
    path = str(output.absolute()) if _absolute_paths else str(output)
    command.extend(("-o", path))

    if cache_path_lto:
        path = str(cache_path_lto.absolute() if _absolute_paths else cache_path_lto)
        command.extend(("-cache_path_lto", path))

    # dtrace static probes script
    if dtrace_script:
        path = str(dtrace_script.absolute() if _absolute_paths else dtrace_script)
        command.extend(("-dtrace", path))

    # Propagated linker flags from above.
    if additional_flags:
        command.extend(additional_flags)

    # Do not perform some optimizations
    # must only be enabled for debug builds
    if debug_do_not_optimize:
        command.append("-O0")

    # Skips DFARF/STABS information
    if strip_debug_symbols:
        command.append("-S")

    # Specification of version to assume features of that OS/SDK
    if platform_version:
        platform, min_version, sdk_version = platform_version
        platform_version_flag = (
            platform,
            str(round(min_version, 2)),
            str(round(sdk_version, 2)),
        )
        command.extend(("-platform_version", *platform_version_flag))
    if macos_version_min:
        command.extend(("-macos_version_min", str(round(macos_version_min, 2))))
    if ios_version_min:
        command.extend(("-macos_version_min", str(round(ios_version_min, 2))))

    # Optimizations
    if optim_dead_strip:
        command.append("-dead_strip")  # DCE on Linker stage

    return command


def _get_output_format_flag(
    output_format: AppleLinkerOutputFormat,
) -> Literal[
    "-execute",
    "-dylib",
    "-bundle",
    "-r",
    "-dylinker",
]:
    """Translate `AppleLinkerOutputFormat` into LD CLI flag."""
    match output_format:
        case AppleLinkerOutputFormat.EXECUTABLE:
            return "-execute"
        case AppleLinkerOutputFormat.SHARED_LIBRARY:
            return "-dylib"
        case AppleLinkerOutputFormat.BUNDLE:
            return "-bundle"
        case AppleLinkerOutputFormat.OBJECT_FILE:
            return "-r"
        case AppleLinkerOutputFormat.DYLINKER:
            return "-dylinker"
        case _:
            assert_never(output_format)


def _get_output_format_kind_flags(
    output_format_kinds: Iterable[AppleLinkerOutputFormatKindFlag],
) -> set[Literal["-static", "-preload", "-dynamic"]]:
    """Translate `AppleLinkerOutputFormatKindFlag` into LD CLI flags."""
    flags: set[Literal["-static", "-preload", "-dynamic"]] = set()
    for kind in output_format_kinds:
        match kind:
            case AppleLinkerOutputFormatKindFlag.DYNAMIC:
                flags.add("-dynamic")
            case AppleLinkerOutputFormatKindFlag.STATIC:
                flags.add("-static")
            case AppleLinkerOutputFormatKindFlag.PRELOAD:
                flags.add("-preload")
            case _:
                assert_never(kind)
    return flags
