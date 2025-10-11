"""Gofra core entry."""

from collections.abc import Generator, Iterable
from pathlib import Path

from gofra.hir.module import Module
from gofra.lexer import tokenize_from_raw
from gofra.lexer.io import open_source_file_line_stream
from gofra.lexer.tokens import Token
from gofra.parser.parser import parse_module_from_tokenizer
from gofra.preprocessor import preprocess_file
from gofra.preprocessor.macros.registry import MacrosRegistry


def process_input_file(
    filepath: Path,
    include_paths: Iterable[Path],
    *,
    macros: MacrosRegistry,
    _debug_emit_lexemes: bool = False,
) -> Module:
    """Core entry for Gofra API.

    Compiles given filepath down to `IR` into `Module` (e.g translation unit).
    Maybe assembled into executable/library/object/etc... via `assemble_program`

    Does not provide optimizer or type checker.
    """
    io = open_source_file_line_stream(filepath)
    lexer = tokenize_from_raw(filepath, iterable=io)
    preprocessor = preprocess_file(
        filepath,
        lexer,
        include_paths,
        macros,
    )

    if _debug_emit_lexemes:
        preprocessor = _debug_lexer_wrapper(preprocessor)

    return parse_module_from_tokenizer(filepath, preprocessor)


def _debug_lexer_wrapper(lexer: Generator[Token]) -> Generator[Token]:
    for token in lexer:
        print(token.type.name, token.value, token.location)
        yield token
