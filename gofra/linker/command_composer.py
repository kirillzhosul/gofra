from collections.abc import Iterable, MutableSequence
from pathlib import Path
from platform import system
from typing import Protocol

from gofra.linker.apple.command_composer import compose_apple_linker_command
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
    ) -> list[str]: ...


def get_linker_command_composer_backend(
    target: Target,
) -> LinkerCommandComposer:
    assert system() == "Darwin", "TODO: cannot link on non-darwin systems"
    assert target.operating_system == "Darwin", "TODO: can link for darwin systems only"

    return compose_apple_linker_command
