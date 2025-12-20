"""Gofra core entry."""

from collections.abc import Generator, Iterable
from pathlib import Path

from libgofra.hir.module import Module
from libgofra.hir.operator import FunctionCallOperand, OperatorType
from libgofra.lexer import tokenize_from_raw
from libgofra.lexer.io import open_source_file_line_stream
from libgofra.lexer.tokens import Token
from libgofra.parser.exceptions import ParserUnknownFunctionError
from libgofra.parser.parser import parse_module_from_tokenizer
from libgofra.preprocessor import preprocess_file
from libgofra.preprocessor.macros.registry import MacrosRegistry


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
    Requires compiling dependency modules (e.g returned_module.dependencies)

    Does not provide optimizer or type checker.
    """
    io = open_source_file_line_stream(filepath)
    lexer = tokenize_from_raw(filepath, lines=io)
    preprocessor = preprocess_file(
        filepath,
        lexer,
        include_paths,
        macros,
    )

    if _debug_emit_lexemes:
        preprocessor = _debug_lexer_wrapper(preprocessor)

    core_module = parse_module_from_tokenizer(
        filepath,
        preprocessor,
        macros=macros,
        include_paths=include_paths,
    )
    _validate_function_existence(core_module)
    return core_module


def _validate_function_existence(root: Module) -> None:
    # TODO(@kirillzhosul): This must be refactored - as implemented new dependency system
    for func in root.executable_functions:
        for op in func.operators:
            if op.type == OperatorType.FUNCTION_CALL:
                assert isinstance(op.operand, FunctionCallOperand), op.operand
                if op.operand.module is not None:
                    continue

                resolved_symbol = root.resolve_function_dependency(
                    op.operand.module,
                    op.operand.func_name,
                )
                if resolved_symbol is None:
                    raise ParserUnknownFunctionError(
                        token=op.token,
                        functions_available=[],
                        best_match=None,
                    )

    for mod in root.dependencies.values():
        _validate_function_existence(mod)


def _debug_lexer_wrapper(lexer: Generator[Token]) -> Generator[Token]:
    for token in lexer:
        print(token.type.name, token.value, token.location)
        yield token
