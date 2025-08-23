"""Gofra core entry."""

from collections.abc import Iterable
from pathlib import Path

from gofra.context import ProgramContext
from gofra.lexer import tokenize_file
from gofra.parser import parse_file
from gofra.preprocessor import preprocess_file


def process_input_file(
    filepath: Path,
    include_paths: Iterable[Path],
) -> ProgramContext:
    """Core entry for Gofra API.

    Compiles given filepath down to `IR` into `ProgramContext`.
    Maybe assembled into executable/library/object/etc... via `assemble_program`

    Does not provide optimizer or type checker.
    """
    lexer = tokenize_file(filepath)
    preprocessor = preprocess_file(filepath, lexer, include_paths)
    parser_context, entry_point = parse_file(preprocessor)
    return ProgramContext.from_parser_context(parser_context, entry_point)
