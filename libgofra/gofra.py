"""Gofra core entry."""

from collections.abc import Generator, Iterable
from pathlib import Path

from gofra.cli.output import cli_message
from libgofra.hir.module import Module
from libgofra.import_path_resolver import (
    try_resolve_and_find_real_include_path,
)
from libgofra.lexer import tokenize_from_raw
from libgofra.lexer.io import open_source_file_line_stream
from libgofra.lexer.tokens import Token
from libgofra.parser.parser import parse_module_from_tokenizer
from libgofra.preprocessor import preprocess_file
from libgofra.preprocessor.macros.registry import MacrosRegistry


def process_input_file(
    filepath: Path,
    include_paths: Iterable[Path],
    *,
    macros: MacrosRegistry,
    rt_array_oob_check: bool = False,
    entry_point_name: str = "main",
) -> Module:
    """Core entry for Gofra API.

    Compiles given filepath down to `IR` into `Module` (e.g translation unit).
    Maybe assembled into executable/library/object/etc... via `assemble_program`
    Requires compiling dependency modules (e.g returned_module.dependencies)

    Does not provide optimizer or type checker.
    """
    module = Module(path=filepath)

    def on_import_request(
        named_import_as_name: str,
        requested_import_path: Path,
    ) -> None:
        import_path = try_resolve_and_find_real_include_path(
            requested_import_path,
            current_path=Path(),
            search_paths=include_paths,
        )
        if import_path is None:
            msg = f"Cannot find import path for module '{requested_import_path}' at ..."
            raise ValueError(msg)

        already_imported_paths = (m.path for m in module.dependencies.values())
        if import_path in already_imported_paths:
            cli_message(
                "WARNING",
                "Tried to import already imported module -> rejecting",
            )
            return

        imported_module = process_input_file(
            import_path,
            include_paths=include_paths,
            macros=macros.copy(),
            rt_array_oob_check=rt_array_oob_check,
            entry_point_name=entry_point_name,
        )
        assert named_import_as_name not in module.dependencies
        module.dependencies[named_import_as_name] = imported_module

    return parse_module_from_tokenizer(
        module,
        tokenizer=_get_tokenizer(filepath, include_paths, macros),
        rt_array_oob_check=rt_array_oob_check,
        entry_point_name=entry_point_name,
        on_import_request=on_import_request,
    )


def _get_tokenizer(
    filepath: Path,
    include_paths: Iterable[Path],
    macros: MacrosRegistry,
) -> Generator[Token]:
    io = open_source_file_line_stream(filepath)
    lexer = tokenize_from_raw(filepath, lines=io)
    return preprocess_file(
        filepath,
        lexer,
        include_paths,
        macros,
    )
