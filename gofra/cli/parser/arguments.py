from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from gofra.linker.profile import LinkerProfile
from gofra.optimizer.config import OptimizerConfig
from gofra.targets.target import Target


@dataclass(slots=True, frozen=True)
class CLIArguments:
    """Arguments from argument parser provided for whole Gofra toolchain process."""

    source_filepaths: list[Path]
    output_filepath: Path
    output_format: Literal["library", "object", "executable", "assembly"]
    output_file_is_specified: bool

    execute_after_compilation: bool
    debug_symbols: bool

    include_paths: list[Path]
    definitions: dict[str, str]

    version: bool
    repl: bool

    hir: bool
    preprocess_only: bool

    assembler_flags: list[str]

    verbose: bool

    target: Target

    skip_typecheck: bool

    build_cache_dir: Path
    delete_build_cache: bool

    linker_profile: LinkerProfile

    linker_additional_flags: list[str]
    linker_libraries: list[str]
    linker_libraries_search_paths: list[Path]
    linker_backend: Literal["gnu-ld", "apple-ld"] | None
    linker_resolve_libraries_with_pkgconfig: bool
    linker_executable: Path | None

    optimizer: OptimizerConfig
    lexer_debug_emit_lexemes: bool
    cli_debug_user_friendly_errors: bool
