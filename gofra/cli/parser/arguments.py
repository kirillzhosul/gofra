from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from libgofra.codegen.config import CodegenConfig
from libgofra.linker.profile import LinkerProfile
from libgofra.optimizer.config import OptimizerConfig
from libgofra.targets.target import Target


@dataclass(slots=True, frozen=True)
class CLIArguments:
    """Arguments from argument parser provided for whole Gofra toolchain process."""

    source_filepaths: list[Path]
    output_filepath: Path
    output_format: Literal["library", "object", "executable", "assembly"]
    output_file_is_specified: bool  # Internal flag

    execute_after_compilation: bool
    propagate_execute_child_exit_code: bool

    include_paths: list[Path]
    definitions: dict[str, str]

    version: bool
    repl: bool
    hir: bool
    preprocess_only: bool
    call_graph_only: bool

    verbose: bool
    show_commands: bool

    target: Target

    skip_typecheck: bool
    display_lint_warnings: bool

    build_cache_dir: Path
    delete_build_cache: bool

    lexer_debug_emit_lexemes: bool
    cli_debug_user_friendly_errors: bool

    runtime_array_oob_checks: bool

    linker_profile: LinkerProfile
    linker_additional_flags: list[str]
    linker_libraries: list[str]
    linker_libraries_search_paths: list[Path]
    linker_backend: Literal["gnu-ld", "apple-ld"] | None
    linker_resolve_libraries_with_pkgconfig: bool
    linker_executable: Path | None

    debug_symbols: bool
    incremental_compilation: bool
    optimizer: OptimizerConfig

    assembler_flags: list[str]

    codegen_config: CodegenConfig
