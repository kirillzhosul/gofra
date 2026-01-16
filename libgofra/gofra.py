"""Gofra core entry."""

from collections.abc import Generator, Iterable
from pathlib import Path

from libgofra.hir.module import Module
from libgofra.lexer import tokenize_from_raw
from libgofra.lexer.io import open_source_file_line_stream
from libgofra.lexer.lexer import debug_lexer_wrapper
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
    _debug_emit_lexemes: bool = False,
) -> Module:
    """Core entry for Gofra API.

    Compiles given filepath down to `IR` into `Module` (e.g translation unit).
    Maybe assembled into executable/library/object/etc... via `assemble_program`
    Requires compiling dependency modules (e.g returned_module.dependencies)

    Does not provide optimizer or type checker.
    """
    return parse_module_from_tokenizer(
        filepath,
        tokenizer=_get_tokenizer(
            filepath,
            include_paths,
            macros,
            debug_emit_lexemes=_debug_emit_lexemes,
        ),
        macros=macros,
        include_paths=include_paths,
        rt_array_oob_check=rt_array_oob_check,
    )


def _get_tokenizer(
    filepath: Path,
    include_paths: Iterable[Path],
    macros: MacrosRegistry,
    *,
    debug_emit_lexemes: bool,
) -> Generator[Token]:
    io = open_source_file_line_stream(filepath)
    lexer = tokenize_from_raw(filepath, lines=io)
    preprocessor = preprocess_file(
        filepath,
        lexer,
        include_paths,
        macros,
    )

    if debug_emit_lexemes:
        return debug_lexer_wrapper(preprocessor)
    return preprocessor
