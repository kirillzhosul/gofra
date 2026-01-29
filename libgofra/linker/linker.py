from collections.abc import Iterable, MutableSequence
from pathlib import Path
from subprocess import PIPE, CompletedProcess, run

from libgofra.linker.command_composer import (
    LinkerCommandComposer,
    get_linker_command_composer_backend,
)
from libgofra.linker.output_format import LinkerOutputFormat
from libgofra.linker.profile import LinkerProfile
from libgofra.targets.target import Target


def link_object_files(  # noqa: PLR0913
    objects: Iterable[Path],
    output: Path,
    target: Target,
    output_format: LinkerOutputFormat,
    libraries: MutableSequence[str],
    additional_flags: list[str],
    libraries_search_paths: list[Path],
    profile: LinkerProfile,
    cache_directory: Path | None = None,
    *,
    executable_entry_point_symbol: str,
    linker_backend: LinkerCommandComposer | None = None,
    linker_executable: Path | None = None,
) -> CompletedProcess[bytes]:
    """Link given objects into another object (executable / library).

    Runs an new process with linker, returns it for high-level checks.
    """
    if not linker_backend:
        linker_backend = get_linker_command_composer_backend(target)

    command = linker_backend(
        objects=objects,
        target=target,
        output=output,
        libraries=libraries,
        output_format=output_format,
        additional_flags=additional_flags,
        libraries_search_paths=libraries_search_paths,
        executable_entry_point_symbol=executable_entry_point_symbol,
        profile=profile,
        linker_executable=linker_executable,
        cache_directory=cache_directory,
    )

    return run(
        command,
        check=False,
        capture_output=False,
        stdout=PIPE,
        shell=False,
    )


# TODO(@kirillzhosul): logging
