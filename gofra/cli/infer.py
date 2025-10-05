import sys
from pathlib import Path
from platform import system
from typing import Literal

from gofra.cli.output import cli_message
from gofra.targets.target import Target


def infer_output_filename(
    source_filepaths: list[Path],
    output_format: Literal["library", "object", "executable", "assembly"],
    target: Target,
) -> Path:
    """Try to infer filename for output from input source files."""
    match output_format:
        case "library":
            is_dynamic = False
            suffix = [
                target.file_library_static_suffix,
                target.file_library_dynamic_suffix,
            ][is_dynamic]
        case "object":
            suffix = target.file_object_suffix
        case "assembly":
            suffix = target.file_assembly_suffix
        case "executable":
            suffix = target.file_executable_suffix

    if not source_filepaths:
        return Path("out").with_suffix(suffix)

    source_filepath = source_filepaths[0]

    if source_filepath.suffix == suffix:
        suffix = source_filepath.suffix + suffix
    return source_filepath.with_suffix(suffix)


def infer_target() -> Target:
    """Try to infer target from current system."""
    assert system() in ["Darwin", "Linux"]

    match system():
        case "Darwin":
            return Target.from_triplet("arm64-apple-darwin")
        case "Linux":
            return Target.from_triplet("amd64-unknown-linux")
        case _:
            cli_message(
                level="ERROR",
                text="Unable to infer compilation target due to no fallback for current operating system",
            )
            sys.exit(1)
