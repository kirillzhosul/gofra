from collections.abc import Iterable, MutableSequence
from pathlib import Path
from platform import system
from typing import Protocol

from gofra.linker.apple.command_composer import compose_apple_linker_command
from gofra.linker.gnu.command_composer import compose_gnu_linker_command
from gofra.linker.output_format import LinkerOutputFormat
from gofra.linker.profile import LinkerProfile
from gofra.targets.target import Target


class LinkerCommandComposer(Protocol):
    @staticmethod
    def __call__(  # noqa: PLR0913
        objects: Iterable[Path],
        output: Path,
        target: Target,
        output_format: LinkerOutputFormat,
        libraries: MutableSequence[str],
        additional_flags: list[str],
        libraries_search_paths: list[Path],
        profile: LinkerProfile,
        executable_entry_point_symbol: str = ...,
        *,
        linker_executable: Path | None = ...,
    ) -> list[str]: ...


def get_linker_command_composer_backend(
    target: Target,  # noqa: ARG001
) -> LinkerCommandComposer:
    """Gut linker command composer backend suitable for that target and current host."""
    if system() == "Darwin":
        # Always use Apple linker on Darwin (e.g MacOS)
        return compose_apple_linker_command

    return compose_gnu_linker_command
