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
    rt_array_oob_check: bool = False,
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
        rt_array_oob_check=rt_array_oob_check,
    )
    _validate_function_existence_and_visibility(root=core_module, module=core_module)
    return core_module


def _validate_function_existence_and_visibility(root: Module, module: Module) -> None:
    # TODO(@kirillzhosul): This must be refactored - as implemented new dependency system
    for func in module.executable_functions:
        for op in func.operators:
            if op.type == OperatorType.FUNCTION_CALL:
                assert isinstance(op.operand, FunctionCallOperand), op.operand
                resolved_symbol = module.resolve_function_dependency(
                    op.operand.module,
                    op.operand.func_name,
                )
                if resolved_symbol is None:
                    print(f"[help] Tried to resolve import from {op.operand.module}")
                    raise ParserUnknownFunctionError(
                        at=op.token.location,
                        name=op.operand.func_name,
                        functions_available=[],
                        best_match=None,
                    )
                if op.operand.module is not None:
                    func_owner_mod = module.dependencies[op.operand.module]
                    if (
                        not resolved_symbol.is_public
                        and func_owner_mod.path != root.path
                    ):
                        msg = f"Tried to call private/internal function symbol {resolved_symbol.name} (defined at {resolved_symbol.defined_at}) from module named as `{op.operand.module}` (import from {func_owner_mod.path}):\nEither make it public or not use prohibited symbols!"
                        raise ValueError(msg)

    for children_module in module.dependencies.values():
        _validate_function_existence_and_visibility(root=root, module=children_module)


def _debug_lexer_wrapper(lexer: Generator[Token]) -> Generator[Token]:
    for token in lexer:
        print(token.type.name, token.value, token.location)
        yield token
