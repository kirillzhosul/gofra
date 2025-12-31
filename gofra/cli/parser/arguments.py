from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from libgofra.linker.profile import LinkerProfile
from libgofra.optimizer.config import OptimizerConfig
from libgofra.targets.target import Target


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

    display_lint_warnings: bool
    incremental_compilation: bool

    hir: bool
    preprocess_only: bool

    assembler_flags: list[str]

    verbose: bool
    show_commands: bool

    target: Target

    skip_typecheck: bool

    build_cache_dir: Path
    delete_build_cache: bool

    linker_profile: LinkerProfile

    runtime_array_oob_checks: bool

    linker_additional_flags: list[str]
    linker_libraries: list[str]
    linker_libraries_search_paths: list[Path]
    linker_backend: Literal["gnu-ld", "apple-ld"] | None
    linker_resolve_libraries_with_pkgconfig: bool
    linker_executable: Path | None

    optimizer: OptimizerConfig
    lexer_debug_emit_lexemes: bool
    cli_debug_user_friendly_errors: bool
